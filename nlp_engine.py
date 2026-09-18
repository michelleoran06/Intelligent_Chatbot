import re
import unicodedata
from vector_store import collection

class NLPEngine:
    def __init__(self, confidence_threshold: float = 0.50):
        self.confidence_threshold = confidence_threshold

    def preprocess(self, text: str) -> str:
        text = text.lower().strip()
        # Remove accents
        text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
        # Remove non-alphanumeric characters except spaces
        text = re.sub(r"[^\w\s]", "", text)
        
        # Remove common Spanish stopwords that confuse the English embedding model
        stopwords = {"quiero", "saber", "los", "las", "el", "la", "un", "una", "unos", "unas", 
                     "de", "en", "para", "por", "con", "sin", "a", "y", "o", "que", "es", "son", 
                     "como", "cual", "cuales", "donde", "cuando", "quien", "bueno", "me", "te", 
                     "se", "le", "les", "nos", "mi", "tu", "su", "mis", "tus", "sus", "al", "del",
                     "hola", "oye", "disculpa", "info", "informacion", "sobre"}
        
        words = text.split()
        clean_words = [w for w in words if w not in stopwords]
        
        # If the user only typed stopwords (rare, but possible), fallback to original text to avoid empty query
        if not clean_words:
            return text
            
        return " ".join(clean_words)

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