"""
Auth middleware for JWT validation on all protected routes.

Note: The actual JWT validation and role enforcement is handled via
FastAPI dependencies in core/dependencies.py (get_current_user, require_role).

This module provides an optional middleware layer for logging auth failures
and a convenience decorator for route-level role checks.
"""

import logging
from functools import wraps
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger

logger = get_logger("auth")

# Paths that don't require authentication
PUBLIC_PATHS = {
    "/health",
    "/api/v1/health",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/reset-password",
    "/api/v1/webhook/sms",
    "/api/docs",
    "/api/redoc",
    "/openapi.json",
}

# Paths with prefix matching (e.g., /api/v1/calendar/ for ICS endpoints)
PUBLIC_PATH_PREFIXES = (
    "/api/v1/calendar/",
)


class AuthLoggingMiddleware(BaseHTTPMiddleware):
    """Logs authentication failures for monitoring."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        if response.status_code == 401:
            logger.warning(
                "Auth failure: %s %s from %s",
                request.method,
                request.url.path,
                request.client.host if request.client else "unknown",
            )
        elif response.status_code == 403:
            logger.warning(
                "Permission denied: %s %s from %s",
                request.method,
                request.url.path,
                request.client.host if request.client else "unknown",
            )

        return response
