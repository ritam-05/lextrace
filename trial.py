def retrieve_context(self, query: str, top_k: int = 5) -> str:
    """
    Executes parallel Vector and BM25 searches, fuses them via RRF, 
    and chronologically reconstructs parent contexts.
    """
    model = ml_models.get("bge")
    db = Database.get_db()

    if not model:
        raise RuntimeError("BGE model not loaded in VRAM.")

    # --- THE SYNC DELAY (Hackathon Fix) ---
    print("Waiting 3 seconds for Atlas Indexes to sync...")
    time.sleep(3)

    # ==========================================
    # QUERY A: DENSE VECTOR SEARCH (Semantic)
    # ==========================================
    prefix = "Represent this sentence for searching relevant passages: "
    full_query = prefix + query

    with torch.no_grad():
        query_vector = model.encode(full_query, convert_to_tensor=True).cpu().tolist()

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
                "score": { "$meta": "vectorSearchScore" }
            }
        }
    ]
    
    print(f"🔍 Executing vector search...")
    vector_results = list(db.child_chunks.aggregate(vector_pipeline))

    # ==========================================
    # QUERY B: SPARSE TEXT SEARCH (BM25 Keyword)
    # ==========================================
    text_pipeline = [
        {
            "$search": {
                "index": "default", 
                "text": {
                    "query": query,
                    "path": "text"
                }
            }
        },
        { "$limit": top_k * 2 },
        {
            "$project": {
                "child_id": 1,
                "parent_id": 1,
                "score": { "$meta": "searchScore" }
            }
        }
    ]

    print(f"🔍 Executing BM25 keyword search...")
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
            "parent_id": pid
        }

    for rank, res in enumerate(text_results):
        cid = res.get("child_id", str(res.get("_id")))
        pid = res.get("parent_id")
        if cid in rrf_scores:
            rrf_scores[cid]["score"] += 1.0 / (k + rank + 1)
        else:
            rrf_scores[cid] = {
                "score": 1.0 / (k + rank + 1),
                "parent_id": pid
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
        return ""

    # ==========================================
    # SEQUENTIAL PARENT RECONSTRUCTION
    # ==========================================
    unordered_parents = list(db.parent_documents.find({"parent_id": {"$in":distinct_parents}}))
    parent_map = {p["parent_id"]: p["text"] for p in unordered_parents}

    # CRUCIAL FIX: Sort distinct_parents chronologically by their suffix (e.g., doc123_p1, doc123_p2)
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
    print(f"✅ Reconstructed {len(ordered_texts)} parent contexts in chronological order.")
    
    return context