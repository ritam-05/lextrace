import uuid
import fitz  # PyMuPDF
from fastapi import APIRouter, UploadFile, File, HTTPException
from backend.rag_engine.chunker import LegalDocumentChunker
from backend.rag_engine.embeddings import RAGService
from backend.rag_engine.generator import ActionPlanGenerator
from backend.database import Database

router = APIRouter()

# Initialize singletons for the route
chunker = LegalDocumentChunker()
rag_service = RAGService(batch_size=16)  # Strict VRAM constraint
generator = ActionPlanGenerator()

@router.post("/upload")
async def process_judgment(file: UploadFile = File(...)):
    """
    Receives a judgment PDF and runs the standalone Track B (RAG) pipeline.
    Track A (Regex) is currently bypassed.
    """
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    print(f"\nReceived Document: {file.filename}")
    document_id = f"doc_{uuid.uuid4().hex[:8]}"

    # --- INGESTION & SANITIZATION ---
    try:
        pdf_bytes = await file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        # Extract text from all pages and join with newlines
        raw_text = "\n".join([page.get_text() for page in doc])
        doc.close()
        
        if not raw_text.strip():
            raise HTTPException(status_code=400, detail="Could not extract readable text from the PDF. It may be a scanned image requiring OCR.")
            
        print(f"Extracted {len(raw_text)} characters of raw text.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDF Parsing Failed: {str(e)}")

    try:
        # --- TRACK B: RAG PIPELINE ---
        # 1. Parent-Document Chunking
        parent_documents, child_chunks = chunker.process_document(raw_text, document_id)

        # 2. VRAM-Throttled Vectorization & Atlas Ingestion
        rag_service.ingest_document(parent_documents, child_chunks)

        # 3. Context Retrieval
        # We decouple the query: one conversational for semantic intent, one keyword-dense for exact matching.
        semantic_query = "What are the final operational directives, orders, deadlines issued by the court, and which specific departments are instructed to take action?"
        
        keyword_query = (
            "directed directs ordered orders mandate hereby shall instructed "
            "timeline days weeks months within forthwith immediately period "
            "department ministry authority respondent committee board "
            "compliance strict affidavit report execution disposed decree"
        )
        
        retrieved_context = rag_service.retrieve_context(
            semantic_query=semantic_query,
            keyword_query=keyword_query,
            top_k=5
        )

        if not retrieved_context:
            raise HTTPException(status_code=500, detail="Failed to retrieve relevant context from the database.")

        # 4. LLM Generation
        # We pass an empty dictionary for `hard_facts` since the Regex track is offline
        print("Generating Action Plan via Groq...")
        action_plan = generator.generate(context=retrieved_context, hard_facts={})
        
        # Append tracking metadata
        action_plan["document_id"] = document_id
        action_plan["source_file"] = file.filename

        # --- DATABASE QUEUEING ---
        db = Database.get_db()
        try:
            # Insert a copy to prevent PyMongo from mutating our dict with an ObjectId
            db.action_plans.insert_one(action_plan.copy())
            print("Action Plan successfully queued in MongoDB pending_review status.")
        except Exception as e:
            print(f"Failed to save Action Plan to MongoDB: {e}")

        # Return the structured data to the client
        return {
            "status": "success",
            "document_id": document_id,
            "action_plan": action_plan
        }
    finally:
        rag_service.delete_document_data(document_id)
