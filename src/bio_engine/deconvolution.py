"""
Bulk RNA Deconvolution — estimate cell type composition from bulk expression data.

Three methods available:
  1. Marker-based scoring (built-in, no external deps)
     Uses curated marker gene sets per cell type. Scores each sample
     by mean expression of marker genes. Fast, interpretable, always available.

  2. Non-negative least squares (NNLS) reference-based
     Given a single-cell reference signature matrix (cell_type x gene),
     fits bulk = signature @ proportions, with proportions >= 0 and sum-to-1.
     Requires a reference matrix (can come from CELLxGENE or user upload).

  3. Support Vector Regression (CIBERSORT-like)
     Nu-SVR with linear kernel on signature matrix. More robust to noise
     than NNLS. Requires scikit-learn.

Public API:
    from bio_engine.deconvolution import (
        deconvolve_markers,
        deconvolve_nnls,
        deconvolve_svr,
        DeconvolutionResult,
    )

    # Quick marker-based (always works)
    result = deconvolve_markers(bulk_matrix, tissue="bone")

    # Reference-based
    result = deconvolve_nnls(bulk_matrix, signature_matrix)
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
class DeconvolutionResult:
    """Cell type proportion estimates per sample."""
    proportions:    pd.DataFrame    # rows = samples, cols = cell types, values = [0,1]
    method:         str             # "markers" | "nnls" | "svr"
    cell_types:     List[str] = field(default_factory=list)
    sample_names:   List[str] = field(default_factory=list)
    residuals:      Optional[np.ndarray] = None   # fit residuals (reference methods)
    correlation:    Optional[float] = None         # overall fit correlation
    warnings:       List[str] = field(default_factory=list)
    error:          Optional[str] = None


# ── Curated marker gene sets ────────────────────────────────────────────────
# Organised by tissue context. Each cell type has 8-15 marker genes.
# These are canonical markers used in single-cell annotation literature.

MARKER_SETS: Dict[str, Dict[str, List[str]]] = {
    "general": {
        "Fibroblasts": [
            "COL1A1", "COL1A2", "COL3A1", "FN1", "VIM", "DCN", "LUM",
            "FAP", "PDGFRA", "THY1", "S100A4",
        ],
        "Endothelial": [
            "PECAM1", "CDH5", "VWF", "KDR", "FLT1", "ERG", "ENG",
            "EMCN", "CLDN5", "TIE1",
        ],
        "Macrophages": [
            "CD68", "CD163", "CSF1R", "MARCO", "MRC1", "MSR1",
            "ITGAM", "ADGRE1", "FCGR1A", "CD14",
        ],
        "T cells": [
            "CD3D", "CD3E", "CD3G", "CD4", "CD8A", "CD8B", "TRAC",
            "IL7R", "LEF1", "TCF7",
        ],
        "B cells": [
            "CD19", "MS4A1", "CD79A", "CD79B", "PAX5", "BANK1",
            "IGHM", "IGHD", "BLK",
        ],
        "NK cells": [
            "NKG7", "GNLY", "KLRD1", "KLRB1", "KLRC1", "NCAM1",
            "PRF1", "GZMB", "NCR1",
        ],
        "Epithelial": [
            "EPCAM", "KRT8", "KRT18", "KRT19", "CDH1", "CLDN4",
            "MUC1", "TJP1", "OCLN",
        ],
        "Smooth muscle": [
            "ACTA2", "MYH11", "TAGLN", "CNN1", "DES", "SMTN",
            "MYL9", "MYLK", "ACTG2",
        ],
        "Pericytes": [
            "RGS5", "PDGFRB", "NOTCH3", "MCAM", "CSPG4", "ABCC9",
            "KCNJ8", "DLK1",
        ],
        "Mast cells": [
            "KIT", "TPSAB1", "TPSB2", "CPA3", "HPGDS", "HDC",
            "FCER1A", "MS4A2",
        ],
        "Neutrophils": [
            "S100A8", "S100A9", "S100A12", "FCGR3B", "CSF3R",
            "CXCR2", "FPR1", "MMP8",
        ],
    },
    "bone": {
        "Osteoblasts": [
            "RUNX2", "SP7", "ALPL", "BGLAP", "SPP1", "COL1A1",
            "IBSP", "DLX5", "MSX2", "PHEX",
        ],
        "Osteoclasts": [
            "ACP5", "CTSK", "MMP9", "TNFRSF11A", "CALCR", "DCSTAMP",
            "OCSTAMP", "NFATC1", "TRAP",
        ],
        "Osteocytes": [
            "SOST", "DMP1", "MEPE", "FGF23", "PHEX", "PDPN",
            "GJA1", "TNFSF11",
        ],
        "MSCs": [
            "NT5E", "THY1", "ENG", "LEPR", "CXCL12", "VCAM1",
            "MCAM", "PDGFRA", "PDGFRB", "ALCAM",
        ],
        "Chondrocytes": [
            "SOX9", "COL2A1", "ACAN", "COL10A1", "COL11A1", "COMP",
            "PRG4", "HAPLN1",
        ],
    },
    "cartilage": {
        "Chondrocytes": [
            "SOX9", "COL2A1", "ACAN", "COL11A1", "COMP", "HAPLN1",
            "MATN3", "PRG4", "FGFR3",
        ],
        "Hypertrophic chondrocytes": [
            "COL10A1", "MMP13", "IHH", "RUNX2", "MEF2C", "VEGFA",
            "ALPL", "SPP1",
        ],
        "Synoviocytes": [
            "PRG4", "HAS1", "HAS2", "CDH11", "CD55", "UDPGD",
            "FLS", "CLIC5",
        ],
    },
    "skin": {
        "Keratinocytes": [
            "KRT14", "KRT5", "KRT10", "KRT1", "IVL", "LOR",
            "FLG", "DSG1", "DSC1",
        ],
        "Melanocytes": [
            "MITF", "TYR", "TYRP1", "DCT", "PMEL", "MLANA",
            "SOX10", "KIT",
        ],
        "Dermal fibroblasts": [
            "COL1A1", "COL3A1", "FN1", "DCN", "LUM", "PDGFRA",
            "FAP", "VIM",
        ],
    },
    "neural": {
        "Neurons": [
            "RBFOX3", "SYP", "SNAP25", "SYT1", "MAP2", "TUBB3",
            "ENO2", "NEFL", "NEFM",
        ],
        "Astrocytes": [
            "GFAP", "AQP4", "S100B", "ALDH1L1", "SLC1A2", "SLC1A3",
            "GJA1", "GLUL",
        ],
        "Oligodendrocytes": [
            "MBP", "PLP1", "MOG", "MAG", "OLIG2", "SOX10",
            "CNP", "CLDN11",
        ],
        "Microglia": [
            "CX3CR1", "P2RY12", "TMEM119", "ITGAM", "AIF1",
            "CSF1R", "CD68", "HEXB",
        ],
    },
    "liver": {
        "Hepatocytes": [
            "ALB", "APOB", "SERPINA1", "HNF4A", "CYP3A4", "CYP2E1",
            "TTR", "AFP", "ASGR1",
        ],
        "Cholangiocytes": [
            "KRT19", "KRT7", "EPCAM", "SOX9", "HNF1B", "CFTR",
            "AQP1", "MUC1",
        ],
        "Hepatic stellate": [
            "ACTA2", "COL1A1", "LRAT", "PDGFRB", "DES", "RGS5",
            "HGF", "TIMP1",
        ],
        "Kupffer cells": [
            "CD68", "CLEC4F", "MARCO", "CD163", "VSIG4", "TIMD4",
            "CSF1R",
        ],
    },
}


# ── Method 1: Marker-based scoring ──────────────────────────────────────────

def deconvolve_markers(
    bulk_matrix: pd.DataFrame,
    tissue: str = "general",
    custom_markers: Optional[Dict[str, List[str]]] = None,
    log_transform: bool = True,
) -> DeconvolutionResult:
    """
    Estimate cell type proportions from bulk RNA-seq using marker gene scoring.

    For each cell type, computes the mean expression of its marker genes
    across each sample, then normalises to proportions (sum-to-1 per sample).

    Args:
        bulk_matrix:     rows = genes, columns = samples
        tissue:          tissue context for marker selection
                         ("general", "bone", "cartilage", "skin", "neural", "liver")
        custom_markers:  optional dict of cell_type -> [gene_symbols] to override defaults
        log_transform:   if True, log2(x+1) transform before scoring

    Returns:
        DeconvolutionResult with proportions DataFrame.
    """
    # Select marker sets
    if custom_markers:
        markers = custom_markers
    else:
        markers = dict(MARKER_SETS.get("general", {}))
        tissue_markers = MARKER_SETS.get(tissue.lower(), {})
        markers.update(tissue_markers)

    if not markers:
        return DeconvolutionResult(
            proportions=pd.DataFrame(),
            method="markers",
            error=f"No marker sets for tissue '{tissue}'",
        )

    genes_upper = {g.upper(): g for g in bulk_matrix.index}
    samples = list(bulk_matrix.columns)

    # Optionally log-transform
    data = bulk_matrix.copy()
    if log_transform:
        data = np.log2(data + 1)

    # Score each cell type per sample
    scores = {}
    warnings = []
    for cell_type, marker_genes in markers.items():
        present = [genes_upper[g.upper()] for g in marker_genes if g.upper() in genes_upper]
        if len(present) < 2:
            warnings.append(
                f"{cell_type}: only {len(present)}/{len(marker_genes)} markers found"
            )
            if len(present) == 0:
                continue

        # Mean expression of marker genes per sample
        scores[cell_type] = data.loc[present].mean(axis=0).values

    if not scores:
        return DeconvolutionResult(
            proportions=pd.DataFrame(),
            method="markers",
            error="No cell types with enough marker genes in the data.",
            warnings=warnings,
        )

    # Build score matrix and normalise to proportions
    score_df = pd.DataFrame(scores, index=samples)

    # Shift to non-negative (subtract row min if any negatives)
    score_df = score_df.clip(lower=0)

    # Normalise each sample to sum = 1
    row_sums = score_df.sum(axis=1)
    row_sums = row_sums.replace(0, 1)  # avoid div by zero
    proportions = score_df.div(row_sums, axis=0)

    return DeconvolutionResult(
        proportions=proportions,
        method="markers",
        cell_types=list(proportions.columns),
        sample_names=samples,
        warnings=warnings,
    )


# ── Method 2: NNLS reference-based ──────────────────────────────────────────

def deconvolve_nnls(
    bulk_matrix: pd.DataFrame,
    signature: pd.DataFrame,
    log_transform: bool = True,
) -> DeconvolutionResult:
    """
    Reference-based deconvolution using non-negative least squares.

    Solves: bulk_sample = signature @ proportions (per sample)
    with proportions >= 0, then normalises to sum-to-1.

    Args:
        bulk_matrix:  rows = genes, columns = samples
        signature:    rows = genes, columns = cell types (mean expression per type)
        log_transform: if True, log2(x+1) transform both inputs

    Returns:
        DeconvolutionResult with proportions and fit residuals.
    """
    from scipy.optimize import nnls

    # Align genes
    common_genes = sorted(set(bulk_matrix.index) & set(signature.index))
    if len(common_genes) < 10:
        return DeconvolutionResult(
            proportions=pd.DataFrame(),
            method="nnls",
            error=f"Only {len(common_genes)} overlapping genes (need >= 10).",
        )

    bulk = bulk_matrix.loc[common_genes].copy()
    sig = signature.loc[common_genes].copy()

    if log_transform:
        bulk = np.log2(bulk + 1)
        sig = np.log2(sig + 1)

    S = sig.values  # (n_genes, n_cell_types)
    samples = list(bulk.columns)
    cell_types = list(sig.columns)

    proportions_list = []
    residuals = []

    for sample in samples:
        b = bulk[sample].values
        coef, residual = nnls(S, b)
        # Normalise to sum-to-1
        total = coef.sum()
        if total > 0:
            coef = coef / total
        proportions_list.append(coef)
        residuals.append(residual)

    prop_df = pd.DataFrame(proportions_list, index=samples, columns=cell_types)

    # Overall fit correlation
    reconstructed = S @ prop_df.T.values
    from scipy.stats import pearsonr
    flat_orig = bulk.values.flatten()
    flat_recon = reconstructed.flatten()
    corr, _ = pearsonr(flat_orig, flat_recon)

    return DeconvolutionResult(
        proportions=prop_df,
        method="nnls",
        cell_types=cell_types,
        sample_names=samples,
        residuals=np.array(residuals),
        correlation=round(float(corr), 4),
    )


# ── Method 3: SVR (CIBERSORT-like) ──────────────────────────────────────────

def deconvolve_svr(
    bulk_matrix: pd.DataFrame,
    signature: pd.DataFrame,
    nu: float = 0.5,
    log_transform: bool = True,
) -> DeconvolutionResult:
    """
    CIBERSORT-style deconvolution using nu-SVR with linear kernel.

    More robust to noise and collinearity than NNLS.
    Requires scikit-learn.

    Args:
        bulk_matrix:  rows = genes, columns = samples
        signature:    rows = genes, columns = cell types
        nu:           SVR nu parameter (0, 1]. Lower = sparser solution.
        log_transform: log2(x+1) transform both inputs

    Returns:
        DeconvolutionResult with proportions.
    """
    try:
        from sklearn.svm import NuSVR
    except ImportError:
        return DeconvolutionResult(
            proportions=pd.DataFrame(),
            method="svr",
            error="scikit-learn not installed. Run: pip install scikit-learn",
        )

    # Align genes
    common_genes = sorted(set(bulk_matrix.index) & set(signature.index))
    if len(common_genes) < 10:
        return DeconvolutionResult(
            proportions=pd.DataFrame(),
            method="svr",
            error=f"Only {len(common_genes)} overlapping genes.",
        )

    bulk = bulk_matrix.loc[common_genes].copy()
    sig = signature.loc[common_genes].copy()

    if log_transform:
        bulk = np.log2(bulk + 1)
        sig = np.log2(sig + 1)

    S = sig.values
    samples = list(bulk.columns)
    cell_types = list(sig.columns)

    proportions_list = []
    for sample in samples:
        b = bulk[sample].values
        coefs = np.zeros(len(cell_types))
        for j in range(len(cell_types)):
            svr = NuSVR(nu=min(nu, 0.99), kernel="linear", C=1.0)
            svr.fit(S[:, j].reshape(-1, 1), b)
            coefs[j] = max(svr.coef_[0][0], 0)

        total = coefs.sum()
        if total > 0:
            coefs = coefs / total
        proportions_list.append(coefs)

    prop_df = pd.DataFrame(proportions_list, index=samples, columns=cell_types)

    return DeconvolutionResult(
        proportions=prop_df,
        method="svr",
        cell_types=cell_types,
        sample_names=samples,
    )


# ── Reference signature builders ────────────────────────────────────────────

def build_signature_from_markers(
    tissue: str = "general",
) -> pd.DataFrame:
    """
    Build a pseudo-signature matrix from marker gene sets.
    Each cell type gets 1.0 for its markers and 0.0 elsewhere.

    Useful as a simple reference when no single-cell data is available.
    """
    markers = dict(MARKER_SETS.get("general", {}))
    markers.update(MARKER_SETS.get(tissue.lower(), {}))

    all_genes = set()
    for genes in markers.values():
        all_genes.update(g.upper() for g in genes)

    gene_list = sorted(all_genes)
    cell_types = list(markers.keys())

    sig = pd.DataFrame(0.0, index=gene_list, columns=cell_types)
    for ct, genes in markers.items():
        for g in genes:
            if g.upper() in sig.index:
                sig.loc[g.upper(), ct] = 1.0

    return sig


def make_demo_bulk_with_composition(
    n_genes: int = 500,
    n_samples: int = 8,
    tissue: str = "general",
    seed: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generate demo bulk matrix with known cell type compositions for testing.

    Returns (bulk_matrix, true_proportions).
    """
    rng = np.random.default_rng(seed)

    markers = dict(MARKER_SETS.get("general", {}))
    markers.update(MARKER_SETS.get(tissue.lower(), {}))
    cell_types = list(markers.keys())

    # Collect all marker genes
    all_marker_genes = []
    for genes in markers.values():
        all_marker_genes.extend(g.upper() for g in genes)
    all_marker_genes = sorted(set(all_marker_genes))

    # Build gene list: markers + random genes
    genes = list(all_marker_genes)
    n_extra = max(0, n_genes - len(genes))
    genes.extend([f"GENE{i:04d}" for i in range(n_extra)])
    genes = genes[:n_genes]

    samples = [f"sample_{i+1}" for i in range(n_samples)]

    # Generate random true proportions (Dirichlet)
    true_props = rng.dirichlet(np.ones(len(cell_types)) * 2, size=n_samples)
    true_df = pd.DataFrame(true_props, index=samples, columns=cell_types)

    # Build bulk = sum(proportion * cell_type_profile)
    # Cell type profiles: markers get high expression, others low
    profiles = {}
    for ct, ct_genes in markers.items():
        profile = rng.exponential(5, size=n_genes)  # background
        for g in ct_genes:
            g_upper = g.upper()
            if g_upper in genes:
                idx = genes.index(g_upper)
                profile[idx] = rng.exponential(200)  # high expression
        profiles[ct] = profile

    # Mix
    bulk = np.zeros((n_genes, n_samples))
    for j, sample in enumerate(samples):
        for k, ct in enumerate(cell_types):
            bulk[:, j] += true_props[j, k] * profiles[ct]
        # Add noise
        bulk[:, j] += rng.normal(0, 2, size=n_genes)
        bulk[:, j] = np.maximum(bulk[:, j], 0)

    bulk_df = pd.DataFrame(bulk, index=genes, columns=samples)

    return bulk_df, true_df
