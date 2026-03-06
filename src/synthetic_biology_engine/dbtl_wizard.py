"""DBTL Wizard — Design-Build-Test-Learn circuit planner.

7-step guided process from a goal function to a build-ready circuit design
document with iGEM/SynBioHub part suggestions and a test plan.
"""
from dataclasses import dataclass, field
from typing import Optional
import datetime


@dataclass
class DBTLDesign:
    # Step 1-4 inputs
    goal:            str = ""          # e.g. "cells that sense inflammation + release IL-10"
    sensing_part:    str = ""          # promoter / sensor
    sensing_source:  str = ""          # iGEM part name, SynBioHub URI, or custom
    output_part:     str = ""          # coding sequence / therapeutic output
    output_source:   str = ""
    chassis:         str = ""          # E. coli / S. cerevisiae / mammalian / CHO / iPSC
    terminator:      str = "BBa_B0015" # standard double terminator
    regulatory_note: str = ""          # Scenario C flag if GMO in vivo

    # Step 5-7 generated content
    build_protocol:  list[str] = field(default_factory=list)
    test_plan:       list[str] = field(default_factory=list)
    dbtl_stage:      str = "Design"    # Design / Build / Test / Learn
    iteration:       int = 1
    notes:           str = ""
    created_at:      str = field(default_factory=lambda: datetime.datetime.now().isoformat())


# ── Chassis knowledge base ────────────────────────────────────────────────────
CHASSIS_KB: dict[str, dict] = {
    "E. coli": {
        "full_name": "Escherichia coli BL21(DE3) or DH5α",
        "strengths": "Fast growth, cheap, high yield, huge parts library",
        "weaknesses": "No post-translational modifications, endotoxin risk",
        "best_for": ["protein production", "biosynthetic polymers", "PHB", "growth factors"],
        "transformation": "Heat shock (42°C, 90s) or electroporation",
        "promoters": ["T7", "lac", "trc", "BBa_J23100 (Anderson constitutive series)"],
        "doubling_time": "~20 min",
    },
    "S. cerevisiae": {
        "full_name": "Saccharomyces cerevisiae BY4741 or CEN.PK",
        "strengths": "Eukaryotic glycosylation, HR-based editing (no CRISPR needed), safe",
        "weaknesses": "Slower, lower yield vs E. coli, complex media",
        "best_for": ["recombinant proteins needing glycosylation", "spider silk", "collagen"],
        "transformation": "Lithium acetate / PEG / heat shock or electroporation",
        "promoters": ["GAL1", "TEF1", "CYC1", "GPD"],
        "doubling_time": "~90 min",
    },
    "CHO cells": {
        "full_name": "Chinese Hamster Ovary CHO-K1",
        "strengths": "Human-like glycosylation, established GMP manufacturing",
        "weaknesses": "Expensive, slow, requires serum-free adaptation",
        "best_for": ["therapeutic proteins", "growth factors at scale", "mAbs"],
        "transformation": "Lipofection or electroporation",
        "promoters": ["CMV", "EF1a", "SV40"],
        "doubling_time": "~12-14 h",
    },
    "iPSC / Primary cells": {
        "full_name": "Human iPSC or primary cell lines",
        "strengths": "Most physiologically relevant, direct clinical translation",
        "weaknesses": "Difficult to transfect, expensive, passage-limited",
        "best_for": ["living materials in vivo", "Scenario C ATMP circuits", "disease models"],
        "transformation": "RNP electroporation (non-viral) or AAV / LNP",
        "promoters": ["CAG", "EF1a", "tissue-specific"],
        "doubling_time": "~20-24 h",
    },
    "Pichia pastoris": {
        "full_name": "Komagataella phaffii (Pichia pastoris) GS115 / X-33",
        "strengths": "Methanol-inducible high yield, secretion, partial glycosylation",
        "weaknesses": "Non-human glycosylation, methanol handling hazard",
        "best_for": ["extracellular protein secretion", "collagen-like peptides"],
        "transformation": "Electroporation or spheroplast",
        "promoters": ["AOX1 (methanol-inducible)", "GAP (constitutive)"],
        "doubling_time": "~2 h",
    },
}

# ── Part suggestions by function ─────────────────────────────────────────────
SENSING_PARTS: dict[str, list[dict]] = {
    "inflammation": [
        {"name": "BBa_K3801005", "description": "NF-kB promoter — responds to IL-1β, TNF-α",
         "source": "iGEM 2021", "url": "https://parts.igem.org/Part:BBa_K3801005"},
        {"name": "P_TNF_responsive", "description": "TNF-α responsive promoter",
         "source": "Literature", "url": ""},
    ],
    "hypoxia": [
        {"name": "HRE_promoter", "description": "Hypoxia response element — HIF-1α binding",
         "source": "Literature", "url": "https://www.addgene.org/search/catalog/plasmids/?q=hypoxia+HRE"},
    ],
    "mechanical stress": [
        {"name": "MEC1_promoter", "description": "Mechanosensitive promoter in yeast",
         "source": "Literature", "url": ""},
    ],
    "constitutive": [
        {"name": "BBa_J23100", "description": "Strong constitutive promoter (E. coli)",
         "source": "iGEM Registry", "url": "https://parts.igem.org/Part:BBa_J23100"},
        {"name": "BBa_J23106", "description": "Medium constitutive promoter (E. coli)",
         "source": "iGEM Registry", "url": "https://parts.igem.org/Part:BBa_J23106"},
    ],
}

OUTPUT_PARTS: dict[str, list[dict]] = {
    "anti-inflammatory": [
        {"name": "BBa_K4242001", "description": "IL-10 anti-inflammatory cytokine",
         "source": "iGEM 2022", "url": "https://parts.igem.org/Part:BBa_K4242001"},
        {"name": "IL-4_CDS", "description": "IL-4 immunosuppressive cytokine",
         "source": "Literature", "url": ""},
    ],
    "vascularisation": [
        {"name": "BBa_K2924000", "description": "VEGF165 — angiogenesis",
         "source": "iGEM 2019", "url": "https://parts.igem.org/Part:BBa_K2924000"},
    ],
    "osteogenic": [
        {"name": "BBa_K1404003", "description": "BMP-2 — osteogenic differentiation",
         "source": "iGEM 2014", "url": "https://parts.igem.org/Part:BBa_K1404003"},
    ],
    "chondrogenic": [
        {"name": "TGF-B1_CDS", "description": "TGF-β1 — chondrogenic differentiation",
         "source": "Literature", "url": ""},
    ],
    "reporter": [
        {"name": "BBa_E0040", "description": "GFP reporter",
         "source": "iGEM Registry", "url": "https://parts.igem.org/Part:BBa_E0040"},
        {"name": "BBa_E1010", "description": "mRFP red fluorescent reporter",
         "source": "iGEM Registry", "url": "https://parts.igem.org/Part:BBa_E1010"},
    ],
    "biomaterial": [
        {"name": "BBa_K1902001", "description": "Spider silk MaSp1 protein",
         "source": "iGEM 2016", "url": "https://parts.igem.org/Part:BBa_K1902001"},
        {"name": "BBa_K3801000", "description": "Recombinant collagen type I alpha-1",
         "source": "iGEM 2021", "url": "https://parts.igem.org/Part:BBa_K3801000"},
        {"name": "BBa_K1323009", "description": "PHB synthase — biodegradable polymer",
         "source": "iGEM 2014", "url": "https://parts.igem.org/Part:BBa_K1323009"},
    ],
}

BUILD_PROTOCOLS: dict[str, list[str]] = {
    "E. coli": [
        "1. Synthesise or order gene blocks for sensing and output parts (IDT, Twist)",
        "2. Clone sensing promoter + RBS + CDS + terminator into pSB1C3 or pET backbone via Gibson assembly",
        "3. Transform DH5α (cloning) then BL21(DE3) (expression) via heat shock",
        "4. Colony PCR + Sanger sequencing to confirm insert",
        "5. Overnight culture induction (IPTG or appropriate inducer)",
        "6. SDS-PAGE + Western blot to confirm protein expression",
        "7. Functional assay (ELISA or activity assay) for circuit output",
    ],
    "S. cerevisiae": [
        "1. Amplify parts with homology arms (50 bp overlap for HR)",
        "2. Linearise vector by restriction digest at target locus",
        "3. Transform BY4741 via lithium acetate / PEG / heat shock protocol",
        "4. Select on appropriate dropout medium (SD-Ura / SD-Leu)",
        "5. Colony PCR to confirm integration at correct locus",
        "6. Induce with galactose (GAL1) or appropriate inducer",
        "7. ELISA / flow cytometry to confirm circuit output",
    ],
    "iPSC / Primary cells": [
        "1. Design guide RNAs via CRISPOR (crispor.tefor.net)",
        "2. Order RNP (Cas9 protein + guide RNA) from IDT or Synthego",
        "3. Electroporate with RNP using Lonza 4D-Nucleofector (cell-type specific program)",
        "4. Sort GFP+ cells if donor template used (HDR)",
        "5. Single-cell clone expansion for 2-3 weeks",
        "6. Sanger sequencing / NGS to confirm edit",
        "7. Functional validation: immunofluorescence, flow cytometry, ELISA",
    ],
    "CHO cells": [
        "1. Clone GOI into lentiviral or pIRES expression vector",
        "2. Transfect with lipofectamine 3000 or electroporate",
        "3. Select stable integrants with puromycin / G418 for 14 days",
        "4. Expand clonal populations by limiting dilution",
        "5. Confirm expression: Western blot + ELISA on conditioned media",
        "6. Freeze master cell bank at P5",
        "7. Scale: spinner flask -> bioreactor",
    ],
}

TEST_PLANS: dict[str, list[str]] = {
    "protein_output": [
        "ELISA: quantify secreted protein in conditioned media (compare to baseline)",
        "Western blot: confirm molecular weight and expression level",
        "qPCR: confirm transcript-level induction (dose-response to inducer)",
        "Bioassay: functional activity of output protein (e.g., cell migration, ALP for BMP-2)",
        "Dose-response: test circuit across inducer concentration range",
    ],
    "reporter": [
        "Flow cytometry: GFP/RFP fluorescence distribution across population",
        "Confocal microscopy: spatial reporter expression pattern",
        "Live imaging: time-lapse of reporter induction kinetics",
        "FACS sort: enrich responding cells for transcriptomics",
    ],
    "living_material": [
        "Cell viability: live/dead staining at day 1, 7, 14 post-encapsulation",
        "Circuit function in scaffold: in situ staining or conditioned media ELISA",
        "Scaffold structural integrity: rheology / mechanical testing before and after cell loading",
        "Inflammatory challenge: add LPS or IL-1β to culture, measure output",
        "In vitro release kinetics: measure therapeutic output over 28 days",
    ],
    "genome_edit": [
        "ICE or TIDE analysis: indel frequency at cut site",
        "NGS deep sequencing: off-target screening at predicted sites",
        "Karyotyping: chromosomal integrity after editing",
        "Functional phenotype assay: differentiation, migration, or target protein level",
    ],
}


class DBTLWizard:
    """Guides a DBTL circuit design from goal to build-ready document."""

    def suggest_sensing_parts(self, trigger_keyword: str) -> list[dict]:
        """Return sensing part suggestions for a trigger keyword."""
        kw = trigger_keyword.lower()
        for key in SENSING_PARTS:
            if key in kw or kw in key:
                return SENSING_PARTS[key]
        return SENSING_PARTS.get("constitutive", [])

    def suggest_output_parts(self, function_keyword: str) -> list[dict]:
        """Return output part suggestions for a function keyword."""
        kw = function_keyword.lower()
        for key in OUTPUT_PARTS:
            if key in kw or kw in key:
                return OUTPUT_PARTS[key]
        return OUTPUT_PARTS.get("reporter", [])

    def get_chassis_info(self, chassis: str) -> dict:
        return CHASSIS_KB.get(chassis, {})

    def get_chassis_list(self) -> list[str]:
        return list(CHASSIS_KB.keys())

    def check_scenario_c(self, design: DBTLDesign) -> bool:
        """True if this design triggers Regulatory Scenario C (ATMP)."""
        mammalian = design.chassis.lower() in ("ipsc / primary cells", "primary cells",
                                                "ipsc", "mammalian")
        living_material_hint = any(
            kw in design.goal.lower()
            for kw in ("in vivo", "living", "implant", "scaffold", "atmp", "cell therapy")
        )
        return mammalian and living_material_hint

    def generate_build_protocol(self, design: DBTLDesign) -> list[str]:
        chassis = design.chassis
        for key in BUILD_PROTOCOLS:
            if key.lower() in chassis.lower() or chassis.lower() in key.lower():
                return BUILD_PROTOCOLS[key]
        return BUILD_PROTOCOLS.get("E. coli", [])

    def generate_test_plan(self, design: DBTLDesign) -> list[str]:
        goal = design.goal.lower()
        if any(k in goal for k in ("reporter", "gfp", "rfp", "fluorescent")):
            return TEST_PLANS["reporter"]
        if any(k in goal for k in ("edit", "crispr", "knockout", "knock-in")):
            return TEST_PLANS["genome_edit"]
        if any(k in goal for k in ("living", "scaffold", "implant", "encapsul")):
            return TEST_PLANS["living_material"]
        return TEST_PLANS["protein_output"]

    def generate_design_document(self, design: DBTLDesign) -> str:
        chassis_info = self.get_chassis_info(design.chassis)
        scenario_c = self.check_scenario_c(design)
        reg_note = (" REGULATORY FLAG: This design involves GMO cells intended for in vivo use."
                    " This triggers Regulatory Scenario C (ATMP / gene therapy pathway)."
                    " Consult the Regulatory tab before proceeding."
                    if scenario_c else "")

        protocol = "\n".join(f"  {step}" for step in (design.build_protocol or
                                                        self.generate_build_protocol(design)))
        test_plan = "\n".join(f"  - {step}" for step in (design.test_plan or
                                                           self.generate_test_plan(design)))
        chassis_str = ""
        if chassis_info:
            chassis_str = (
                f"  Full name:   {chassis_info.get('full_name', design.chassis)}\n"
                f"  Strengths:   {chassis_info.get('strengths', '')}\n"
                f"  Promoters:   {', '.join(chassis_info.get('promoters', []))}\n"
                f"  Transform:   {chassis_info.get('transformation', '')}\n"
            )

        return f"""DBTL CIRCUIT DESIGN DOCUMENT
Generated: {design.created_at[:10]}   Iteration: {design.iteration}   Stage: {design.dbtl_stage}
{'='*70}

GOAL
  {design.goal}
{reg_note}

CIRCUIT ARCHITECTURE
  Sensing component:  {design.sensing_part or '(not selected)'}
                      Source: {design.sensing_source or '—'}
  Output component:   {design.output_part or '(not selected)'}
                      Source: {design.output_source or '—'}
  Terminator:         {design.terminator}

CHASSIS
  {design.chassis or '(not selected)'}
{chassis_str}
BUILD PROTOCOL
{protocol}

TEST PLAN
{test_plan}

NOTES
  {design.notes or '(none)'}

NEXT DBTL ITERATION
  After completing the Test stage, update this document with:
  - What worked (carry forward)
  - What failed (change in next Design)
  - Specific hypothesis for iteration {design.iteration + 1}
  - Updated part selections based on data
"""
