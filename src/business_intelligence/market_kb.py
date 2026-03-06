"""
Market Knowledge Base -- curated biomaterials market data.
===========================================================
Static data curated from publicly available market reports (Grand View Research,
MarketsandMarkets, Mordor Intelligence) and industry databases (2023-2024 baselines).

All figures are approximate and intended for strategic orientation, not investment decisions.

Usage:
    from business_intelligence.market_kb import get_segment, ALL_SEGMENTS, search_segments
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class MarketSegment:
    key:              str
    name:             str
    market_size_2024: str       # USD billions
    cagr:             str       # % CAGR 2024-2030
    market_2030:      str       # projected USD billions
    geography_split:  Dict[str, str]   # region -> % share
    key_players:      List[str]
    growth_drivers:   List[str]
    restraints:       List[str]
    unmet_needs:      List[str]
    reimbursement_notes: str = ""
    relevant_tissues: List[str] = field(default_factory=list)
    regulatory_hurdles: str = ""
    notes:            str = ""


ALL_SEGMENTS: Dict[str, MarketSegment] = {

    "bone_regeneration": MarketSegment(
        key="bone_regeneration",
        name="Bone Regeneration & Substitutes",
        market_size_2024="3.8",
        cagr="5.8",
        market_2030="5.3",
        geography_split={"North America": "42%", "Europe": "28%", "Asia-Pacific": "22%", "Rest": "8%"},
        key_players=["Medtronic", "DePuy Synthes (J&J)", "Stryker", "Zimmer Biomet",
                     "Geistlich Pharma", "Osteomedical", "Artoss", "Berkeley Advanced Biomaterials"],
        growth_drivers=[
            "Ageing population driving osteoporosis and fracture incidence",
            "Rising trauma cases and road accident burden globally",
            "Shift from autograft (donor site morbidity) to synthetic/allograft substitutes",
            "Increasing adoption of bioactive ceramics (HA/TCP) in spinal fusion",
            "3D-printed patient-specific implants gaining regulatory traction",
        ],
        restraints=[
            "High cost of advanced synthetic substitutes vs autograft",
            "Reimbursement limitations in many healthcare systems",
            "Long regulatory timelines for Class III devices",
            "Competition from established metallic implants",
        ],
        unmet_needs=[
            "Vascularised large-volume bone defect repair (>2cm segmental)",
            "Osteoporotic bone — poor primary fixation, need osteoanabolic scaffolds",
            "Paediatric applications (growth-compatible materials)",
            "Off-the-shelf, room-temperature-stable bioactive scaffold",
        ],
        reimbursement_notes=(
            "CPT codes 20930-20938 (bone grafts). Synthetic bone substitutes often reimbursed "
            "under device codes. NICE technology appraisals (TA) generally cover standard bone substitutes. "
            "Novel bioactive scaffolds may require HTA dossier."
        ),
        relevant_tissues=["bone"],
        regulatory_hurdles="Class II-III depending on composition; calcium phosphates typically Class II (510k). "
                           "Growth-factor loaded = Class III (PMA). Cell-seeded = ATMP (EU) / BLA (FDA).",
    ),

    "cartilage_repair": MarketSegment(
        key="cartilage_repair",
        name="Cartilage Repair & Regeneration",
        market_size_2024="1.6",
        cagr="7.2",
        market_2030="2.4",
        geography_split={"North America": "45%", "Europe": "32%", "Asia-Pacific": "17%", "Rest": "6%"},
        key_players=["Smith+Nephew", "Arthrex", "Vericel (MACI)", "Anika Therapeutics",
                     "JRF Ortho", "Bioventus", "CartiHeal (acquired by Bioventus)", "Matricel"],
        growth_drivers=[
            "High prevalence of osteoarthritis (>300 million patients globally)",
            "Sports injury-driven demand in young active population",
            "MACI (autologous chondrocyte implantation) expanding to more centres",
            "One-stage cell-free scaffold approaches reducing procedure cost",
            "MRI advances improving early-stage lesion diagnosis",
        ],
        restraints=[
            "MACI requires 2-stage procedure — high cost and patient burden",
            "Fibrocartilage repair (inferior collagen II:I ratio) remains common outcome",
            "Long rehabilitation periods reducing patient willingness",
            "Limited reimbursement for advanced cell therapies in many countries",
        ],
        unmet_needs=[
            "Full osteochondral unit repair (bone + cartilage in one implant)",
            "Large defects (>4 cm2) — current products limited to <4 cm2",
            "Off-the-shelf (allogeneic) cartilage repair without immune rejection",
            "Durable repair lasting >15 years comparable to native cartilage",
        ],
        reimbursement_notes=(
            "MACI (Vericel) FDA-approved 2017, reimbursed under CPT 27412 (autologous). "
            "EU: MACI is an ATMP — national HTA in each member state. NICE does not currently "
            "recommend ACI broadly (TA89, updated guidance pending). Cell-free scaffolds reimbursed "
            "under standard arthroscopy codes in most markets."
        ),
        relevant_tissues=["cartilage", "bone"],
        regulatory_hurdles="Cell-seeded products = ATMP (EU) / BLA (FDA). "
                           "Cell-free scaffolds typically Class II-III device.",
    ),

    "wound_care": MarketSegment(
        key="wound_care",
        name="Advanced Wound Care & Skin Substitutes",
        market_size_2024="12.1",
        cagr="6.4",
        market_2030="17.5",
        geography_split={"North America": "38%", "Europe": "30%", "Asia-Pacific": "24%", "Rest": "8%"},
        key_players=["3M", "Mölnlycke", "Smith+Nephew", "Acelity (KCI, now 3M)", "Organogenesis",
                     "MiMedx", "Integra LifeSciences", "Coloplast", "Convatec"],
        growth_drivers=[
            "Diabetic foot ulcer epidemic (537 million diabetics globally, IDF 2021)",
            "Rising incidence of chronic wounds (venous leg ulcers, pressure injuries)",
            "Burns and trauma increasing demand for skin substitutes",
            "Ageing population with impaired wound healing capacity",
            "Growth in home-care wound management market",
        ],
        restraints=[
            "Wide heterogeneity in wound aetiology complicates clinical trial design",
            "Reimbursement for advanced dressings inconsistent across payers (US: MAC LCD policies)",
            "High upfront material cost vs standard of care",
            "Regulatory complexity for cell-containing skin substitutes (ATMP/BLA)",
        ],
        unmet_needs=[
            "Diabetic wound healing — anti-biofilm + pro-angiogenic scaffold",
            "Scar-free wound healing (recapitulating foetal healing biology)",
            "Off-the-shelf living skin equivalent with immune tolerance",
            "Point-of-care bioprinted skin for large burns",
        ],
        reimbursement_notes=(
            "US: CMS HCPCS Q-codes for skin substitutes. LCD L33831 limits reimbursement "
            "to wounds with documented standard-of-care failure. UK: NICE NG19 wound care "
            "guidance — advanced dressings recommended for specific indications. "
            "HTA bodies increasingly requiring RCT data for novel skin substitutes."
        ),
        relevant_tissues=["skin"],
        regulatory_hurdles="Scaffold-only: Class II (510k). Cell-containing: ATMP (EU) / BLA or HCT/P (FDA). "
                           "Drug-eluting (antibiotics): combination product.",
    ),

    "cardiovascular_biomaterials": MarketSegment(
        key="cardiovascular_biomaterials",
        name="Cardiovascular Biomaterials & Vascular Grafts",
        market_size_2024="4.9",
        cagr="5.1",
        market_2030="6.6",
        geography_split={"North America": "40%", "Europe": "29%", "Asia-Pacific": "24%", "Rest": "7%"},
        key_players=["Edwards Lifesciences", "Medtronic", "Abbott", "Boston Scientific",
                     "Terumo", "Getinge (Maquet)", "LeMaitre Vascular", "Xeltis"],
        growth_drivers=[
            "Cardiovascular disease remains leading cause of mortality globally",
            "TAVI/TAVR expansion reducing need for open-heart surgery",
            "Small-diameter vascular graft unmet need driving bioengineering R&D",
            "Biodegradable stent and scaffold market growing",
            "Tissue-engineered heart valves entering Phase II/III trials",
        ],
        restraints=[
            "Thrombogenicity remains a key safety challenge for all cardiovascular biomaterials",
            "Class III regulatory pathway for all implantable cardiovascular devices",
            "Long clinical trial durations (5-10 year follow-up endpoints)",
            "Competition from established metallic and ePTFE devices",
        ],
        unmet_needs=[
            "Small-diameter (<6 mm) vascular graft that resists thrombosis without anticoagulation",
            "Off-the-shelf tissue-engineered heart valve (durable, non-immunogenic)",
            "Congenital heart defect patches that grow with the paediatric patient",
            "Endothelialisable scaffold surfaces with rapid cell attachment",
        ],
        reimbursement_notes=(
            "All cardiovascular implants: Class III (PMA) in US. EU MDR Class III. "
            "Novel tissue-engineered valves will require ATMP designation in EU. "
            "DRG-based reimbursement in US and most EU markets — hospital technology "
            "assessment committees (TACs) are key adoption gatekeepers."
        ),
        relevant_tissues=["cardiovascular", "cardiac", "vascular"],
        regulatory_hurdles="Class III (PMA) universally. Cell-seeded = ATMP (EU) / BLA (FDA). "
                           "High clinical evidence bar — pivotal trial mandatory.",
    ),

    "neural_regeneration": MarketSegment(
        key="neural_regeneration",
        name="Neural Regeneration & Spinal Cord Repair",
        market_size_2024="0.8",
        cagr="9.3",
        market_2030="1.4",
        geography_split={"North America": "44%", "Europe": "27%", "Asia-Pacific": "21%", "Rest": "8%"},
        key_players=["Integra LifeSciences (NeuraGen)", "Stryker (NeuroMatrix)", "Axogen",
                     "Collagen Matrix", "Polyganics", "NovaBay Pharmaceuticals"],
        growth_drivers=[
            "Spinal cord injury and peripheral nerve injury incidence rising with trauma",
            "No disease-modifying therapies for SCI — high unmet need",
            "iPSC-derived neural cell therapies entering early clinical trials",
            "Conductive biomaterials (graphene, PEDOT) improving nerve conduit performance",
        ],
        restraints=[
            "Blood-brain barrier limits systemic drug delivery to CNS",
            "Complex surgical access and high variability in injury severity",
            "Long follow-up needed to measure meaningful functional endpoints",
            "Regulatory uncertainty for ATMPs containing gene-modified neural cells",
        ],
        unmet_needs=[
            "Long-gap (>3 cm) peripheral nerve repair — current conduits limited to <3 cm",
            "Spinal cord complete transection repair (no approved therapy exists)",
            "Electroactive scaffolds for functional recovery beyond sensory",
            "Non-invasive delivery of neuroregenerative biomaterials",
        ],
        reimbursement_notes=(
            "Nerve conduits: Class II (510k) in US, covered under CPT 64910-64911. "
            "Novel spinal cord implants: Class III (PMA). "
            "NICE does not currently cover advanced neural regeneration products. "
            "Orphan designation available for SCI products (rare disease criteria)."
        ),
        relevant_tissues=["neural", "spinal cord"],
        regulatory_hurdles="Neural/brain-contact devices always Class III. ATMPs for neural cell therapy "
                           "require full clinical programme. Orphan designation available (reduces trial size).",
    ),

    "dental_biomaterials": MarketSegment(
        key="dental_biomaterials",
        name="Dental Biomaterials & Guided Bone Regeneration",
        market_size_2024="5.2",
        cagr="6.1",
        market_2030="7.4",
        geography_split={"North America": "35%", "Europe": "33%", "Asia-Pacific": "25%", "Rest": "7%"},
        key_players=["Straumann", "Nobel Biocare (Danaher)", "Dentsply Sirona", "Geistlich",
                     "Botiss Biomaterials", "Zimmer Biomet Dental", "Osstem"],
        growth_drivers=[
            "Growing dental implant adoption and implant-supported prosthetics",
            "Rising periodontal disease prevalence driving guided bone regeneration demand",
            "Digital dentistry (CBCT planning, CAD/CAM) enabling patient-specific scaffolds",
            "Ageing edentulous population in Western markets",
        ],
        restraints=[
            "Out-of-pocket payment for most dental procedures limits premium product adoption",
            "Price sensitivity in dental market — standard allografts dominate",
            "Conservative dentist adoption of novel materials without strong clinical evidence",
        ],
        unmet_needs=[
            "Simultaneous implant placement + bone regeneration in compromised sockets",
            "Soft tissue volume augmentation scaffold for gingival aesthetics",
            "Anti-infection bone scaffold for post-extraction ridge preservation",
        ],
        reimbursement_notes=(
            "Most dental biomaterials are not reimbursed under national health systems. "
            "Private dental insurance covers basic procedures. High volume, lower-cost market. "
            "CDT codes cover bone grafting (D7950-D7953) — US private insurance."
        ),
        relevant_tissues=["bone", "connective tissue"],
    ),

    "drug_delivery_biomaterials": MarketSegment(
        key="drug_delivery_biomaterials",
        name="Biomaterial-Based Drug Delivery Systems",
        market_size_2024="8.3",
        cagr="7.8",
        market_2030="13.1",
        geography_split={"North America": "39%", "Europe": "27%", "Asia-Pacific": "26%", "Rest": "8%"},
        key_players=["Evonik", "Ashland", "CordenPharma", "Lubrizol", "Surmodics",
                     "Wuxi Apptec", "Cambrex"],
        growth_drivers=[
            "Biologics requiring injectable depot delivery systems (mAbs, peptides)",
            "Local drug delivery from implants reducing systemic side effects",
            "RNA therapeutics requiring lipid nanoparticle or hydrogel delivery",
            "Controlled release antibiotic coatings on orthopaedic implants",
        ],
        restraints=[
            "Combination product regulatory complexity (CDRH + CDER/CBER)",
            "Drug stability within biomaterial matrix — ICH Q3C extractables",
            "Scale-up challenges for drug-loaded scaffolds under dual GMP regimes",
        ],
        unmet_needs=[
            "Sequential release of multiple growth factors (spatiotemporal control)",
            "Stimuli-responsive systems (pH, temperature, ultrasound-triggered release)",
            "Injectable self-healing hydrogels for minimally invasive delivery",
        ],
        reimbursement_notes=(
            "Drug-device combinations reimbursed under the lead regulatory product: "
            "if drug primary — reimbursed as pharmaceutical (drug formulary). "
            "If device primary — DRG / device code. Separate P&R dossiers often needed."
        ),
        relevant_tissues=["general", "bone", "skin", "cardiovascular"],
        regulatory_hurdles="Combination product (21 CFR Part 3). Dual GMP: device manufacturing "
                           "and pharmaceutical manufacturing. E&L studies mandatory (ICH Q3C).",
    ),
}


def get_segment(key: str) -> Optional[MarketSegment]:
    return ALL_SEGMENTS.get(key)


def search_segments(tissue: str) -> List[MarketSegment]:
    t = tissue.lower()
    return [s for s in ALL_SEGMENTS.values()
            if any(t in rt.lower() for rt in s.relevant_tissues)]


def get_all_segments() -> List[MarketSegment]:
    return list(ALL_SEGMENTS.values())
