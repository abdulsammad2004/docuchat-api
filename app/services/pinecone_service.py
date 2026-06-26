import os
from pinecone import Pinecone
from openai import OpenAI

# Initialize clients (lazy — errors only surface on first call, not import)
_pc = None
_index = None
_openai = None

def _get_index():
    global _pc, _index
    if _index is None:
        _pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
        _index = _pc.Index(os.environ["PINECONE_INDEX_NAME"])
    return _index

def _get_openai():
    global _openai
    if _openai is None:
        _openai = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _openai

def embed_text(text: str) -> list[float]:
    response = _get_openai().embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding

def upsert_chunks(chunks: list[dict], namespace: str):
    index = _get_index()
    vectors = []
    for chunk in chunks:
        embedding = embed_text(chunk["text"])
        vectors.append({
            "id": chunk["id"],
            "values": embedding,
            "metadata": {
                "text": chunk["text"],
                "source": chunk["source"],
                "page": chunk["page"]
            }
        })
        # Upsert in batches of 100 to avoid payload limits
        if len(vectors) >= 100:
            index.upsert(vectors=vectors, namespace=namespace)
            vectors = []
    if vectors:
        index.upsert(vectors=vectors, namespace=namespace)

def query_index(query: str, namespace: str, top_k: int = 5) -> list[dict]:
    index = _get_index()
    embedding = embed_text(query)
    results = index.query(
        vector=embedding,
        top_k=top_k,
        namespace=namespace,
        include_metadata=True
    )
    return [
        {
            "text": m.metadata["text"],
            "source": m.metadata["source"],
            "page": m.metadata["page"],
            "score": m.score
        }
        for m in results.matches
        if m.score > 0.3  # Filter out low-relevance results
    ]

def delete_namespace(namespace: str):
    _get_index().delete(delete_all=True, namespace=namespace)
