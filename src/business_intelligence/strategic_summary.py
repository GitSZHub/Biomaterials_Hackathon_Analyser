"""
Strategic Summary Engine
========================
Claude synthesises across all business intelligence quadrants (market,
stakeholders, SWOT, regulatory pathway) and produces a concise
strategic insight paragraph tailored to a chosen audience lens.

Audiences:
  - technical:    R&D team focus — scientific differentiation, gaps, experiments needed
  - investor:     VC/BD focus — market size, IP, regulatory risk, exit pathway
  - clinical:     Clinical KOL focus — unmet need, evidence base, procedural fit
  - regulatory:   Regulatory affairs focus — pathway, timeline, risk flags
  - executive:    C-suite summary — balanced view across all quadrants

Usage:
    from business_intelligence.strategic_summary import StrategicSummaryEngine, SynthesisContext

    engine = StrategicSummaryEngine()
    result = engine.synthesise(context)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SynthesisContext:
    """All inputs gathered from the BI module for Claude to synthesise."""
    project_name:       str
    tissue:             str
    scenario:           str
    audience:           str = "executive"       # see module docstring
    market_segment:     str = ""                # MarketSegment.name
    market_size:        str = ""                # USD billions
    market_cagr:        str = ""
    swot_text:          str = ""                # from SWOTAnalysis.to_context_string()
    regulatory_pathway: str = ""                # RegulatoryPathway.pathway_name
    regulatory_timeline:str = ""
    regulatory_risks:   str = ""
    key_stakeholders:   str = ""                # comma-separated names
    competitive_context:str = ""                # top competitors + stage
    user_notes:         str = ""                # freeform notes from user


@dataclass
class StrategyResult:
    insight:        str            # one concise paragraph
    key_actions:    list = field(default_factory=list)   # top 3-5 recommended next actions
    watch_list:     list = field(default_factory=list)   # risks to monitor
    audience:       str = "executive"
    success:        bool = True
    error:          Optional[str] = None


# ── Engine ─────────────────────────────────────────────────────────────────────

class StrategicSummaryEngine:

    def synthesise(self, context: SynthesisContext) -> StrategyResult:
        prompt = self._build_prompt(context)
        try:
            from ai_engine.llm_client import LLMClient
            client = LLMClient()
            raw = client.complete(prompt, max_tokens=900)
            return self._parse_response(raw, context.audience)
        except ImportError:
            return StrategyResult(
                insight="AI engine not available — install and configure the LLM client.",
                success=False,
                error="LLMClient not importable",
            )
        except Exception as e:
            logger.error("StrategicSummaryEngine error: %s", e)
            return StrategyResult(insight="", success=False, error=str(e))

    # ── Prompt builder ─────────────────────────────────────────────────────────

    @staticmethod
    def _build_prompt(ctx: SynthesisContext) -> str:
        audience_instructions = {
            "technical": (
                "Focus on scientific differentiation, key experimental gaps, "
                "and what data needs to be generated next to de-risk the programme."
            ),
            "investor": (
                "Focus on market opportunity size, competitive positioning, IP defensibility, "
                "regulatory risk-to-reward, and the most likely exit pathway and timeline."
            ),
            "clinical": (
                "Focus on the unmet clinical need addressed, how the technology fits into "
                "existing surgical workflow, and what clinical evidence would be most persuasive "
                "to adopting clinicians."
            ),
            "regulatory": (
                "Focus on the regulatory classification, key submissions required, "
                "the most significant regulatory risks, and the recommended strategy "
                "to minimise time to approval."
            ),
            "executive": (
                "Provide a balanced executive summary covering market opportunity, "
                "competitive differentiation, regulatory pathway, key risks, "
                "and the single most important strategic priority for the next 12 months."
            ),
        }
        instruction = audience_instructions.get(ctx.audience, audience_instructions["executive"])

        sections = [
            f"You are a senior biomaterials commercialisation strategist advising on a {ctx.tissue} "
            f"tissue engineering project called '{ctx.project_name}'.",
            f"\nAudience: {ctx.audience.upper()} — {instruction}",
            "\n--- CONTEXT ---",
        ]

        if ctx.market_segment:
            sections.append(
                f"Market: {ctx.market_segment} | Size: ${ctx.market_size}B | CAGR: {ctx.market_cagr}%/yr"
            )
        if ctx.regulatory_pathway:
            sections.append(
                f"Regulatory pathway: {ctx.regulatory_pathway} | Timeline: {ctx.regulatory_timeline}"
            )
        if ctx.regulatory_risks:
            sections.append(f"Regulatory risks: {ctx.regulatory_risks}")
        if ctx.key_stakeholders:
            sections.append(f"Key stakeholders: {ctx.key_stakeholders}")
        if ctx.competitive_context:
            sections.append(f"Competitive landscape:\n{ctx.competitive_context}")
        if ctx.swot_text:
            sections.append(f"\nSWOT Analysis:\n{ctx.swot_text}")
        if ctx.user_notes:
            sections.append(f"\nAdditional notes from team:\n{ctx.user_notes}")

        sections.append(
            "\n--- TASK ---\n"
            "Provide:\n"
            "1. INSIGHT: One concise strategic paragraph (5-7 sentences) for the stated audience.\n"
            "2. KEY ACTIONS: Exactly 3-5 numbered recommended next actions (one line each).\n"
            "3. WATCH LIST: Exactly 2-3 risks to actively monitor (one line each).\n\n"
            "Format your response EXACTLY as:\n"
            "INSIGHT:\n<paragraph>\n\n"
            "KEY ACTIONS:\n1. <action>\n2. <action>\n...\n\n"
            "WATCH LIST:\n1. <risk>\n2. <risk>\n..."
        )

        return "\n".join(sections)

    @staticmethod
    def _parse_response(raw: str, audience: str) -> StrategyResult:
        insight = ""
        actions = []
        watch   = []

        section = None
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.startswith("INSIGHT:"):
                section = "insight"
                remainder = stripped[len("INSIGHT:"):].strip()
                if remainder:
                    insight = remainder
            elif stripped.startswith("KEY ACTIONS:"):
                section = "actions"
            elif stripped.startswith("WATCH LIST:"):
                section = "watch"
            elif section == "insight" and stripped:
                insight = (insight + " " + stripped).strip() if insight else stripped
            elif section == "actions" and stripped:
                # Strip leading "1. " numbering
                text = stripped.lstrip("0123456789. ").strip()
                if text:
                    actions.append(text)
            elif section == "watch" and stripped:
                text = stripped.lstrip("0123456789. ").strip()
                if text:
                    watch.append(text)

        if not insight:
            insight = raw.strip()

        return StrategyResult(
            insight=insight,
            key_actions=actions,
            watch_list=watch,
            audience=audience,
            success=True,
        )
