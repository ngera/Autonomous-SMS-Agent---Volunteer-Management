"""Service for recording token usage from Anthropic API calls."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.token_usage import TokenUsage, TokenUsageSource

logger = get_logger("token_usage")


async def record_token_usage(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    source: TokenUsageSource,
    model: str,
    input_tokens: int,
    output_tokens: int,
    conversation_id: uuid.UUID | None = None,
    contact_id: uuid.UUID | None = None,
    contact_phone: str | None = None,
    tool_calls: list[dict] | None = None,
) -> None:
    """Record a single API call's token usage."""
    try:
        # Slim down tool_calls to just names for storage
        slim_tools = None
        if tool_calls:
            slim_tools = [
                {"tool": tc.get("tool"), "input": tc.get("input")}
                for tc in tool_calls
            ]

        usage = TokenUsage(
            tenant_id=tenant_id,
            source=source,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            conversation_id=conversation_id,
            contact_id=contact_id,
            contact_phone=contact_phone,
            tool_calls=slim_tools,
        )
        db.add(usage)
        await db.flush()
    except Exception as e:
        logger.warning("Failed to record token usage: %s", e)
        # Expunge the failed object to prevent session invalidation
        try:
            db.expunge(usage)
        except Exception:
            pass
