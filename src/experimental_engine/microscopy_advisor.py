"""
Microscopy Advisor — technique selection, sample preparation guidance,
and links to public image databases for biomaterials research.

Covers: SEM/TEM/Cryo variants, AFM, confocal, two-photon/SHG, FLIM,
light sheet, super-resolution, histology, and intravital microscopy.

Public API:
    from experimental_engine.microscopy_advisor import (
        recommend_technique, MicroscopyRecommendation,
        TECHNIQUE_DATABASE, IMAGE_DATABASES,
        get_sample_prep, get_techniques_for_question,
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class MicroscopyRecommendation:
    """Single microscopy technique recommendation."""
    technique:          str
    variant:            str = ""            # e.g. "FE-SEM", "Cryo-SEM"
    purpose:            str = ""
    resolution:         str = ""            # e.g. "~1 nm", "~200 nm"
    sample_state:       str = ""            # "fixed" | "live" | "cryo" | "cleared"
    sample_prep:        List[str] = field(default_factory=list)
    advantages:         List[str] = field(default_factory=list)
    limitations:        List[str] = field(default_factory=list)
    cost:               str = "medium"      # "low" | "medium" | "high"
    accessibility:      str = "core_facility"
    readout:            str = ""
    biomaterial_notes:  str = ""            # specific biomaterial relevance
    priority:           int = 0


@dataclass
class MicroscopyReport:
    """Full microscopy recommendation report."""
    question:           str
    recommendations:    List[MicroscopyRecommendation] = field(default_factory=list)
    sample_prep_notes:  List[str] = field(default_factory=list)
    image_databases:    List[Dict] = field(default_factory=list)
    error:              Optional[str] = None


# ── Technique Database ───────────────────────────────────────────────────────

TECHNIQUE_DATABASE: Dict[str, Dict] = {
    "SEM": {
        "technique": "Scanning Electron Microscopy",
        "variant": "Standard SEM",
        "purpose": "Surface morphology, scaffold architecture, pore geometry, cell attachment",
        "resolution": "~1-10 nm",
        "sample_state": "fixed, dried, conductive coating",
        "sample_prep": [
            "Fix (glutaraldehyde 2.5% in PBS, 1h)",
            "Dehydrate (graded ethanol: 30-50-70-90-100%)",
            "Critical point dry or air dry",
            "Sputter coat (Au/Pd, 5-10 nm)",
        ],
        "advantages": ["High resolution surface imaging", "3D topography", "Wide availability"],
        "limitations": ["Dry sample only — hydrogel collapses", "Conductive coating artefacts",
                        "Fixation/dehydration alters cell morphology"],
        "cost": "medium",
        "accessibility": "core_facility",
        "readout": "Surface topography, pore size, cell spreading area",
        "biomaterial_notes": "First choice for scaffold architecture. Flag: hydrogel samples need Cryo-SEM.",
        "categories": ["morphology", "scaffold", "nanoscale", "cell_attachment"],
    },
    "Cryo-SEM": {
        "technique": "Cryo Scanning Electron Microscopy",
        "variant": "Cryo-SEM",
        "purpose": "Hydrated scaffold microstructure preserved in vitrified state",
        "resolution": "~10-50 nm",
        "sample_state": "cryo (vitrified)",
        "sample_prep": [
            "Plunge freeze in liquid ethane/nitrogen slush",
            "Transfer to cryo stage under vacuum",
            "Sublimate ice layer if needed",
            "No coating required (or thin Pt sputter at cryo)",
        ],
        "advantages": ["Preserves hydrated state", "No dehydration artefacts",
                        "Gold standard for hydrogel architecture"],
        "limitations": ["Not universally available", "Lower resolution than FE-SEM",
                        "Challenging sample transfer"],
        "cost": "high",
        "accessibility": "specialist",
        "readout": "Hydrogel pore network, swelling state, ice crystal structure",
        "biomaterial_notes": "Required for hydrogels (GelMA, alginate, PEG-based). Standard SEM collapses hydrated pores.",
        "categories": ["morphology", "scaffold", "hydrogel"],
    },
    "FE-SEM": {
        "technique": "Field Emission SEM",
        "variant": "FE-SEM",
        "purpose": "High-resolution surface nanostructure imaging",
        "resolution": "~1 nm",
        "sample_state": "fixed, dried",
        "sample_prep": ["Same as SEM", "Lower kV imaging possible (less charging)"],
        "advantages": ["Higher resolution", "Better for nanofibers/nanoparticles",
                        "Low-kV reduces charging on polymers"],
        "limitations": ["Same drying artefacts as standard SEM"],
        "cost": "medium",
        "accessibility": "core_facility",
        "readout": "Nanofiber diameter, nanoparticle distribution, surface nanostructure",
        "biomaterial_notes": "Best for electrospun scaffolds, MEW fibres, nanoparticle coatings.",
        "categories": ["morphology", "nanoscale", "scaffold"],
    },
    "TEM": {
        "technique": "Transmission Electron Microscopy",
        "variant": "Standard TEM",
        "purpose": "Internal ultrastructure, cross-sections, nanomaterial characterisation",
        "resolution": "~0.2 nm",
        "sample_state": "fixed, ultrathin sections (80-100 nm)",
        "sample_prep": [
            "Fix (glutaraldehyde + OsO4)",
            "Dehydrate and embed in resin (Epon/Araldite)",
            "Ultramicrotome sectioning (80-100 nm)",
            "Heavy metal stain (uranyl acetate, lead citrate)",
        ],
        "advantages": ["Atomic-level resolution", "Internal structure visible",
                        "Organelle-level cell response"],
        "limitations": ["Intensive sample prep", "Small field of view",
                        "Fixation artefacts at ultrastructural level"],
        "cost": "high",
        "accessibility": "specialist",
        "readout": "Cell organelle response, nanoparticle internalisation, fibril spacing",
        "biomaterial_notes": "Use for nanoparticle cellular uptake, collagen fibril D-periodicity in scaffolds.",
        "categories": ["ultrastructure", "nanoscale", "nanoparticle"],
    },
    "Cryo-TEM": {
        "technique": "Cryo Transmission Electron Microscopy",
        "variant": "Cryo-TEM",
        "purpose": "Vitrified nanostructure — LNPs, vesicles, protein assemblies",
        "resolution": "~1-3 nm",
        "sample_state": "cryo (vitrified thin film)",
        "sample_prep": [
            "Blot thin film on grid",
            "Plunge freeze in liquid ethane",
            "Image at cryo temperature (-170°C)",
        ],
        "advantages": ["No staining artefacts", "Native nanostructure preserved",
                        "Gold standard for LNP and vesicle imaging"],
        "limitations": ["Expensive", "Specialist operation", "Low throughput"],
        "cost": "high",
        "accessibility": "specialist",
        "readout": "Nanoparticle internal structure, LNP morphology, protein corona",
        "biomaterial_notes": "Required for drug delivery LNPs, exosome characterisation, protein corona morphology.",
        "categories": ["nanoscale", "nanoparticle", "drug_delivery"],
    },
    "AFM": {
        "technique": "Atomic Force Microscopy",
        "variant": "Standard / Force Spectroscopy",
        "purpose": "Nanoscale topography + local mechanical properties in liquid",
        "resolution": "~1-10 nm (topography), ~100 nm (force map)",
        "sample_state": "live or fixed, can be in liquid",
        "sample_prep": [
            "Adhere sample to substrate (glass, mica)",
            "Can image in PBS (live) or after fixation",
            "No coating needed",
        ],
        "advantages": ["Physiological conditions (liquid)", "Mechanical + topography simultaneously",
                        "Force curves give local Young's modulus"],
        "limitations": ["Slow (minutes per image)", "Small scan area (<100 um)",
                        "Probe tip can damage soft samples"],
        "cost": "high",
        "accessibility": "specialist",
        "readout": "Surface roughness (Ra), Young's modulus map, adhesion force",
        "biomaterial_notes": "Maps stiffness gradients in composite scaffolds. Links to YAP/TAZ mechanosensing data.",
        "categories": ["mechanical", "stiffness", "nanoscale", "mechanosensing"],
    },
    "Confocal": {
        "technique": "Confocal Laser Scanning Microscopy",
        "variant": "CLSM",
        "purpose": "Cell distribution, cytoskeleton, marker co-localisation, Z-stacks",
        "resolution": "~200 nm XY, ~500 nm Z",
        "sample_state": "fixed or live (with environmental chamber)",
        "sample_prep": [
            "Fix (4% PFA, 15-30 min) — or image live",
            "Permeabilise (0.1% Triton X-100, 5 min) if intracellular staining",
            "Stain: phalloidin (actin), DAPI (nuclei), specific antibodies",
            "Mount on glass coverslip",
        ],
        "advantages": ["Optical sectioning (Z-stacks)", "3D reconstruction",
                        "Live imaging possible", "Widely available"],
        "limitations": ["Limited penetration depth (~100 um)", "Photobleaching",
                        "Diffraction-limited resolution"],
        "cost": "medium",
        "accessibility": "core_facility",
        "readout": "Cell morphology, marker localisation, scaffold colonisation depth",
        "biomaterial_notes": "Standard for cell-scaffold imaging. Z-stacks show depth of cell infiltration.",
        "categories": ["cell_morphology", "cell_attachment", "spatial", "live"],
    },
    "Two-Photon SHG": {
        "technique": "Two-Photon / Second Harmonic Generation",
        "variant": "Multiphoton + SHG",
        "purpose": "Label-free collagen fibril imaging, deep tissue penetration",
        "resolution": "~300 nm XY",
        "sample_state": "live or fixed, no label needed for SHG",
        "sample_prep": ["Minimal — can image scaffold directly", "No staining for SHG"],
        "advantages": ["Label-free collagen imaging (SHG)", "Deep tissue (~1 mm)",
                        "Less phototoxic than confocal", "Discriminates collagen types"],
        "limitations": ["Expensive instrument", "Not universally available"],
        "cost": "high",
        "accessibility": "specialist",
        "readout": "Collagen fibre organisation, scaffold remodelling, fibre alignment",
        "biomaterial_notes": "First choice for collagen-containing scaffolds. Collagen I shows strong SHG; collagen IV does not.",
        "categories": ["ecm", "collagen", "scaffold", "label_free"],
    },
    "FLIM": {
        "technique": "Fluorescence Lifetime Imaging Microscopy",
        "variant": "NAD(P)H FLIM",
        "purpose": "Spatial metabolic state mapping without metabolite extraction",
        "resolution": "~200 nm XY",
        "sample_state": "live (endogenous fluorescence)",
        "sample_prep": ["No staining needed", "Image in phenol-red-free media"],
        "advantages": ["Label-free metabolic readout", "Spatial information",
                        "Distinguishes glycolysis vs OXPHOS in situ"],
        "limitations": ["Specialist instrument + analysis", "Requires careful calibration"],
        "cost": "high",
        "accessibility": "specialist",
        "readout": "NAD(P)H lifetime: short = glycolytic, long = OXPHOS",
        "biomaterial_notes": "Detects Warburg shift under material-induced hypoxia. Complementary to metabolomics.",
        "categories": ["metabolism", "hypoxia", "live", "label_free"],
    },
    "Light Sheet": {
        "technique": "Light Sheet Fluorescence Microscopy",
        "variant": "LSFM / SPIM",
        "purpose": "Whole-organoid / whole-scaffold imaging at single-cell resolution",
        "resolution": "~300 nm XY, ~1 um Z",
        "sample_state": "cleared or transparent",
        "sample_prep": [
            "Fix and optionally clear (CUBIC, iDISCO, or CLARITY)",
            "Mount in refractive-index-matched medium",
            "Stain (immunofluorescence or endogenous reporters)",
        ],
        "advantages": ["Very low photobleaching", "Entire organoid in 3D",
                        "Single-cell resolution across large volumes"],
        "limitations": ["Requires tissue clearing for opaque samples",
                        "Large datasets (TB per sample)", "Specialist alignment"],
        "cost": "high",
        "accessibility": "specialist",
        "readout": "3D cell distribution, organoid architecture, scaffold colonisation",
        "biomaterial_notes": "Best for organoid-on-scaffold imaging. Clearing protocol depends on sample.",
        "categories": ["spatial", "organoid", "scaffold", "3d"],
    },
    "Super-Resolution (STORM/PALM)": {
        "technique": "Stochastic Optical Reconstruction Microscopy",
        "variant": "STORM / PALM",
        "purpose": "Nanoscale receptor distribution on material surfaces",
        "resolution": "~20 nm",
        "sample_state": "fixed",
        "sample_prep": [
            "Fix (4% PFA)",
            "Immunostain with photoswitchable dyes (Alexa Fluor 647)",
            "Imaging buffer (thiol + O2 scavenger for STORM)",
        ],
        "advantages": ["~20 nm resolution (10x better than confocal)",
                        "Single-molecule sensitivity", "Quantitative cluster analysis"],
        "limitations": ["Fixed samples only", "Long acquisition (minutes per FOV)",
                        "Complex analysis pipeline"],
        "cost": "high",
        "accessibility": "specialist",
        "readout": "Integrin nanocluster size/density, focal adhesion organisation",
        "biomaterial_notes": "Maps integrin nanoclusters on material surfaces. Links to mechanosensing and adhesion data.",
        "categories": ["nanoscale", "receptor", "mechanosensing"],
    },
    "H&E Histology": {
        "technique": "Haematoxylin & Eosin staining",
        "variant": "Standard histology",
        "purpose": "Tissue morphology, cellularity, necrosis assessment",
        "resolution": "~1 um (optical)",
        "sample_state": "fixed, paraffin-embedded sections",
        "sample_prep": [
            "Fix (10% NBF or 4% PFA)",
            "Process (dehydrate, clear, embed in paraffin)",
            "Section (4-5 um microtome)",
            "Stain H&E",
        ],
        "advantages": ["Gold standard morphology", "Any pathology lab",
                        "Prerequisite for spatial transcriptomics"],
        "limitations": ["No molecular information", "2D sections only"],
        "cost": "low",
        "accessibility": "any_lab",
        "readout": "Tissue architecture, cell infiltration, necrosis, fibrous capsule",
        "biomaterial_notes": "Must precede spatial transcriptomics (Visium/Xenium). Essential for in vivo implant assessment.",
        "categories": ["morphology", "tissue", "histology", "in_vivo"],
    },
}


# ── Public Image Databases ───────────────────────────────────────────────────

IMAGE_DATABASES: List[Dict[str, str]] = [
    {
        "name": "BioImage Archive",
        "url": "https://www.ebi.ac.uk/bioimage-archive/",
        "description": "Primary repository for bioimaging datasets (EMBL-EBI). Free access.",
    },
    {
        "name": "Image Data Resource (IDR)",
        "url": "https://idr.openmicroscopy.org/",
        "description": "Curated high-content screening, confocal, EM datasets. Queryable.",
    },
    {
        "name": "OMERO",
        "url": "https://www.openmicroscopy.org/omero/",
        "description": "Open Microscopy Environment — institutional image management platform.",
    },
    {
        "name": "EMPIAR",
        "url": "https://www.ebi.ac.uk/empiar/",
        "description": "Electron Microscopy Public Image Archive. Cryo-EM/ET maps and raw data.",
    },
    {
        "name": "Allen Brain Atlas",
        "url": "https://portal.brain-map.org/",
        "description": "Brain region imaging — relevant for neural biomaterials.",
    },
]


# ── Question -> Technique Mapping ────────────────────────────────────────────

_QUESTION_PATTERNS: Dict[str, List[str]] = {
    "morphology": ["morpholog", "look like", "shape", "appearance", "cell shape"],
    "scaffold": ["scaffold", "pore", "architecture", "structure", "fibr"],
    "nanoscale": ["nanoscale", "nano", "nanoparticle", "nanofiber", "surface feature"],
    "cell_attachment": ["attach", "spread", "adhes", "contact", "seed"],
    "collagen": ["collagen", "ecm", "extracellular matrix", "remodel"],
    "mechanical": ["stiffness", "modulus", "mechanic", "force", "elast"],
    "mechanosensing": ["yap", "taz", "focal adhesion", "mechanosens", "integrin cluster"],
    "metabolism": ["metabol", "glycoly", "oxphos", "warburg", "hypoxia"],
    "spatial": ["spatial", "where", "localiz", "distribut", "infiltrat"],
    "live": ["live", "real-time", "time-lapse", "dynamic"],
    "organoid": ["organoid", "spheroid", "3d culture", "whole mount"],
    "nanoparticle": ["nanoparticle", "lnp", "vesicle", "liposome", "exosome"],
    "receptor": ["receptor", "integrin nano", "cluster"],
    "histology": ["histol", "h&e", "tissue section", "implant"],
    "hydrogel": ["hydrogel", "gelma", "alginate", "peg hydrogel"],
    "in_vivo": ["in vivo", "implant", "animal", "tissue response"],
}


# ── Public API ────────────────────────────────────────────────────────────────

def recommend_technique(
    question: str,
    sample_type: str = "",
    material: str = "",
) -> MicroscopyReport:
    """
    Recommend microscopy techniques based on a research question.

    Args:
        question:    free-text question (e.g. "What does my scaffold look like?")
        sample_type: e.g. "hydrogel", "electrospun scaffold", "organoid"
        material:    e.g. "GelMA", "PCL", "PLGA"

    Returns:
        MicroscopyReport with ranked technique recommendations.
    """
    full_text = f"{question} {sample_type} {material}".lower()
    categories = set()
    for cat, keywords in _QUESTION_PATTERNS.items():
        if any(kw in full_text for kw in keywords):
            categories.add(cat)

    if not categories:
        categories = {"morphology", "scaffold"}

    recommendations = []

    for tech_id, info in TECHNIQUE_DATABASE.items():
        tech_cats = set(info.get("categories", []))
        if not tech_cats & categories:
            continue

        relevance = len(tech_cats & categories)

        rec = MicroscopyRecommendation(
            technique=info["technique"],
            variant=info.get("variant", ""),
            purpose=info["purpose"],
            resolution=info["resolution"],
            sample_state=info["sample_state"],
            sample_prep=info.get("sample_prep", []),
            advantages=info.get("advantages", []),
            limitations=info.get("limitations", []),
            cost=info.get("cost", "medium"),
            accessibility=info.get("accessibility", "core_facility"),
            readout=info["readout"],
            biomaterial_notes=info.get("biomaterial_notes", ""),
        )
        recommendations.append((relevance, rec))

    # Sort: relevance DESC, cost ASC
    cost_order = {"low": 1, "medium": 2, "high": 3}
    recommendations.sort(key=lambda x: (-x[0], cost_order.get(x[1].cost, 2)))

    for i, (_, rec) in enumerate(recommendations, 1):
        rec.priority = i

    recs = [rec for _, rec in recommendations]

    # Sample prep notes
    prep_notes = _get_sample_prep_notes(full_text)

    return MicroscopyReport(
        question=question,
        recommendations=recs,
        sample_prep_notes=prep_notes,
        image_databases=IMAGE_DATABASES,
    )


def get_techniques_for_question(question: str) -> List[str]:
    """Quick lookup: return technique names matching a question."""
    report = recommend_technique(question)
    return [r.technique for r in report.recommendations]


def get_sample_prep(technique_id: str) -> List[str]:
    """Return sample prep steps for a technique."""
    info = TECHNIQUE_DATABASE.get(technique_id, {})
    return info.get("sample_prep", [])


def _get_sample_prep_notes(text: str) -> List[str]:
    """Context-specific sample preparation notes."""
    notes = []
    if "hydrogel" in text or "gelma" in text:
        notes.append(
            "Hydrogel samples: standard SEM dehydration collapses pore network. "
            "Use Cryo-SEM for true hydrated architecture."
        )
    if "organoid" in text or "spheroid" in text:
        notes.append(
            "Organoid/spheroid samples: consider tissue clearing (CUBIC or iDISCO) "
            "before light sheet imaging for intact 3D visualisation."
        )
    if "collagen" in text or "ecm" in text:
        notes.append(
            "Collagen imaging: Two-photon SHG provides label-free fibril visualisation. "
            "Note: Collagen I shows strong SHG, collagen IV does not."
        )
    if "live" in text or "dynamic" in text:
        notes.append(
            "Live imaging: use spinning disk confocal for reduced photobleaching "
            "during time-lapse. Environmental chamber (37°C, CO2) required."
        )
    if "implant" in text or "in vivo" in text:
        notes.append(
            "In vivo implant: H&E histology on serial sections is mandatory. "
            "Always perform before spatial transcriptomics."
        )
    return notes
