"""
Cell Models Knowledge Base -- curated in vitro models for biomaterials testing.
===============================================================================
Covers cell lines and primary cell types used in ISO 10993 testing,
differentiation assays, and tissue-specific biocompatibility studies.

Usage:
    from experimental_engine.cell_models_db import get_models_for_tissue, ALL_CELL_MODELS

    bone_models = get_models_for_tissue("bone")
    iso_models  = get_iso10993_models()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class CellModel:
    name:           str
    full_name:      str
    species:        str              # Human / Mouse / Rat / Porcine / Bovine
    cell_type:      str              # Fibroblast, Osteoblast, Endothelial, etc.
    tissues:        List[str]        # applicable tissues
    iso10993:       bool = False     # True if used in ISO 10993 standard protocols
    iso_tests:      List[str] = field(default_factory=list)   # which ISO 10993 parts
    typical_assays: List[str] = field(default_factory=list)
    culture_notes:  str = ""
    source:         str = ""        # ATCC / primary / iPSC-derived
    translational_relevance: str = "moderate"   # low / moderate / high
    three_rs_score: str = "replacement"         # replacement / reduction / refinement


# ── Cell model knowledge base ──────────────────────────────────────────────────

ALL_CELL_MODELS: Dict[str, CellModel] = {

    # ── ISO 10993 standard lines ──────────────────────────────────────────────

    "L929": CellModel(
        name="L929", full_name="L929 Mouse Fibroblast",
        species="Mouse", cell_type="Fibroblast",
        tissues=["skin", "general", "connective tissue"],
        iso10993=True, iso_tests=["ISO 10993-5"],
        typical_assays=["MTT/MTS cytotoxicity", "LDH release", "live-dead staining",
                        "neutral red uptake", "direct/indirect contact"],
        culture_notes="DMEM + 10% FBS. Standard ISO 10993-5 cytotoxicity line.",
        source="ATCC CCL-1",
        translational_relevance="low",
        three_rs_score="replacement",
    ),

    "3T3": CellModel(
        name="3T3", full_name="NIH 3T3 Mouse Fibroblast",
        species="Mouse", cell_type="Fibroblast",
        tissues=["skin", "general"],
        iso10993=True, iso_tests=["ISO 10993-5", "ISO 10993-10"],
        typical_assays=["MTT cytotoxicity", "BALB/c 3T3 phototoxicity assay",
                        "cell morphology", "neutral red uptake"],
        culture_notes="DMEM + 10% CS. Used in OECD 432 phototoxicity protocol.",
        source="ATCC CRL-1658",
        translational_relevance="low",
    ),

    # ── Bone / osteogenic ─────────────────────────────────────────────────────

    "MG-63": CellModel(
        name="MG-63", full_name="MG-63 Human Osteosarcoma",
        species="Human", cell_type="Osteoblast-like",
        tissues=["bone"],
        iso10993=True, iso_tests=["ISO 10993-5"],
        typical_assays=["ALP activity", "osteocalcin ELISA", "Alizarin Red (mineralisation)",
                        "collagen secretion", "cytotoxicity", "cell attachment SEM"],
        culture_notes="DMEM + 10% FBS. Good osteoblast marker expression.",
        source="ATCC CRL-1427",
        translational_relevance="moderate",
    ),

    "SaOS-2": CellModel(
        name="SaOS-2", full_name="SaOS-2 Human Osteosarcoma",
        species="Human", cell_type="Osteoblast",
        tissues=["bone"],
        iso10993=False,
        typical_assays=["ALP activity (high)", "mineralisation (Alizarin Red)",
                        "BMP-2 responsiveness", "OCN/OPN expression"],
        culture_notes="McCoy's 5A + 15% FBS. Highest ALP of bone lines.",
        source="ATCC HTB-85",
        translational_relevance="moderate",
    ),

    "MC3T3-E1": CellModel(
        name="MC3T3-E1", full_name="MC3T3-E1 Mouse Calvarial Osteoblast",
        species="Mouse", cell_type="Osteoblast precursor",
        tissues=["bone"],
        iso10993=False,
        typical_assays=["proliferation", "osteogenic differentiation (ascorbic acid)",
                        "ALP", "mineralisation (von Kossa)", "gene expression (Runx2, Col1a1)"],
        culture_notes="Alpha-MEM without ascorbic acid (for maintenance); add for differentiation.",
        source="ATCC CRL-2593",
        translational_relevance="moderate",
    ),

    # ── MSC / stem cell ───────────────────────────────────────────────────────

    "hMSC": CellModel(
        name="hMSC", full_name="Human Mesenchymal Stem Cell (bone marrow)",
        species="Human", cell_type="Mesenchymal stem cell",
        tissues=["bone", "cartilage", "adipose", "tendon"],
        iso10993=False,
        typical_assays=["tri-lineage differentiation (osteo/adipo/chondro)",
                        "surface markers (CD73/90/105+, CD34/45-)",
                        "colony forming unit (CFU-F)", "gene expression panel"],
        culture_notes="MSCGM or low-glucose DMEM + 10% FBS. Passage < 6.",
        source="Primary / commercial (Lonza, RoosterBio)",
        translational_relevance="high",
    ),

    "iPSC-MSC": CellModel(
        name="iPSC-MSC", full_name="iPSC-derived Mesenchymal Stem Cell",
        species="Human", cell_type="iPSC-derived MSC",
        tissues=["bone", "cartilage"],
        iso10993=False,
        typical_assays=["differentiation capacity", "immunomodulation assays",
                        "paracrine factor secretome", "scalability assessment"],
        culture_notes="Defined xeno-free media required for GMP translation.",
        source="iPSC-derived (various)",
        translational_relevance="high",
    ),

    # ── Cartilage ─────────────────────────────────────────────────────────────

    "chondrocytes": CellModel(
        name="chondrocytes", full_name="Primary Articular Chondrocytes",
        species="Human/Bovine", cell_type="Chondrocyte",
        tissues=["cartilage"],
        iso10993=False,
        typical_assays=["GAG production (DMMB)", "collagen II immunostaining",
                        "aggrecan gene expression", "pellet culture",
                        "live-dead in 3D scaffold", "mechanical compression"],
        culture_notes="DMEM/F12 + ITS + TGF-β3 for redifferentiation. "
                      "Primary bovine chondrocytes widely used as model.",
        source="Primary (bovine metacarpophalangeal / human OA tissue)",
        translational_relevance="high",
    ),

    "ATDC5": CellModel(
        name="ATDC5", full_name="ATDC5 Mouse Chondrogenic Cell Line",
        species="Mouse", cell_type="Chondroprogenitor",
        tissues=["cartilage"],
        iso10993=False,
        typical_assays=["chondrogenic differentiation (insulin)", "Alcian Blue staining",
                        "collagen II/X expression", "sox9 signalling"],
        culture_notes="DMEM/F12 1:1 + 5% FBS + insulin for differentiation.",
        source="RIKEN Cell Bank",
        translational_relevance="moderate",
    ),

    # ── Endothelial / vascular ────────────────────────────────────────────────

    "HUVEC": CellModel(
        name="HUVEC", full_name="Human Umbilical Vein Endothelial Cell",
        species="Human", cell_type="Endothelial",
        tissues=["cardiovascular", "vascular", "general"],
        iso10993=True, iso_tests=["ISO 10993-4"],
        typical_assays=["tube formation (Matrigel angiogenesis)", "VEGF response",
                        "haemocompatibility (thrombogenicity)", "eNOS expression",
                        "VCAM-1/ICAM-1 (inflammation)", "migration (scratch assay)"],
        culture_notes="EGM-2 medium. P3-6 only. Sensitive to shear stress.",
        source="Primary / ATCC CRL-1730",
        translational_relevance="high",
    ),

    "HCMEC": CellModel(
        name="hCMEC/D3", full_name="Human Cerebral Microvascular Endothelial Cell",
        species="Human", cell_type="Brain endothelial",
        tissues=["neural", "blood-brain barrier"],
        iso10993=False,
        typical_assays=["TEER (barrier integrity)", "P-gp efflux", "tight junction staining",
                        "BBB permeability assay"],
        culture_notes="EC medium + hydrocortisone + bFGF. Transwells required for TEER.",
        source="Millipore SCC066",
        translational_relevance="high",
    ),

    # ── Skin / wound healing ──────────────────────────────────────────────────

    "HaCaT": CellModel(
        name="HaCaT", full_name="HaCaT Human Keratinocyte",
        species="Human", cell_type="Keratinocyte",
        tissues=["skin"],
        iso10993=True, iso_tests=["ISO 10993-5", "ISO 10993-10"],
        typical_assays=["cytotoxicity", "migration (scratch assay)",
                        "stratification (air-liquid interface)", "involucrin/keratin14"],
        culture_notes="DMEM + 10% FBS. Spontaneously immortalised.",
        source="DKFZ / AddexBio",
        translational_relevance="moderate",
    ),

    "NHDF": CellModel(
        name="NHDF", full_name="Normal Human Dermal Fibroblast",
        species="Human", cell_type="Fibroblast",
        tissues=["skin"],
        iso10993=True, iso_tests=["ISO 10993-5"],
        typical_assays=["collagen gel contraction", "alpha-SMA (myofibroblast)",
                        "wound healing migration", "ECM secretion panel"],
        culture_notes="FBM medium or DMEM + 10% FBS. Primary, P5-10.",
        source="Primary / Lonza CC-2511",
        translational_relevance="high",
    ),

    # ── Cardiac ───────────────────────────────────────────────────────────────

    "iPSC-CM": CellModel(
        name="iPSC-CM", full_name="iPSC-derived Cardiomyocyte",
        species="Human", cell_type="Cardiomyocyte",
        tissues=["cardiovascular", "cardiac"],
        iso10993=False,
        typical_assays=["beating rate (video analysis)", "calcium transients (Fluo-4)",
                        "action potential (MEA)", "cardiotoxicity (hERG, contractility)",
                        "troponin I/T staining", "sarcomere organisation"],
        culture_notes="Maturation protocol required post-differentiation (30+ days). "
                      "Glucose-free lactate purification improves purity.",
        source="iPSC-derived (Fujifilm CDI, Axol, or in-house)",
        translational_relevance="high",
    ),

    # ── Neural ────────────────────────────────────────────────────────────────

    "SH-SY5Y": CellModel(
        name="SH-SY5Y", full_name="SH-SY5Y Human Neuroblastoma",
        species="Human", cell_type="Neuron-like",
        tissues=["neural"],
        iso10993=False,
        typical_assays=["neurite outgrowth", "differentiation (retinoic acid)",
                        "TH/MAP2 expression", "dopamine release", "neurotoxicity"],
        culture_notes="DMEM/F12 + 10% FBS. Differentiate with RA + BDNF.",
        source="ATCC CRL-2266",
        translational_relevance="low",
    ),

    "primary_neurons": CellModel(
        name="primary_neurons", full_name="Primary Cortical/DRG Neurons",
        species="Rat/Mouse", cell_type="Neuron",
        tissues=["neural", "spinal cord"],
        iso10993=False,
        typical_assays=["neurite outgrowth", "axon guidance", "electrophysiology (patch-clamp)",
                        "calcium imaging", "synapse formation"],
        culture_notes="Neurobasal + B27. E18 rat cortical or P0 DRG. Requires laminin coating.",
        source="Primary (E18 rat or P0 mouse)",
        translational_relevance="high",
    ),

    # ── Liver ─────────────────────────────────────────────────────────────────

    "HepG2": CellModel(
        name="HepG2", full_name="HepG2 Human Hepatocellular Carcinoma",
        species="Human", cell_type="Hepatocyte-like",
        tissues=["liver"],
        iso10993=True, iso_tests=["ISO 10993-5"],
        typical_assays=["CYP450 activity", "albumin secretion", "urea synthesis",
                        "hepatotoxicity panel", "lipid accumulation"],
        culture_notes="DMEM + 10% FBS. 3D spheroid culture improves hepatic function.",
        source="ATCC HB-8065",
        translational_relevance="low",
    ),

    "HepaRG": CellModel(
        name="HepaRG", full_name="HepaRG Human Hepatocyte-like Cell",
        species="Human", cell_type="Hepatocyte",
        tissues=["liver"],
        iso10993=False,
        typical_assays=["Phase I/II metabolism", "CYP1A2/3A4 induction",
                        "biliary transport", "DILI screening"],
        culture_notes="Requires differentiation (2% DMSO for 2 weeks). "
                      "Superior CYP activity vs HepG2.",
        source="Biopredic International",
        translational_relevance="moderate",
    ),

    # ── Retina ────────────────────────────────────────────────────────────────

    "ARPE-19": CellModel(
        name="ARPE-19", full_name="ARPE-19 Human Retinal Pigment Epithelium",
        species="Human", cell_type="RPE",
        tissues=["eye", "retina"],
        iso10993=False,
        typical_assays=["TEER (epithelial barrier)", "phagocytosis (photoreceptor outer segments)",
                        "VEGF secretion", "RPE65/ZO-1 staining", "photoreceptor co-culture"],
        culture_notes="DMEM/F12 + 10% FBS. Long-term culture (3-6 months) for barrier maturation.",
        source="ATCC CRL-2302",
        translational_relevance="moderate",
    ),
}


# ── Query functions ────────────────────────────────────────────────────────────

def get_models_for_tissue(tissue: str) -> List[CellModel]:
    """Return all cell models relevant to a tissue (case-insensitive partial match)."""
    tissue_lower = tissue.lower()
    return [m for m in ALL_CELL_MODELS.values()
            if any(tissue_lower in t.lower() for t in m.tissues)]


def get_iso10993_models() -> List[CellModel]:
    """Return cell models used in ISO 10993 standard protocols."""
    return [m for m in ALL_CELL_MODELS.values() if m.iso10993]


def get_model(name: str) -> Optional[CellModel]:
    """Return a model by key name, or None."""
    return ALL_CELL_MODELS.get(name)


def list_tissues() -> List[str]:
    """Return sorted unique list of tissues covered."""
    tissues = set()
    for m in ALL_CELL_MODELS.values():
        tissues.update(m.tissues)
    return sorted(tissues)


def search_models(query: str) -> List[CellModel]:
    """Search models by name, cell type, or assay (case-insensitive)."""
    q = query.lower()
    return [
        m for m in ALL_CELL_MODELS.values()
        if q in m.name.lower()
        or q in m.full_name.lower()
        or q in m.cell_type.lower()
        or any(q in a.lower() for a in m.typical_assays)
    ]
