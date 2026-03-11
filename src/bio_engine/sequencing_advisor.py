"""
Sequencing Technology Advisor
=============================
Recommends appropriate sequencing / omics platform based on
research question, budget, and sample constraints.

Covers: 10x Chromium (scRNA-seq), ONT direct RNA, PacBio Iso-Seq,
Spatial Transcriptomics (Visium/Xenium), ATAC-seq / Multiome,
Bulk RNA-seq, and metabolomics platforms.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional


# ── Data classes ──────────────────────────────────────────────

@dataclass
class SequencingTechnology:
    """A sequencing / omics platform."""
    name: str
    platform: str          # e.g. "Illumina", "Oxford Nanopore", "10x Genomics"
    best_for: List[str]
    limitations: List[str]
    biomaterials_angle: str
    cost_per_sample: str   # e.g. "$200-500", "$2000-5000"
    turnaround: str        # e.g. "2-4 weeks"
    accessibility: str     # "Most core facilities", "Specialist centres"
    data_format: str       # e.g. "FASTQ", "BAM", "H5AD"
    public_repos: List[str]
    categories: List[str]  # keyword tags for matching


@dataclass
class TechRecommendation:
    """A single technology recommendation with rationale."""
    technology: SequencingTechnology
    relevance_score: float   # 0-1
    rationale: str
    tier: int               # 1=first-line, 2=complementary, 3=advanced/niche


@dataclass
class TechAdvisorReport:
    """Full advisor output."""
    question: str
    recommendations: List[TechRecommendation]
    decision_summary: str
    suggested_order: List[str]   # names in recommended execution order


# ── Technology database ──────────────────────────────────────

TECHNOLOGY_DATABASE: Dict[str, SequencingTechnology] = {
    "bulk_rnaseq": SequencingTechnology(
        name="Bulk RNA-seq",
        platform="Illumina (NovaSeq / NextSeq)",
        best_for=[
            "Differential gene expression between conditions",
            "Pathway-level transcriptomic changes",
            "Large sample sizes (n>20) at reasonable cost",
        ],
        limitations=[
            "Averages across cell types -- masks heterogeneity",
            "Cannot identify rare cell populations",
            "3' counting loses isoform information",
        ],
        biomaterials_angle=(
            "First-line for detecting material-induced transcriptomic shifts. "
            "Best when cell population is homogeneous (monoculture on scaffold)."
        ),
        cost_per_sample="$150-400",
        turnaround="1-3 weeks",
        accessibility="Most genomics core facilities",
        data_format="FASTQ -> count matrix",
        public_repos=["GEO (NCBI)", "ArrayExpress (EMBL-EBI)"],
        categories=[
            "gene_expression", "deg", "pathway", "transcriptomics",
            "bulk", "rna", "cheap", "first_line",
        ],
    ),
    "scrnaseq_10x": SequencingTechnology(
        name="10x Chromium scRNA-seq",
        platform="10x Genomics + Illumina",
        best_for=[
            "Cell type composition in mixed cultures / tissue",
            "Cell state shifts per population",
            "Trajectory / pseudotime analysis",
            "Differential abundance between conditions",
        ],
        limitations=[
            "3' counting -- misses isoforms",
            "Dropout noise for lowly expressed genes",
            "Requires fresh viable single-cell suspension",
            "Cost scales with number of samples",
        ],
        biomaterials_angle=(
            "Gold standard for understanding how a biomaterial changes "
            "cell type proportions and per-cell-type gene expression. "
            "Most CELLxGENE data is this format."
        ),
        cost_per_sample="$2000-5000",
        turnaround="3-6 weeks",
        accessibility="Major genomics centres",
        data_format="H5AD / Seurat object",
        public_repos=["CELLxGENE (CZI)", "GEO", "Single Cell Portal (Broad)"],
        categories=[
            "single_cell", "cell_type", "composition", "trajectory",
            "heterogeneity", "identity", "differentiation", "scrnaseq",
        ],
    ),
    "ont_direct_rna": SequencingTechnology(
        name="ONT Direct RNA Sequencing",
        platform="Oxford Nanopore (MinION / PromethION)",
        best_for=[
            "Full-length transcript isoform discovery",
            "Alternative splicing detection",
            "RNA base modifications (m6A, pseudouridine)",
            "No PCR amplification bias",
        ],
        limitations=[
            "Lower per-read accuracy than Illumina (~95-99%)",
            "Lower throughput per run",
            "Requires high-quality, high-input RNA",
        ],
        biomaterials_angle=(
            "Detects whether material contact induces alternative splicing "
            "in stress response genes -- information completely invisible "
            "to short-read 3' counting. MinION is USB-sized, relatively accessible."
        ),
        cost_per_sample="$500-1500",
        turnaround="1-2 weeks",
        accessibility="Growing -- MinION available in many labs",
        data_format="FASTQ (long reads) / BAM",
        public_repos=["GEO", "ENA"],
        categories=[
            "isoform", "splicing", "long_read", "rna_modification",
            "m6a", "nanopore", "full_length",
        ],
    ),
    "pacbio_isoseq": SequencingTechnology(
        name="PacBio Iso-Seq (HiFi)",
        platform="PacBio Sequel IIe / Revio",
        best_for=[
            "Definitive full-length isoform atlas",
            "High-accuracy long reads (>99.9% HiFi)",
            "Fusion transcript detection",
        ],
        limitations=[
            "Most expensive per-sample",
            "Large instrument footprint",
            "Likely overkill for most biomaterials questions",
        ],
        biomaterials_angle=(
            "Use when ONT identifies candidate isoform switches and you need "
            "high-confidence validation. Rarely first-line for biomaterials."
        ),
        cost_per_sample="$3000-8000",
        turnaround="4-8 weeks",
        accessibility="Specialist sequencing centres",
        data_format="BAM (HiFi reads)",
        public_repos=["GEO", "SRA"],
        categories=[
            "isoform", "long_read", "high_accuracy", "validation",
            "pacbio", "full_length",
        ],
    ),
    "spatial_visium": SequencingTechnology(
        name="10x Visium Spatial Transcriptomics",
        platform="10x Genomics Visium + Illumina",
        best_for=[
            "Gene expression mapped to spatial position in tissue section",
            "Interface biology -- scaffold edge vs bulk tissue",
            "Spatial gradients of gene expression",
        ],
        limitations=[
            "55um spot size -- not single-cell resolution",
            "Requires cryosectioned tissue (10um)",
            "Limited to ~5000 spots per capture area",
        ],
        biomaterials_angle=(
            "Most directly relevant spatial technology for biomaterials. "
            "Shows which genes are expressed at the scaffold-tissue interface "
            "vs 500um away. Reveals spatial gradients of inflammation, "
            "angiogenesis, and ECM remodelling."
        ),
        cost_per_sample="$3000-6000",
        turnaround="4-8 weeks",
        accessibility="Major genomics centres with spatial capability",
        data_format="SpaceRanger output / H5AD with spatial coords",
        public_repos=["GEO", "10x Datasets"],
        categories=[
            "spatial", "tissue_section", "interface", "gradient",
            "location", "where", "position", "visium",
        ],
    ),
    "spatial_xenium": SequencingTechnology(
        name="10x Xenium / Nanostring CosMx",
        platform="10x Xenium or Nanostring CosMx",
        best_for=[
            "In situ single-cell resolution spatial transcriptomics",
            "Targeted panel (100-1000 genes)",
            "Subcellular transcript localisation",
        ],
        limitations=[
            "Targeted -- must pre-select gene panel",
            "Very high instrument cost",
            "Limited public datasets so far",
        ],
        biomaterials_angle=(
            "Single-cell resolution at the material-tissue interface. "
            "Can resolve individual immune cells infiltrating a scaffold "
            "and their gene expression in situ."
        ),
        cost_per_sample="$5000-10000",
        turnaround="2-4 weeks (once on instrument)",
        accessibility="Specialist spatial genomics centres",
        data_format="Cell-by-gene matrix with XY coordinates",
        public_repos=["GEO (emerging)", "10x Datasets"],
        categories=[
            "spatial", "in_situ", "single_cell", "targeted",
            "subcellular", "xenium", "cosmx",
        ],
    ),
    "atacseq": SequencingTechnology(
        name="ATAC-seq / Multiome (RNA + ATAC)",
        platform="10x Multiome or standalone ATAC-seq + Illumina",
        best_for=[
            "Chromatin accessibility profiling",
            "Transcription factor activity inference",
            "Epigenetic state changes",
            "Joint RNA + chromatin from same cell (Multiome)",
        ],
        limitations=[
            "Requires high-quality nuclei isolation",
            "Computationally intensive analysis",
            "Interpretation requires TF motif expertise",
        ],
        biomaterials_angle=(
            "Relevant when material is suspected to alter epigenetic state -- "
            "e.g. substrate stiffness driving YAP/TAZ nuclear translocation, "
            "or material-induced inflammatory epigenetic priming."
        ),
        cost_per_sample="$3000-7000 (Multiome)",
        turnaround="4-8 weeks",
        accessibility="Specialist epigenomics centres",
        data_format="Fragment file / peak matrix",
        public_repos=["GEO", "ENCODE"],
        categories=[
            "epigenetic", "chromatin", "atac", "transcription_factor",
            "accessibility", "multiome", "epigenome",
        ],
    ),
    "metabolomics_lcms": SequencingTechnology(
        name="LC-MS/MS Untargeted Metabolomics",
        platform="Thermo Orbitrap / Bruker timsTOF",
        best_for=[
            "Full metabolome profiling (lipids + polar metabolites)",
            "Drug release quantification",
            "Inflammatory mediator detection (prostaglandins, leukotrienes)",
            "Degradation product identification",
        ],
        limitations=[
            "Requires both RP-LC and HILIC for full coverage",
            "Compound identification challenging without standards",
            "Data processing requires specialist software",
        ],
        biomaterials_angle=(
            "Full metabolic rewiring after material contact. "
            "Identifies degradation products, drug metabolites, "
            "and inflammatory lipid mediators in conditioned media."
        ),
        cost_per_sample="$200-600",
        turnaround="2-4 weeks",
        accessibility="Most analytical chemistry core facilities",
        data_format="mzML / feature table",
        public_repos=["MetaboLights (EMBL-EBI)", "Metabolomics Workbench (NIH)"],
        categories=[
            "metabolomics", "metabolite", "lipid", "drug_release",
            "degradation", "lcms", "untargeted",
        ],
    ),
    "metabolomics_gcms": SequencingTechnology(
        name="GC-MS Metabolomics",
        platform="Agilent / Shimadzu GC-MS",
        best_for=[
            "Volatile / semi-volatile metabolites",
            "Fatty acids (FAMEs), amino acids (derivatised)",
            "TCA cycle intermediates",
            "Well-established spectral libraries (NIST, Golm)",
        ],
        limitations=[
            "Requires derivatisation for many metabolites",
            "Misses large / non-volatile compounds",
            "Lower coverage than LC-MS",
        ],
        biomaterials_angle=(
            "Scaffold degradation products, membrane fatty acid changes. "
            "Accessible at most analytical chemistry core facilities."
        ),
        cost_per_sample="$100-300",
        turnaround="1-3 weeks",
        accessibility="Most analytical chemistry labs",
        data_format="mzML / peak table",
        public_repos=["Golm Metabolome Database", "MetaboLights"],
        categories=[
            "metabolomics", "volatile", "fatty_acid", "tca",
            "degradation", "gcms", "cheap",
        ],
    ),
    "nmr_metabolomics": SequencingTechnology(
        name="NMR Metabolomics",
        platform="Bruker NMR (400-800 MHz)",
        best_for=[
            "Quantitative metabolite measurement",
            "Non-destructive -- sample can be re-used",
            "Abundant metabolites (lactate, glucose, glutamine, acetate)",
            "No chromatography needed",
        ],
        limitations=[
            "Low sensitivity -- misses rare metabolites",
            "Spectral overlap in complex mixtures",
            "Requires concentrated samples",
        ],
        biomaterials_angle=(
            "Quick quantitative screen of conditioned media metabolites. "
            "Accessible at most university NMR facilities."
        ),
        cost_per_sample="$50-150",
        turnaround="1-2 weeks",
        accessibility="Most university chemistry departments",
        data_format="NMR spectra / quantified concentrations",
        public_repos=["BMRB", "MetaboLights"],
        categories=[
            "metabolomics", "quantitative", "nmr", "non_destructive",
            "cheap", "first_line", "conditioned_media",
        ],
    ),
}


# ── Question pattern matching ────────────────────────────────

_QUESTION_PATTERNS: Dict[str, List[str]] = {
    "gene_expression": [
        r"which genes", r"gene expression", r"transcriptom",
        r"deg\b", r"differentially expressed", r"pathway",
        r"what.*(genes|transcripts).*chang",
    ],
    "cell_type": [
        r"cell type", r"cell composition", r"cell identity",
        r"heterogen", r"which cells", r"cell state",
        r"differentiat", r"cell population",
    ],
    "spatial": [
        r"where.*tissue", r"spatial", r"interface",
        r"gradient", r"location", r"position",
        r"scaffold.*edge", r"tissue.*section",
    ],
    "isoform": [
        r"isoform", r"splicing", r"alternative splic",
        r"full.length", r"rna modif", r"m6a",
    ],
    "epigenetic": [
        r"epigenet", r"chromatin", r"transcription factor",
        r"atac", r"accessibility", r"histone",
        r"methylat", r"acetylat",
    ],
    "metabolomics": [
        r"metabol", r"metabolit", r"lipid",
        r"fatty acid", r"drug release", r"degradation product",
        r"conditioned media", r"warburg",
    ],
    "cytotoxicity": [
        r"cytotox", r"toxic", r"viab", r"live.*dead",
        r"cell death", r"apoptos",
    ],
    "mechanistic": [
        r"full.*picture", r"mechanis", r"comprehensive",
        r"multi.*omic", r"integrat",
    ],
    "cheap_screen": [
        r"first.*pass", r"quick", r"cheap", r"screen",
        r"preliminary", r"budget",
    ],
}

# Map categories to technology keys
_CATEGORY_TECH_MAP: Dict[str, List[str]] = {
    "gene_expression": ["bulk_rnaseq", "scrnaseq_10x"],
    "cell_type": ["scrnaseq_10x", "spatial_visium"],
    "spatial": ["spatial_visium", "spatial_xenium"],
    "isoform": ["ont_direct_rna", "pacbio_isoseq"],
    "epigenetic": ["atacseq"],
    "metabolomics": [
        "metabolomics_lcms", "metabolomics_gcms", "nmr_metabolomics",
    ],
    "cytotoxicity": ["bulk_rnaseq", "metabolomics_lcms"],
    "mechanistic": [
        "scrnaseq_10x", "spatial_visium", "metabolomics_lcms",
        "atacseq",
    ],
    "cheap_screen": ["bulk_rnaseq", "nmr_metabolomics", "metabolomics_gcms"],
}


# ── Public API ───────────────────────────────────────────────

def recommend_technology(
    question: str,
    sample_type: str = "",
    budget: str = "standard",      # "low", "standard", "high"
    has_tissue_section: bool = False,
) -> TechAdvisorReport:
    """Recommend sequencing / omics technologies for a research question.

    Parameters
    ----------
    question : str
        Free-text research question.
    sample_type : str
        Optional sample description (e.g. "monoculture", "tissue biopsy").
    budget : str
        "low", "standard", or "high".
    has_tissue_section : bool
        Whether cryosectioned tissue is available (enables spatial).

    Returns
    -------
    TechAdvisorReport
    """
    q_lower = question.lower()

    # Identify matching categories
    matched_categories: Dict[str, int] = {}
    for cat, patterns in _QUESTION_PATTERNS.items():
        hits = sum(1 for p in patterns if re.search(p, q_lower))
        if hits > 0:
            matched_categories[cat] = hits

    # If nothing matched, default to gene_expression
    if not matched_categories:
        matched_categories["gene_expression"] = 1

    # Collect relevant technologies with scores
    tech_scores: Dict[str, float] = {}
    for cat, hit_count in matched_categories.items():
        for tech_key in _CATEGORY_TECH_MAP.get(cat, []):
            tech_scores[tech_key] = tech_scores.get(tech_key, 0) + hit_count

    # Add all technologies with base score of 0 if not already present
    for key in TECHNOLOGY_DATABASE:
        if key not in tech_scores:
            tech_scores[key] = 0.0

    # Boost/penalise based on context
    if has_tissue_section:
        for k in ["spatial_visium", "spatial_xenium"]:
            tech_scores[k] = tech_scores.get(k, 0) + 2.0
    else:
        for k in ["spatial_visium", "spatial_xenium"]:
            tech_scores[k] = max(0, tech_scores.get(k, 0) - 1.0)

    if budget == "low":
        for k in ["bulk_rnaseq", "nmr_metabolomics", "metabolomics_gcms"]:
            tech_scores[k] = tech_scores.get(k, 0) + 1.0
        for k in ["pacbio_isoseq", "spatial_xenium", "atacseq"]:
            tech_scores[k] = max(0, tech_scores.get(k, 0) - 2.0)
    elif budget == "high":
        for k in ["scrnaseq_10x", "spatial_visium", "metabolomics_lcms"]:
            tech_scores[k] = tech_scores.get(k, 0) + 0.5

    # Normalise scores to 0-1
    max_score = max(tech_scores.values()) if tech_scores else 1.0
    if max_score == 0:
        max_score = 1.0

    # Build recommendations
    recs: List[TechRecommendation] = []
    for key, score in tech_scores.items():
        if score <= 0:
            continue
        tech = TECHNOLOGY_DATABASE[key]
        norm_score = score / max_score
        tier = 1 if norm_score >= 0.7 else (2 if norm_score >= 0.3 else 3)
        rationale = _build_rationale(tech, matched_categories, q_lower)
        recs.append(TechRecommendation(
            technology=tech,
            relevance_score=round(norm_score, 2),
            rationale=rationale,
            tier=tier,
        ))

    recs.sort(key=lambda r: (-r.tier == 1, -r.relevance_score))
    # Actually sort: tier ASC, then relevance DESC
    recs.sort(key=lambda r: (r.tier, -r.relevance_score))

    # Decision summary
    top_names = [r.technology.name for r in recs if r.tier == 1]
    if not top_names:
        top_names = [recs[0].technology.name] if recs else ["Bulk RNA-seq"]

    summary = _build_decision_summary(top_names, matched_categories, budget)

    # Suggested order (tier-1 first, then tier-2)
    order = [r.technology.name for r in recs if r.tier <= 2]

    return TechAdvisorReport(
        question=question,
        recommendations=recs,
        decision_summary=summary,
        suggested_order=order,
    )


def get_technology(name: str) -> Optional[SequencingTechnology]:
    """Look up a technology by key."""
    return TECHNOLOGY_DATABASE.get(name)


def list_technologies() -> List[str]:
    """Return all technology keys."""
    return list(TECHNOLOGY_DATABASE.keys())


def get_decision_tree() -> Dict[str, str]:
    """Return the high-level decision tree as question->technology mapping."""
    return {
        "Which genes are changing?": "Bulk RNA-seq or scRNA-seq",
        "WHERE in the tissue?": "Spatial Transcriptomics (Visium/Xenium)",
        "Full-length isoforms?": "ONT Direct RNA or PacBio Iso-Seq",
        "Chromatin accessibility?": "ATAC-seq or Multiome",
        "What metabolites?": "LC-MS (untargeted) or GC-MS",
        "Quick first-pass screen?": "NMR or lactate/glucose ratio",
        "Cell type composition?": "10x Chromium scRNA-seq",
        "Full mechanistic picture?": "scRNA-seq + spatial + LC-MS + MOFA",
    }


# ── Private helpers ──────────────────────────────────────────

def _build_rationale(
    tech: SequencingTechnology,
    matched_cats: Dict[str, int],
    q_lower: str,
) -> str:
    """Generate a one-line rationale for why this technology is recommended."""
    parts = []
    for cat in matched_cats:
        for tag in tech.categories:
            if tag in cat or cat in tag:
                parts.append(f"matches '{cat}' query")
                break
    if not parts:
        parts.append("general relevance to biomaterials research")
    return "; ".join(parts[:2]) + f". {tech.best_for[0]}."


def _build_decision_summary(
    top_names: List[str],
    matched_cats: Dict[str, int],
    budget: str,
) -> str:
    """Build a natural-language decision summary."""
    cats = ", ".join(matched_cats.keys())
    tops = " + ".join(top_names)
    budget_note = ""
    if budget == "low":
        budget_note = " Budget-conscious options prioritised."
    elif budget == "high":
        budget_note = " Higher-cost comprehensive platforms included."
    return (
        f"For questions about {cats}, recommend starting with {tops}.{budget_note}"
    )
