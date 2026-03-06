"""
Knowledge Card Generator
========================
Generates AI knowledge cards for materials using Claude.

Card sections (per architecture doc):
  - what_it_is
  - key_properties      (with ranges, grounded in papers)
  - current_applications
  - fabrication_compat  (which methods work and why)
  - frontier            (last 12 months, grounded in papers only)
  - open_problems
  - limitations
  - key_papers          (linked by PMID)

Confidence: flagged AI_GENERATED until human-verified.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

CARD_SYSTEM = """You are a biomaterials scientist writing a structured knowledge card
for a research analysis tool. Be precise and factual. Use quantitative ranges where
available. Do not add information not present in the provided context.
Return only valid JSON — no markdown, no preamble."""

CARD_PROMPT = """Generate a knowledge card for the biomaterial: {name}

Material class: {material_class}

Recent papers (use these as your primary evidence source):
{papers_text}

Existing known properties:
{known_properties}

Project context: {project_context}

Return a JSON object with exactly these keys:
{{
  "what_it_is": "2-3 sentence definition and overview.",
  "key_properties": {{
    "property_name": "value or range with units",
    ...
  }},
  "current_applications": ["application 1", "application 2", ...],
  "fabrication_compatibility": {{
    "method_name": "Excellent | Good | Moderate | Poor | Not applicable — one sentence reason",
    ...
  }},
  "frontier_developments": [
    "Specific recent development grounded in provided papers only",
    ...
  ],
  "open_problems": ["Problem 1", "Problem 2", ...],
  "limitations": ["Limitation 1", "Limitation 2", ...],
  "key_paper_pmids": ["pmid1", "pmid2", ...],
  "confidence": "high | medium | low"
}}"""


def generate_knowledge_card(material_name: str,
                             material_class: str,
                             recent_papers: Optional[List[Dict]] = None,
                             known_properties: Optional[Dict] = None,
                             project_context: str = "",
                             client=None) -> Dict:
    """
    Generate an AI knowledge card for a material.

    Args:
        material_name:    e.g. "GelMA"
        material_class:   e.g. "polymers"
        recent_papers:    list of paper dicts from PubMed search
        known_properties: existing properties dict from materials DB
        project_context:  e.g. "retinal tissue engineering"
        client:           LLMClient (uses singleton if None)

    Returns:
        Card dict — all fields present, confidence tier set.
    """
    if client is None:
        from ai_engine.llm_client import get_client
        client = get_client()

    # Format papers for context
    papers_text = _format_papers(recent_papers or [])

    # Format known properties
    props_text = ""
    if known_properties:
        props_text = "\n".join(f"  {k}: {v}"
                               for k, v in known_properties.items())
    if not props_text:
        props_text = "None on record yet."

    prompt = CARD_PROMPT.format(
        name             = material_name,
        material_class   = material_class,
        papers_text      = papers_text or "No recent papers retrieved.",
        known_properties = props_text,
        project_context  = project_context or "general biomaterials research",
    )

    try:
        card = client.complete_json(prompt=prompt, system=CARD_SYSTEM,
                                    max_tokens=2000)
        card["material_name"]  = material_name
        card["material_class"] = material_class
        card["ai_generated"]   = True
        card["human_verified"] = False
        return card

    except Exception as e:
        logger.error(f"Knowledge card generation failed for {material_name}: {e}")
        return _empty_card(material_name, material_class, error=str(e))


def format_card_markdown(card: Dict) -> str:
    """
    Convert a knowledge card dict to readable markdown for display.
    """
    lines = []
    name = card.get("material_name", "Unknown")
    lines.append(f"## {name}\n")

    if card.get("error"):
        lines.append(f"Card generation failed: {card['error']}")
        return "\n".join(lines)

    ai_flag = "AI-generated" if card.get("ai_generated") else "Human-verified"
    conf    = card.get("confidence", "unknown")
    lines.append(f"*{ai_flag} · Confidence: {conf}*\n")

    what = card.get("what_it_is", "")
    if what:
        lines.append(f"{what}\n")

    props = card.get("key_properties", {})
    if props:
        lines.append("**Key Properties:**")
        for k, v in props.items():
            lines.append(f"• {k}: {v}")
        lines.append("")

    apps = card.get("current_applications", [])
    if apps:
        lines.append("**Applications:**")
        for a in apps:
            lines.append(f"• {a}")
        lines.append("")

    fab = card.get("fabrication_compatibility", {})
    if fab:
        lines.append("**Fabrication Compatibility:**")
        for method, rating in fab.items():
            lines.append(f"• {method}: {rating}")
        lines.append("")

    frontier = card.get("frontier_developments", [])
    if frontier:
        lines.append("**Frontier Developments (recent papers):**")
        for f in frontier:
            lines.append(f"• {f}")
        lines.append("")

    problems = card.get("open_problems", [])
    if problems:
        lines.append("**Open Problems:**")
        for p in problems:
            lines.append(f"• {p}")
        lines.append("")

    limitations = card.get("limitations", [])
    if limitations:
        lines.append("**Limitations:**")
        for l in limitations:
            lines.append(f"• {l}")
        lines.append("")

    pmids = card.get("key_paper_pmids", [])
    if pmids:
        links = [f"[{pmid}](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)"
                 for pmid in pmids[:5]]
        lines.append("**Key Papers:** " + " · ".join(links))

    return "\n".join(lines)


def _format_papers(papers: List[Dict]) -> str:
    """Format paper list into a context block for the prompt."""
    if not papers:
        return ""
    chunks = []
    for p in papers[:10]:   # cap at 10 to stay within context
        title    = p.get("title", "")
        abstract = (p.get("abstract") or "")[:400]
        year     = p.get("year") or p.get("publication_date", "")
        pmid     = p.get("pmid", "")
        chunks.append(f"[PMID:{pmid} {year}] {title}\n{abstract}")
    return "\n\n".join(chunks)


def _empty_card(name: str, material_class: str,
                error: str = "") -> Dict:
    return {
        "material_name":           name,
        "material_class":          material_class,
        "what_it_is":              "",
        "key_properties":          {},
        "current_applications":    [],
        "fabrication_compatibility":{},
        "frontier_developments":   [],
        "open_problems":           [],
        "limitations":             [],
        "key_paper_pmids":         [],
        "confidence":              "low",
        "ai_generated":            True,
        "human_verified":          False,
        "error":                   error,
    }