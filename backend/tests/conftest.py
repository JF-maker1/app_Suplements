import pytest
import asyncio
import os
import sys
from typing import Generator
from fastapi.testclient import TestClient

# 1. PATH SETUP
# Ensures 'app' module is visible to tests
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_root = os.path.dirname(current_dir)
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

# --- CRITICAL FIX FOR UNIT TESTS (IMPORT TIME VALIDATION) ---
# Pydantic validates Settings() immediately upon import of app.main.
# We must inject dummy env vars BEFORE the import happens, otherwise
# Unit Tests (which have no real .env) will crash.
os.environ.setdefault("SUPABASE_URL", "https://mock.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "mock-key-for-unit-tests")
os.environ.setdefault("GOOGLE_API_KEY", "TEST_GUARD_KEY_POISONED")

# Late import to ensure sys.path is set
from app.main import app  # noqa: E402


# 2. EVENT LOOP FIXTURE
# Prevents "Event loop is closed" error in async tests
@pytest.fixture(scope="session")
def event_loop() -> Generator:
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


# 3. GLOBAL SECURITY LOCK (POISON PILL STRATEGY)
# Risk Mitigation: R2 (API Leakage)
@pytest.fixture(autouse=True)
def poison_google_credentials(monkeypatch):
    """
    CRITICAL: Overwrites GOOGLE_API_KEY with a dummy value for ALL tests.
    This guarantees that if a mock fails, the real API call will fail
    with 403 Forbidden/Invalid Key, preventing billing usage.
    """
    monkeypatch.setenv("GOOGLE_API_KEY", "TEST_GUARD_KEY_POISONED")
    monkeypatch.setenv("GOOGLE_API_KEY_2", "TEST_GUARD_KEY_POISONED")
    monkeypatch.setenv("SUPABASE_URL", "https://mock.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "mock-key")


# 4. DB MOCK
@pytest.fixture
def mock_supabase(mocker):
    """
    Mocks the SupabaseService to prevent real DB connections.
    """
    mock_service = mocker.patch("app.services.db.SupabaseService")
    mock_instance = mock_service.return_value

    # Default behavior for common methods
    mock_instance.client.table.return_value.select.return_value.execute.return_value.data = (
        []
    )
    mock_instance.client.rpc.return_value.execute.return_value.data = []

    return mock_instance


# 5. TEST CLIENT
@pytest.fixture(scope="module")
def client() -> Generator:
    with TestClient(app) as c:
        yield c