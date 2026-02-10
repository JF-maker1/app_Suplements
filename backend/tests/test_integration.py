import os
import sys
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# Přidání root adresáře do path pro import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.services.gemini_service import GeminiService

client = TestClient(app)

# --- MOCK DATA ---
MOCK_GEMINI_RESPONSE = {
    "full_name": "SuperKick 3000",
    "brand": "PowerGym",
    "category": "Doplňky stravy",
    "composition": {
        "active_ingredients": [{"name": "Kofein", "amount": "200mg"}],
        "excipients": ["Magnesium Stearate"],
        "nutritional_table": {"energy_kcal": "0"},
        "allergen_warning": [],
    },
    "specs": {"net_quantity": "60 kapslí", "expiry_date_indicated": True},
    "marketing": {"claims": ["Energy Boost"], "description": "Nakopávač pro trénink."},
    "detected_price": 499.0,
    "currency": "CZK",
}


class MockFileState:
    name = "PROCESSING"


class MockGeminiFile:
    def __init__(self):
        self.name = "files/mock-file-123"
        self.state = MockFileState()

    def delete(self):
        pass


# --- TESTS ---


def test_health_check():
    """Ověří, že API běží."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "online"


@patch("google.generativeai.upload_file")
@patch("google.generativeai.get_file")
@patch("google.generativeai.GenerativeModel")
def test_analyze_endpoint_flow(mock_model_cls, mock_get_file, mock_upload_file):
    """
    Simuluje kompletní průchod endpointem /scan/analyze.
    Ověřuje:
    1. Sanitizaci schématu (že neobsahuje $defs, anyOf atd.)
    2. Volání modelu se správnými parametry.
    3. Správný návrat dat z endpointu.
    """

    # 1. SETUP MOCKS
    # Mock File API flow
    mock_file = MockGeminiFile()
    mock_file.state.name = "ACTIVE"  # Hned aktivní, přeskočíme loop
    mock_upload_file.return_value = mock_file
    mock_get_file.return_value = mock_file

    # Mock GenerativeModel & generate_content
    mock_model_instance = MagicMock()
    mock_model_cls.return_value = mock_model_instance

    # Async mock pro generate_content (protože v servise voláme run_in_threadpool)
    # Note: run_in_threadpool spouští sync funkci v threadu, takže mockujeme return value
    mock_response = MagicMock()
    mock_response.text = (
        str(MOCK_GEMINI_RESPONSE).replace("'", '"').replace("True", "true")
    )
    mock_model_instance.generate_content.return_value = mock_response

    # 2. EXECUTE REQUEST
    # Vytvoříme dummy obrázek
    files = {"file": ("test_image.jpg", b"fake_image_bytes", "image/jpeg")}
    response = client.post("/scan/analyze", files=files)

    # 3. ASSERTIONS (VALIDACE LOGIKY)

    # A) Status Code
    if response.status_code != 200:
        print("Response Error:", response.json())
    assert response.status_code == 200

    # B) Response Structure
    json_data = response.json()
    assert json_data["status"] == "PARSED"
    assert json_data["data"]["full_name"] == "SuperKick 3000"

    # C) CRITICAL: Schema Sanitization Check
    # Zkontrolujeme, co bylo předáno do generation_config
    call_args = mock_model_instance.generate_content.call_args
    assert call_args is not None, "generate_content nebylo zavoláno!"

    # Získání kwargs (v kódu servisy je generation_config předáváno jako kwarg)
    _, kwargs = call_args
    gen_config = kwargs.get("generation_config")

    assert gen_config is not None
    schema = gen_config.response_schema

    # Ověření, že sanitizér fungoval (nesmí obsahovat Pydantic v2 artefakty)
    print("\n[DEBUG] Sanitized Schema Keys:", schema.keys())
    assert "$defs" not in schema, "CHYBA: Schéma obsahuje $defs (Sanitizer selhal)"
    assert "title" not in schema, "CHYBA: Schéma obsahuje title (Sanitizer selhal)"
    assert "anyOf" not in str(schema), "CHYBA: Schéma obsahuje anyOf (Sanitizer selhal)"

    print("✅ TEST PASSED: Endpoint funguje a Schéma je čisté.")


def test_sanitizer_logic_direct():
    """Unit test přímo pro metodu _resolve_and_sanitize."""
    service = GeminiService()

    # Pydantic v2 Raw Schema (Simulace problému)
    raw_schema = {
        "$defs": {
            "Ingredient": {
                "properties": {"name": {"type": "string"}},
                "title": "Ingredient",
                "type": "object",
            }
        },
        "properties": {
            "composition": {"anyOf": [{"$ref": "#/$defs/Ingredient"}, {"type": "null"}]}
        },
        "title": "MainModel",
        "type": "object",
    }

    clean_schema = service._resolve_and_sanitize(raw_schema)

    # Validace
    assert "$defs" not in clean_schema
    assert "title" not in clean_schema
    # anyOf by mělo být zploštělé na první variantu -> Ingredient -> properties -> name
    assert "properties" in clean_schema["properties"]["composition"]
    assert "name" in clean_schema["properties"]["composition"]["properties"]

    print("✅ TEST PASSED: Sanitizer Logic Direct.")


if __name__ == "__main__":
    # Jednoduchý spouštěč pokud nemáme pytest
    try:
        test_sanitizer_logic_direct()
        print(
            "Integration tests require pytest/httpx. Run: 'pytest backend/tests/test_integration.py'"
        )
    except Exception as e:
        print(f"❌ TEST FAILED: {e}")
