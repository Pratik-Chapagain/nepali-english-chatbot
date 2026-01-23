# faq_search.py
# This connects your embeddings to your chatbot

from sentence_transformers import SentenceTransformer
import json
import numpy as np

class FAQSearcher:
    """Simple FAQ semantic search for your chatbot"""
    
    def __init__(self, embeddings_file="faq_embeddings.json"):
        """Initialize once when chatbot starts"""
        print("🔍 Loading FAQ search system...")
        
        # Load the model (same one you used to create embeddings)
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Load your FAQ embeddings
        try:
            with open(embeddings_file, "r", encoding="utf-8") as f:
                self.faq_data = json.load(f)
            print(f"✅ Loaded {len(self.faq_data)} FAQs")
        except FileNotFoundError:
            print(f"❌ {embeddings_file} not found!")
            self.faq_data = {}
    
    def search(self, user_query: str, threshold: float = 0.70):
        """
        Search for similar FAQ
        
        Args:
            user_query: What the user asked
            threshold: Minimum similarity (0.70 = 70% match)
        
        Returns:
            dict with 'found', 'answer', 'similarity', 'question'
        """
        if not self.faq_data:
            return {'found': False, 'similarity': 0}
        
        # Get embedding for user's question
        user_embedding = self.model.encode(user_query)
        
        # Find best matching FAQ
        best_match = None
        best_score = 0
        best_question = None
        
        for faq_question, data in self.faq_data.items():
            faq_embedding = np.array(data["embedding"])
            
            # Calculate cosine similarity
            similarity = np.dot(user_embedding, faq_embedding) / (
                np.linalg.norm(user_embedding) * np.linalg.norm(faq_embedding)
            )
            
            if similarity > best_score:
                best_score = similarity
                best_match = data
                best_question = faq_question
        
        # Return result
        if best_score >= threshold:
            return {
                'found': True,
                'answer': best_match['answers'],
                'similarity': best_score,
                'question': best_question
            }
        else:
            return {
                'found': False,
                'similarity': best_score,
                'question': best_question  # Show what it almost matched
            }
    
    def get_answer(self, user_query: str, language: str = 'en', threshold: float = 0.70):
        """
        Simple helper - returns answer text or None
        
        Args:
            user_query: User's question
            language: 'en', 'ne', or 'np'
            threshold: Similarity threshold
        
        Returns:
            Answer text or None
        """
        result = self.search(user_query, threshold)
        
        if result['found']:
            answers = result['answer']
            
            # Get answer in requested language (fallback to English)
            answer = answers.get(language, answers.get('en', 'No answer available'))
            
            # Add debug info (optional - remove in production)
            similarity_percent = result['similarity'] * 100
            debug = f"\n\n_[FAQ Match: {similarity_percent:.1f}% - '{result['question']}']_"
            
            return answer + debug
        
        return None


# Quick test function
if __name__ == "__main__":
    """Test the searcher"""
    searcher = FAQSearcher()
    
    test_queries = [
        "tell me about kancha",
        "who created you",
        "what can you help with",
        "ioe entrance information"
    ]
    
    print("\n" + "="*60)
    print("TESTING FAQ SEARCH")
    print("="*60)
    
    for query in test_queries:
        print(f"\n🔍 Query: '{query}'")
        result = searcher.search(query)
        
        if result['found']:
            print(f"✅ MATCH!")
            print(f"   Similarity: {result['similarity']*100:.1f}%")
            print(f"   FAQ: {result['question']}")
            print(f"   Answer: {result['answer']['en'][:50]}...")
        else:
            print(f"❌ No match (best: {result['similarity']*100:.1f}%)")