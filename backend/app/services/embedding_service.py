from google import genai
from google.genai import types

from app.core.config import settings


client = genai.Client(
    api_key=settings.GEMINI_API_KEY
)


def create_embedding(text: str) -> list[float]:
    result = client.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
        config=types.EmbedContentConfig(
            output_dimensionality=768
        ),
    )

    return result.embeddings[0].values
