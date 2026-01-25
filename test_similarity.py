# test_similarity.py
"""
Understanding how embeddings capture meaning
"""

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

model = SentenceTransformer("all-MiniLM-L6-v2")

# Test sentences
sentences = [
    "The student is studying for exams.",
    "A pupil is preparing for tests.",
    "The cat is sleeping on the couch.",
]

embeddings = model.encode(sentences)

print("🔢 Similarity Scores (0-1, higher = more similar):\n")

for i in range(len(sentences)):
    for j in range(i+1, len(sentences)):
        similarity = cosine_similarity([embeddings[i]], [embeddings[j]])[0][0]
        print(f"'{sentences[i][:30]}...'")
        print(f"  vs")
        print(f"'{sentences[j][:30]}...'")
        print(f"  → Similarity: {similarity:.4f}\n")