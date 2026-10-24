"""Motor de IA del chatbot (AI / Prediction Layer, Secciones 8 y 16.1).

Flujo:
1. Normalización del texto (input_validation.normalize_text).
2. Recuperación semántica en ChromaDB: S = 1 - d / divisor, con d = distancia L2 al cuadrado
   de la entrada más cercana. Si S >= umbral, se devuelve la respuesta de esa entrada.
3. Respaldo léxico: si la búsqueda semántica no alcanza el umbral, se buscan palabras clave.
   Se exigen al menos 2 coincidencias con una sola entrada (sin empates) para evitar falsos
   positivos como "la API de pagos no me responde". La confianza asignada es fija
   (KEYWORD_CONFIDENCE) y se registra con method="keyword" para poder auditarla.
4. Rechazo explícito (opcional): si la entrada más cercana es el grupo de ejemplos de rechazo
   (knowledge_base.REJECTION_ID), la confianza es 0, se omite el respaldo léxico y se escala
   (method="rejected").
5. Si nada alcanza el umbral, el resultado se devuelve con confianza baja y main.py escala.

Los errores del vector store NO se atrapan aquí: se propagan para que la API registre el
error y responda HTTP 500 (Sección 9), y nunca quedan guardados en la caché.
"""
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, FrozenSet, Iterable, List, Optional, Tuple

from input_validation import normalize_text
from knowledge_base import REJECTION_ID

try:
    from rapidfuzz import fuzz as _fuzz

    def _similarity(a: str, b: str) -> float:
        return float(_fuzz.ratio(a, b))
except ImportError:  # respaldo para entornos sin rapidfuzz
    from difflib import SequenceMatcher

    def _similarity(a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio() * 100.0

_FUZZY_MIN_LENGTH = 5
_FUZZY_MIN_RATIO = 88.0


def simple_stem(token: str) -> str:
    """Quita una 's' final para unificar singular y plural ("pagos" -> "pago")."""
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]
    return token


def keyword_tokens(normalized_text: str) -> FrozenSet[str]:
    return frozenset(simple_stem(t) for t in normalized_text.split() if len(t) >= 3)


@dataclass(frozen=True)
class RetrievalResult:
    answer: str
    confidence: float
    kb_id: Optional[str]
    method: str  # "semantic" | "keyword" | "rejected" | "none"
    distance: Optional[float] = None
    candidates: Tuple[str, ...] = ()  # ranking semántico (para hit rate @1 / @3)


class NLPEngine:
    def __init__(
        self,
        store,
        confidence_threshold: float = 0.70,
        divisor: float = 2.5,
        keyword_confidence: float = 0.75,
        min_keyword_matches: int = 2,
        n_results: int = 10,
        cache_size: int = 256,
    ):
        if divisor <= 0:
            raise ValueError("El divisor de confianza debe ser mayor que cero.")
        self.store = store
        self.confidence_threshold = confidence_threshold
        self.divisor = divisor
        self.keyword_confidence = keyword_confidence
        self.min_keyword_matches = min_keyword_matches
        self.n_results = n_results
        self.cache_size = max(0, cache_size)
        self._entries: Dict[str, dict] = {}
        self._keywords: Dict[str, List[Tuple[str, ...]]] = {}
        self._cache: "OrderedDict[str, RetrievalResult]" = OrderedDict()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ base de conocimiento
    def set_knowledge_base(self, entries: Iterable[dict]) -> None:
        """Carga (o recarga) las entradas y limpia la caché para no servir respuestas viejas."""
        new_entries: Dict[str, dict] = {}
        new_keywords: Dict[str, List[Tuple[str, ...]]] = {}
        for entry in entries:
            new_entries[entry["id"]] = entry
            parsed = []
            for keyword in entry.get("keywords", []):
                parts = tuple(simple_stem(p) for p in normalize_text(keyword).split())
                if parts:
                    parsed.append(parts)
            new_keywords[entry["id"]] = parsed
        with self._lock:
            self._entries = new_entries
            self._keywords = new_keywords
            self._cache.clear()

    @property
    def entries(self) -> Dict[str, dict]:
        with self._lock:
            return dict(self._entries)

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()

    # ------------------------------------------------------------------ puntuación
    def score_from_distance(self, distance: float) -> float:
        score = 1.0 - (float(distance) / self.divisor)
        return round(min(1.0, max(0.0, score)), 4)

    @staticmethod
    def _keyword_in(keyword: Tuple[str, ...], tokens: FrozenSet[str]) -> bool:
        if len(keyword) > 1:  # frase: todas sus palabras deben aparecer
            return all(part in tokens for part in keyword)
        word = keyword[0]
        if word in tokens:
            return True
        if len(word) < _FUZZY_MIN_LENGTH:
            return False
        return any(len(t) >= _FUZZY_MIN_LENGTH and _similarity(t, word) >= _FUZZY_MIN_RATIO for t in tokens)

    def keyword_match(self, normalized_query: str) -> Tuple[Optional[str], int]:
        """Devuelve (kb_id, coincidencias) del ganador único, o (None, mejor_conteo)."""
        tokens = keyword_tokens(normalized_query)
        if not tokens:
            return None, 0
        with self._lock:
            keywords = self._keywords
        scores = {}
        for kb_id, kws in keywords.items():
            count = sum(1 for kw in kws if self._keyword_in(kw, tokens))
            if count:
                scores[kb_id] = count
        if not scores:
            return None, 0
        best = max(scores.values())
        winners = [kb_id for kb_id, count in scores.items() if count == best]
        if best < self.min_keyword_matches or len(winners) != 1:
            return None, best
        return winners[0], best

    # ------------------------------------------------------------------ recuperación
    def semantic_search(self, normalized_query: str) -> List[Tuple[str, float]]:
        if not normalized_query:
            return []
        with self._lock:
            known = set(self._entries)
        hits = self.store.query(normalized_query, self.n_results)
        return [(kb_id, float(distance)) for kb_id, distance in hits if kb_id in known or kb_id == REJECTION_ID]

    def retrieve(self, query: str) -> RetrievalResult:
        key = normalize_text(query)
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                self._cache.move_to_end(key)
                return cached
        result = self._compute(key)  # si falla, la excepción sube y no se guarda en caché
        if self.cache_size:
            with self._lock:
                self._cache[key] = result
                self._cache.move_to_end(key)
                while len(self._cache) > self.cache_size:
                    self._cache.popitem(last=False)
        return result

    def _compute(self, key: str) -> RetrievalResult:
        with self._lock:
            entries = self._entries
        all_hits = self.semantic_search(key)
        hits = [hit for hit in all_hits if hit[0] != REJECTION_ID]
        candidates = tuple(kb_id for kb_id, _ in hits)
        if all_hits and all_hits[0][0] == REJECTION_ID:
            return RetrievalResult("", 0.0, None, "rejected", round(all_hits[0][1], 4), candidates)
        if hits:
            kb_id, distance = hits[0]
            semantic = RetrievalResult(
                answer=entries[kb_id]["answer"],
                confidence=self.score_from_distance(distance),
                kb_id=kb_id,
                method="semantic",
                distance=round(distance, 4),
                candidates=candidates,
            )
        else:
            semantic = RetrievalResult("", 0.0, None, "none", None, candidates)

        if semantic.confidence >= self.confidence_threshold:
            return semantic

        keyword_id, _ = self.keyword_match(key)
        if keyword_id is not None and keyword_id in entries:
            return RetrievalResult(
                answer=entries[keyword_id]["answer"],
                confidence=round(self.keyword_confidence, 4),
                kb_id=keyword_id,
                method="keyword",
                distance=semantic.distance if semantic.kb_id == keyword_id else None,
                candidates=candidates,
            )
        return semantic
