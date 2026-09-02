import json

from app.services.llm_service import generate_text


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

    try:
        text = generate_text(prompt)
        text = text.replace("```json", "").replace("```", "").strip()
        memories = json.loads(text)
    except Exception as e:
        print(f"Memory extraction skipped: {e}")
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


def is_duplicate_memory(
    new_memory: str,
    existing_memories: list[dict],
) -> bool:
    new_text = new_memory.lower().strip()

    for memory in existing_memories:
        existing_text = memory["content"].lower().strip()

        if new_text == existing_text:
            return True

    return False
