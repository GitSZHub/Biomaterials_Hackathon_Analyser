"""
Tissue Interaction Modeller
============================
Models the biological response timeline when a biomaterial is implanted
or contacts tissue. Provides phase-by-phase expected biomarkers, cell
types, and durations. Advisory / knowledge-base module (not ODE simulation).

Phases: Protein Adsorption -> Acute Inflammation -> Chronic Inflammation
        -> Granulation / Repair -> Fibrous Encapsulation or Integration
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import re


# ── Data classes ──────────────────────────────────────────────

@dataclass
class ResponsePhase:
    """One phase in the tissue response timeline."""
    name: str
    onset: str               # e.g. "seconds", "1-3 days"
    duration: str            # e.g. "minutes to hours", "1-2 weeks"
    key_cells: List[str]
    key_molecules: List[str]
    biomarkers: List[str]    # measurable markers for this phase
    description: str
    material_factors: List[str]  # material properties that influence this phase


@dataclass
class TissueResponseTimeline:
    """Complete timeline for a material-tissue interaction."""
    material_type: str
    tissue_type: str
    phases: List[ResponsePhase]
    overall_outcome: str         # "Integration", "Encapsulation", "Rejection"
    outcome_factors: List[str]
    warnings: List[str]
    total_duration_weeks: str


@dataclass
class InterfaceZone:
    """Spatial zone around an implant with expected biology."""
    zone_name: str
    distance_from_surface: str   # e.g. "0-10um", "10-100um"
    expected_cells: List[str]
    expected_ecm: List[str]
    gene_signatures: List[str]


# ── Response phase database ──────────────────────────────────

RESPONSE_PHASES: List[ResponsePhase] = [
    ResponsePhase(
        name="Protein Adsorption (Vroman Effect)",
        onset="Immediate (seconds)",
        duration="Minutes to hours",
        key_cells=[],
        key_molecules=[
            "Albumin (first, then displaced)",
            "Fibrinogen",
            "Fibronectin",
            "Vitronectin",
            "Complement C3, C4, C5",
            "IgG",
            "Von Willebrand factor",
        ],
        biomarkers=[
            "Protein corona composition (LC-MS/MS)",
            "Fibrinogen adsorption (ELISA / QCM-D)",
            "Complement activation (C3a, C5a ELISA)",
        ],
        description=(
            "Within seconds of blood/tissue fluid contact, proteins adsorb "
            "to the material surface. The Vroman effect describes competitive "
            "displacement: albumin arrives first, then is displaced by higher-"
            "affinity proteins (fibrinogen, fibronectin). This protein layer "
            "is what cells actually 'see' -- not the bare material."
        ),
        material_factors=[
            "Surface chemistry (hydrophobicity, charge)",
            "Surface roughness / topography",
            "Surface energy",
            "Protein-repellent coatings (PEG, zwitterionic)",
        ],
    ),
    ResponsePhase(
        name="Acute Inflammation",
        onset="Hours to 1 day",
        duration="1-7 days",
        key_cells=[
            "Neutrophils (PMNs) -- first responders",
            "Mast cells -- histamine release",
            "Monocytes (arriving, differentiating)",
        ],
        key_molecules=[
            "IL-1beta", "TNF-alpha", "IL-6",
            "IL-8 (CXCL8) -- neutrophil chemotaxis",
            "MCP-1 (CCL2) -- monocyte recruitment",
            "Histamine", "ROS / superoxide",
            "Complement anaphylatoxins (C3a, C5a)",
        ],
        biomarkers=[
            "TNF-alpha, IL-6, IL-1beta (ELISA or Luminex)",
            "Neutrophil count (flow cytometry: CD66b+/CD16+)",
            "ROS production (DCFDA assay)",
            "MPO activity (myeloperoxidase)",
            "Acute phase proteins (CRP, SAA)",
        ],
        description=(
            "Neutrophils arrive within hours, releasing ROS and proteases to "
            "clear debris. Pro-inflammatory cytokines recruit monocytes. "
            "This phase is normal and necessary -- its RESOLUTION determines "
            "outcome. Persistent acute inflammation indicates material toxicity."
        ),
        material_factors=[
            "Particle debris / wear products",
            "Degradation rate (fast degradation = more debris)",
            "Surface roughness",
            "Endotoxin contamination",
            "Material biocompatibility score",
        ],
    ),
    ResponsePhase(
        name="Chronic Inflammation",
        onset="3-7 days",
        duration="1-4 weeks (or persistent)",
        key_cells=[
            "Macrophages (M1 pro-inflammatory)",
            "Macrophages transitioning to M2 (resolution)",
            "Foreign body giant cells (FBGC) -- fused macrophages",
            "Lymphocytes (T cells, if adaptive response)",
        ],
        key_molecules=[
            "IFN-gamma (M1 polarisation)",
            "IL-4, IL-13 (M2 polarisation, FBGC fusion)",
            "IL-10, TGF-beta (resolution signals)",
            "MMP-2, MMP-9 (matrix remodelling)",
            "VEGF (angiogenesis initiation)",
        ],
        biomarkers=[
            "M1/M2 ratio (flow cytometry: CD86/CD206)",
            "FBGC count (histology: multinucleated cells)",
            "IL-10/TNF-alpha ratio (resolution indicator)",
            "MMP activity (zymography or ELISA)",
            "TGF-beta1 (ELISA)",
        ],
        description=(
            "Monocyte-derived macrophages dominate. The M1->M2 transition "
            "is the critical fork: successful resolution drives M2 polarisation "
            "and tissue repair. Failure to resolve leads to persistent inflammation, "
            "foreign body giant cell formation, and eventual fibrous encapsulation."
        ),
        material_factors=[
            "Degradation products (chronic irritation)",
            "Surface topography (macro- vs micro-roughness)",
            "Material compliance / stiffness mismatch",
            "Bioactive factor release (anti-inflammatory coatings)",
            "Porosity (macrophage infiltration)",
        ],
    ),
    ResponsePhase(
        name="Granulation Tissue / Repair",
        onset="1-2 weeks",
        duration="2-8 weeks",
        key_cells=[
            "Fibroblasts / myofibroblasts",
            "Endothelial cells (neovascularisation)",
            "M2 macrophages (tissue repair)",
            "Mesenchymal stem/progenitor cells",
        ],
        key_molecules=[
            "VEGF, FGF-2 (angiogenesis)",
            "PDGF (fibroblast recruitment)",
            "TGF-beta1 (ECM deposition, fibrosis driver)",
            "Collagen I, III (new ECM)",
            "Fibronectin (provisional matrix)",
            "alpha-SMA (myofibroblast marker)",
        ],
        biomarkers=[
            "VEGF (ELISA)",
            "Vessel density (CD31 immunostaining)",
            "Collagen deposition (Masson trichrome / Sirius red)",
            "alpha-SMA+ cells (immunohistochemistry)",
            "Hydroxyproline content (collagen quantification)",
        ],
        description=(
            "New blood vessels (angiogenesis) and provisional ECM form within "
            "and around the implant. Fibroblasts deposit collagen. This phase "
            "determines whether the material integrates with native tissue or "
            "becomes encapsulated. Porous scaffolds with appropriate degradation "
            "rate favour tissue ingrowth over encapsulation."
        ),
        material_factors=[
            "Porosity and pore size (>100um for vascularisation)",
            "Degradation rate matching tissue remodelling",
            "Growth factor loading (VEGF, BMP-2)",
            "Scaffold architecture (interconnected pores)",
            "Mechanical properties matching native tissue",
        ],
    ),
    ResponsePhase(
        name="Fibrous Encapsulation or Integration",
        onset="4-12 weeks",
        duration="Permanent (steady state)",
        key_cells=[
            "Fibroblasts (capsule) or tissue-specific cells (integration)",
            "Resident macrophages (surveillance)",
            "Osteoblasts/chondrocytes (if bone/cartilage)",
            "Endothelial cells (maintained vasculature)",
        ],
        key_molecules=[
            "Collagen I (dense capsule or remodelled tissue)",
            "MMPs / TIMPs (ongoing remodelling)",
            "Osteocalcin, ALP (if bone integration)",
        ],
        biomarkers=[
            "Capsule thickness (histomorphometry)",
            "Tissue-material bond strength (push-out / pull-out test)",
            "Bone-implant contact ratio (micro-CT + histology)",
            "Vascular density at interface",
            "Foreign body giant cell density",
        ],
        description=(
            "Final outcome: either a dense avascular fibrous capsule isolates "
            "the implant (encapsulation -- foreign body response), or the "
            "material integrates with regenerated tissue (successful outcome). "
            "Degradable scaffolds ideally replaced by native tissue by this point."
        ),
        material_factors=[
            "Non-degradable -> encapsulation (silicone, PEEK, titanium alloy)",
            "Degradable with matched rate -> integration (PLGA, collagen, silk)",
            "Bioactive surface (HA coating, RGD peptides) -> better integration",
            "Mechanical mismatch -> stress shielding (bone) or capsular contracture",
        ],
    ),
]


# ── Interface zone database ──────────────────────────────────

INTERFACE_ZONES: List[InterfaceZone] = [
    InterfaceZone(
        zone_name="Immediate interface (protein corona)",
        distance_from_surface="0-1 um",
        expected_cells=["Adherent macrophages", "Adherent fibroblasts/osteoblasts"],
        expected_ecm=["Adsorbed protein layer", "Provisional fibrin matrix"],
        gene_signatures=["Focal adhesion genes", "Integrin signalling", "Mechanotransduction"],
    ),
    InterfaceZone(
        zone_name="Peri-implant zone",
        distance_from_surface="1-100 um",
        expected_cells=[
            "Macrophages (M1/M2 gradient)",
            "Fibroblasts / myofibroblasts",
            "Foreign body giant cells (if non-degradable)",
            "Endothelial cells (neovascularisation)",
        ],
        expected_ecm=["Collagen III (early) -> Collagen I (mature)", "Fibronectin"],
        gene_signatures=[
            "Inflammatory: NFkB, IL-6/JAK-STAT, TLR signalling",
            "Fibrosis: TGF-beta, Wnt, alpha-SMA",
            "Angiogenesis: VEGF, HIF-1",
        ],
    ),
    InterfaceZone(
        zone_name="Transition zone",
        distance_from_surface="100-500 um",
        expected_cells=[
            "Decreasing macrophage density",
            "Tissue-specific cells returning to normal",
            "Progenitor cells (if regenerative)",
        ],
        expected_ecm=["Transitional -- partial remodelling", "Native tissue ECM re-appearing"],
        gene_signatures=[
            "Decreasing inflammatory signature",
            "Tissue-specific differentiation markers",
            "ECM remodelling: MMP/TIMP balance",
        ],
    ),
    InterfaceZone(
        zone_name="Native tissue",
        distance_from_surface=">500 um",
        expected_cells=["Normal tissue-resident cells"],
        expected_ecm=["Native tissue ECM"],
        gene_signatures=["Homeostatic tissue signature"],
    ),
]


# ── Material-outcome knowledge base ─────────────────────────

_MATERIAL_OUTCOMES: Dict[str, Dict] = {
    "titanium": {
        "outcome": "Integration (osseointegration)",
        "timeline": "8-16 weeks",
        "notes": "Gold standard for bone. Oxide layer is biocompatible. "
                 "Micro/nano-roughened surfaces improve osseointegration.",
        "capsule_risk": "Low (bone)",
    },
    "plga": {
        "outcome": "Integration then resorption",
        "timeline": "12-52 weeks (depends on LA:GA ratio)",
        "notes": "Degrades to lactic + glycolic acid. Acidic degradation products "
                 "can cause late-stage inflammation if bulk degradation occurs.",
        "capsule_risk": "Low-moderate",
    },
    "silicone": {
        "outcome": "Fibrous encapsulation",
        "timeline": "4-12 weeks (capsule matures 6-12 months)",
        "notes": "Non-degradable, bioinert. Fibrous capsule forms around implant. "
                 "Capsular contracture (Baker grade) is the main complication.",
        "capsule_risk": "High",
    },
    "collagen": {
        "outcome": "Integration and remodelling",
        "timeline": "4-12 weeks",
        "notes": "Natural ECM component. Rapidly remodelled by host cells. "
                 "Cross-linking slows degradation. Source species matters (bovine, porcine).",
        "capsule_risk": "Low",
    },
    "hydrogel": {
        "outcome": "Integration or encapsulation (composition-dependent)",
        "timeline": "4-16 weeks",
        "notes": "High water content mimics soft tissue. PEG hydrogels may encapsulate "
                 "if non-degradable. Gelatin/HA hydrogels integrate better.",
        "capsule_risk": "Moderate (PEG) / Low (natural polymer)",
    },
    "peek": {
        "outcome": "Fibrous encapsulation (unless HA-coated)",
        "timeline": "8-16 weeks",
        "notes": "Bioinert polymer. Excellent mechanical properties for load-bearing. "
                 "HA coating or surface modification needed for bone integration.",
        "capsule_risk": "High (uncoated) / Low (HA-coated)",
    },
    "hydroxyapatite": {
        "outcome": "Integration (osteoconductive)",
        "timeline": "8-24 weeks",
        "notes": "Mineral phase of bone. Slowly resorbed and replaced by new bone. "
                 "Excellent biocompatibility. Brittle -- often used as coating.",
        "capsule_risk": "Very low",
    },
    "silk": {
        "outcome": "Integration and slow resorption",
        "timeline": "12-52+ weeks",
        "notes": "Degrades via proteolysis (months-years). Minimal inflammatory response. "
                 "Excellent for soft tissue engineering (skin, tendon, nerve).",
        "capsule_risk": "Low",
    },
    "pcl": {
        "outcome": "Slow integration and very slow resorption",
        "timeline": "1-3 years",
        "notes": "Very slow degradation (2-4 years). Good for long-term scaffolds. "
                 "Often blended with faster-degrading polymers (PLGA).",
        "capsule_risk": "Moderate (slow degradation means prolonged FBR)",
    },
    "chitosan": {
        "outcome": "Integration with antimicrobial benefit",
        "timeline": "4-12 weeks",
        "notes": "Degraded by lysozyme. Inherent antimicrobial properties. "
                 "Cationic nature may enhance cell adhesion. pH-dependent solubility.",
        "capsule_risk": "Low",
    },
}


# ── Matrigel caveat ──────────────────────────────────────────

MATRIGEL_CAVEAT = (
    "WARNING: Matrigel (Corning) is murine tumor-derived basement membrane extract. "
    "It is lot-variable, poorly defined, and non-translatable to clinical use. "
    "If your experimental control is Matrigel, consider: (1) defined recombinant "
    "alternatives (Geltrex, Cultrex BME-2, VitroGel), (2) synthetic matrices "
    "(PEG-based with defined peptide ligands), or (3) at minimum, report lot number "
    "and protein concentration. Many reviewers now flag Matrigel-only studies."
)


# ── Public API ───────────────────────────────────────────────

def model_tissue_response(
    material_type: str = "",
    tissue_type: str = "",
    is_degradable: bool = True,
    biocompat_score: Optional[float] = None,
) -> TissueResponseTimeline:
    """Model the expected tissue response timeline for a material.

    Parameters
    ----------
    material_type : str
        Material name/class (e.g. "PLGA", "titanium", "hydrogel").
    tissue_type : str
        Target tissue (e.g. "bone", "skin", "cartilage").
    is_degradable : bool
        Whether the material degrades in vivo.
    biocompat_score : float, optional
        0-100 biocompatibility score from regulatory module.

    Returns
    -------
    TissueResponseTimeline
    """
    mat_lower = material_type.lower().strip()
    warnings: List[str] = []

    # Check for Matrigel
    if "matrigel" in mat_lower:
        warnings.append(MATRIGEL_CAVEAT)

    # Look up material-specific outcomes
    mat_info = None
    for key, info in _MATERIAL_OUTCOMES.items():
        if key in mat_lower:
            mat_info = info
            break

    # Determine outcome
    if mat_info:
        outcome = mat_info["outcome"]
        total_duration = mat_info["timeline"]
        outcome_factors = [mat_info["notes"]]
        if mat_info["capsule_risk"].startswith(("High", "Very high")):
            warnings.append(
                f"High capsule risk for {material_type}. Consider surface "
                f"modification or bioactive coating to improve integration."
            )
    else:
        if is_degradable:
            outcome = "Integration (if degradation rate matches tissue remodelling)"
            total_duration = "8-24 weeks (material-dependent)"
        else:
            outcome = "Likely fibrous encapsulation (non-degradable)"
            total_duration = "4-12 weeks capsule formation"
            warnings.append(
                "Non-degradable materials typically result in fibrous encapsulation. "
                "Consider bioactive surface modification."
            )
        outcome_factors = [
            "Degradation rate vs tissue remodelling rate",
            "Surface chemistry and topography",
            "Porosity and pore interconnectivity",
            "Mechanical property match with host tissue",
        ]

    # Biocompat score influence
    if biocompat_score is not None:
        if biocompat_score < 40:
            warnings.append(
                f"Low biocompatibility score ({biocompat_score:.0f}/100) -- "
                f"expect prolonged acute inflammation and higher FBR risk."
            )
        elif biocompat_score > 80:
            outcome_factors.append(
                f"High biocompatibility score ({biocompat_score:.0f}/100) -- "
                f"favourable inflammatory resolution expected."
            )

    # Tissue-specific notes
    tissue_notes = _get_tissue_notes(tissue_type)
    if tissue_notes:
        outcome_factors.append(tissue_notes)

    return TissueResponseTimeline(
        material_type=material_type or "Unknown material",
        tissue_type=tissue_type or "General soft tissue",
        phases=RESPONSE_PHASES,
        overall_outcome=outcome,
        outcome_factors=outcome_factors,
        warnings=warnings,
        total_duration_weeks=total_duration,
    )


def get_interface_zones() -> List[InterfaceZone]:
    """Return the spatial interface zone model."""
    return INTERFACE_ZONES


def get_material_outcome(material: str) -> Optional[Dict]:
    """Look up known outcome for a material type."""
    mat_lower = material.lower().strip()
    for key, info in _MATERIAL_OUTCOMES.items():
        if key in mat_lower:
            return {"material_key": key, **info}
    return None


def list_known_materials() -> List[str]:
    """Return materials with known tissue response data."""
    return list(_MATERIAL_OUTCOMES.keys())


def get_phase_by_name(name: str) -> Optional[ResponsePhase]:
    """Look up a response phase by partial name match."""
    name_lower = name.lower()
    for phase in RESPONSE_PHASES:
        if name_lower in phase.name.lower():
            return phase
    return None


def get_biomarkers_for_timepoint(weeks: float) -> List[str]:
    """Return recommended biomarkers to measure at a given timepoint (weeks)."""
    markers: List[str] = []
    if weeks < 0.15:  # ~1 day
        markers.extend(RESPONSE_PHASES[0].biomarkers)  # Protein adsorption
        markers.extend(RESPONSE_PHASES[1].biomarkers[:2])  # Early acute
    elif weeks < 1:
        markers.extend(RESPONSE_PHASES[1].biomarkers)  # Acute inflammation
    elif weeks < 4:
        markers.extend(RESPONSE_PHASES[2].biomarkers)  # Chronic inflammation
        markers.extend(RESPONSE_PHASES[3].biomarkers[:2])  # Early repair
    elif weeks < 12:
        markers.extend(RESPONSE_PHASES[3].biomarkers)  # Granulation/repair
        markers.extend(RESPONSE_PHASES[4].biomarkers[:2])  # Early outcome
    else:
        markers.extend(RESPONSE_PHASES[4].biomarkers)  # Final outcome
    return markers


# ── Private helpers ──────────────────────────────────────────

def _get_tissue_notes(tissue_type: str) -> str:
    """Return tissue-specific integration notes."""
    if not tissue_type:
        return ""
    t = tissue_type.lower()
    notes = {
        "bone": (
            "Bone: osseointegration requires osteoblast attachment + mineralisation. "
            "Key markers: ALP, osteocalcin, RUNX2, BMP-2. Micro-CT for bone volume. "
            "Pore size >300um optimal for bone ingrowth."
        ),
        "cartilage": (
            "Cartilage: avascular tissue with limited self-repair. Material must support "
            "chondrocyte phenotype (SOX9, COL2A1, ACAN) without hypertrophy (COL10A1, MMP13). "
            "Mechanical match critical (0.5-1 MPa compressive modulus)."
        ),
        "skin": (
            "Skin: layered structure (epidermis/dermis). Keratinocyte migration on surface, "
            "fibroblast infiltration in bulk. Key markers: KRT14 (basal), KRT10 (suprabasal), "
            "COL1A1/COL3A1 (dermis). Wound contraction vs regeneration balance."
        ),
        "nerve": (
            "Nerve: axonal regeneration requires aligned guidance channels. Schwann cell "
            "migration critical. Key markers: S100B, MBP (myelin), NF200 (axons), GAP43 "
            "(regeneration). Conduit lumen diameter and wall porosity matter."
        ),
        "cardiac": (
            "Cardiac: cardiomyocyte electromechanical coupling required. Material must "
            "support contractile function. Key markers: cTnT, MYH7 (maturation), Cx43 "
            "(gap junctions). Conductive materials (carbon, PEDOT:PSS) may improve coupling."
        ),
        "vascular": (
            "Vascular: endothelialisation of lumen surface critical. Anti-thrombogenic surface "
            "needed. Key markers: CD31, vWF (endothelial), alpha-SMA (smooth muscle). "
            "Compliance mismatch causes intimal hyperplasia at anastomosis."
        ),
        "tendon": (
            "Tendon: aligned collagen fibre structure. Material must support tenocyte phenotype "
            "and mechanical loading. Key markers: SCX, TNMD, COL1A1. Mechanical testing: "
            "tensile strength and stiffness must approach native values (500-1000 MPa)."
        ),
        "liver": (
            "Liver: hepatocyte polarity and bile canaliculi formation critical. 3D architecture "
            "preferred. Key markers: ALB, CYP3A4 (function), HNF4A (identity). Drug metabolism "
            "capacity (CYP450 activity) as functional readout."
        ),
    }
    for key, note in notes.items():
        if key in t:
            return note
    return ""
