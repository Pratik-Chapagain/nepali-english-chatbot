# understand_embeddings.py
import json
import numpy as np

# Load your embeddings
with open("faq_embeddings.json", "r", encoding="utf-8") as f:
    faq_data = json.load(f)

print("=== Let's UNDERSTAND Embeddings ===\n")

# Pick ONE FAQ to examine
faq_question = "what is kancha ai"
data = faq_data[faq_question]
embedding = data["embedding"]

print(f"1. FAQ Question: '{faq_question}'")
print(f"2. Embedding length: {len(embedding)} numbers")
print(f"3. First 5 numbers: {embedding[:5]}")
print(f"4. Are they all similar?")
print(f"   Min: {min(embedding):.6f}")
print(f"   Max: {max(embedding):.6f}")
print(f"   Average: {np.mean(embedding):.6f}")

print("\n5. Now let's compare TWO questions:")

# Compare with another FAQ
faq2_question = "who made you"
data2 = faq_data[faq2_question]
embedding2 = data2["embedding"]

# Manual similarity calculation
similarity = np.dot(embedding, embedding2) / (
    np.linalg.norm(embedding) * np.linalg.norm(embedding2)
)

print(f"\n   '{faq_question}' vs '{faq2_question}'")
print(f"   Similarity: {similarity:.4f} ({similarity*100:.1f}%)")
print(f"   Interpretation: {'Related' if similarity > 0.5 else 'Not related'}")

# Compare with a similar question
print("\n6. Now let's test SIMILAR meaning:")
similar_query = "tell me about kancha ai"

# We need to create embedding for this new query
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
query_embedding = model.encode(similar_query)

# Compare
similarity2 = np.dot(embedding, query_embedding) / (
    np.linalg.norm(embedding) * np.linalg.norm(query_embedding)
)

print(f"\n   FAQ: '{faq_question}'")
print(f"   Query: '{similar_query}'")
print(f"   Similarity: {similarity2:.4f} ({similarity2*100:.1f}%)")
print(f"   This shows: Different words, SAME meaning!")