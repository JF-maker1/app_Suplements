import pytest
from unittest.mock import MagicMock, AsyncMock
from app.services.etl_service import EtlService

# --- FIXTURES ---

@pytest.fixture
def mock_db_service(mocker):
    """
    R7 Mitigation: Prevents writing to real DB.
    Mocks the SupabaseService class used inside EtlService.
    We patch the class where it is IMPORTED (in etl_service), not where it is defined.
    """
    return mocker.patch("app.services.etl_service.SupabaseService")

@pytest.fixture
def etl_service(mock_db_service):
    """
    Initializes EtlService with mocked DB.
    """
    # Initialize service
    service = EtlService()
    
    # Explicitly replace the db instance with our mock return value
    # (EtlService.__init__ creates self.db = SupabaseService())
    service.db = mock_db_service.return_value 
    
    return service

# --- TESTS ---

@pytest.mark.asyncio
async def test_etl_process_happy_path(etl_service, mocker):
    """
    Scenario: Gemini API works perfectly on 1st try.
    Expected: Returns True, Updates DB with data.
    """
    # 1. SETUP: Mock AI Response (R6 Mitigation)
    expected_data = {
        "normalized_ingredients": [{"name": "Whey", "amount": 80}],
        "health_flags": {"is_vegan": False}
    }
    
    # Patching the internal method that calls Gemini to isolate service logic from AI lib
    mock_generate = mocker.patch.object(
        etl_service, 
        '_generate_with_model', 
        new_callable=AsyncMock
    )
    mock_generate.return_value = expected_data

    # 2. EXECUTE
    result = await etl_service.process_scan("scan_123", "raw text content")

    # 3. ASSERT
    assert result is True
    
    # Verify DB update was called with correct data
    etl_service.db.update_scan_data.assert_called_once_with(
        "scan_123", 
        {"derived_data": expected_data}
    )

@pytest.mark.asyncio
async def test_etl_process_retry_logic(etl_service, mocker):
    """
    Scenario: Gemini API fails twice, succeeds on 3rd try.
    Expected: Service retries 3 times, eventually returns True.
    """
    # 1. SETUP: Mock Sequence of failures then success
    mock_generate = mocker.patch.object(
        etl_service, 
        '_generate_with_model', 
        new_callable=AsyncMock
    )
    # Side effect: Raise exception 2x, then return success
    mock_generate.side_effect = [
        Exception("API Error 500"), 
        Exception("API Timeout"), 
        {"status": "recovered_data"}
    ]

    # Mock asyncio.sleep to skip waiting time during tests
    mock_sleep = mocker.patch("asyncio.sleep", new_callable=AsyncMock)

    # 2. EXECUTE
    result = await etl_service.process_scan("scan_retry_123", "raw text")

    # 3. ASSERT
    assert result is True
    
    # Must have tried 3 times (2 failures + 1 success)
    assert mock_generate.call_count == 3
    
    # Verify sleep was called (backoff logic)
    assert mock_sleep.call_count >= 2
    
    # Verify final DB write uses the successful data
    etl_service.db.update_scan_data.assert_called_with(
        "scan_retry_123", 
        {"derived_data": {"status": "recovered_data"}}
    )

@pytest.mark.asyncio
async def test_etl_process_fail_safe(etl_service, mocker):
    """
    Scenario: Gemini API fails completely (All retries exhausted).
    Expected: Returns False, Does NOT write to DB (Soft Fail), Does not crash.
    """
    # 1. SETUP: Mock permanent failure
    mock_generate = mocker.patch.object(
        etl_service, 
        '_generate_with_model', 
        new_callable=AsyncMock
    )
    # Always raise exception
    mock_generate.side_effect = Exception("Critical API Failure")

    # Speed up tests
    mocker.patch("asyncio.sleep", new_callable=AsyncMock)

    # 2. EXECUTE
    result = await etl_service.process_scan("scan_fail_123", "raw text")

    # 3. ASSERT
    assert result is False
    
    # Logic in EtlService returns False immediately, NO DB update is made.
    # The previous test expected a DB call with None, but the code does not do that.
    # We assert that NO database update is attempted in case of total failure.
    etl_service.db.update_scan_data.assert_not_called()