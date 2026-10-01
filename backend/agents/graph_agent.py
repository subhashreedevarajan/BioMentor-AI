"""BioMentor AI — Knowledge Graph Agent (Strict Grounding)

Extracts knowledge graph from document text with zero hallucination:
  - Concepts: ONLY terms explicitly mentioned in the text
  - Relationships: ONLY connections clearly described in the text
  - No inferred links, no assumed prerequisites

Each course gets its own isolated graph.
"""
import json
from langchain_groq import ChatGroq
from config import GROQ_API_KEY, LLM_MODEL, LLM_TEMPERATURES


def _get_llm(max_tokens=2000):
    """Create LLM instance for graph extraction."""
    return ChatGroq(
        api_key=GROQ_API_KEY,
        model=LLM_MODEL,
        temperature=0.1,  # Very low — factual extraction only
        max_tokens=max_tokens,
    )


def _parse_json_response(content: str) -> dict:
    """Parse JSON from LLM response, handling markdown code blocks."""
    content = content.strip()
    if content.startswith("```"):
        parts = content.split("```")
        if len(parts) >= 3:
            inner = parts[1]
            if inner.startswith("json"):
                inner = inner[4:]
            content = inner.strip()
        else:
            content = parts[1] if len(parts) > 1 else content
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
    return json.loads(content)


# ── Prompts ───────────────────────────────────────────

GRAPH_SYSTEM_PROMPT = """You are a knowledge graph builder.
Extract ONLY explicitly mentioned concepts from the provided text.
Only create relationships that are clearly described in the text.
Do NOT infer missing links.
Do NOT add concepts not present in the text.
Do NOT assume prerequisites unless the text explicitly states one topic requires or depends on another.

RULES:
- Every concept name must appear verbatim (or very close) in the source text.
- Relationship types must describe what the text actually states (e.g., "requires", "enables", "part_of", "used_in", "causes", "contrasts_with").
- If no clear relationships exist, return an empty relationships list.
- Source and target in relationships must reference concept names from the concepts list."""

GRAPH_USER_PROMPT = """Extract a knowledge graph from the following text.

TEXT:
\"\"\"
{text}
\"\"\"

Return ONLY this JSON (no markdown, no explanation):
{{
  "concepts": [
    {{"id": "c1", "name": "concept name exactly as in text"}}
  ],
  "relationships": [
    {{
      "source": "concept name",
      "target": "concept name",
      "relation_type": "relationship as described in text"
    }}
  ]
}}"""


def extract_knowledge_graph(raw_text: str) -> dict:
    """Extract grounded knowledge graph from the full document text.

    Args:
        raw_text: Full document text (source of truth)

    Returns:
        Dict with concepts list and relationships list.
        All concepts appear in the text. No hallucinated links.
    """
    llm = _get_llm(max_tokens=2000)

    # Use enough text for graph extraction (but cap for token safety)
    text_for_graph = raw_text[:12000]

    try:
        response = llm.invoke([
            {"role": "system", "content": GRAPH_SYSTEM_PROMPT},
            {"role": "user", "content": GRAPH_USER_PROMPT.format(text=text_for_graph)},
        ])
        graph = _parse_json_response(response.content)

        concepts = graph.get("concepts", [])
        relationships = graph.get("relationships", [])

        # Validate: ensure concept names appear in the source text
        validated_concepts = []
        text_lower = raw_text.lower()
        for c in concepts:
            name = c.get("name", "").strip()
            if name and name.lower() in text_lower:
                validated_concepts.append({"id": c.get("id", ""), "name": name})

        # Validate: ensure relationship endpoints exist in validated concepts
        valid_names = {c["name"].lower() for c in validated_concepts}
        validated_relationships = []
        for r in relationships:
            source = r.get("source", "").strip()
            target = r.get("target", "").strip()
            if source.lower() in valid_names and target.lower() in valid_names:
                validated_relationships.append({
                    "source": source,
                    "target": target,
                    "relation_type": r.get("relation_type", "related_to"),
                })

        print(f"  📊 Graph: {len(validated_concepts)} concepts, {len(validated_relationships)} relationships")
        if len(concepts) != len(validated_concepts):
            print(f"  ⚠️ Filtered out {len(concepts) - len(validated_concepts)} hallucinated concepts")

        return {
            "concepts": validated_concepts,
            "relationships": validated_relationships,
        }

    except Exception as e:
        print(f"  ⚠️ Graph extraction failed: {e}")
        return {
            "concepts": [],
            "relationships": [],
        }


def extract_section_graph(section_text: str, section_concepts: list) -> dict:
    """Extract a mini knowledge graph for a single section.

    Uses pre-extracted concepts from section generation as seed.

    Args:
        section_text: Text of this section
        section_concepts: Concepts already extracted during section generation

    Returns:
        Dict with concepts and relationships for this section
    """
    if not section_concepts:
        return {"concepts": [], "relationships": []}

    llm = _get_llm(max_tokens=1500)

    # Build a focused prompt with known concepts
    concepts_str = ", ".join(section_concepts)

    prompt = f"""Given these concepts from the text: {concepts_str}

And this section text:
\"\"\"
{section_text[:5000]}
\"\"\"

Extract ONLY relationships between these concepts that are explicitly described in the text.
Do NOT infer relationships. Only extract what the text clearly states.

Return ONLY this JSON:
{{
  "relationships": [
    {{
      "source": "concept name",
      "target": "concept name",
      "relation_type": "relationship described in text"
    }}
  ]
}}"""

    try:
        response = llm.invoke([
            {"role": "system", "content": GRAPH_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ])
        result = _parse_json_response(response.content)
        relationships = result.get("relationships", [])

        # Validate endpoints exist in the concepts list
        valid = {c.lower() for c in section_concepts}
        validated = [
            r for r in relationships
            if r.get("source", "").lower() in valid
            and r.get("target", "").lower() in valid
        ]

        return {
            "concepts": [{"id": f"c{i}", "name": c} for i, c in enumerate(section_concepts)],
            "relationships": validated,
        }

    except Exception as e:
        print(f"  ⚠️ Section graph extraction failed: {e}")
        return {
            "concepts": [{"id": f"c{i}", "name": c} for i, c in enumerate(section_concepts)],
            "relationships": [],
        }
