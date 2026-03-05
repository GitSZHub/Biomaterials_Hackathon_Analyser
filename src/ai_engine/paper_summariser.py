"""
Paper Summariser
================
Takes a paper dict (title + abstract, or full text if PDF available)
and returns a structured summary via Claude.

Output sections (all grounded in the paper — no hallucination):
  - one_liner:      single sentence for busy readers
  - key_findings:   list of concrete findings with numbers where present
  - material:       material studied (if any)
  - cell_model:     cell model or organism used
  - limitations:    stated or implied limitations
  - relevance:      why this matters for biomaterials / tissue engineering

Used by:
  - literature_tab.py  (AI Summary button)
  - briefing_gen.py    (auto-summarise flagged papers)
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

SUMMARY_SYSTEM = """You are a biomaterials and tissue engineering research analyst.
You read scientific abstracts and extract structured, factual summaries.
You never add information not present in the text.
You always return valid JSON only — no markdown, no explanation outside the JSON."""

SUMMARY_PROMPT = """Analyse this scientific paper and return a JSON object with these exact keys:

{{
  "one_liner": "One sentence: what was done and the main result.",
  "key_findings": ["Finding 1 with specific numbers if available", "Finding 2", ...],
  "material": "Primary material studied, or null",
  "cell_model": "Cell line, primary cells, organoid, or organism used, or null",
  "tissue_target": "Target tissue or application, or null",
  "limitations": ["Limitation 1", "Limitation 2"],
  "relevance": "1-2 sentences on why this matters for biomaterials research.",
  "confidence": "high | medium | low based on abstract completeness"
}}

Paper title: {title}

Abstract:
{abstract}"""


def summarise_paper(paper: Dict[str, Any],
                    client=None) -> Dict[str, Any]:
    """
    Summarise a single paper dict.

    Args:
        paper:  dict with at least 'title' and 'abstract' keys
        client: LLMClient instance (uses singleton if None)

    Returns:
        dict with summary fields, or error dict if failed
    """
    if client is None:
        from ai_engine.llm_client import get_client
        client = get_client()

    title    = paper.get("title", "Unknown title")
    abstract = paper.get("abstract", "")

    if not abstract:
        return {
            "one_liner":    "Abstract not available.",
            "key_findings": [],
            "material":     None,
            "cell_model":   None,
            "tissue_target":None,
            "limitations":  [],
            "relevance":    "Cannot summarise without abstract.",
            "confidence":   "low",
            "error":        "no_abstract"
        }

    prompt = SUMMARY_PROMPT.format(
        title    = title,
        abstract = abstract[:3000]   # cap at ~3000 chars to stay within context
    )

    try:
        result = client.complete_json(prompt=prompt, system=SUMMARY_SYSTEM)
        # Ensure all expected keys are present
        defaults = {
            "one_liner": "", "key_findings": [], "material": None,
            "cell_model": None, "tissue_target": None,
            "limitations": [], "relevance": "", "confidence": "medium"
        }
        defaults.update(result)
        return defaults

    except Exception as e:
        logger.error(f"Summarise failed for '{title}': {e}")
        return {
            "one_liner":    "Summary failed.",
            "key_findings": [],
            "material":     None,
            "cell_model":   None,
            "tissue_target":None,
            "limitations":  [],
            "relevance":    "",
            "confidence":   "low",
            "error":        str(e)
        }


def format_summary_markdown(summary: Dict[str, Any]) -> str:
    """
    Convert a summary dict to readable markdown for display in the UI.
    """
    lines = []

    if summary.get("error") and summary["error"] != "no_abstract":
        lines.append(f"⚠️ **Summary error:** {summary['error']}")
        return "\n".join(lines)

    one_liner = summary.get("one_liner", "")
    if one_liner:
        lines.append(f"**{one_liner}**\n")

    if summary.get("material"):
        lines.append(f"**Material:** {summary['material']}")
    if summary.get("cell_model"):
        lines.append(f"**Model:** {summary['cell_model']}")
    if summary.get("tissue_target"):
        lines.append(f"**Tissue target:** {summary['tissue_target']}")

    findings = summary.get("key_findings", [])
    if findings:
        lines.append("\n**Key findings:**")
        for f in findings:
            lines.append(f"• {f}")

    limitations = summary.get("limitations", [])
    if limitations:
        lines.append("\n**Limitations:**")
        for l in limitations:
            lines.append(f"• {l}")

    relevance = summary.get("relevance", "")
    if relevance:
        lines.append(f"\n**Relevance:** {relevance}")

    confidence = summary.get("confidence", "")
    if confidence:
        lines.append(f"\n*Confidence: {confidence}*")

    return "\n".join(lines)