"""Shared test fixtures for the backend test suite.

Uses dependency overrides to inject mock DB sessions and fake auth users
into the FastAPI app, avoiding the need for a real PostgreSQL database.
"""

import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

# Set test environment variables BEFORE importing the app
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "ACtest")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "test-auth-token")
os.environ.setdefault("TWILIO_PHONE_NUMBER", "+15005550006")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-api-key")
os.environ.setdefault("ENVIRONMENT", "test")

from app.core.dependencies import get_current_user, get_db
from app.main import app
from app.models.admin_user import AdminRole, AdminUser


# ── Fake Users ──

def make_user(role: AdminRole, email: str | None = None):
    """Create a fake AdminUser using MagicMock (avoids SQLAlchemy instrumentation)."""
    user = MagicMock(spec=AdminUser)
    user.id = uuid.uuid4()
    user.email = email or f"{role.value}@test.com"
    user.role = role
    user.is_active = True
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    user.last_login_at = None
    user.failed_login_count = 0
    user.locked_until = None
    return user


@pytest.fixture
def staff_user():
    return make_user(AdminRole.STAFF)


@pytest.fixture
def manager_user():
    return make_user(AdminRole.MANAGER)


@pytest.fixture
def owner_user():
    return make_user(AdminRole.OWNER)


# ── Mock DB ──

def make_scalar_result(value):
    """Create a mock result for scalar_one_or_none() or scalar()."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    result.scalar.return_value = value
    result.scalars.return_value.all.return_value = [value] if value else []
    result.scalars.return_value.first.return_value = value
    result.all.return_value = [(value,)] if value else []
    # Support result.unique().scalar_one_or_none() pattern
    result.unique.return_value = result
    return result


def make_list_result(items):
    """Create a mock result for scalars().all()."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    result.scalar.return_value = len(items)
    result.all.return_value = items
    # Support result.unique().scalars().all() pattern
    result.unique.return_value = result
    return result


def make_row_result(row_tuple):
    """Create a mock result for one_or_none() returning a tuple row."""
    result = MagicMock()
    result.one_or_none.return_value = row_tuple
    result.scalar_one_or_none.return_value = row_tuple[0] if row_tuple else None
    return result


def make_rows_result(rows):
    """Create a mock result for all() returning list of tuple rows."""
    result = MagicMock()
    result.all.return_value = rows
    return result


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.close = AsyncMock()
    # Default: empty result
    db.execute.return_value = make_list_result([])
    return db


# ── App + Client Fixtures ──

@pytest.fixture
def test_app(mock_db, manager_user):
    """FastAPI app with dependency overrides."""
    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: manager_user
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
async def client(test_app):
    """Authenticated async HTTP client (default: manager role)."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def auth_as():
    """Helper to switch the authenticated user for a test."""
    def _auth_as(user: AdminUser):
        app.dependency_overrides[get_current_user] = lambda: user
    return _auth_as


@pytest.fixture
async def no_auth_client(mock_db):
    """Client with DB override but NO auth override (for testing 401s)."""
    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    # Remove auth override if present
    app.dependency_overrides.pop(get_current_user, None)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
