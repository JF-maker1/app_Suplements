import pytest
import math
from unittest.mock import MagicMock, AsyncMock
from typing import List, Dict, Any

from app.services.vector_service import VectorService

# --- HELPERS: MATH & SIMULATION ---


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Vypočítá cosine similarity pro simulaci pgvector chování."""
    dot_product = sum(a * b for a, b in zip(v1, v2))
    magnitude1 = math.sqrt(sum(a * a for a in v1))
    magnitude2 = math.sqrt(sum(a * a for a in v2))
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    return dot_product / (magnitude1 * magnitude2)


class MockVectorDB:
    """
    Stateful Mock simulující chování Supabase tabulky a RPC funkce 'match_documents'.
    Umožňuje testovat sémantické vyhledávání in-memory.
    """

    def __init__(self):
        self.records = []  # List[Dict]

    def insert(self, record: Dict[str, Any]):
        self.records.append(record)

    def match_documents(self, params: Dict[str, Any]):
        query_embedding = params["query_embedding"]
        threshold = params["match_threshold"]
        limit = params["match_count"]

        results = []
        for record in self.records:
            if not record.get("embedding"):
                continue

            similarity = cosine_similarity(query_embedding, record["embedding"])

            if similarity >= threshold:
                # Simulace struktury, kterou vrací Supabase RPC
                result_row = record.copy()
                result_row["similarity"] = similarity
                # RPC nevrací embedding, pokud není explicitně žádán, pro lehkost
                result_row.pop("embedding", None)
                results.append(result_row)

        # Sort by similarity DESC
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:limit]


# --- FIXTURES ---


@pytest.fixture
def mock_db_simulator():
    return MockVectorDB()


@pytest.fixture
def vector_service(mocker, mock_db_simulator):
    """
    Inicializuje VectorService s napojením na MockVectorDB.
    """
    # 1. Patch DB Service class
    mock_supabase_cls = mocker.patch("app.services.vector_service.SupabaseService")
    mock_db_instance = mock_supabase_cls.return_value

    # 2. Wire up RPC to Simulator
    # capture params passed to rpc call
    def rpc_side_effect(func_name, params):
        if func_name == "match_documents":
            data = mock_db_simulator.match_documents(params)
            # Mock response object structure
            mock_res = MagicMock()
            mock_res.data = data

            # Create an object that has an .execute() method returning the response
            mock_exec = MagicMock()
            mock_exec.execute.return_value = mock_res
            return mock_exec
        return MagicMock()

    mock_db_instance.client.rpc.side_effect = rpc_side_effect

    # Init service
    service = VectorService()
    service.db = mock_db_instance  # Explicit injection
    return service


# --- TESTS ---


@pytest.mark.asyncio
async def test_uc2_001_semantic_accuracy(vector_service, mock_db_simulator, mocker):
    """
    Testuje sémantickou přesnost vyhledávání pomocí syntetických vektorů.
    Scénář:
    - DB obsahuje "Sleep Product" (vektor 0.1) a "Energy Product" (vektor 0.9).
    - Query je "Sleep" (vektor 0.1).
    - Očekávání: "Sleep Product" je první s similarity ~1.0.
    """
    # 1. SETUP: Deterministické Vektory (3072 dim)
    # Vektor A: [1, 0, 0, ...] (Sleep) - ortogonální k B
    vec_sleep = [0.0] * 3072
    vec_sleep[0] = 1.0
    # Vektor B: [0, 1, 0, ...] (Energy) - ortogonální k A
    vec_energy = [0.0] * 3072
    vec_energy[1] = 1.0
    # Query: [1, 0, 0, ...] - Identický se Sleep
    vec_query = [0.0] * 3072
    vec_query[0] = 1.0

    # 2. SEED DB (In-Memory Simulator)
    mock_db_simulator.insert(
        {"id": "prod_sleep", "full_name": "Sleep Well", "embedding": vec_sleep}
    )
    mock_db_simulator.insert(
        {"id": "prod_energy", "full_name": "Energy Kick", "embedding": vec_energy}
    )

    # 3. MOCK GENERATION
    # Patchujeme embed_content přímo v google.generativeai
    mock_genai = mocker.patch("google.generativeai.embed_content")
    mock_genai.return_value = {"embedding": vec_query}

    # 4. ACTION
    results = await vector_service.search_vectors("Sleep", limit=5, threshold=0.5)

    # 5. ASSERT
    assert len(results) >= 1
    top_match = results[0]

    # Sleep Well by měl být první
    assert top_match["id"] == "prod_sleep"
    # Similarity by měla být 1.0 (identické vektory)
    assert top_match["similarity"] > 0.99

    # Energy Kick by tam neměl být (ortogonální vektor -> similarity 0.0 -> pod threshold 0.5)
    ids = [r["id"] for r in results]
    assert "prod_energy" not in ids


@pytest.mark.asyncio
async def test_uc2_005_dimensions_validation(vector_service, mocker):
    """
    Validuje, že služba odmítne vektory nesprávné délky (např. 768 místo 3072).
    """
    # 1. SETUP: Mock return value s chybnou dimenzí
    wrong_vec = [0.1] * 768  # Starý model

    mock_genai = mocker.patch("google.generativeai.embed_content")
    mock_genai.return_value = {"embedding": wrong_vec}

    # Mock Logger pro ověření warningu
    mock_logger = mocker.patch("app.services.vector_service.logger")

    # 2. ACTION
    results = await vector_service.search_vectors("Test Query")

    # 3. ASSERT
    assert results == []
    # Ověříme varování v logu
    assert any(
        "Dimension Mismatch" in str(call) for call in mock_logger.warning.call_args_list
    )


@pytest.mark.asyncio
async def test_uc2_002_fallback_logic(vector_service, mocker):
    """
    Testuje odolnost proti výpadku modelu (Fallback).
    1. pokus -> Selže (Simulace 404 nebo 500)
    2. pokus -> Uspěje
    """
    # 1. SETUP
    vec_valid = [0.0] * 3072

    mock_genai = mocker.patch("google.generativeai.embed_content")
    # Side effect: 1x Exception, 1x Success
    mock_genai.side_effect = [
        Exception("404 Model Not Found"),
        {"embedding": vec_valid},
    ]

    # Mock sleep
    mock_sleep = mocker.patch("asyncio.sleep", new_callable=AsyncMock)

    # 2. ACTION
    embedding = await vector_service.generate_embedding("Retry Me")

    # 3. ASSERT
    assert embedding is not None
    assert len(embedding) == 3072
    assert mock_genai.call_count == 2
    mock_sleep.assert_called()
