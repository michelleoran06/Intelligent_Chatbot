from vector_store import collection

class BotStrategy:
    def generate_response(self, query, context):
        return {
            "message": context,
            "routed_to": "bot",
            "status": "resolved"
        }

class FallbackStrategy:
    def generate_response(self, query, context):
        return {
            "message": "Tu consulta requiere asistencia personalizada. Te estamos transfiriendo con un operador.",
            "routed_to": "human",
            "status": "pending"
        }

class NLPEngine:
    def _init_(self):
        self.confidence_threshold = 0.65

    def retrieve_and_score(self, query):
        try:
            results = collection.query(
                query_texts=[query],
                n_results=1
            )
            
            if results['distances'] and results['distances'][0]:
                distance = results['distances'][0][0]
                # Invertimos la distancia para que funcione como tu "confidence_score"
                confidence = 1.0 / (1.0 + distance)
                context = results['metadatas'][0][0]['respuesta']
                return context, float(confidence)
            else:
                return "", 0.0
        except Exception:
            return "", 0.0

nlp_engine = NLPEngine()
bot_strategy = BotStrategy()
fallback_strategy = FallbackStrategy()
