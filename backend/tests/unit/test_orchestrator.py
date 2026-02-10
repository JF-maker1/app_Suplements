import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.orchestrator import OrchestratorService, OrchestratorResult

@pytest.fixture
def orchestrator(mocker):
    """
    Initializes Orchestrator with all sub-services mocked.
    """
    # Patch sub-services BEFORE initialization to avoid real init logic
    mocker.patch("app.services.orchestrator.IntentService")
    mocker.patch("app.services.orchestrator.SqlService")
    mocker.patch("app.services.orchestrator.VectorService")
    
    # Initialize
    service = OrchestratorService()
    
    # Setup standard mocks for instance methods
    service.intent_service.classify_intent = AsyncMock()
    service.sql_service.generate_sql = AsyncMock()
    service.sql_service.execute_sql = AsyncMock()
    service.vector_service.search_vectors = AsyncMock()
    
    # Mock private chat handler to avoid Gemini calls
    service._handle_general_chat = AsyncMock()
    
    return service

@pytest.mark.asyncio
async def test_routing_vector_search(orchestrator):
    """Test routing to Vector Search when intent is VECTOR_SEARCH."""
    # 1. Setup
    orchestrator.intent_service.classify_intent.return_value = {"intent": "VECTOR_SEARCH"}
    orchestrator.vector_service.search_vectors.return_value = [{"full_name": "Protein X"}]
    
    # 2. Execute
    result = await orchestrator.process_user_query("Find protein")
    
    # 3. Assert
    orchestrator.vector_service.search_vectors.assert_called_once()
    assert result.type == "product_cards"
    assert len(result.payload) == 1

@pytest.mark.asyncio
async def test_routing_sql_analysis(orchestrator):
    """Test routing to SQL Service when intent is SQL_ANALYSIS."""
    # 1. Setup
    orchestrator.intent_service.classify_intent.return_value = {"intent": "SQL_ANALYSIS"}
    orchestrator.sql_service.generate_sql.return_value = "SELECT * FROM products"
    orchestrator.sql_service.execute_sql.return_value = [{"price": 100}]
    
    # 2. Execute
    result = await orchestrator.process_user_query("Show prices")
    
    # 3. Assert
    orchestrator.sql_service.generate_sql.assert_called_once()
    orchestrator.sql_service.execute_sql.assert_called_once()
    assert result.type == "data_table"

@pytest.mark.asyncio
async def test_routing_fallback_to_chat(orchestrator):
    """Test routing to General Chat when intent is GENERAL_CHAT."""
    # 1. Setup
    orchestrator.intent_service.classify_intent.return_value = {"intent": "GENERAL_CHAT"}
    orchestrator._handle_general_chat.return_value = OrchestratorResult(type="text", content="Hello")
    
    # 2. Execute
    result = await orchestrator.process_user_query("Hello")
    
    # 3. Assert
    orchestrator._handle_general_chat.assert_called_once()
    assert result.content == "Hello"