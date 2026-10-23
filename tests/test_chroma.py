"""Integración con ChromaDB real (Sección 15.3). Descarga el modelo la primera vez.

Ejecutar con:  pytest -m chroma
"""
import pytest

from input_validation import normalize_text
from knowledge_base import DEFAULT_ENTRIES
from nlp_engine import NLPEngine

pytestmark = pytest.mark.chroma
pytest.importorskip("chromadb")


def test_real_retrieval_and_reindex(tmp_path):
    from vector_store import ChromaVectorStore

    store = ChromaVectorStore(path=str(tmp_path / "chroma"), collection_name="kb_test")
    store.rebuild(DEFAULT_ENTRIES)
    engine = NLPEngine(store=store)
    engine.set_knowledge_base(DEFAULT_ENTRIES)

    result = engine.retrieve("¿A qué hora abren la cafetería?")
    assert result.kb_id == "horarios"
    assert result.method == "semantic"
    assert result.confidence >= 0.70  # pregunta idéntica a un ejemplo: d ≈ 0

    store.delete_entry("horarios")
    hits = store.query(normalize_text("a que hora abren la cafeteria"))
    assert "horarios" not in [kb_id for kb_id, _ in hits]

    store.upsert_entry(DEFAULT_ENTRIES[0])
    assert store.query(normalize_text("a que hora abren la cafeteria"))[0][0] == "horarios"
