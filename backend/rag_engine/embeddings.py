import gc
import torch
import time
from typing import List, Dict
from backend.state import ml_models
from backend.database import Database

class RAGService:
    def __init__(self, batch_size: int = 16):
        """
        batch_size=16 is hardcoded to strictly prevent RTX 2050 OOM crashes.
        """
        self.batch_size = batch_size

    def ingest_document(self, parent_documents: List[Dict], child_chunks: List[Dict]):
        """
        Executes the VRAM Throttling Execution Plan to safely embed and upload chunks.
        """
        # 1. Fetch resources
        model = ml_models.get("bge")
        if not model:
            raise RuntimeError("❌ BGE model not loaded in VRAM. Is the FastAPI server running?")
        
        db = Database.get_db()

        print(f"⚙️ Starting strictly batched embedding for {len(child_chunks)} chunks (Batch Size: {self.batch_size})...")
        
        # 2. Extract texts for the embedding model
        # NOTE: BGE models DO NOT use the "Represent this sentence..." prefix for DOCUMENTS. 
        # The prefix is strictly for queries. We embed the raw text here.
        child_texts = [chunk["text"] for chunk in child_chunks]

        # 3. Strict Batch Processing Loop
        for i in range(0, len(child_texts), self.batch_size):
            batch_texts = child_texts[i : i + self.batch_size]
            
            # Disable gradient calculation for pure inference (saves VRAM)
            with torch.no_grad():
                # Generate embeddings for this specific batch
                embeddings_tensor = model.encode(batch_texts, convert_to_tensor=True)
                
                # IMMEDIATE CPU OFFLOADING
                # Moves the 1024-d tensors off the GPU and into 8GB System RAM as native Python lists
                cpu_embeddings = embeddings_tensor.cpu().tolist()
            
            # Map the offloaded embeddings back to our dictionaries
            for j, emb in enumerate(cpu_embeddings):
                child_chunks[i + j]["embedding"] = emb
            
            print(f"   -> Embedded batch {i // self.batch_size + 1}")

        # 4. Aggressive VRAM Flushing
        # The exact millisecond the loop is done, we purge the PyTorch cache
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            gc.collect()
        print("🧹 Chunk encoding complete. VRAM aggressively flushed and garbage collected.")

        # 5. MongoDB Ingestion (System RAM -> Network)
        print("☁️ Pushing vectors and text to MongoDB Atlas...")
        try:
            # We insert parents (text only) and children (text + 1024d vector)
            if parent_documents:
                db.parent_documents.insert_many(parent_documents)
            if child_chunks:
                db.child_chunks.insert_many(child_chunks)
            print(f"✅ Successfully ingested {len(parent_documents)} parents and {len(child_chunks)} children.")
        except Exception as e:
            print(f"❌ MongoDB Insertion Failed: {e}")
            raise e
        

    def retrieve_context(self, query: str, top_k: int = 5) -> str:
        """
        Embeds the query, executes vector search, and strictly preserves semantic ranking.
        """
        model = ml_models.get("bge")
        db = Database.get_db()

        if not model:
            raise RuntimeError("❌ BGE model not loaded in VRAM.")

        # --- THE SYNC DELAY (Hackathon Fix) ---
        # Atlas M0 Free Tier needs a moment to index newly inserted vectors.
        # If running a single combined upload/search route, we must wait.
        print("⏳ Waiting 3 seconds for Atlas Vector Index to sync...")
        time.sleep(3)

        # 1. Embed Query WITH Prefix
        prefix = "Represent this sentence for searching relevant passages: "
        full_query = prefix + query

        with torch.no_grad():
            query_vector = model.encode(full_query, convert_to_tensor=True).cpu().tolist()

        # 2. Atlas Vector Search Pipeline
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index", 
                    "path": "embedding",
                    "queryVector": query_vector,
                    "numCandidates": top_k * 10, 
                    "limit": top_k
                }
            },
            {
                "$project": {
                    "parent_id": 1,
                    "score": { "$meta": "vectorSearchScore" }
                }
            }
        ]

        print(f"🔍 Executing vector search for query: '{query}'")
        search_results = list(db.child_chunks.aggregate(pipeline))

        if not search_results:
            print("⚠️ No relevant chunks found in the database.")
            return ""

        # 3. Preserving Semantic Rank
        # We loop through results and keep the exact ordered sequence of parent IDs.
        ordered_parent_ids = []
        for res in search_results:
            pid = res["parent_id"]
            if pid not in ordered_parent_ids:
                ordered_parent_ids.append(pid)

        # 4. Fetch Full Parent Contexts
        # MongoDB $in queries return documents in random disk order. 
        unordered_parents = list(db.parent_documents.find({"parent_id": {"$in": ordered_parent_ids}}))
        
        # 5. Rebuild the Strict Ordering
        # Map the random output back to our mathematically ranked sequence
        parent_map = {p["parent_id"]: p["text"] for p in unordered_parents}
        
        ordered_texts = []
        for pid in ordered_parent_ids:
            if pid in parent_map:
                ordered_texts.append(parent_map[pid])

        context = "\n\n".join(ordered_texts)
        print(f"✅ Retrieved and ordered {len(ordered_texts)} unique parent contexts.")
        
        return context

# Quick test block
if __name__ == "__main__":
    print("Run this through the FastAPI route to ensure lifespan loads the model first.")