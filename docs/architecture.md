# Architecture

End-to-end architecture of the shipped system. For features and usage, see the [root README](../README.md).

---

## At a glance

A multi-tenant SaaS that coordinates volunteers over plain SMS. The system is split into six horizontal layers:

1. **Channels & surfaces** — how volunteers and admins reach the system.
2. **HTTP layer** — FastAPI app with webhook + REST transports, multi-tenant resolution.
3. **Agent architecture** — orchestrator + per-domain agents on a hybrid intent stack.
4. **Tool layer** — Anthropic `tool_use` loop, deterministic server-side execution.
5. **Domain services + scheduler** — recruitment waves, reminders, event lifecycle, KPI digest.
6. **Data + persistence** — multi-tenant PostgreSQL with row-level isolation.

Cross-cutting: per-tenant credentials for external services (Twilio, Anthropic, Google, Resend).

---

## End-to-end diagram

```
+----------------------------------------------------------------------+
| 1. Channels & surfaces                                               |
|                                                                      |
|   Volunteer SMS         Admin Web (React)         Admin SMS          |
|   (Twilio)              (React + Vite + tanstack) (Twilio)           |
+--------|--------------------|-----------------------|----------------+
         v                    v                       v
+----------------------------------------------------------------------+
| 2. HTTP layer  --  FastAPI                                           |
|                                                                      |
|   Webhook  /api/v1/webhook       REST  /api/v1/*                     |
|                                                                      |
|   Multi-tenant resolution:                                           |
|     - Webhook: Twilio "To" phone number  ->  tenant                  |
|     - REST:    JWT tenant_id claim       ->  tenant                  |
|                                                                      |
|   Returns 200 immediately; heavy work runs in BackgroundTasks.       |
+----------------------------------|-----------------------------------+
                                   v
+----------------------------------------------------------------------+
| 3. Agent architecture  --  Orchestrator + BaseAgent                  |
|                                                                      |
|   Orchestrator  --  hybrid intent stack:                             |
|                     Tier 1 regex   ->  Tier 2 Haiku classifier ->    |
|                     Tier 3 full Sonnet conversation                  |
|                                                                      |
|     +-------------------+---------------------+-------------------+  |
|     v                   v                     v                   v  |
|  Recruiter          Recruiter             Engagement          Screener|
|  Scheduler          (waves, escalation,   (day-of, check-in,  (Stage 1|
|  (event design,     reschedule cascade)   post-event, reviews)+ Haiku)|
|   service mix)                                                       |
|                                                                      |
|  Each agent = planner.py + executor.py + reporter.py + intents.py    |
|  Per-seam model resolver (Sonnet for reasoning, Haiku for routing)   |
|  Graph-style agent_call_log audit table (shared turn_id per trace)   |
+----------------------------------|-----------------------------------+
                                   v
+----------------------------------------------------------------------+
| 4. Tool layer  --  Anthropic tool_use loop                           |
|                                                                      |
|  Volunteer tools: list_services, check_availability,                 |
|                   get_event_roster, book_appointment,                |
|                   cancel_appointment, reschedule_appointment,        |
|                   set_roster_visibility                              |
|                                                                      |
|  Admin tools:     manage_service, manage_availability,               |
|                   manage_volunteer, suspend / unsuspend,             |
|                   start_recruitment_campaign, approve_campaign,      |
|                   campaign_status, send_announcement,                |
|                   search_bookings                                    |
|                                                                      |
|  All tools run server-side with full transactional context.          |
+----------------------------------|-----------------------------------+
                                   v
+----------------------------------------------------------------------+
| 5. Domain services + scheduler  --  APScheduler cron                 |
|                                                                      |
|  Inbound pipeline (screener  ->  agent loop  ->  outbound router)    |
|  Recruitment wave dispatch (per-campaign tick)                       |
|  Reminder dispatch (T-24h, T-1h)                                     |
|  Event status pings to admin (T-30 through T+60)                     |
|  Auto-close forgotten checkouts (T+end+1h)                           |
|  Daily KPI SMS digest (per-tenant schedule)                          |
|  Pending review + no-show review                                     |
|  Strike decay, conversation expiry                                   |
+----------------------------------|-----------------------------------+
                                   v
+----------------------------------------------------------------------+
| 6. Data + persistence  --  PostgreSQL (Supabase) via asyncpg         |
|                                                                      |
|  Row-level isolation: tenant_id FK on every table                    |
|                                                                      |
|  Core tables:                                                        |
|    Tenants          (per-tenant Twilio/Anthropic/Google/Resend creds)|
|    AdminUsers       (incl. SUPER_ADMIN role, tenant_id=NULL)         |
|    Contacts         (UUID PK; UNIQUE(tenant_id, phone))              |
|    Conversations, Messages, AgentCallLog                             |
|    AppointmentTypes, AvailabilityRules, SpecificDateSlots, Bookings  |
|    RecruitmentCampaigns, RecruitmentWaves, WaveSignups               |
|    Announcements, Reminders, Suspensions                             |
|    BookingReview, BookingServiceLog, RosterStatusPingLog             |
|    AwardDefinition, VolunteerRecognition                             |
|    SystemSetting (per-tenant prompt overrides, agent_models config)  |
|    TokenUsage    (per-call Anthropic accounting)                     |
+----------------------------------------------------------------------+
```

---

## Cross-cutting

### External integrations (per-tenant credentials)

| Service          | Used for                                       |
|------------------|-------------------------------------------------|
| Anthropic Claude | Haiku 4.5 (routing) + Sonnet 4.6 (reasoning)   |
| Twilio           | SMS send/receive with signature validation     |
| Google Calendar  | ICS exports + OAuth2 event sync                |
| Resend           | Transactional email                            |

### Trust & guardrails

- **Hybrid intent stack** — regex → Haiku → Sonnet, with always-confirm on destructive intents (`delete_campaign`). Holds per-tenant LLM cost predictable.
- **Two-stage pre-screener** — deterministic Stage 1 (opt-out, garbage, prompt injection) + Haiku Stage 2 (RELEVANT / IRRELEVANT / ABUSIVE) with contextual-reply bypass so brief answers to assistant questions ("anything", "idk") aren't punished.
- **Fresh-state preamble** — every admin turn re-injects current system state (~250 tokens) so the LLM can't parrot stale conversation history.
- **Per-tenant LLM rate limit** — request-per-minute ceiling at the application layer; clean 429 with retry-after.
- **Bounded conversation history** — sliced before every LLM send (per-turn cost cap) AND FIFO-trimmed in storage.
- **Editable prompts** — 17 system prompts editable per tenant, with "reset to shipped default" when overrides drift.
- **Agent call audit** — every orchestrator routing decision + tool call writes to `agent_call_log` under a shared `turn_id`, surfaced as a per-conversation Trace tab.
- **SMS suppression flag** — per-tenant kill switch for testing without burning Twilio credits.

### Multi-tenant operations

- `Tenant` model holds per-tenant Twilio, Anthropic, Google, Resend credentials.
- Tenant resolution at webhook: Twilio `To` phone → tenant.
- Tenant resolution at REST: JWT `tenant_id` claim.
- `SUPER_ADMIN` role above `OWNER`; manages tenants and platform-level config; `tenant_id` is `NULL`.
- Scheduler iterates active tenants per tick.
- `is_active` / `is_paused` flags gate request handling at the dependency layer.

---

## Detail: Agent layer

```
                   Inbound message (SMS or REST)
                              |
                              v
                    +---------------------+
                    |    Orchestrator     |
                    +---------------------+
                              |
              +---------------+---------------+
              |               |               |
              v               v               v
        regex (Tier 1)  Haiku (Tier 2)  Sonnet (Tier 3)
        sub-millisecond ~200ms          ~1-2s
              |               |               |
              +-------+-------+-------+-------+
                      |               |
                      v               v
                Intent +         Destructive-intent
                event_ref        confirmation gate
                      |               |
                      v               v
              +-----------------------------+
              |  Route to owning agent      |
              +-----------------------------+
                      |
   +------------------+------------------+------------------+
   v                  v                  v                  v
 Recruiter        Recruiter          Engagement         Screener
 Scheduler        - wave plan        - day-of intents   (pre-filter,
 - event design   - escalation       - check-in/out     runs before
 - service mix    - reschedule       - post-event       any agent)
                    cascade          - reviews
                  - approval flow
   |                  |                  |                  |
   +------------------+------------------+------------------+
                      |
                      v
              +-----------------------------+
              |  Tool execution layer       |
              |  + audit to agent_call_log  |
              +-----------------------------+
```

Each agent ships with the same four-file shape: `planner.py` (decides what to do), `executor.py` (does it), `reporter.py` (renders the result), `intents.py` (declares which intents it owns). Code lives under [backend/app/agents/](../backend/app/agents/).

---

## Detail: Data isolation

```
HTTP request    --->    CurrentTenant dependency    --->    DB query
                            |
                            v
                      tenant_id resolved from JWT (REST)
                      or Twilio "To" number (webhook)

Every tenant-scoped table:
  - tenant_id FK to tenants.id, NOT NULL
  - Composite UNIQUE indexes per tenant where appropriate
    (e.g. contacts: UNIQUE(tenant_id, phone))
  - Application-side filter via query dependency

SUPER_ADMIN role:
  - tenant_id = NULL
  - Optionally passes X-Tenant-Id header to act as a tenant
```

---

## What this diagram doesn't cover

- **Frontend internals** — tanstack-query keys, shadcn/ui composition, Recharts pipelines. Lives in [frontend/](../frontend/), not on the architectural critical path.
- **Per-intent sequence diagrams** — book, reschedule, switch, check-in — captured in code rather than diagrams.
- **Operational concerns** — CI/CD, monitoring, alerting. Lightweight by design (Supabase dashboard + GitHub Actions).

For the eval framework that gates changes to any of this, see [eval-framework.md](eval-framework.md).
