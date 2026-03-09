from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin_users import router as admin_users_router
from app.api.analytics import router as analytics_router
from app.api.appointment_types import router as appointment_types_router
from app.api.auth import router as auth_router
from app.api.availability import router as availability_router
from app.api.bookings import router as bookings_router
from app.api.calendar_ics import router as calendar_ics_router
from app.api.customers import router as customers_router
from app.api.dashboard import router as dashboard_router
from app.api.reminders import router as reminders_router
from app.api.settings import router as settings_router
from app.api.suspensions import router as suspensions_router
from app.api.webhook import router as webhook_router
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.middleware.auth import AuthLoggingMiddleware
from app.middleware.ratelimit import setup_rate_limiting
from app.scheduler.jobs import (
    conversation_expiry,
    follow_up_dispatch,
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.admin_panel_url],
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
app.include_router(customers_router)
app.include_router(appointment_types_router)
app.include_router(availability_router)
app.include_router(reminders_router)
app.include_router(suspensions_router)
app.include_router(analytics_router)
app.include_router(settings_router)
app.include_router(admin_users_router)
app.include_router(calendar_ics_router)
app.include_router(webhook_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "environment": settings.environment}


@app.get("/api/v1/health")
async def api_health_check():
    return {"status": "healthy", "version": "1.0.0"}
