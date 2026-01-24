# vector_search_demo.py
"""
Day 3: Vector Database Demo
Understanding semantic search with Chroma
"""

from sentence_transformers import SentenceTransformer
import chromadb

# ========== STEP 1: Prepare Documents ==========
documents = [
    "Nepal has many rural villages with limited healthcare access.",
    "Vector databases store embeddings for semantic search.",
    "AI can help improve rural healthcare systems in remote areas.",
    "Chroma is a simple vector database for AI applications.",
    "SEE exam is important for Nepali students.",
    "Career guidance is crucial for students after grade 10.",
    "Dashain is the biggest festival in Nepal.",
    "IOE entrance exam requires good preparation in mathematics."
]

print("📚 Documents loaded:", len(documents))

# ========== STEP 2: Generate Embeddings ==========
print("\n🔄 Generating embeddings...")
model = SentenceTransformer("all-MiniLM-L6-v2")
embeddings = model.encode(documents)

print(f"✅ Generated {len(embeddings)} embeddings")
print(f"📊 Each embedding has {len(embeddings[0])} dimensions")

# ========== STEP 3: Store in Chroma ==========
print("\n💾 Storing in Chroma...")
client = chromadb.Client()
collection = client.create_collection(name="kancha_demo")

collection.add(
    documents=documents,
    embeddings=embeddings.tolist(),
    ids=[f"doc_{i}" for i in range(len(documents))]
)

print("✅ Stored in vector database")

# ========== STEP 4: Semantic Search ==========
print("\n" + "="*60)
print("🔍 SEMANTIC SEARCH DEMO")
print("="*60)

# Test queries
test_queries = [
    "How can AI help healthcare in villages?",
    "What should students do after SEE?",
    "Tell me about festivals in Nepal"
]

for query in test_queries:
    print(f"\n❓ Query: '{query}'")
    print("-" * 60)
    
    # Generate query embedding
    query_embedding = model.encode([query])
    
    # Search
    results = collection.query(
        query_embeddings=query_embedding.tolist(),
        n_results=2
    )
    
    # Display results
    print("📌 Most relevant documents:")
    for i, doc in enumerate(results["documents"][0], 1):
        print(f"  {i}. {doc}")

print("\n" + "="*60)
print("✅ Day 3 Complete: Vector Search Working!")
print("="*60)