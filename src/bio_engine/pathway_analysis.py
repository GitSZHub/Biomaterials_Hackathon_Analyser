"""
Pathway Enrichment Analysis — KEGG, Reactome, GO enrichment for DEG lists.

Primary:   g:Profiler REST API (free, no key, GO + KEGG + Reactome in one call).
Fallback:  Local ORA (Fisher's exact test) against curated biomaterial gene sets.

Public API:
    from bio_engine.pathway_analysis import run_enrichment, EnrichmentResult

    results = run_enrichment(
        gene_list  = ["TGFB1", "SMAD3", "COL1A1", ...],
        organism   = "hsapiens",
        sources    = ["GO:BP", "KEGG", "REAC"],
    )
    for r in results:
        print(r.source, r.term_name, r.padj, r.genes)

Also:
    gsea_results = run_preranked_gsea(
        ranked_genes = {"TGFB1": 3.2, "SMAD3": 2.1, ...},  # gene -> log2FC
    )
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ── g:Profiler source codes ──────────────────────────────────────────────────
# https://biit.cs.ut.ee/gprofiler/page/apis
GPROFILER_SOURCES = {
    "GO:BP":  "GO:BP",   # Gene Ontology Biological Process
    "GO:MF":  "GO:MF",   # Gene Ontology Molecular Function
    "GO:CC":  "GO:CC",   # Gene Ontology Cellular Component
    "KEGG":   "KEGG",    # KEGG pathways
    "REAC":   "REAC",    # Reactome pathways
    "WP":     "WP",      # WikiPathways
    "HP":     "HP",      # Human Phenotype Ontology
}

GPROFILER_URL = "https://biit.cs.ut.ee/gprofiler/api/gost/profile/"


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class EnrichmentResult:
    """Single enriched term / pathway."""
    source:         str             # GO:BP | GO:MF | GO:CC | KEGG | REAC | LOCAL
    term_id:        str             # e.g. GO:0006954, hsa04010, R-HSA-1280215
    term_name:      str             # human-readable name
    p_value:        float           # raw p-value
    padj:           float           # corrected p-value (g:SCS or BH)
    term_size:      int             # total genes in this term
    query_size:     int             # genes in user list
    intersection:   int             # overlap count
    genes:          List[str]       # overlapping gene symbols
    direction:      str = ""        # "up" | "down" | "mixed" (set by caller)
    precision:      float = 0.0     # intersection / query_size
    recall:         float = 0.0     # intersection / term_size

    def __post_init__(self):
        if self.query_size > 0:
            self.precision = self.intersection / self.query_size
        if self.term_size > 0:
            self.recall = self.intersection / self.term_size


@dataclass
class GSEAResult:
    """Single GSEA result for a gene set."""
    source:     str
    term_name:  str
    es:         float       # enrichment score
    nes:        float       # normalised enrichment score
    p_value:    float
    fdr:        float
    leading_edge: List[str]
    size:       int


@dataclass
class PathwayReport:
    """Full pathway enrichment report from a DEG analysis."""
    enrichment_results: List[EnrichmentResult] = field(default_factory=list)
    gsea_results:       List[GSEAResult]       = field(default_factory=list)
    n_input_genes:      int = 0
    n_background:       int = 0
    organism:           str = "hsapiens"
    sources_queried:    List[str] = field(default_factory=list)
    method:             str = ""        # "gprofiler" | "local_ora"
    error:              Optional[str] = None

    # Biomaterial-relevant pathway flags (convenience)
    biomaterial_flags:  List[str] = field(default_factory=list)


# ── Curated biomaterial-relevant gene sets (local fallback) ──────────────────
# Expanded from transcriptomics.PATHWAY_GENES to ~20 sets.

BIOMATERIAL_GENE_SETS: Dict[str, List[str]] = {
    "Inflammation (NFkB)": [
        "NFKB1", "NFKB2", "RELA", "RELB", "IL6", "TNF", "CXCL8", "IL1B",
        "IL1A", "CXCL1", "CXCL2", "CCL2", "CCL5", "ICAM1", "VCAM1",
        "PTGS2", "MMP9", "TRAF6", "IRAK4", "MYD88",
    ],
    "JAK-STAT (IL-6)": [
        "STAT3", "STAT1", "STAT5A", "STAT5B", "JAK1", "JAK2", "JAK3",
        "IL6ST", "SOCS1", "SOCS3", "IFNG", "IL10", "IL6", "IL4",
    ],
    "TGF-beta / Fibrosis": [
        "TGFB1", "TGFB2", "TGFB3", "SMAD2", "SMAD3", "SMAD4", "SMAD7",
        "COL1A1", "COL1A2", "COL3A1", "FN1", "ACTA2", "SERPINE1",
        "CTGF", "TGFBR1", "TGFBR2", "LTBP1", "BMP2", "BMP4", "BMP7",
    ],
    "YAP/TAZ (Mechanosensing)": [
        "YAP1", "WWTR1", "CYR61", "CTGF", "AMOTL2", "LATS1", "LATS2",
        "MST1", "MST2", "MOB1A", "MOB1B", "TEAD1", "TEAD4", "ANKRD1",
    ],
    "Integrin Signalling": [
        "ITGB1", "ITGB3", "ITGA5", "ITGA6", "ITGAV", "ITGA2", "ITGA1",
        "PTK2", "SRC", "PXN", "VCL", "TLN1", "FERMT2", "ILK",
    ],
    "Focal Adhesion": [
        "PTK2", "SRC", "PXN", "VCL", "TLN1", "FERMT2", "ILK",
        "ROCK1", "ROCK2", "RHOA", "RAC1", "CDC42", "PAK1",
        "ACTN1", "ZYX", "VASP",
    ],
    "Wnt Signalling": [
        "WNT3A", "WNT5A", "WNT1", "CTNNB1", "APC", "GSK3B", "AXIN1",
        "AXIN2", "FZD1", "LRP5", "LRP6", "DVL1", "LEF1", "TCF7",
    ],
    "Apoptosis": [
        "TP53", "BCL2", "BCL2L1", "BAX", "BAK1", "CASP3", "CASP9",
        "CASP8", "CASP7", "PARP1", "BID", "CYCS", "APAF1", "XIAP",
        "BIRC5", "FAS", "FASLG",
    ],
    "PI3K/AKT/mTOR": [
        "PIK3CA", "PIK3CB", "PIK3R1", "AKT1", "AKT2", "PTEN", "MTOR",
        "RPS6KB1", "EIF4EBP1", "RPTOR", "RICTOR", "TSC1", "TSC2",
    ],
    "MAPK/ERK": [
        "MAPK1", "MAPK3", "MAP2K1", "MAP2K2", "RAF1", "BRAF", "KRAS",
        "HRAS", "GRB2", "SOS1", "EGF", "EGFR", "FOS", "JUN",
    ],
    "Cell Cycle": [
        "CCND1", "CCNE1", "CCNA2", "CCNB1", "CDK4", "CDK6", "CDK2",
        "CDK1", "CDKN1A", "CDKN2A", "RB1", "E2F1", "MKI67", "PCNA",
    ],
    "HIF-1 / Hypoxia": [
        "HIF1A", "EPAS1", "VEGFA", "LDHA", "SLC2A1", "ENO1", "PDK1",
        "BNIP3", "BNIP3L", "CA9", "PGK1", "ALDOA", "PKM",
    ],
    "Osteogenic Differentiation": [
        "RUNX2", "SP7", "ALPL", "BGLAP", "SPP1", "COL1A1", "BMP2",
        "BMP4", "BMP7", "IBSP", "DLX5", "MSX2", "PHEX", "DMP1",
    ],
    "Chondrogenic Differentiation": [
        "SOX9", "COL2A1", "ACAN", "COL10A1", "COL11A1", "COMP",
        "HAPLN1", "MATN3", "IHH", "PRG4", "GDF5", "FGFR3",
    ],
    "Angiogenesis": [
        "VEGFA", "VEGFB", "VEGFC", "KDR", "FLT1", "ANGPT1", "ANGPT2",
        "TEK", "NOS3", "PECAM1", "CDH5", "HIF1A", "FGF2", "PDGFB",
    ],
    "ECM Remodelling": [
        "MMP1", "MMP2", "MMP3", "MMP9", "MMP13", "MMP14", "TIMP1",
        "TIMP2", "TIMP3", "ADAM10", "ADAM17", "ADAMTS4", "ADAMTS5",
        "LOX", "LOXL2", "TGM2",
    ],
    "Oxidative Stress / ROS": [
        "SOD1", "SOD2", "CAT", "GPX1", "GPX4", "HMOX1", "NQO1",
        "NFE2L2", "KEAP1", "TXNRD1", "PRDX1", "PRDX2", "GSR",
    ],
    "Autophagy": [
        "BECN1", "MAP1LC3B", "ATG5", "ATG7", "ATG12", "SQSTM1",
        "ULK1", "MTOR", "LAMP1", "LAMP2", "TFEB", "ATG16L1",
    ],
    "Foreign Body Response": [
        "TNF", "IL1B", "IL6", "CCL2", "CCR2", "CSF1", "CSF1R",
        "CD68", "CD163", "MRC1", "ITGAM", "ARG1", "NOS2",
        "TGFB1", "PDGFB", "ACTA2", "COL1A1",
    ],
    "Complement Activation": [
        "C3", "C5", "C1QA", "C1QB", "C1QC", "CFB", "CFD", "CFH",
        "CFI", "C4A", "C4B", "MASP1", "MASP2", "MBL2", "CR1", "CD55",
    ],
}


# ── Main public API ──────────────────────────────────────────────────────────

def run_enrichment(
    gene_list: List[str],
    organism: str = "hsapiens",
    sources: Optional[List[str]] = None,
    padj_threshold: float = 0.05,
    background: Optional[List[str]] = None,
) -> PathwayReport:
    """
    Run pathway enrichment on a gene list.

    Tries g:Profiler API first; falls back to local ORA if network unavailable.

    Args:
        gene_list:      List of gene symbols (e.g. from significant DEGs).
        organism:       g:Profiler organism code (default "hsapiens").
        sources:        Which databases to query (default: GO:BP, KEGG, REAC).
        padj_threshold: Only return terms with padj below this.
        background:     Optional background gene list for ORA.

    Returns:
        PathwayReport with enrichment results sorted by padj.
    """
    if sources is None:
        sources = ["GO:BP", "KEGG", "REAC"]

    gene_list = [g.strip().upper() for g in gene_list if g.strip()]
    if not gene_list:
        return PathwayReport(error="Empty gene list.")

    report = PathwayReport(
        n_input_genes=len(gene_list),
        organism=organism,
        sources_queried=sources,
    )

    # Try g:Profiler first
    try:
        results = _gprofiler_query(gene_list, organism, sources, padj_threshold)
        report.enrichment_results = results
        report.method = "gprofiler"
        logger.info(f"g:Profiler returned {len(results)} significant terms")
    except Exception as e:
        logger.warning(f"g:Profiler failed ({e}), falling back to local ORA")
        try:
            results = _local_ora(gene_list, padj_threshold, background)
            report.enrichment_results = results
            report.method = "local_ora"
        except Exception as e2:
            report.error = f"Both g:Profiler and local ORA failed: {e2}"
            return report

    # Flag biomaterial-relevant pathways
    report.biomaterial_flags = _flag_biomaterial_pathways(report.enrichment_results)

    return report


def run_enrichment_split(
    up_genes: List[str],
    down_genes: List[str],
    organism: str = "hsapiens",
    sources: Optional[List[str]] = None,
    padj_threshold: float = 0.05,
) -> PathwayReport:
    """
    Run enrichment separately on up- and down-regulated genes,
    then merge results with direction labels.
    """
    report = PathwayReport(
        n_input_genes=len(up_genes) + len(down_genes),
        organism=organism,
        sources_queried=sources or ["GO:BP", "KEGG", "REAC"],
    )

    all_results = []

    if up_genes:
        up_report = run_enrichment(up_genes, organism, sources, padj_threshold)
        for r in up_report.enrichment_results:
            r.direction = "up"
        all_results.extend(up_report.enrichment_results)
        if up_report.error:
            report.error = up_report.error
        report.method = up_report.method

    if down_genes:
        down_report = run_enrichment(down_genes, organism, sources, padj_threshold)
        for r in down_report.enrichment_results:
            r.direction = "down"
        all_results.extend(down_report.enrichment_results)
        if down_report.error and not report.error:
            report.error = down_report.error
        if not report.method:
            report.method = down_report.method

    # Sort by padj
    all_results.sort(key=lambda r: r.padj)
    report.enrichment_results = all_results
    report.biomaterial_flags = _flag_biomaterial_pathways(all_results)

    return report


def run_preranked_gsea(
    ranked_genes: Dict[str, float],
    gene_sets: Optional[Dict[str, List[str]]] = None,
    min_size: int = 5,
    max_size: int = 500,
    n_perm: int = 1000,
    seed: int = 42,
) -> List[GSEAResult]:
    """
    Simple pre-ranked GSEA against curated biomaterial gene sets.

    Args:
        ranked_genes: dict of gene_symbol -> ranking metric (e.g. log2FC).
        gene_sets:    dict of set_name -> list of gene symbols.
                      Defaults to BIOMATERIAL_GENE_SETS.
        min_size:     minimum gene set size after filtering.
        max_size:     maximum gene set size after filtering.
        n_perm:       number of permutations for p-value estimation.

    Returns:
        List of GSEAResult sorted by absolute NES.
    """
    if gene_sets is None:
        gene_sets = BIOMATERIAL_GENE_SETS

    # Sort genes by metric (descending)
    all_genes = sorted(ranked_genes.keys(), key=lambda g: ranked_genes[g], reverse=True)
    n = len(all_genes)
    if n < 10:
        return []

    gene_rank = {g: i for i, g in enumerate(all_genes)}
    metrics = np.array([ranked_genes[g] for g in all_genes])

    rng = np.random.default_rng(seed)
    results = []

    for set_name, set_genes in gene_sets.items():
        # Filter to genes present in ranked list
        hits = [g for g in set_genes if g.upper() in gene_rank]
        if len(hits) < min_size or len(hits) > max_size:
            continue

        es, leading = _compute_es(all_genes, set(h.upper() for h in hits), metrics)

        # Permutation test
        null_es = np.zeros(n_perm)
        for i in range(n_perm):
            perm_hits = set(rng.choice(all_genes, size=len(hits), replace=False))
            null_es[i], _ = _compute_es(all_genes, perm_hits, metrics)

        # NES: normalise by mean of same-sign null
        pos_null = null_es[null_es >= 0]
        neg_null = null_es[null_es < 0]

        if es >= 0 and len(pos_null) > 0:
            nes = es / (np.mean(pos_null) + 1e-10)
        elif es < 0 and len(neg_null) > 0:
            nes = -es / (np.mean(np.abs(neg_null)) + 1e-10)
        else:
            nes = 0.0

        # P-value
        if es >= 0:
            p_val = np.mean(null_es >= es) if len(null_es) > 0 else 1.0
        else:
            p_val = np.mean(null_es <= es) if len(null_es) > 0 else 1.0

        results.append(GSEAResult(
            source="LOCAL",
            term_name=set_name,
            es=round(float(es), 4),
            nes=round(float(nes), 4),
            p_value=round(float(p_val), 6),
            fdr=0.0,  # computed below
            leading_edge=leading,
            size=len(hits),
        ))

    # BH FDR correction on GSEA p-values
    if results:
        pvals = np.array([r.p_value for r in results])
        fdrs = _bh_correction(pvals)
        for r, fdr in zip(results, fdrs):
            r.fdr = round(float(fdr), 6)

    # Sort by |NES| descending
    results.sort(key=lambda r: abs(r.nes), reverse=True)
    return results


# ── g:Profiler API ───────────────────────────────────────────────────────────

def _gprofiler_query(
    gene_list: List[str],
    organism: str,
    sources: List[str],
    padj_threshold: float,
) -> List[EnrichmentResult]:
    """Query g:Profiler REST API and parse results."""
    import requests

    payload = {
        "organism":        organism,
        "query":           gene_list,
        "sources":         sources,
        "user_threshold":  padj_threshold,
        "significance_threshold_method": "g_SCS",  # g:Profiler's multiple testing correction
        "all_results":     False,
        "ordered":         False,
        "no_evidences":    False,
    }

    resp = requests.post(GPROFILER_URL, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    results = []
    for item in data.get("result", []):
        er = EnrichmentResult(
            source=item.get("source", ""),
            term_id=item.get("native", ""),
            term_name=item.get("name", ""),
            p_value=item.get("p_value", 1.0),
            padj=item.get("p_value", 1.0),  # g:Profiler returns already corrected
            term_size=item.get("term_size", 0),
            query_size=item.get("query_size", 0),
            intersection=item.get("intersection_size", 0),
            genes=item.get("intersections", []),
        )
        results.append(er)

    results.sort(key=lambda r: r.padj)
    return results


# ── Local ORA (Fisher's exact test) ──────────────────────────────────────────

def _local_ora(
    gene_list: List[str],
    padj_threshold: float,
    background: Optional[List[str]] = None,
) -> List[EnrichmentResult]:
    """
    Over-representation analysis using Fisher's exact test
    against curated biomaterial gene sets.
    """
    from scipy.stats import fisher_exact

    gene_set_upper = {g.upper() for g in gene_list}
    query_size = len(gene_set_upper)

    # Background: union of all curated genes + query genes
    if background:
        bg = {g.upper() for g in background}
    else:
        bg = set(gene_set_upper)
        for genes in BIOMATERIAL_GENE_SETS.values():
            bg.update(g.upper() for g in genes)
    bg_size = len(bg)

    raw_results = []
    for set_name, set_genes in BIOMATERIAL_GENE_SETS.items():
        set_upper = {g.upper() for g in set_genes}
        overlap = gene_set_upper & set_upper
        if len(overlap) < 2:
            continue

        # 2x2 contingency: overlap, query-only, set-only, neither
        a = len(overlap)
        b = query_size - a
        c = len(set_upper & bg) - a
        d = bg_size - a - b - c
        if d < 0:
            d = 0

        _, p_val = fisher_exact([[a, b], [c, d]], alternative="greater")

        raw_results.append(EnrichmentResult(
            source="LOCAL",
            term_id=set_name.replace(" ", "_").replace("/", "_"),
            term_name=set_name,
            p_value=p_val,
            padj=p_val,  # corrected below
            term_size=len(set_upper),
            query_size=query_size,
            intersection=a,
            genes=sorted(overlap),
        ))

    # BH correction
    if raw_results:
        pvals = np.array([r.p_value for r in raw_results])
        padj = _bh_correction(pvals)
        for r, pa in zip(raw_results, padj):
            r.padj = round(float(pa), 6)

    # Filter and sort
    results = [r for r in raw_results if r.padj < padj_threshold]
    results.sort(key=lambda r: r.padj)
    return results


# ── GSEA helpers ─────────────────────────────────────────────────────────────

def _compute_es(
    ranked_genes: List[str],
    hit_set: set,
    metrics: np.ndarray,
) -> Tuple[float, List[str]]:
    """
    Compute enrichment score using weighted Kolmogorov-Smirnov statistic.
    Returns (ES, leading_edge_genes).
    """
    n = len(ranked_genes)
    n_hit = len(hit_set)
    n_miss = n - n_hit

    if n_hit == 0 or n_miss == 0:
        return 0.0, []

    # Weighted hit score (weight by |metric|)
    hit_weights = np.array([
        abs(metrics[i]) if ranked_genes[i].upper() in hit_set else 0.0
        for i in range(n)
    ])
    total_hit_weight = hit_weights.sum()
    if total_hit_weight == 0:
        return 0.0, []

    miss_penalty = 1.0 / n_miss

    running_sum = 0.0
    max_es = 0.0
    min_es = 0.0
    max_idx = 0
    leading = []

    for i in range(n):
        gene = ranked_genes[i].upper()
        if gene in hit_set:
            running_sum += hit_weights[i] / total_hit_weight
        else:
            running_sum -= miss_penalty

        if running_sum > max_es:
            max_es = running_sum
            max_idx = i
        if running_sum < min_es:
            min_es = running_sum

    # ES is the maximum deviation
    es = max_es if abs(max_es) >= abs(min_es) else min_es

    # Leading edge: hit genes up to peak
    if es >= 0:
        for i in range(max_idx + 1):
            if ranked_genes[i].upper() in hit_set:
                leading.append(ranked_genes[i])
    else:
        for i in range(n - 1, max_idx - 1, -1):
            if ranked_genes[i].upper() in hit_set:
                leading.append(ranked_genes[i])

    return es, leading


def _bh_correction(pvalues: np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg FDR correction."""
    n = len(pvalues)
    if n == 0:
        return pvalues
    idx = np.argsort(pvalues)
    padj = np.ones(n)
    cummin = 1.0
    for rank, i in enumerate(reversed(idx)):
        raw_adj = pvalues[i] * n / (n - rank)
        cummin = min(cummin, raw_adj)
        padj[i] = cummin
    return np.clip(padj, 0, 1)


# ── Biomaterial pathway flagging ─────────────────────────────────────────────

_BIOMATERIAL_KEYWORDS = {
    "inflammation": ["inflam", "nfkb", "nf-kappa", "interleukin", "cytokine", "tnf", "il-1", "il-6"],
    "fibrosis":     ["fibro", "tgf-beta", "tgfb", "smad", "collagen", "ecm"],
    "apoptosis":    ["apoptos", "caspase", "programmed cell death", "bcl-2", "p53"],
    "angiogenesis": ["angiogen", "vegf", "vascula", "endothel"],
    "mechanosensing": ["yap", "taz", "hippo", "mechano", "focal adhesion", "integrin"],
    "oxidative stress": ["oxidat", "ros", "reactive oxygen", "nrf2", "antioxidant", "glutathione"],
    "osteogenesis":  ["osteogen", "bone", "runx2", "ossif", "mineral"],
    "chondrogenesis": ["chondrogen", "cartilage", "sox9", "aggrecan"],
    "foreign body":  ["foreign body", "macrophage", "phagocyt", "complement"],
    "hypoxia":       ["hypox", "hif-1", "hif1", "oxygen"],
    "cell cycle":    ["cell cycle", "proliferat", "mitot", "g1/s", "g2/m"],
    "wnt":           ["wnt", "beta-catenin", "ctnnb"],
    "autophagy":     ["autophag", "beclin", "lc3", "atg"],
}


def _flag_biomaterial_pathways(results: List[EnrichmentResult]) -> List[str]:
    """Scan enrichment results for biomaterial-relevant pathway categories."""
    flags = set()
    for r in results:
        name_lower = r.term_name.lower()
        genes_str = " ".join(r.genes).lower()
        combined = name_lower + " " + genes_str
        for category, keywords in _BIOMATERIAL_KEYWORDS.items():
            if any(kw in combined for kw in keywords):
                direction_tag = f" ({r.direction})" if r.direction else ""
                flags.add(f"{category}{direction_tag}")
    return sorted(flags)


# ── Convenience: extract gene lists from DEGResult ───────────────────────────

def genes_from_deg_result(deg_result, padj_threshold: float = 0.05,
                          fc_threshold: float = 1.0) -> Tuple[List[str], List[str], Dict[str, float]]:
    """
    Extract up/down gene lists and ranked dict from a DEGResult.

    Returns:
        (up_genes, down_genes, ranked_dict)
    """
    up_genes = []
    down_genes = []
    ranked = {}

    for pt in deg_result.volcano_points:
        ranked[pt.gene] = pt.log2fc
        if pt.padj < padj_threshold and abs(pt.log2fc) >= fc_threshold:
            if pt.log2fc > 0:
                up_genes.append(pt.gene)
            else:
                down_genes.append(pt.gene)

    return up_genes, down_genes, ranked
