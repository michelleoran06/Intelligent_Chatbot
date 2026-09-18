import re
from vector_store import collection

class NLPEngine:
    def __init__(self, confidence_threshold: float = 0.70):
        self.confidence_threshold = confidence_threshold

    def preprocess(self, text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^\w\s]", "", text)
        return text

    def retrieve_and_score(self, query: str):
        cleaned_query = self.preprocess(query)
        
        results = collection.query(
            query_texts=[cleaned_query],
            n_results=1
        )

        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        if not metadatas or not distances:
            return "", 0.0

        distance = distances[0]
        
        confidence_score = max(0.0, 1.0 - (distance / 2.5))
        
        respuesta = metadatas[0].get("respuesta", "") if metadatas else ""
        
        return respuesta, round(confidence_score, 4)