"""
Flow Cytometry Advisor — technique selection, panel design, and biomaterials-specific
application guidance for flow cytometry experiments.

Complements bio_engine.flow_data_processor (FCS import + gating) by providing
the experimental design intelligence layer.

Public API:
    from experimental_engine.flow_cytometry_advisor import (
        recommend_panel, design_panel, PanelRecommendation, PanelDesign,
        TECHNIQUE_VARIANTS, FLUOROCHROME_DB, APPLICATION_KB,
    )

    panel = recommend_panel(
        question="Is my material activating macrophages?",
        cell_type="THP-1",
        instrument_channels=8,
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class MarkerSpec:
    """A marker in a flow cytometry panel."""
    marker:         str             # e.g. "CD90", "pFAK"
    fluorochrome:   str = ""        # e.g. "FITC", "PE", "APC"
    clone:          str = ""        # antibody clone
    purpose:        str = ""        # what this marker tells you
    is_surface:     bool = True     # False = intracellular (needs perm)
    antigen_density: str = "medium" # "low" | "medium" | "high"


@dataclass
class PanelDesign:
    """Complete flow cytometry panel design."""
    panel_name:     str
    markers:        List[MarkerSpec] = field(default_factory=list)
    viability_dye:  str = "Zombie Aqua"
    fixation:       str = ""            # "none" | "PFA" | "methanol" | "Cytofix/Cytoperm"
    permeabilisation: str = ""          # "none" | "Triton" | "saponin" | "methanol"
    instrument_min: int = 4             # minimum laser/channel requirement
    protocol_notes: List[str] = field(default_factory=list)
    n_colours:      int = 0


@dataclass
class PanelRecommendation:
    """Recommended panel(s) for a research question."""
    question:       str
    panels:         List[PanelDesign] = field(default_factory=list)
    technique:      str = ""            # recommended flow variant
    controls:       List[str] = field(default_factory=list)
    acquisition_notes: List[str] = field(default_factory=list)
    analysis_notes: List[str] = field(default_factory=list)
    error:          Optional[str] = None


# ── Technique Variants ───────────────────────────────────────────────────────

TECHNIQUE_VARIANTS: Dict[str, Dict] = {
    "Conventional": {
        "description": "Standard 4-18 colour flow cytometry",
        "markers_max": 18,
        "live_sort": True,
        "accessibility": "any_lab",
        "cost": "low",
        "best_for": ["Viability", "Surface phenotyping", "Cell cycle", "ROS"],
    },
    "Spectral": {
        "description": "Full emission spectrum capture, 30-40 channels (Aurora, Symphony A5)",
        "markers_max": 40,
        "live_sort": True,
        "accessibility": "core_facility",
        "cost": "medium",
        "best_for": ["Deep immunophenotyping", "Complex panels", "Rare populations"],
    },
    "Mass Cytometry (CyTOF)": {
        "description": "Metal isotope-conjugated antibodies, 40+ markers, no spectral overlap",
        "markers_max": 50,
        "live_sort": False,
        "accessibility": "specialist",
        "cost": "high",
        "best_for": ["Deep immune profiling", "Scaffold-explanted cells", "Signalling states"],
    },
    "FACS (Sorting)": {
        "description": "Fluorescence-activated cell sorting for downstream culture/sequencing",
        "markers_max": 18,
        "live_sort": True,
        "accessibility": "core_facility",
        "cost": "medium",
        "best_for": ["Subpopulation isolation", "Sort → scRNA-seq", "Functional assays"],
    },
    "Imaging Flow (ImageStream)": {
        "description": "Flow throughput + brightfield + fluorescence images per cell",
        "markers_max": 12,
        "live_sort": False,
        "accessibility": "specialist",
        "cost": "high",
        "best_for": ["YAP nuclear translocation", "Phagocytosis scoring", "Morphology at scale"],
    },
}


# ── Fluorochrome Database ────────────────────────────────────────────────────

FLUOROCHROME_DB: Dict[str, Dict] = {
    "FITC": {"excitation": 488, "emission": 519, "brightness": "medium",
             "laser": "488nm Blue", "best_for": "medium-high density antigens"},
    "PE": {"excitation": 565, "emission": 578, "brightness": "very_high",
            "laser": "488nm Blue / 561nm Yellow-Green", "best_for": "low density antigens (brightest)"},
    "PE-Cy7": {"excitation": 565, "emission": 780, "brightness": "high",
                "laser": "488nm / 561nm", "best_for": "medium density antigens"},
    "APC": {"excitation": 650, "emission": 660, "brightness": "high",
             "laser": "633nm Red", "best_for": "low-medium density antigens"},
    "APC-Cy7": {"excitation": 650, "emission": 785, "brightness": "medium",
                 "laser": "633nm Red", "best_for": "medium density antigens"},
    "BV421": {"excitation": 405, "emission": 421, "brightness": "very_high",
               "laser": "405nm Violet", "best_for": "low density antigens"},
    "BV510": {"excitation": 405, "emission": 510, "brightness": "medium",
               "laser": "405nm Violet", "best_for": "medium density antigens"},
    "BV711": {"excitation": 405, "emission": 711, "brightness": "high",
               "laser": "405nm Violet", "best_for": "medium density antigens"},
    "BV785": {"excitation": 405, "emission": 785, "brightness": "medium",
               "laser": "405nm Violet", "best_for": "medium density antigens"},
    "PerCP-Cy5.5": {"excitation": 488, "emission": 695, "brightness": "medium",
                     "laser": "488nm Blue", "best_for": "medium density antigens"},
    "AF647": {"excitation": 650, "emission": 668, "brightness": "high",
               "laser": "633nm Red", "best_for": "low density antigens"},
    "AF700": {"excitation": 696, "emission": 719, "brightness": "medium",
               "laser": "633nm Red", "best_for": "medium density antigens"},
}


# ── Application Knowledge Base ───────────────────────────────────────────────

APPLICATION_KB: Dict[str, Dict] = {
    "Viability / Cytotoxicity": {
        "markers": [
            MarkerSpec("Live/Dead (Zombie Aqua)", "BV510", purpose="Viability gate", is_surface=True),
            MarkerSpec("Annexin V", "FITC", purpose="Early apoptosis (PS externalisation)"),
            MarkerSpec("PI", "", purpose="Late apoptosis / necrosis"),
            MarkerSpec("Caspase-3/7", "APC", purpose="Executioner caspase activation", is_surface=False),
        ],
        "fixation": "none",
        "categories": ["viability", "cytotoxicity", "apoptosis", "biocompatibility"],
        "notes": ["Stain viability BEFORE fixation", "Include unstained and single-stain controls"],
    },
    "MSC Identity (ISCT)": {
        "markers": [
            MarkerSpec("CD90", "FITC", purpose="MSC positive marker", antigen_density="high"),
            MarkerSpec("CD105", "PE", purpose="MSC positive marker (endoglin)", antigen_density="medium"),
            MarkerSpec("CD73", "APC", purpose="MSC positive marker (ecto-5'-nucleotidase)", antigen_density="high"),
            MarkerSpec("CD45", "PerCP-Cy5.5", purpose="Hematopoietic exclusion (must be negative)"),
            MarkerSpec("CD34", "PE-Cy7", purpose="Hematopoietic/endothelial exclusion"),
            MarkerSpec("CD14", "BV421", purpose="Monocyte exclusion"),
            MarkerSpec("HLA-DR", "APC-Cy7", purpose="MHC class II exclusion"),
        ],
        "fixation": "none",
        "categories": ["identity", "stem_cell", "msc", "phenotyping"],
        "notes": ["ISCT criteria: ≥95% positive for CD90/CD105/CD73, ≤2% positive for CD45/CD34/CD14/CD19/HLA-DR"],
    },
    "Macrophage Polarisation (M1/M2)": {
        "markers": [
            MarkerSpec("CD68", "PE", purpose="Pan-macrophage marker", antigen_density="high"),
            MarkerSpec("CD80", "FITC", purpose="M1 co-stimulatory (pro-inflammatory)"),
            MarkerSpec("CD86", "APC", purpose="M1 co-stimulatory"),
            MarkerSpec("HLA-DR", "BV421", purpose="M1 activation marker"),
            MarkerSpec("CD163", "PE-Cy7", purpose="M2 scavenger receptor (anti-inflammatory)"),
            MarkerSpec("CD206", "APC-Cy7", purpose="M2 mannose receptor"),
        ],
        "fixation": "PFA",
        "categories": ["inflammation", "immune", "macrophage", "foreign_body", "biocompatibility"],
        "notes": ["M1 = CD80+/CD86+/HLA-DR+, M2 = CD163+/CD206+",
                  "Foreign body response: M1→M2 transition over time indicates resolution"],
    },
    "Integrin Panel": {
        "markers": [
            MarkerSpec("CD49e (a5)", "FITC", purpose="Fibronectin receptor (a5b1)"),
            MarkerSpec("CD49f (a6)", "PE", purpose="Laminin receptor (a6b1/a6b4)"),
            MarkerSpec("CD49b (a2)", "APC", purpose="Collagen receptor (a2b1)"),
            MarkerSpec("CD51 (aV)", "PE-Cy7", purpose="RGD receptor (aVb3/aVb5)"),
            MarkerSpec("CD29 (b1)", "BV421", purpose="Common integrin b1 subunit"),
            MarkerSpec("CD61 (b3)", "APC-Cy7", purpose="Vitronectin/osteopontin receptor (aVb3)"),
        ],
        "fixation": "none",
        "categories": ["adhesion", "integrin", "mechanosensing", "ecm"],
        "notes": ["Material stiffness/ligand density → integrin expression changes",
                  "Cross-reference with proteomics surface proteomics and STRING PPI data"],
    },
    "Phospho-Flow Signalling": {
        "markers": [
            MarkerSpec("pFAK (Y397)", "AF647", purpose="Integrin activation / focal adhesion kinase",
                       is_surface=False, antigen_density="low"),
            MarkerSpec("pYAP (S127)", "PE", purpose="Mechanosensing — S127 phospho = cytoplasmic/inactive",
                       is_surface=False, antigen_density="low"),
            MarkerSpec("pSmad2/3", "FITC", purpose="TGF-b pathway activation",
                       is_surface=False, antigen_density="low"),
            MarkerSpec("pERK1/2", "APC", purpose="MAPK proliferation signal",
                       is_surface=False, antigen_density="medium"),
            MarkerSpec("pAKT (S473)", "BV421", purpose="PI3K/AKT survival signal",
                       is_surface=False, antigen_density="low"),
        ],
        "fixation": "Cytofix/Cytoperm or methanol",
        "permeabilisation": "methanol or saponin",
        "categories": ["signalling", "mechanosensing", "pathway", "phospho"],
        "notes": ["Fix immediately (prevent dephosphorylation): BD Cytofix 10 min 37°C → ice-cold methanol",
                  "Dim signals — use brightest fluorochromes for low-density phospho-epitopes",
                  "Cells destroyed (fixed) — cannot sort downstream"],
    },
    "ROS / Oxidative Stress": {
        "markers": [
            MarkerSpec("DCFH-DA", "", purpose="General intracellular ROS", is_surface=False),
            MarkerSpec("CellROX Green", "FITC", purpose="Cytoplasmic/nuclear ROS", is_surface=False),
            MarkerSpec("MitoSOX Red", "PE", purpose="Mitochondrial superoxide", is_surface=False),
        ],
        "fixation": "none",
        "categories": ["oxidative_stress", "ros", "cytotoxicity"],
        "notes": ["Load probes BEFORE stimulus (30 min pre-incubation)",
                  "Material degradation products, crosslinker residuals → ROS generation"],
    },
    "Cell Cycle": {
        "markers": [
            MarkerSpec("PI (DNA)", "", purpose="DNA content for G0/G1/S/G2/M phases", is_surface=False),
            MarkerSpec("Ki-67", "FITC", purpose="Proliferation marker (all active phases)",
                       is_surface=False, antigen_density="medium"),
            MarkerSpec("BrdU/EdU", "APC", purpose="S-phase (active DNA synthesis)",
                       is_surface=False),
        ],
        "fixation": "70% ethanol (cold)",
        "permeabilisation": "ethanol",
        "categories": ["proliferation", "cell_cycle"],
        "notes": ["RNase treatment required for clean PI histogram",
                  "EdU (click chemistry) preferred over BrdU (no DNA denaturation needed)"],
    },
    "Endothelial Identity": {
        "markers": [
            MarkerSpec("CD31 (PECAM-1)", "PE", purpose="Endothelial marker", antigen_density="high"),
            MarkerSpec("CD34", "FITC", purpose="Endothelial progenitor", antigen_density="medium"),
            MarkerSpec("VE-cadherin (CD144)", "APC", purpose="Endothelial junction protein"),
            MarkerSpec("VEGFR2 (KDR)", "PE-Cy7", purpose="VEGF receptor — angiogenesis readout",
                       antigen_density="low"),
        ],
        "fixation": "none",
        "categories": ["endothelial", "angiogenesis", "vascularisation"],
        "notes": ["Relevant for scaffold vascularisation assessment",
                  "VEGFR2 is dim — assign brightest fluorochrome"],
    },
}


# ── Public Repositories ──────────────────────────────────────────────────────

FLOW_REPOSITORIES: List[Dict[str, str]] = [
    {
        "name": "FlowRepository",
        "url": "https://flowrepository.org/",
        "description": "Public FCS datasets linked to publications. Standard repository.",
    },
    {
        "name": "ImmPort",
        "url": "https://www.immport.org/",
        "description": "NIH-funded immunology data. Well-curated, flow-heavy.",
    },
]


# ── Question -> Application Mapping ──────────────────────────────────────────

_QUESTION_PATTERNS: Dict[str, List[str]] = {
    "viability": ["viab", "cytotox", "alive", "dead", "kill", "biocompat", "safe"],
    "identity": ["identity", "phenotype", "msc", "stem cell", "isct", "who are"],
    "inflammation": ["inflam", "macrophage", "m1", "m2", "foreign body", "immune",
                     "cytokine", "polariz"],
    "adhesion": ["adhesion", "integrin", "attach", "spread", "ecm", "receptor"],
    "signalling": ["signal", "phospho", "pfak", "pyap", "psmad", "perk", "mechano",
                   "pathway activation"],
    "oxidative_stress": ["ros", "oxidat", "reactive oxygen", "superoxide", "mitosox"],
    "proliferation": ["proliferat", "cell cycle", "growth", "divid", "ki-67"],
    "endothelial": ["endothel", "angiogen", "vascular", "cd31", "vegf"],
}


# ── Public API ────────────────────────────────────────────────────────────────

def recommend_panel(
    question: str,
    cell_type: str = "",
    material: str = "",
    instrument_channels: int = 8,
) -> PanelRecommendation:
    """
    Recommend flow cytometry panel(s) for a research question.

    Args:
        question:             free-text research question
        cell_type:            e.g. "MSC", "THP-1", "HUVEC"
        material:             e.g. "GelMA", "titanium"
        instrument_channels:  number of available fluorescence channels

    Returns:
        PanelRecommendation with designed panels and guidance.
    """
    full_text = f"{question} {cell_type} {material}".lower()

    # Match categories
    matched = set()
    for cat, keywords in _QUESTION_PATTERNS.items():
        if any(kw in full_text for kw in keywords):
            matched.add(cat)

    if not matched:
        matched = {"viability"}  # default to viability

    # Select matching panels
    panels = []
    for panel_name, info in APPLICATION_KB.items():
        panel_cats = set(info.get("categories", []))
        if not panel_cats & matched:
            continue

        markers = info["markers"]
        # Trim to instrument capacity
        if len(markers) > instrument_channels:
            markers = markers[:instrument_channels]

        pd_obj = PanelDesign(
            panel_name=panel_name,
            markers=markers,
            viability_dye="Zombie Aqua" if info.get("fixation") == "none" else "",
            fixation=info.get("fixation", ""),
            permeabilisation=info.get("permeabilisation", ""),
            instrument_min=min(len(markers), 4),
            protocol_notes=info.get("notes", []),
            n_colours=len(markers),
        )
        panels.append(pd_obj)

    # Recommend technique variant
    technique = _recommend_technique_variant(matched, instrument_channels)

    # Standard controls
    controls = [
        "Unstained control (autofluorescence baseline)",
        "Single-stain compensation controls (one per fluorochrome)",
        "FMO controls (Fluorescence Minus One) for gating dim markers",
        "Isotype controls (optional, FMO preferred)",
    ]

    # Acquisition notes
    acq_notes = [
        f"Instrument: minimum {instrument_channels} channels required",
        "Acquire ≥10,000 events in gate of interest for statistical power",
        "Set PMT voltages using unstained control before acquisition",
    ]

    analysis_notes = [
        "Gate hierarchy: FSC/SSC → singlets (FSC-H/FSC-A) → viability → markers",
        "Export as FCS 3.0/3.1 for analysis in FlowJo, Cytobank, or this app",
    ]

    return PanelRecommendation(
        question=question,
        panels=panels,
        technique=technique,
        controls=controls,
        acquisition_notes=acq_notes,
        analysis_notes=analysis_notes,
    )


def design_panel(
    markers: List[str],
    instrument_channels: int = 8,
) -> PanelDesign:
    """
    Design a custom panel by assigning fluorochromes to markers.

    Optimises: dim markers → brightest fluorochromes, avoids spectral overlap.
    """
    # Sort fluorochromes by brightness
    brightness_order = {"very_high": 0, "high": 1, "medium": 2, "low": 3}
    sorted_fluors = sorted(
        FLUOROCHROME_DB.items(),
        key=lambda x: brightness_order.get(x[1]["brightness"], 2),
    )

    available = [f[0] for f in sorted_fluors[:instrument_channels]]

    specs = []
    for i, marker in enumerate(markers[:instrument_channels]):
        fluor = available[i] if i < len(available) else ""
        specs.append(MarkerSpec(
            marker=marker,
            fluorochrome=fluor,
        ))

    return PanelDesign(
        panel_name="Custom Panel",
        markers=specs,
        n_colours=len(specs),
        instrument_min=min(len(specs), 4),
    )


def get_panels_for_question(question: str) -> List[str]:
    """Quick lookup: return panel names matching a question."""
    rec = recommend_panel(question)
    return [p.panel_name for p in rec.panels]


def _recommend_technique_variant(categories: set, n_channels: int) -> str:
    """Recommend flow technique variant based on needs."""
    if "signalling" in categories and n_channels < 10:
        return "Mass Cytometry (CyTOF) — 40+ markers, no spectral overlap, ideal for phospho panels"

    if n_channels > 20:
        return "Spectral Flow Cytometry — 30-40 channels with computational unmixing"

    total_markers = 0
    for cat in categories:
        for info in APPLICATION_KB.values():
            if cat in info.get("categories", []):
                total_markers += len(info["markers"])
                break

    if total_markers > 15:
        return "Spectral Flow Cytometry recommended for complex panel (>15 markers)"

    return "Conventional Flow Cytometry — suitable for this panel complexity"
