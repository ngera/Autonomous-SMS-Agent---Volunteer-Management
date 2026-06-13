from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin_users import router as admin_users_router
from app.api.analytics import router as analytics_router
from app.api.announcements import router as announcements_router
from app.api.appointment_types import router as appointment_types_router
from app.api.auth import router as auth_router
from app.api.availability import router as availability_router
from app.api.bookings import router as bookings_router
from app.api.bookings_checkin import router as bookings_checkin_router
from app.api.calendar_ics import router as calendar_ics_router
from app.api.candidates import router as candidates_router
from app.api.observability import router as observability_router
from app.api.recognition import router as recognition_router
from app.api.reviews import router as reviews_router
from app.api.service_log import router as service_log_router
from app.api.conversations import router as conversations_router
from app.api.customers import router as customers_router
from app.api.dashboard import router as dashboard_router
from app.api.eval_cases import router as eval_cases_router
from app.api.reminders import router as reminders_router
from app.api.settings import router as settings_router
from app.api.suspensions import router as suspensions_router
from app.api.recruitment import router as recruitment_router
from app.api.tenants import router as tenants_router
from app.api.test_conversation import router as test_conversation_router
from app.api.token_usage import router as token_usage_router
from app.api.webhook import router as webhook_router
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.middleware.auth import AuthLoggingMiddleware
from app.middleware.ratelimit import setup_rate_limiting
from app.scheduler.jobs import (
    announcement_dispatch,
    auto_close_forgotten_checkouts_tick,
    conversation_expiry,
    event_status_ping_tick,
    follow_up_dispatch,
    kpi_summary_tick,
    no_show_review_tick,
    pending_review_tick,
    prune_stale_candidates_tick,
    recruitment_daily_report,
    recruitment_tick,
    reminder_dispatch,
    strike_decay,
)

setup_logging()
logger = get_logger("main")

scheduler = AsyncIOScheduler(timezone=settings.business_timezone)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — register cron jobs
    scheduler.add_job(
        strike_decay,
        CronTrigger(hour=0, minute=0),
        id="strike_decay",
        replace_existing=True,
    )
    scheduler.add_job(
        conversation_expiry,
        CronTrigger(hour=2, minute=0),
        id="conversation_expiry",
        replace_existing=True,
    )
    scheduler.add_job(
        reminder_dispatch,
        CronTrigger(hour=8, minute=0),
        id="reminder_dispatch",
        replace_existing=True,
    )
    scheduler.add_job(
        follow_up_dispatch,
        CronTrigger(hour=10, minute=0),
        id="follow_up_dispatch",
        replace_existing=True,
    )
    scheduler.add_job(
        announcement_dispatch,
        CronTrigger(minute=0),
        id="announcement_dispatch",
        replace_existing=True,
    )
    scheduler.add_job(
        recruitment_tick,
        CronTrigger(minute="*/15"),
        id="recruitment_tick",
        replace_existing=True,
    )
    scheduler.add_job(
        recruitment_daily_report,
        CronTrigger(hour=8, minute=15),
        id="recruitment_daily_report",
        replace_existing=True,
    )
    # Event-lifecycle jobs (Phase 1 steps 5c + 8)
    scheduler.add_job(
        auto_close_forgotten_checkouts_tick,
        CronTrigger(minute="*/15"),
        id="auto_close_forgotten_checkouts_tick",
        replace_existing=True,
    )
    scheduler.add_job(
        prune_stale_candidates_tick,
        CronTrigger(hour=3, minute=0),  # nightly at 3am
        id="prune_stale_candidates_tick",
        replace_existing=True,
    )
    # Phase 2 — Roster status auto-pings (decision #9)
    scheduler.add_job(
        event_status_ping_tick,
        CronTrigger(minute="*"),  # every minute
        id="event_status_ping_tick",
        replace_existing=True,
    )
    # Phase 4 — post-event review auto-creation (decisions #5 + #14)
    scheduler.add_job(
        no_show_review_tick,
        CronTrigger(minute="*/5"),  # every 5 minutes
        id="no_show_review_tick",
        replace_existing=True,
    )
    scheduler.add_job(
        pending_review_tick,
        CronTrigger(minute="*/15"),  # every 15 minutes
        id="pending_review_tick",
        replace_existing=True,
    )
    # Daily KPI digest — per-tenant configurable time + days-of-week.
    # The job runs every 5 min and uses idempotency stamps + local-time
    # gating so each tenant gets exactly one SMS per configured day.
    scheduler.add_job(
        kpi_summary_tick,
        CronTrigger(minute="*/5"),
        id="kpi_summary_tick",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
    logger.info("Scheduler shut down")


app = FastAPI(
    title="AI Appointment Booking System",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.environment == "development" else None,
    redoc_url="/api/redoc" if settings.environment == "development" else None,
)

# Middleware (order matters — outermost first)
#
# In development we accept the configured admin URL plus the common
# localhost variants (127.0.0.1 / both vite default ports). A mismatch
# between the browser's Origin (e.g. http://127.0.0.1:5173) and the single
# allowed origin shows up in the frontend as a generic axios "Network
# Error" — because the browser strips the response before axios can read
# the status — so the dev list intentionally covers both spellings.
_dev_origins = {
    settings.admin_panel_url,
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
}
app.add_middleware(
    CORSMiddleware,
    allow_origins=(
        sorted(_dev_origins)
        if settings.environment == "development"
        else [settings.admin_panel_url]
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuthLoggingMiddleware)

# Rate limiting
setup_rate_limiting(app)

# Routers
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(bookings_router)
app.include_router(bookings_checkin_router)
app.include_router(customers_router)
app.include_router(appointment_types_router)
app.include_router(availability_router)
app.include_router(reminders_router)
app.include_router(suspensions_router)
app.include_router(analytics_router)
app.include_router(settings_router)
app.include_router(admin_users_router)
app.include_router(conversations_router)
app.include_router(calendar_ics_router)
app.include_router(webhook_router)
app.include_router(tenants_router)
app.include_router(announcements_router)
app.include_router(test_conversation_router)
app.include_router(token_usage_router)
app.include_router(recruitment_router)
app.include_router(candidates_router)
app.include_router(observability_router)
app.include_router(service_log_router)
app.include_router(reviews_router)
app.include_router(recognition_router)
app.include_router(eval_cases_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "environment": settings.environment}


@app.get("/api/v1/health")
async def api_health_check():
    return {"status": "healthy", "version": "1.0.0"}
