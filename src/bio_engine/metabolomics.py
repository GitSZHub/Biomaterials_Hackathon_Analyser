"""
Metabolomics Analysis Engine — differential metabolite analysis, PCA/UMAP,
pathway overlay, and biomaterial-specific metabolic profiling.

Works with tabular metabolomics data (metabolites x samples) from any source:
  - Downloaded via MetabolomicsClient (MetaboLights / Metabolomics Workbench)
  - User-uploaded CSV/TSV files
  - JSON exports from Metabolomics Workbench REST API

Public API:
    from bio_engine.metabolomics import (
        run_differential_analysis,
        run_pca,
        run_umap,
        load_metabolomics_table,
        DifferentialResult,
        MetaboliteHit,
    )

    result = run_differential_analysis(matrix, group_a, group_b, material="GelMA")
    pca    = run_pca(matrix)
    umap   = run_umap(matrix)
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class MetaboliteHit:
    """Single differentially abundant metabolite."""
    name:        str
    log2fc:      float
    p_value:     float
    padj:        float
    mean_a:      float      # mean abundance in group A (control)
    mean_b:      float      # mean abundance in group B (treatment)
    significant: bool
    direction:   str        # "up" | "down" | "ns"
    pathway_flag: str = ""  # biomaterial-relevant pathway if matched


@dataclass
class DifferentialResult:
    """Full result from run_differential_analysis()."""
    material:       str
    baseline:       str
    n_metabolites:  int
    n_samples_a:    int
    n_samples_b:    int
    hits:           List[MetaboliteHit] = field(default_factory=list)
    top_hits:       List[Dict]          = field(default_factory=list)
    up_count:       int = 0
    down_count:     int = 0
    flagged_pathways: List[str] = field(default_factory=list)
    error:          Optional[str] = None


@dataclass
class PCAResult:
    """PCA decomposition result."""
    scores:         np.ndarray          # (n_samples, n_components)
    loadings:       np.ndarray          # (n_metabolites, n_components)
    explained_var:  List[float]         # variance explained per component (%)
    sample_names:   List[str]
    metabolite_names: List[str]
    n_components:   int = 0
    error:          Optional[str] = None


@dataclass
class UMAPResult:
    """UMAP embedding result."""
    embedding:      np.ndarray          # (n_samples, 2)
    sample_names:   List[str]
    error:          Optional[str] = None


# ── Biomaterial-relevant metabolite pathway sets ─────────────────────────────
# For flagging metabolites relevant to material-tissue interaction.

METABOLITE_PATHWAYS: Dict[str, List[str]] = {
    "Glycolysis / Warburg": [
        "glucose", "lactate", "pyruvate", "g6p", "f6p", "fbp",
        "glyceraldehyde", "phosphoenolpyruvate", "2-phosphoglycerate",
    ],
    "TCA Cycle": [
        "citrate", "isocitrate", "alpha-ketoglutarate", "succinate",
        "fumarate", "malate", "oxaloacetate", "acetyl-coa",
    ],
    "Amino Acids": [
        "glutamine", "glutamate", "proline", "hydroxyproline", "glycine",
        "alanine", "serine", "arginine", "ornithine", "citrulline",
        "tryptophan", "kynurenine",
    ],
    "Collagen Biosynthesis": [
        "proline", "hydroxyproline", "glycine", "ascorbate",
        "alpha-ketoglutarate", "lysine", "hydroxylysine",
    ],
    "Oxidative Stress": [
        "glutathione", "gssg", "malondialdehyde", "mda",
        "8-ohdg", "superoxide", "nitric oxide", "peroxynitrite",
        "isoprostane", "4-hne",
    ],
    "Lipid Mediators": [
        "prostaglandin", "pge2", "pgd2", "pgf2", "thromboxane",
        "leukotriene", "ltb4", "ltc4", "resolvin", "lipoxin",
        "arachidonic acid", "epa", "dha",
    ],
    "Purine Metabolism": [
        "adenosine", "atp", "adp", "amp", "inosine", "hypoxanthine",
        "xanthine", "uric acid", "guanosine", "gtp",
    ],
    "Energy Metabolism": [
        "nad+", "nadh", "nadp+", "nadph", "fad", "fadh2",
        "creatine", "phosphocreatine", "atp", "adp",
    ],
    "ECM Degradation Products": [
        "hydroxyproline", "proline", "glucosamine", "galactosamine",
        "hyaluronic acid", "chondroitin sulfate", "keratan sulfate",
    ],
    "Inflammatory Markers": [
        "prostaglandin", "pge2", "leukotriene", "kynurenine",
        "quinolinic acid", "itaconate", "succinate",
    ],
}


# ── Main API ─────────────────────────────────────────────────────────────────

def run_differential_analysis(
    matrix: pd.DataFrame,
    group_a: List[str],
    group_b: List[str],
    material: str = "",
    baseline: str = "",
    fc_threshold: float = 1.0,
    padj_threshold: float = 0.05,
) -> DifferentialResult:
    """
    Run differential abundance analysis between two sample groups.

    Args:
        matrix:        rows = metabolites, columns = sample names
        group_a:       control sample column names
        group_b:       treatment sample column names
        material:      material name (metadata)
        baseline:      baseline condition (metadata)
        fc_threshold:  |log2FC| threshold for significance
        padj_threshold: adjusted p-value threshold

    Returns:
        DifferentialResult with hits, top_hits, and pathway flags.
    """
    result = DifferentialResult(
        material=material,
        baseline=baseline,
        n_metabolites=len(matrix),
        n_samples_a=len(group_a),
        n_samples_b=len(group_b),
    )

    # Validate columns
    missing_a = [c for c in group_a if c not in matrix.columns]
    missing_b = [c for c in group_b if c not in matrix.columns]
    if missing_a or missing_b:
        result.error = f"Missing columns: {missing_a + missing_b}"
        return result

    if len(group_a) < 2 or len(group_b) < 2:
        result.error = "Need at least 2 samples per group."
        return result

    try:
        data_a = matrix[group_a].values.astype(float)
        data_b = matrix[group_b].values.astype(float)
        metabolites = matrix.index.tolist()

        mean_a = data_a.mean(axis=1)
        mean_b = data_b.mean(axis=1)

        # Log2 fold change (pseudocount to avoid log(0))
        log2fc = np.log2(mean_b + 1) - np.log2(mean_a + 1)

        # Welch t-test
        _, pvalues = stats.ttest_ind(data_b.T, data_a.T, equal_var=False)
        pvalues = np.nan_to_num(pvalues, nan=1.0)

        # BH FDR
        padj = _bh_correction(pvalues)

        hits = []
        for i, name in enumerate(metabolites):
            fc = float(log2fc[i])
            pa = float(padj[i])
            sig = (pa < padj_threshold) and (abs(fc) >= fc_threshold)
            direction = ("up" if fc > 0 else "down") if sig else "ns"

            hit = MetaboliteHit(
                name=str(name),
                log2fc=round(fc, 4),
                p_value=round(float(pvalues[i]), 6),
                padj=round(pa, 6),
                mean_a=round(float(mean_a[i]), 4),
                mean_b=round(float(mean_b[i]), 4),
                significant=sig,
                direction=direction,
                pathway_flag=_match_metabolite_pathway(str(name)),
            )
            hits.append(hit)

        result.hits = hits
        result.up_count = sum(1 for h in hits if h.direction == "up")
        result.down_count = sum(1 for h in hits if h.direction == "down")

        # Top hits by significance
        sig_hits = [h for h in hits if h.significant]
        sig_hits.sort(key=lambda h: (h.padj, -abs(h.log2fc)))
        result.top_hits = [
            {
                "name": h.name, "log2fc": h.log2fc, "padj": h.padj,
                "direction": h.direction, "pathway": h.pathway_flag,
            }
            for h in sig_hits[:50]
        ]

        # Flag pathways
        result.flagged_pathways = _flag_metabolite_pathways(sig_hits)

    except Exception as e:
        logger.exception("Metabolomics differential analysis failed")
        result.error = str(e)

    return result


def run_pca(matrix: pd.DataFrame, n_components: int = 5,
            scale: bool = True) -> PCAResult:
    """
    Run PCA on a metabolite abundance matrix.
    Rows = metabolites, columns = samples. Transposed internally.
    """
    try:
        # Transpose: PCA on samples (observations = samples, features = metabolites)
        X = matrix.T.values.astype(float)

        # Handle NaN
        col_means = np.nanmean(X, axis=0)
        nan_mask = np.isnan(X)
        X[nan_mask] = np.take(col_means, np.where(nan_mask)[1])

        # Center and optionally scale
        X_mean = X.mean(axis=0)
        X_centered = X - X_mean
        if scale:
            X_std = X.std(axis=0)
            X_std[X_std == 0] = 1.0
            X_centered = X_centered / X_std

        # SVD
        n_comp = min(n_components, X_centered.shape[0], X_centered.shape[1])
        U, S, Vt = np.linalg.svd(X_centered, full_matrices=False)

        # Scores and loadings
        scores = U[:, :n_comp] * S[:n_comp]
        loadings = Vt[:n_comp, :].T

        # Variance explained
        total_var = np.sum(S ** 2)
        explained = [(s ** 2 / total_var) * 100 for s in S[:n_comp]]

        return PCAResult(
            scores=scores,
            loadings=loadings,
            explained_var=[round(e, 2) for e in explained],
            sample_names=list(matrix.columns),
            metabolite_names=list(matrix.index),
            n_components=n_comp,
        )
    except Exception as e:
        return PCAResult(
            scores=np.array([]),
            loadings=np.array([]),
            explained_var=[],
            sample_names=[],
            metabolite_names=[],
            error=str(e),
        )


def run_umap(matrix: pd.DataFrame, n_neighbors: int = 15,
             min_dist: float = 0.1) -> UMAPResult:
    """
    Run UMAP on a metabolite abundance matrix (samples in 2D).

    Requires the `umap-learn` package. Falls back to PCA if unavailable.
    """
    try:
        import umap
        X = matrix.T.values.astype(float)

        # Handle NaN
        col_means = np.nanmean(X, axis=0)
        nan_mask = np.isnan(X)
        X[nan_mask] = np.take(col_means, np.where(nan_mask)[1])

        reducer = umap.UMAP(n_neighbors=min(n_neighbors, X.shape[0] - 1),
                            min_dist=min_dist, n_components=2, random_state=42)
        embedding = reducer.fit_transform(X)

        return UMAPResult(
            embedding=embedding,
            sample_names=list(matrix.columns),
        )
    except ImportError:
        logger.warning("umap-learn not installed, falling back to PCA(2)")
        pca = run_pca(matrix, n_components=2)
        if pca.error:
            return UMAPResult(embedding=np.array([]), sample_names=[], error=pca.error)
        return UMAPResult(
            embedding=pca.scores,
            sample_names=pca.sample_names,
        )
    except Exception as e:
        return UMAPResult(embedding=np.array([]), sample_names=[], error=str(e))


# ── Data loading ─────────────────────────────────────────────────────────────

def load_metabolomics_table(file_path: str,
                            metabolite_col: str = "",
                            transpose: bool = False) -> Optional[pd.DataFrame]:
    """
    Load a metabolomics data table from CSV, TSV, or JSON.

    Expects rows = metabolites, columns = samples (or transpose=True).
    Auto-detects format from extension.

    Returns DataFrame with metabolites as index and samples as columns,
    or None on failure.
    """
    path = Path(file_path)
    try:
        if path.suffix.lower() == ".json":
            return _load_from_json(path)
        elif path.suffix.lower() in (".tsv", ".tab"):
            df = pd.read_csv(path, sep="\t", index_col=0)
        elif path.suffix.lower() == ".csv":
            df = pd.read_csv(path, index_col=0)
        elif path.suffix.lower() in (".xlsx", ".xls"):
            df = pd.read_excel(path, index_col=0)
        else:
            # Try tab-separated first, then comma
            try:
                df = pd.read_csv(path, sep="\t", index_col=0)
            except Exception:
                df = pd.read_csv(path, index_col=0)

        if metabolite_col and metabolite_col in df.columns:
            df = df.set_index(metabolite_col)

        if transpose:
            df = df.T

        # Keep only numeric columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) < df.shape[1]:
            logger.info(f"Dropped {df.shape[1] - len(numeric_cols)} non-numeric columns")
        df = df[numeric_cols]

        if df.empty:
            logger.warning(f"No numeric data in {file_path}")
            return None

        df.index.name = "metabolite"
        return df

    except Exception as e:
        logger.error(f"Failed to load metabolomics file {file_path}: {e}")
        return None


def _load_from_json(path: Path) -> Optional[pd.DataFrame]:
    """Load metabolomics data from Metabolomics Workbench JSON export."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    if isinstance(data, list):
        # List of metabolite records
        df = pd.DataFrame(data)
        if "metabolite_name" in df.columns:
            df = df.set_index("metabolite_name")
        # Keep only numeric columns
        numeric = df.select_dtypes(include=[np.number])
        return numeric if not numeric.empty else None

    elif isinstance(data, dict):
        # Nested dict: metabolite_name -> {sample: value, ...}
        # or numbered keys from MW REST
        records = list(data.values()) if not any(
            isinstance(v, (int, float)) for v in data.values()
        ) else [data]

        if records and isinstance(records[0], dict):
            df = pd.DataFrame(records)
            # Try to find a name column
            for col in ["metabolite_name", "metabolite", "name", "Metabolite"]:
                if col in df.columns:
                    df = df.set_index(col)
                    break
            numeric = df.select_dtypes(include=[np.number])
            return numeric if not numeric.empty else None

    return None


def make_demo_metabolomics(n_metabolites: int = 100, n_samples: int = 8,
                           seed: int = 42) -> Tuple[pd.DataFrame, List[str], List[str]]:
    """
    Generate a demo metabolomics matrix for UI testing.

    Returns (matrix, group_a_cols, group_b_cols).
    """
    rng = np.random.default_rng(seed)
    metabolites = [f"MET_{i:04d}" for i in range(n_metabolites)]

    # Inject known pathway metabolites
    known = [
        "glucose", "lactate", "pyruvate", "glutamine", "glutamate",
        "proline", "hydroxyproline", "succinate", "citrate", "fumarate",
        "glutathione", "pge2", "arachidonic_acid", "adenosine", "nad+",
    ]
    metabolites[:len(known)] = known

    cols_a = [f"ctrl_{i+1}" for i in range(n_samples // 2)]
    cols_b = [f"treat_{i+1}" for i in range(n_samples // 2)]

    base = rng.exponential(scale=50, size=(n_metabolites, n_samples // 2))
    treat = base * rng.lognormal(mean=0, sigma=0.3, size=(n_metabolites, n_samples // 2))

    # Make ~15% truly differential
    de_idx = rng.choice(n_metabolites, size=n_metabolites // 7, replace=False)
    treat[de_idx] *= rng.uniform(2, 8, size=(len(de_idx), n_samples // 2))

    df = pd.DataFrame(
        np.hstack([base, treat]),
        index=metabolites,
        columns=cols_a + cols_b,
    )
    df.index.name = "metabolite"
    return df, cols_a, cols_b


# ── Internal helpers ─────────────────────────────────────────────────────────

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


def _match_metabolite_pathway(name: str) -> str:
    """Match a metabolite name to a biomaterial-relevant pathway."""
    name_lower = name.lower().strip()
    for pathway, metabolites in METABOLITE_PATHWAYS.items():
        for m in metabolites:
            if m in name_lower or name_lower in m:
                return pathway
    return ""


def _flag_metabolite_pathways(sig_hits: List[MetaboliteHit]) -> List[str]:
    """Flag pathways with 2+ significant metabolites."""
    pathway_counts: Dict[str, int] = {}
    for h in sig_hits:
        if h.pathway_flag:
            pathway_counts[h.pathway_flag] = pathway_counts.get(h.pathway_flag, 0) + 1

    return [f"{pw} ({n} metabolites)" for pw, n in sorted(
        pathway_counts.items(), key=lambda x: x[1], reverse=True
    ) if n >= 2]
