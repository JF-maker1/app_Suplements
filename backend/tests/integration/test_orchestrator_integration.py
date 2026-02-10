import pytest
from unittest.mock import AsyncMock
from app.services.orchestrator import OrchestratorService, OrchestratorResult

# --- FIXTURES ---


@pytest.fixture
def mock_subservices(mocker):
    """
    Patches class constructors BEFORE OrchestratorService is initialized.
    This ensures Orchestrator uses mocks instead of real services.
    """
    return {
        "intent": mocker.patch("app.services.orchestrator.IntentService"),
        "sql": mocker.patch("app.services.orchestrator.SqlService"),
        "vector": mocker.patch("app.services.orchestrator.VectorService"),
    }


@pytest.fixture
def orchestrator(mock_subservices):
    """
    Initializes Orchestrator with mocked dependencies.
    """
    service = OrchestratorService()

    # Setup Instance Mocks (Async Methods)
    service.intent_service.classify_intent = AsyncMock()
    service.sql_service.generate_sql = AsyncMock()
    service.sql_service.execute_sql = AsyncMock()
    service.vector_service.search_vectors = AsyncMock()

    # Mock private chat handler to keep tests focused on routing
    service._handle_general_chat = AsyncMock()
    service._handle_general_chat.return_value = OrchestratorResult(
        type="text", content="General Chat Fallback"
    )

    return service


# --- TESTS ---


@pytest.mark.asyncio
async def test_uc4_001_routing_vector(orchestrator):
    """
    Ověřuje routing pro Intent: VECTOR_SEARCH.
    Očekávání: Zavolá se VectorService, SQLService se NEVOLÁ.
    """
    # 1. SETUP
    orchestrator.intent_service.classify_intent.return_value = {
        "intent": "VECTOR_SEARCH"
    }

    # Mock Vector Result
    orchestrator.vector_service.search_vectors.return_value = [
        {"full_name": "Sleep Aid 3000", "similarity": 0.85}
    ]

    # 2. ACTION
    result = await orchestrator.process_user_query("Něco na spaní")

    # 3. ASSERT
    # Check Intent Call
    orchestrator.intent_service.classify_intent.assert_called_once()

    # Check Vector Call
    orchestrator.vector_service.search_vectors.assert_called_once_with(
        "Něco na spaní", limit=5, threshold=0.4
    )

    # Check SQL NOT Called (Isolation Check)
    orchestrator.sql_service.generate_sql.assert_not_called()

    # Check Result Format
    assert result.type == "product_cards"
    assert len(result.payload) == 1
    assert result.payload[0]["full_name"] == "Sleep Aid 3000"


@pytest.mark.asyncio
async def test_uc4_002_routing_sql(orchestrator):
    """
    Ověřuje routing pro Intent: SQL_ANALYSIS.
    Očekávání: Zavolá se SqlService (Generate -> Execute), VectorService se NEVOLÁ.
    """
    # 1. SETUP
    orchestrator.intent_service.classify_intent.return_value = {
        "intent": "SQL_ANALYSIS"
    }

    # Mock SQL Chain
    fake_sql = "SELECT * FROM products WHERE price < 500"
    fake_data = [{"product": "Cheap Protein", "price": 400}]

    orchestrator.sql_service.generate_sql.return_value = fake_sql
    orchestrator.sql_service.execute_sql.return_value = fake_data

    # 2. ACTION
    result = await orchestrator.process_user_query("Produkty pod 500")

    # 3. ASSERT
    # Check Intent Call
    orchestrator.intent_service.classify_intent.assert_called_once()

    # Check SQL Calls
    orchestrator.sql_service.generate_sql.assert_called_once_with("Produkty pod 500")
    orchestrator.sql_service.execute_sql.assert_called_once_with(fake_sql)

    # Check Vector NOT Called
    orchestrator.vector_service.search_vectors.assert_not_called()

    # Check Result Format
    assert result.type == "data_table"
    assert result.payload == fake_data
    assert result.metadata["sql"] == fake_sql


@pytest.mark.asyncio
async def test_uc4_003_routing_fallback_general(orchestrator):
    """
    Ověřuje routing pro Intent: GENERAL_CHAT.
    """
    # 1. SETUP
    orchestrator.intent_service.classify_intent.return_value = {
        "intent": "GENERAL_CHAT"
    }

    # 2. ACTION
    result = await orchestrator.process_user_query("Ahoj světe")

    # 3. ASSERT
    orchestrator._handle_general_chat.assert_called_once()
    orchestrator.vector_service.search_vectors.assert_not_called()
    orchestrator.sql_service.generate_sql.assert_not_called()

    assert result.content == "General Chat Fallback"
