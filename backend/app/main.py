from fastapi import FastAPI

from app.core.supabase import supabase


app = FastAPI(
    title="ContextOS API",
    version="0.1.0"
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/db-test")
async def db_test():

    response = (
        supabase
        .table("documents")
        .select("*")
        .limit(1)
        .execute()
    )

    return {
        "status": "connected",
        "data": response.data
    }