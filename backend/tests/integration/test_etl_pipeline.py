import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from app.main import app
from app.services.etl_service import EtlService
from app.schemas import (
    ProductAnalysisResult,
    CompositionData,
    ProductSpecs,
    MarketingData,
)

# --- FIXTURES & SETUP ---


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_product_result():
    """Vrátí validní Pydantic model pro mockování Gemini Vision."""
    return ProductAnalysisResult(
        full_name="Mock Protein",
        brand="MockBrand",
        category="Supplements",
        composition=CompositionData(
            active_ingredients=[{"name": "Whey", "amount": "80g"}],
            excipients=[],
            nutritional_table={"energy_kcal": "300"},
            allergen_warning=[],
        ),
        specs=ProductSpecs(expiry_date_indicated=True),
        marketing=MarketingData(claims=["Best"], description="Desc"),
        detected_price=100.0,
        currency="CZK",
        source_url="http://mock.com",
    )


# --- SCENARIO A: RESILIENCE (Service Layer) ---


@pytest.mark.asyncio
async def test_uc1_002_resilience_api_rotation(mocker):
    """
    Simuluje chování EtlService při chybě 429 (Quota Exceeded).
    Očekávání: Služba zachytí chybu, počká (mock sleep) a zkusí to znovu (úspěšně).
    """
    # 1. SETUP: Mock EtlService dependencies
    # Patchujeme Supabase uvnitř modulu etl_service
    mock_db_cls = mocker.patch("app.services.etl_service.SupabaseService")
    mock_db = mock_db_cls.return_value

    service = EtlService()
    service.db = mock_db  # Inject mock DB instance

    # 2. SETUP: Mock Gemini Generation logic
    # Mockujeme interní metodu _generate_with_model, abychom se vyhnuli reálnému google-generativeai
    # Side Effect: 1. volání -> Exception 429, 2. volání -> Success Dict
    mock_generate = mocker.patch.object(
        service, "_generate_with_model", new_callable=AsyncMock
    )

    mock_generate.side_effect = [
        Exception("429 Resource has been exhausted (e.g. check quota)."),  # Fail 1
        {
            "normalized_ingredients": [{"name": "Syrovátka", "amount_mg": 80000}]
        },  # Success 2
    ]

    # Mock asyncio.sleep to speed up test
    mock_sleep = mocker.patch("asyncio.sleep", new_callable=AsyncMock)

    # 3. ACTION
    result = await service.process_scan("scan_id_123", "Raw Text Context")

    # 4. ASSERT
    assert result is True
    assert mock_generate.call_count == 2  # Musel zkusit 2x

    # Ověříme, že po 1. chybě volal sleep
    mock_sleep.assert_called()

    # Ověříme zápis do DB
    service.db.update_scan_data.assert_called_with(
        "scan_id_123",
        {
            "derived_data": {
                "normalized_ingredients": [{"name": "Syrovátka", "amount_mg": 80000}]
            }
        },
    )


# --- SCENARIO B: VALIDATION (Router Layer) ---


@pytest.mark.asyncio
async def test_uc1_003_validation_invalid_format(client):
    """
    Ověřuje, že API odmítne PDF soubor.
    Validace probíhá v Routeru před voláním služeb.
    """
    # 1. SETUP: Prepare Invalid File
    files = {"file": ("document.pdf", b"%PDF-1.4 content", "application/pdf")}

    # 2. ACTION
    # Note: TestClient in FastAPI is synchronous wrapper around async app, so no await needed here for client calls
    response = client.post("/scan/analyze", files=files)

    # 3. ASSERT
    assert response.status_code == 400
    assert "File must be an image" in response.json()["detail"]


# --- SCENARIO C: ATOMICITY (Router Layer) ---


@pytest.mark.asyncio
async def test_uc1_004_atomicity_rollback(client, mocker, mock_product_result):
    """
    Ověřuje transakční integritu.
    Pokud selže INSERT do DB, musí se smazat nahraný obrázek ze Storage.
    """
    # 1. SETUP: Mock Dependencies in scan.py

    # Mock Gemini Service (Analysis Success)
    # Musíme patchovat instanci, která je už vytvořená v scan.py jako `gemini_service`
    mock_analyze = mocker.patch(
        "app.routers.scan.gemini_service.analyze_image", new_callable=AsyncMock
    )
    mock_analyze.return_value = mock_product_result

    # Mock Supabase Service (Upload Success, Insert FAIL, Delete Success)
    # Patchujeme metody instance `db_service` v scan.py

    # A) Upload -> vrátí URL
    mocker.patch(
        "app.routers.scan.db_service.upload_file",
        return_value="https://mock.storage/image.jpg",
    )

    # B) Delete -> Mock (pro ověření rollbacku)
    mock_delete = mocker.patch("app.routers.scan.db_service.delete_file")

    # C) Insert -> RAISE EXCEPTION (Simulace výpadku DB)
    mocker.patch(
        "app.routers.scan.db_service.insert_scan_data",
        side_effect=Exception("DB Connection Lost"),
    )

    # D) Background Tasks (EtlService) - nesmí se spustit
    mock_etl_process = mocker.patch(
        "app.routers.scan.etl_service.process_scan", new_callable=AsyncMock
    )

    # 2. ACTION
    files = {"file": ("test.jpg", b"fake_bytes", "image/jpeg")}

    # Očekáváme 500 nebo ošetřenou chybu, ale hlavně rollback
    response = client.post("/scan/analyze", files=files)

    # 3. ASSERT
    # Chyba 500 je očekávaná, protože router zachytí Exception a vyhodí HTTPException 500
    assert response.status_code == 500
    assert "DB Connection Lost" in response.json()["detail"]

    # CRITICAL: Verify Rollback (Smazání souboru)
    mock_delete.assert_called_once()

    # FIX: Robustní kontrola argumentů (podpora pro args i kwargs)
    call_args = mock_delete.call_args
    # call_args je tuple (args, kwargs)

    file_name_arg = None
    if call_args.args:
        # Voláno jako delete_file("nazev")
        file_name_arg = call_args.args[0]
    elif "file_name" in call_args.kwargs:
        # Voláno jako delete_file(file_name="nazev")
        file_name_arg = call_args.kwargs["file_name"]

    assert (
        file_name_arg is not None
    ), "delete_file was called but argument 'file_name' could not be found in args or kwargs"
    assert file_name_arg.endswith(".jpg")
    assert file_name_arg.startswith("scan_")

    # Verify ETL was NOT triggered
    mock_etl_process.assert_not_called()
