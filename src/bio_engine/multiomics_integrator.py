"""
Multi-Omics Integrator — joint pathway enrichment, cross-omics correlation,
and latent factor analysis across transcriptomics + metabolomics + proteomics.

Implements three integration strategies (no external R/MOFA dependency):

1. **Joint Pathway Enrichment** — overlay DEGs and differential metabolites
   onto the same KEGG/Reactome pathways. Enzyme mRNA + substrate/product both
   changing = high-confidence pathway activity call.

2. **Cross-Omics Correlation** — Pearson/Spearman correlation between gene
   expression and metabolite abundance across matched samples.

3. **Latent Factor Analysis** — lightweight SVD-based multi-omics factor
   decomposition (MOFA-lite). Identifies shared variation across data layers.

Public API:
    from bio_engine.multiomics_integrator import (
        run_joint_pathway_enrichment,
        run_cross_omics_correlation,
        run_mofa_lite,
        make_demo_multiomics,
        JointPathwayHit,
        JointEnrichmentReport,
        CrossCorrelation,
        MOFAResult,
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class JointPathwayHit:
    """A pathway hit supported by both gene and metabolite evidence."""
    pathway_name:       str
    gene_evidence:      List[str]           # DEGs in this pathway
    metabolite_evidence: List[str]          # differential metabolites in this pathway
    gene_count:         int = 0
    metabolite_count:   int = 0
    combined_score:     float = 0.0         # weighted evidence score
    direction:          str = ""            # "concordant_up" | "concordant_down" | "mixed"
    confidence:         str = ""            # "high" | "medium" | "low"


@dataclass
class JointEnrichmentReport:
    """Full joint pathway enrichment result."""
    hits:               List[JointPathwayHit] = field(default_factory=list)
    n_input_genes:      int = 0
    n_input_metabolites: int = 0
    n_pathways_tested:  int = 0
    n_joint_hits:       int = 0             # pathways with both gene + metabolite evidence
    gene_only_hits:     List[str] = field(default_factory=list)
    metabolite_only_hits: List[str] = field(default_factory=list)
    error:              Optional[str] = None


@dataclass
class CrossCorrelation:
    """Single gene-metabolite correlation result."""
    gene:           str
    metabolite:     str
    r:              float           # correlation coefficient
    p_value:        float
    padj:           float = 1.0     # BH-corrected
    method:         str = "pearson"
    n_samples:      int = 0
    significant:    bool = False


@dataclass
class MOFAResult:
    """Multi-omics factor analysis (SVD-based) result."""
    factors:            np.ndarray          # (n_samples, n_factors)
    gene_weights:       pd.DataFrame        # genes x factors
    metabolite_weights: pd.DataFrame        # metabolites x factors
    variance_explained: Dict[str, List[float]]  # layer -> [var_per_factor]
    sample_names:       List[str] = field(default_factory=list)
    n_factors:          int = 0
    total_variance:     Dict[str, float] = field(default_factory=dict)
    error:              Optional[str] = None


# ── Joint pathway knowledge base ─────────────────────────────────────────────
# Maps pathway names to both gene members and metabolite members.
# This enables overlay: if both a gene AND a metabolite from the same pathway
# are differentially expressed/abundant, that's strong evidence.

JOINT_PATHWAY_DB: Dict[str, Dict[str, List[str]]] = {
    "Glycolysis / Gluconeogenesis": {
        "genes": [
            "HK1", "HK2", "GPI", "PFKL", "PFKM", "ALDOA", "ALDOB",
            "GAPDH", "PGK1", "ENO1", "ENO2", "PKM", "LDHA", "LDHB",
            "PCK1", "PCK2", "G6PC", "FBP1",
        ],
        "metabolites": [
            "glucose", "glucose-6-phosphate", "fructose-6-phosphate",
            "fructose-1,6-bisphosphate", "glyceraldehyde-3-phosphate",
            "pyruvate", "lactate", "phosphoenolpyruvate",
        ],
    },
    "TCA Cycle": {
        "genes": [
            "CS", "ACO1", "ACO2", "IDH1", "IDH2", "IDH3A", "OGDH",
            "SUCLA2", "SUCLG1", "SDHA", "SDHB", "FH", "MDH1", "MDH2",
            "DLST", "DLAT", "PDHA1",
        ],
        "metabolites": [
            "citrate", "isocitrate", "alpha-ketoglutarate", "succinate",
            "fumarate", "malate", "oxaloacetate", "acetyl-coa",
        ],
    },
    "Oxidative Phosphorylation": {
        "genes": [
            "NDUFA1", "NDUFB1", "NDUFS1", "SDHA", "SDHB", "UQCRC1",
            "UQCRC2", "CYC1", "COX4I1", "COX5A", "ATP5F1A", "ATP5F1B",
        ],
        "metabolites": [
            "nad+", "nadh", "fadh2", "atp", "adp", "amp",
        ],
    },
    "Collagen / ECM Biosynthesis": {
        "genes": [
            "COL1A1", "COL1A2", "COL3A1", "COL4A1", "COL5A1",
            "P4HA1", "P4HA2", "PLOD1", "PLOD2", "LOX", "LOXL2",
            "FN1", "LAMB1", "LAMC1", "SPARC", "TNC",
        ],
        "metabolites": [
            "proline", "hydroxyproline", "glycine", "ascorbate",
            "lysine", "hydroxylysine", "alpha-ketoglutarate",
        ],
    },
    "Glutathione / Oxidative Stress": {
        "genes": [
            "GSS", "GSR", "GPX1", "GPX4", "GSTM1", "GSTP1",
            "SOD1", "SOD2", "CAT", "HMOX1", "NQO1", "NFE2L2",
            "TXNRD1", "PRDX1",
        ],
        "metabolites": [
            "glutathione", "gssg", "cysteine", "glycine", "glutamate",
            "malondialdehyde", "4-hne", "8-ohdg",
        ],
    },
    "Arachidonic Acid / Inflammation": {
        "genes": [
            "PTGS2", "PTGS1", "ALOX5", "ALOX12", "ALOX15",
            "PLA2G4A", "TBXAS1", "PTGIS", "PTGES",
            "TNF", "IL6", "IL1B", "CXCL8",
        ],
        "metabolites": [
            "arachidonic acid", "pge2", "pgd2", "pgf2",
            "thromboxane", "leukotriene", "ltb4", "resolvin", "lipoxin",
        ],
    },
    "Purine Metabolism": {
        "genes": [
            "HPRT1", "APRT", "ADA", "PNP", "XDH", "IMPDH1", "IMPDH2",
            "GART", "ATIC", "ADSL",
        ],
        "metabolites": [
            "inosine", "hypoxanthine", "xanthine", "urate",
            "adenine", "guanine", "atp", "gtp", "amp", "gmp",
        ],
    },
    "Arginine / NO Signalling": {
        "genes": [
            "NOS1", "NOS2", "NOS3", "ARG1", "ARG2", "ASS1", "ASL",
            "ODC1", "SRM", "SMS",
        ],
        "metabolites": [
            "arginine", "citrulline", "ornithine", "nitric oxide",
            "putrescine", "spermidine", "spermine",
        ],
    },
    "Tryptophan / Kynurenine": {
        "genes": [
            "IDO1", "IDO2", "TDO2", "KMO", "KYNU", "HAAO",
            "QPRT", "TPH1", "DDC",
        ],
        "metabolites": [
            "tryptophan", "kynurenine", "kynurenic acid",
            "3-hydroxykynurenine", "quinolinic acid", "serotonin",
            "melatonin", "nad+",
        ],
    },
    "Sphingolipid Metabolism": {
        "genes": [
            "SMPD1", "SMPD2", "SPHK1", "SPHK2", "SGPL1",
            "CERS2", "CERS6", "ASAH1", "UGCG",
        ],
        "metabolites": [
            "sphingomyelin", "ceramide", "sphingosine",
            "sphingosine-1-phosphate", "glucosylceramide",
        ],
    },
    "Osteogenic Differentiation": {
        "genes": [
            "RUNX2", "SP7", "ALPL", "BGLAP", "SPP1", "COL1A1",
            "BMP2", "BMP4", "BMP7", "IBSP", "DLX5", "PHEX",
        ],
        "metabolites": [
            "calcium", "phosphate", "hydroxyapatite", "osteocalcin",
            "alkaline phosphatase", "proline", "ascorbate",
        ],
    },
    "HIF-1 / Hypoxia Response": {
        "genes": [
            "HIF1A", "EPAS1", "VEGFA", "LDHA", "SLC2A1", "ENO1",
            "PDK1", "BNIP3", "CA9", "PGK1", "ALDOA", "PKM",
        ],
        "metabolites": [
            "lactate", "succinate", "fumarate", "2-hydroxyglutarate",
            "glucose", "pyruvate",
        ],
    },
}


# ── 1. Joint Pathway Enrichment ──────────────────────────────────────────────

def run_joint_pathway_enrichment(
    deg_genes: List[str],
    diff_metabolites: List[str],
    gene_directions: Optional[Dict[str, str]] = None,
    metabolite_directions: Optional[Dict[str, str]] = None,
    min_evidence: int = 1,
) -> JointEnrichmentReport:
    """
    Overlay DEGs and differential metabolites onto shared pathways.

    Args:
        deg_genes:              list of DEG gene symbols
        diff_metabolites:       list of differential metabolite names
        gene_directions:        gene -> "up"/"down" (optional, for concordance)
        metabolite_directions:  metabolite -> "up"/"down" (optional)
        min_evidence:           minimum total hits (genes + metabolites) per pathway

    Returns:
        JointEnrichmentReport with ranked pathway hits.
    """
    if not deg_genes and not diff_metabolites:
        return JointEnrichmentReport(error="No input genes or metabolites provided")

    gene_directions = gene_directions or {}
    metabolite_directions = metabolite_directions or {}

    genes_upper = {g.upper() for g in deg_genes}
    metab_lower = {m.lower().strip() for m in diff_metabolites}

    hits = []
    gene_only = []
    metabolite_only = []

    for pathway_name, members in JOINT_PATHWAY_DB.items():
        pw_genes = {g.upper() for g in members["genes"]}
        pw_metabs = {m.lower() for m in members["metabolites"]}

        gene_overlap = genes_upper & pw_genes
        metab_overlap = metab_lower & pw_metabs

        total = len(gene_overlap) + len(metab_overlap)
        if total < min_evidence:
            continue

        if gene_overlap and metab_overlap:
            # Both layers have evidence — joint hit
            direction = _infer_joint_direction(
                gene_overlap, metab_overlap,
                gene_directions, metabolite_directions,
            )
            confidence = "high" if (len(gene_overlap) >= 2 and len(metab_overlap) >= 1) else "medium"

            # Score: genes weighted 1.0, metabolites 1.5 (rarer, more specific)
            score = len(gene_overlap) * 1.0 + len(metab_overlap) * 1.5

            hits.append(JointPathwayHit(
                pathway_name=pathway_name,
                gene_evidence=sorted(gene_overlap),
                metabolite_evidence=sorted(metab_overlap),
                gene_count=len(gene_overlap),
                metabolite_count=len(metab_overlap),
                combined_score=round(score, 2),
                direction=direction,
                confidence=confidence,
            ))
        elif gene_overlap:
            gene_only.append(pathway_name)
        elif metab_overlap:
            metabolite_only.append(pathway_name)

    # Sort by combined score descending
    hits.sort(key=lambda h: h.combined_score, reverse=True)

    return JointEnrichmentReport(
        hits=hits,
        n_input_genes=len(deg_genes),
        n_input_metabolites=len(diff_metabolites),
        n_pathways_tested=len(JOINT_PATHWAY_DB),
        n_joint_hits=len(hits),
        gene_only_hits=gene_only,
        metabolite_only_hits=metabolite_only,
    )


def _infer_joint_direction(
    gene_overlap: set, metab_overlap: set,
    gene_dirs: Dict[str, str], metab_dirs: Dict[str, str],
) -> str:
    """Infer whether gene + metabolite changes are concordant."""
    gene_ups = sum(1 for g in gene_overlap if gene_dirs.get(g.upper(), gene_dirs.get(g, "")) == "up")
    gene_downs = sum(1 for g in gene_overlap if gene_dirs.get(g.upper(), gene_dirs.get(g, "")) == "down")
    metab_ups = sum(1 for m in metab_overlap if metab_dirs.get(m.lower(), metab_dirs.get(m, "")) == "up")
    metab_downs = sum(1 for m in metab_overlap if metab_dirs.get(m.lower(), metab_dirs.get(m, "")) == "down")

    total_up = gene_ups + metab_ups
    total_down = gene_downs + metab_downs

    if total_up > 0 and total_down == 0:
        return "concordant_up"
    elif total_down > 0 and total_up == 0:
        return "concordant_down"
    elif total_up > 0 and total_down > 0:
        return "mixed"
    return ""


# ── 2. Cross-Omics Correlation ──────────────────────────────────────────────

def run_cross_omics_correlation(
    gene_matrix: pd.DataFrame,
    metabolite_matrix: pd.DataFrame,
    method: str = "pearson",
    padj_threshold: float = 0.05,
    top_n: int = 50,
) -> List[CrossCorrelation]:
    """
    Compute gene-metabolite correlations across matched samples.

    Args:
        gene_matrix:        genes x samples DataFrame
        metabolite_matrix:  metabolites x samples DataFrame
        method:             "pearson" or "spearman"
        padj_threshold:     FDR threshold for significance
        top_n:              max results to return (sorted by abs(r))

    Returns:
        List of CrossCorrelation results, sorted by |r| descending.
    """
    # Find shared samples
    shared = sorted(set(gene_matrix.columns) & set(metabolite_matrix.columns))
    if len(shared) < 4:
        logger.warning(f"Only {len(shared)} shared samples — need >= 4 for correlation")
        return []

    gmat = gene_matrix[shared]
    mmat = metabolite_matrix[shared]

    # Filter to variable genes/metabolites (avoid flat lines)
    gene_var = gmat.var(axis=1)
    metab_var = mmat.var(axis=1)
    genes = gene_var[gene_var > 0].index.tolist()
    metabs = metab_var[metab_var > 0].index.tolist()

    if not genes or not metabs:
        return []

    # Limit to top variable features for performance
    max_features = 200
    if len(genes) > max_features:
        genes = gene_var.loc[genes].nlargest(max_features).index.tolist()
    if len(metabs) > max_features:
        metabs = metab_var.loc[metabs].nlargest(max_features).index.tolist()

    from scipy import stats as sp_stats

    results = []
    for gene in genes:
        gvals = gmat.loc[gene].values.astype(float)
        for metab in metabs:
            mvals = mmat.loc[metab].values.astype(float)

            if method == "spearman":
                r, p = sp_stats.spearmanr(gvals, mvals)
            else:
                r, p = sp_stats.pearsonr(gvals, mvals)

            if np.isnan(r):
                continue

            results.append(CrossCorrelation(
                gene=gene,
                metabolite=metab,
                r=round(float(r), 4),
                p_value=float(p),
                method=method,
                n_samples=len(shared),
            ))

    # BH FDR correction
    if results:
        results = _bh_correct_correlations(results)

    # Filter and sort
    results = [r for r in results if r.padj <= padj_threshold]
    results.sort(key=lambda x: abs(x.r), reverse=True)

    # Mark significant
    for r in results:
        r.significant = True

    return results[:top_n]


def _bh_correct_correlations(results: List[CrossCorrelation]) -> List[CrossCorrelation]:
    """Apply Benjamini-Hochberg correction to correlation p-values."""
    n = len(results)
    if n == 0:
        return results

    # Sort by p-value
    indexed = sorted(enumerate(results), key=lambda x: x[1].p_value)
    for rank, (idx, _) in enumerate(indexed, 1):
        padj = results[idx].p_value * n / rank
        results[idx].padj = min(padj, 1.0)

    # Enforce monotonicity (from bottom up)
    prev = 1.0
    for rank in range(n - 1, -1, -1):
        idx = indexed[rank][0]
        results[idx].padj = min(results[idx].padj, prev)
        prev = results[idx].padj

    return results


# ── 3. MOFA-lite (SVD-based latent factor analysis) ─────────────────────────

def run_mofa_lite(
    gene_matrix: pd.DataFrame,
    metabolite_matrix: pd.DataFrame,
    n_factors: int = 5,
    scale: bool = True,
) -> MOFAResult:
    """
    Lightweight multi-omics factor analysis using concatenated SVD.

    Concatenates gene and metabolite matrices (matched samples),
    decomposes via SVD, and reports per-layer variance explained
    by each factor.

    Args:
        gene_matrix:        genes x samples DataFrame
        metabolite_matrix:  metabolites x samples DataFrame
        n_factors:          number of latent factors to extract
        scale:              z-score normalise each feature before SVD

    Returns:
        MOFAResult with factors, weights, and variance explained per layer.
    """
    shared = sorted(set(gene_matrix.columns) & set(metabolite_matrix.columns))
    if len(shared) < 3:
        return MOFAResult(
            factors=np.array([]), gene_weights=pd.DataFrame(),
            metabolite_weights=pd.DataFrame(), variance_explained={},
            error=f"Need >= 3 shared samples, found {len(shared)}",
        )

    gmat = gene_matrix[shared].copy()
    mmat = metabolite_matrix[shared].copy()

    # Filter zero-variance features
    gmat = gmat.loc[gmat.var(axis=1) > 0]
    mmat = mmat.loc[mmat.var(axis=1) > 0]

    if gmat.empty or mmat.empty:
        return MOFAResult(
            factors=np.array([]), gene_weights=pd.DataFrame(),
            metabolite_weights=pd.DataFrame(), variance_explained={},
            error="No variable features after filtering",
        )

    # Z-score normalisation
    if scale:
        gmat = ((gmat.T - gmat.mean(axis=1)) / (gmat.std(axis=1) + 1e-10)).T
        mmat = ((mmat.T - mmat.mean(axis=1)) / (mmat.std(axis=1) + 1e-10)).T

    # Concatenate: features x samples
    n_genes = len(gmat)
    n_metabs = len(mmat)
    combined = pd.concat([gmat, mmat], axis=0)  # (n_genes + n_metabs) x n_samples

    # SVD
    X = combined.values  # features x samples
    n_factors = min(n_factors, min(X.shape) - 1, 10)
    if n_factors < 1:
        n_factors = 1

    # Center columns (samples)
    X = X - X.mean(axis=0, keepdims=True)

    U, S, Vt = np.linalg.svd(X, full_matrices=False)

    # Factors = sample scores (Vt[:k] transposed)
    factors = Vt[:n_factors].T  # (n_samples, n_factors)

    # Weights = feature loadings (U * S)
    loadings = U[:, :n_factors] * S[:n_factors]  # (n_features, n_factors)

    gene_weights = pd.DataFrame(
        loadings[:n_genes],
        index=gmat.index,
        columns=[f"Factor{i+1}" for i in range(n_factors)],
    )
    metabolite_weights = pd.DataFrame(
        loadings[n_genes:],
        index=mmat.index,
        columns=[f"Factor{i+1}" for i in range(n_factors)],
    )

    # Variance explained per layer per factor
    total_var = float(np.sum(S**2))
    gene_var_explained = []
    metab_var_explained = []

    for f in range(n_factors):
        # Reconstruct factor contribution
        factor_reconstruction = np.outer(U[:, f] * S[f], Vt[f])
        gene_part = factor_reconstruction[:n_genes]
        metab_part = factor_reconstruction[n_genes:]

        gene_orig = X[:n_genes]
        metab_orig = X[n_genes:]

        g_total = float(np.sum(gene_orig**2)) if np.sum(gene_orig**2) > 0 else 1.0
        m_total = float(np.sum(metab_orig**2)) if np.sum(metab_orig**2) > 0 else 1.0

        gene_var_explained.append(round(float(np.sum(gene_part**2)) / g_total * 100, 2))
        metab_var_explained.append(round(float(np.sum(metab_part**2)) / m_total * 100, 2))

    return MOFAResult(
        factors=factors,
        gene_weights=gene_weights,
        metabolite_weights=metabolite_weights,
        variance_explained={
            "transcriptomics": gene_var_explained,
            "metabolomics": metab_var_explained,
        },
        sample_names=shared,
        n_factors=n_factors,
        total_variance={
            "transcriptomics": round(sum(gene_var_explained), 2),
            "metabolomics": round(sum(metab_var_explained), 2),
        },
    )


# ── Demo data generator ─────────────────────────────────────────────────────

def make_demo_multiomics(
    n_samples: int = 12,
    n_genes: int = 200,
    n_metabolites: int = 50,
    seed: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame, List[str], List[str]]:
    """
    Generate matched demo transcriptomics + metabolomics data.

    Returns:
        (gene_matrix, metabolite_matrix, group_a_samples, group_b_samples)

    The data has a shared latent factor driving coordinated changes
    in a subset of genes (glycolysis/TCA) and metabolites (lactate, pyruvate).
    """
    rng = np.random.default_rng(seed)

    samples = [f"S{i+1:02d}" for i in range(n_samples)]
    half = n_samples // 2
    group_a = samples[:half]    # control
    group_b = samples[half:]    # material-exposed

    # Gene names: use some real pathway genes + random
    real_genes = [
        "HIF1A", "VEGFA", "LDHA", "PKM", "ENO1", "SLC2A1",  # HIF-1/glycolysis
        "COL1A1", "COL1A2", "FN1", "SPARC", "LOX",           # ECM
        "PTGS2", "IL6", "TNF", "CXCL8",                      # inflammation
        "SOD2", "CAT", "GPX1", "HMOX1", "NQO1",              # oxidative stress
    ]
    filler_genes = [f"GENE_{i}" for i in range(n_genes - len(real_genes))]
    all_genes = real_genes + filler_genes

    # Metabolite names: use real pathway metabolites + random
    real_metabs = [
        "lactate", "pyruvate", "glucose", "citrate", "succinate",
        "glutathione", "proline", "hydroxyproline", "glycine",
        "arachidonic acid", "pge2", "arginine", "glutamate",
    ]
    filler_metabs = [f"metab_{i}" for i in range(n_metabolites - len(real_metabs))]
    all_metabs = real_metabs + filler_metabs

    # Baseline expression
    gene_data = rng.lognormal(mean=4, sigma=1.0, size=(n_genes, n_samples))
    metab_data = rng.lognormal(mean=6, sigma=0.8, size=(n_metabolites, n_samples))

    # Inject shared signal: HIF-1/glycolysis genes + lactate/pyruvate UP in group B
    effect_genes = list(range(6))   # first 6 = HIF-1 genes
    effect_metabs = list(range(3))  # first 3 = lactate, pyruvate, glucose

    for idx in effect_genes:
        gene_data[idx, half:] *= rng.uniform(2.0, 4.0)

    for idx in effect_metabs:
        metab_data[idx, half:] *= rng.uniform(1.5, 3.0)

    # ECM genes up in group B
    for idx in range(6, 11):
        gene_data[idx, half:] *= rng.uniform(1.8, 3.0)

    # Oxidative stress metabolites
    metab_data[5, half:] *= 0.5   # glutathione DOWN (oxidative stress)

    gene_df = pd.DataFrame(gene_data, index=all_genes, columns=samples)
    metab_df = pd.DataFrame(metab_data, index=all_metabs, columns=samples)

    return gene_df, metab_df, group_a, group_b
