"""
Device Classifier -- FDA/EU device class + regulatory scenario detection.
=========================================================================
Implements the four architectural scenarios:

  Scenario A: Inert scaffold -> Class I/II/III standard device pathway
  Scenario B: Scaffold + drug -> Drug-device combination product
  Scenario C: Scaffold + engineered living cells -> ATMP / BLA pathway
  Scenario D: Engineered organism produces the material -> GMO manufacturing

Classification rules follow:
  - FDA: 21 CFR Part 860 device classification framework
  - EU:  EU MDR 2017/745 Annex VIII classification rules
  - ATMP detection: EU Regulation 1394/2007 (gene/cell therapy, TEPs)

All logic is pure Python -- no external dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


# ── Classification result ──────────────────────────────────────────────────────

@dataclass
class DeviceClassification:
    """Full regulatory classification for a biomaterial/device."""
    scenario:            str              # A / B / C / D
    scenario_label:      str             # human-readable label
    fda_class:           str             # Class I / II / III / BLA / ATMP
    eu_class:            str             # I / IIa / IIb / III / ATMP
    atmp_flag:           bool = False    # True = ATMP pathway (EU) / BLA (FDA)
    combination_product: bool = False    # scaffold + drug
    gmo_flag:            bool = False    # engineered organism involved
    contact_type:        str = ""
    contact_duration:    str = ""
    reasoning:           str = ""
    regulation_refs:     List[str] = field(default_factory=list)
    risk_class_rationale: str = ""

    @property
    def is_high_risk(self) -> bool:
        return self.fda_class in ("Class III", "BLA", "ATMP")

    @property
    def needs_clinical_trial(self) -> bool:
        return self.fda_class in ("Class III", "BLA", "ATMP") or self.combination_product

    @property
    def summary_line(self) -> str:
        parts = [f"Scenario {self.scenario}", self.fda_class]
        if self.atmp_flag:
            parts.append("ATMP")
        if self.combination_product:
            parts.append("Combination Product")
        return "  |  ".join(parts)


# ── EU MDR classification rules (Annex VIII simplified) ───────────────────────

_EU_RULES: dict = {
    # Rule 1-4: non-invasive devices
    ("surface",  "limited"):   "I",
    ("surface",  "prolonged"): "IIa",
    ("surface",  "permanent"): "IIb",
    # Rule 5-8: invasive / implant
    ("external_communicating", "limited"):   "IIa",
    ("external_communicating", "prolonged"): "IIb",
    ("external_communicating", "permanent"): "III",
    ("implant",  "limited"):   "IIb",
    ("implant",  "prolonged"): "IIb",
    ("implant",  "permanent"): "III",
}

# FDA classification cross-reference
_FDA_RULES: dict = {
    "I":   "Class I",
    "IIa": "Class II",
    "IIb": "Class II",
    "III": "Class III",
}


# ── Classifier ─────────────────────────────────────────────────────────────────

class DeviceClassifier:
    """
    Determine the regulatory scenario, device class, and applicable pathway.

    Usage:
        clf = DeviceClassifier()
        result = clf.classify(
            contact_type="implant",
            contact_duration="permanent",
            has_drug=False,
            has_living_cells=False,
            cells_engineered=False,
            is_engineered_organism=False,
            target_tissue="bone",
        )
        print(result.scenario, result.fda_class)
    """

    def classify(
        self,
        contact_type: str,
        contact_duration: str,
        has_drug: bool = False,
        has_living_cells: bool = False,
        cells_engineered: bool = False,
        is_engineered_organism: bool = False,
        target_tissue: str = "",
    ) -> DeviceClassification:
        """
        Args:
            contact_type:          "surface" | "external_communicating" | "implant"
            contact_duration:      "limited" | "prolonged" | "permanent"
            has_drug:              scaffold releases a pharmaceutical agent
            has_living_cells:      scaffold contains human/animal cells
            cells_engineered:      cells have been genetically modified
            is_engineered_organism: GMO produces the material (Scenario D)
            target_tissue:         e.g. "bone", "cartilage", "neural"
        """
        # ── Scenario D: GMO manufacturing ──────────────────────────────────
        if is_engineered_organism:
            return self._scenario_d(contact_type, contact_duration)

        # ── Scenario C: ATMP (living cells, especially engineered) ─────────
        if has_living_cells and (cells_engineered or contact_duration == "permanent"):
            return self._scenario_c(contact_type, contact_duration, cells_engineered)

        # ── Scenario B: drug-device combination ────────────────────────────
        if has_drug:
            return self._scenario_b(contact_type, contact_duration)

        # ── Scenario A: standard scaffold / device ─────────────────────────
        return self._scenario_a(contact_type, contact_duration, target_tissue)

    # ── Scenario builders ──────────────────────────────────────────────────────

    def _scenario_a(self, contact_type: str, contact_duration: str,
                    target_tissue: str) -> DeviceClassification:
        eu_class  = _EU_RULES.get((contact_type, contact_duration), "III")
        fda_class = _FDA_RULES.get(eu_class, "Class III")

        # Tissue upgrades: CNS/cardiac → always Class III
        if target_tissue.lower() in ("neural", "spinal cord", "cardiac", "brain"):
            eu_class  = "III"
            fda_class = "Class III"

        refs = ["21 CFR Part 860", "EU MDR 2017/745 Annex VIII"]
        if fda_class == "Class I":
            refs.append("510(k) Exemption (likely)")
        elif fda_class == "Class II":
            refs.append("510(k) Premarket Notification")
        else:
            refs.append("PMA — Premarket Approval")

        return DeviceClassification(
            scenario="A",
            scenario_label="Inert scaffold / medical device",
            fda_class=fda_class,
            eu_class=eu_class,
            contact_type=contact_type,
            contact_duration=contact_duration,
            reasoning=(
                f"{contact_type.replace('_',' ')} contact, {contact_duration} duration. "
                f"EU MDR Annex VIII Rule → {eu_class}. "
                f"FDA equivalent → {fda_class}."
            ),
            regulation_refs=refs,
            risk_class_rationale=self._class_rationale(fda_class),
        )

    def _scenario_b(self, contact_type: str,
                    contact_duration: str) -> DeviceClassification:
        eu_class  = _EU_RULES.get((contact_type, contact_duration), "III")
        # Drug-device combinations are upgraded by one step in EU
        eu_class  = self._upgrade_class(eu_class)
        fda_class = "Class III"   # FDA: combination products default to most stringent

        return DeviceClassification(
            scenario="B",
            scenario_label="Scaffold + drug (combination product)",
            fda_class=fda_class,
            eu_class=eu_class,
            combination_product=True,
            contact_type=contact_type,
            contact_duration=contact_duration,
            reasoning=(
                "Drug-eluting scaffold = drug-device combination product. "
                "FDA: primary mode of action determines lead centre (CDRH vs CDER/CBER). "
                "Usually PMA track. EU: MDR 2017/745 Art. 1(8) — drug component requires "
                "CHMP consultation."
            ),
            regulation_refs=[
                "21 CFR Part 3 (combination products)",
                "FDA Guidance: Combination Products",
                "EU MDR 2017/745 Art. 1(8)",
                "PMA required (FDA)",
            ],
            risk_class_rationale="Combination products follow the most stringent applicable pathway.",
        )

    def _scenario_c(self, contact_type: str, contact_duration: str,
                    engineered: bool) -> DeviceClassification:
        subtype = "Gene-modified cell therapy (TEP)" if engineered else "Cell therapy / TEP"
        return DeviceClassification(
            scenario="C",
            scenario_label=f"Scaffold + living cells — ATMP ({subtype})",
            fda_class="BLA (Biologic License Application)",
            eu_class="ATMP — TEP (Tissue Engineered Product)",
            atmp_flag=True,
            contact_type=contact_type,
            contact_duration=contact_duration,
            reasoning=(
                "Scaffold seeded with living cells intended for in vivo use = "
                "Advanced Therapy Medicinal Product (ATMP). "
                "EU: Regulation EC 1394/2007 — CAT scientific review + EMA centralised "
                "procedure required. "
                "FDA: BLA submission to CBER, Phase I-III clinical programme needed. "
                + ("Genetic modification triggers gene therapy ATMP sub-classification." if engineered else "")
            ),
            regulation_refs=[
                "EU Regulation EC 1394/2007 (ATMPs)",
                "FDA 21 CFR Part 1271 (HCT/Ps)",
                "EMA CAT (Committee for Advanced Therapies)",
                "BLA submission to FDA CBER",
                "ICH Q5A-Q5D (biologics quality)",
            ],
            risk_class_rationale=(
                "ATMPs require full clinical development programme (Phase I-III). "
                "GMP manufacturing under EU GMP Annex 2A (ATMPs). "
                "Hospital exemption may apply for academic/investigator-led studies."
            ),
        )

    def _scenario_d(self, contact_type: str,
                    contact_duration: str) -> DeviceClassification:
        eu_class  = _EU_RULES.get((contact_type, contact_duration), "III")
        fda_class = _FDA_RULES.get(eu_class, "Class III")
        return DeviceClassification(
            scenario="D",
            scenario_label="GMO produces material (manufacturing only, standard device product)",
            fda_class=fda_class,
            eu_class=eu_class,
            gmo_flag=True,
            contact_type=contact_type,
            contact_duration=contact_duration,
            reasoning=(
                "Engineered organism is used only in manufacturing; "
                "the final product contains no living GMO cells. "
                "Product classified as standard medical device. "
                "GMO manufacturing regulated separately under contained use legislation."
            ),
            regulation_refs=[
                "EU Directive 2009/41/EC (contained use of GMOs)",
                "EU MDR 2017/745 (for the final device)",
                "FDA Biotechnology regulations (manufacturing)",
                _FDA_RULES.get(eu_class, "Class III") + " device pathway for final product",
            ],
            risk_class_rationale=(
                "The device pathway applies to the finished product. "
                "GMO manufacturing site requires separate biosafety authorisation. "
                "Traceability of GM-derived components must be documented."
            ),
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _upgrade_class(eu_class: str) -> str:
        order = ["I", "IIa", "IIb", "III"]
        idx = order.index(eu_class) if eu_class in order else len(order) - 1
        return order[min(idx + 1, len(order) - 1)]

    @staticmethod
    def _class_rationale(fda_class: str) -> str:
        return {
            "Class I":   "Low risk. General controls only. Often 510(k) exempt.",
            "Class II":  "Moderate risk. Special controls + 510(k) or De Novo.",
            "Class III": "High risk (sustains life, prevents impairment). PMA required.",
        }.get(fda_class, "")
