"""Test conversation endpoint — lets admins test the AI tool_use flow without real SMS."""

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.core.config import settings
from app.core.dependencies import CurrentTenant, DbSession, ManagerUser
from app.core.logging import get_logger
from app.models.contact import Contact, ContactStatus
from app.models.conversation import Conversation, ConversationStatus
from app.models.system_setting import SystemSetting
from app.modules.conversation import get_ai_model
from app.modules.screener import Classification, screen_message
from app.modules.pipeline import _handle_strike, STRIKE_MESSAGES, SUSPENSION_MESSAGE
from app.modules.tool_definitions import ADMIN_TOOLS, CUSTOMER_TOOLS
from app.models.token_usage import TokenUsageSource
from app.modules.tool_executor import run_tool_conversation
from app.modules.tool_handlers import ToolContext
from app.prompts.conversation import get_admin_system_prompt, get_customer_system_prompt
from app.services.token_usage import record_token_usage

logger = get_logger("test_conversation")

router = APIRouter(prefix="/api/v1/test-conversation", tags=["test-conversation"])


class TestConversationRequest(BaseModel):
    message: str
    mode: str  # "customer" or "admin"
    history: list[dict] = []
    phone: str | None = None  # optional phone for customer simulation
    use_test_user: bool = False  # simulate a new unknown volunteer
    save_conversation: bool = False


class ToolCallInfo(BaseModel):
    tool: str
    input: dict
    output: str


class TestConversationResponse(BaseModel):
    reply: str
    tool_calls: list[ToolCallInfo]
    screened: bool = False
    strike_number: int | None = None


@router.post("", response_model=TestConversationResponse)
async def test_conversation(
    body: TestConversationRequest,
    db: DbSession,
    current_user: ManagerUser,
    tenant: CurrentTenant,
):
    """Run a test conversation turn through the AI tool_use engine.

    No SMS is sent. Tool calls are executed against real data but
    announcement SMS sending is skipped in test mode.
    Screener and strike system are active for customer mode.
    """
    if body.mode not in ("customer", "admin"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mode must be 'customer' or 'admin'",
        )

    is_admin = body.mode == "admin"
    tenant_id = tenant.id

    # Resolve contact for customer mode
    contact_phone = body.phone or "+10000000000"

    if not is_admin:
        if body.use_test_user:
            # Simulate an unknown new volunteer — create a temporary in-memory contact
            import uuid as _uuid
            contact_id = _uuid.uuid4()
            contact_phone = "+10000000000"
            # Skip screener/suspension for test user — go straight to AI
        elif not body.phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Customer phone is required in customer mode.",
            )
        else:
            result = await db.execute(
                select(Contact).where(
                    Contact.phone == body.phone,
                    Contact.tenant_id == tenant_id,
                )
            )
            contact = result.scalar_one_or_none()
            if not contact:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No customer found with phone '{body.phone}' for this tenant.",
                )
            contact_id = contact.id
            contact_phone = contact.phone

            # Check if customer is suspended
            if contact.status in (ContactStatus.SUSPENDED, ContactStatus.BANNED):
                return TestConversationResponse(
                    reply=f"[SUSPENDED] This customer is {contact.status.value}. Messages are blocked.",
                    tool_calls=[],
                    screened=True,
                )

        # Run screener on customer messages (skip for test user). Pass the
        # request's history so short contextual replies ("1", "yes") aren't
        # misclassified as IRRELEVANT — same fix as the production pipeline.
        if not body.use_test_user:
            screener_result = await screen_message(
                body.message, db, tenant=tenant,
                contact_id=contact_id, contact_phone=contact_phone,
                conversation_history=body.history or None,
            )

            if screener_result.classification in (Classification.IRRELEVANT, Classification.ABUSIVE):
                # Record strike and escalate
                await _handle_strike(
                    db, contact, body.message,
                    screener_result.classification,
                    screener_result.method.value,
                    tenant=tenant,
                    tenant_id=tenant_id,
                    test_mode=True,
                )
                await db.flush()

                # Refresh contact to get updated status
                await db.refresh(contact)

                # Determine the reply based on strike outcome
                from sqlalchemy import func
                from app.models.strike import ContactStrike
                thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
                strike_count_result = await db.execute(
                    select(func.count()).where(
                        ContactStrike.contact_phone == contact.phone,
                        ContactStrike.tenant_id == tenant_id,
                        ContactStrike.decayed_at.is_(None),
                        ContactStrike.created_at >= thirty_days_ago,
                    )
                )
                strike_count = strike_count_result.scalar() or 0

                if contact.status == ContactStatus.SUSPENDED:
                    reply = f"[SCREENED — {screener_result.classification.value}] {SUSPENSION_MESSAGE}"
                elif strike_count in STRIKE_MESSAGES:
                    reply = f"[SCREENED — {screener_result.classification.value}] {STRIKE_MESSAGES[strike_count]}"
                else:
                    reply = f"[SCREENED — {screener_result.classification.value}] Strike {strike_count} recorded."

                return TestConversationResponse(
                    reply=reply,
                    tool_calls=[],
                    screened=True,
                    strike_number=strike_count,
                )
    else:
        contact_id = current_user.id

    # Build system prompt
    if is_admin:
        prompt_template = await get_admin_system_prompt(db, tenant_id)
    else:
        prompt_template = await get_customer_system_prompt(db, tenant_id)

    custom_result = await db.execute(
        select(SystemSetting).where(
            SystemSetting.tenant_id == tenant_id,
            SystemSetting.key == "custom_ai_instructions",
        )
    )
    custom_setting = custom_result.scalar_one_or_none()
    custom_instructions = custom_setting.value if custom_setting else ""

    system_prompt = prompt_template.format(
        business_name=tenant.business_name or "our business",
        custom_instructions=custom_instructions,
    )
    today = date.today()
    system_prompt += f"\nToday's date is {today.strftime('%A %B %d, %Y')}."
    system_prompt += "\n[TEST MODE] This is a test conversation. No real SMS will be sent."

    # Inject a fresh-state preamble for admin turns so the LLM grounds
    # its replies in current DB state instead of parroting stale history.
    if is_admin:
        from app.agents.recruiter.chat_tools import build_admin_state_preamble
        from app.models.admin_user import AdminUser as _AdminUser
        _admin = await db.get(_AdminUser, current_user.id)
        preamble = await build_admin_state_preamble(db, tenant, _admin)
        system_prompt += "\n\n" + preamble

    if not is_admin and body.use_test_user:
        system_prompt += "\nThis is a new volunteer who is not yet in the system."
    elif not is_admin and body.phone:
        result = await db.execute(
            select(Contact).where(
                Contact.phone == body.phone,
                Contact.tenant_id == tenant_id,
            )
        )
        contact_for_name = result.scalar_one_or_none()
        if contact_for_name and contact_for_name.name:
            system_prompt += f"\nThe customer's name is {contact_for_name.name}."

        # Surface the pending recruitment solicitation so a "yes" reply
        # in the test panel resolves to the wave's actual service, not
        # whichever same-named service the LLM would guess from the
        # outbound SMS text. Mirrors the production pipeline path.
        if contact_for_name:
            from app.agents.recruiter.chat_tools import (
                build_customer_state_preamble,
            )
            try:
                volunteer_preamble = await build_customer_state_preamble(
                    db, tenant, contact_for_name.id
                )
                if volunteer_preamble:
                    system_prompt += "\n\n" + volunteer_preamble
            except Exception:
                logger.exception(
                    "Failed to build customer state preamble in test mode"
                )

            # Server-side intent router for YES/STOP replies to a
            # reschedule reconfirmation. Same as production pipeline so
            # the test panel exercises the real short-circuit path.
            from app.services.reconfirm import (
                maybe_handle_reconfirmation_directly,
            )
            try:
                reconfirm_reply = await maybe_handle_reconfirmation_directly(
                    db, tenant, contact_for_name, body.message
                )
                if reconfirm_reply is not None:
                    return TestConversationResponse(
                        reply=reconfirm_reply,
                        tool_calls=[
                            ToolCallInfo(
                                tool="reconfirm_or_cancel",
                                input={},
                                output='{"ok": true, "auto_routed": true}',
                            )
                        ],
                    )
            except Exception:
                logger.exception(
                    "Reconfirmation intent router failed in test mode"
                )

    # Select tools
    tools = ADMIN_TOOLS if is_admin else CUSTOMER_TOOLS

    # Cap history sent to the LLM — see design_decisions.md #13. Test-tool
    # sessions accumulate quickly; without a cap a single conversation can
    # ship hundreds of turns of context per request.
    from app.modules.conversation import (
        LLM_HISTORY_CAP_ADMIN,
        LLM_HISTORY_CAP_CUSTOMER,
    )
    cap = LLM_HISTORY_CAP_ADMIN if is_admin else LLM_HISTORY_CAP_CUSTOMER
    trimmed_history = (
        body.history[-cap:] if len(body.history) > cap else body.history
    )

    # Build API messages
    api_messages = []
    for msg in trimmed_history:
        api_messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", ""),
        })
    api_messages.append({"role": "user", "content": body.message})

    # Create tool context with test_mode=True
    ctx = ToolContext(
        db=db,
        tenant=tenant,
        contact_phone=contact_phone,
        contact_id=contact_id,
        is_admin=is_admin,
        test_mode=True,
    )

    # Get model and API key
    model = await get_ai_model(db, tenant)
    api_key = tenant.anthropic_api_key or settings.anthropic_api_key

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Anthropic API key configured. Set it in tenant settings or environment.",
        )

    # Server-side intent routers for recruitment intents. The LLM has
    # consistently failed to call approve_recruitment_campaign and
    # recruitment_status despite explicit prompt rules; these
    # short-circuits unambiguous phrases and skip the LLM round-trip.
    if is_admin:
        from app.agents.recruiter.chat_tools import (
            maybe_handle_approval_directly,
            maybe_handle_status_directly,
        )
        from app.models.admin_user import AdminUser as _AdminUser
        admin_user = await db.get(_AdminUser, current_user.id)
        approval_reply = await maybe_handle_approval_directly(
            db, tenant, body.message, admin_user
        )
        if approval_reply is not None:
            return TestConversationResponse(
                reply=approval_reply,
                tool_calls=[
                    ToolCallInfo(
                        tool="approve_recruitment_campaign",
                        input={},
                        output='{"ok": true, "auto_routed": true}',
                    )
                ],
            )
        status_reply = await maybe_handle_status_directly(
            db, tenant, body.message
        )
        if status_reply is not None:
            return TestConversationResponse(
                reply=status_reply,
                tool_calls=[
                    ToolCallInfo(
                        tool="recruitment_status",
                        input={},
                        output='{"ok": true, "auto_routed": true}',
                    )
                ],
            )

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

        # Record token usage for test tool
        await record_token_usage(
            db=db,
            tenant_id=tenant_id,
            source=TokenUsageSource.TEST_TOOL,
            model=result.model,
            input_tokens=result.total_input_tokens,
            output_tokens=result.total_output_tokens,
            contact_id=contact_id if not is_admin else None,
            contact_phone=contact_phone,
            tool_calls=ctx.tool_calls if ctx.tool_calls else None,
        )
    except Exception as e:
        logger.exception("Test conversation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Conversation engine error: {str(e)}",
        )

    # Save conversation if requested. Skip the test_user case (we don't
    # want to pollute that synthetic phone). Persist both customer and
    # admin modes so the multi-volunteer test page can rehydrate the
    # admin chat on reload — admin entries go under sender_type="admin"
    # so they don't mix with volunteer-side queries.
    if body.save_conversation and not body.use_test_user:
        try:
            now = datetime.now(timezone.utc)
            now_iso = now.isoformat()
            # Each appended message carries a timestamp so the
            # /recent-messages endpoint can include it (entries without
            # timestamps are dropped by that filter).
            full_history = list(body.history)
            full_history.append(
                {"role": "user", "content": body.message, "timestamp": now_iso}
            )
            full_history.append(
                {"role": "assistant", "content": result_text, "timestamp": now_iso}
            )

            from app.modules.conversation import trim_message_history
            conversation = Conversation(
                tenant_id=tenant_id,
                contact_id=contact_id if not is_admin else None,
                contact_phone=contact_phone,
                message_history=trim_message_history(full_history),
                status=ConversationStatus.ACTIVE,
                sender_type="admin" if is_admin else "customer",
                last_message_at=now,
            )
            db.add(conversation)
            await db.flush()
        except Exception as e:
            logger.error("Failed to save test conversation: %s", e)

    return TestConversationResponse(
        reply=result_text,
        tool_calls=[ToolCallInfo(**tc) for tc in ctx.tool_calls],
    )
