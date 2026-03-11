"""
Assay Recommender — research question -> prioritised analytical technology stack.

Given a research question, cell type, material, and budget constraints,
recommends the appropriate assays with cost/equipment flags and links
to downstream modules (bio_engine, tox_engine, materials_engine).

Public API:
    from experimental_engine.assay_recommender import (
        recommend_assays, AssayRecommendation, AssayStack,
        ASSAY_DATABASE, get_assays_for_question,
    )

    stack = recommend_assays(
        question="Is my material cytotoxic?",
        cell_type="MSC",
        material="GelMA hydrogel",
    )
    for rec in stack.recommendations:
        print(rec.assay_name, rec.tier, rec.cost_flag, rec.turnaround)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class AssayRecommendation:
    """Single assay recommendation."""
    assay_name:     str
    technique:      str                 # e.g. "Flow cytometry", "LC-MS", "RNA-seq"
    purpose:        str                 # what this assay answers
    tier:           int                 # 1=basic/day-one, 2=intermediate, 3=advanced
    cost_flag:      str                 # "low" | "medium" | "high" | "very_high"
    turnaround:     str                 # e.g. "1 day", "1-2 weeks"
    equipment:      str                 # required equipment
    accessibility:  str                 # "any_lab" | "core_facility" | "specialist"
    readout:        str                 # what you measure
    module_link:    str = ""            # which app module processes the data
    notes:          str = ""            # caveats, Matrigel warnings, etc.
    priority:       int = 0             # ranking within the stack (1 = do first)


@dataclass
class AssayStack:
    """Prioritised stack of assay recommendations for a research question."""
    question:           str
    cell_type:          str = ""
    material:           str = ""
    recommendations:    List[AssayRecommendation] = field(default_factory=list)
    summary:            str = ""
    n_tiers:            int = 3
    error:              Optional[str] = None


# ── Assay Knowledge Base ─────────────────────────────────────────────────────

ASSAY_DATABASE: Dict[str, Dict] = {
    # ── Viability & Cytotoxicity ──────────────────────────────────────
    "Live/Dead Staining": {
        "technique": "Fluorescence microscopy / Flow cytometry",
        "purpose": "Binary viability assessment — are cells alive or dead?",
        "tier": 1, "cost_flag": "low", "turnaround": "1 day",
        "equipment": "Fluorescence microscope or flow cytometer",
        "accessibility": "any_lab",
        "readout": "% live, % dead (calcein AM / ethidium homodimer or PI)",
        "module_link": "bio_engine.flow_data_processor",
        "categories": ["cytotoxicity", "viability", "biocompatibility"],
    },
    "MTT/MTS/WST Assay": {
        "technique": "Plate reader (absorbance)",
        "purpose": "Metabolic activity as viability proxy",
        "tier": 1, "cost_flag": "low", "turnaround": "1 day",
        "equipment": "Microplate reader",
        "accessibility": "any_lab",
        "readout": "Absorbance (OD) proportional to metabolic activity",
        "module_link": "",
        "categories": ["cytotoxicity", "viability", "proliferation"],
    },
    "LDH Release Assay": {
        "technique": "Plate reader (absorbance)",
        "purpose": "Membrane integrity — LDH leaks from damaged cells",
        "tier": 1, "cost_flag": "low", "turnaround": "1 day",
        "equipment": "Microplate reader",
        "accessibility": "any_lab",
        "readout": "LDH activity in conditioned media",
        "module_link": "",
        "categories": ["cytotoxicity", "viability"],
    },
    "Annexin V / Caspase Apoptosis": {
        "technique": "Flow cytometry",
        "purpose": "Distinguish apoptosis vs necrosis",
        "tier": 1, "cost_flag": "low", "turnaround": "1 day",
        "equipment": "Flow cytometer",
        "accessibility": "any_lab",
        "readout": "Early apoptosis (Annexin V+/PI-) vs late (Annexin V+/PI+)",
        "module_link": "bio_engine.flow_data_processor",
        "categories": ["cytotoxicity", "apoptosis", "viability"],
    },

    # ── Metabolic Screening ───────────────────────────────────────────
    "Lactate/Glucose Ratio": {
        "technique": "Bench analyser (YSI, Nova Biomedical)",
        "purpose": "Quick metabolic screen — glycolytic shift indicates stress",
        "tier": 1, "cost_flag": "low", "turnaround": "1 day",
        "equipment": "Bench metabolite analyser",
        "accessibility": "any_lab",
        "readout": "Lactate production, glucose consumption (mmol/L)",
        "module_link": "bio_engine.metabolomics",
        "categories": ["metabolism", "cytotoxicity", "hypoxia"],
    },
    "Seahorse XF (Agilent)": {
        "technique": "Extracellular flux analyser",
        "purpose": "Real-time mitochondrial respiration + glycolysis",
        "tier": 2, "cost_flag": "medium", "turnaround": "1-2 days",
        "equipment": "Seahorse XFe96/XFp analyser",
        "accessibility": "core_facility",
        "readout": "OCR (O2 consumption), ECAR (extracellular acidification)",
        "module_link": "",
        "categories": ["metabolism", "mitochondria", "hypoxia", "drug_delivery"],
    },

    # ── Transcriptomics ──────────────────────────────────────────────
    "Bulk RNA-seq": {
        "technique": "Next-generation sequencing",
        "purpose": "Genome-wide gene expression profiling",
        "tier": 2, "cost_flag": "medium", "turnaround": "1-2 weeks",
        "equipment": "Illumina sequencer (outsource to core)",
        "accessibility": "core_facility",
        "readout": "DEGs, pathway enrichment, full transcriptome",
        "module_link": "bio_engine.transcriptomics",
        "categories": ["gene_expression", "pathway", "identity", "mechanism"],
    },
    "scRNA-seq (10x Chromium)": {
        "technique": "Single-cell RNA sequencing",
        "purpose": "Cell-type-resolved transcriptomics, heterogeneity analysis",
        "tier": 3, "cost_flag": "high", "turnaround": "2-4 weeks",
        "equipment": "10x Chromium controller + Illumina sequencer",
        "accessibility": "specialist",
        "readout": "Per-cell transcriptomes, clusters, trajectory, cell type proportions",
        "module_link": "bio_engine.deconvolution",
        "categories": ["gene_expression", "identity", "heterogeneity", "mechanism"],
    },
    "Spatial Transcriptomics (Visium/Xenium)": {
        "technique": "Spatially resolved RNA profiling",
        "purpose": "Gene expression with spatial context in tissue sections",
        "tier": 3, "cost_flag": "very_high", "turnaround": "2-4 weeks",
        "equipment": "10x Visium or Xenium platform",
        "accessibility": "specialist",
        "readout": "Spatially resolved gene expression, tissue architecture",
        "module_link": "bio_engine.transcriptomics",
        "categories": ["gene_expression", "spatial", "tissue_interaction"],
        "notes": "Always preceded by H&E histology on serial section.",
    },
    "RT-qPCR Panel": {
        "technique": "Targeted gene expression",
        "purpose": "Validate specific gene targets from RNA-seq",
        "tier": 1, "cost_flag": "low", "turnaround": "1-2 days",
        "equipment": "qPCR machine",
        "accessibility": "any_lab",
        "readout": "Fold change for selected genes (5-20 targets)",
        "module_link": "",
        "categories": ["gene_expression", "validation"],
    },

    # ── Metabolomics ─────────────────────────────────────────────────
    "GC-MS Metabolomics": {
        "technique": "Gas chromatography - mass spectrometry",
        "purpose": "Primary metabolite screening (amino acids, organic acids, sugars)",
        "tier": 2, "cost_flag": "medium", "turnaround": "1-2 weeks",
        "equipment": "GC-MS instrument",
        "accessibility": "core_facility",
        "readout": "Identified metabolites + relative abundance",
        "module_link": "bio_engine.metabolomics",
        "categories": ["metabolism", "pathway", "mechanism"],
    },
    "LC-MS Untargeted Metabolomics": {
        "technique": "Liquid chromatography - mass spectrometry",
        "purpose": "Full metabolome profiling including lipids",
        "tier": 2, "cost_flag": "high", "turnaround": "2-4 weeks",
        "equipment": "LC-MS/MS (Q-TOF or Orbitrap)",
        "accessibility": "core_facility",
        "readout": "Comprehensive metabolite identification + quantification",
        "module_link": "bio_engine.metabolomics",
        "categories": ["metabolism", "pathway", "mechanism", "drug_delivery"],
    },
    "NMR Metabolomics": {
        "technique": "Nuclear magnetic resonance",
        "purpose": "Non-destructive metabolite profiling",
        "tier": 2, "cost_flag": "high", "turnaround": "1-2 weeks",
        "equipment": "NMR spectrometer (400+ MHz)",
        "accessibility": "specialist",
        "readout": "Metabolite identification + absolute quantification",
        "module_link": "bio_engine.metabolomics",
        "categories": ["metabolism", "pathway"],
    },

    # ── Proteomics ───────────────────────────────────────────────────
    "DIA Proteomics (Global)": {
        "technique": "Data-independent acquisition LC-MS/MS",
        "purpose": "Comprehensive proteome quantification",
        "tier": 2, "cost_flag": "high", "turnaround": "2-4 weeks",
        "equipment": "Orbitrap or timsTOF Pro",
        "accessibility": "specialist",
        "readout": "Protein abundance (5000+ proteins), differential expression",
        "module_link": "experimental_engine.proteomics_client",
        "categories": ["proteomics", "mechanism", "pathway"],
    },
    "Phosphoproteomics": {
        "technique": "TiO2/Fe-IMAC enrichment + LC-MS/MS",
        "purpose": "Map active signalling cascades (pFAK, pYAP, pSmad, pERK)",
        "tier": 3, "cost_flag": "very_high", "turnaround": "3-6 weeks",
        "equipment": "Mass spec + phospho-enrichment workflow",
        "accessibility": "specialist",
        "readout": "Phosphorylation sites, kinase activity inference",
        "module_link": "experimental_engine.proteomics_client",
        "categories": ["proteomics", "signalling", "mechanosensing"],
    },
    "Protein Corona Analysis": {
        "technique": "Material incubation + LC-MS/MS",
        "purpose": "Identify proteins adsorbed onto material surface from serum",
        "tier": 2, "cost_flag": "high", "turnaround": "2-4 weeks",
        "equipment": "Mass spec",
        "accessibility": "specialist",
        "readout": "Hard/soft corona composition, complement activation flag",
        "module_link": "experimental_engine.proteomics_client",
        "categories": ["proteomics", "biocompatibility", "immune_response"],
    },
    "ELISA / Luminex": {
        "technique": "Immunoassay (plate or bead-based)",
        "purpose": "Quantify specific cytokines/growth factors in conditioned media",
        "tier": 1, "cost_flag": "medium", "turnaround": "1-2 days",
        "equipment": "Plate reader or Luminex instrument",
        "accessibility": "any_lab",
        "readout": "pg/mL of target proteins (TNF-a, IL-6, IL-1b, VEGF, etc.)",
        "module_link": "",
        "categories": ["cytokines", "inflammation", "immune_response", "biocompatibility"],
    },

    # ── Flow Cytometry ───────────────────────────────────────────────
    "Surface Immunophenotyping (Flow)": {
        "technique": "Flow cytometry",
        "purpose": "Identify cell surface markers, confirm cell identity",
        "tier": 1, "cost_flag": "low", "turnaround": "1 day",
        "equipment": "Flow cytometer (4+ colour)",
        "accessibility": "any_lab",
        "readout": "% positive cells per marker, MFI",
        "module_link": "bio_engine.flow_data_processor",
        "categories": ["identity", "phenotyping", "stem_cell"],
    },
    "Phospho-flow": {
        "technique": "Intracellular flow cytometry",
        "purpose": "Population-level signalling pathway activation",
        "tier": 2, "cost_flag": "medium", "turnaround": "1-2 days",
        "equipment": "Flow cytometer + fix/perm kit",
        "accessibility": "core_facility",
        "readout": "pFAK, pYAP, pSmad2/3, pERK — % positive, MFI shift",
        "module_link": "bio_engine.flow_data_processor",
        "categories": ["signalling", "mechanosensing", "pathway"],
    },
    "ROS Detection (Flow)": {
        "technique": "Flow cytometry with ROS probes",
        "purpose": "Quantify oxidative stress from material exposure",
        "tier": 1, "cost_flag": "low", "turnaround": "1 day",
        "equipment": "Flow cytometer",
        "accessibility": "any_lab",
        "readout": "DCFH-DA / CellROX / MitoSOX fluorescence intensity",
        "module_link": "bio_engine.flow_data_processor",
        "categories": ["oxidative_stress", "cytotoxicity", "biocompatibility"],
    },
    "Cell Cycle (Flow)": {
        "technique": "DNA content analysis (PI/DAPI) + BrdU/EdU",
        "purpose": "Proliferation status, cell cycle distribution",
        "tier": 1, "cost_flag": "low", "turnaround": "1 day",
        "equipment": "Flow cytometer",
        "accessibility": "any_lab",
        "readout": "G0/G1, S, G2/M percentages; S-phase fraction",
        "module_link": "bio_engine.flow_data_processor",
        "categories": ["proliferation", "cell_cycle"],
    },

    # ── Microscopy ───────────────────────────────────────────────────
    "SEM (Scanning Electron Microscopy)": {
        "technique": "Electron microscopy",
        "purpose": "Surface morphology, scaffold architecture, cell attachment",
        "tier": 1, "cost_flag": "medium", "turnaround": "1-3 days",
        "equipment": "SEM (standard or FE-SEM)",
        "accessibility": "core_facility",
        "readout": "Surface topography images, pore size measurement",
        "module_link": "experimental_engine.microscopy_advisor",
        "categories": ["morphology", "scaffold", "cell_attachment"],
    },
    "Confocal CLSM": {
        "technique": "Confocal laser scanning microscopy",
        "purpose": "Cell distribution, cytoskeleton, marker co-localisation in 3D",
        "tier": 1, "cost_flag": "medium", "turnaround": "1-2 days",
        "equipment": "Confocal microscope",
        "accessibility": "core_facility",
        "readout": "Z-stacks, 3D reconstruction, fluorescence intensity",
        "module_link": "experimental_engine.microscopy_advisor",
        "categories": ["morphology", "cell_attachment", "identity", "spatial"],
    },
    "Two-photon SHG": {
        "technique": "Second harmonic generation microscopy",
        "purpose": "Label-free collagen fibril imaging in scaffolds",
        "tier": 2, "cost_flag": "high", "turnaround": "1-3 days",
        "equipment": "Two-photon microscope",
        "accessibility": "specialist",
        "readout": "Collagen fibre organisation, scaffold remodelling",
        "module_link": "experimental_engine.microscopy_advisor",
        "categories": ["ecm", "collagen", "scaffold", "remodelling"],
    },

    # ── Mechanical Testing ───────────────────────────────────────────
    "Rheology": {
        "technique": "Oscillatory shear rheometry",
        "purpose": "Hydrogel mechanical properties (G', G'', gelation kinetics)",
        "tier": 1, "cost_flag": "medium", "turnaround": "1 day",
        "equipment": "Rheometer (parallel plate or cone-plate)",
        "accessibility": "core_facility",
        "readout": "Storage modulus (G'), loss modulus (G''), gelation time",
        "module_link": "",
        "categories": ["mechanical", "hydrogel", "scaffold"],
    },
    "AFM Force Spectroscopy": {
        "technique": "Atomic force microscopy indentation",
        "purpose": "Local stiffness mapping, nanoscale mechanical properties",
        "tier": 2, "cost_flag": "high", "turnaround": "2-5 days",
        "equipment": "AFM with force spectroscopy module",
        "accessibility": "specialist",
        "readout": "Young's modulus map, force-distance curves",
        "module_link": "experimental_engine.microscopy_advisor",
        "categories": ["mechanical", "stiffness", "mechanosensing"],
    },

    # ── Degradation / Drug Release ───────────────────────────────────
    "HPLC-UV Drug Release": {
        "technique": "High-performance liquid chromatography",
        "purpose": "Quantify drug release from scaffold over time",
        "tier": 1, "cost_flag": "medium", "turnaround": "1-2 weeks (time course)",
        "equipment": "HPLC with UV detector",
        "accessibility": "any_lab",
        "readout": "Cumulative drug release (%) vs time",
        "module_link": "drug_engine",
        "categories": ["drug_delivery", "release_kinetics"],
    },
    "GC-MS Degradation Products": {
        "technique": "GC-MS headspace / conditioned media",
        "purpose": "Identify volatile/semi-volatile degradation products",
        "tier": 2, "cost_flag": "medium", "turnaround": "1-2 weeks",
        "equipment": "GC-MS",
        "accessibility": "core_facility",
        "readout": "Identified degradation compounds, concentration estimates",
        "module_link": "tox_engine",
        "categories": ["degradation", "cytotoxicity", "biocompatibility"],
    },
}


# ── Question -> Category Mapping ─────────────────────────────────────────────

_QUESTION_PATTERNS: Dict[str, List[str]] = {
    "cytotoxicity": [
        "cytotoxic", "toxic", "kill", "biocompatible", "biocompatibility",
        "safe", "viability", "alive", "dead", "harm",
    ],
    "metabolism": [
        "metabol", "glycoly", "warburg", "mitochondri", "respir",
        "lactate", "glucose", "metabolic state", "energy",
    ],
    "gene_expression": [
        "gene", "transcript", "rna", "express", "deg", "pathway",
        "differentially expressed", "upregulat", "downregulat",
    ],
    "identity": [
        "identity", "phenotype", "differentiat", "stem cell",
        "osteogenic", "chondrogenic", "adipogenic", "lineage",
    ],
    "mechanosensing": [
        "stiffness", "mechano", "yap", "taz", "focal adhesion",
        "integrin", "force", "substrate", "modulus",
    ],
    "drug_delivery": [
        "drug", "release", "deliver", "encapsulat", "payload",
        "therapeutic", "dosing", "burst release",
    ],
    "inflammation": [
        "inflam", "immune", "foreign body", "macrophage", "cytokine",
        "tnf", "il-6", "il-1", "m1", "m2", "polariz",
    ],
    "morphology": [
        "morpholog", "scaffold", "pore", "architecture", "surface",
        "attach", "spread", "topograph",
    ],
    "degradation": [
        "degrad", "erosion", "breakdown", "dissolv", "resorb",
    ],
    "proliferation": [
        "proliferat", "growth", "divid", "cell cycle", "expand",
    ],
    "proteomics": [
        "proteom", "protein", "corona", "phospho", "secretome",
        "integrin express",
    ],
    "oxidative_stress": [
        "ros", "oxidative", "reactive oxygen", "free radical",
        "antioxidant", "stress",
    ],
    "full_mechanistic": [
        "full picture", "mechanistic", "multi-omics", "comprehensive",
        "everything",
    ],
}


# ── Public API ────────────────────────────────────────────────────────────────

def recommend_assays(
    question: str,
    cell_type: str = "",
    material: str = "",
    budget: str = "medium",
    max_tier: int = 3,
) -> AssayStack:
    """
    Recommend assays based on a research question.

    Args:
        question:   free-text research question
        cell_type:  e.g. "MSC", "ARPE-19", "HeLa"
        material:   e.g. "GelMA hydrogel", "PCL scaffold"
        budget:     "low" | "medium" | "high" (filters max cost)
        max_tier:   maximum tier to include (1-3)

    Returns:
        AssayStack with prioritised recommendations.
    """
    categories = _match_categories(question)

    if not categories:
        # Default to broad biocompatibility screen
        categories = {"cytotoxicity", "viability", "morphology"}

    # Collect matching assays
    cost_order = {"low": 1, "medium": 2, "high": 3, "very_high": 4}
    budget_max = cost_order.get(budget, 3)

    recommendations = []
    seen = set()

    for assay_name, info in ASSAY_DATABASE.items():
        assay_cats = set(info.get("categories", []))
        if not assay_cats & categories:
            continue

        if info["tier"] > max_tier:
            continue

        if cost_order.get(info["cost_flag"], 3) > budget_max:
            continue

        if assay_name in seen:
            continue
        seen.add(assay_name)

        # Relevance score: more category overlap = higher priority
        relevance = len(assay_cats & categories)

        rec = AssayRecommendation(
            assay_name=assay_name,
            technique=info["technique"],
            purpose=info["purpose"],
            tier=info["tier"],
            cost_flag=info["cost_flag"],
            turnaround=info["turnaround"],
            equipment=info["equipment"],
            accessibility=info["accessibility"],
            readout=info["readout"],
            module_link=info.get("module_link", ""),
            notes=info.get("notes", ""),
            priority=0,
        )
        recommendations.append((relevance, rec))

    # Sort: tier ASC, relevance DESC, cost ASC
    recommendations.sort(key=lambda x: (x[1].tier, -x[0], cost_order.get(x[1].cost_flag, 3)))

    for i, (_, rec) in enumerate(recommendations, 1):
        rec.priority = i

    recs = [rec for _, rec in recommendations]

    # Build summary
    tier_counts = {}
    for r in recs:
        tier_counts[r.tier] = tier_counts.get(r.tier, 0) + 1

    summary_parts = [f"Question: {question}"]
    if cell_type:
        summary_parts.append(f"Cell type: {cell_type}")
    if material:
        summary_parts.append(f"Material: {material}")
    summary_parts.append(f"Matched categories: {', '.join(sorted(categories))}")
    summary_parts.append(
        f"Recommendations: {len(recs)} assays across "
        + ", ".join(f"Tier {t}: {n}" for t, n in sorted(tier_counts.items()))
    )

    return AssayStack(
        question=question,
        cell_type=cell_type,
        material=material,
        recommendations=recs,
        summary="\n".join(summary_parts),
    )


def get_assays_for_question(question: str) -> List[str]:
    """Quick lookup: return list of assay names matching a question."""
    stack = recommend_assays(question)
    return [r.assay_name for r in stack.recommendations]


def get_assays_by_category(category: str) -> List[str]:
    """Return assay names that belong to a specific category."""
    return [
        name for name, info in ASSAY_DATABASE.items()
        if category in info.get("categories", [])
    ]


def get_assays_by_tier(tier: int) -> List[str]:
    """Return assay names at a specific tier level."""
    return [
        name for name, info in ASSAY_DATABASE.items()
        if info.get("tier") == tier
    ]


# ── Internal helpers ─────────────────────────────────────────────────────────

def _match_categories(question: str) -> set:
    """Match a free-text question to assay categories."""
    q_lower = question.lower()
    matched = set()
    for category, keywords in _QUESTION_PATTERNS.items():
        if any(kw in q_lower for kw in keywords):
            matched.add(category)

    # Full mechanistic -> add everything
    if "full_mechanistic" in matched:
        matched.update([
            "cytotoxicity", "metabolism", "gene_expression",
            "proteomics", "morphology",
        ])

    return matched
