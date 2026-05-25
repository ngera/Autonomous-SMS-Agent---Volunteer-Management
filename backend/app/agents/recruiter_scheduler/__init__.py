"""Recruiter+Scheduler agent.

The two roles from the spec are MERGED into a single inbound-SMS
pipeline that shares LLM context. They're documented as two roles
(Recruiter = Q&A + objection handling + intent detection; Scheduler =
booking/swap/cancel + capacity + conflict detection) but live in one
runtime because the volunteer-facing conversation is a single thread
and splitting it would force the LLM to re-load context per turn.

The agent's handle_inbound currently delegates to the existing
pipeline.process_inbound_message — this keeps Path A a no-behavior-
change refactor. Future work (tool-call tagging as recruiter_* vs
scheduler_*, dedicated planner.py + intents.py modules) lives in this
directory and arrives with the top-3 feature work.

See memory/path_a_agent_architecture_plan.md.
"""

from app.agents.recruiter_scheduler.agent import RecruiterSchedulerAgent

__all__ = ["RecruiterSchedulerAgent"]
