"""Test fixtures for Arranged backend tests.

Provides an isolated async test database, test client, and helpers
for creating users/profiles without hitting production.
"""
import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models.user import User, UserType
from app.models.profile import Profile, Gender
from app.models.subscription import Subscription, SubscriptionTier
from app.services.auth import hash_password, create_access_token

# Use a test database — same as production but with _test suffix
# Falls back to in-memory SQLite if no test DB configured
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db():
    """Provide a clean database session per test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSession() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db):
    """Provide an async test client with DB override."""
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sugar_user(db):
    """Create a sugar daddy user with profile and subscription."""
    user = User(
        email="testsd@test.com",
        password_hash=hash_password("testpass123"),
        user_type=UserType.ESTABLISHED,
    )
    db.add(user)
    await db.flush()

    from datetime import date
    profile = Profile(
        user_id=user.id,
        display_name="Test SD",
        date_of_birth=date(1988, 5, 15),
        gender=Gender.MALE,
        city="Miami",
    )
    db.add(profile)

    sub = Subscription(user_id=user.id, tier=SubscriptionTier.FREE)
    db.add(sub)

    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id)
    return {"user": user, "profile": profile, "sub": sub, "token": token}


@pytest_asyncio.fixture
async def attractive_user(db):
    """Create an attractive member with profile."""
    user = User(
        email="testsb@test.com",
        password_hash=hash_password("testpass123"),
        user_type=UserType.PLUS,
    )
    db.add(user)
    await db.flush()

    from datetime import date
    profile = Profile(
        user_id=user.id,
        display_name="Test SB",
        date_of_birth=date(1998, 7, 20),
        gender=Gender.FEMALE,
        city="Miami",
    )
    db.add(profile)

    sub = Subscription(user_id=user.id, tier=SubscriptionTier.FREE)
    db.add(sub)

    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id)
    return {"user": user, "profile": profile, "sub": sub, "token": token}


@pytest_asyncio.fixture
async def premium_user(db):
    """Create a sugar daddy with active Premium subscription."""
    user = User(
        email="testpremium@test.com",
        password_hash=hash_password("testpass123"),
        user_type=UserType.ESTABLISHED,
    )
    db.add(user)
    await db.flush()

    from datetime import date
    profile = Profile(
        user_id=user.id,
        display_name="Premium SD",
        date_of_birth=date(1985, 3, 10),
        gender=Gender.MALE,
        city="New York",
    )
    db.add(profile)

    sub = Subscription(
        user_id=user.id,
        tier=SubscriptionTier.PLUS,
        is_active=True,
        stripe_customer_id="cus_test_premium",
        stripe_subscription_id="sub_test_premium",
    )
    db.add(sub)

    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id)
    return {"user": user, "profile": profile, "sub": sub, "token": token}


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Isolation
#
# Registration schedules background work that opens a *sync* engine against
# DATABASE_URL_SYNC and calls Stripe, Resend and the audience API. Under test
# that database isn't running, so the whole suite blocked on a TCP timeout
# rather than failing. Nothing here should reach the network.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def no_external_io(monkeypatch):
    """Neutralise outbound calls and background side effects."""
    import app.routers.auth as auth_router

    monkeypatch.setattr(auth_router, "_post_registration_tasks", lambda *a, **k: None)

    def _blocked(*args, **kwargs):
        raise AssertionError(
            "A test attempted a real HTTP request. Stub the caller instead."
        )

    for name in ("post", "get", "put", "patch", "delete", "request"):
        monkeypatch.setattr(f"httpx.{name}", _blocked, raising=False)

    # A dummy key, not a blank one: billing returns 503 before validating
    # anything when Stripe is unconfigured, which masks the 400s the tests are
    # actually checking. Requests never reach Stripe — the paths under test
    # return before any API call.
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_dummy_not_used", raising=False)
    monkeypatch.setattr(settings, "RESEND_API_KEY", "", raising=False)
    monkeypatch.setattr(settings, "SENDGRID_API_KEY", "", raising=False)
    # Signature verification is local HMAC, no network. Without a secret the
    # webhook skips verification entirely, so the security test can't fail.
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_test_dummy", raising=False)


@pytest.fixture(autouse=True)
def no_rate_limits():
    """Limits are per-process and shared, so the sixth registration in a run
    returns 429 regardless of which test made it. Patching Limiter.limit is
    too late — the decorators are applied at import — so the limiter itself is
    switched off."""
    limiters = []
    for obj in (app.state.__dict__.get("limiter"),):
        if obj is not None:
            limiters.append(obj)
    for module in ("app.routers.auth", "app.routers.profiles"):
        try:
            mod = __import__(module, fromlist=["limiter"])
            if hasattr(mod, "limiter"):
                limiters.append(mod.limiter)
        except Exception:
            pass

    previous = [(l, getattr(l, "enabled", True)) for l in limiters]
    for l in limiters:
        l.enabled = False
    yield
    for l, was in previous:
        l.enabled = was
