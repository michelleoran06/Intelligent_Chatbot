import os
from vector_store import collection
import google.generativeai as genai

class BotStrategy:
    def _init_(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
        else:
            self.model = None

    def generate_response(self, query, context):
        if self.model:
            prompt = f"Eres el asistente de la cafetería de la Facultad de Ingeniería. Responde la duda basándote solo en este contexto:\n\n{context}\n\nPregunta: {query}"
            try:
                response = self.model.generate_content(prompt)
                message = response.text
            except Exception:
                message = context
        else:
            message = context

        return {
            "message": message,
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
