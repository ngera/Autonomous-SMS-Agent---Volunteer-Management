# AI-Powered Appointment Booking System

A full-stack appointment booking system with an AI-powered SMS chatbot, built for service businesses (e.g., hair salons, barbershops). Customers book appointments via natural SMS conversations, while staff manage everything through a React admin panel.

## Features

### SMS Chatbot
- Natural language booking via Twilio SMS
- 2-stage AI pre-screener (rule-based + Claude AI) to filter spam, abuse, and opt-outs
- 19-step inbound message pipeline with conversation context
- Automatic opt-in/opt-out consent management

### Admin Panel (React)
- **Dashboard** — Today's bookings, monthly KPIs, unreviewed suspensions, notifications
- **Bookings** — Full CRUD, reschedule, cancel, status updates, booking history timeline
- **Customers** — Contact management, conversation history, appointment patterns, CSV import
- **Appointment Types** — Service catalog with pricing, durations, related services
- **Availability** — Weekly schedule builder, blocked dates, real-time slot preview
- **Reminders** — Upcoming/history views, manual trigger, cancel with reason, analytics
- **Conversations** — Per-customer SMS conversation viewer with chat-style UI
- **Suspensions** — AI-flagged review queue, lift/confirm/ban actions, manual suspend
- **Analytics** — Booking volume charts, revenue trends, consent funnel, retention metrics
- **Settings** — System configuration, admin user management (owner/manager/staff roles)

### Backend Services
- Google Calendar integration (OAuth2, event CRUD)
- ICS calendar file generation (RFC 5545)
- Email notifications via Resend
- Recurrence pattern calculation for proactive reminders
- APScheduler background jobs (reminders, follow-ups, pattern recalculation)

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
- **Anthropic Claude** (claude-haiku-4-5) — Conversation AI engine
- **Google Calendar API** — Calendar event sync
- **Resend** — Transactional email

## Project Structure

```
booking-system/
├── backend/
│   ├── app/
│   │   ├── api/            # 13 API routers (~64 endpoints)
│   │   ├── core/           # Config, database, dependencies, logging
│   │   ├── middleware/     # Auth, rate limiting
│   │   ├── models/         # 17 SQLAlchemy models
│   │   ├── modules/        # Screener, pattern calc, SMS pipeline
│   │   ├── scheduler/      # APScheduler background jobs
│   │   ├── schemas/        # Pydantic request/response schemas
│   │   ├── services/       # Auth, booking, SMS, calendar, email, availability
│   │   └── main.py
│   ├── alembic/            # Database migrations
│   ├── tests/              # 90 tests across 17 files
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/     # Shared UI components (shadcn/ui)
│   │   ├── features/       # 11 feature modules
│   │   │   ├── analytics/
│   │   │   ├── appointment-types/
│   │   │   ├── availability/
│   │   │   ├── auth/
│   │   │   ├── bookings/
│   │   │   ├── conversations/
│   │   │   ├── customers/
│   │   │   ├── dashboard/
│   │   │   ├── reminders/
│   │   │   ├── settings/
│   │   │   └── suspensions/
│   │   ├── context/        # Auth context
│   │   ├── hooks/          # Shared hooks
│   │   ├── lib/            # API client, utilities
│   │   └── types/          # TypeScript type definitions
│   └── package.json
└── requirements/           # Functional & technical specs
```

## Getting Started

### Prerequisites
- Python 3.11+
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
| `SUPABASE_JWT_SECRET` | JWT secret for token validation |
| `SUPABASE_SERVICE_KEY` | Supabase service role key |
| `TWILIO_ACCOUNT_SID` | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | Twilio auth token |
| `TWILIO_PHONE_NUMBER` | Twilio phone number for sending SMS |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude |
| `GOOGLE_CREDENTIALS_JSON` | Google OAuth2 credentials (optional) |
| `RESEND_API_KEY` | Resend API key for email (optional) |

## API Overview

The backend exposes 64 endpoints across 13 routers:

| Router | Prefix | Description |
|--------|--------|-------------|
| Auth | `/api/v1/auth` | Login, refresh, logout |
| Bookings | `/api/v1/bookings` | CRUD, reschedule, cancel, history |
| Customers | `/api/v1/customers` | CRUD, conversations, patterns, consent |
| Appointment Types | `/api/v1/appointment-types` | Service catalog management |
| Availability | `/api/v1/availability` | Schedule rules, blocked dates, slots |
| Dashboard | `/api/v1/dashboard` | KPIs, today's bookings, notifications |
| Analytics | `/api/v1/analytics` | Booking, revenue, retention, consent stats |
| Reminders | `/api/v1/reminders` | Upcoming, history, trigger, cancel |
| Suspensions | `/api/v1/suspensions` | List, review, lift, confirm, ban |
| Settings | `/api/v1/settings` | System configuration |
| Admin Users | `/api/v1/admin-users` | User management (owner only) |
| Webhook | `/api/v1/webhook` | Twilio SMS inbound webhook |
| Health | `/health` | Health check |

## License

Private project — all rights reserved.
