# Autonomous SMS Agent — Volunteer Management

## Intro video

[![Watch the intro](https://img.youtube.com/vi/NU_NMDMl1-I/maxresdefault.jpg)](https://youtu.be/NU_NMDMl1-I)

An autonomous assistant that manages volunteer coordination for a Volunteer Coordinator — handling the day-to-day work of keeping events staffed, on its own.

The system is designed to:

- **Recruit volunteers** for open shifts and events, matching people to work based on their history and preferences
- **Remind and confirm** — nudge volunteers before events and track who's coming
- **Adjust automatically** when someone reschedules or cancels, backfilling the shift without you stepping in
- **Answer volunteers' questions** directly, around the clock
- **Keep you in the loop** — flagging events at risk of going understaffed, reporting progress, and surfacing anything that needs your attention
- **Give you a live dashboard** — see staffing status, volunteer activity, and progress across all your events at a glance, anytime

It runs on its own and only comes to you when there's a real issue — not for the routine work. And it works entirely over text, since that's what volunteers actually respond to.

## Features

The system is built around an AI core that actually drives outcomes — not a chatbot bolted onto a CRUD app. The features below are ordered by AI leverage.

### Volunteer Recruitment Agent (flagship)

Plans and executes multi-wave recruitment campaigns for events without an admin in the loop after approval.

- **Planner** (Sonnet) — one tool-use call per campaign. Pulls event details + current signups + ranked candidate pool, then proposes policy (wave offsets, overshoot factor, cooldowns), per-wave SMS templates, and a complete wave preview. Deterministic fallback materializes a sensible plan when the LLM stalls.
- **Executor** — materializes waves on approval, dispatches outreach in scheduled batches, attributes signups back to waves, snaps the first wave to "now" so admins see immediate motion.
- **Reporter** (Sonnet) — daily 2-3 sentence SMS to the admin with fill rate + recent wave activity + next action. Editable per-tenant.
- **Server-side intent routers** — admin SMS like "plan recruitment for food drive", "approve", "delete the gala campaign", "status of food drive" short-circuit the LLM and dispatch deterministically. Five routers across approve / status / list-events / start / delete.
- **Per-volunteer attribution** — each wave records `targeted_contact_ids`, `sent_count`, `signups_attributed`; the status command rolls these up per `wave_number` across services.
- **Per-service goals** — campaigns track `min_required` + `max_allowed` per appointment type; the planner fills `min` first across competing campaigns, then `max`.

### AI Conversation Engine

Tool-use conversation loop powered by Anthropic Claude, with per-seam model selection.

- **Two-seam architecture** — heavy reasoning (planning, narrative) uses Sonnet; routing, classification, and intent-disambiguation use Haiku. Per-seam model is editable per tenant (`agent_models` JSONB).
- **Tool-use protocol** — 16 customer + admin tools (list services, check availability, book / reschedule / cancel, manage events, get roster, recruitment status, …). All tools run server-side with full transactional context.
- **CURRENT SYSTEM STATE preamble** — every admin turn re-injects fresh facts (admin phone configured? campaigns awaiting approval? upcoming events?) so the LLM can't parrot stale history.
- **Pending-solicitation preamble** — when a volunteer received a recruitment SMS in the last 48h, the customer LLM is told the authoritative service + event so an ambiguous "yes" books the right thing.
- **Roster-visibility memory** — first time a volunteer books, the agent asks how they want to appear (first name / full name / hidden); the answer is persisted on the contact and reused for every future booking.

### Hybrid Intent Detection (3-tier)

LLMs fail unreliably at typed-action invocation — the system uses a three-tier stack so that failure mode never reaches the database.

1. **Regex routers** — free, instant, covers the 80% of common phrasings.
2. **Haiku JSON classifier** — fires on miss with structured `{intent, confidence, event_reference}`. Confidence threshold 0.7 for direct dispatch.
3. **Full LLM** — handles novel chat / questions / multi-turn.

Destructive intents (`delete_campaign`) always surface a confirmation prompt that requires explicit re-typing — even at high classifier confidence.

### Two-Stage Pre-Screener (with contextual bypass)

- **Stage 1 (rule-based, zero cost)** — opt-out keywords, empty / garbage rejection, prompt-injection detection.
- **Stage 1.5 (contextual reply bypass)** — when the assistant just asked a question and the volunteer replies with a brief answer ("anything", "yes", "idk", "you pick"), classify as RELEVANT without calling Haiku. Stops the false-IRRELEVANT strikes that punish volunteers for engaging.
- **Stage 2 (Haiku micro-prompt)** — RELEVANT / IRRELEVANT / ABUSIVE classification with conversation context.
- Strike-and-suspension policy with admin review queue.

### Orchestrator-Routed Inbound Pipeline

Every inbound SMS flows through a supervisor layer (`app/agents/orchestrator/`) before reaching an agent:

- **Crisis pre-filter** — keyword check today; Haiku classifier seam wired for Phase 2.
- **Take-over detection** — admin "take over" mode pauses agent outbound silently.
- **Routing audit** — every routing decision + tool call writes a row to `agent_call_log` with shared `turn_id` for graph-shaped traces.
- **Per-tenant policy hooks** — cross-agent cooldown (default 24h), per-volunteer weekly cap, quiet hours (default 21:00–09:00 tenant timezone).

### Editable Prompts + Full Observability

- **AI Prompts page** — 17 editable system prompts per tenant: customer SMS, admin SMS, recruitment routing (start / approve / delete), recruitment planner + reporter, screener, fallback / error messages, announcement / reminder / wave templates, service presentation, roster visibility (saved / unset / booking hint). "Reset to default" button shows when a tenant override has drifted from the shipped default.
- **Token Usage dashboard** — every Anthropic call recorded with input/output tokens, model, source, tool calls. Drill-down by volunteer / tool / source / model with daily cost estimates.
- **`agent_call_log` audit table** — orchestrator routing decisions + agent invocations + tool calls all share a turn_id, surfaced as a per-conversation Trace tab.
- **Per-tenant LLM rate limit** — request-per-minute ceiling guards against any one tenant exhausting upstream quota; 429 returned cleanly with retry-after.
- **Bounded conversation history** — sliced before every LLM send (per-turn cost cap) and FIFO-trimmed in storage (per-row size cap).

### Volunteer Profile

- **Service access control** — per-service assignment via join table OR "All Services" toggle. Volunteers with no services assigned cannot book; admin is notified on attempt.
- **Roster visibility default** — `contacts.default_roster_visibility` carries forward across bookings.
- **Availability** — weekly hours + unavailable date list.
- **Background check flag** — gates booking until cleared.
- **Long-term memory** — post-conversation Haiku call extracts durable facts (preferences + free-form notes) into `contacts.preferences` + `contacts.notes` for the next conversation to use.
- **Cross-booking overlap detection** — `book_appointment` refuses to double-book the same volunteer in overlapping windows; surfaces the conflicting booking to the LLM with an explicit "ask the volunteer" instruction.

### Admin Panel (React)

- **Dashboard** — today's bookings, monthly KPIs, weekly slot overview, volunteer breakdown, unreviewed suspensions, notifications.
- **Campaigns** — per-event recruitment pipeline with at-risk badge, fill bar, per-service min/max/signed-up/need columns, last + next wave timestamps.
- **Bookings** — full CRUD, reschedule, cancel, status updates, history timeline.
- **Volunteers** — contact management, service assignment, conversation history, appointment patterns, CSV import.
- **Appointment Types** — service catalog with pricing, durations, related services, category.
- **Availability** — weekly schedule builder, specific date slot overrides, blocked dates, real-time slot preview, per-event service config (min/max).
- **Reminders** — upcoming/history, manual trigger, cancel with reason, analytics.
- **Conversations** — per-customer SMS viewer with chat-style UI and Trace tab.
- **Suspensions** — AI-flagged review queue, lift / confirm / ban, manual suspend via SMS.
- **Analytics** — booking volume, revenue trends, consent funnel, retention.
- **Token Usage** — see Observability above.
- **SMS Test Tool** — multi-volunteer iOS-style simulator with searchable volunteer picker, screener integration, tool-call visibility, per-panel history. No real SMS sent.
- **Announcements** — broadcast messages with optional event/service targeting.
- **AI Prompts** — see Observability above.
- **Settings + Admin Users** — system config, role-based user management (owner / manager / staff / super-admin).
- **Tenants** — super-admin tenant dashboard for multi-tenant management.

### Multi-Tenant Architecture

- Row-level isolation (`tenant_id` on every table; 22 models).
- Per-tenant credentials (Twilio, Anthropic, Google, Resend).
- Super-admin role with cross-tenant management.
- Tenant context via `X-Tenant-Id` header for super-admins.
- Tenant `is_active` / `is_paused` flags gate request handling at the dependency layer.
- Per-tenant SMS suppression flag for testing without burning Twilio credits.

### Backend Services

- Google Calendar integration (OAuth2, event CRUD on booking lifecycle).
- ICS calendar file generation (RFC 5545) with UUID-based security tokens.
- Email notifications via Resend.
- APScheduler background jobs (reminders, follow-ups, announcement dispatch, recruitment wave ticks, pattern recalculation).
- Webhook returns 200 immediately, processes inbound via `BackgroundTasks`.

### Design Decisions (selected)

A few structural choices that shape how the system behaves:

- **#1 Two-seam Recruitment Agent.** Planner runs once per campaign (~2 LLM calls/day/campaign), Executor is plain Python iterating over candidates. Keeps the agent debuggable, cheap, and race-resistant.
- **#7 / #20 / #21 Server-side intent routers.** Explicit recruitment verbs ("approve", "plan for X", "delete the X campaign") never fall through to the LLM. Regex catches the verb, dispatches to the handler. Closes the silent-tool-omission failure mode where the LLM emits "Approved!" without invoking the tool.
- **#8 Fresh-state preamble.** Every admin turn re-injects current system state (~250 tokens). Stops the LLM from parroting stale "no phone configured" / "no campaign awaiting approval" from earlier in the conversation history.
- **#22 Hybrid intent detection.** Regex → Haiku classifier → full LLM, with always-confirm guardrail on destructive intents. The tier structure (deterministic → cheap classifier → full LLM) is the generalizable pattern for "user input might want one of N typed actions" surfaces.
- **#23 Screener contextual-reply bypass.** Brief replies right after an assistant question ("anything", "whatever", "idk") classify RELEVANT in Stage 1 without a Haiku call. Real volunteers don't get strikes for engaging with the assistant's open invitation.
- **#15 Per-tenant LLM rate limit.** Hard request-per-minute ceiling at the application layer, not just the upstream provider's. Prevents any one tenant from exhausting global quota — and surfaces 429s cleanly with retry-after.
- **#14 / #13 Bounded conversation history.** History is sliced before every LLM send (per-turn cost cap) AND FIFO-trimmed in storage (per-row size cap). Bound every dimension explicitly at the application layer.

## Tech Stack

### Backend
- **Python 3.12+** with **FastAPI**
- **SQLAlchemy 2.x** async ORM with **asyncpg**
- **Supabase PostgreSQL** database
- **Supabase Auth** + JWT validation (python-jose)
- **Alembic** for database migrations
- **APScheduler** for background job scheduling

### Frontend
- **React 18** with **TypeScript**
- **Vite** build tool
- **Tailwind CSS v4** + **shadcn/ui v4** (base-ui primitives)
- **TanStack Query v5** for server state management
- **Recharts** for analytics visualizations
- **React Router v7** for navigation

### External Services
- **Twilio** — SMS sending/receiving with webhook signature validation
- **Anthropic Claude** — Sonnet 4.6 (planner + reporter + customer/admin conversation) and Haiku 4.5 (screener + intent classifier + routing seams), with per-tenant per-seam overrides
- **Google Calendar API** — Calendar event sync
- **Resend** — Transactional email

## Project Structure

```
booking-system/
├── backend/
│   ├── app/
│   │   ├── agents/         # Path A architecture: orchestrator + base + per-agent (recruiter, recruiter_scheduler, engagement)
│   │   ├── api/            # 19 API routers (~80+ endpoints)
│   │   ├── core/           # Config, database, dependencies, logging
│   │   ├── middleware/     # Auth, rate limiting
│   │   ├── models/         # 22 SQLAlchemy models
│   │   ├── modules/        # Screener, conversation AI, SMS pipeline, tool executor
│   │   ├── prompts/        # System prompts (screener, conversation, recruitment seams)
│   │   ├── scheduler/      # APScheduler background jobs
│   │   ├── schemas/        # Pydantic request/response schemas
│   │   ├── services/       # Auth, booking, SMS, calendar, email, availability, token usage, agent_models
│   │   └── main.py
│   ├── alembic/            # Database migrations (a001–a031)
│   ├── tests/              # 90+ tests across 17 files
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/     # Shared UI components (shadcn/ui)
│   │   ├── features/       # 15 feature modules
│   │   │   ├── analytics/
│   │   │   ├── announcements/
│   │   │   ├── appointment-types/
│   │   │   ├── availability/
│   │   │   ├── auth/
│   │   │   ├── bookings/
│   │   │   ├── conversations/
│   │   │   ├── customers/
│   │   │   ├── dashboard/
│   │   │   ├── marketing/
│   │   │   ├── recruitment/
│   │   │   ├── reminders/
│   │   │   ├── settings/
│   │   │   ├── suspensions/
│   │   │   ├── tenants/
│   │   │   ├── test-tool/
│   │   │   └── token-usage/
│   │   ├── context/        # Auth + tenant filter context
│   │   ├── hooks/          # Shared hooks
│   │   ├── lib/            # API client, utilities
│   │   └── types/          # TypeScript type definitions
│   └── package.json
└── README.md
```

## Getting Started

### Prerequisites
- Python 3.12+
- Node.js 18+
- Supabase project (PostgreSQL + Auth)
- Twilio account (for SMS)
- Anthropic API key (for AI chatbot)

### Environment file

Put a single **`.env`** at the **repository root** (`booking-system/.env`) **or** in **`backend/.env`**. If both exist, `backend/.env` overrides. Copy from `backend/.env.example` and fill in real values. Extra keys in `.env` (e.g. split Postgres vars) are ignored.

### Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate            # Linux/macOS
# Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Migrations (PYTHONPATH required so `app` imports resolve)
# Linux/macOS: export PYTHONPATH="$(pwd)"
# Windows PowerShell: $env:PYTHONPATH = (Get-Location).Path
alembic upgrade head

# Or Windows: .\migrate.ps1  (uses .venv Python automatically)

# Start the API
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
# Or Windows: .\run-dev.ps1
```

### Frontend Setup

```bash
cd frontend
npm install
# Optional: copy .env.example to .env — defaults to http://localhost:8000/api/v1
npm run dev
```

Open **http://127.0.0.1:5173** (or the URL Vite prints). Set `ADMIN_PANEL_URL=http://localhost:5173` in backend `.env` so CORS allows the dev origin.

### Running Tests

```bash
cd backend
python -m pytest tests/ -v
```

All 90 tests pass in under 1 second using mock-based testing (no database required).

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string (asyncpg) |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_JWT_SECRET` | JWT secret for token validation |
| `SUPABASE_SERVICE_KEY` | Supabase service role key |
| `TWILIO_ACCOUNT_SID` | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | Twilio auth token |
| `TWILIO_PHONE_NUMBER` | Twilio phone number for sending SMS |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude |
| `GOOGLE_CREDENTIALS_JSON` | Google OAuth2 credentials (optional) |
| `RESEND_API_KEY` | Resend API key for email (optional) |
| `ADMIN_PANEL_URL` | Frontend URL for CORS (default: `http://localhost:5173`) |

## API Overview

The backend exposes 80+ endpoints across 19 routers:

| Router | Prefix | Description |
|--------|--------|-------------|
| Auth | `/api/v1/auth` | Login, refresh, logout |
| Dashboard | `/api/v1/dashboard` | KPIs, today's bookings, weekly slots, notifications |
| Bookings | `/api/v1/bookings` | CRUD, reschedule, cancel, history |
| Customers | `/api/v1/customers` | CRUD, service assignment, conversations, patterns, consent |
| Appointment Types | `/api/v1/appointment-types` | Service catalog management |
| Availability | `/api/v1/availability` | Schedule rules, specific dates, blocked dates, slots |
| Reminders | `/api/v1/reminders` | Upcoming, history, trigger, cancel |
| Suspensions | `/api/v1/suspensions` | List, review, lift, confirm, ban |
| Analytics | `/api/v1/analytics` | Booking, revenue, retention, consent stats |
| Token Usage | `/api/v1/token-usage` | AI token consumption analytics with drill-downs |
| Recruitment | `/api/v1/recruitment` | Campaign CRUD, waves, signups, reports |
| Announcements | `/api/v1/announcements` | Broadcast messages with optional event/service targeting |
| Settings | `/api/v1/settings` | System configuration + per-tenant AI prompt overrides |
| Admin Users | `/api/v1/admin-users` | User management (owner only) |
| Tenants | `/api/v1/tenants` | Multi-tenant management (super-admin) |
| Conversations | `/api/v1/conversations` | Conversation history + Trace tab |
| Test Conversation | `/api/v1/test-conversation` | SMS test tool |
| Webhook | `/api/v1/webhook` | Twilio SMS inbound webhook (orchestrator-routed) |
| Calendar ICS | `/api/v1/calendar` | ICS file endpoints |
| Health | `/health` | Health check |

## License

MIT — see [LICENSE](LICENSE).

This is a personal portfolio project. It is functional end-to-end but not
maintained as a product. Feel free to read, fork, or borrow ideas.
