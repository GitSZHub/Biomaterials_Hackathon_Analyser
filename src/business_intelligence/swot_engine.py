"""
SWOT Engine
===========
Manages SWOT (Strengths / Weaknesses / Opportunities / Threats) analysis
for a biomaterials project. Each item is evidence-grounded (linked to source),
stakeholder-filtered, and versioned.

The engine also provides a competitive landscape model (basic).

Usage:
    from business_intelligence.swot_engine import SWOTEngine, SWOTAnalysis

    engine = SWOTEngine()
    analysis = engine.create(
        project_name="OsteoBridge HA-PCL Scaffold",
        tissue="bone",
        scenario="A",
    )
    analysis.add_strength("Unique macroporous HA structure", evidence="Pub: Smith 2023 JBMR")
    analysis.add_threat("Medtronic InFUSE dominates spinal fusion market", stakeholder_lens="investor")
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class SWOTItem:
    text:             str
    evidence:         str = ""         # citation, data source, or "expert judgement"
    stakeholder_lens: str = "general"  # "general" / "investor" / "clinical" / "regulatory" / "payer"
    priority:         str = "medium"   # "high" / "medium" / "low"
    created_at:       str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


@dataclass
class CompetitorEntry:
    name:         str
    product:      str
    stage:        str     # "market" / "clinical" / "preclinical" / "research"
    strengths:    List[str] = field(default_factory=list)
    weaknesses:   List[str] = field(default_factory=list)
    website:      str = ""
    notes:        str = ""


@dataclass
class SWOTAnalysis:
    project_name:   str
    tissue:         str
    scenario:       str
    version:        int = 1
    created_at:     str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    updated_at:     str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    strengths:      List[SWOTItem] = field(default_factory=list)
    weaknesses:     List[SWOTItem] = field(default_factory=list)
    opportunities:  List[SWOTItem] = field(default_factory=list)
    threats:        List[SWOTItem] = field(default_factory=list)
    competitors:    List[CompetitorEntry] = field(default_factory=list)
    strategic_notes: str = ""

    # ── Item management ────────────────────────────────────────────────────────

    def add_strength(self, text: str, evidence: str = "", stakeholder_lens: str = "general",
                     priority: str = "medium") -> None:
        self.strengths.append(SWOTItem(text, evidence, stakeholder_lens, priority))
        self._touch()

    def add_weakness(self, text: str, evidence: str = "", stakeholder_lens: str = "general",
                     priority: str = "medium") -> None:
        self.weaknesses.append(SWOTItem(text, evidence, stakeholder_lens, priority))
        self._touch()

    def add_opportunity(self, text: str, evidence: str = "", stakeholder_lens: str = "general",
                        priority: str = "medium") -> None:
        self.opportunities.append(SWOTItem(text, evidence, stakeholder_lens, priority))
        self._touch()

    def add_threat(self, text: str, evidence: str = "", stakeholder_lens: str = "general",
                   priority: str = "medium") -> None:
        self.threats.append(SWOTItem(text, evidence, stakeholder_lens, priority))
        self._touch()

    def add_competitor(self, name: str, product: str, stage: str,
                       strengths: Optional[List[str]] = None,
                       weaknesses: Optional[List[str]] = None,
                       notes: str = "") -> None:
        self.competitors.append(CompetitorEntry(
            name=name, product=product, stage=stage,
            strengths=strengths or [], weaknesses=weaknesses or [], notes=notes,
        ))
        self._touch()

    def filter_by_lens(self, lens: str) -> "SWOTAnalysis":
        """Return a view filtered to a specific stakeholder lens (general items always included)."""
        def _f(items: List[SWOTItem]) -> List[SWOTItem]:
            return [i for i in items if i.stakeholder_lens in ("general", lens)]
        filtered = SWOTAnalysis(
            project_name=self.project_name, tissue=self.tissue,
            scenario=self.scenario, version=self.version,
        )
        filtered.strengths    = _f(self.strengths)
        filtered.weaknesses   = _f(self.weaknesses)
        filtered.opportunities= _f(self.opportunities)
        filtered.threats      = _f(self.threats)
        filtered.competitors  = self.competitors
        return filtered

    def to_dict(self) -> dict:
        return {
            "project_name": self.project_name, "tissue": self.tissue,
            "scenario": self.scenario, "version": self.version,
            "created_at": self.created_at, "updated_at": self.updated_at,
            "strengths":    [vars(i) for i in self.strengths],
            "weaknesses":   [vars(i) for i in self.weaknesses],
            "opportunities":[vars(i) for i in self.opportunities],
            "threats":      [vars(i) for i in self.threats],
            "competitors":  [vars(c) for c in self.competitors],
            "strategic_notes": self.strategic_notes,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def to_context_string(self) -> str:
        """Flatten SWOT to a plain-text block for AI prompting."""
        lines = [f"Project: {self.project_name} | Tissue: {self.tissue} | Scenario: {self.scenario}",
                 ""]
        for label, items in [("STRENGTHS", self.strengths), ("WEAKNESSES", self.weaknesses),
                              ("OPPORTUNITIES", self.opportunities), ("THREATS", self.threats)]:
            lines.append(f"== {label} ==")
            if items:
                for item in items:
                    ev = f" [{item.evidence}]" if item.evidence else ""
                    lines.append(f"  - [{item.priority.upper()}] {item.text}{ev}")
            else:
                lines.append("  (none entered)")
            lines.append("")
        if self.competitors:
            lines.append("== COMPETITORS ==")
            for c in self.competitors:
                lines.append(f"  - {c.name}: {c.product} ({c.stage})")
                if c.strengths:
                    lines.append(f"    Strengths: {'; '.join(c.strengths)}")
                if c.weaknesses:
                    lines.append(f"    Weaknesses: {'; '.join(c.weaknesses)}")
        return "\n".join(lines)

    def _touch(self):
        self.updated_at = datetime.now().isoformat(timespec="seconds")


# ── Engine ─────────────────────────────────────────────────────────────────────

class SWOTEngine:
    """
    Create and manage SWOT analyses, with optional pre-seeding from the
    market knowledge base for the target tissue segment.
    """

    def create(
        self,
        project_name: str,
        tissue: str = "",
        scenario: str = "A",
        pre_seed: bool = True,
    ) -> SWOTAnalysis:
        """
        Create a new SWOTAnalysis, optionally pre-seeded with curated items
        from the market KB for the relevant tissue segment.
        """
        analysis = SWOTAnalysis(
            project_name=project_name,
            tissue=tissue,
            scenario=scenario,
        )
        if pre_seed and tissue:
            self._seed_from_market_kb(analysis, tissue, scenario)
        return analysis

    def _seed_from_market_kb(self, analysis: SWOTAnalysis, tissue: str, scenario: str) -> None:
        try:
            from .market_kb import search_segments
            segments = search_segments(tissue)
            if not segments:
                return
            seg = segments[0]

            # Pre-seed opportunities from market growth drivers
            for driver in seg.growth_drivers[:3]:
                analysis.add_opportunity(
                    driver,
                    evidence=f"Market KB: {seg.name}",
                    priority="medium",
                )

            # Pre-seed threats from market restraints
            for restraint in seg.restraints[:2]:
                analysis.add_threat(
                    restraint,
                    evidence=f"Market KB: {seg.name}",
                    priority="medium",
                )

            # Pre-seed competitor threats from key players
            if seg.key_players:
                analysis.add_threat(
                    f"Established incumbents: {', '.join(seg.key_players[:4])}",
                    evidence=f"Market KB: {seg.name}",
                    stakeholder_lens="investor",
                    priority="high",
                )

            # Pre-seed opportunity from unmet needs
            for need in seg.unmet_needs[:2]:
                analysis.add_opportunity(
                    f"Unmet need: {need}",
                    evidence=f"Market KB: {seg.name}",
                    priority="high",
                )

            # Regulatory scenario threats
            reg_threat = self._scenario_threat(scenario)
            if reg_threat:
                analysis.add_threat(
                    reg_threat, evidence="Regulatory pathway KB",
                    stakeholder_lens="investor", priority="high",
                )

        except Exception:
            pass   # silent — pre-seeding is optional

    @staticmethod
    def _scenario_threat(scenario: str) -> str:
        return {
            "A": "Class II-III regulatory pathway requires substantial predicate or PMA — 2-5 year timeline to market.",
            "B": "Combination product dual-agency review (CDRH + CDER) extends timeline; GMP for both components.",
            "C": "ATMP pathway requires Phase I-III clinical programme; 10-20 year timeline, >$100M investment.",
            "D": "GMO contained use authorisation adds 2-4 years; public perception risk.",
        }.get(scenario, "")
