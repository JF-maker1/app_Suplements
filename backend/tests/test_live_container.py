import pytest
import httpx
import os
import sys

# Konfigurace
BASE_URL = "http://localhost:8000"
TIMEOUT = 60.0 # Gemini může být pomalé
TEST_IMAGE_PATH = os.path.join(os.path.dirname(__file__), "../../_legacy_sprint01/produkt01_image.jpg")

@pytest.fixture
def client():
    """Vytvoří HTTP klienta pro komunikaci s Docker kontejnerem."""
    with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT) as c:
        yield c

def test_container_health(client):
    """T1: Ověří, že kontejner běží a odpovídá."""
    try:
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "online"
        print("\n✅ T1 Health Check: PASS")
    except httpx.ConnectError:
        pytest.fail("❌ Nelze se připojit k localhost:8000. Běží Docker kontejner?")

def test_validation_bad_file_type(client):
    """T2: Ověří odolnost proti špatnému typu souboru."""
    # Pošleme textový soubor jako 'file'
    files = {"file": ("test.txt", b"Toto neni obrazek", "text/plain")}
    
    response = client.post("/scan/analyze", files=files)
    
    # Očekáváme 400 Bad Request (ošetřeno v routeru)
    assert response.status_code == 400
    assert "image" in response.json()["detail"]
    print("\n✅ T2 Bad File Type: PASS")

def test_validation_missing_file(client):
    """T3: Ověří odolnost proti chybějícímu souboru."""
    # Žádné soubory
    response = client.post("/scan/analyze")
    
    # Očekáváme 422 (FastAPI default validation)
    assert response.status_code == 422
    print("\n✅ T3 Missing File: PASS")

@pytest.mark.skipif(not os.path.exists(TEST_IMAGE_PATH), reason="Testovací obrázek nenalezen")
def test_real_analysis_live(client):
    """
    T4: SKUTEČNÉ VOLÁNÍ GEMINI API.
    Ověří end-to-end funkčnost celého stacku.
    """
    print(f"\n⚠️ Odesílám reálný obrázek do Gemini ({TEST_IMAGE_PATH})... Čekejte.")
    
    with open(TEST_IMAGE_PATH, "rb") as f:
        files = {"file": ("produkt.jpg", f, "image/jpeg")}
        response = client.post("/scan/analyze", files=files)
    
    # Diagnostika při chybě
    if response.status_code != 200:
        print(f"❌ API Error: {response.text}")
    
    assert response.status_code == 200
    data = response.json()
    
    # Validace struktury odpovědi
    assert data["status"] == "PARSED"
    result = data["data"]
    
    # Kontrola klíčových polí (Schema Sanitizer Verification)
    assert "full_name" in result
    assert isinstance(result["composition"]["active_ingredients"], list)
    
    print(f"\n✅ T4 Real Analysis: PASS (Produkt: {result.get('full_name')})")

if __name__ == "__main__":
    # Umožní spustit test přímo přes python backend/tests/test_live_container.py
    sys.exit(pytest.main(["-v", "-s", __file__]))