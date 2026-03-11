"""
Pathway Intervention Planner
=============================
Given a dysregulated pathway + direction + key genes, recommends
genetic, pharmacological, and combinatorial intervention strategies.

Evaluates each pathway node for:
  - GENETIC: CRISPR editing strategy, essentiality, delivery
  - PHARMACOLOGICAL: small molecule modulators via target_lookup
  - COMBINATORIAL: dual-target and sensitisation strategies
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Data classes ──────────────────────────────────────────────

@dataclass
class InterventionStrategy:
    """A single intervention strategy for a pathway node."""
    target_gene: str
    strategy_type: str       # "genetic", "pharmacological", "combinatorial"
    mechanism: str           # e.g. "CRISPRi knockdown", "Small molecule inhibitor"
    tool: str                # e.g. "CRISPRi", "Celecoxib", "CRISPRi + BMP-2"
    evidence_level: str      # "approved", "clinical_trial", "preclinical", "computational"
    rationale: str
    delivery_note: str       # tissue-specific delivery considerations
    safety_flag: str         # known toxicity or off-target risks
    links: List[str]         # module cross-references


@dataclass
class InterventionPlan:
    """Complete intervention plan for a dysregulated pathway."""
    pathway_name: str
    direction: str           # "activated" or "suppressed"
    key_genes: List[str]
    strategies: List[InterventionStrategy]
    summary: str
    warnings: List[str]


# ── Essential genes (do not suggest KO) ──────────────────────

_ESSENTIAL_GENES = {
    "RPS3", "RPS5", "RPL4", "RPL11",  # ribosomal
    "POLR2A", "POLR2B",               # RNA polymerase II
    "TP53",                            # tumour suppressor (context-dependent)
    "MYC",                             # context-dependent
    "ACTB", "GAPDH", "TUBA1B",        # housekeeping
    "PCNA", "RPA1",                    # DNA replication
    "HSPA5", "HSPA8",                  # protein folding
    "PSMB1", "PSMD1",                 # proteasome
    "ATP5F1A", "ATP5F1B",             # ATP synthase
}


# ── Editing strategy KB ──────────────────────────────────────

_EDITING_STRATEGIES: Dict[str, Dict] = {
    "knockout": {
        "description": "Complete gene disruption via CRISPR-Cas9 double-strand break + NHEJ",
        "best_for": "Eliminating toxic/detrimental gene product",
        "caution": "Irreversible. Check essentiality first.",
        "delivery": "Lipofection, viral (AAV/lentivirus), electroporation",
    },
    "crispri": {
        "description": "Transcriptional repression via dCas9-KRAB. Tunable, reversible.",
        "best_for": "Reducing expression without eliminating -- dose-response studies",
        "caution": "Requires constitutive dCas9 expression or transient delivery",
        "delivery": "Plasmid/mRNA delivery of dCas9-KRAB + sgRNA",
    },
    "crispra": {
        "description": "Transcriptional activation via dCas9-VPR/p65. Tunable, reversible.",
        "best_for": "Upregulating suppressed protective genes",
        "caution": "May cause supraphysiological expression",
        "delivery": "Plasmid/mRNA delivery of dCas9-VPR + sgRNA",
    },
    "base_edit": {
        "description": "Single nucleotide change (C>T or A>G) without double-strand break",
        "best_for": "Correcting point mutations, introducing specific SNPs",
        "caution": "Limited to transition mutations. Off-target deamination possible.",
        "delivery": "mRNA + sgRNA (transient preferred to minimise off-target window)",
    },
    "prime_edit": {
        "description": "Search-and-replace editing without DSB. Any small edit possible.",
        "best_for": "Precise insertions, deletions, or all substitutions",
        "caution": "Lower efficiency than Cas9 KO. Large construct.",
        "delivery": "mRNA delivery preferred; AAV capacity may be limiting",
    },
}


# ── Tissue-specific delivery notes ──────────────────────────

_TISSUE_DELIVERY: Dict[str, str] = {
    "bone": (
        "Bone: scaffold-mediated delivery preferred. BMP-2-loaded carriers standard. "
        "Hydroxyapatite nanoparticles for nucleic acid delivery. "
        "AAV serotypes: AAV2, AAV9 show bone tropism."
    ),
    "cartilage": (
        "Cartilage: avascular -- systemic delivery ineffective. "
        "Intra-articular injection or scaffold-loaded. "
        "AAV5 shows chondrocyte tropism. Electroporation of chondrocytes ex vivo."
    ),
    "skin": (
        "Skin: topical application possible. Microneedle patches for nucleic acids. "
        "Lipid nanoparticles (LNP) applied to wound bed. "
        "AAV6 shows keratinocyte tropism."
    ),
    "nerve": (
        "Nerve: intrathecal or direct injection to nerve conduit. "
        "AAV9 crosses blood-brain barrier. "
        "Schwann cell-targeted nanoparticles under development."
    ),
    "cardiac": (
        "Cardiac: direct intramyocardial injection, catheter-based, or pericardial. "
        "AAV9 shows strong cardiac tropism. "
        "mRNA-LNP via coronary delivery emerging."
    ),
    "liver": (
        "Liver: LNP-mRNA is gold standard (cf. Onpattro, COVID vaccines). "
        "AAV8 shows strong hepatocyte tropism. "
        "GalNAc conjugation for hepatocyte-targeted ASOs/siRNAs."
    ),
    "vascular": (
        "Vascular: stent-mediated local delivery. Drug-eluting stents proven. "
        "Endothelial-targeted nanoparticles (anti-CD31 conjugated). "
        "Gene-eluting stents in preclinical development."
    ),
}


# ── Public API ───────────────────────────────────────────────

def plan_intervention(
    pathway_name: str,
    direction: str,                # "activated" or "suppressed"
    key_genes: List[str],
    tissue_type: str = "",
    include_pharmacological: bool = True,
) -> InterventionPlan:
    """Generate an intervention plan for a dysregulated pathway.

    Parameters
    ----------
    pathway_name : str
        Name of the pathway (e.g. "NF-kB signalling").
    direction : str
        "activated" or "suppressed".
    key_genes : List[str]
        Gene symbols driving the dysregulation.
    tissue_type : str
        Target tissue for delivery feasibility.
    include_pharmacological : bool
        Whether to include drug-based strategies.

    Returns
    -------
    InterventionPlan
    """
    strategies: List[InterventionStrategy] = []
    warnings: List[str] = []

    for gene in key_genes:
        gene_upper = gene.upper().strip()

        # ── GENETIC strategies ──
        genetic = _plan_genetic(gene_upper, direction, tissue_type)
        strategies.extend(genetic)

        # Check essentiality
        if gene_upper in _ESSENTIAL_GENES:
            warnings.append(
                f"{gene_upper} is likely essential -- knockout NOT recommended. "
                f"CRISPRi/CRISPRa preferred for tuning."
            )

        # ── PHARMACOLOGICAL strategies ──
        if include_pharmacological:
            pharma = _plan_pharmacological(gene_upper, direction)
            strategies.extend(pharma)

    # ── COMBINATORIAL strategies ──
    if len(key_genes) >= 2 and include_pharmacological:
        combo = _plan_combinatorial(key_genes, direction, tissue_type)
        strategies.extend(combo)

    # Sort by evidence level
    evidence_order = {
        "approved": 0, "clinical_trial": 1,
        "preclinical": 2, "computational": 3,
    }
    strategies.sort(key=lambda s: evidence_order.get(s.evidence_level, 4))

    # Summary
    n_genetic = sum(1 for s in strategies if s.strategy_type == "genetic")
    n_pharma = sum(1 for s in strategies if s.strategy_type == "pharmacological")
    n_combo = sum(1 for s in strategies if s.strategy_type == "combinatorial")
    summary = (
        f"Pathway '{pathway_name}' is {direction}. "
        f"Identified {len(strategies)} intervention strategies: "
        f"{n_genetic} genetic, {n_pharma} pharmacological, {n_combo} combinatorial."
    )

    return InterventionPlan(
        pathway_name=pathway_name,
        direction=direction,
        key_genes=key_genes,
        strategies=strategies,
        summary=summary,
        warnings=warnings,
    )


def get_editing_strategies() -> Dict[str, Dict]:
    """Return the CRISPR editing strategy KB."""
    return dict(_EDITING_STRATEGIES)


def is_essential(gene_symbol: str) -> bool:
    """Check if a gene is in the essential gene list."""
    return gene_symbol.upper().strip() in _ESSENTIAL_GENES


# ── Private helpers ──────────────────────────────────────────

def _plan_genetic(
    gene: str, direction: str, tissue: str,
) -> List[InterventionStrategy]:
    """Generate genetic intervention strategies for a gene."""
    strategies = []
    delivery = _TISSUE_DELIVERY.get(tissue.lower(), "Standard lipofection or viral delivery.")

    if direction == "activated":
        # Gene is overactive -> suppress it
        if gene not in _ESSENTIAL_GENES:
            strategies.append(InterventionStrategy(
                target_gene=gene,
                strategy_type="genetic",
                mechanism=f"CRISPRi knockdown of {gene}",
                tool="CRISPRi (dCas9-KRAB)",
                evidence_level="preclinical",
                rationale=f"{gene} is activated in this pathway. CRISPRi provides "
                          f"tunable repression without permanent gene disruption.",
                delivery_note=delivery,
                safety_flag="Off-target repression possible. Validate with 2+ guides.",
                links=["Synbio > Genetic Editor", "Synbio > Delivery Advisor"],
            ))
            strategies.append(InterventionStrategy(
                target_gene=gene,
                strategy_type="genetic",
                mechanism=f"CRISPR knockout of {gene}",
                tool="SpCas9 + sgRNA",
                evidence_level="preclinical",
                rationale=f"Complete elimination of {gene} if CRISPRi insufficient.",
                delivery_note=delivery,
                safety_flag="Irreversible. Confirm non-essential in target cell type.",
                links=["Synbio > Genetic Editor"],
            ))
        else:
            strategies.append(InterventionStrategy(
                target_gene=gene,
                strategy_type="genetic",
                mechanism=f"CRISPRi partial knockdown of {gene} (essential gene)",
                tool="CRISPRi (dCas9-KRAB) with weak promoter",
                evidence_level="preclinical",
                rationale=f"{gene} is essential -- full KO is lethal. "
                          f"CRISPRi with calibrated repression level recommended.",
                delivery_note=delivery,
                safety_flag="Essential gene -- titrate carefully. Monitor cell viability.",
                links=["Synbio > Genetic Editor"],
            ))
    else:
        # Gene is suppressed -> activate it
        strategies.append(InterventionStrategy(
            target_gene=gene,
            strategy_type="genetic",
            mechanism=f"CRISPRa activation of {gene}",
            tool="CRISPRa (dCas9-VPR)",
            evidence_level="preclinical",
            rationale=f"{gene} is suppressed. CRISPRa upregulates endogenous expression "
                      f"without permanent genomic change.",
            delivery_note=delivery,
            safety_flag="May cause supraphysiological expression. Dose-response needed.",
            links=["Synbio > Genetic Editor", "Synbio > Delivery Advisor"],
        ))

    return strategies


def _plan_pharmacological(
    gene: str, direction: str,
) -> List[InterventionStrategy]:
    """Generate pharmacological strategies by querying target_lookup."""
    strategies = []
    try:
        from .target_lookup import lookup_target

        # Determine desired mode
        if direction == "activated":
            mode = "inhibitor"
        else:
            mode = "activator"

        result = lookup_target(gene, mode_filter=mode)
        for compound in result.compounds[:3]:  # top 3
            strategies.append(InterventionStrategy(
                target_gene=gene,
                strategy_type="pharmacological",
                mechanism=compound.mechanism or f"{compound.mode} of {gene}",
                tool=compound.compound_name,
                evidence_level=_clinical_to_evidence(compound.clinical_stage),
                rationale=(
                    f"{compound.compound_name} ({compound.compound_id}): "
                    f"{compound.potency}. {compound.indication or ''}"
                ),
                delivery_note=f"Source: {compound.source}",
                safety_flag=compound.toxicity_flag or "Check ADMET profile in Drug Delivery tab.",
                links=["Drug Delivery > Drug Lookup", "Tox > ADMET"],
            ))

        # Also try "all" mode if we got nothing specific
        if not strategies:
            result2 = lookup_target(gene, mode_filter="all")
            for compound in result2.compounds[:2]:
                strategies.append(InterventionStrategy(
                    target_gene=gene,
                    strategy_type="pharmacological",
                    mechanism=compound.mechanism or f"{compound.mode} of {gene}",
                    tool=compound.compound_name,
                    evidence_level=_clinical_to_evidence(compound.clinical_stage),
                    rationale=(
                        f"{compound.compound_name}: {compound.potency}. "
                        f"Mode: {compound.mode}. {compound.indication or ''}"
                    ),
                    delivery_note=f"Source: {compound.source}",
                    safety_flag=compound.toxicity_flag or "Check ADMET profile.",
                    links=["Drug Delivery > Drug Lookup"],
                ))
    except Exception as e:
        logger.debug("Pharmacological lookup for %s failed: %s", gene, e)

    return strategies


def _plan_combinatorial(
    genes: List[str], direction: str, tissue: str,
) -> List[InterventionStrategy]:
    """Suggest combination strategies across multiple targets."""
    strategies = []
    if len(genes) < 2:
        return strategies

    g1, g2 = genes[0].upper(), genes[1].upper()
    delivery = _TISSUE_DELIVERY.get(tissue.lower(), "")

    if direction == "activated":
        strategies.append(InterventionStrategy(
            target_gene=f"{g1}+{g2}",
            strategy_type="combinatorial",
            mechanism=f"CRISPRi {g1} + small molecule inhibitor of {g2}",
            tool=f"Dual-target: genetic ({g1}) + pharmacological ({g2})",
            evidence_level="computational",
            rationale=(
                f"Dual targeting of {g1} and {g2} may provide synergistic "
                f"pathway suppression with lower doses of each intervention, "
                f"reducing off-target effects."
            ),
            delivery_note=delivery or "Requires compatible delivery of both agents.",
            safety_flag="Combination toxicity must be assessed. Start with dose-response matrix.",
            links=["Synbio > Genetic Editor", "Drug Delivery > Drug Lookup"],
        ))
    else:
        strategies.append(InterventionStrategy(
            target_gene=f"{g1}+{g2}",
            strategy_type="combinatorial",
            mechanism=f"CRISPRa {g1} + growth factor for {g2}",
            tool=f"Dual-target: genetic ({g1}) + recombinant protein ({g2})",
            evidence_level="computational",
            rationale=(
                f"Combined activation of {g1} and {g2} may restore "
                f"pathway activity more effectively than single-target."
            ),
            delivery_note=delivery or "Growth factor can be scaffold-loaded.",
            safety_flag="Monitor for over-activation. Dose-response studies essential.",
            links=["Synbio > Genetic Editor", "Materials > Growth Factor Loading"],
        ))

    return strategies


def _clinical_to_evidence(stage: str) -> str:
    """Map clinical stage to evidence level."""
    mapping = {
        "approved": "approved",
        "phase_3": "clinical_trial",
        "phase_2": "clinical_trial",
        "phase_1": "clinical_trial",
        "preclinical": "preclinical",
    }
    return mapping.get(stage, "computational")
