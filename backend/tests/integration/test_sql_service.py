import pytest
from unittest.mock import MagicMock, AsyncMock
from app.services.data_access import SqlService

# --- FIXTURES ---


@pytest.fixture
def mock_db_client(mocker):
    """
    Mockuje SupabaseService a jeho vnitřní client.rpc.
    Důležité: Nemockujeme execute_sql, ale až tu nejnižší vrstvu (DB driver).
    """
    # Patch SupabaseService inside data_access module
    mock_supabase_cls = mocker.patch("app.services.data_access.SupabaseService")
    mock_service_instance = mock_supabase_cls.return_value

    # Mock RPC chain: client.rpc("func", params).execute().data
    mock_rpc = MagicMock()
    mock_response = MagicMock()
    mock_response.data = [{"id": 1, "product_name": "Test Protein", "price": 500}]

    mock_rpc.return_value.execute.return_value = mock_response
    mock_service_instance.client.rpc = mock_rpc

    return mock_service_instance


@pytest.fixture
def sql_service(mock_db_client):
    service = SqlService()
    # Explicit injection to be sure
    service.db = mock_db_client
    return service


# --- TESTS ---


@pytest.mark.asyncio
async def test_uc3_002_injection_prevention(sql_service):
    """
    Testuje Security Validator uvnitř execute_sql.
    Vstup obsahuje zakázané klíčové slovo DROP.
    Očekáváme ValueError DŘÍVE, než se zavolá DB.
    """
    # 1. SETUP
    unsafe_query = "SELECT * FROM products; DROP TABLE scans; --"

    # 2. ACTION & ASSERT
    with pytest.raises(ValueError) as excinfo:
        await sql_service.execute_sql(unsafe_query)

    assert "Security Violation" in str(excinfo.value)

    # 3. VERIFY MOCK
    # DB RPC nesmí být vůbec zavoláno
    sql_service.db.client.rpc.assert_not_called()


@pytest.mark.asyncio
async def test_uc3_001_nl_to_sql_execution(sql_service, mocker):
    """
    Testuje kompletní tok: NL Query -> LLM -> SQL -> DB Exec -> Data.
    Mockujeme LLM (Gemini) a DB RPC.
    """
    # 1. SETUP: Mock LLM (Gemini)
    # Patch GenerativeModel used inside generate_sql
    mock_gen_model = mocker.patch("google.generativeai.GenerativeModel")
    mock_chat_session = mock_gen_model.return_value

    # Mock async response
    mock_ai_response = MagicMock()
    mock_ai_response.text = (
        "SELECT product_name, price FROM ai_analytics_view WHERE price < 500"
    )
    mock_chat_session.generate_content_async = AsyncMock(return_value=mock_ai_response)

    # 2. ACTION: Generate SQL
    user_query = "Najdi produkty pod 500 Kč"
    generated_sql = await sql_service.generate_sql(user_query)

    # Assert SQL generation
    assert "SELECT" in generated_sql
    assert "WHERE price < 500" in generated_sql

    # 3. ACTION: Execute SQL
    # V reálném flow (Orchestrator) se tento výstup předá do execute_sql
    results = await sql_service.execute_sql(generated_sql)

    # 4. ASSERT
    # Ověříme, že RPC bylo zavoláno se správným SQL
    sql_service.db.client.rpc.assert_called_once_with(
        "exec_sql", {"query": generated_sql}
    )

    # Ověříme data
    assert len(results) == 1
    assert results[0]["product_name"] == "Test Protein"
