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
            raise RuntimeError("BGE model not loaded in VRAM. Is the FastAPI server running?")
        
        db = Database.get_db()

        print(f"Starting strictly batched embedding for {len(child_chunks)} chunks (Batch Size: {self.batch_size})...")
        
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
        print(" Chunk encoding complete. VRAM aggressively flushed and garbage collected.")

        # 5. MongoDB Ingestion (System RAM -> Network)
        print("Pushing vectors and text to MongoDB Atlas...")
        try:
            # We insert parents (text only) and children (text + 1024d vector)
            if parent_documents:
                db.parent_documents.insert_many(parent_documents)
            if child_chunks:
                db.child_chunks.insert_many(child_chunks)
            print(f"Successfully ingested {len(parent_documents)} parents and {len(child_chunks)} children.")
        except Exception as e:
            print(f"MongoDB Insertion Failed: {e}")
            raise e
        

    def retrieve_context(
        self,
        semantic_query: str,
        keyword_query: str,
        top_k: int = 5,
        include_sources: bool = False,
    ):
        """
        Executes parallel Vector and BM25 searches using decoupled queries, 
        fuses them via RRF, and chronologically reconstructs parent contexts.
        """
        model = ml_models.get("bge")
        db = Database.get_db()

        if not model:
            raise RuntimeError("BGE model not loaded in VRAM.")

        # --- THE SYNC DELAY (Hackathon Fix) ---
        print("Waiting 11 seconds for Atlas Indexes to sync...")
        time.sleep(11)

        # ==========================================
        # QUERY A: DENSE VECTOR SEARCH (Semantic)
        # ==========================================
        prefix = "Represent this sentence for searching relevant passages: "
        full_semantic_query = prefix + semantic_query

        with torch.no_grad():
            query_vector = model.encode(full_semantic_query, convert_to_tensor=True).cpu().tolist()

        vector_pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index", 
                    "path": "embedding",
                    "queryVector": query_vector,
                    "numCandidates": top_k * 10, 
                    "limit": top_k * 2
                }
            },
            {
                "$project": {
                    "child_id": 1,
                    "parent_id": 1,
                    "score": { "$meta": "vectorSearchScore" },
                    "page": 1,
                    "text": 1,
                }
            }
        ]

        print(f"Executing vector search...")
        vector_results = list(db.child_chunks.aggregate(vector_pipeline))

        # ==========================================
        # QUERY B: SPARSE TEXT SEARCH (BM25 Keyword)
        # ==========================================
        text_pipeline = [
            {
                "$search": {
                    "index": "default", 
                    "text": {
                        "query": keyword_query,
                        "path": "text"
                    }
                }
            },
            { "$limit": top_k * 2 },
            {
                "$project": {
                    "child_id": 1,
                    "parent_id": 1,
                    "score": { "$meta": "searchScore" },
                    "page": 1,
                    "text": 1,
                }
            }
        ]

        print(f"Executing BM25 keyword search...")
        text_results = list(db.child_chunks.aggregate(text_pipeline))

        # ==========================================
        # RECIPROCAL RANK FUSION (RRF)
        # ==========================================
        # Formula: 1 / (k + Rank_vector) + 1 / (k + Rank_keyword) where k = 60
        k = 60
        rrf_scores = {}

        for rank, res in enumerate(vector_results):
            cid = res.get("child_id", str(res.get("_id")))
            pid = res.get("parent_id")
            rrf_scores[cid] = {
                "score": 1.0 / (k + rank + 1),
                "parent_id": pid,
                "page": res.get("page"),
                "text": res.get("text", ""),
            }

        for rank, res in enumerate(text_results):
            cid = res.get("child_id", str(res.get("_id")))
            pid = res.get("parent_id")
            if cid in rrf_scores:
                rrf_scores[cid]["score"] += 1.0 / (k + rank + 1)
            else:
                rrf_scores[cid] = {
                    "score": 1.0 / (k + rank + 1),
                    "parent_id": pid,
                    "page": res.get("page"),
                    "text": res.get("text", ""),
                }

        # Sort chunks by unified RRF score descending
        sorted_chunks = sorted(rrf_scores.items(), key=lambda item: item[1]["score"], reverse=True)

        # Extract top distinct parent_ids
        distinct_parents = []
        for cid, data in sorted_chunks:
            pid = data["parent_id"]
            if pid and pid not in distinct_parents:
                distinct_parents.append(pid)
            if len(distinct_parents) == top_k:
                break

        if not distinct_parents:
            print("No relevant chunks found across both indexes.")
            if include_sources:
                return {"context": "", "source_pages": [], "source_chunks": []}
            return ""

        # ==========================================
        # SEQUENTIAL PARENT RECONSTRUCTION
        # ==========================================
        unordered_parents = list(db.parent_documents.find({"parent_id": {"$in":distinct_parents}}))
        parent_map = {p["parent_id"]: p["text"] for p in unordered_parents}

        # CRUCIAL FIX: Sort distinct_parents chronologically by their suffix (e.g., doc123_p1,  doc123_p2)
        # This prevents the LLM from hallucinating legal timelines.
        def extract_sequence(pid: str) -> int:
            try:
                return int(pid.split('_p')[-1])
            except ValueError:
                return 0

        chronological_parents = sorted(distinct_parents, key=extract_sequence)

        ordered_texts = []
        for pid in chronological_parents:
            if pid in parent_map:
                ordered_texts.append(parent_map[pid])

        context = "\n\n".join(ordered_texts)
        print(f"Reconstructed {len(ordered_texts)} parent contexts in chronological order.")

        if include_sources:
            source_chunks = []
            source_pages = []

            for cid, data in sorted_chunks[: top_k * 2]:
                page = data.get("page")
                source_chunks.append(
                    {
                        "child_id": cid,
                        "parent_id": data.get("parent_id"),
                        "page": page,
                        "score": data.get("score"),
                        "text": data.get("text", ""),
                    }
                )

                if isinstance(page, int) and page not in source_pages:
                    source_pages.append(page)

            return {
                "context": context,
                "source_pages": source_pages,
                "source_chunks": source_chunks,
            }

        return context

    def delete_document_data(self, document_id: str):
        """
        Deletes all temporary parent/child records for a processed document.
        """
        db = Database.get_db()
        parent_result = db.parent_documents.delete_many({"document_id": document_id})
        child_result = db.child_chunks.delete_many({"document_id": document_id})

        print(
            f"Cleaned up temporary RAG data for {document_id}: "
            f"{parent_result.deleted_count} parent chunks, "
            f"{child_result.deleted_count} child chunks deleted."
        )

# Quick test block
if __name__ == "__main__":
    print("Run this through the FastAPI route to ensure lifespan loads the model first.")
