"""
Stakeholder Knowledge Base -- biomaterials ecosystem stakeholder map.
======================================================================
Covers the full set of stakeholders in the biomaterials commercialisation
pathway, including the commonly missed HTA bodies, GPOs, and payers.

Usage:
    from business_intelligence.stakeholder_kb import ALL_STAKEHOLDERS, get_stakeholders_by_type
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Stakeholder:
    key:            str
    name:           str
    category:       str        # "clinical" / "payer" / "regulator" / "industry" / "patient" / "hta" / "investor"
    role:           str        # one-sentence description
    interests:      List[str]  # what they care about
    influence:      str        # "high" / "medium" / "low"
    engagement_strategy: str   # how to engage them
    examples:       List[str]  # real-world examples
    typically_missed: bool = False   # flag for stakeholders often overlooked


ALL_STAKEHOLDERS: Dict[str, Stakeholder] = {

    # ── Clinical stakeholders ─────────────────────────────────────────────────

    "surgeons": Stakeholder(
        key="surgeons",
        name="Surgeons / Interventionalists",
        category="clinical",
        role="Primary proceduralists who implant devices and directly evaluate clinical performance.",
        interests=["Ease of use and handling properties", "Surgical technique compatibility",
                   "Clinical outcome data", "Training and support", "Peer-reviewed evidence"],
        influence="high",
        engagement_strategy="KOL advisory boards, cadaveric workshops, surgical technique publications, "
                            "clinical fellowship funding.",
        examples=["Orthopaedic surgeon societies (AAOS, BOA)", "Plastic/reconstructive surgeons (BAPRAS)",
                  "Neurosurgeons (EANS, CNS)", "Interventional cardiologists"],
    ),

    "clinicians": Stakeholder(
        key="clinicians",
        name="Clinical Wound Care / Tissue Specialists",
        category="clinical",
        role="Non-surgical clinicians managing chronic wounds, tissue defects, and biomaterial follow-up.",
        interests=["Evidence base for product switching", "Nurse/clinician training",
                   "Ease of application", "Cost-effectiveness vs standard of care"],
        influence="medium",
        engagement_strategy="Clinical guidelines development, wound care society engagement, "
                            "nurse specialist training programmes.",
        examples=["Tissue viability nurses (TVN)", "Diabetes care nurses", "Dermatologists"],
    ),

    "hospital_procurement": Stakeholder(
        key="hospital_procurement",
        name="Hospital Procurement / Value Analysis Committees (VAC)",
        category="clinical",
        role="Approve product inclusion on formulary; gate purchase decisions based on clinical and economic evidence.",
        interests=["Health economics (cost per QALY, budget impact)",
                   "Total cost of care (not just unit price)",
                   "Compliance with GPO contracts", "Risk (recall history, company stability)"],
        influence="high",
        engagement_strategy="Health economic modelling, budget impact analysis, clinician champion support, "
                            "pilot programme proposals.",
        examples=["NHS procurement hubs", "US hospital IDNs (Vizient, Intalere)", "GPO contract holders"],
    ),

    # ── Payers ────────────────────────────────────────────────────────────────

    "national_payers": Stakeholder(
        key="national_payers",
        name="National Health Insurance / Government Payers",
        category="payer",
        role="Determine reimbursement codes, coverage decisions, and reference prices for medical technologies.",
        interests=["Clinical evidence (RCT data)", "Cost-effectiveness (ICER below threshold)",
                   "Budget impact on public health system", "Equity of access"],
        influence="high",
        engagement_strategy="Early HTA engagement (pre-submission scientific advice), "
                            "real-world evidence generation, patient registry agreements.",
        examples=["CMS (USA — Medicare/Medicaid)", "NHS England", "GKV-Spitzenverband (Germany)",
                  "CNAMTS (France)", "INAMI (Belgium)"],
    ),

    "private_payers": Stakeholder(
        key="private_payers",
        name="Private Health Insurers",
        category="payer",
        role="Coverage decisions for commercially insured patients; often follow national payer decisions with delay.",
        interests=["Claims cost reduction", "Utilisation management", "Comparative effectiveness"],
        influence="medium",
        engagement_strategy="Dossier submission to medical directors, outcomes-based contracting proposals.",
        examples=["UnitedHealth", "Aetna", "Cigna", "Bupa", "Allianz Care"],
    ),

    "gpos": Stakeholder(
        key="gpos",
        name="Group Purchasing Organisations (GPOs)",
        category="payer",
        role="Negotiate contracts for hospital supplies on behalf of member hospitals; control product access in US.",
        interests=["Volume rebates and pricing leverage", "Portfolio rationalisation",
                   "Supplier financial stability and reliability"],
        influence="high",
        engagement_strategy="GPO contract negotiation (often requires >$5M revenue threshold), "
                            "clinical evidence package for formulary inclusion.",
        examples=["Vizient", "Premier", "HealthTrust (HPG)", "Intalere"],
        typically_missed=True,
    ),

    # ── HTA bodies ────────────────────────────────────────────────────────────

    "nice": Stakeholder(
        key="nice",
        name="NICE (National Institute for Health and Care Excellence, UK)",
        category="hta",
        role="Produces technology appraisals (TAs) and medtech innovation briefings (MIBs) for NHS England adoption.",
        interests=["Clinical effectiveness (RCT evidence preferred)", "Cost per QALY (<£20-30k threshold)",
                   "Budget impact to NHS", "Equity and access considerations"],
        influence="high",
        engagement_strategy="NICE Medtech Innovation Briefing (MIB) request early; "
                            "engage MedCity / NICE Advice pre-submission; design UK RCT for TA submission.",
        examples=["NICE TA — MACI (TA895, negative)", "NICE MIB — various wound care products"],
        typically_missed=False,
    ),

    "iqwig": Stakeholder(
        key="iqwig",
        name="IQWiG (Institut fur Qualitat und Wirtschaftlichkeit, Germany)",
        category="hta",
        role="Provides benefit assessments for new drugs and medical devices for German statutory payers (GKV).",
        interests=["Added benefit vs comparator (RCT required)", "Patient-relevant endpoints",
                   "Subgroup analyses", "Long-term data"],
        influence="high",
        engagement_strategy="Engage Gemeinsamer Bundesausschuss (G-BA) early; "
                            "design study with German comparator arm; consider IQWIG early scientific advice.",
        examples=["IQWiG benefit assessment framework (AMNOG for drugs; NUB for devices)"],
        typically_missed=True,
    ),

    "has": Stakeholder(
        key="has",
        name="HAS (Haute Autorite de Sante, France)",
        category="hta",
        role="Evaluates medical devices for reimbursement under LPPR (Liste des Produits et Prestations Remboursables).",
        interests=["Service Attendu (SA) — clinical benefit", "Amelioration du Service Attendu (ASA) — added benefit",
                   "French clinical trial data preferred"],
        influence="medium",
        engagement_strategy="Early scientific advice from HAS Commission Nationale d'Evaluation; "
                            "target French clinical sites for evidence generation.",
        examples=["HAS LPPR evaluation for advanced wound care dressings"],
        typically_missed=True,
    ),

    "eba": Stakeholder(
        key="eba",
        name="EMA / National Competent Authorities (EU)",
        category="regulator",
        role="Regulatory approval for ATMPs (EMA centralised) and medical devices (national CAs enforce MDR).",
        interests=["Safety and efficacy data", "GMP compliance", "Benefit-risk balance",
                   "Post-market surveillance plans"],
        influence="high",
        engagement_strategy="EMA Scientific Advice pre-submission; PRIME designation for ATMPs; "
                            "engage CAT early for ATMP classification.",
        examples=["EMA CHMP (drugs/ATMPs)", "EMA CAT (advanced therapies)", "MHRA (UK post-Brexit)"],
    ),

    "fda": Stakeholder(
        key="fda",
        name="FDA (CDRH / CBER / CDER)",
        category="regulator",
        role="US regulatory clearance/approval for medical devices (CDRH), biologics (CBER), and drugs (CDER).",
        interests=["Substantial equivalence (510k) or safety+efficacy (PMA/BLA)", "GMP manufacturing",
                   "Post-approval study commitments"],
        influence="high",
        engagement_strategy="Q-Sub / Pre-Sub meetings; IDE application for pivotal trials; "
                            "Breakthrough Device Designation for innovative technologies.",
        examples=["FDA CDRH Q-Sub programme", "FDA Breakthrough Device Designation"],
    ),

    # ── Patient stakeholders ───────────────────────────────────────────────────

    "patients": Stakeholder(
        key="patients",
        name="Patients / Patient Advocacy Groups",
        category="patient",
        role="End users of biomaterial devices; increasingly influential in HTA and regulatory processes.",
        interests=["Functional outcomes (mobility, pain, quality of life)",
                   "Minimally invasive procedures", "Durable outcomes avoiding revision surgery",
                   "Access and affordability"],
        influence="medium",
        engagement_strategy="Patient advisory panels, PROMs in clinical trials, "
                            "disease foundation partnerships (e.g. Versus Arthritis), "
                            "patient-reported endpoints in HTA submissions.",
        examples=["Versus Arthritis (UK)", "National Osteoporosis Foundation (US)",
                  "Diabetic foot patient groups", "Spinal Cord Injury charities"],
    ),

    # ── Industry stakeholders ─────────────────────────────────────────────────

    "strategic_partners": Stakeholder(
        key="strategic_partners",
        name="Strategic Industry Partners / Potential Acquirers",
        category="industry",
        role="Large medtech / pharma companies seeking to in-license, acquire, or co-develop novel biomaterials.",
        interests=["Defensible IP portfolio", "Phase II+ clinical data de-risking",
                   "Manufacturing scalability", "Regulatory pathway clarity",
                   "Market size and growth (>$1B TAM preferred for major acquirers)"],
        influence="high",
        engagement_strategy="Business development meetings at medtech conferences (EUROMEDTECH, AdvaMed, DeviceTalks), "
                            "targeted outreach to M&A teams, licensing deal structure.",
        examples=["Stryker", "Medtronic", "J&J MedTech", "Smith+Nephew", "Zimmer Biomet",
                  "Collagen Matrix", "Geistlich"],
    ),

    "cdmos": Stakeholder(
        key="cdmos",
        name="CDMOs / Contract Manufacturers",
        category="industry",
        role="Manufacturing partners for scale-up from prototype to GMP production.",
        interests=["Long-term supply agreements", "Technology transfer clarity",
                   "IP non-compete agreements", "Volume and revenue visibility"],
        influence="medium",
        engagement_strategy="Early CDMO engagement (design for manufacturability), "
                            "manufacturing feasibility studies, quality agreements.",
        examples=["Evonik (polymers)", "Collagen Matrix (collagen)", "Lonza (ATMPs)",
                  "Wuxi Biologics (biologics)", "Stevanato (medical packaging)"],
        typically_missed=True,
    ),

    "investors": Stakeholder(
        key="investors",
        name="Venture Capital / Impact Investors",
        category="investor",
        role="Provide early-stage and growth capital; expect milestone-driven valuation inflection.",
        interests=["Clear regulatory pathway and timeline to revenue",
                   "Strong IP (composition of matter > method)",
                   "Experienced management team",
                   "Large and growing addressable market",
                   "Exit via trade sale or IPO in 7-10 year horizon"],
        influence="high",
        engagement_strategy="Tailored pitch with regulatory + clinical roadmap, competitive landscape, "
                            "market sizing, and IP summary. Target medtech-focused VCs.",
        examples=["Forbion", "Andera Partners (Edmond de Rothschild)", "M Ventures (Merck)",
                  "LifeSci VC", "Versant Ventures", "Wellcome Leap", "EIC Accelerator (EU)"],
    ),

    "kols": Stakeholder(
        key="kols",
        name="Key Opinion Leaders (KOLs) / Academic Collaborators",
        category="clinical",
        role="Scientific credibility builders; run investigator-initiated studies, present at conferences, generate publications.",
        interests=["Scientific novelty", "Research funding and equipment access",
                   "Publication opportunities and authorship", "Grant co-applications"],
        influence="high",
        engagement_strategy="Research collaboration agreements, sponsored investigator grants, "
                            "co-authorship on pivotal publications, scientific advisory board membership.",
        examples=["UMC Utrecht biofabrication group (Malda, Levato)", "AO Research Institute Davos",
                  "Harvard Wyss Institute", "University College London (UCL) IOTA"],
    ),
}


def get_stakeholders_by_type(category: str) -> List[Stakeholder]:
    return [s for s in ALL_STAKEHOLDERS.values() if s.category == category]


def get_commonly_missed() -> List[Stakeholder]:
    return [s for s in ALL_STAKEHOLDERS.values() if s.typically_missed]


def get_high_influence() -> List[Stakeholder]:
    return [s for s in ALL_STAKEHOLDERS.values() if s.influence == "high"]


def get_stakeholder(key: str) -> Optional[Stakeholder]:
    return ALL_STAKEHOLDERS.get(key)
