from fastapi import FastAPI

from app.api.routes import charter, document_lion, translation, writing_assistant

app = FastAPI(title="AI-Fighters", version="0.1.0")

app.include_router(translation.router, prefix="/api/ai")
app.include_router(writing_assistant.router, prefix="/api/ai")
app.include_router(document_lion.router, prefix="/api/ai")
app.include_router(charter.router, prefix="/api/ai")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
