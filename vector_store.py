"""Vector DB del sistema (Polyglot Persistence, Sección 4.4).

ChromaDB con cliente persistente. Cada pregunta de ejemplo y el texto de la respuesta (sin precios)
se indexan como documentos separados con metadata {"kb_id": ...}; la consulta devuelve la distancia
mínima por entrada.

Modelo de embeddings (EMBEDDING_MODEL):
- "default": all-MiniLM-L6-v2 en ONNX, incluido en chromadb (vectores unitarios, distancia L2^2).
- otro valor: modelo de sentence-transformers con normalize_embeddings=True. Así los vectores
  también son unitarios y la distancia sigue en el rango 0-4, de modo que la fórmula
  S = 1 - d / divisor conserva su significado (Sección 8).

Ejemplos de rechazo: si están activos, se indexan con kb_id = REJECTION_ID (ver nlp_engine.py).

chromadb se importa de forma diferida para que el resto del sistema y las pruebas unitarias no
dependan de él.
"""
import logging
import os
import re
import threading
from typing import Iterable, List, Optional, Tuple

import config
from input_validation import normalize_text
from knowledge_base import REJECTION_EXAMPLES, REJECTION_ID

logger = logging.getLogger("VectorStore")

_PRICE = re.compile(r"\$\s?\d+")


def documents_for_entry(entry: dict) -> Tuple[List[str], List[str], List[dict]]:
    ids, documents, metadatas = [], [], []
    for index, question in enumerate(entry.get("questions", [])):
        text = normalize_text(question)
        if text:
            ids.append(f"{entry['id']}::q{index}")
            documents.append(text)
            metadatas.append({"kb_id": entry["id"]})
    answer_text = normalize_text(_PRICE.sub(" ", entry.get("answer", "")))
    if answer_text:
        ids.append(f"{entry['id']}::answer")
        documents.append(answer_text)
        metadatas.append({"kb_id": entry["id"]})
    return ids, documents, metadatas


def documents_for_rejection(examples: Iterable[str]) -> Tuple[List[str], List[str], List[dict]]:
    ids, documents, metadatas = [], [], []
    for index, example in enumerate(examples):
        text = normalize_text(example)
        if text:
            ids.append(f"{REJECTION_ID}::{index}")
            documents.append(text)
            metadatas.append({"kb_id": REJECTION_ID})
    return ids, documents, metadatas


def add_in_batches(collection, ids, documents, metadatas, batch_size: int) -> None:
    """Agrega documentos por lotes: el embedding de cada lote se calcula por separado, lo que
    limita la memoria pico (calcular 141 documentos juntos excedía los 512 MB de Render)."""
    size = max(1, int(batch_size))
    for start in range(0, len(ids), size):
        end = start + size
        collection.add(ids=ids[start:end], documents=documents[start:end], metadatas=metadatas[start:end])


def make_embedding_function(model_name: str):
    """None = función por defecto de chromadb; otro nombre = sentence-transformers normalizado."""
    if not model_name or model_name == "default":
        return None
    try:
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise RuntimeError(
            f"EMBEDDING_MODEL='{model_name}' requiere sentence-transformers "
            "(pip install -r requirements-experiment.txt)."
        ) from exc
    return SentenceTransformerEmbeddingFunction(model_name=model_name, normalize_embeddings=True)


class ChromaVectorStore:
    def __init__(self, path: Optional[str] = None, collection_name: Optional[str] = None,
                 persistent: bool = True, embedding_model: Optional[str] = None,
                 rejection_examples: Optional[Iterable[str]] = None,
                 embedding_concurrency: Optional[int] = None):
        self.path = path or config.CHROMA_PATH
        self.collection_name = collection_name or config.CHROMA_COLLECTION
        self.persistent = persistent
        self.embedding_model = embedding_model or config.EMBEDDING_MODEL
        if rejection_examples is None:
            rejection_examples = REJECTION_EXAMPLES if config.USE_REJECTION_EXAMPLES else []
        self.rejection_examples = list(rejection_examples)
        self._embedding_function = None
        self._client = None
        self._collection = None
        self._write_lock = threading.RLock()
        # Fase 3: limita cuántas consultas calculan su embedding a la vez. Sin límite, decenas de
        # hilos compiten por la CPU y todas las respuestas se vuelven lentas al mismo tiempo.
        limit = config.EMBEDDING_CONCURRENCY if embedding_concurrency is None else embedding_concurrency
        self.embedding_concurrency = max(0, int(limit))
        self._query_slots = threading.BoundedSemaphore(self.embedding_concurrency) if self.embedding_concurrency else None

    def _get_client(self):
        if self._client is None:
            import chromadb

            if self.persistent:
                os.makedirs(self.path, exist_ok=True)
                self._client = chromadb.PersistentClient(path=self.path)
            else:
                self._client = chromadb.EphemeralClient()
        return self._client

    def _collection_kwargs(self) -> dict:
        if self._embedding_function is None:
            self._embedding_function = make_embedding_function(self.embedding_model)
        kwargs = {"name": self.collection_name}
        if self._embedding_function is not None:
            kwargs["embedding_function"] = self._embedding_function
        return kwargs

    def _get_collection(self):
        if self._collection is None:
            self._collection = self._get_client().get_or_create_collection(**self._collection_kwargs())
        return self._collection

    def rebuild(self, entries: Iterable[dict]) -> int:
        """Reconstruye el índice completo a partir de la SQL DB (fuente de verdad)."""
        with self._write_lock:
            client = self._get_client()
            try:
                client.delete_collection(self.collection_name)
            except Exception:  # la colección todavía no existía
                pass
            self._collection = client.get_or_create_collection(**self._collection_kwargs())
            ids, documents, metadatas = documents_for_rejection(self.rejection_examples)
            for entry in entries:
                entry_ids, entry_docs, entry_meta = documents_for_entry(entry)
                ids.extend(entry_ids)
                documents.extend(entry_docs)
                metadatas.extend(entry_meta)
            add_in_batches(self._collection, ids, documents, metadatas, config.EMBEDDING_BATCH_SIZE)
            logger.info("Índice vectorial reconstruido: %d documentos (modelo=%s, rechazo=%d ejemplos).",
                        len(ids), self.embedding_model, len(self.rejection_examples))
            return len(ids)

    def upsert_entry(self, entry: dict) -> None:
        with self._write_lock:
            collection = self._get_collection()
            collection.delete(where={"kb_id": entry["id"]})
            ids, documents, metadatas = documents_for_entry(entry)
            add_in_batches(collection, ids, documents, metadatas, config.EMBEDDING_BATCH_SIZE)

    def delete_entry(self, kb_id: str) -> None:
        with self._write_lock:
            self._get_collection().delete(where={"kb_id": kb_id})

    @staticmethod
    def _run_query(collection, text: str, n_results: int):
        return collection.query(query_texts=[text], n_results=n_results, include=["metadatas", "distances"])

    def count(self) -> int:
        return self._get_collection().count()

    def query(self, text: str, n_results: int = 20) -> List[Tuple[str, float]]:
        """Devuelve [(kb_id, distancia_mínima)] ordenado de la más cercana a la más lejana."""
        if not text:
            return []
        collection = self._get_collection()
        total = collection.count()
        if total == 0:
            return []
        if self._query_slots is None:
            result = self._run_query(collection, text, min(n_results, total))
        else:
            with self._query_slots:
                result = self._run_query(collection, text, min(n_results, total))
        metadatas = (result.get("metadatas") or [[]])[0] or []
        distances = (result.get("distances") or [[]])[0] or []
        best = {}
        for metadata, distance in zip(metadatas, distances):
            kb_id = (metadata or {}).get("kb_id")
            if kb_id is None:
                continue
            if kb_id not in best or distance < best[kb_id]:
                best[kb_id] = float(distance)
        return sorted(best.items(), key=lambda item: item[1])


_store = None
_store_lock = threading.Lock()


def get_store():
    """Devuelve el vector store compartido (se crea la primera vez)."""
    global _store
    with _store_lock:
        if _store is None:
            _store = ChromaVectorStore()
        return _store


def set_store(store) -> None:
    """Permite reemplazar el vector store (por ejemplo, por uno falso en las pruebas)."""
    global _store
    with _store_lock:
        _store = store
