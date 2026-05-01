from fastapi import FastAPI

from backend.routes.upload import router as upload_router


app = FastAPI(
    title="LexTrace Stage 1 Extraction API",
    description="Deterministic PDF ingestion, OCR fallback, operative isolation, and regex metadata extraction.",
    version="1.0.0",
)

app.include_router(upload_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

