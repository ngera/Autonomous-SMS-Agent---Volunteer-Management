"""Agent registry — the list of agent implementations the Orchestrator
knows about. Lookup by name string returns the singleton implementation.

External agents (REST/MCP-based) register here too via Path A's open
question #2 — for now, only internal agents.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.agents.base import (
    AGENT_ENGAGEMENT,
    AGENT_RECRUITER_SCHEDULER,
)

if TYPE_CHECKING:
    from app.agents.base import BaseAgent


_REGISTRY: dict[str, "BaseAgent"] = {}


def _build_registry() -> dict[str, "BaseAgent"]:
    """Lazy-build the registry on first access — avoids import-time
    circular dependencies (agents import the orchestrator's audit
    helper; the orchestrator imports agents)."""
    if _REGISTRY:
        return _REGISTRY

    # Internal agents
    from app.agents.recruiter_scheduler.agent import RecruiterSchedulerAgent
    from app.agents.engagement.agent import EngagementAgent

    _REGISTRY[AGENT_RECRUITER_SCHEDULER] = RecruiterSchedulerAgent()
    _REGISTRY[AGENT_ENGAGEMENT] = EngagementAgent()

    return _REGISTRY


def get(name: str) -> "BaseAgent | None":
    return _build_registry().get(name)


def all_agents() -> dict[str, "BaseAgent"]:
    """Snapshot of registered agents — for health checks + admin UI."""
    return dict(_build_registry())
