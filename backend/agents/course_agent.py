"""BioMentor AI — Course Agent (Strict Grounding)

Section-aware course generation pipeline:
  1. extract_course_metadata() → title, summary, main_topic (from text ONLY)
  2. detect_sections() → split document into logical sections
  3. generate_section_content() → detailed lesson per section (grounded)

CRITICAL RULES:
  - Use ONLY the provided text
  - Never use external knowledge
  - Never infer domain if not stated
  - If something is not mentioned, leave it blank/empty
"""
import json
import re
from langchain_groq import ChatGroq
from config import GROQ_API_KEY, LLM_MODEL, LLM_TEMPERATURES


def _get_llm(max_tokens=2048, temperature=None):
    """Create LLM instance with specified token limit."""
    return ChatGroq(
        api_key=GROQ_API_KEY,
        model=LLM_MODEL,
        temperature=temperature or LLM_TEMPERATURES.get("course", 0.3),
        max_tokens=max_tokens,
    )


def _parse_json_response(content: str) -> dict:
    """Parse JSON from LLM response, handling markdown code blocks."""
    content = content.strip()
    if content.startswith("```"):
        # Extract content between first ``` and next ```
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


# ═══════════════════════════════════════════════════════
# STEP 1: EXTRACT COURSE METADATA
# ═══════════════════════════════════════════════════════

METADATA_SYSTEM_PROMPT = """You are an academic extraction engine.
Use ONLY the provided text. Do NOT add external knowledge.
If domain is not explicitly mentioned, say 'Not specified in text'.
If keywords are not explicitly present in the text, do not invent them.
Extract only what is explicitly stated."""

METADATA_USER_PROMPT = """Read the following document text and extract metadata.

RULES:
- main_topic must be a phrase that appears in the text
- summary must be 5-7 sentences using ONLY information from the text
- subtopics must be explicitly mentioned topics/headings in the text
- keywords must be words/phrases that actually appear in the text
- domain: only state if the text explicitly mentions its field/domain
- Do NOT add any information not present in the text

DOCUMENT TEXT:
\"\"\"
{document_text}
\"\"\"

Return ONLY this JSON (no markdown, no explanation):
{{
  "title": "",
  "main_topic": "",
  "domain": "",
  "summary": "",
  "explicit_subtopics": [],
  "keywords_from_text": []
}}"""


def extract_course_metadata(raw_text: str) -> dict:
    """Extract course metadata strictly from the document text.

    Returns:
        Dict with title, main_topic, domain, summary, subtopics, keywords.
        All fields are grounded in the source text.
    """
    llm = _get_llm(max_tokens=1500, temperature=0.2)

    # Use first 8000 chars for metadata — covers title, abstract, intro
    text_for_metadata = raw_text[:8000]

    prompt = METADATA_USER_PROMPT.format(document_text=text_for_metadata)

    try:
        response = llm.invoke([
            {"role": "system", "content": METADATA_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ])
        metadata = _parse_json_response(response.content)

        # Validate: ensure required fields exist
        return {
            "title": metadata.get("title", "Untitled Course"),
            "main_topic": metadata.get("main_topic", ""),
            "domain": metadata.get("domain", "Not specified in text"),
            "summary": metadata.get("summary", ""),
            "explicit_subtopics": metadata.get("explicit_subtopics", []),
            "keywords_from_text": metadata.get("keywords_from_text", []),
        }
    except Exception as e:
        print(f"  ⚠️ Metadata extraction failed: {e}")
        return {
            "title": _extract_title_fallback(raw_text),
            "main_topic": "",
            "domain": "Not specified in text",
            "summary": "",
            "explicit_subtopics": [],
            "keywords_from_text": [],
        }


def _extract_title_fallback(text: str) -> str:
    """Extract a title from the first meaningful line of text."""
    for line in text.split("\n"):
        line = line.strip()
        if len(line) > 10 and len(line) < 200:
            return line
    return "Untitled Course"


# ═══════════════════════════════════════════════════════
# STEP 2: DETECT SECTIONS
# ═══════════════════════════════════════════════════════

def detect_sections(raw_text: str, max_section_chars: int = 6000) -> list:
    """Detect and split document into logical sections.

    Uses heading patterns to identify section boundaries:
    - Numbered headings: "1.", "1.1", "2.", etc.
    - ALL CAPS headings
    - Bold/emphasized headings
    - Keyword headings: "Introduction", "Methods", "Results", etc.

    Args:
        raw_text: Full document text
        max_section_chars: Maximum characters per section

    Returns:
        List of dicts: [{"heading": str, "text": str}, ...]
    """
    lines = raw_text.split("\n")

    # Heading detection patterns
    heading_patterns = [
        # Numbered headings: "1.", "1.1", "2.3.1"
        re.compile(r"^\s*\d+\.[\d.]*\s+\S"),
        # ALL CAPS headings (at least 3 words)
        re.compile(r"^[A-Z][A-Z\s]{8,}$"),
        # Common academic section headings
        re.compile(
            r"^\s*(Abstract|Introduction|Background|Methods?|Methodology|"
            r"Results?|Discussion|Conclusion|Summary|References|"
            r"Literature Review|Related Work|Materials|Experimental|"
            r"Acknowledgements?|Appendix|Overview|Objectives?|"
            r"Findings|Analysis|Implications|Future Work|Limitations)\s*$",
            re.IGNORECASE,
        ),
        # Title-case headings (3+ words, each capitalized)
        re.compile(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){2,}$"),
    ]

    # Find section boundaries
    section_starts = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or len(stripped) < 3:
            continue
        for pattern in heading_patterns:
            if pattern.match(stripped):
                section_starts.append((i, stripped))
                break

    # If no sections detected, split by paragraph count
    if len(section_starts) < 2:
        return _split_by_paragraphs(raw_text, max_section_chars)

    # Build sections from boundaries
    sections = []
    for idx, (start_line, heading) in enumerate(section_starts):
        # Section text runs from this heading to the next heading (or end)
        if idx + 1 < len(section_starts):
            end_line = section_starts[idx + 1][0]
        else:
            end_line = len(lines)

        section_text = "\n".join(lines[start_line + 1 : end_line]).strip()

        if len(section_text) < 50:
            continue  # Skip empty/trivial sections

        sections.append({
            "heading": heading,
            "text": section_text,
        })

    # If sections are too large, further split them
    final_sections = []
    for section in sections:
        if len(section["text"]) > max_section_chars:
            sub_chunks = _split_by_paragraphs(section["text"], max_section_chars)
            for i, chunk in enumerate(sub_chunks):
                final_sections.append({
                    "heading": f"{section['heading']} (Part {i+1})" if len(sub_chunks) > 1 else section["heading"],
                    "text": chunk["text"],
                })
        else:
            final_sections.append(section)

    return final_sections if final_sections else _split_by_paragraphs(raw_text, max_section_chars)


def _split_by_paragraphs(text: str, max_chars: int = 6000) -> list:
    """Fallback: split text into chunks by paragraph boundaries."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    if not paragraphs:
        # Last resort: split by character count
        chunks = []
        for i in range(0, len(text), max_chars):
            chunks.append({
                "heading": f"Section {len(chunks) + 1}",
                "text": text[i : i + max_chars],
            })
        return chunks

    sections = []
    current_text = ""
    section_num = 1

    for para in paragraphs:
        if len(current_text) + len(para) > max_chars and current_text:
            sections.append({
                "heading": f"Section {section_num}",
                "text": current_text.strip(),
            })
            section_num += 1
            current_text = para
        else:
            current_text += "\n\n" + para if current_text else para

    if current_text.strip():
        sections.append({
            "heading": f"Section {section_num}",
            "text": current_text.strip(),
        })

    return sections


# ═══════════════════════════════════════════════════════
# STEP 3: GENERATE SECTION CONTENT (GROUNDED)
# ═══════════════════════════════════════════════════════

SECTION_SYSTEM_PROMPT = """You are an academic course content generator.
Generate detailed structured educational content ONLY from the provided section text.
Do not summarize the entire document.
Do not introduce external knowledge.
Do not add examples unless explicitly mentioned in the text.
Do not infer applications unless explicitly stated.
If something is not mentioned, leave it as an empty string or empty list."""

SECTION_USER_PROMPT = """Generate structured lesson content from the following section.
Education level: {education_level}

RULES:
- detailed_explanation: Teach ALL content from this section thoroughly. Cover every topic, process, term mentioned. 4-8 paragraphs.
- key_points: Only specific facts/points explicitly stated in the text.
- explicit_concepts: Only concepts/terms that appear in the text.
- mentioned_challenges: Only challenges/problems explicitly mentioned. Empty list if none mentioned.
- mentioned_applications: Only applications explicitly mentioned. Empty list if none mentioned.
- section_summary: 2-3 sentence summary using ONLY information from this section.

Section Text:
\"\"\"
{section_text}
\"\"\"

Return ONLY this JSON (no markdown, no explanation):
{{
  "section_title": "",
  "detailed_explanation": "",
  "key_points": [],
  "explicit_concepts": [],
  "mentioned_challenges": [],
  "mentioned_applications": [],
  "section_summary": ""
}}"""


def generate_section_content(
    section_text: str,
    section_heading: str,
    education_level: str = "UG",
) -> dict:
    """Generate structured lesson content for a single section.

    Args:
        section_text: Raw text of this section
        section_heading: Detected heading for this section
        education_level: School / UG / PG

    Returns:
        Dict with section_title, detailed_explanation, key_points, etc.
    """
    llm = _get_llm(max_tokens=3000, temperature=0.3)

    prompt = SECTION_USER_PROMPT.format(
        section_text=section_text[:6000],
        education_level=education_level,
    )

    try:
        response = llm.invoke([
            {"role": "system", "content": SECTION_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ])
        parsed = _parse_json_response(response.content)

        return {
            "section_title": parsed.get("section_title", section_heading),
            "detailed_explanation": parsed.get("detailed_explanation", section_text[:2000]),
            "key_points": parsed.get("key_points", []),
            "explicit_concepts": parsed.get("explicit_concepts", []),
            "mentioned_challenges": parsed.get("mentioned_challenges", []),
            "mentioned_applications": parsed.get("mentioned_applications", []),
            "section_summary": parsed.get("section_summary", ""),
        }
    except Exception as e:
        print(f"  ⚠️ Section generation failed: {e}")
        return {
            "section_title": section_heading,
            "detailed_explanation": section_text[:2000],
            "key_points": [],
            "explicit_concepts": [],
            "mentioned_challenges": [],
            "mentioned_applications": [],
            "section_summary": "",
        }


# ═══════════════════════════════════════════════════════
# FULL PIPELINE
# ═══════════════════════════════════════════════════════

def generate_course_from_text(document_text: str, education_level: str = "UG") -> dict:
    """Full grounded course generation pipeline.

    Pipeline:
      1. Extract metadata (title, summary, domain)
      2. Detect sections
      3. Generate detailed content per section
      4. Collect all concepts

    Args:
        document_text: Full raw text from PDF
        education_level: School / UG / PG

    Returns:
        Structured course dict with metadata + sections
    """
    text = document_text.strip()
    print(f"📄 Processing document: {len(text)} characters")

    # Step 1: Extract metadata
    print("  🔍 Step 1: Extracting course metadata...")
    metadata = extract_course_metadata(text)
    print(f"  ✅ Title: {metadata['title']}")

    # Step 2: Detect sections
    print("  🔍 Step 2: Detecting sections...")
    sections = detect_sections(text)
    print(f"  ✅ Found {len(sections)} sections")

    # Step 3: Generate content per section
    print("  🔍 Step 3: Generating section content...")
    generated_sections = []
    all_concepts = []

    for i, section in enumerate(sections):
        print(f"    📝 Section {i+1}/{len(sections)}: {section['heading'][:50]}...")
        content = generate_section_content(
            section_text=section["text"],
            section_heading=section["heading"],
            education_level=education_level,
        )
        content["source_text"] = section["text"]
        generated_sections.append(content)
        all_concepts.extend(content.get("explicit_concepts", []))
        print(f"    ✅ Generated ({len(content['detailed_explanation'])} chars, {len(content['explicit_concepts'])} concepts)")

    # Deduplicate concepts
    unique_concepts = list(dict.fromkeys(all_concepts))

    return {
        "title": metadata["title"],
        "summary": metadata["summary"],
        "main_topic": metadata["main_topic"],
        "domain": metadata["domain"],
        "difficulty": "Intermediate",
        "sections": generated_sections,
        "concepts": unique_concepts,
        "keywords": metadata.get("keywords_from_text", []),
    }
