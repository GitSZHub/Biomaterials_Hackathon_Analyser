"""
Proteomics Client — workflow design, STRING PPI queries, PRIDE dataset search,
protein corona knowledge base, and biomaterials-relevant proteomics intelligence.

Public API:
    from experimental_engine.proteomics_client import (
        ProteomicsClient,
        recommend_workflow, ProtWorkflowRec,
        PROTEOMICS_TYPES, CORONA_PROTEINS, MATRISOME_CATEGORIES,
    )

    # STRING PPI lookup
    client = ProteomicsClient()
    partners = client.get_interaction_partners(["ITGB1", "PTK2", "VCL"])

    # Workflow recommendation
    rec = recommend_workflow("protein corona", material="titanium implant")
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class PPIEdge:
    """A protein-protein interaction edge from STRING."""
    protein_a:  str
    protein_b:  str
    score:      float           # combined score 0-1
    source:     str = "STRING"
    is_surface: bool = False    # True if both are plasma membrane proteins


@dataclass
class PPINetwork:
    """Protein-protein interaction network."""
    query_proteins: List[str]
    edges:          List[PPIEdge] = field(default_factory=list)
    nodes:          List[str] = field(default_factory=list)
    hub_proteins:   List[str] = field(default_factory=list)      # high-degree nodes
    n_edges:        int = 0
    n_nodes:        int = 0
    error:          Optional[str] = None


@dataclass
class ProtWorkflowRec:
    """Proteomics workflow recommendation."""
    workflow_type:      str         # "DIA_global" | "phospho" | "corona" | "secretome" | "surface" | "ecm"
    name:               str
    description:        str
    acquisition:        str         # "DDA" | "DIA"
    quantification:     str         # "LFQ" | "TMT" | "SILAC"
    enrichment:         str = ""    # "TiO2" | "Fe-IMAC" | "biotinylation" | "detergent"
    instruments:        List[str] = field(default_factory=list)
    analysis_tools:     List[str] = field(default_factory=list)
    sample_prep:        List[str] = field(default_factory=list)
    cost_flag:          str = "high"
    turnaround:         str = "2-4 weeks"
    notes:              str = ""
    priority:           int = 0


@dataclass
class PRIDEDataset:
    """A dataset from PRIDE Archive."""
    accession:      str
    title:          str
    organism:       str = ""
    tissue:         str = ""
    instrument:     str = ""
    n_assays:       int = 0
    publication:    str = ""


# ── Proteomics Knowledge Bases ───────────────────────────────────────────────

PROTEOMICS_TYPES: Dict[str, Dict] = {
    "Global Discovery": {
        "description": "Full cellular proteome after material contact. Identifies all protein changes.",
        "acquisition": "DIA",
        "quantification": "LFQ",
        "enrichment": "",
        "instruments": ["Orbitrap Exploris", "timsTOF Pro"],
        "analysis_tools": ["DIA-NN", "Spectronaut", "MaxQuant"],
        "sample_prep": [
            "Cell lysis (SDS or urea-based)",
            "Reduction + alkylation (DTT + IAA)",
            "Trypsin digestion (overnight)",
            "Desalting (C18 stage tips)",
            "nanoLC-MS/MS",
        ],
        "depth": "5000-8000 proteins",
        "categories": ["global", "mechanism", "pathway"],
    },
    "Phosphoproteomics": {
        "description": "Map active signalling: pFAK, pYAP, pSmad2/3, pERK. Enrichment required.",
        "acquisition": "DIA",
        "quantification": "TMT",
        "enrichment": "TiO2 or Fe-IMAC",
        "instruments": ["Orbitrap Exploris 480", "Orbitrap Astral"],
        "analysis_tools": ["MaxQuant", "MSFragger", "PhosphoSitePlus"],
        "sample_prep": [
            "Cell lysis + digestion (as global)",
            "Phosphopeptide enrichment (TiO2 beads or Fe-IMAC)",
            "Optional: TMT labelling before enrichment",
            "nanoLC-MS/MS (long gradient, 120 min)",
        ],
        "depth": "10000-30000 phosphosites",
        "categories": ["phospho", "signalling", "mechanosensing"],
    },
    "Secretome": {
        "description": "Conditioned media analysis — cytokines, growth factors, ECM shed into media.",
        "acquisition": "DIA",
        "quantification": "LFQ",
        "enrichment": "",
        "instruments": ["Orbitrap", "timsTOF Pro"],
        "analysis_tools": ["DIA-NN", "MaxQuant"],
        "sample_prep": [
            "Condition cells in serum-free media (24-48h)",
            "Collect conditioned media, centrifuge to remove debris",
            "Concentrate (TCA precipitation or molecular weight cutoff filter)",
            "Digest + desalt",
        ],
        "depth": "500-2000 proteins",
        "notes": "CRITICAL: serum-containing media must be depleted before analysis.",
        "categories": ["secretome", "cytokines", "paracrine"],
    },
    "ECM / Matrisome": {
        "description": "Detergent-enrichment to isolate deposited ECM. Quantifies collagen/fibronectin/laminin.",
        "acquisition": "DDA",
        "quantification": "LFQ",
        "enrichment": "Detergent decellularisation",
        "instruments": ["Orbitrap"],
        "analysis_tools": ["MaxQuant", "Matrisome Project DB"],
        "sample_prep": [
            "Sequential detergent extraction (NaCl → SDS → GuHCl)",
            "ECM fraction = insoluble residue after detergent steps",
            "Digest with trypsin (may need multiple enzymes for crosslinked ECM)",
        ],
        "depth": "100-300 ECM proteins",
        "categories": ["ecm", "scaffold", "remodelling"],
    },
    "Surface Proteomics": {
        "description": "Biotinylation of cell surface proteins → streptavidin pulldown → MS.",
        "acquisition": "DDA",
        "quantification": "LFQ",
        "enrichment": "Biotinylation + streptavidin",
        "instruments": ["Orbitrap"],
        "analysis_tools": ["MaxQuant", "STRING"],
        "sample_prep": [
            "Cell surface biotinylation (Sulfo-NHS-SS-Biotin, 30 min on ice)",
            "Quench, lyse cells",
            "Streptavidin pulldown of biotinylated proteins",
            "On-bead digest or elute + digest",
        ],
        "depth": "500-1500 surface proteins",
        "categories": ["surface", "receptor", "integrin"],
    },
    "Protein Corona": {
        "description": "Incubate material in serum/plasma → recover adsorbed proteins → MS.",
        "acquisition": "DIA",
        "quantification": "LFQ",
        "enrichment": "",
        "instruments": ["Orbitrap", "timsTOF Pro"],
        "analysis_tools": ["DIA-NN", "MaxQuant"],
        "sample_prep": [
            "Incubate material in 55% human plasma (37°C, 1h or time series)",
            "Wash material (PBS × 3) to remove soft corona",
            "Elute hard corona (2% SDS or 8M urea)",
            "Digest + nanoLC-MS/MS",
        ],
        "depth": "100-500 corona proteins",
        "categories": ["corona", "biocompatibility", "immune_response"],
    },
}

# Key corona proteins to watch
CORONA_PROTEINS: Dict[str, Dict] = {
    "Vitronectin": {
        "role": "Promotes cell attachment via aVb3 integrin",
        "flag": "pro_adhesion",
    },
    "Fibronectin": {
        "role": "Major adhesion protein, binds a5b1 integrin, promotes spreading",
        "flag": "pro_adhesion",
    },
    "Albumin": {
        "role": "Most abundant plasma protein, often anti-adhesive (surface passivation)",
        "flag": "anti_adhesion",
    },
    "Complement C3": {
        "role": "Complement activation → opsonisation → macrophage phagocytosis",
        "flag": "immune_activation",
    },
    "Complement C4": {
        "role": "Classical pathway complement component",
        "flag": "immune_activation",
    },
    "Complement C5": {
        "role": "Terminal complement → membrane attack complex (MAC)",
        "flag": "immune_activation",
    },
    "IgG": {
        "role": "Opsonisation marker — FcγR-mediated phagocytosis",
        "flag": "immune_activation",
    },
    "Fibrinogen": {
        "role": "Acute phase protein, promotes macrophage attachment",
        "flag": "inflammatory",
    },
    "ApoA-I": {
        "role": "Competitive binder, can displace functional proteins",
        "flag": "passivation",
    },
    "ApoE": {
        "role": "Competitive binder, nanoparticle brain targeting (receptor-mediated)",
        "flag": "targeting",
    },
}

# Matrisome categories (from the Naba lab Matrisome Project)
MATRISOME_CATEGORIES: Dict[str, List[str]] = {
    "Core Matrisome - Collagens": [
        "COL1A1", "COL1A2", "COL2A1", "COL3A1", "COL4A1", "COL4A2",
        "COL5A1", "COL5A2", "COL6A1", "COL6A2", "COL6A3",
        "COL10A1", "COL11A1", "COL12A1", "COL14A1",
    ],
    "Core Matrisome - Glycoproteins": [
        "FN1", "LAMB1", "LAMB2", "LAMC1", "TNC", "SPARC", "THBS1",
        "THBS2", "FBLN1", "FBLN2", "POSTN", "VTN", "NID1", "NID2",
    ],
    "Core Matrisome - Proteoglycans": [
        "ACAN", "VCAN", "DCN", "BGN", "LUM", "FMOD",
        "HSPG2", "SDC1", "SDC4", "GPC1",
    ],
    "Matrisome-associated - ECM Regulators": [
        "MMP1", "MMP2", "MMP3", "MMP9", "MMP13", "MMP14",
        "TIMP1", "TIMP2", "TIMP3",
        "LOX", "LOXL2", "TGM2",
        "ADAM10", "ADAM17", "ADAMTS4", "ADAMTS5",
    ],
    "Matrisome-associated - ECM-affiliated": [
        "ANXA1", "ANXA2", "ANXA5", "LGALS1", "LGALS3",
        "PLOD1", "PLOD2", "P4HA1", "P4HA2",
    ],
    "Matrisome-associated - Secreted Factors": [
        "TGFB1", "TGFB2", "BMP2", "BMP4", "BMP7",
        "VEGFA", "FGF2", "PDGFB", "IGF1", "EGF",
        "CTGF", "CYR61", "WNT3A", "WNT5A",
    ],
}


# ── Integrin-ECM Ligand Matrix ───────────────────────────────────────────────

INTEGRIN_LIGANDS: Dict[str, Dict[str, List[str]]] = {
    "a5b1": {"ligands": ["Fibronectin"], "genes": ["ITGA5", "ITGB1"]},
    "aVb3": {"ligands": ["Vitronectin", "Fibronectin", "Osteopontin"], "genes": ["ITGAV", "ITGB3"]},
    "a2b1": {"ligands": ["Collagen I", "Collagen IV"], "genes": ["ITGA2", "ITGB1"]},
    "a1b1": {"ligands": ["Collagen I", "Collagen IV", "Laminin"], "genes": ["ITGA1", "ITGB1"]},
    "a6b1": {"ligands": ["Laminin"], "genes": ["ITGA6", "ITGB1"]},
    "a6b4": {"ligands": ["Laminin"], "genes": ["ITGA6", "ITGB4"]},
    "aVb5": {"ligands": ["Vitronectin"], "genes": ["ITGAV", "ITGB5"]},
    "aVb1": {"ligands": ["Fibronectin"], "genes": ["ITGAV", "ITGB1"]},
    "a4b1": {"ligands": ["Fibronectin (IIICS)", "VCAM-1"], "genes": ["ITGA4", "ITGB1"]},
    "aIIbb3": {"ligands": ["Fibrinogen", "Fibronectin", "vWF"], "genes": ["ITGA2B", "ITGB3"]},
}


# ── STRING PPI Client ────────────────────────────────────────────────────────

class ProteomicsClient:
    """Query STRING for protein-protein interactions."""

    STRING_API = "https://string-db.org/api"

    def __init__(self, species: int = 9606, score_threshold: float = 0.7):
        """
        Args:
            species:          NCBI taxonomy ID (9606 = human)
            score_threshold:  STRING combined score cutoff (0-1, 0.7 = high confidence)
        """
        self.species = species
        self.threshold = score_threshold
        self._last_request = 0.0

    def get_interaction_partners(
        self,
        proteins: List[str],
        limit: int = 20,
    ) -> PPINetwork:
        """
        Query STRING for interaction partners of given proteins.

        Args:
            proteins:  list of gene symbols (e.g. ["ITGB1", "PTK2"])
            limit:     max partners per protein

        Returns:
            PPINetwork with edges and hub identification.
        """
        if not proteins:
            return PPINetwork(query_proteins=[], error="No proteins provided")

        try:
            import requests
        except ImportError:
            return PPINetwork(query_proteins=proteins, error="requests library not available")

        self._rate_limit()

        try:
            url = f"{self.STRING_API}/json/network"
            params = {
                "identifiers": "%0d".join(proteins),
                "species": self.species,
                "required_score": int(self.threshold * 1000),
                "limit": limit,
                "caller_identity": "BioHackathonAnalyser",
            }
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            return self._parse_string_network(proteins, data)

        except Exception as e:
            logger.error(f"STRING API query failed: {e}")
            return PPINetwork(query_proteins=proteins, error=str(e))

    def get_enrichment(self, proteins: List[str]) -> List[Dict]:
        """Get functional enrichment for a protein list from STRING."""
        if not proteins:
            return []

        try:
            import requests
        except ImportError:
            return []

        self._rate_limit()

        try:
            url = f"{self.STRING_API}/json/enrichment"
            params = {
                "identifiers": "%0d".join(proteins),
                "species": self.species,
                "caller_identity": "BioHackathonAnalyser",
            }
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"STRING enrichment failed: {e}")
            return []

    def _parse_string_network(self, query: List[str], data: list) -> PPINetwork:
        """Parse STRING JSON response into PPINetwork."""
        edges = []
        nodes = set()

        for edge in data:
            a = edge.get("preferredName_A", edge.get("stringId_A", ""))
            b = edge.get("preferredName_B", edge.get("stringId_B", ""))
            score = edge.get("score", 0)

            if not a or not b:
                continue

            nodes.add(a)
            nodes.add(b)
            edges.append(PPIEdge(
                protein_a=a,
                protein_b=b,
                score=round(float(score), 3),
            ))

        # Identify hub proteins (top degree nodes)
        degree = {}
        for e in edges:
            degree[e.protein_a] = degree.get(e.protein_a, 0) + 1
            degree[e.protein_b] = degree.get(e.protein_b, 0) + 1

        sorted_nodes = sorted(degree.items(), key=lambda x: x[1], reverse=True)
        hubs = [n for n, d in sorted_nodes[:5] if d >= 3]

        return PPINetwork(
            query_proteins=query,
            edges=edges,
            nodes=sorted(nodes),
            hub_proteins=hubs,
            n_edges=len(edges),
            n_nodes=len(nodes),
        )

    def _rate_limit(self):
        elapsed = time.time() - self._last_request
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        self._last_request = time.time()


# ── Workflow Recommendation ──────────────────────────────────────────────────

def recommend_workflow(
    question: str,
    material: str = "",
    cell_type: str = "",
) -> List[ProtWorkflowRec]:
    """
    Recommend proteomics workflow(s) based on research question.

    Args:
        question:   e.g. "protein corona", "signalling pathways", "ECM remodelling"
        material:   optional material context
        cell_type:  optional cell type

    Returns:
        List of ProtWorkflowRec, priority-sorted.
    """
    q_lower = f"{question} {material} {cell_type}".lower()

    _PATTERNS = {
        "Global Discovery": ["global", "proteome", "differential", "discovery", "overall"],
        "Phosphoproteomics": ["phospho", "signall", "kinase", "pfak", "pyap", "psmad", "perk",
                              "mechanosens"],
        "Secretome": ["secretome", "conditioned media", "cytokine", "paracrine", "growth factor"],
        "ECM / Matrisome": ["ecm", "matrisome", "collagen", "fibronectin", "laminin",
                            "extracellular matrix", "remodel"],
        "Surface Proteomics": ["surface protein", "receptor", "integrin express", "cell surface",
                               "adhesion molecule"],
        "Protein Corona": ["corona", "adsorb", "serum protein", "biofouling", "implant surface"],
    }

    recs = []
    for wf_name, keywords in _PATTERNS.items():
        if not any(kw in q_lower for kw in keywords):
            continue

        info = PROTEOMICS_TYPES[wf_name]
        rec = ProtWorkflowRec(
            workflow_type=wf_name.lower().replace(" ", "_").replace("/", "_"),
            name=wf_name,
            description=info["description"],
            acquisition=info["acquisition"],
            quantification=info["quantification"],
            enrichment=info.get("enrichment", ""),
            instruments=info.get("instruments", []),
            analysis_tools=info.get("analysis_tools", []),
            sample_prep=info.get("sample_prep", []),
            cost_flag="very_high" if "Phospho" in wf_name else "high",
            turnaround="3-6 weeks" if "Phospho" in wf_name else "2-4 weeks",
            notes=info.get("notes", ""),
        )
        recs.append(rec)

    # Default to global discovery if nothing matched
    if not recs:
        info = PROTEOMICS_TYPES["Global Discovery"]
        recs.append(ProtWorkflowRec(
            workflow_type="dia_global",
            name="Global Discovery",
            description=info["description"],
            acquisition="DIA",
            quantification="LFQ",
            instruments=info.get("instruments", []),
            analysis_tools=info.get("analysis_tools", []),
            sample_prep=info.get("sample_prep", []),
        ))

    for i, r in enumerate(recs, 1):
        r.priority = i

    return recs


def classify_corona(proteins: List[str]) -> Dict[str, List[str]]:
    """
    Classify a list of corona proteins by their biomaterial relevance.

    Returns dict with keys: pro_adhesion, anti_adhesion, immune_activation,
    inflammatory, passivation, targeting, unknown.
    """
    classified = {
        "pro_adhesion": [],
        "anti_adhesion": [],
        "immune_activation": [],
        "inflammatory": [],
        "passivation": [],
        "targeting": [],
        "unknown": [],
    }

    for p in proteins:
        matched = False
        for name, info in CORONA_PROTEINS.items():
            if name.lower() in p.lower() or p.lower() in name.lower():
                flag = info["flag"]
                if flag in classified:
                    classified[flag].append(p)
                matched = True
                break
        if not matched:
            classified["unknown"].append(p)

    return classified


def get_integrin_ligands(expressed_integrins: List[str]) -> Dict[str, List[str]]:
    """
    Given a list of expressed integrin subunits (gene symbols),
    return the ECM ligands they bind.
    """
    result = {}
    expressed_upper = {g.upper() for g in expressed_integrins}

    for heterodimer, info in INTEGRIN_LIGANDS.items():
        genes = {g.upper() for g in info["genes"]}
        if genes & expressed_upper:
            result[heterodimer] = info["ligands"]

    return result
