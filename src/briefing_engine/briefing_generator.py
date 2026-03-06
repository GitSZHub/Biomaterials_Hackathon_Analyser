"""
Briefing Generator
==================
Generates section-by-section Technical or Executive briefings using Claude.

Two modes:
  - "technical":  For R&D teammates — scientific rigour, data gaps, next experiments
  - "executive":  For investors / partners — market opportunity, pathway, risks, ask

Each section is generated in a separate Claude call for best quality and
streaming-like UX (the UI can render each section as it arrives).

Prompts are designed to be visible and editable by the user before generation.

Usage:
    from briefing_engine.briefing_generator import BriefingGenerator, BriefingSection

    gen = BriefingGenerator()
    sections = gen.get_sections("technical")

    for section in sections:
        text = gen.generate_section(section.key, context, mode="technical")
        print(text)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Iterator, List, Optional

from .context_assembler import BriefingContext

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a world-class biomaterials scientist and medical device strategist. "
    "You write with precision, authority, and clarity. "
    "Avoid speculation beyond the evidence provided. "
    "When data is missing, note the gap explicitly rather than filling it with assumptions. "
    "Use SI units and standard biomaterials terminology."
)


@dataclass
class BriefingSection:
    key:          str
    title:        str
    mode:         str           # "technical" / "executive" / "both"
    description:  str           # shown to user in checklist
    default_on:   bool = True


# ── Section definitions ────────────────────────────────────────────────────────

TECHNICAL_SECTIONS: List[BriefingSection] = [
    BriefingSection("tech_overview",    "Project Overview & Scientific Rationale",
                    "technical", "Scientific background, hypothesis, and design rationale."),
    BriefingSection("tech_materials",   "Material Characterisation & Properties",
                    "technical", "Chemical composition, mechanical properties, degradation profile."),
    BriefingSection("tech_biocompat",   "Biocompatibility & Toxicology",
                    "technical", "ISO 10993 status, cytotoxicity data, AOP flags."),
    BriefingSection("tech_bio",         "Biological Response & Transcriptomics",
                    "technical", "DEG analysis, pathway enrichment, key gene expression data."),
    BriefingSection("tech_drug",        "Drug Delivery Profile",
                    "technical", "Release kinetics, PK modelling, in vitro/in vivo correlation.",
                    default_on=False),
    BriefingSection("tech_regulatory",  "Regulatory Classification & Pathway",
                    "technical", "FDA/EU device class, scenario, ISO 10993 test matrix."),
    BriefingSection("tech_roadmap",     "Experimental Roadmap & DBTL Status",
                    "technical", "Current stage, completed iterations, next planned experiments."),
    BriefingSection("tech_literature",  "Literature Evidence Base",
                    "technical", "Key papers, conflicting findings, evidence gaps."),
    BriefingSection("tech_gaps",        "Knowledge Gaps & Recommended Next Steps",
                    "technical", "Critical data gaps and the highest-priority experiments to address them."),
    BriefingSection("tech_researchers", "Researcher Network & Collaboration",
                    "technical", "Key collaborators, KOLs, and open collaboration opportunities.",
                    default_on=False),
]

EXECUTIVE_SECTIONS: List[BriefingSection] = [
    BriefingSection("exec_summary",     "Executive Summary",
                    "executive", "One-paragraph synthesis covering all key points."),
    BriefingSection("exec_problem",     "Problem & Unmet Clinical Need",
                    "executive", "Epidemiology, current standard of care, limitations."),
    BriefingSection("exec_solution",    "Our Solution & Differentiation",
                    "executive", "Technology description, key advantages over alternatives."),
    BriefingSection("exec_market",      "Market Opportunity",
                    "executive", "Market size, CAGR, addressable segments, reimbursement."),
    BriefingSection("exec_regulatory",  "Regulatory Pathway & Timeline",
                    "executive", "Classification, key submissions, milestones, de-risking events."),
    BriefingSection("exec_competitive", "Competitive Landscape",
                    "executive", "Key competitors, differentiation, freedom to operate."),
    BriefingSection("exec_business",    "Business Model & Commercialisation",
                    "executive", "Revenue model, go-to-market, partnership strategy."),
    BriefingSection("exec_risks",       "Key Risks & Mitigation",
                    "executive", "Top 3-5 risks with mitigation strategy for each."),
    BriefingSection("exec_team",        "Team & Partnerships",
                    "executive", "Key expertise, advisors, clinical and industry partners.",
                    default_on=False),
    BriefingSection("exec_ask",         "Funding Ask & Key Milestones",
                    "executive", "Investment required, use of funds, value inflection milestones.",
                    default_on=False),
]


# ── Generator ──────────────────────────────────────────────────────────────────

class BriefingGenerator:

    def get_sections(self, mode: str) -> List[BriefingSection]:
        return TECHNICAL_SECTIONS if mode == "technical" else EXECUTIVE_SECTIONS

    def generate_section(
        self,
        section_key: str,
        context: BriefingContext,
        mode: str = "technical",
        extra_instructions: str = "",
    ) -> str:
        """
        Generate one briefing section. Returns Markdown-formatted text.
        Raises LLMError if the AI call fails.
        """
        prompt = self._build_section_prompt(section_key, context, mode, extra_instructions)
        from ai_engine.llm_client import LLMClient
        client = LLMClient()
        return client.complete(prompt=prompt, system=SYSTEM_PROMPT, max_tokens=800, temperature=0.25)

    def generate_all(
        self,
        context: BriefingContext,
        mode: str,
        section_keys: List[str],
        on_section_done: Optional[Callable[[str, str], None]] = None,
    ) -> str:
        """
        Generate all selected sections sequentially.
        Calls on_section_done(section_key, text) after each section — for streaming UI.
        Returns the assembled full Markdown document.
        """
        parts = [f"# {context.project_name or 'Biomaterials Project'} — "
                 f"{'Technical Briefing' if mode == 'technical' else 'Executive Briefing'}\n"]
        sections = {s.key: s for s in self.get_sections(mode)}

        for key in section_keys:
            section = sections.get(key)
            if section is None:
                continue
            try:
                text = self.generate_section(key, context, mode)
                formatted = f"## {section.title}\n\n{text}\n"
                parts.append(formatted)
                if on_section_done:
                    on_section_done(key, formatted)
            except Exception as e:
                error_text = f"## {section.title}\n\n*[Generation failed: {e}]*\n"
                parts.append(error_text)
                logger.error("Section %s failed: %s", key, e)
                if on_section_done:
                    on_section_done(key, error_text)

        return "\n".join(parts)

    def build_visible_prompt(self, section_key: str, context: BriefingContext,
                              mode: str = "technical") -> str:
        """Return the full prompt that will be sent — for the editable prompt pane."""
        return self._build_section_prompt(section_key, context, mode, "")

    # ── Prompt builders ────────────────────────────────────────────────────────

    def _build_section_prompt(self, key: str, ctx: BriefingContext,
                               mode: str, extra: str) -> str:
        """Dispatch to the appropriate section prompt builder."""
        builders = {
            # Technical
            "tech_overview":    self._tech_overview,
            "tech_materials":   self._tech_materials,
            "tech_biocompat":   self._tech_biocompat,
            "tech_bio":         self._tech_bio,
            "tech_drug":        self._tech_drug,
            "tech_regulatory":  self._tech_regulatory,
            "tech_roadmap":     self._tech_roadmap,
            "tech_literature":  self._tech_literature,
            "tech_gaps":        self._tech_gaps,
            "tech_researchers": self._tech_researchers,
            # Executive
            "exec_summary":     self._exec_summary,
            "exec_problem":     self._exec_problem,
            "exec_solution":    self._exec_solution,
            "exec_market":      self._exec_market,
            "exec_regulatory":  self._exec_regulatory,
            "exec_competitive": self._exec_competitive,
            "exec_business":    self._exec_business,
            "exec_risks":       self._exec_risks,
            "exec_team":        self._exec_team,
            "exec_ask":         self._exec_ask,
        }
        fn = builders.get(key)
        if fn is None:
            return f"Write a briefing section about '{key}' for this project:\n\n{ctx.to_full_context()}"
        base = fn(ctx)
        if extra.strip():
            base += f"\n\nAdditional instructions: {extra}"
        return base

    @staticmethod
    def _context_header(ctx: BriefingContext) -> str:
        return f"PROJECT DATA:\n{ctx.to_full_context()}\n\n"

    # ── Technical section prompts ──────────────────────────────────────────────

    def _tech_overview(self, ctx: BriefingContext) -> str:
        return (
            self._context_header(ctx) +
            "Write the 'Project Overview & Scientific Rationale' section of a Technical Briefing. "
            "Cover: (1) the clinical problem being addressed, (2) the scientific hypothesis, "
            "(3) why this material/approach was chosen over alternatives, "
            "(4) the key innovation. 200-300 words. Markdown format with no heading (it will be added)."
        )

    def _tech_materials(self, ctx: BriefingContext) -> str:
        return (
            self._context_header(ctx) +
            "Write the 'Material Characterisation & Properties' section. "
            "Cover: composition, key physicochemical properties (porosity, mechanical, degradation), "
            "fabrication method if known, and any outstanding characterisation gaps. "
            "200-300 words. Markdown."
        )

    def _tech_biocompat(self, ctx: BriefingContext) -> str:
        return (
            self._context_header(ctx) +
            "Write the 'Biocompatibility & Toxicology' section. "
            "Cover: ISO 10993 test status, cytotoxicity results if available, any toxicology flags, "
            "and what additional testing is still required before regulatory submission. "
            "Be specific about which ISO 10993 parts are complete vs outstanding. "
            "200-300 words. Markdown."
        )

    def _tech_bio(self, ctx: BriefingContext) -> str:
        return (
            self._context_header(ctx) +
            "Write the 'Biological Response & Transcriptomics' section. "
            "Cover: GEO datasets used, key differentially expressed genes, enriched pathways, "
            "and what the transcriptomic data tells us about the material-cell interaction. "
            f"{'Note prominently: Matrigel artefact genes may confound results. ' if ctx.matrigel_warning else ''}"
            "If no transcriptomic data is available, note what data would be most valuable and why. "
            "200-300 words. Markdown."
        )

    def _tech_drug(self, ctx: BriefingContext) -> str:
        return (
            self._context_header(ctx) +
            "Write the 'Drug Delivery Profile' section. "
            "Cover: drug(s) loaded, release kinetics (burst + sustained phase), PK model used, "
            "predicted in vivo AUC/Cmax at target tissue, and in vitro-in vivo correlation limitations. "
            "200-300 words. Markdown."
        )

    def _tech_regulatory(self, ctx: BriefingContext) -> str:
        return (
            self._context_header(ctx) +
            "Write the 'Regulatory Classification & Pathway' section. "
            "Cover: FDA class, EU MDR class, regulatory scenario (A/B/C/D), "
            "the most critical regulatory milestone to achieve next, "
            "and any specific ISO 10993 tests that are still outstanding. "
            "Be factual and specific — avoid vague statements. 200-300 words. Markdown."
        )

    def _tech_roadmap(self, ctx: BriefingContext) -> str:
        return (
            self._context_header(ctx) +
            "Write the 'Experimental Roadmap & DBTL Status' section. "
            "Cover: the current experimental stage, completed DBTL iterations and key learnings, "
            "the next planned experiment and its go/no-go criterion, "
            "and the estimated time to first in vivo data. 200-300 words. Markdown."
        )

    def _tech_literature(self, ctx: BriefingContext) -> str:
        return (
            self._context_header(ctx) +
            "Write the 'Literature Evidence Base' section. "
            "Cover: the key papers supporting this approach, any contradictory findings in the literature, "
            "the quality of evidence (RCT vs in vitro), and what systematic reviews or meta-analyses exist. "
            "Cite the papers listed in the project data. 200-300 words. Markdown."
        )

    def _tech_gaps(self, ctx: BriefingContext) -> str:
        return (
            self._context_header(ctx) +
            "Write the 'Knowledge Gaps & Recommended Next Steps' section. "
            "Identify the 3-5 most critical data gaps. For each gap, specify: "
            "(1) what is unknown, (2) why it matters for the programme, "
            "(3) the specific experiment or study that would address it, "
            "(4) estimated resource requirement (weeks + cost tier: low/medium/high). "
            "Be concrete and actionable. 300-400 words. Markdown with a sub-heading per gap."
        )

    def _tech_researchers(self, ctx: BriefingContext) -> str:
        return (
            self._context_header(ctx) +
            "Write the 'Researcher Network & Collaboration Opportunities' section. "
            "Cover: key collaborators and their specific expertise, "
            "any KOLs who have published in this space, "
            "and open collaboration opportunities (co-applications, visiting fellowships, etc.). "
            "150-200 words. Markdown."
        )

    # ── Executive section prompts ──────────────────────────────────────────────

    def _exec_summary(self, ctx: BriefingContext) -> str:
        return (
            self._context_header(ctx) +
            "Write the 'Executive Summary' for an investor-facing briefing. "
            "In ONE paragraph of 6-8 sentences, cover: the problem, the solution, "
            "the market size, the regulatory pathway, the stage of development, "
            "and the key ask. Write in a compelling but factually grounded style. "
            "Markdown (no heading)."
        )

    def _exec_problem(self, ctx: BriefingContext) -> str:
        return (
            self._context_header(ctx) +
            "Write the 'Problem & Unmet Clinical Need' section for an investor briefing. "
            "Cover: epidemiology (incidence, prevalence), economic burden, "
            "current standard of care and its limitations, "
            "and why no existing solution adequately addresses this need. "
            "Use specific numbers where available. 200-250 words. Markdown."
        )

    def _exec_solution(self, ctx: BriefingContext) -> str:
        return (
            self._context_header(ctx) +
            "Write the 'Our Solution & Differentiation' section for an investor briefing. "
            "Cover: what the technology is (plain language), the key innovation, "
            "the 2-3 most compelling differentiators vs competitors and current SoC, "
            "and the strongest piece of supporting data. 200-250 words. Markdown."
        )

    def _exec_market(self, ctx: BriefingContext) -> str:
        return (
            self._context_header(ctx) +
            "Write the 'Market Opportunity' section for an investor briefing. "
            "Cover: TAM/SAM/SOM with specific numbers, CAGR, "
            "key growth drivers, reimbursement landscape, "
            "and the most attractive initial market beachhead. 200-250 words. Markdown."
        )

    def _exec_regulatory(self, ctx: BriefingContext) -> str:
        return (
            self._context_header(ctx) +
            "Write the 'Regulatory Pathway & Timeline' section for an investor briefing. "
            "Cover: regulatory classification, key submissions, "
            "major value inflection milestones (what events will increase valuation), "
            "and how the regulatory strategy de-risks investment. "
            "Use a timeline format where possible. 200-250 words. Markdown."
        )

    def _exec_competitive(self, ctx: BriefingContext) -> str:
        return (
            self._context_header(ctx) +
            "Write the 'Competitive Landscape' section for an investor briefing. "
            "Cover: named competitors and their stage, "
            "why our approach is superior on the dimensions that matter to payers and surgeons, "
            "and any freedom-to-operate considerations. 200-250 words. Markdown."
        )

    def _exec_business(self, ctx: BriefingContext) -> str:
        return (
            self._context_header(ctx) +
            "Write the 'Business Model & Commercialisation Strategy' section for an investor briefing. "
            "Cover: revenue model (device sales / licensing / royalties), "
            "go-to-market strategy (direct / distributor / partnership), "
            "target customer and procurement pathway (GPO / hospital VAC / national tender), "
            "and the most likely exit route (trade sale / IPO / licensing). 200-250 words. Markdown."
        )

    def _exec_risks(self, ctx: BriefingContext) -> str:
        return (
            self._context_header(ctx) +
            "Write the 'Key Risks & Mitigation' section for an investor briefing. "
            "Identify the 4-5 most significant risks (scientific, regulatory, commercial, execution). "
            "For each risk: state the risk in one sentence, the probability (high/medium/low), "
            "the impact if it materialises, and the mitigation strategy already in place or planned. "
            "Use a table or structured list format. 250-300 words. Markdown."
        )

    def _exec_team(self, ctx: BriefingContext) -> str:
        return (
            self._context_header(ctx) +
            "Write the 'Team & Partnerships' section for an investor briefing. "
            "Cover: key team expertise (do not invent names — note gaps if team data is unavailable), "
            "scientific advisory board, clinical development partners, "
            "and manufacturing/CDMO relationships. 150-200 words. Markdown."
        )

    def _exec_ask(self, ctx: BriefingContext) -> str:
        return (
            self._context_header(ctx) +
            "Write the 'Funding Ask & Key Milestones' section for an investor briefing. "
            "Cover: the funding amount being sought (use 'undisclosed' if not in project data), "
            "use of funds broken down by category, "
            "and the 3-5 key milestones this funding will deliver with expected timelines. "
            "Tie milestones explicitly to regulatory and clinical de-risking events. "
            "200-250 words. Markdown."
        )
