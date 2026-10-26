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

```mermaid
flowchart TB
  subgraph L1["1 · Channels & surfaces"]
    direction LR
    smsV["Volunteer SMS<br/>Twilio"]
    web["Admin Web<br/>React · Vite · TanStack"]
    smsA["Admin SMS<br/>Twilio"]
  end

  subgraph L2["2 · HTTP layer — FastAPI"]
    direction LR
    webhook["Webhook /api/v1/webhook<br/>Twilio To → tenant"]
    rest["REST /api/v1/*<br/>JWT tenant_id → tenant"]
  end

  subgraph L3["3 · Agent architecture — Orchestrator + BaseAgent"]
    orch["Orchestrator<br/>Tier 1 regex → Tier 2 Haiku → Tier 3 Sonnet"]
    sched["Recruiter Scheduler<br/>event design · service mix"]
    recruit["Recruiter<br/>waves · escalation · reschedule"]
    engage["Engagement<br/>day-of · check-in · reviews"]
    screen["Screener<br/>Stage 1 + Haiku"]
    orch --> sched & recruit & engage & screen
  end

  subgraph L4["4 · Tool layer — Anthropic tool_use"]
    tools["Volunteer + admin tools<br/>server-side · transactional"]
  end

  subgraph L5["5 · Domain services + scheduler — APScheduler"]
    jobs["Inbound pipeline · recruitment waves · reminders<br/>event pings · KPI digest · reviews · strike decay"]
  end

  subgraph L6["6 · Data + persistence — PostgreSQL / Supabase"]
    db["Row-level isolation via tenant_id<br/>Contacts · Bookings · Campaigns · AgentCallLog · …"]
  end

  smsV & web & smsA --> webhook & rest
  webhook & rest --> orch
  sched & recruit & engage & screen --> tools
  tools --> jobs
  jobs --> db
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

```mermaid
flowchart TB
  inbound["Inbound message<br/>SMS or REST"] --> orch["Orchestrator"]

  orch --> t1["Tier 1 · regex<br/>sub-millisecond"]
  orch --> t2["Tier 2 · Haiku<br/>~200ms"]
  orch --> t3["Tier 3 · Sonnet<br/>~1–2s"]

  t1 & t2 --> intent["Intent + event_ref"]
  t3 --> confirm["Destructive-intent<br/>confirmation gate"]

  intent & confirm --> route["Route to owning agent"]

  route --> a1["Recruiter Scheduler<br/>event design · service mix"]
  route --> a2["Recruiter<br/>waves · escalation · reschedule"]
  route --> a3["Engagement<br/>day-of · check-in · reviews"]
  route --> a4["Screener<br/>pre-filter before any agent"]

  a1 & a2 & a3 & a4 --> tools["Tool execution layer<br/>+ audit to agent_call_log"]
```

Each agent ships with the same four-file shape: `planner.py` (decides what to do), `executor.py` (does it), `reporter.py` (renders the result), `intents.py` (declares which intents it owns). Code lives under [backend/app/agents/](../backend/app/agents/).

---

## Detail: Data isolation

```mermaid
flowchart LR
  req["HTTP request"] --> dep["CurrentTenant<br/>dependency"]
  dep --> db["DB query"]

  dep --> resolve["tenant_id from<br/>JWT claim or Twilio To"]

  resolve --> rules["Tenant-scoped tables<br/>tenant_id FK · NOT NULL<br/>composite UNIQUE per tenant<br/>app-side query filter"]

  resolve --> super["SUPER_ADMIN<br/>tenant_id = NULL<br/>optional X-Tenant-Id"]
```

---

## What this diagram doesn't cover

- **Frontend internals** — tanstack-query keys, shadcn/ui composition, Recharts pipelines. Lives in [frontend/](../frontend/), not on the architectural critical path.
- **Per-intent sequence diagrams** — book, reschedule, switch, check-in — captured in code rather than diagrams.
- **Operational concerns** — CI/CD, monitoring, alerting. Lightweight by design (Supabase dashboard + GitHub Actions).

For the eval framework that gates changes to any of this, see [eval-framework.md](eval-framework.md).
