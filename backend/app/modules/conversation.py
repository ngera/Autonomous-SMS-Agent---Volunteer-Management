"""AI conversation engine for SMS booking dialogue.

Uses Claude with tool_use for on-demand data fetching instead of
prompt-stuffing. Falls back to a configurable model per tenant.
"""

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

logger = get_logger("conversation")

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

    # For customer conversations, append their name if known
    if not is_admin:
        contact_result = await db.execute(
            select(Contact).where(
                Contact.phone == contact_phone,
                Contact.tenant_id == tenant_id,
            )
        )
        contact = contact_result.scalar_one_or_none()
        if contact and contact.name:
            system_prompt += f"\nThe customer's name is {contact.name}."

    # Select tools
    tools = ADMIN_TOOLS if is_admin else CUSTOMER_TOOLS

    # Build API messages from history (text only, no tool_use replay)
    api_messages = []
    for msg in message_history:
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

    # Run the conversation loop
    try:
        result_text = await run_tool_conversation(
            system_prompt=system_prompt,
            tools=tools,
            messages=api_messages,
            ctx=ctx,
            api_key=api_key,
            model=model,
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
