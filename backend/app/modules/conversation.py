"""AI conversation engine for SMS booking dialogue.

Uses Claude with tool_use for on-demand data fetching instead of
prompt-stuffing. Falls back to a configurable model per tenant.
"""

import json
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.contact import Contact
from app.models.system_setting import SystemSetting
from app.models.tenant import Tenant
from app.models.token_usage import TokenUsageSource
from app.modules.tool_definitions import ADMIN_TOOLS, CUSTOMER_TOOLS
from app.modules.tool_executor import DEFAULT_MODEL, run_tool_conversation
from app.modules.tool_handlers import ToolContext
from app.prompts.conversation import (
    CUSTOMER_SYSTEM_PROMPT,
    ADMIN_SYSTEM_PROMPT,
    get_customer_system_prompt,
    get_admin_system_prompt,
    get_error_message,
)
from app.services.token_usage import record_token_usage

logger = get_logger("conversation")

# How many trailing messages from a conversation to include in the LLM
# context. Admin caps lower because:
#   1. The CURRENT SYSTEM STATE preamble already gives ground truth, so
#      the LLM doesn't need long history to answer correctly.
#   2. Stale admin replies (old "no phone configured" text, etc.) bias
#      the model into parroting them — see design_decisions.md #8.
#   3. Test-tool admin sessions accumulate hundreds of turns over time.
# Customer caps higher because conversations are short, naturally bounded
# by the 7-day conversation-expiry job, and parroting risk is lower.
LLM_HISTORY_CAP_ADMIN = 20
LLM_HISTORY_CAP_CUSTOMER = 40

# Hard upper bound on the stored Conversation.message_history JSONB array.
# Without this, a long-lived conversation row can grow unbounded —
# JSONB column gets larger on every save, query latency degrades, and
# eventually we hit asyncpg's row-size limits. We FIFO-trim (drop oldest)
# when an append would exceed this cap. The 7-day conversation_expiry
# job is the other line of defense but doesn't actually delete rows.
# See design_decisions.md decision #14.
MESSAGE_HISTORY_HARD_CAP = 200


def trim_message_history(history: list[dict]) -> list[dict]:
    """FIFO-trim a conversation's message_history to MESSAGE_HISTORY_HARD_CAP.

    Returns the input unchanged when it's under the cap. Otherwise returns
    a new list containing the last ``MESSAGE_HISTORY_HARD_CAP`` items.
    Safe to call on every append site — cheap when under the cap.
    """
    if len(history) <= MESSAGE_HISTORY_HARD_CAP:
        return history
    return history[-MESSAGE_HISTORY_HARD_CAP:]


# ── Configurable model ──


async def get_ai_model(db: AsyncSession, tenant: Tenant | None) -> str:
    """Get the AI model for a tenant, falling back to the default."""
    if not tenant:
        return DEFAULT_MODEL
    result = await db.execute(
        select(SystemSetting).where(
            SystemSetting.tenant_id == tenant.id,
            SystemSetting.key == "ai_model",
        )
    )
    setting = result.scalar_one_or_none()
    return setting.value if setting else DEFAULT_MODEL


# ── Response dataclass ──


@dataclass
class AIResult:
    """Result from the tool_use conversation AI."""
    message_to_user: str
    booking_created: bool = False
    booking_cancelled: bool = False
    booking_rescheduled: bool = False


# ── Main entry point ──


async def get_ai_response_with_tools(
    db: AsyncSession,
    contact_phone: str,
    contact_id: uuid.UUID,
    message_history: list[dict],
    user_message: str,
    tenant: Tenant,
    is_admin: bool = False,
) -> AIResult:
    """Call Claude with tool_use for a conversation turn.

    Builds a lightweight system prompt, selects the appropriate tool set,
    and runs the tool_use conversation loop.
    """
    tenant_id = tenant.id

    # Get custom instructions
    custom_result = await db.execute(
        select(SystemSetting).where(
            SystemSetting.tenant_id == tenant_id,
            SystemSetting.key == "custom_ai_instructions",
        )
    )
    custom_setting = custom_result.scalar_one_or_none()
    custom_instructions = custom_setting.value if custom_setting else ""

    # Build system prompt
    if is_admin:
        prompt_template = await get_admin_system_prompt(db, tenant_id)
    else:
        prompt_template = await get_customer_system_prompt(db, tenant_id)

    system_prompt = prompt_template.format(
        business_name=tenant.business_name or "our business",
        custom_instructions=custom_instructions,
    )

    # Append today's date for temporal context
    today = date.today()
    system_prompt += f"\nToday's date is {today.strftime('%A %B %d, %Y')}."

    # For admin turns, inject the fresh "CURRENT SYSTEM STATE" preamble so
    # the LLM grounds its replies in current DB facts (phone status,
    # active campaigns, upcoming events) instead of repeating stale text
    # from conversation history.
    if is_admin:
        from app.agents.recruiter.chat_tools import build_admin_state_preamble
        from app.models.admin_user import AdminUser as _AdminUser
        _admin = await db.get(_AdminUser, contact_id) if contact_id else None
        try:
            preamble = await build_admin_state_preamble(db, tenant, _admin)
            system_prompt += "\n\n" + preamble
        except Exception:
            logger.exception(
                "Failed to build admin state preamble; falling through"
            )

    # For customer conversations, append known long-term context
    if not is_admin:
        contact_result = await db.execute(
            select(Contact).where(
                Contact.phone == contact_phone,
                Contact.tenant_id == tenant_id,
            )
        )
        contact = contact_result.scalar_one_or_none()
        if contact:
            if contact.name:
                system_prompt += f"\nThe customer's name is {contact.name}."
            if contact.notes:
                system_prompt += f"\nWhat we know about this customer: {contact.notes}"
            if contact.preferences:
                system_prompt += (
                    f"\nKnown preferences (use to suggest, don't assume): "
                    f"{json.dumps(contact.preferences)}"
                )

    # Select tools
    tools = ADMIN_TOOLS if is_admin else CUSTOMER_TOOLS

    # Cap conversation history sent to the LLM. We keep full history on the
    # Conversation row (for display, audit, future analytics) but only the
    # recent slice goes into the LLM context. For admins specifically, the
    # CURRENT SYSTEM STATE preamble injected above carries the ground-truth
    # facts the LLM needs — so a long stale tail of history mostly adds
    # token cost AND increases the surface for parroting old (now-wrong)
    # statements. See design_decisions.md decision #13.
    history_cap = LLM_HISTORY_CAP_ADMIN if is_admin else LLM_HISTORY_CAP_CUSTOMER
    trimmed_history = (
        message_history[-history_cap:] if len(message_history) > history_cap else message_history
    )

    # Build API messages from history (text only, no tool_use replay)
    api_messages = []
    for msg in trimmed_history:
        api_messages.append({
            "role": msg["role"],
            "content": msg["content"],
        })
    api_messages.append({"role": "user", "content": user_message})

    # Create tool context
    ctx = ToolContext(
        db=db,
        tenant=tenant,
        contact_phone=contact_phone,
        contact_id=contact_id,
        is_admin=is_admin,
    )

    # Get model and API key
    model = await get_ai_model(db, tenant)
    api_key = tenant.anthropic_api_key or settings.anthropic_api_key

    # Per-tenant LLM rate limit guard — see design_decisions.md #15.
    # Raises LLMRateLimitExceeded if the tenant has burned through its
    # per-minute cap; we surface a polite reply rather than retrying.
    # The cap is super-admin-configurable via Settings → System Settings
    # (llm_rate_limit_rpm), with a safe global default.
    from app.services.llm_rate_limit import (
        consume,
        get_tenant_limit,
        LLMRateLimitExceeded,
    )
    try:
        tenant_limit = await get_tenant_limit(db, tenant_id)
        await consume(tenant_id, limit=tenant_limit)
    except LLMRateLimitExceeded as e:
        return AIResult(
            message_to_user=(
                "I'm getting too many requests right now. Please try "
                f"again in about {int(e.retry_after_seconds)} seconds."
            ),
        )

    # Run the conversation loop
    try:
        result = await run_tool_conversation(
            system_prompt=system_prompt,
            tools=tools,
            messages=api_messages,
            ctx=ctx,
            api_key=api_key,
            model=model,
        )
        result_text = result.text

        # Record token usage
        source = TokenUsageSource.TEST_TOOL if is_admin else TokenUsageSource.CONVERSATION
        await record_token_usage(
            db=db,
            tenant_id=tenant_id,
            source=source,
            model=result.model,
            input_tokens=result.total_input_tokens,
            output_tokens=result.total_output_tokens,
            contact_id=contact_id,
            contact_phone=contact_phone,
            tool_calls=ctx.tool_calls if ctx.tool_calls else None,
        )
    except Exception as e:
        logger.error("Tool conversation failed: %s", e)
        result_text = await get_error_message(db, tenant_id)

    return AIResult(
        message_to_user=result_text,
        booking_created=ctx.booking_created,
        booking_cancelled=ctx.booking_cancelled,
        booking_rescheduled=ctx.booking_rescheduled,
    )
