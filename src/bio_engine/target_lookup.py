"""
Target Lookup
=============
Given a gene symbol or UniProt ID, find small molecule modulators
via ChEMBL, OpenTargets, and PubChem REST APIs.

All APIs are free with no key required.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)


# ── Data classes ──────────────────────────────────────────────

@dataclass
class CompoundHit:
    """A compound found to modulate the target."""
    compound_name: str
    compound_id: str           # ChEMBL ID, PubChem CID, or DrugBank ID
    source: str                # "ChEMBL", "OpenTargets", "PubChem"
    mode: str                  # "inhibitor", "activator", "modulator", "unknown"
    potency: str               # e.g. "IC50 = 12 nM", "Ki = 45 nM", "N/A"
    potency_nm: Optional[float] = None  # numeric nM value for sorting
    clinical_stage: str = "preclinical"  # "approved", "phase_3", "phase_2", "phase_1", "preclinical"
    organism_tested: str = ""
    toxicity_flag: str = ""
    mechanism: str = ""
    indication: str = ""


@dataclass
class TargetInfo:
    """Basic info about the queried target."""
    gene_symbol: str
    uniprot_id: str
    protein_name: str
    druggability: str          # "druggable", "partially_druggable", "undruggable", "unknown"
    protein_class: str         # e.g. "kinase", "GPCR", "ion_channel"


@dataclass
class TargetLookupResult:
    """Full result of a target lookup."""
    query: str
    target_info: Optional[TargetInfo]
    compounds: List[CompoundHit]
    sources_queried: List[str]
    errors: List[str]


# ── Known target classes (offline KB for common biomaterials targets) ────

_TARGET_KB: Dict[str, Dict] = {
    "VEGFA": {
        "uniprot": "P15692", "name": "Vascular endothelial growth factor A",
        "druggability": "druggable", "class": "growth_factor",
        "compounds": [
            CompoundHit("Bevacizumab", "CHEMBL1201583", "ChEMBL", "inhibitor",
                        "Kd ~ 58 pM", 0.058, "approved", "human",
                        mechanism="Anti-VEGF monoclonal antibody",
                        indication="Colorectal cancer, NSCLC, glioblastoma"),
            CompoundHit("Ranibizumab", "CHEMBL1201822", "ChEMBL", "inhibitor",
                        "Kd ~ 46 pM", 0.046, "approved", "human",
                        mechanism="Anti-VEGF Fab fragment",
                        indication="Wet AMD, diabetic macular edema"),
        ],
    },
    "TGFB1": {
        "uniprot": "P01137", "name": "Transforming growth factor beta-1",
        "druggability": "druggable", "class": "growth_factor",
        "compounds": [
            CompoundHit("Fresolimumab", "CHEMBL2108475", "ChEMBL", "inhibitor",
                        "Kd ~ 1 nM", 1.0, "phase_2", "human",
                        mechanism="Anti-TGF-beta monoclonal antibody",
                        indication="Fibrosis, cancer"),
            CompoundHit("Galunisertib", "CHEMBL3545110", "ChEMBL", "inhibitor",
                        "IC50 = 56 nM", 56.0, "phase_2", "human",
                        mechanism="TGF-beta R1 kinase inhibitor (ALK5)",
                        indication="Hepatocellular carcinoma, fibrosis"),
            CompoundHit("Pirfenidone", "CHEMBL1256391", "ChEMBL", "inhibitor",
                        "IC50 ~ 500 nM (indirect)", 500.0, "approved", "human",
                        mechanism="Anti-fibrotic, reduces TGF-beta signalling",
                        indication="Idiopathic pulmonary fibrosis"),
        ],
    },
    "TNF": {
        "uniprot": "P01375", "name": "Tumor necrosis factor",
        "druggability": "druggable", "class": "cytokine",
        "compounds": [
            CompoundHit("Infliximab", "CHEMBL1201581", "ChEMBL", "inhibitor",
                        "Kd ~ 44 pM", 0.044, "approved", "human",
                        mechanism="Anti-TNF chimeric monoclonal antibody",
                        indication="RA, Crohn's, UC, ankylosing spondylitis"),
            CompoundHit("Adalimumab", "CHEMBL1201580", "ChEMBL", "inhibitor",
                        "Kd ~ 100 pM", 0.1, "approved", "human",
                        mechanism="Fully human anti-TNF antibody",
                        indication="RA, psoriasis, Crohn's"),
            CompoundHit("Etanercept", "CHEMBL1201572", "ChEMBL", "inhibitor",
                        "Kd ~ 300 pM", 0.3, "approved", "human",
                        mechanism="TNF receptor-Fc fusion protein",
                        indication="RA, psoriatic arthritis"),
        ],
    },
    "IL6": {
        "uniprot": "P05231", "name": "Interleukin-6",
        "druggability": "druggable", "class": "cytokine",
        "compounds": [
            CompoundHit("Tocilizumab", "CHEMBL1201834", "ChEMBL", "inhibitor",
                        "Kd ~ 2.5 nM", 2.5, "approved", "human",
                        mechanism="Anti-IL-6R monoclonal antibody",
                        indication="RA, giant cell arteritis, CRS"),
            CompoundHit("Siltuximab", "CHEMBL1742990", "ChEMBL", "inhibitor",
                        "Kd ~ 0.9 nM", 0.9, "approved", "human",
                        mechanism="Anti-IL-6 chimeric antibody",
                        indication="Castleman disease"),
        ],
    },
    "MMP9": {
        "uniprot": "P14780", "name": "Matrix metalloproteinase-9 (Gelatinase B)",
        "druggability": "druggable", "class": "metalloprotease",
        "compounds": [
            CompoundHit("Andecaliximab (GS-5745)", "CHEMBL4297564", "ChEMBL", "inhibitor",
                        "Ki ~ 0.2 nM", 0.2, "phase_3", "human",
                        mechanism="Anti-MMP-9 monoclonal antibody",
                        indication="Gastric cancer, ulcerative colitis"),
            CompoundHit("Marimastat", "CHEMBL302237", "ChEMBL", "inhibitor",
                        "IC50 = 3 nM", 3.0, "phase_3", "human",
                        mechanism="Broad-spectrum MMP inhibitor (hydroxamate)",
                        indication="Cancer (failed -- musculoskeletal toxicity)"),
        ],
    },
    "RUNX2": {
        "uniprot": "Q13950", "name": "Runt-related transcription factor 2",
        "druggability": "partially_druggable", "class": "transcription_factor",
        "compounds": [
            CompoundHit("BMP-2 (recombinant)", "CHEMBL2108730", "ChEMBL", "activator",
                        "EC50 ~ 10-100 nM (indirect via Smad)", 50.0, "approved", "human",
                        mechanism="Upstream activator of RUNX2 via BMP/Smad pathway",
                        indication="Spinal fusion, bone healing"),
        ],
    },
    "HIF1A": {
        "uniprot": "Q16665", "name": "Hypoxia-inducible factor 1-alpha",
        "druggability": "druggable", "class": "transcription_factor",
        "compounds": [
            CompoundHit("Roxadustat", "CHEMBL3707373", "ChEMBL", "activator",
                        "IC50 = 19 nM (PHD2 inhibitor)", 19.0, "approved", "human",
                        mechanism="Prolyl hydroxylase inhibitor -- stabilises HIF-1a",
                        indication="Anaemia of chronic kidney disease"),
            CompoundHit("Belzutifan", "CHEMBL4594382", "ChEMBL", "inhibitor",
                        "IC50 ~ 9 nM (HIF-2a)", 9.0, "approved", "human",
                        mechanism="HIF-2a inhibitor (related pathway)",
                        indication="VHL-associated renal cell carcinoma"),
            CompoundHit("Acriflavine", "CHEMBL504", "ChEMBL", "inhibitor",
                        "IC50 ~ 1 uM", 1000.0, "preclinical", "human/mouse",
                        mechanism="Blocks HIF-1a/HIF-1b dimerisation",
                        indication="Preclinical anti-angiogenic"),
        ],
    },
    "PTGS2": {
        "uniprot": "P35354", "name": "Prostaglandin-endoperoxide synthase 2 (COX-2)",
        "druggability": "druggable", "class": "oxidoreductase",
        "compounds": [
            CompoundHit("Celecoxib", "CHEMBL118", "ChEMBL", "inhibitor",
                        "IC50 = 40 nM", 40.0, "approved", "human",
                        mechanism="Selective COX-2 inhibitor",
                        indication="Osteoarthritis, rheumatoid arthritis, pain"),
            CompoundHit("Indomethacin", "CHEMBL6", "ChEMBL", "inhibitor",
                        "IC50 = 26 nM", 26.0, "approved", "human",
                        mechanism="Non-selective COX inhibitor (NSAID)",
                        indication="Inflammation, gout, patent ductus arteriosus"),
        ],
    },
    "ALPL": {
        "uniprot": "P05186", "name": "Alkaline phosphatase, tissue-nonspecific",
        "druggability": "druggable", "class": "hydrolase",
        "compounds": [
            CompoundHit("Asfotase alfa (Strensiq)", "CHEMBL2108090", "ChEMBL", "activator",
                        "Enzyme replacement", None, "approved", "human",
                        mechanism="Recombinant TNSALP-Fc fusion enzyme replacement",
                        indication="Hypophosphatasia"),
            CompoundHit("Levamisole", "CHEMBL1473", "ChEMBL", "inhibitor",
                        "IC50 ~ 10 uM", 10000.0, "approved", "human",
                        mechanism="ALP inhibitor (used as histochemistry control)",
                        indication="ALP staining control; antihelminthic"),
        ],
    },
    "NFKB1": {
        "uniprot": "P19838", "name": "Nuclear factor NF-kappa-B p105/p50",
        "druggability": "partially_druggable", "class": "transcription_factor",
        "compounds": [
            CompoundHit("Bortezomib", "CHEMBL325041", "ChEMBL", "inhibitor",
                        "IC50 = 3.3 nM (proteasome)", 3.3, "approved", "human",
                        mechanism="Proteasome inhibitor -- blocks IkBa degradation, indirect NF-kB inhibition",
                        indication="Multiple myeloma, mantle cell lymphoma"),
            CompoundHit("BAY 11-7082", "CHEMBL295951", "ChEMBL", "inhibitor",
                        "IC50 ~ 10 uM", 10000.0, "preclinical", "human/mouse",
                        mechanism="IKK inhibitor -- blocks NF-kB activation",
                        indication="Research tool compound"),
        ],
    },
}


# ── Public API ───────────────────────────────────────────────

def lookup_target(
    query: str,
    mode_filter: str = "all",           # "inhibitor", "activator", "all"
    clinical_filter: str = "all",       # "approved", "clinical", "all"
    max_potency_nm: Optional[float] = None,
    use_api: bool = False,
) -> TargetLookupResult:
    """Look up small molecule modulators for a gene/protein target.

    Parameters
    ----------
    query : str
        Gene symbol (e.g. "VEGFA") or UniProt ID (e.g. "P15692").
    mode_filter : str
        Filter by mode of action.
    clinical_filter : str
        Filter by clinical stage.
    max_potency_nm : float, optional
        Maximum potency threshold in nM.
    use_api : bool
        If True, also query ChEMBL REST API (requires network).

    Returns
    -------
    TargetLookupResult
    """
    query_upper = query.strip().upper()
    errors: List[str] = []
    sources = ["local_kb"]

    # Try local KB first
    target_info = None
    compounds: List[CompoundHit] = []

    kb_entry = _TARGET_KB.get(query_upper)
    if not kb_entry:
        # Try matching by UniProt ID
        for sym, entry in _TARGET_KB.items():
            if entry["uniprot"].upper() == query_upper:
                kb_entry = entry
                query_upper = sym
                break

    if kb_entry:
        target_info = TargetInfo(
            gene_symbol=query_upper,
            uniprot_id=kb_entry["uniprot"],
            protein_name=kb_entry["name"],
            druggability=kb_entry["druggability"],
            protein_class=kb_entry["class"],
        )
        compounds = list(kb_entry.get("compounds", []))

    # Optionally query ChEMBL API
    if use_api:
        try:
            api_compounds = _query_chembl_by_target(query_upper)
            compounds.extend(api_compounds)
            sources.append("ChEMBL_API")
        except Exception as e:
            errors.append(f"ChEMBL API error: {e}")

    # Apply filters
    if mode_filter != "all":
        compounds = [c for c in compounds if c.mode == mode_filter]

    if clinical_filter == "approved":
        compounds = [c for c in compounds if c.clinical_stage == "approved"]
    elif clinical_filter == "clinical":
        compounds = [c for c in compounds
                     if c.clinical_stage in ("approved", "phase_3", "phase_2", "phase_1")]

    if max_potency_nm is not None:
        compounds = [c for c in compounds
                     if c.potency_nm is not None and c.potency_nm <= max_potency_nm]

    # Sort by clinical stage then potency
    stage_order = {"approved": 0, "phase_3": 1, "phase_2": 2, "phase_1": 3, "preclinical": 4}
    compounds.sort(key=lambda c: (
        stage_order.get(c.clinical_stage, 5),
        c.potency_nm if c.potency_nm is not None else 1e9,
    ))

    # Deduplicate by compound_id
    seen_ids = set()
    unique = []
    for c in compounds:
        if c.compound_id not in seen_ids:
            seen_ids.add(c.compound_id)
            unique.append(c)
    compounds = unique

    if not target_info:
        target_info = TargetInfo(
            gene_symbol=query_upper,
            uniprot_id="",
            protein_name=f"Unknown target: {query_upper}",
            druggability="unknown",
            protein_class="unknown",
        )
        if not compounds:
            errors.append(
                f"Target '{query_upper}' not found in local KB. "
                f"Enable API queries or check gene symbol."
            )

    return TargetLookupResult(
        query=query,
        target_info=target_info,
        compounds=compounds,
        sources_queried=sources,
        errors=errors,
    )


def list_known_targets() -> List[str]:
    """Return gene symbols in the local KB."""
    return list(_TARGET_KB.keys())


def get_target_info(gene_symbol: str) -> Optional[TargetInfo]:
    """Quick lookup of target info without compound search."""
    entry = _TARGET_KB.get(gene_symbol.upper())
    if not entry:
        return None
    return TargetInfo(
        gene_symbol=gene_symbol.upper(),
        uniprot_id=entry["uniprot"],
        protein_name=entry["name"],
        druggability=entry["druggability"],
        protein_class=entry["class"],
    )


# ── Private helpers ──────────────────────────────────────────

def _query_chembl_by_target(gene_symbol: str) -> List[CompoundHit]:
    """Query ChEMBL REST API for bioactivity data by target gene symbol."""
    import urllib.request
    import json

    # Step 1: resolve gene symbol to ChEMBL target ID
    url = (
        f"https://www.ebi.ac.uk/chembl/api/data/target/search.json"
        f"?q={quote(gene_symbol)}&limit=1"
    )
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return []

    targets = data.get("targets", [])
    if not targets:
        return []

    target_chembl_id = targets[0].get("target_chembl_id", "")
    if not target_chembl_id:
        return []

    # Step 2: get bioactivity data
    url2 = (
        f"https://www.ebi.ac.uk/chembl/api/data/activity.json"
        f"?target_chembl_id={target_chembl_id}"
        f"&standard_type__in=IC50,Ki,EC50,Kd"
        f"&limit=20"
    )
    try:
        req2 = urllib.request.Request(url2, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req2, timeout=15) as resp2:
            data2 = json.loads(resp2.read().decode())
    except Exception:
        return []

    compounds = []
    seen = set()
    for act in data2.get("activities", []):
        mol_id = act.get("molecule_chembl_id", "")
        if mol_id in seen:
            continue
        seen.add(mol_id)

        std_type = act.get("standard_type", "")
        std_value = act.get("standard_value")
        std_units = act.get("standard_units", "")

        potency_str = "N/A"
        potency_nm = None
        if std_value:
            try:
                val = float(std_value)
                if std_units == "nM":
                    potency_nm = val
                elif std_units == "uM":
                    potency_nm = val * 1000
                potency_str = f"{std_type} = {std_value} {std_units}"
            except (ValueError, TypeError):
                pass

        compounds.append(CompoundHit(
            compound_name=act.get("molecule_pref_name", mol_id) or mol_id,
            compound_id=mol_id,
            source="ChEMBL",
            mode="inhibitor" if std_type in ("IC50", "Ki") else "modulator",
            potency=potency_str,
            potency_nm=potency_nm,
            organism_tested=act.get("assay_organism", ""),
        ))

    return compounds
