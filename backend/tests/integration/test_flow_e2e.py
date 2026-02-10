from unittest.mock import patch
from app.services.orchestrator import OrchestratorResult

# Note: Using 'client' fixture from conftest.py which uses TestClient


@patch("app.services.orchestrator.OrchestratorService.process_user_query")
def test_chat_widget_flow_success(mock_process, client):
    """
    E2E Simulation: Frontend calls /agent/chat -> Backend delegates to Orchestrator -> Response.
    Everything is mocked at the Orchestrator level to ensure deterministic output.
    """
    # 1. Setup Mock Response
    expected_response = OrchestratorResult(
        type="text",
        content="This is a mocked response from the Brain.",
        metadata={"intent": "GENERAL_CHAT"},
    )

    # Make the mock async-compatible
    mock_process.return_value = expected_response

    # 2. Execute HTTP Request
    payload = {"query": "Hello RDM", "history": []}

    response = client.post("/agent/chat", json=payload)

    # 3. Assertions
    assert response.status_code == 200
    data = response.json()

    assert data["type"] == "text"
    assert data["content"] == "This is a mocked response from the Brain."
    assert data["metadata"]["intent"] == "GENERAL_CHAT"

    # Verify Orchestrator was called with correct args
    mock_process.assert_called_once()


@patch("app.services.orchestrator.OrchestratorService.process_user_query")
def test_chat_widget_flow_error_handling(mock_process, client):
    """
    E2E Simulation: Orchestrator crashes -> API should return graceful error, not 500 crash.
    """
    # 1. Setup Mock Error
    mock_process.side_effect = Exception("Critical Brain Failure")

    # 2. Execute HTTP Request
    payload = {"query": "Crash me", "history": []}
    response = client.post("/agent/chat", json=payload)

    # 3. Assertions
    # API Router catches generic exceptions and returns 200 with error message (Fail-Safe)
    # OR returns 500 if unhandled. The agent_chat.py logic uses try/except block.

    assert (
        response.status_code == 200
    )  # Expecting Fail-Safe response if implemented correctly in router
    data = response.json()

    assert data["type"] == "text"
    assert "Omlouvám se" in data["content"]  # Check for localized error message
    assert "Critical Brain Failure" in data["metadata"]["error"]
