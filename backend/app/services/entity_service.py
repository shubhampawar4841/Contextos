import json

from app.services.llm_service import generate_text


def extract_entities_and_relationships(text: str):
    prompt = f"""
Extract important entities and relationships from the message.

Entity types can include:
- person
- project
- company
- technology
- product
- location
- topic

Only extract useful, meaningful knowledge.
Do not extract random words.

Return ONLY valid JSON.

Format:

{{
  "entities": [
    {{
      "name": "ContextOS",
      "type": "project"
    }}
  ],
  "relationships": [
    {{
      "source": "ContextOS",
      "relationship": "uses",
      "target": "Supabase"
    }}
  ]
}}

Message:
{text}
"""

    try:
        raw = generate_text(prompt)
        raw = (
            raw
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )
        data = json.loads(raw)
    except Exception as e:
        print(f"Entity extraction skipped: {e}")
        return {
            "entities": [],
            "relationships": [],
        }

    if not isinstance(data, dict):
        return {
            "entities": [],
            "relationships": [],
        }

    entities = data.get("entities") or []
    relationships = data.get("relationships") or []

    if not isinstance(entities, list):
        entities = []
    if not isinstance(relationships, list):
        relationships = []

    return {
        "entities": entities,
        "relationships": relationships,
    }
