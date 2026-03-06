"""
Transcriptomics Analysis Engine — bulk RNA-seq DEG analysis.

Takes a gene expression matrix (genes x samples as pandas DataFrame)
and returns differentially expressed genes with statistics suitable
for volcano plots and heatmaps.

No external bioinformatics packages required beyond scipy + pandas + numpy,
which are in requirements.txt.

Public API:
    from bio_engine.transcriptomics import run_deg_analysis, VolcanoData

    result = run_deg_analysis(
        matrix     = df,           # DataFrame: rows=genes, cols=samples
        group_a    = ["s1","s2"],  # control sample column names
        group_b    = ["s3","s4"],  # treatment sample column names
        material   = "GelMA",
        baseline   = "Matrigel",
    )
    result.volcano_points   # list of VolcanoPoint for plotting
    result.top_degs         # top 20 DEGs sorted by significance
    result.pathway_summary  # placeholder for future KEGG enrichment

Matrigel caveat: always injected into result when baseline == "Matrigel".
"""

from __future__ import annotations

import gzip
import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class VolcanoPoint:
    gene:        str
    log2fc:      float           # positive = up in group_b
    neg_log10p:  float           # -log10(adjusted p-value)
    padj:        float           # BH-adjusted p-value
    significant: bool            # padj < 0.05 AND |log2fc| >= 1.0
    direction:   str             # "up" | "down" | "ns"


@dataclass
class DEGResult:
    """Full result from run_deg_analysis()."""
    material:        str
    baseline:        str
    n_genes:         int
    n_samples_a:     int
    n_samples_b:     int
    volcano_points:  List[VolcanoPoint] = field(default_factory=list)
    top_degs:        List[Dict]         = field(default_factory=list)
    up_count:        int = 0
    down_count:      int = 0
    matrigel_caveat: bool = False
    matrigel_genes:  List[str] = field(default_factory=list)  # known Matrigel-response genes present
    pathway_summary: str = ""   # placeholder — KEGG enrichment post-hackathon
    error:           Optional[str] = None

    # Key biomaterial-relevant pathways flagged in top DEGs
    flagged_pathways: List[str] = field(default_factory=list)


# ── Known Matrigel-response genes (hypoxia + ECM artefacts) ──────────────────
# These genes are upregulated by Matrigel culture conditions, not material response.
# App flags them separately so the user knows which signals are artefacts.

MATRIGEL_ARTEFACT_GENES = {
    # Hypoxia / HIF-1alpha pathway (necrotic core artefact)
    "HIF1A", "VEGFA", "VEGFB", "VEGFC", "LDHA", "LDHA", "SLC2A1", "GLUT1",
    "PGAM1", "ENO1", "PKM", "ALDOA", "PGK1", "TPI1",
    # Matrigel ECM components (mouse-derived)
    "LAMA1", "LAMB1", "LAMC1", "COL4A1", "COL4A2", "NID1", "HSPG2",
    # Batch-variable signals
    "EGF", "FGF7", "IGF1",
}

# Key biomaterial-relevant pathway gene sets (simplified, curated)
PATHWAY_GENES: Dict[str, List[str]] = {
    "Inflammation (NFkB)":  ["NFKB1", "NFKB2", "RELA", "RELB", "IL6", "TNF", "CXCL8", "IL1B"],
    "JAK-STAT (IL-6)":      ["STAT3", "STAT1", "JAK1", "JAK2", "IL6ST", "SOCS1", "SOCS3"],
    "TGF-beta / Fibrosis":  ["TGFB1", "TGFB2", "SMAD2", "SMAD3", "SMAD4", "COL1A1", "COL3A1", "FN1"],
    "YAP/TAZ (Mechano)":    ["YAP1", "WWTR1", "CYR61", "CTGF", "AMOTL2", "LATS1", "LATS2"],
    "Integrin signalling":  ["ITGB1", "ITGB3", "ITGA5", "ITGA6", "FAK1", "PTK2", "SRC", "PXN"],
    "Wnt signalling":       ["WNT3A", "WNT5A", "CTNNB1", "APC", "GSK3B", "AXIN1", "FZD1"],
    "Apoptosis":            ["TP53", "BCL2", "BCL2L1", "BAX", "CASP3", "CASP9", "PARP1"],
    "PI3K/AKT":             ["PIK3CA", "AKT1", "AKT2", "PTEN", "MTOR", "RPS6KB1"],
    "Cell cycle":           ["CCND1", "CDK4", "CDK6", "CDKN1A", "CDKN2A", "RB1", "E2F1"],
    "HIF-1 / Hypoxia":      ["HIF1A", "VEGFA", "LDHA", "SLC2A1", "ENO1", "PDK1"],
}


# ── Main function ─────────────────────────────────────────────────────────────

def run_deg_analysis(matrix: pd.DataFrame,
                     group_a: List[str],
                     group_b: List[str],
                     material: str = "",
                     baseline: str = "",
                     fc_threshold: float = 1.0,
                     padj_threshold: float = 0.05) -> DEGResult:
    """
    Run differential expression analysis between two groups of samples.

    Args:
        matrix:        rows = genes, columns = sample names, values = normalised counts
        group_a:       column names for the baseline/control group
        group_b:       column names for the treatment group
        material:      name of the test material (for metadata)
        baseline:      name of the baseline (flags Matrigel caveat if "Matrigel")
        fc_threshold:  |log2 fold change| threshold for significance
        padj_threshold: adjusted p-value threshold for significance

    Returns:
        DEGResult with volcano_points, top_degs, and pathway flags.
    """
    result = DEGResult(
        material    = material,
        baseline    = baseline,
        n_genes     = len(matrix),
        n_samples_a = len(group_a),
        n_samples_b = len(group_b),
        matrigel_caveat = baseline.lower() == "matrigel",
    )

    # Validate columns
    missing_a = [c for c in group_a if c not in matrix.columns]
    missing_b = [c for c in group_b if c not in matrix.columns]
    if missing_a or missing_b:
        result.error = f"Missing columns: {missing_a + missing_b}"
        return result

    if len(group_a) < 2 or len(group_b) < 2:
        result.error = "Need at least 2 samples per group for statistical test."
        return result

    try:
        volcano_points, top_degs = _compute_degs(
            matrix, group_a, group_b, fc_threshold, padj_threshold
        )
        result.volcano_points = volcano_points
        result.top_degs       = top_degs
        result.up_count   = sum(1 for v in volcano_points if v.direction == "up")
        result.down_count = sum(1 for v in volcano_points if v.direction == "down")

        # Flag Matrigel artefact genes in significant DEGs
        if result.matrigel_caveat:
            sig_genes = {v.gene for v in volcano_points if v.significant}
            result.matrigel_genes = sorted(sig_genes & MATRIGEL_ARTEFACT_GENES)

        # Flag biomaterial-relevant pathways
        result.flagged_pathways = _flag_pathways(volcano_points, fc_threshold, padj_threshold)

        result.pathway_summary = (
            f"{result.up_count} genes up, {result.down_count} genes down "
            f"(|log2FC| ≥ {fc_threshold}, padj < {padj_threshold}). "
            f"Flagged pathways: {', '.join(result.flagged_pathways) or 'none detected'}."
        )

    except Exception as e:
        logger.exception("DEG analysis failed")
        result.error = str(e)

    return result


def _compute_degs(matrix: pd.DataFrame,
                  group_a: List[str],
                  group_b: List[str],
                  fc_threshold: float,
                  padj_threshold: float) -> Tuple[List[VolcanoPoint], List[Dict]]:
    """Core statistics: Welch t-test + BH FDR correction."""
    data_a = matrix[group_a].values.astype(float)
    data_b = matrix[group_b].values.astype(float)
    genes  = matrix.index.tolist()

    # Per-gene means
    mean_a = data_a.mean(axis=1)
    mean_b = data_b.mean(axis=1)

    # Log2 fold change (add 1 pseudocount to avoid log(0))
    log2fc = np.log2(mean_b + 1) - np.log2(mean_a + 1)

    # Welch t-test (unequal variance)
    _, pvalues = stats.ttest_ind(data_b.T, data_a.T, equal_var=False)
    pvalues = np.nan_to_num(pvalues, nan=1.0)

    # BH FDR correction
    padj = _bh_correction(pvalues)

    # Assemble results
    points = []
    for i, gene in enumerate(genes):
        fc   = float(log2fc[i])
        p    = float(pvalues[i])
        pa   = float(padj[i])
        nlp  = -math.log10(pa + 1e-300)   # avoid log(0)
        sig  = (pa < padj_threshold) and (abs(fc) >= fc_threshold)
        if sig:
            direction = "up" if fc > 0 else "down"
        else:
            direction = "ns"

        points.append(VolcanoPoint(
            gene       = str(gene),
            log2fc     = round(fc, 4),
            neg_log10p = round(nlp, 4),
            padj       = round(pa, 6),
            significant= sig,
            direction  = direction,
        ))

    # Top DEGs sorted by adjusted p-value, then fold change
    sig_points = [p for p in points if p.significant]
    sig_points.sort(key=lambda p: (p.padj, -abs(p.log2fc)))

    top_degs = [
        {
            "gene":      p.gene,
            "log2fc":    p.log2fc,
            "padj":      p.padj,
            "direction": p.direction,
        }
        for p in sig_points[:50]
    ]

    return points, top_degs


def _bh_correction(pvalues: np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg FDR correction."""
    n   = len(pvalues)
    idx = np.argsort(pvalues)
    padj = np.ones(n)
    cummin = 1.0
    for rank, i in enumerate(reversed(idx)):
        raw_adj = pvalues[i] * n / (n - rank)
        cummin  = min(cummin, raw_adj)
        padj[i] = cummin
    return np.clip(padj, 0, 1)


def _flag_pathways(points: List[VolcanoPoint],
                   fc_threshold: float,
                   padj_threshold: float) -> List[str]:
    """Check whether significant DEGs overlap with known biomaterial pathways."""
    sig_genes = {p.gene.upper() for p in points if p.significant}
    flagged = []
    for pathway, genes in PATHWAY_GENES.items():
        hit = sig_genes & {g.upper() for g in genes}
        if len(hit) >= 2:   # require at least 2 hits to call a pathway
            flagged.append(f"{pathway} ({len(hit)} genes)")
    return flagged


# ── Convenience: load a Series Matrix file ────────────────────────────────────

def load_series_matrix(file_path: str) -> Optional[pd.DataFrame]:
    """
    Parse a GEO Series Matrix file into a gene-expression DataFrame.
    Rows = probe/gene IDs, columns = GSM sample IDs.
    Returns None on failure.

    Series Matrix format: tab-separated, header lines start with '!',
    data starts at '!series_matrix_table_begin'.
    """
    try:
        lines = []
        in_table = False
        open_fn = gzip.open if file_path.endswith(".gz") else open
        with open_fn(file_path, "rt", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith("!series_matrix_table_begin"):
                    in_table = True
                    continue
                if line.startswith("!series_matrix_table_end"):
                    break
                if in_table:
                    lines.append(line)

        if not lines:
            logger.warning(f"No data table found in {file_path}")
            return None

        from io import StringIO
        df = pd.read_csv(StringIO("".join(lines)), sep="\t", index_col=0)
        df.index.name = "gene"
        return df

    except Exception as e:
        logger.error(f"Failed to load series matrix {file_path}: {e}")
        return None


def make_demo_matrix(n_genes: int = 500, n_samples: int = 6,
                     seed: int = 42) -> Tuple[pd.DataFrame, List[str], List[str]]:
    """
    Generate a small random expression matrix for UI demo / testing.
    Returns (matrix, group_a_cols, group_b_cols).
    """
    rng = np.random.default_rng(seed)
    genes   = [f"GENE{i:04d}" for i in range(n_genes)]

    # Inject a few known pathway genes so flagging demo works
    known = list(MATRIGEL_ARTEFACT_GENES)[:10] + ["NFKB1", "IL6", "TGFB1", "YAP1", "ITGB1"]
    genes[:len(known)] = known

    cols_a = [f"ctrl_{i+1}" for i in range(n_samples // 2)]
    cols_b = [f"treat_{i+1}" for i in range(n_samples // 2)]

    base   = rng.exponential(scale=100, size=(n_genes, n_samples // 2))
    treat  = base * rng.lognormal(mean=0, sigma=0.5, size=(n_genes, n_samples // 2))

    # Make ~10% of genes truly DE
    de_idx = rng.choice(n_genes, size=n_genes // 10, replace=False)
    treat[de_idx] *= rng.uniform(3, 10, size=(len(de_idx), n_samples // 2))

    df = pd.DataFrame(
        np.hstack([base, treat]),
        index   = genes,
        columns = cols_a + cols_b,
    )
    return df, cols_a, cols_b
