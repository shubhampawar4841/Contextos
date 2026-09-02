from fastapi import FastAPI

from app.api.documents import router as documents_router
from app.api.search import router as search_router


app = FastAPI(
    title="ContextOS API",
    version="0.1.0",
)


@app.get("/health")
async def health():
    return {
        "status": "ok"
    }


app.include_router(documents_router)
app.include_router(search_router)
