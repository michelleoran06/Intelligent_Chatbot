"""Pruebas de las optimizaciones de desempeño (Fase 3). No necesitan ChromaDB."""
import threading
import time

from vector_store import ChromaVectorStore


class SlowFakeCollection:
    """Simula una colección de ChromaDB cuya consulta tarda y registra la concurrencia máxima."""

    def __init__(self):
        self.active = 0
        self.max_active = 0
        self._lock = threading.Lock()

    def count(self):
        return 5

    def query(self, query_texts, n_results, include):
        with self._lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        time.sleep(0.05)
        with self._lock:
            self.active -= 1
        return {"metadatas": [[{"kb_id": "horarios"}]], "distances": [[0.1]]}


def run_concurrently(store, threads=8):
    workers = [threading.Thread(target=store.query, args=(f"pregunta {i}",)) for i in range(threads)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()


def test_embedding_concurrency_limit_is_respected():
    store = ChromaVectorStore(path="no_se_usa", embedding_concurrency=2, rejection_examples=[])
    store._collection = SlowFakeCollection()
    run_concurrently(store)
    assert store._collection.max_active <= 2


def test_no_limit_allows_full_concurrency():
    store = ChromaVectorStore(path="no_se_usa", embedding_concurrency=0, rejection_examples=[])
    store._collection = SlowFakeCollection()
    run_concurrently(store)
    assert store._collection.max_active > 2


def test_query_result_is_unchanged_by_the_limit():
    store = ChromaVectorStore(path="no_se_usa", embedding_concurrency=1, rejection_examples=[])
    store._collection = SlowFakeCollection()
    assert store.query("a que hora abren") == [("horarios", 0.1)]
