"""Test conversation endpoint — lets admins test the AI tool_use flow without real SMS."""

from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.core.config import settings
from app.core.dependencies import CurrentTenant, DbSession, ManagerUser
from app.core.logging import get_logger
from app.models.contact import Contact
from app.models.conversation import Conversation, ConversationStatus
from app.models.system_setting import SystemSetting
from app.modules.conversation import get_ai_model
from app.modules.tool_definitions import ADMIN_TOOLS, CUSTOMER_TOOLS
from app.modules.tool_executor import run_tool_conversation
from app.modules.tool_handlers import ToolContext
from app.prompts.conversation import get_admin_system_prompt, get_customer_system_prompt

logger = get_logger("test_conversation")

router = APIRouter(prefix="/api/v1/test-conversation", tags=["test-conversation"])


class TestConversationRequest(BaseModel):
    message: str
    mode: str  # "customer" or "admin"
    history: list[dict] = []
    phone: str | None = None  # optional phone for customer simulation
    save_conversation: bool = False


class ToolCallInfo(BaseModel):
    tool: str
    input: dict
    output: str


class TestConversationResponse(BaseModel):
    reply: str
    tool_calls: list[ToolCallInfo]


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
        if not body.phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Customer phone is required in customer mode.",
            )
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

    if not is_admin and body.phone:
        result = await db.execute(
            select(Contact).where(
                Contact.phone == body.phone,
                Contact.tenant_id == tenant_id,
            )
        )
        contact = result.scalar_one_or_none()
        if contact and contact.name:
            system_prompt += f"\nThe customer's name is {contact.name}."

    # Select tools
    tools = ADMIN_TOOLS if is_admin else CUSTOMER_TOOLS

    # Build API messages
    api_messages = []
    for msg in body.history:
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
        logger.exception("Test conversation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Conversation engine error: {str(e)}",
        )

    # Save conversation if requested (customer mode only — admin has no contact FK)
    if body.save_conversation and not is_admin:
        try:
            full_history = list(body.history)
            full_history.append({"role": "user", "content": body.message})
            full_history.append({"role": "assistant", "content": result_text})

            conversation = Conversation(
                tenant_id=tenant_id,
                contact_id=contact_id,
                contact_phone=contact_phone,
                message_history=full_history,
                status=ConversationStatus.ACTIVE,
                sender_type="customer",
                last_message_at=datetime.now(timezone.utc),
            )
            db.add(conversation)
            await db.flush()
        except Exception as e:
            logger.error("Failed to save test conversation: %s", e)

    return TestConversationResponse(
        reply=result_text,
        tool_calls=[ToolCallInfo(**tc) for tc in ctx.tool_calls],
    )
