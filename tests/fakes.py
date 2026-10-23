"""Dobles de prueba: vector store determinista que no necesita ChromaDB ni el modelo."""
from input_validation import normalize_text
from knowledge_base import REJECTION_ID


class FakeVectorStore:
    """Similitud de Jaccard entre palabras; distancia = 2 * (1 - similitud).

    Una pregunta idéntica a un ejemplo da d = 0 (S = 1.0) y un texto sin palabras en común
    da d = 2 (S = 0.2), igual que el rango de la distancia real (Sección 8).
    """

    def __init__(self, rejection_examples=None):
        self.rejection_examples = list(rejection_examples or [])
        self.documents = {}
        self.fail = False
        self.calls = 0

    def rebuild(self, entries):
        self.documents = {}
        if self.rejection_examples:
            self.documents[REJECTION_ID] = [set(normalize_text(q).split()) for q in self.rejection_examples]
        for entry in entries:
            self.upsert_entry(entry)
        return self.count()

    def upsert_entry(self, entry):
        self.documents[entry["id"]] = [set(normalize_text(q).split()) for q in entry["questions"]]

    def delete_entry(self, kb_id):
        self.documents.pop(kb_id, None)

    def count(self):
        return sum(len(docs) for docs in self.documents.values())

    def query(self, text, n_results=10):
        self.calls += 1
        if self.fail:
            raise RuntimeError("Fallo simulado del vector store")
        tokens = set(text.split())
        hits = []
        for kb_id, docs in self.documents.items():
            best = max((len(tokens & d) / len(tokens | d) for d in docs if tokens | d), default=0.0)
            hits.append((kb_id, round(2.0 * (1.0 - best), 4)))
        hits.sort(key=lambda item: item[1])
        return hits[:n_results]
