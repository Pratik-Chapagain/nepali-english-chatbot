# test_similarity.py
from sentence_transformers import SentenceTransformer
import json
import numpy as np

# Load your embeddings
print("Loading FAQ embeddings...")
with open("faq_embeddings.json", "r", encoding="utf-8") as f:
    faq_data = json.load(f)

print(f"✓ Loaded {len(faq_data)} FAQs\n")

# Load the model
print("Loading model...")
model = SentenceTransformer('all-MiniLM-L6-v2')
print("✓ Model loaded!\n")

# Function to find similar FAQs
def find_similar_faq(user_question, top_k=3):
    """Find the most similar FAQ to user's question"""
    
    # Get embedding for user's question
    user_embedding = model.encode(user_question)
    
    # Calculate similarity with each FAQ
    similarities = []
    for faq_question, data in faq_data.items():
        faq_embedding = np.array(data["embedding"])
        
        # Cosine similarity (math to compare embeddings)
        similarity = np.dot(user_embedding, faq_embedding) / (
            np.linalg.norm(user_embedding) * np.linalg.norm(faq_embedding)
        )
        
        similarities.append({
            "question": faq_question,
            "similarity": similarity,
            "answers": data["answers"]
        })
    
    # Sort by similarity (highest first)
    similarities.sort(key=lambda x: x["similarity"], reverse=True)
    
    return similarities[:top_k]

# Test with different questions
test_queries = [
    "what is kancha ai",           # Exact match
    "tell me about kancha",        # Similar meaning
    "who created you",             # Different words, same meaning
    "what can kancha do",          # Partial match
    "ioe exam information",        # Related topic
]

print("="*60)
print("TESTING SIMILARITY SEARCH")
print("="*60)

for query in test_queries:
    print(f"\n🔍 User asks: '{query}'")
    print("-" * 60)
    
    results = find_similar_faq(query)
    
    for i, result in enumerate(results, 1):
        similarity_percent = result["similarity"] * 100
        print(f"{i}. {result['question']}")
        print(f"   Similarity: {similarity_percent:.1f}%")
        
        # Show answer if similarity is high enough
        if similarity_percent > 70:
            print(f"   ✓ MATCH! Answer: {result['answers']['en'][:50]}...")
        print()