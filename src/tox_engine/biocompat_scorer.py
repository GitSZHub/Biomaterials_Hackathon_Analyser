"""
Biocompatibility Scorer

Aggregates data from CompTox, ADMETlab, and AOP to produce a composite
biocompatibility score and confidence-tiered risk assessment for a material.

Score architecture:
  - Chemical Hazard Score (CompTox):  40% weight
    NOAEL/LOAEL levels, carcinogen flags, genotox flags
  - ADMET Toxicity Score (ADMETlab):  30% weight
    hepatotoxicity, hERG, Ames, acute tox of active molecules
  - AOP Pathway Score:                30% weight
    number and severity of Adverse Outcome Pathways triggered

Output: 0-100 score where 100 = no concerns detected.
Confidence tier: A (data-rich) / B (partial data) / C (prediction-only)
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .comptox_client import CompToxClient, ChemicalHazardProfile
    from .aop_client import AOPClient, AOPMappingResult
    from .admet_client import ADMETClient, ADMETResult

logger = logging.getLogger(__name__)


@dataclass
class BiocCompatScore:
    """Composite biocompatibility score for a material."""
    material_name: str
    overall_score: float = 0.0          # 0-100, higher = safer
    confidence_tier: str = "C"          # A / B / C
    chemical_hazard_score: float = 0.0
    admet_score: float = 0.0
    aop_score: float = 0.0
    risk_tier: str = "undetermined"     # low / moderate / high
    flags: list = field(default_factory=list)
    strengths: list = field(default_factory=list)
    recommended_tests: list = field(default_factory=list)
    score_rationale: str = ""
    success: bool = True
    error: Optional[str] = None

    @property
    def traffic_light(self) -> str:
        """Red / Amber / Green label for UI display."""
        if self.overall_score >= 70:
            return "green"
        if self.overall_score >= 40:
            return "amber"
        return "red"


class BiocCompatScorer:
    """
    Produces composite biocompatibility scores using ToxMCP data sources.

    Args:
        comptox:  CompToxClient (optional)
        admet:    ADMETClient (optional)
        aop:      AOPClient (optional)
    """

    def __init__(self, comptox=None, admet=None, aop=None):
        self._comptox = comptox
        self._admet = admet
        self._aop = aop

    def score_material(
        self,
        material_name: str,
        components: list,
        drug_smiles: Optional[list] = None,
    ) -> BiocCompatScore:
        """
        Score a material based on its chemical composition.

        Args:
            material_name:  Human-readable name e.g. "PCL scaffold"
            components:     List of chemical names making up the material
            drug_smiles:    SMILES list for any loaded drugs (drug-eluting devices)
        """
        chem_score = 100.0
        admet_score = 100.0
        aop_score = 100.0
        flags = []
        strengths = []
        data_points = 0

        # Chemical hazard scoring via CompTox
        if self._comptox and components:
            profiles = self._comptox.screen_material_components(components)
            for p in profiles:
                if not p.success:
                    continue
                data_points += 1
                if p.risk_tier == "high":
                    chem_score -= 40
                    flags.append(f"HIGH HAZARD: {p.name} ({p.carcinogenicity or p.genotoxicity})")
                elif p.risk_tier == "moderate":
                    chem_score -= 15
                    flags.append(f"Moderate concern: {p.name}")
                else:
                    strengths.append(f"{p.name}: low hazard in CompTox database")
            chem_score = max(0.0, chem_score)

        # ADMET scoring for drug molecules
        if self._admet and drug_smiles:
            for smiles in drug_smiles:
                result = self._admet.predict_admet(smiles)
                if not result.success:
                    continue
                data_points += 1
                if result.has_toxicity_flags:
                    admet_score -= 30
                    flags.append(f"ADMET flag ({smiles[:20]}...): {result.toxicity_summary}")
            admet_score = max(0.0, admet_score)

        # AOP scoring
        if self._aop and components:
            total_aops = 0
            for comp in components:
                mapping = self._aop.map_chemical_to_aops(comp)
                if mapping.success:
                    data_points += 1
                    total_aops += mapping.aop_count
                    for aop in mapping.aops[:2]:
                        flags.append(f"AOP: {aop.title} (via {comp})")
            # Penalise proportionally to number of AOPs
            aop_score = max(0.0, 100.0 - (total_aops * 10))

        # Weighted composite
        overall = (chem_score * 0.4) + (admet_score * 0.3) + (aop_score * 0.3)

        # Confidence tier
        if data_points >= len(components) * 2:
            tier = "A"
        elif data_points >= len(components):
            tier = "B"
        else:
            tier = "C"

        risk = "low" if overall >= 70 else ("moderate" if overall >= 40 else "high")

        return BiocCompatScore(
            material_name=material_name,
            overall_score=round(overall, 1),
            confidence_tier=tier,
            chemical_hazard_score=round(chem_score, 1),
            admet_score=round(admet_score, 1),
            aop_score=round(aop_score, 1),
            risk_tier=risk,
            flags=flags,
            strengths=strengths,
            score_rationale=(
                f"Score based on {data_points} data point(s) across "
                f"{len(components)} component(s). "
                f"Confidence tier {tier} "
                f"({'data-rich' if tier == 'A' else 'partial data' if tier == 'B' else 'prediction-only'})."
            ),
            success=True,
        )
