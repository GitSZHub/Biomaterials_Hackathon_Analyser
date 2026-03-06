"""
Organism Models Knowledge Base -- curated in vivo models for biomaterials testing.
==================================================================================
Covers small animal, large animal, and 3Rs alternative models used in ISO 10993-6
implantation, preclinical efficacy, and GLP toxicology studies.

Usage:
    from experimental_engine.organism_models_db import get_models_for_tissue, ALL_ORGANISM_MODELS
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class OrganismModel:
    key:              str
    name:             str             # display name
    species:          str             # Rat / Mouse / Rabbit / Sheep / Pig / Zebrafish
    strain:           str             # e.g. Sprague-Dawley, New Zealand White
    model_type:       str             # subcutaneous / orthotopic / defect / systemic / ex vivo
    tissues:          List[str]
    iso10993:         bool = False
    iso_parts:        List[str] = field(default_factory=list)
    defect_size:      str = ""        # e.g. "5 mm critical-size calvaria"
    implant_duration: str = ""        # typical endpoint e.g. "4, 12 weeks"
    endpoint_assays:  List[str] = field(default_factory=list)
    strengths:        List[str] = field(default_factory=list)
    limitations:      List[str] = field(default_factory=list)
    regulatory_acceptance: str = "accepted"   # accepted / limited / emerging
    three_rs_category: str = "animal"         # animal / alternative
    gmp_required:     bool = False


# ── Model KB ──────────────────────────────────────────────────────────────────

ALL_ORGANISM_MODELS: Dict[str, OrganismModel] = {

    # ── ISO 10993-6 implantation ──────────────────────────────────────────────

    "rat_subcutaneous": OrganismModel(
        key="rat_subcutaneous",
        name="Rat Subcutaneous Implant",
        species="Rat", strain="Sprague-Dawley or Wistar",
        model_type="subcutaneous implant",
        tissues=["skin", "connective tissue", "general"],
        iso10993=True, iso_parts=["ISO 10993-6"],
        implant_duration="1, 4, 12, 26 weeks",
        endpoint_assays=[
            "Histopathology (H&E, Masson's trichrome)",
            "Inflammatory cell infiltration grading (ISO 10993-6 scoring)",
            "Fibrous capsule thickness",
            "Foreign body giant cell count",
            "Vascularisation (CD31 IHC)",
            "Macrophage polarisation (M1/M2, CD68/CD163 IHC)",
        ],
        strengths=["ISO 10993-6 compliant", "Low cost", "High throughput",
                   "Good for material biocompatibility screening"],
        limitations=["Not tissue-specific", "Does not test functional efficacy",
                     "Rodent immune response differs from human"],
        regulatory_acceptance="accepted",
    ),

    "rat_calvaria": OrganismModel(
        key="rat_calvaria",
        name="Rat Calvaria Critical-Size Defect",
        species="Rat", strain="Sprague-Dawley or Fischer 344",
        model_type="orthotopic bone defect",
        tissues=["bone"],
        defect_size="5 mm circular critical-size defect (will not heal spontaneously)",
        implant_duration="4, 8, 12 weeks",
        endpoint_assays=[
            "Micro-CT (bone volume/total volume, trabecular microarchitecture)",
            "Histology (Goldner's trichrome, H&E)",
            "Biomechanical testing (push-out, compression)",
            "Histomorphometry (osteoid, mineralisation front)",
            "Immunohistochemistry (osteocalcin, RUNX2, VEGF)",
        ],
        strengths=["Well-established model", "Easy surgical access",
                   "Critical-size ensures scaffold dependency",
                   "Accepted by FDA/EMA for bone substitute screening"],
        limitations=["Calvarial bone is membranous, not endochondral",
                     "Thin cortical bone limits mechanical endpoints",
                     "Poor vascularisation challenge vs weight-bearing sites"],
        regulatory_acceptance="accepted",
    ),

    "rat_femoral": OrganismModel(
        key="rat_femoral",
        name="Rat Femoral Segmental Defect",
        species="Rat", strain="Sprague-Dawley",
        model_type="orthotopic bone defect",
        tissues=["bone"],
        defect_size="5-8 mm segmental defect (critical-size)",
        implant_duration="4, 8, 12 weeks",
        endpoint_assays=[
            "Micro-CT (bridging, BV/TV)",
            "Torsional/bending biomechanics",
            "Histology (Goldner's, Safranin O)",
            "Bone mineral density (pQCT)",
        ],
        strengths=["Load-bearing environment", "Critical-size model",
                   "Established fixation techniques (intramedullary pin)"],
        limitations=["Higher surgical complexity", "Fixation hardware artefacts on CT",
                     "Not large enough for human-sized implants"],
        regulatory_acceptance="accepted",
    ),

    "rat_osteochondral": OrganismModel(
        key="rat_osteochondral",
        name="Rat Osteochondral Defect (Femoral Condyle)",
        species="Rat", strain="Sprague-Dawley",
        model_type="osteochondral defect",
        tissues=["cartilage", "bone"],
        defect_size="1.5-2 mm diameter, full-thickness osteochondral",
        implant_duration="4, 8, 16 weeks",
        endpoint_assays=[
            "ICRS histological scoring (Safranin O/fast green)",
            "Micro-CT (subchondral bone repair)",
            "Immunohistochemistry (collagen I, II; aggrecan)",
            "Biomechanical indentation testing",
        ],
        strengths=["Simultaneous cartilage + bone repair assessment",
                   "Relatively standardised protocol"],
        limitations=["Rat cartilage is thin — limited clinical translation",
                     "Spontaneous healing capacity higher than in larger species"],
        regulatory_acceptance="accepted",
    ),

    # ── Rabbit models ─────────────────────────────────────────────────────────

    "rabbit_femoral_condyle": OrganismModel(
        key="rabbit_femoral_condyle",
        name="Rabbit Femoral Condyle Defect",
        species="Rabbit", strain="New Zealand White",
        model_type="osteochondral defect",
        tissues=["cartilage", "bone"],
        defect_size="4-6 mm diameter, full-thickness osteochondral",
        implant_duration="4, 12, 24 weeks",
        endpoint_assays=[
            "Macroscopic scoring (ICRS)",
            "Histological scoring (modified O'Driscoll or ICRS II)",
            "Safranin O / collagen II IHC",
            "Micro-CT subchondral bone",
            "Mechanical indentation (stiffness vs native)",
        ],
        strengths=["Larger defect than rat — better clinical scale",
                   "Well-established model accepted by regulatory bodies",
                   "NZW rabbit widely available"],
        limitations=["Higher intrinsic repair capacity than humans",
                     "Quadruped biomechanics differ from humans",
                     "Rabbit antibodies/reagents more limited"],
        regulatory_acceptance="accepted",
    ),

    "rabbit_spine": OrganismModel(
        key="rabbit_spine",
        name="Rabbit Lumbar Spine Fusion",
        species="Rabbit", strain="New Zealand White",
        model_type="spinal fusion",
        tissues=["bone", "intervertebral disc"],
        implant_duration="8, 12, 24 weeks",
        endpoint_assays=[
            "Radiographic fusion assessment",
            "Manual palpation fusion score",
            "Micro-CT volumetric bone",
            "Biomechanical flexion-extension testing",
            "Histology (decalcified sections)",
        ],
        strengths=["Standard model for spinal fusion devices",
                   "Accepted by FDA for spine cage evaluation"],
        limitations=["Lordotic spine vs kyphotic in humans", "Small body weight"],
        regulatory_acceptance="accepted",
    ),

    # ── Large animal models ───────────────────────────────────────────────────

    "sheep_stifle": OrganismModel(
        key="sheep_stifle",
        name="Sheep Stifle (Knee) Osteochondral Defect",
        species="Sheep", strain="Merino or Corriedale",
        model_type="osteochondral defect",
        tissues=["cartilage", "bone"],
        defect_size="6-10 mm diameter full-thickness osteochondral",
        implant_duration="3, 6, 12 months",
        endpoint_assays=[
            "MRI (T2 mapping, dGEMRIC)",
            "Arthroscopic ICRS assessment",
            "Histology (OARSI grading)",
            "Biomechanical compressive modulus",
            "GAG content (DMMB)",
            "Collagen II/I ratio",
        ],
        strengths=["Cartilage thickness similar to human",
                   "Load-bearing joint biomechanics",
                   "Accepted for pivotal preclinical cartilage studies",
                   "MRI-compatible (no metal implant)"],
        limitations=["High cost", "Long study duration",
                     "Specialist surgical team required",
                     "Sheep are quadrupeds — different joint loading"],
        regulatory_acceptance="accepted",
        gmp_required=True,
    ),

    "pig_skin": OrganismModel(
        key="pig_skin",
        name="Porcine (Pig) Full-Thickness Skin Wound",
        species="Pig", strain="Landrace or Yorkshire",
        model_type="wound healing",
        tissues=["skin"],
        defect_size="2 x 2 cm full-thickness excisional wounds",
        implant_duration="7, 14, 21 days",
        endpoint_assays=[
            "Wound area planimetry (digital photography)",
            "Histology (re-epithelialisation, granulation tissue, scar)",
            "Immunohistochemistry (collagen I/III, alpha-SMA, CD31)",
            "Tensile strength (scar biomechanics)",
        ],
        strengths=["Pig skin histologically and anatomically closest to human",
                   "Thick dermis allows full-thickness wound models",
                   "Accepted gold standard for wound healing scaffolds"],
        limitations=["High cost", "Facility requirements", "Ethical considerations"],
        regulatory_acceptance="accepted",
        gmp_required=True,
    ),

    "minipig_systemic": OrganismModel(
        key="minipig_systemic",
        name="Minipig Systemic Toxicology",
        species="Pig", strain="Gottingen or Yucatan Minipig",
        model_type="systemic toxicology",
        tissues=["general", "cardiovascular", "liver", "kidney"],
        iso10993=True, iso_parts=["ISO 10993-11"],
        implant_duration="28, 90, 180 days",
        endpoint_assays=[
            "Haematology panel", "Clinical chemistry (liver/kidney/lipids)",
            "Organ weights and histopathology",
            "Cardiovascular monitoring (ECG, BP)",
            "Toxicokinetics",
        ],
        strengths=["GLP-compliant non-rodent toxicology",
                   "Minipig physiology close to human (GI, CV, skin)",
                   "Accepted by FDA/EMA as non-rodent toxicology species"],
        limitations=["Very high cost", "Long study duration",
                     "Specialist GLP facility required"],
        regulatory_acceptance="accepted",
        gmp_required=True,
    ),

    # ── 3Rs alternatives ──────────────────────────────────────────────────────

    "zebrafish": OrganismModel(
        key="zebrafish",
        name="Zebrafish Embryo Toxicity",
        species="Zebrafish", strain="AB or TL wildtype",
        model_type="embryo toxicity screen",
        tissues=["general"],
        implant_duration="120 hours post-fertilisation",
        endpoint_assays=[
            "Mortality / developmental stage scoring",
            "Heartbeat rate",
            "Fin/jaw development",
            "Fluorescent reporter assays (Tg lines)",
            "Angiogenesis (Tg(fli1:EGFP))",
        ],
        strengths=["High throughput", "3Rs replacement for mammalian toxicity screens",
                   "OECD 236 recognised test guideline",
                   "Transparent embryo enables live imaging",
                   "Low cost, fast (5 days)"],
        limitations=["Not ISO 10993 accepted for device classification",
                     "Complementary screen only, not standalone",
                     "Species-specific drug metabolism"],
        regulatory_acceptance="limited",
        three_rs_category="alternative",
    ),

    "rhe_skin": OrganismModel(
        key="rhe_skin",
        name="Reconstructed Human Epidermis (RhE)",
        species="Human", strain="EpiDerm (MatTek) or SkinEthic",
        model_type="ex vivo skin model",
        tissues=["skin"],
        iso10993=True, iso_parts=["ISO 10993-10", "ISO 10993-23"],
        implant_duration="24-42 hours exposure",
        endpoint_assays=[
            "MTT viability (ET50)",
            "Cytokine release (IL-1α, IL-18)",
            "Histology (H&E)",
            "TEER",
        ],
        strengths=["ISO 10993-10 / ISO 10993-23 validated",
                   "Replaces Draize rabbit skin test",
                   "Human-derived cells — better translation"],
        limitations=["Not suitable for systemic toxicity",
                     "Limited to surface contact materials"],
        regulatory_acceptance="accepted",
        three_rs_category="alternative",
    ),

    "mouse_tumor": OrganismModel(
        key="mouse_tumor",
        name="Mouse Subcutaneous Tumour Xenograft",
        species="Mouse", strain="BALB/c nude or NOD-SCID",
        model_type="tumour model",
        tissues=["oncology", "drug delivery"],
        implant_duration="2-4 weeks (tumour growth), then treatment",
        endpoint_assays=[
            "Tumour volume (callipers)",
            "Bioluminescence imaging (luciferase tumour lines)",
            "Drug concentration in tumour (PK)",
            "Histology (Ki67, TUNEL, CD31)",
        ],
        strengths=["Standard model for local drug delivery from scaffolds",
                   "Well-characterised tumour cell lines available"],
        limitations=["Immunocompromised model — no immune response",
                     "Subcutaneous tumour differs from native tumour microenvironment"],
        regulatory_acceptance="accepted",
    ),
}


# ── Query functions ────────────────────────────────────────────────────────────

def get_models_for_tissue(tissue: str) -> List[OrganismModel]:
    """Return organism models relevant to a tissue."""
    t = tissue.lower()
    return [m for m in ALL_ORGANISM_MODELS.values()
            if any(t in tis.lower() for tis in m.tissues)]


def get_iso10993_models() -> List[OrganismModel]:
    return [m for m in ALL_ORGANISM_MODELS.values() if m.iso10993]


def get_small_animal_models() -> List[OrganismModel]:
    return [m for m in ALL_ORGANISM_MODELS.values()
            if m.species.lower() in ("rat", "mouse", "rabbit")]


def get_large_animal_models() -> List[OrganismModel]:
    return [m for m in ALL_ORGANISM_MODELS.values()
            if m.species.lower() in ("sheep", "pig")]


def get_alternatives() -> List[OrganismModel]:
    return [m for m in ALL_ORGANISM_MODELS.values()
            if m.three_rs_category == "alternative"]


def get_model(key: str) -> Optional[OrganismModel]:
    return ALL_ORGANISM_MODELS.get(key)
