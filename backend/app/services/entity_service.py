import json
import uuid

from app.services.llm_service import generate_text


# Temporary single-user MVP until auth exists
DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001"


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


def _get_or_create_entity(
    supabase,
    user_id: str,
    name: str,
    entity_type: str,
    entity_cache: dict,
    source_type: str = "chat",
    source_document_id: str | None = None,
):
    key = (name.lower().strip(), entity_type.lower().strip())

    if key in entity_cache:
        return entity_cache[key]

    existing = (
        supabase
        .table("entities")
        .select("id, name, entity_type")
        .eq("user_id", user_id)
        .ilike("name", name.strip())
        .eq("entity_type", entity_type.strip())
        .limit(1)
        .execute()
    )

    if existing.data:
        entity_id = existing.data[0]["id"]
        entity_cache[key] = entity_id
        return entity_id

    row = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "name": name.strip(),
        "entity_type": entity_type.strip(),
        "source_type": source_type,
        "source_document_id": source_document_id,
    }

    created = (
        supabase
        .table("entities")
        .insert(row)
        .execute()
    )

    entity_id = created.data[0]["id"]
    entity_cache[key] = entity_id
    return entity_id


def save_knowledge(
    supabase,
    user_id: str,
    knowledge: dict,
    source_type: str = "chat",
    source_document_id: str | None = None,
    source_page: int | None = None,
):
    entities = knowledge.get("entities") or []
    relationships = knowledge.get("relationships") or []

    if not entities and not relationships:
        return {
            "entities_saved": 0,
            "relationships_saved": 0,
        }

    entity_cache = {}
    entities_saved = 0

    for entity in entities:
        name = entity.get("name")
        entity_type = entity.get("type") or entity.get("entity_type")

        if not name or not entity_type:
            continue

        before = len(entity_cache)
        _get_or_create_entity(
            supabase=supabase,
            user_id=user_id,
            name=name,
            entity_type=entity_type,
            entity_cache=entity_cache,
            source_type=source_type,
            source_document_id=source_document_id,
        )
        if len(entity_cache) > before:
            entities_saved += 1

    name_to_type = {
        (e.get("name") or "").lower().strip(): (
            e.get("type") or e.get("entity_type") or "topic"
        )
        for e in entities
        if e.get("name")
    }

    relationships_saved = 0

    for rel in relationships:
        source = (rel.get("source") or "").strip()
        target = (rel.get("target") or "").strip()
        relationship = (rel.get("relationship") or "").strip()

        if not source or not target or not relationship:
            continue

        source_entity_type = name_to_type.get(source.lower(), "topic")
        target_entity_type = name_to_type.get(target.lower(), "topic")

        source_id = _get_or_create_entity(
            supabase=supabase,
            user_id=user_id,
            name=source,
            entity_type=source_entity_type,
            entity_cache=entity_cache,
            source_type=source_type,
            source_document_id=source_document_id,
        )
        target_id = _get_or_create_entity(
            supabase=supabase,
            user_id=user_id,
            name=target,
            entity_type=target_entity_type,
            entity_cache=entity_cache,
            source_type=source_type,
            source_document_id=source_document_id,
        )

        existing_rel = (
            supabase
            .table("entity_relationships")
            .select("id")
            .eq("user_id", user_id)
            .eq("source_entity_id", source_id)
            .eq("target_entity_id", target_id)
            .ilike("relationship", relationship)
            .limit(1)
            .execute()
        )

        if existing_rel.data:
            continue

        supabase.table("entity_relationships").insert({
            "user_id": user_id,
            "source_entity_id": source_id,
            "target_entity_id": target_id,
            "relationship": relationship,
            "source_type": source_type,
            "source_document_id": source_document_id,
            "source_page": source_page,
        }).execute()

        relationships_saved += 1

    return {
        "entities_saved": entities_saved,
        "relationships_saved": relationships_saved,
    }


def get_user_graph_context(
    supabase,
    user_id: str = DEFAULT_USER_ID,
) -> list[dict]:
    response = (
        supabase
        .table("entity_relationships")
        .select(
            """
            relationship,
            source:entities!entity_relationships_source_entity_id_fkey(name, entity_type),
            target:entities!entity_relationships_target_entity_id_fkey(name, entity_type)
            """
        )
        .eq("user_id", user_id)
        .limit(50)
        .execute()
    )

    return response.data or []
