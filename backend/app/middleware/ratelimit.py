from fastapi import FastAPI, Request, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


def get_key_func(request: Request) -> str:
    """Use client IP as rate limit key."""
    return get_remote_address(request)


limiter = Limiter(key_func=get_key_func)


def setup_rate_limiting(app: FastAPI) -> None:
    """Configure rate limiting on the FastAPI app."""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Rate limit constants for use in route decorators
AUTH_RATE_LIMIT = "10/minute"
DEFAULT_RATE_LIMIT = "100/minute"
