import re
import unicodedata
from vector_store import collection

class NLPEngine:
    def __init__(self, confidence_threshold: float = 0.65):
        self.confidence_threshold = confidence_threshold
        
        # Hardcoded intents for Spanish to bypass English model limitations
        self.intents = {
            "horarios": {
                "keywords": ["hora", "horario", "abren", "cierran", "temprano", "tarde", "dias", "sabado"],
                "respuesta": "La cafetería está abierta de lunes a sábado de 7:00 AM a 5:00 PM. (Abrimos puertas 6:30 AM, pero el servicio empieza a las 7:00 AM)."
            },
            "pagos": {
                "keywords": ["pago", "pagar", "tarjeta", "efectivo", "transferencia", "terminal", "cobran"],
                "respuesta": "Aceptamos pagos en efectivo, tarjetas de débito/crédito y transferencias."
            },
            "ubicacion": {
                "keywords": ["donde", "ubicacion", "llegar", "edificio", "lugar", "encuentran", "estan"],
                "respuesta": "Estamos ubicados en la planta baja del edificio principal de la Facultad de Ingeniería."
            },
            "menu": {
                "keywords": ["menu", "comida", "comer", "hambre", "venden", "alimentos", "desayuno", "paquete", "pizza", "chilaquiles", "hamburguesa", "bebida", "agua", "postre", "dulce", "precio", "cuesta"],
                "respuesta": "Tenemos una gran variedad:\n- **Desayunos:** Huevos, chilaquiles, omelettes ($55)\n- **Comidas:** Paquetes con milanesa, pechuga, arrachera ($60-$80)\n- **Menú del día:** $80 (Sopa, arroz, guisado, gelatina)\n- **Antojitos:** Quesadillas, tacos, burritos\n- **Pizzas, postres y bebidas.**\n\n¿Buscas algo en específico?"
            }
        }

    def preprocess(self, text: str) -> str:
        text = text.lower().strip()
        text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
        text = re.sub(r"[^\w\s]", "", text)
        return text

    def retrieve_and_score(self, query: str):
        cleaned_query = self.preprocess(query)
        words = set(cleaned_query.split())
        
        # 1. Intent Keyword Matching (Fast & Accurate for Spanish)
        best_intent_match = None
        best_match_count = 0
        
        for intent, data in self.intents.items():
            match_count = sum(1 for kw in data["keywords"] if kw in words or any(kw in w for w in words))
            if match_count > best_match_count:
                best_match_count = match_count
                best_intent_match = data["respuesta"]
                
        if best_intent_match and best_match_count >= 1:
            # High confidence if we hit keywords
            return best_intent_match, 0.85

        # 2. Fallback to ChromaDB (Vector Search)
        try:
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
        except Exception:
            return "", 0.0