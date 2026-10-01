"""BioMentor AI — Validation Agent (Hallucination Checker)

Second-pass verification: checks whether LLM-generated output
contains information NOT present in the source text.

Usage:
  result = validate_output(source_text, generated_output)
  if not result["grounded"]:
      # Regenerate with stricter instructions
"""
import json
from langchain_groq import ChatGroq
from config import GROQ_API_KEY, LLM_MODEL


def _get_llm():
    """Create LLM with very low temperature for factual validation."""
    return ChatGroq(
        api_key=GROQ_API_KEY,
        model=LLM_MODEL,
        temperature=0.1,
        max_tokens=1000,
    )


def _parse_json_response(content: str) -> dict:
    """Parse JSON from LLM response."""
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


VALIDATION_PROMPT = """You are a grounding validator. Your job is to check whether generated content is faithful to the source text.

SOURCE TEXT:
\"\"\"
{source_text}
\"\"\"

GENERATED OUTPUT:
\"\"\"
{generated_output}
\"\"\"

Check whether the generated output contains ANY information not explicitly present in the source text.

Look specifically for:
1. Concepts or terms NOT mentioned in the source text
2. Relationships or connections NOT described in the source text
3. Domain claims NOT stated in the source text
4. Applications or examples NOT mentioned in the source text
5. Any factual claims that cannot be verified from the source text

Return ONLY this JSON:
{{
  "grounded": true or false,
  "hallucinated_parts": ["description of each hallucinated item"],
  "confidence": 0.0 to 1.0
}}

If everything is grounded, return:
{{
  "grounded": true,
  "hallucinated_parts": [],
  "confidence": 1.0
}}"""


def validate_output(source_text: str, generated_output: str) -> dict:
    """Validate whether generated output is grounded in source text.

    Args:
        source_text: Original document text (source of truth)
        generated_output: LLM-generated content to validate

    Returns:
        Dict with grounded (bool), hallucinated_parts (list), confidence (float)
    """
    llm = _get_llm()

    # Cap text lengths for token safety
    source_excerpt = source_text[:6000]

    # If generated_output is a dict, convert to string for validation
    if isinstance(generated_output, dict):
        output_str = json.dumps(generated_output, indent=2)
    else:
        output_str = str(generated_output)

    output_excerpt = output_str[:3000]

    try:
        response = llm.invoke([
            {"role": "system", "content": "You are a strict grounding validator. Check if generated content is faithful to source text. Be conservative — flag anything suspicious."},
            {"role": "user", "content": VALIDATION_PROMPT.format(
                source_text=source_excerpt,
                generated_output=output_excerpt,
            )},
        ])

        result = _parse_json_response(response.content)
        return {
            "grounded": result.get("grounded", True),
            "hallucinated_parts": result.get("hallucinated_parts", []),
            "confidence": result.get("confidence", 0.5),
        }

    except Exception as e:
        print(f"  ⚠️ Validation check failed: {e}")
        # On failure, assume grounded (don't block generation)
        return {
            "grounded": True,
            "hallucinated_parts": [],
            "confidence": 0.5,
        }


def validate_concepts(source_text: str, concepts: list) -> list:
    """Validate that all extracted concepts appear in the source text.

    Simple text-matching validation — no LLM needed.

    Args:
        source_text: Original document text
        concepts: List of concept names

    Returns:
        List of validated concepts (only those found in text)
    """
    text_lower = source_text.lower()
    validated = []
    removed = []

    for concept in concepts:
        if not concept or not concept.strip():
            continue
        # Check if concept appears in text (case-insensitive)
        if concept.lower().strip() in text_lower:
            validated.append(concept.strip())
        else:
            # Try partial match (concept words appear near each other)
            words = concept.lower().strip().split()
            if len(words) > 1 and all(w in text_lower for w in words):
                validated.append(concept.strip())
            else:
                removed.append(concept)

    if removed:
        print(f"  ⚠️ Removed {len(removed)} hallucinated concepts: {removed[:5]}")

    return validated


def validate_and_retry(
    source_text: str,
    generator_fn,
    generator_args: dict,
    max_retries: int = 2,
) -> tuple:
    """Generate output, validate, and retry if hallucinated.

    Args:
        source_text: Original text for grounding check
        generator_fn: Function to call for generation
        generator_args: Keyword arguments for generator_fn
        max_retries: Maximum retry attempts

    Returns:
        Tuple of (generated_output, validation_result)
    """
    for attempt in range(max_retries + 1):
        output = generator_fn(**generator_args)

        # Convert output to string for validation
        if isinstance(output, dict):
            output_str = json.dumps(output)
        else:
            output_str = str(output)

        validation = validate_output(source_text, output_str)

        if validation["grounded"]:
            return output, validation

        print(f"  🔄 Hallucination detected (attempt {attempt + 1}), retrying...")

    # Return last attempt even if not fully grounded
    print(f"  ⚠️ Max retries reached, using last output")
    return output, validation
