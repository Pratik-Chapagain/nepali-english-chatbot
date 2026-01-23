
import json
import numpy as np

class DummyTransformer:
    def __init__(self, model_name):
        pass
    def encode(self, text):
        return np.random.rand(384)  # Random embeddings

class FAQSearcher:
    def __init__(self, embeddings_file="faq_embeddings.json"):
        self.model = DummyTransformer('dummy')
        self.faq_data = {}
        try:
            with open(embeddings_file, "r") as f:
                self.faq_data = json.load(f)
        except:
            pass
    
    def get_answer(self, user_query, language='en', threshold=0.7, debug=False):
        if not self.faq_data:
            return None
        
        # Simple text matching as fallback
        query_lower = user_query.lower()
        for question, data in self.faq_data.items():
            if any(word in query_lower for word in question.split()):
                return data['answers'].get(language, data['answers'].get('en', ''))
        return None