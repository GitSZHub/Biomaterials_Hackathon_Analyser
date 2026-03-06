"""
Briefing Context Assembler
===========================
Gathers data from every module in the application and assembles it into
a structured BriefingContext object ready for Claude to synthesise into
a Technical or Executive briefing.

Each module is harvested independently with full try/except isolation —
if a module has no data or fails to import, its section is simply empty.
The briefing still works with partial data.

Usage:
    from briefing_engine.context_assembler import ContextAssembler, BriefingContext
    ctx = ContextAssembler().assemble()
    print(ctx.to_section_text("regulatory"))
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Context data class ─────────────────────────────────────────────────────────

@dataclass
class BriefingContext:
    """
    Flat structured container for all module data.
    Each field is a string or list of strings ready for prompt injection.
    Empty fields mean the module had no data.
    """

    # Project
    project_name:       str = ""
    project_tissue:     str = ""
    project_aim:        str = ""
    project_keywords:   List[str] = field(default_factory=list)
    project_description:str = ""
    project_timeline:   str = ""
    project_budget:     str = ""

    # Literature
    paper_count:        int = 0
    top_papers:         List[str] = field(default_factory=list)   # "Author (year) — Title"
    key_findings:       List[str] = field(default_factory=list)

    # Materials
    materials_named:    List[str] = field(default_factory=list)
    material_highlights:List[str] = field(default_factory=list)

    # Bio / transcriptomics
    geo_datasets:       List[str] = field(default_factory=list)
    top_deg_genes:      List[str] = field(default_factory=list)
    pathway_hits:       List[str] = field(default_factory=list)
    matrigel_warning:   bool = False

    # Drug engine
    drug_compounds:     List[str] = field(default_factory=list)
    pk_model_used:      str = ""
    drug_release_notes: str = ""

    # Regulatory
    reg_scenario:       str = ""
    reg_fda_class:      str = ""
    reg_eu_class:       str = ""
    reg_pathway_name:   str = ""
    reg_total_duration: str = ""
    reg_total_cost:     str = ""
    reg_key_risks:      List[str] = field(default_factory=list)
    iso_test_count:     int = 0
    atmp_flag:          bool = False

    # Experimental
    exp_stages:         List[str] = field(default_factory=list)   # "Stage N: Name (X weeks)"
    exp_duration:       str = ""
    dbtl_iterations:    int = 0
    dbtl_latest_status: str = ""
    dbtl_latest_learning: str = ""

    # Business
    market_name:        str = ""
    market_size_2024:   str = ""
    market_cagr:        str = ""
    market_2030:        str = ""
    key_players:        List[str] = field(default_factory=list)
    unmet_needs:        List[str] = field(default_factory=list)
    swot_strengths:     List[str] = field(default_factory=list)
    swot_weaknesses:    List[str] = field(default_factory=list)
    swot_opportunities: List[str] = field(default_factory=list)
    swot_threats:       List[str] = field(default_factory=list)
    competitors:        List[str] = field(default_factory=list)
    reimbursement_notes:str = ""

    # Researcher network
    researcher_count:   int = 0
    key_researchers:    List[str] = field(default_factory=list)

    # User-supplied free text (editable in UI before generation)
    user_context:       str = ""

    # ── Helpers ────────────────────────────────────────────────────────────────

    def has_data(self) -> bool:
        return bool(self.project_name or self.paper_count or self.materials_named
                    or self.reg_scenario or self.market_name)

    def to_section_text(self, section: str) -> str:
        """Return a compact text block for a named section, suitable for prompt injection."""
        sections = {
            "project":      self._project_block,
            "literature":   self._literature_block,
            "materials":    self._materials_block,
            "bio":          self._bio_block,
            "drug":         self._drug_block,
            "regulatory":   self._regulatory_block,
            "experimental": self._experimental_block,
            "business":     self._business_block,
            "researchers":  self._researcher_block,
        }
        fn = sections.get(section)
        return fn() if fn else ""

    def to_full_context(self) -> str:
        """Assemble all sections into one master context string."""
        parts = []
        for section in ["project", "literature", "materials", "bio", "drug",
                        "regulatory", "experimental", "business", "researchers"]:
            text = self.to_section_text(section)
            if text.strip():
                parts.append(text)
        if self.user_context.strip():
            parts.append(f"== ADDITIONAL CONTEXT (from team) ==\n{self.user_context}")
        return "\n\n".join(parts)

    # ── Section text builders ──────────────────────────────────────────────────

    def _project_block(self) -> str:
        if not self.project_name:
            return ""
        lines = ["== PROJECT ==",
                 f"Name: {self.project_name}",
                 f"Target tissue: {self.project_tissue or 'not specified'}",
                 f"Regulatory aim: {self.project_aim or 'not specified'}",
                 f"Timeline: {self.project_timeline or 'not specified'}",
                 f"Budget tier: {self.project_budget or 'not specified'}"]
        if self.project_keywords:
            lines.append(f"Focus keywords: {', '.join(self.project_keywords)}")
        if self.project_description:
            lines.append(f"Description: {self.project_description}")
        return "\n".join(lines)

    def _literature_block(self) -> str:
        if self.paper_count == 0 and not self.top_papers:
            return ""
        lines = [f"== LITERATURE ({self.paper_count} papers indexed) =="]
        for p in self.top_papers[:5]:
            lines.append(f"  - {p}")
        if self.key_findings:
            lines.append("Key findings:")
            for f_ in self.key_findings[:4]:
                lines.append(f"  - {f_}")
        return "\n".join(lines)

    def _materials_block(self) -> str:
        if not self.materials_named:
            return ""
        lines = ["== MATERIALS ==",
                 "Named materials: " + ", ".join(self.materials_named[:8])]
        for h in self.material_highlights[:3]:
            lines.append(f"  - {h}")
        return "\n".join(lines)

    def _bio_block(self) -> str:
        if not self.geo_datasets and not self.top_deg_genes:
            return ""
        lines = ["== TRANSCRIPTOMICS / BIO =="]
        if self.geo_datasets:
            lines.append(f"GEO datasets: {', '.join(self.geo_datasets[:5])}")
        if self.top_deg_genes:
            lines.append(f"Top DEGs: {', '.join(self.top_deg_genes[:10])}")
        if self.pathway_hits:
            lines.append(f"Pathway hits: {', '.join(self.pathway_hits[:5])}")
        if self.matrigel_warning:
            lines.append("CAVEAT: Matrigel used as baseline — results include Matrigel artefact genes.")
        return "\n".join(lines)

    def _drug_block(self) -> str:
        if not self.drug_compounds:
            return ""
        lines = ["== DRUG DELIVERY ==",
                 f"Compounds: {', '.join(self.drug_compounds[:5])}"]
        if self.pk_model_used:
            lines.append(f"PK model: {self.pk_model_used}")
        if self.drug_release_notes:
            lines.append(f"Notes: {self.drug_release_notes}")
        return "\n".join(lines)

    def _regulatory_block(self) -> str:
        if not self.reg_scenario:
            return ""
        lines = ["== REGULATORY ==",
                 f"Scenario: {self.reg_scenario}  |  FDA: {self.reg_fda_class}  |  EU: {self.reg_eu_class}",
                 f"Pathway: {self.reg_pathway_name}",
                 f"Timeline: {self.reg_total_duration}  |  Est. cost: {self.reg_total_cost}"]
        if self.atmp_flag:
            lines.append("ATMP FLAG: This product requires ATMP/BLA pathway.")
        if self.iso_test_count:
            lines.append(f"ISO 10993 tests identified: {self.iso_test_count}")
        if self.reg_key_risks:
            lines.append("Key risks: " + "; ".join(self.reg_key_risks[:3]))
        return "\n".join(lines)

    def _experimental_block(self) -> str:
        if not self.exp_stages and self.dbtl_iterations == 0:
            return ""
        lines = ["== EXPERIMENTAL ROADMAP =="]
        if self.exp_stages:
            lines.append(f"Roadmap ({self.exp_duration}):")
            for s in self.exp_stages[:6]:
                lines.append(f"  {s}")
        if self.dbtl_iterations > 0:
            lines.append(f"DBTL iterations completed: {self.dbtl_iterations}")
            if self.dbtl_latest_status:
                lines.append(f"Latest cycle status: {self.dbtl_latest_status}")
            if self.dbtl_latest_learning:
                lines.append(f"Latest learning: {self.dbtl_latest_learning}")
        return "\n".join(lines)

    def _business_block(self) -> str:
        if not self.market_name:
            return ""
        lines = ["== MARKET & BUSINESS ==",
                 f"Market: {self.market_name}",
                 f"Size: ${self.market_size_2024}B (2024)  |  CAGR: {self.market_cagr}%  |  2030: ${self.market_2030}B"]
        if self.key_players:
            lines.append(f"Key players: {', '.join(self.key_players[:5])}")
        if self.unmet_needs:
            lines.append("Unmet needs: " + "; ".join(self.unmet_needs[:3]))
        if self.swot_strengths:
            lines.append("Strengths: " + "; ".join(s.text if hasattr(s, 'text') else str(s)
                                                    for s in self.swot_strengths[:3]))
        if self.swot_threats:
            lines.append("Threats: " + "; ".join(s.text if hasattr(s, 'text') else str(s)
                                                  for s in self.swot_threats[:3]))
        if self.competitors:
            lines.append("Competitors: " + ", ".join(self.competitors[:5]))
        if self.reimbursement_notes:
            lines.append(f"Reimbursement: {self.reimbursement_notes[:200]}")
        return "\n".join(lines)

    def _researcher_block(self) -> str:
        if self.researcher_count == 0:
            return ""
        lines = [f"== RESEARCHER NETWORK ({self.researcher_count} tracked) =="]
        for r in self.key_researchers[:5]:
            lines.append(f"  - {r}")
        return "\n".join(lines)


# ── Assembler ──────────────────────────────────────────────────────────────────

class ContextAssembler:
    """
    Pull data from all application modules and return a BriefingContext.
    Each module harvest is isolated — failures are logged and skipped.
    """

    def assemble(self, swot=None, roadmap=None, dbtl_tracker=None) -> BriefingContext:
        """
        Args:
            swot:         Active SWOTAnalysis object (from business tab) — optional
            roadmap:      Active ExperimentalRoadmap object (from experimental tab) — optional
            dbtl_tracker: Active DBTLTracker (from experimental tab) — optional
        """
        ctx = BriefingContext()
        self._harvest_project(ctx)
        self._harvest_literature(ctx)
        self._harvest_materials(ctx)
        self._harvest_bio(ctx)
        self._harvest_regulatory(ctx)
        self._harvest_experimental(ctx, roadmap, dbtl_tracker)
        self._harvest_business(ctx, swot)
        self._harvest_researchers(ctx)
        return ctx

    # ── Module harvesters ──────────────────────────────────────────────────────

    def _harvest_project(self, ctx: BriefingContext) -> None:
        try:
            from data_manager import get_db
            db = get_db()
            with db.connection() as conn:
                row = conn.execute(
                    "SELECT * FROM projects ORDER BY id DESC LIMIT 1"
                ).fetchone()
            if row:
                ctx.project_name    = row["name"] or ""
                ctx.project_tissue  = row["target_tissue"] or ""
                ctx.project_aim     = row["regulatory_aim"] or ""
                ctx.project_budget  = row["budget_tier"] or ""
                ctx.project_timeline= str(row["timeline_months"] or "") + " months"
                ctx.project_description = row["description"] or ""
                kw_raw = row["focus_keywords"] or ""
                ctx.project_keywords = [k.strip() for k in kw_raw.split(",") if k.strip()]
        except Exception as e:
            logger.debug("Project harvest failed: %s", e)
            ctx.project_name = "Untitled Project"

    def _harvest_literature(self, ctx: BriefingContext) -> None:
        try:
            from data_manager import get_db
            db = get_db()
            with db.connection() as conn:
                count = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
                papers = conn.execute(
                    "SELECT authors, year, title FROM papers ORDER BY year DESC LIMIT 5"
                ).fetchall()
            ctx.paper_count = count
            ctx.top_papers = [
                f"{(p['authors'] or 'Unknown').split(',')[0]} ({p['year'] or '?'}) — {(p['title'] or '')[:80]}"
                for p in papers
            ]
        except Exception as e:
            logger.debug("Literature harvest failed: %s", e)

    def _harvest_materials(self, ctx: BriefingContext) -> None:
        try:
            from data_manager import get_db
            db = get_db()
            with db.connection() as conn:
                materials = conn.execute(
                    "SELECT name, material_class FROM materials LIMIT 10"
                ).fetchall()
            ctx.materials_named = [m["name"] for m in materials]
            ctx.material_highlights = [
                f"{m['name']} ({m['material_class']})" for m in materials[:3]
                if m.get("material_class")
            ]
        except Exception as e:
            logger.debug("Materials harvest failed: %s", e)

    def _harvest_bio(self, ctx: BriefingContext) -> None:
        try:
            from data_manager import get_db
            db = get_db()
            with db.connection() as conn:
                datasets = conn.execute(
                    "SELECT gse_id FROM geo_datasets LIMIT 5"
                ).fetchall()
            ctx.geo_datasets = [d["gse_id"] for d in datasets]
        except Exception as e:
            logger.debug("Bio harvest (DB) failed: %s", e)

    def _harvest_regulatory(self, ctx: BriefingContext) -> None:
        try:
            from data_manager import get_db
            db = get_db()
            with db.connection() as conn:
                row = conn.execute(
                    "SELECT * FROM regulatory_classifications ORDER BY id DESC LIMIT 1"
                ).fetchone()
            if row:
                ctx.reg_scenario   = row["scenario"] or ""
                ctx.reg_fda_class  = row["fda_class"] or ""
                ctx.reg_eu_class   = row["eu_class"] or ""
                ctx.reg_pathway_name = row["pathway_name"] or ""
                ctx.reg_total_duration = row["total_duration"] or ""
                ctx.reg_total_cost = row["total_cost"] or ""
                ctx.atmp_flag      = bool(row["atmp_flag"])
                import json
                risks_raw = row["key_risks"] or "[]"
                try:
                    ctx.reg_key_risks = json.loads(risks_raw)
                except Exception:
                    ctx.reg_key_risks = []
        except Exception as e:
            logger.debug("Regulatory harvest failed: %s", e)

    def _harvest_experimental(self, ctx: BriefingContext,
                               roadmap=None, dbtl_tracker=None) -> None:
        if roadmap is not None:
            try:
                ctx.exp_duration = roadmap.total_duration
                ctx.exp_stages = [
                    f"Stage {s.stage_number}: {s.name} ({s.duration_weeks} weeks)"
                    for s in roadmap.stages
                ]
            except Exception as e:
                logger.debug("Roadmap harvest failed: %s", e)

        if dbtl_tracker is not None:
            try:
                cycles = dbtl_tracker.get_all_cycles()
                ctx.dbtl_iterations = len(cycles)
                if cycles:
                    latest = cycles[-1]
                    ctx.dbtl_latest_status  = latest.status
                    ctx.dbtl_latest_learning= latest.learning
            except Exception as e:
                logger.debug("DBTL harvest failed: %s", e)

    def _harvest_business(self, ctx: BriefingContext, swot=None) -> None:
        try:
            from business_intelligence import search_segments
            if ctx.project_tissue:
                segs = search_segments(ctx.project_tissue)
                if segs:
                    seg = segs[0]
                    ctx.market_name     = seg.name
                    ctx.market_size_2024= seg.market_size_2024
                    ctx.market_cagr     = seg.cagr
                    ctx.market_2030     = seg.market_2030
                    ctx.key_players     = seg.key_players[:6]
                    ctx.unmet_needs     = seg.unmet_needs[:3]
                    ctx.reimbursement_notes = seg.reimbursement_notes
        except Exception as e:
            logger.debug("Market harvest failed: %s", e)

        if swot is not None:
            try:
                ctx.swot_strengths    = [i.text for i in swot.strengths[:4]]
                ctx.swot_weaknesses   = [i.text for i in swot.weaknesses[:4]]
                ctx.swot_opportunities= [i.text for i in swot.opportunities[:4]]
                ctx.swot_threats      = [i.text for i in swot.threats[:4]]
                ctx.competitors       = [f"{c.name} ({c.product}, {c.stage})"
                                         for c in swot.competitors[:5]]
            except Exception as e:
                logger.debug("SWOT harvest failed: %s", e)

    def _harvest_researchers(self, ctx: BriefingContext) -> None:
        try:
            from data_manager import get_db
            db = get_db()
            with db.connection() as conn:
                count = conn.execute("SELECT COUNT(*) FROM researchers").fetchone()[0]
                researchers = conn.execute(
                    "SELECT name, institution FROM researchers ORDER BY h_index DESC LIMIT 5"
                ).fetchall()
            ctx.researcher_count = count
            ctx.key_researchers = [
                f"{r['name']} ({r['institution'] or 'unknown institution'})"
                for r in researchers
            ]
        except Exception as e:
            logger.debug("Researcher harvest failed: %s", e)
