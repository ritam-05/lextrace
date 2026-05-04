import gc
import torch
from fastapi import FastAPI
from contextlib import asynccontextmanager
from sentence_transformers import SentenceTransformer
from backend.database import Database

#from backend.routes.upload import router as upload_router
#app.include_router(upload_router, prefix="/api")
from backend.state import ml_models
from backend.routes.rag_test import router as upload_router





@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP SEQUENCE ---
    print("🚀 Starting LexTrace Backend...")
    
    # 1. Initialize MongoDB Connection
    Database.connect()

    # 2. Load BGE Model into VRAM
    print("🧠 Loading BAAI/bge-large-en-v1.5 into VRAM...")
    try:
        # Strictly enforce CUDA constraint for the RTX 2050
        device = "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cpu":
            print("⚠️ FATAL WARNING: CUDA not detected. Model is running on CPU. This violates the hardware constraints.")
        
        # Load the model directly to the target device
        model = SentenceTransformer("BAAI/bge-large-en-v1.5", device=device)
        ml_models["bge"] = model
        print(f"✅ BGE Model loaded successfully on {device}!")
        
    except Exception as e:
        print(f"❌ Failed to load embedding model: {e}")
        raise e

    # Yield control to the FastAPI application
    yield 

    # --- SHUTDOWN SEQUENCE ---
    print("🛑 Shutting down LexTrace Backend...")
    
    # 1. Close Database Connections
    Database.close()
    
    # 2. Aggressive VRAM Flushing
    ml_models.clear()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        gc.collect()
    print("🧹 VRAM explicitly cleared and garbage collected.")

# Initialize the FastAPI app with the lifespan context
app = FastAPI(lifespan=lifespan, title="LexTrace Core API")
app.include_router(upload_router, prefix="/api")

@app.get("/health")
async def health_check():
    """Simple endpoint to verify system status."""
    return {
        "status": "active", 
        "database": "connected" if Database.client is not None else "disconnected",
        "embedding_model": "loaded" if "bge" in ml_models else "missing",
        "device": "cuda" if torch.cuda.is_available() else "cpu"
    }