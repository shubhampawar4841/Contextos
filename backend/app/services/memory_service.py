import json

from google import genai

from app.core.config import settings


client = genai.Client(
    api_key=settings.GEMINI_API_KEY
)


def extract_memories(user_message: str):
    prompt = f"""
Extract durable memories from this user message.

Only extract information that could be useful in future conversations.

Allowed types:
- semantic: stable fact, preference, goal, skill, interest
- episodic: meaningful event or experience

Do NOT extract temporary questions or random statements.

Return ONLY valid JSON.

Format:
[
  {{
    "memory_type": "semantic",
    "content": "..."
  }}
]

If there is nothing worth remembering, return [].

User message:
{user_message}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    text = response.text.strip()
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        memories = json.loads(text)
    except Exception:
        return []

    if not isinstance(memories, list):
        return []

    cleaned = []
    for memory in memories:
        memory_type = memory.get("memory_type")
        content = memory.get("content")

        if memory_type not in {"semantic", "episodic"}:
            continue
        if not content or not str(content).strip():
            continue

        cleaned.append({
            "memory_type": memory_type,
            "content": str(content).strip(),
        })

    return cleaned
