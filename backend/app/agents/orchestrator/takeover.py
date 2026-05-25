"""Admin take-over of an agent-owned conversation.

When admin clicks "Take over" on the conversation page:
  - conversations.takeover_mode = true
  - conversations.takeover_admin_id = the admin
  - agent responses paused (Orchestrator.handle_inbound returns
    silently for inbound messages on takeover threads; admin replies
    are sent directly via a different code path)

When admin clicks "Hand back":
  - takeover_mode = false; agent resumes normal handling
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation


@dataclass(frozen=True)
class TakeoverState:
    in_takeover: bool
    admin_id: uuid.UUID | None


def state_of(conversation: Conversation | None) -> TakeoverState:
    if conversation is None:
        return TakeoverState(in_takeover=False, admin_id=None)
    return TakeoverState(
        in_takeover=bool(getattr(conversation, "takeover_mode", False)),
        admin_id=getattr(conversation, "takeover_admin_id", None),
    )


async def take_over(
    db: AsyncSession, conversation: Conversation, admin_id: uuid.UUID
) -> None:
    conversation.takeover_mode = True
    conversation.takeover_admin_id = admin_id
    await db.flush()


async def hand_back(db: AsyncSession, conversation: Conversation) -> None:
    conversation.takeover_mode = False
    conversation.takeover_admin_id = None
    await db.flush()
