"""
Experimental Roadmap Designer
==============================
Generates a structured experimental roadmap for a biomaterials project based on:
  - Target tissue
  - Regulatory scenario (A / B / C / D)
  - Available resources (cell culture / animal facility / GMP)
  - Timeline constraint

The roadmap is a curated static knowledge base layered with AI expansion.
Each stage has recommended cell models, organism models, endpoint assays,
and milestone criteria.

Usage:
    from experimental_engine.experimental_designer import ExperimentalDesigner
    roadmap = ExperimentalDesigner().generate(
        tissue="bone",
        scenario="A",
        has_cell_lab=True,
        has_animal_facility=True,
        has_gmp=False,
        timeline_months=18,
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .cell_models_db import get_models_for_tissue as get_cell_models, CellModel
from .organism_models_db import get_models_for_tissue as get_org_models, OrganismModel


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class RoadmapStage:
    stage_number:   int
    name:           str          # e.g. "Stage 1: In vitro cytotoxicity"
    phase:          str          # "in_vitro" / "in_vivo" / "regulatory" / "clinical"
    duration_weeks: str          # e.g. "4-8"
    objective:      str
    cell_models:    List[CellModel]    = field(default_factory=list)
    organism_models: List[OrganismModel] = field(default_factory=list)
    assays:         List[str]    = field(default_factory=list)
    milestone:      str          = ""   # go/no-go criterion
    iso_standards:  List[str]    = field(default_factory=list)
    three_rs_notes: str          = ""
    gmp_required:   bool         = False
    notes:          str          = ""


@dataclass
class ExperimentalRoadmap:
    tissue:          str
    scenario:        str
    stages:          List[RoadmapStage] = field(default_factory=list)
    total_duration:  str = ""
    key_go_nogo:     List[str] = field(default_factory=list)
    critical_path:   str = ""


# ── Designer ───────────────────────────────────────────────────────────────────

class ExperimentalDesigner:
    """
    Generate a staged experimental roadmap for a biomaterials project.
    """

    def generate(
        self,
        tissue: str,
        scenario: str = "A",
        has_cell_lab: bool = True,
        has_animal_facility: bool = True,
        has_gmp: bool = False,
        timeline_months: int = 24,
    ) -> ExperimentalRoadmap:
        """
        Args:
            tissue:               Target tissue (e.g. "bone", "skin", "cartilage")
            scenario:             Regulatory scenario A/B/C/D
            has_cell_lab:         Access to cell culture facility
            has_animal_facility:  Access to licensed animal facility
            has_gmp:              GMP manufacturing capability
            timeline_months:      Project timeline constraint
        """
        cell_models = get_cell_models(tissue)
        org_models  = get_org_models(tissue)

        # Filter by available resources
        if not has_animal_facility:
            org_models = [m for m in org_models if m.three_rs_category == "alternative"]
        if not has_gmp:
            org_models = [m for m in org_models if not m.gmp_required]

        stages = self._build_stages(tissue, scenario, cell_models, org_models,
                                    has_cell_lab, has_animal_facility, has_gmp,
                                    timeline_months)

        go_nogo = [s.milestone for s in stages if s.milestone]

        return ExperimentalRoadmap(
            tissue=tissue,
            scenario=scenario,
            stages=stages,
            total_duration=self._estimate_duration(stages),
            key_go_nogo=go_nogo,
            critical_path=self._critical_path(scenario),
        )

    # ── Stage builders ─────────────────────────────────────────────────────────

    def _build_stages(
        self,
        tissue: str,
        scenario: str,
        cell_models: List[CellModel],
        org_models: List[OrganismModel],
        has_cell_lab: bool,
        has_animal_facility: bool,
        has_gmp: bool,
        timeline_months: int,
    ) -> List[RoadmapStage]:

        stages: List[RoadmapStage] = []
        n = 1

        # ── Stage 1: Physicochemical characterisation (always first) ──────────
        stages.append(RoadmapStage(
            stage_number=n, name="Physicochemical Characterisation",
            phase="in_vitro",
            duration_weeks="2-4",
            objective="Characterise material composition, structure, and degradation before any biological testing.",
            assays=[
                "SEM/TEM morphology",
                "FTIR / Raman spectroscopy (chemical identity)",
                "XRD (crystallinity)",
                "TGA / DSC (thermal properties)",
                "Swelling + degradation rate (PBS, 37 degC)",
                "pH / ion release (ICP-OES for metals/ceramics)",
                "Porosity (mercury porosimetry / micro-CT)",
                "Mechanical testing (compression / tensile / DMA)",
            ],
            milestone="Material composition confirmed; degradation kinetics within design spec.",
            iso_standards=["ISO 10993-18 (chemical characterisation)", "ISO 10993-13 (polymers)"],
            notes="Complete before in vitro biology — leachables must be characterised first.",
        ))
        n += 1

        # ── Stage 2: ISO 10993-5 cytotoxicity (if cell lab available) ─────────
        if has_cell_lab:
            iso_lines = [m for m in cell_models if m.iso10993]
            if not iso_lines:
                iso_lines = cell_models[:2]
            stages.append(RoadmapStage(
                stage_number=n, name="ISO 10993-5 Cytotoxicity Screening",
                phase="in_vitro",
                duration_weeks="3-6",
                objective="Screen material extract and direct contact for cytotoxicity using ISO 10993-5 compliant cell lines.",
                cell_models=iso_lines,
                assays=[
                    "MTT / MTS viability (ISO 10993-5)",
                    "LDH cytotoxicity (indirect contact — extract)",
                    "Live/dead staining (direct contact)",
                    "Cell morphology (phase contrast / SEM)",
                    "Neutral red uptake (NRU)",
                ],
                milestone=">70% cell viability vs. negative control; no significant cytotoxicity at clinical dose equivalent.",
                iso_standards=["ISO 10993-5"],
                three_rs_notes="ISO 10993-5 replacement of Draize test. L929 and 3T3 preferred.",
            ))
            n += 1

        # ── Stage 3: Tissue-specific in vitro functional assays ───────────────
        if has_cell_lab and cell_models:
            tissue_cells = [m for m in cell_models if not m.iso10993][:3]
            if tissue_cells:
                assays = self._tissue_assays(tissue)
                stages.append(RoadmapStage(
                    stage_number=n, name=f"Tissue-Specific In Vitro Efficacy ({tissue.title()})",
                    phase="in_vitro",
                    duration_weeks="6-12",
                    objective=f"Assess material support for {tissue} cell adhesion, proliferation, and differentiation.",
                    cell_models=tissue_cells,
                    assays=assays,
                    milestone="Significant improvement vs. TCP control on at least 2 functional endpoints.",
                    three_rs_notes="Primary or iPSC-derived cells increase translational value and reduce animal use.",
                ))
                n += 1

        # ── Scenario B: drug release in vitro ─────────────────────────────────
        if scenario == "B":
            stages.append(RoadmapStage(
                stage_number=n, name="Drug Release Characterisation (In Vitro)",
                phase="in_vitro",
                duration_weeks="4-8",
                objective="Characterise drug release kinetics, stability, and biological activity of released drug.",
                assays=[
                    "HPLC drug release quantification (PBS + simulated body fluid)",
                    "Franz diffusion cell or USP paddle dissolution",
                    "Drug bioactivity after release (cell-based assay)",
                    "Extractables and leachables (ICH Q3C guideline)",
                    "Drug-material compatibility (stability study)",
                ],
                milestone="Sustained release profile matching design target; released drug retains >80% bioactivity.",
                iso_standards=["ICH Q3C (E&L)", "ISO 10993-18"],
            ))
            n += 1

        # ── Scenario C: cell seeding and GMP scale-up ─────────────────────────
        if scenario == "C":
            stages.append(RoadmapStage(
                stage_number=n, name="Cell-Scaffold Integration & GMP Readiness",
                phase="in_vitro",
                duration_weeks="12-24",
                objective="Establish GMP-compatible cell seeding process; demonstrate cell viability and function on scaffold.",
                assays=[
                    "Cell seeding efficiency",
                    "Long-term viability (21-42 days)",
                    "Sterility testing (USP <71>)",
                    "Identity / potency assays (release criteria)",
                    "Karyotyping (genomic stability for iPSC lines)",
                    "Tumorigenicity assay (if iPSC-derived)",
                ],
                milestone="Sterile product meeting release criteria; >80% viability at day 14; karyotype normal.",
                iso_standards=["EU GMP Annex 2A (ATMPs)", "ICH Q5A-Q5D"],
                gmp_required=True,
                notes="Hospital exemption may allow non-GMP prototype for early in vivo proof-of-concept.",
            ))
            n += 1

        # ── Stage: In vivo small animal ───────────────────────────────────────
        if has_animal_facility and org_models:
            small_animals = [m for m in org_models
                             if m.species.lower() in ("rat", "mouse", "rabbit")][:2]
            if small_animals:
                stages.append(RoadmapStage(
                    stage_number=n, name="Small Animal In Vivo Implantation",
                    phase="in_vivo",
                    duration_weeks="12-26",
                    objective="Establish in vivo biocompatibility and preliminary efficacy in small animal model.",
                    organism_models=small_animals,
                    assays=self._in_vivo_assays(small_animals),
                    milestone="No adverse local tissue reaction (ISO 10993-6 grade <= 1); tissue integration demonstrated.",
                    iso_standards=["ISO 10993-6 (implantation)", "ISO 10993-2 (animal welfare)"],
                    three_rs_notes="Apply 3Rs: minimum group size (n=6/group), power analysis, use of alternatives where validated.",
                ))
                n += 1

        # ── Stage: Large animal / pivotal preclinical (Class III / ATMP) ──────
        if has_animal_facility and scenario in ("A", "B", "C") and org_models:
            large_animals = [m for m in org_models
                             if m.species.lower() in ("sheep", "pig")][:1]
            if large_animals and (scenario in ("B", "C") or timeline_months >= 18):
                stages.append(RoadmapStage(
                    stage_number=n, name="Large Animal Pivotal Preclinical Study",
                    phase="in_vivo",
                    duration_weeks="24-52",
                    objective="Pivotal GLP preclinical study in large animal model for regulatory submission.",
                    organism_models=large_animals,
                    assays=self._in_vivo_assays(large_animals),
                    milestone="Primary efficacy endpoint met; no serious adverse events; GLP report signed.",
                    iso_standards=["ISO 10993-6", "OECD GLP principles"],
                    gmp_required=has_gmp,
                    notes="Required for FDA IDE / EU pivotal clinical study authorisation.",
                ))
                n += 1

        # ── Regulatory submission stage ────────────────────────────────────────
        sub_name, sub_duration, sub_assays = self._regulatory_stage(scenario)
        stages.append(RoadmapStage(
            stage_number=n, name=sub_name,
            phase="regulatory",
            duration_weeks=sub_duration,
            objective="Compile and submit regulatory dossier based on accumulated preclinical evidence.",
            assays=sub_assays,
            milestone="Regulatory clearance / approval received.",
        ))

        return stages

    # ── Helper methods ─────────────────────────────────────────────────────────

    def _tissue_assays(self, tissue: str) -> List[str]:
        base = ["Cell adhesion (SEM / confocal)", "Proliferation (Alamar Blue / BrdU)",
                "Cytoskeleton staining (F-actin / vinculin)"]
        extras: dict = {
            "bone": ["ALP activity", "Alizarin Red mineralisation", "Osteocalcin ELISA",
                     "Collagen secretion (Sircol)", "Runx2/OSX gene expression (RT-qPCR)"],
            "cartilage": ["GAG quantification (DMMB)", "Collagen II IHC", "Aggrecan / SOX9 RT-qPCR",
                          "Pellet culture histology (Safranin O)", "Mechanical indentation"],
            "skin": ["Scratch wound healing assay", "Collagen gel contraction",
                     "Re-epithelialisation assay (ALI)", "Alpha-SMA myofibroblast marker",
                     "Cytokine panel (IL-6, IL-8, TNF-alpha)"],
            "cardiovascular": ["Tube formation assay (HUVEC)", "Calcium transients (Fluo-4)",
                               "Action potential (MEA)", "Thrombogenicity (ISO 10993-4)"],
            "neural": ["Neurite outgrowth quantification", "Electrophysiology (patch-clamp / MEA)",
                       "Neurotrophic factor secretion (BDNF, NGF ELISA)", "Synaptogenesis markers"],
            "liver": ["Albumin secretion", "Urea synthesis", "CYP450 activity (CYP3A4, CYP1A2)",
                      "Hepatotoxicity panel (ALT/AST analogues)"],
        }
        return base + extras.get(tissue.lower(), ["Functional endpoint specific to target tissue"])

    def _in_vivo_assays(self, models: List[OrganismModel]) -> List[str]:
        assays: List[str] = []
        seen: set = set()
        for m in models:
            for a in m.endpoint_assays:
                if a not in seen:
                    assays.append(a)
                    seen.add(a)
        return assays or ["Histopathology (H&E)", "Inflammatory scoring (ISO 10993-6)"]

    def _regulatory_stage(self, scenario: str):
        if scenario == "A":
            return (
                "Regulatory Submission (510(k) / PMA / EU MDR Technical File)",
                "12-26",
                ["Compile ISO 10993 test battery", "510(k) or PMA dossier",
                 "EU Technical File + Clinical Evaluation Report (CER)",
                 "Labelling and IFU review"],
            )
        if scenario == "B":
            return (
                "Combination Product Regulatory Submission (PMA + IND/NDA)",
                "18-36",
                ["FDA Request for Designation (RFD)", "IND submission (drug component)",
                 "PMA + NDA/BLA modules", "CHMP consultation package (EU)"],
            )
        if scenario == "C":
            return (
                "ATMP / BLA Submission (Phase I-III Clinical Programme)",
                "60-120",
                ["IND (FDA) / CTA (EU) filing", "Phase I-III clinical data package",
                 "GMP manufacturing dossier", "BLA (FDA) / MAA (EMA)",
                 "Risk Management Plan + REMS"],
            )
        # Scenario D
        return (
            "GMO Contained Use Authorisation + Standard Device Submission",
            "12-24",
            ["EU Dir 2009/41 contained use notification",
             "Analytical characterisation (no viable GMO in product)",
             "Standard device 510(k) / PMA"],
        )

    @staticmethod
    def _estimate_duration(stages: List[RoadmapStage]) -> str:
        """Sum mid-point of each stage's duration range."""
        total_lo = total_hi = 0
        for s in stages:
            parts = s.duration_weeks.replace(" ", "").split("-")
            try:
                lo, hi = int(parts[0]), int(parts[-1])
            except ValueError:
                lo = hi = 8
            total_lo += lo
            total_hi += hi
        lo_m = round(total_lo / 4)
        hi_m = round(total_hi / 4)
        return f"{lo_m}-{hi_m} months"

    @staticmethod
    def _critical_path(scenario: str) -> str:
        paths = {
            "A": "Physicochemical characterisation -> ISO 10993-5 cytotoxicity -> in vivo implantation -> regulatory submission",
            "B": "Drug release characterisation -> combined biocompatibility + drug safety -> in vivo PK/PD -> IDE/PMA",
            "C": "GMP cell bank development -> Phase I safety -> Phase II PoC -> Phase III pivotal -> BLA/MAA",
            "D": "GMO contained use authorisation -> product characterisation (no viable GMO) -> standard device pathway",
        }
        return paths.get(scenario, "Standard preclinical -> regulatory submission")
