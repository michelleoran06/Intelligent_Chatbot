import re
from vector_store import collection

class NLPEngine:
    def __init__(self, confidence_threshold: float = 0.70):
        self.confidence_threshold = confidence_threshold

    def preprocess(self, text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^\w\s]", "", text)
        return text

    def retrieve_and_score(self, query):
        query_lower = query.lower()
    
        intent_boosts = {
            "horario apertura cierre horas": ["horario", "hora", "abren", "cierran", "servicio"],
            "ubicacion edificio planta llegar": ["ubicacion", "donde", "llegar", "edificio", "lugar", "encuentran"],
            "metodo pago tarjeta efectivo": ["pago", "pagar", "tarjeta", "efectivo", "transferencia", "aceptan"],
            "menu comida desayuno platillos": ["menu", "comer", "desayuno", "comida", "venden", "chilaquiles"]
        }

        boosted_query = query_lower
        for extra_context, words in intent_boosts.items():
            if any(w in query_lower for w in words):
                boosted_query = f"{query_lower} {extra_context}"
                break

        context, confidence = self.vector_store.search(boosted_query)
    
        return context, confidence
    
