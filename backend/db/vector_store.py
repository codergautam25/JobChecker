import os
import requests
import chromadb
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
from dotenv import load_dotenv

load_dotenv()

CHROMADB_PERSIST_DIRECTORY = os.getenv("CHROMADB_PERSIST_DIRECTORY", "./chromadb_storage")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")

class OllamaEmbeddingFunction(EmbeddingFunction):
    def __init__(self, base_url: str, model_name: str):
        self.base_url = base_url
        self.model_name = model_name

    def __call__(self, input: Documents) -> Embeddings:
        embeddings = []
        for text in input:
            try:
                response = requests.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model_name, "prompt": text},
                    timeout=10
                )
                response.raise_for_status()
                embeddings.append(response.json()["embedding"])
            except Exception as e:
                print(f"Error generating embedding via Ollama: {e}")
                # Fallback: return a zero-vector or handle error
                # For safety, we can use a dummy vector if Ollama is not running yet
                # during initial dry runs.
                embeddings.append([0.0] * 768) # nomic-embed-text is 768 dimensions
        return embeddings

def get_chroma_client():
    return chromadb.PersistentClient(path=CHROMADB_PERSIST_DIRECTORY)

def get_resume_collection():
    client = get_chroma_client()
    embedding_fn = OllamaEmbeddingFunction(OLLAMA_BASE_URL, OLLAMA_EMBEDDING_MODEL)
    return client.get_or_create_collection(
        name="resume_chunks",
        embedding_function=embedding_fn
    )

def add_resume_chunks(chunks, doc_id="resume"):
    collection = get_resume_collection()
    
    # Delete existing entries for this doc_id to avoid duplication
    collection.delete(where={"doc_id": doc_id})
    
    ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [{"doc_id": doc_id, "chunk_index": i} for i in range(len(chunks))]
    
    collection.add(
        documents=chunks,
        ids=ids,
        metadatas=metadatas
    )
    print(f"Added {len(chunks)} chunks to vector store.")

def query_resume(query_text, n_results=3):
    collection = get_resume_collection()
    try:
        results = collection.query(
            query_texts=[query_text],
            n_results=n_results
        )
        # Flatten and return documents
        return results["documents"][0] if results["documents"] else []
    except Exception as e:
        print(f"Error querying ChromaDB: {e}")
        return []

if __name__ == "__main__":
    # Test connection
    client = get_chroma_client()
    print("ChromaDB Client initialized. Collection list:", client.list_collections())
