"""Shared eval fixtures.

The synthetic-tenant fixture is the main consumer here — Layers 3 and 5
need a deterministic seeded tenant so multi-turn flows are reproducible.
For Layers 1, 2 (regex / classifier-only), the SUT is pure code; no DB
required and these fixtures are unused.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "ACtest")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "test-auth-token")
os.environ.setdefault("TWILIO_PHONE_NUMBER", "+15005550006")
os.environ.setdefault("ENVIRONMENT", "test")


@pytest.fixture(scope="session")
def seeded_demo_tenant():
    """Stub. Phase 2 (Week 2) fills this in with a real seeded tenant.

    The fixture will:
      - Create a Tenant row with `demo-org-fresh` slug.
      - Seed 3 services, 2 upcoming events, 10 contacts (mixed roster
        visibility states).
      - Yield the tenant id so multi-turn flows can use it.
      - Tear down at session end.
    """
    return {
        "tenant_id": None,
        "label": "demo-org-fresh",
        "stubbed": True,
    }


@pytest.fixture(scope="session")
def two_tenants_with_overlap():
    """Stub. Layer 5 needs two tenants whose volunteer phone numbers
    overlap so we can prove no cross-tenant data leaks."""
    return {
        "tenant_a": None,
        "tenant_b": None,
        "stubbed": True,
    }
