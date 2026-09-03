import httpx

from mcp.server.fastmcp import FastMCP


mcp = FastMCP("ContextOS")

CONTEXTOS_API = "http://127.0.0.1:8000"


@mcp.tool()
async def search_context(query: str, limit: int = 5) -> dict:
    """
    Search ContextOS across memories, documents, and knowledge graph.
    """

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{CONTEXTOS_API}/search",
            json={
                "query": query,
                "limit": limit,
            },
            timeout=30.0,
        )

        response.raise_for_status()

        return response.json()


if __name__ == "__main__":
    mcp.run()
