from memory.embeddings import SimpleVectorEmbeddingModel, _cosine_similarity
from memory.json_store import JSONMemoryStore


def test_simple_vector_embedding_model():
    embedder = SimpleVectorEmbeddingModel()
    v1 = embedder.embed_text("python software development")
    v2 = embedder.embed_text("python software programming")
    v3 = embedder.embed_text("cooking recipe pasta baking")

    assert len(v1) == 128
    sim_1_2 = _cosine_similarity(v1, v2)
    sim_1_3 = _cosine_similarity(v1, v3)

    assert sim_1_2 > sim_1_3
    assert sim_1_2 > 0.3


def test_hybrid_semantic_search(tmp_path):
    store_path = tmp_path / "memories.json"
    store = JSONMemoryStore(store_path)

    store.add("User loves machine learning and neural networks")
    store.add("User lives in San Francisco, California")
    store.add("User works on web development with FastAPI")

    results = store.search("deep learning neural nets", limit=2)
    assert len(results) >= 1
    assert "machine learning" in results[0].entry.content
