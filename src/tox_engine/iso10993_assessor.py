"""
ISO 10993 Toxicological Risk Assessor

Implements the ISO 10993 biological evaluation framework for medical devices.
Uses CompTox + AOP + ADMETlab data to populate the required test matrix.

ISO 10993 is the international standard for biocompatibility testing of
medical devices. It defines required tests based on:
  - Contact type (surface / externally communicating / implant)
  - Contact duration (limited < 24h / prolonged 24h-30d / permanent > 30d)
  - Material nature (polymer, metal, ceramic, natural, composite)

This module:
  - Determines which ISO 10993 tests are required for your device
  - Flags which tests might be waivable based on existing literature/data
  - Uses CompTox to pre-populate chemistry-based risk assessment
  - Uses AOP to identify biological pathways of concern
  - Generates a structured risk assessment narrative for the briefing
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .comptox_client import CompToxClient, ChemicalHazardProfile
    from .aop_client import AOPClient, AOPMappingResult
    from .admet_client import ADMETClient, ADMETResult

logger = logging.getLogger(__name__)

# ISO 10993-1 test matrix: (contact_type, duration) -> required tests
_TEST_MATRIX = {
    ("surface", "limited"):    ["cytotoxicity", "sensitisation"],
    ("surface", "prolonged"):  ["cytotoxicity", "sensitisation", "irritation"],
    ("surface", "permanent"):  ["cytotoxicity", "sensitisation", "irritation", "systemic_toxicity"],
    ("external_communicating", "limited"):   ["cytotoxicity", "sensitisation", "haemocompatibility"],
    ("external_communicating", "prolonged"): ["cytotoxicity", "sensitisation", "haemocompatibility",
                                               "systemic_toxicity", "subacute_toxicity"],
    ("external_communicating", "permanent"): ["cytotoxicity", "sensitisation", "haemocompatibility",
                                               "systemic_toxicity", "subacute_toxicity",
                                               "genotoxicity", "implantation"],
    ("implant", "limited"):    ["cytotoxicity", "sensitisation", "systemic_toxicity",
                                 "haemocompatibility", "implantation"],
    ("implant", "prolonged"):  ["cytotoxicity", "sensitisation", "systemic_toxicity",
                                 "subacute_toxicity", "haemocompatibility", "implantation",
                                 "genotoxicity"],
    ("implant", "permanent"):  ["cytotoxicity", "sensitisation", "systemic_toxicity",
                                 "subchronic_toxicity", "chronic_toxicity", "haemocompatibility",
                                 "implantation", "genotoxicity", "carcinogenicity",
                                 "reproductive_developmental_toxicity"],
}

_TEST_DESCRIPTIONS = {
    "cytotoxicity":          "ISO 10993-5: Cell viability assay (MTS, LDH, or live-dead)",
    "sensitisation":         "ISO 10993-10: Guinea pig maximisation or LLNA (mouse ear swelling)",
    "irritation":            "ISO 10993-10: Skin/mucosal irritation assay or in vitro RhE model",
    "systemic_toxicity":     "ISO 10993-11: Acute systemic toxicity (single dose, rodent)",
    "subacute_toxicity":     "ISO 10993-11: 14-day repeat-dose study (rodent)",
    "subchronic_toxicity":   "ISO 10993-11: 90-day repeat-dose study (rodent)",
    "chronic_toxicity":      "ISO 10993-11: >90-day repeat-dose study",
    "haemocompatibility":    "ISO 10993-4: Haemolysis, thrombogenicity, platelet activation",
    "genotoxicity":          "ISO 10993-3: Ames test + in vitro micronucleus + in vivo if needed",
    "carcinogenicity":       "ISO 10993-3: Only if genotox positive or novel chemistry",
    "implantation":          "ISO 10993-6: Tissue response at implant site (histopathology)",
    "reproductive_developmental_toxicity": "ISO 10993-3: If permanent implant with systemic exposure",
    "degradation":           "ISO 10993-13/14/15: Degradation products characterisation",
}


@dataclass
class ISO10993TestItem:
    test_id: str
    description: str
    required: bool = True
    waiver_possible: bool = False
    waiver_rationale: str = ""
    data_available: bool = False        # True if CompTox/literature data covers this
    risk_level: str = "undetermined"    # low / moderate / high / undetermined


@dataclass
class ISO10993Assessment:
    """Full ISO 10993 biological evaluation assessment for a device/material."""
    material_name: str
    contact_type: str           # surface / external_communicating / implant
    contact_duration: str       # limited / prolonged / permanent
    material_components: list = field(default_factory=list)
    required_tests: list = field(default_factory=list)   # list[ISO10993TestItem]
    chemical_risk_flags: list = field(default_factory=list)
    aop_concerns: list = field(default_factory=list)
    overall_risk_tier: str = "undetermined"
    narrative: str = ""
    success: bool = True
    error: Optional[str] = None

    @property
    def high_risk_tests(self) -> list:
        return [t for t in self.required_tests if t.risk_level == "high"]

    @property
    def waivable_tests(self) -> list:
        return [t for t in self.required_tests if t.waiver_possible]


class ISO10993Assessor:
    """
    Builds ISO 10993 biological evaluation packages for biomaterials.

    Args:
        comptox:  CompToxClient instance (optional -- degrades gracefully)
        aop:      AOPClient instance (optional)
        admet:    ADMETClient instance (optional)
    """

    def __init__(self, comptox=None, aop=None, admet=None):
        self._comptox = comptox
        self._aop = aop
        self._admet = admet

    def assess(
        self,
        material_name: str,
        contact_type: str,
        contact_duration: str,
        components: Optional[list] = None,
    ) -> ISO10993Assessment:
        """
        Run a full ISO 10993 biological evaluation.

        Args:
            material_name:    e.g. "GelMA hydrogel scaffold"
            contact_type:     "surface" | "external_communicating" | "implant"
            contact_duration: "limited" | "prolonged" | "permanent"
            components:       List of chemical names in the formulation
                              e.g. ["gelatin methacryloyl", "lithium phenyl phosphinate",
                                    "phosphate buffered saline"]
        """
        if components is None:
            components = []

        key = (contact_type, contact_duration)
        if key not in _TEST_MATRIX:
            return ISO10993Assessment(
                material_name=material_name,
                contact_type=contact_type,
                contact_duration=contact_duration,
                success=False,
                error=f"Invalid contact_type/duration: {contact_type}/{contact_duration}",
            )

        test_ids = _TEST_MATRIX[key]
        test_items = [
            ISO10993TestItem(
                test_id=tid,
                description=_TEST_DESCRIPTIONS.get(tid, tid),
                required=True,
            )
            for tid in test_ids
        ]

        chemical_flags = []
        aop_concerns = []

        # Enrich with CompTox chemical hazard data
        if self._comptox and components:
            profiles = self._comptox.screen_material_components(components)
            for p in profiles:
                if not p.success:
                    continue
                if p.is_high_concern:
                    chemical_flags.append(
                        f"{p.name}: {p.carcinogenicity or p.genotoxicity} -- elevated risk"
                    )
                    # Mark genotoxicity test as high risk if chemical is genotoxic
                    if p.genotoxicity:
                        for t in test_items:
                            if t.test_id == "genotoxicity":
                                t.risk_level = "high"
                                t.data_available = True

        # Enrich with AOP pathway data
        if self._aop and components:
            for component in components:
                mapping = self._aop.map_chemical_to_aops(component)
                if mapping.success and mapping.aops:
                    for aop in mapping.aops[:2]:   # top 2 per component
                        aop_concerns.append(
                            f"{component}: {aop.title} "
                            f"(AO: {aop.adverse_outcome})"
                        )

        overall = self._compute_overall_risk(test_items, chemical_flags)
        narrative = self._build_narrative(
            material_name, contact_type, contact_duration,
            test_items, chemical_flags, aop_concerns
        )

        return ISO10993Assessment(
            material_name=material_name,
            contact_type=contact_type,
            contact_duration=contact_duration,
            material_components=components,
            required_tests=test_items,
            chemical_risk_flags=chemical_flags,
            aop_concerns=aop_concerns,
            overall_risk_tier=overall,
            narrative=narrative,
            success=True,
        )

    def _compute_overall_risk(self, tests: list, flags: list) -> str:
        if flags:
            return "high"
        if any(t.risk_level == "high" for t in tests):
            return "high"
        if any(t.risk_level == "moderate" for t in tests):
            return "moderate"
        return "low"

    def _build_narrative(self, material, contact_type, duration,
                          tests, flags, aop_concerns) -> str:
        n_tests = len(tests)
        lines = [
            f"## ISO 10993 Biological Evaluation — {material}",
            f"",
            f"Contact type: **{contact_type}** | Duration: **{duration}**",
            f"",
            f"### Required Tests ({n_tests})",
        ]
        for t in tests:
            flag = " ⚠️ HIGH RISK" if t.risk_level == "high" else ""
            lines.append(f"- {t.description}{flag}")

        if flags:
            lines += ["", "### Chemical Hazard Flags"]
            for f in flags:
                lines.append(f"- {f}")

        if aop_concerns:
            lines += ["", "### Adverse Outcome Pathway Concerns"]
            for c in aop_concerns:
                lines.append(f"- {c}")

        return "\n".join(lines)
