from fastapi import FastAPI
from contextlib import asynccontextmanager
from backend.database import DatabaseManager

from backend.routes.upload import router as upload_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup Logic ---
    DatabaseManager.connect()
    
    # (Later, we will also load the BGE-large CUDA model here so it 
    # doesn't reload on every request)
    
    yield # The application runs while yielding
    
    # --- Shutdown Logic ---
    DatabaseManager.disconnect()

app = FastAPI(
    title="LexTrace Stage 1 Extraction API",
    description="Deterministic PDF ingestion, OCR fallback, operative isolation, and regex metadata extraction.",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(upload_router, prefix="/api")


@app.get("/")
def read_root():
    return {"status": "LexTrace Backend is running"}
