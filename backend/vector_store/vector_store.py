import chromadb
from sentence_transformers import SentenceTransformer
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "chroma_db")

class VectorDBManager:
    def __init__(self, path=DB_PATH):
        self.path = path
        self.client = chromadb.PersistentClient(path=path)
        self.model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

        self._ensure_collection()

    def get_collection(self):
        try:
            return self.client.get_or_create_collection(
                name="pdf_documents",
                metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            print(f"ChromaDB collection error: {e}. Connecting again...")
            self.client = chromadb.PersistentClient(path=self.path)
            return self.client.get_or_create_collection(
                name="pdf_documents",
                metadata={"hnsw:space": "cosine"}
            )

    def _ensure_collection(self):
        try:
            self.get_collection()

        except Exception as e:
            print(f"ChromaDB connection error: {e}")
            self.client = chromadb.PersistentClient(path=self.path)
            self.get_collection()                             

    def add_chunks(self, chunks, file_id):
        collection = self.get_collection()

        try:
            existing = collection.get(where={"file_id": file_id})
            if existing and existing['ids']:
                collection.delete(ids=existing['ids'])
                print(f"DEBUG: {len(existing['ids'])} old chunks has been removed.")
        except Exception as e:
            print(f"{e}")

        try:
            self._ensure_collection()

            cleaned_metadata = []
            
            for c in chunks:
                meta = c.get('metadata', {}).copy()
                meta['file_id'] = file_id

                if not meta.get("section_title"):
                    meta["section_title"] = "Untitled"
                cleaned_metadata.append(meta)

            try:
                self.get_collection().delete(where={"file_id": file_id})
            except Exception:
                pass

            documents = [c["text"] for c in chunks]
            embeddings = self.model.encode(documents).tolist()
            ids = [f"{file_id}_{i}" for i in range(1, len(chunks)+1)]

            self.get_collection().upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=cleaned_metadata
            )
        except Exception as e:
            print(e)

    def search(self, query, file_ids, n_results=5):
        query_vector = self.model.encode([query]).tolist()

        count = self.get_collection().count()

        results = self.get_collection().query(
            query_embeddings=query_vector,
            n_results=n_results,
            where = {"file_id": {"$in": file_ids}} if file_ids else None
        )
        return results
    
    
    def clear_all_memory(self):
        try:
            self.client.delete_collection(name="pdf_documents")
            self.get_collection()
        except Exception as e:
            print(f"Error while deleting memory (Collection might be absent.)): {e}")
