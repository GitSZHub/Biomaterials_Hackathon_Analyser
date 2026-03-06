"""Living Materials Engine.

Connects genetic circuit designs (from DBTL wizard) to scaffold
materials. Handles Scenario C detection and generates integration plans.
"""
from dataclasses import dataclass, field
from typing import Optional


# ── Material compatibility matrix ─────────────────────────────────────────────
# For each scaffold material: which cell types encapsulate well, key limitations
MATERIAL_CELL_COMPAT: dict[str, dict] = {
    "GelMA": {
        "suitable_cells": ["iPSC", "primary chondrocytes", "MSCs", "HUVECs",
                           "fibroblasts", "neural cells"],
        "stiffness_kPa": "0.1 – 50 (tunable by crosslink density)",
        "crosslinking": "UV (405 nm, Irgacure 2959) or visible light (Ru/SPS)",
        "degradation": "MMP-dependent, tunable",
        "oxygen_permeability": "High",
        "notes": "Gold standard bioink; defined composition; no animal batch variability",
        "limitations": "UV cytotoxic if overexposed; strength lower than collagen gels",
    },
    "Alginate": {
        "suitable_cells": ["beta cells", "MSCs", "chondrocytes", "hepatocytes"],
        "stiffness_kPa": "1 – 100 (Ca2+ concentration)",
        "crosslinking": "Ionic (CaCl2, BaCl2)",
        "degradation": "Slow (not cell-degradable unless oxidised alginate used)",
        "oxygen_permeability": "Moderate",
        "notes": "Excellent for encapsulation; no RGD inherently; add RGD-alginate for adhesion",
        "limitations": "Non-cell-adhesive — must functionalise for adherent cells",
    },
    "Collagen type I": {
        "suitable_cells": ["fibroblasts", "endothelial cells", "smooth muscle cells", "MSCs"],
        "stiffness_kPa": "0.02 – 2 (concentration-dependent)",
        "crosslinking": "Thermal (37°C) + optional EDC/NHS chemical crosslinking",
        "degradation": "Collagenase-sensitive",
        "oxygen_permeability": "High",
        "notes": "Native ECM component; excellent cell adhesion; animal-derived batch variability",
        "limitations": "Animal source (bovine/rat tail); immunogenicity risk; low mechanical strength",
    },
    "Hyaluronic acid": {
        "suitable_cells": ["chondrocytes", "MSCs", "neural cells", "dermal fibroblasts"],
        "stiffness_kPa": "0.1 – 20 (methacrylate modification)",
        "crosslinking": "UV (HA-MA) or enzymatic",
        "degradation": "Hyaluronidase-sensitive",
        "oxygen_permeability": "High",
        "notes": "Cartilage-native ECM; CD44 binding for MSC niche signalling",
        "limitations": "Low mechanical strength without modification",
    },
    "PLGA scaffold": {
        "suitable_cells": ["osteoblasts", "chondrocytes", "fibroblasts"],
        "stiffness_kPa": "100,000 – 4,000,000 (rigid polymer)",
        "crosslinking": "N/A (melt processing or solvent casting)",
        "degradation": "Hydrolytic (weeks to months, tunable LA:GA ratio)",
        "oxygen_permeability": "Low in bulk; surface seeding only",
        "notes": "FDA-approved polymer; degradation products acidic — buffer carefully",
        "limitations": "Solid scaffold — cell loading by surface seeding, not 3D encapsulation",
    },
    "Fibrin": {
        "suitable_cells": ["endothelial cells", "fibroblasts", "MSCs", "SMCs"],
        "stiffness_kPa": "0.02 – 5",
        "crosslinking": "Thrombin + CaCl2 (physiological)",
        "degradation": "Fibrinolysis (plasmin); fast unless inhibited",
        "oxygen_permeability": "High",
        "notes": "Haemostatic scaffold; autologous option from patient blood",
        "limitations": "Fast degradation — add aprotinin (fibrinolysis inhibitor) for longer culture",
    },
    "dECM (decellularised ECM)": {
        "suitable_cells": ["tissue-matched primary cells", "iPSC-derived cells"],
        "stiffness_kPa": "Tissue-dependent (5 – 50 typical bioink)",
        "crosslinking": "Thermal gelation",
        "degradation": "MMP-sensitive",
        "oxygen_permeability": "Moderate",
        "notes": "Best biochemical match for target tissue; undefined composition",
        "limitations": "Batch variability; decellularisation efficacy critical; residual DNA risk",
    },
}

# ── Circuit-scaffold integration archetypes ───────────────────────────────────
INTEGRATION_ARCHETYPES: list[dict] = [
    {
        "name": "Inflammation-responsive drug release",
        "trigger": "NF-kB / IL-1β sensing",
        "output": "IL-10, dexamethasone prodrug activation, or anti-TNF nanobody",
        "chassis": "iPSC / Primary cells",
        "scaffold": ["GelMA", "Alginate"],
        "scenario_c": True,
        "description": (
            "Cells encapsulated in GelMA or alginate express an NF-kB-driven IL-10 "
            "circuit. Upon local inflammation at the implant site, cells upregulate IL-10 "
            "secretion, dampening the immune response and reducing fibrotic encapsulation."
        ),
        "regulatory_flag": "Scenario C — ATMP (gene-modified cells in device)",
        "key_challenge": "Prolonged cell viability in scaffold; IL-10 dose calibration",
    },
    {
        "name": "On-demand vascularisation",
        "trigger": "Hypoxia response element (HRE)",
        "output": "VEGF165 secretion",
        "chassis": "MSCs or iPSC-derived endothelial cells",
        "scaffold": ["GelMA", "Fibrin"],
        "scenario_c": True,
        "description": (
            "Cells carrying an HRE-VEGF circuit sense local hypoxia in the core of a "
            "thick scaffold and upregulate VEGF, driving in-growth of host vasculature. "
            "Addresses the 200 μm diffusion limit for thick constructs."
        ),
        "regulatory_flag": "Scenario C — ATMP",
        "key_challenge": "Calibrating VEGF dose to avoid tumour-like angiogenesis",
    },
    {
        "name": "Load-sensing ECM upregulation",
        "trigger": "Mechanical stress-responsive element",
        "output": "COL2A1 / aggrecan (chondrogenic ECM)",
        "chassis": "iPSC-derived chondrocytes",
        "scaffold": ["GelMA", "Hyaluronic acid"],
        "scenario_c": True,
        "description": (
            "Chondrocytes engineered with a mechanosensitive promoter driving COL2A1 "
            "upregulate cartilage ECM production in response to cyclic compressive loading. "
            "Couples bioreactor biophysical cues to genetic programme."
        ),
        "regulatory_flag": "Scenario C — ATMP",
        "key_challenge": "Mechanosensitive promoter validation; off-target activation",
    },
    {
        "name": "Engineered producer scaffold coating",
        "trigger": "Constitutive promoter (no sensing)",
        "output": "Spider silk, collagen, or PHB secreted into scaffold",
        "chassis": "E. coli or S. cerevisiae",
        "scaffold": ["PLGA scaffold", "Collagen type I"],
        "scenario_c": False,
        "description": (
            "E. coli or yeast engineered to continuously secrete recombinant structural "
            "proteins (spider silk, collagen-like peptides) are used in bioreactor to "
            "produce scaffold-coating proteins. Cells are NOT implanted; product is purified "
            "and applied to the scaffold."
        ),
        "regulatory_flag": "Scenario D — GMO manufacturing only; product = standard biomaterial",
        "key_challenge": "Protein purification; endotoxin removal (E. coli); batch consistency",
    },
    {
        "name": "Scaffold degradation reporter",
        "trigger": "MMP-cleavable linker drives GFP release",
        "output": "Fluorescent readout of scaffold degradation in vivo",
        "chassis": "Reporter construct (no live cells in scaffold)",
        "scaffold": ["GelMA", "PLGA scaffold"],
        "scenario_c": False,
        "description": (
            "MMP-cleavable peptide linkers conjugated to a fluorophore provide real-time "
            "readout of scaffold degradation rate. No live cells — acellular monitoring device."
        ),
        "regulatory_flag": "Scenario A — acellular diagnostic component",
        "key_challenge": "In vivo imaging window; linker cleavage specificity",
    },
]


@dataclass
class LivingMaterialDesign:
    circuit_goal:      str = ""
    chassis:           str = ""
    scaffold_material: str = ""
    trigger:           str = ""
    output:            str = ""
    scenario_c:        bool = False
    notes:             str = ""
    archetype_name:    str = ""


class LivingMaterialsEngine:
    """Generates living material integration plans from circuit + scaffold pairs."""

    def get_scaffold_list(self) -> list[str]:
        return list(MATERIAL_CELL_COMPAT.keys())

    def get_scaffold_detail(self, material: str) -> dict:
        return MATERIAL_CELL_COMPAT.get(material, {})

    def get_archetypes(self) -> list[dict]:
        return INTEGRATION_ARCHETYPES

    def get_archetypes_for_scaffold(self, scaffold: str) -> list[dict]:
        return [a for a in INTEGRATION_ARCHETYPES
                if scaffold in a.get("scaffold", [])]

    def check_scenario_c(self, design: LivingMaterialDesign) -> bool:
        """True if the design involves live GMO cells implanted in the body."""
        chassis_lower = design.chassis.lower()
        mammalian = any(kw in chassis_lower for kw in
                        ("ipsc", "primary", "msc", "chondrocyte", "endothelial",
                         "fibroblast", "mammalian", "hek", "cho"))
        living_in_vivo = any(kw in design.circuit_goal.lower() for kw in
                             ("implant", "in vivo", "living", "scaffold", "atmp",
                              "encapsul", "therapy", "release"))
        return mammalian and living_in_vivo

    def generate_integration_plan(self, design: LivingMaterialDesign) -> str:
        scaffold_info = MATERIAL_CELL_COMPAT.get(design.scaffold_material, {})
        scenario_c = design.scenario_c or self.check_scenario_c(design)
        reg_flag = (
            "REGULATORY FLAG: Scenario C — ATMP (gene-modified living cells in implantable device).\n"
            "  This pathway requires: IND, Phase I safety trial, GMP manufacturing,\n"
            "  EMA CAT review (EU) or FDA CBER consultation (US).\n"
            "  Consult the Regulatory tab for full pathway."
            if scenario_c else
            "Regulatory pathway: Scenario A or D (acellular or non-implanted GMO production)."
        )

        compat_str = ""
        if scaffold_info:
            compat_str = (
                f"  Stiffness:        {scaffold_info.get('stiffness_kPa', 'N/A')} kPa\n"
                f"  Crosslinking:     {scaffold_info.get('crosslinking', 'N/A')}\n"
                f"  Degradation:      {scaffold_info.get('degradation', 'N/A')}\n"
                f"  O2 permeability:  {scaffold_info.get('oxygen_permeability', 'N/A')}\n"
                f"  Limitations:      {scaffold_info.get('limitations', 'N/A')}\n"
            )

        return f"""LIVING MATERIAL INTEGRATION PLAN
{'='*70}

CIRCUIT GOAL
  {design.circuit_goal}

CIRCUIT COMPONENTS
  Trigger / sensing:  {design.trigger or '(not specified)'}
  Output:             {design.output or '(not specified)'}
  Chassis:            {design.chassis or '(not specified)'}

SCAFFOLD
  Material:           {design.scaffold_material or '(not specified)'}
{compat_str}
{reg_flag}

INTEGRATION WORKFLOW
  1. Validate circuit function in 2D culture before scaffold encapsulation
  2. Optimise cell seeding density in scaffold (typically 2-10 × 10^6 cells/mL)
  3. Confirm cell viability after encapsulation (live/dead, day 1 and 7)
  4. Apply trigger stimulus in scaffold — confirm circuit output by ELISA / imaging
  5. Characterise output kinetics (onset, peak, duration, dose)
  6. Mechanical testing: scaffold integrity before and after cell loading
  7. Long-term stability: culture for minimum 28 days with weekly analysis

KEY CHALLENGES
  - Maintaining cell viability in 3D scaffold (O2/nutrient diffusion limit ~200 μm)
  - Calibrating output dose to therapeutic window (too little = ineffective; too much = toxic)
  - Preventing circuit silencing over long-term culture (methylation of transgene)
  - Immune response to non-autologous cells or viral vector proteins

NOTES
  {design.notes or '(none)'}
"""
