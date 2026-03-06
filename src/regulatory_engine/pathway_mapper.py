"""
Regulatory Pathway Mapper
=========================
Given a DeviceClassification, returns a structured regulatory pathway:
milestones, timelines, lead agencies, key submissions, and cost estimates.

All four architectural scenarios are covered (A/B/C/D).
Data is curated from FDA and EMA public guidance documents.
No external API calls -- pure static knowledge base.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .device_classifier import DeviceClassification


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class RegulatoryMilestone:
    phase:            str    # e.g. "Pre-submission", "Clinical Trial"
    description:      str
    duration_months:  str    # e.g. "3-6" or "12-24"
    cost_estimate:    str    # rough USD range, or "variable"
    fda_relevant:     bool = True
    eu_relevant:      bool = True
    key_docs:         List[str] = field(default_factory=list)


@dataclass
class RegulatoryPathway:
    scenario:                str
    device_class:            str
    pathway_name:            str
    lead_fda_center:         str
    lead_eu_body:            str
    total_duration_estimate: str      # typical total timeline
    total_cost_estimate:     str
    milestones:              List[RegulatoryMilestone] = field(default_factory=list)
    key_submissions:         List[str] = field(default_factory=list)
    key_risks:               List[str] = field(default_factory=list)
    notes:                   str = ""


# ── Pathway mapper ─────────────────────────────────────────────────────────────

class PathwayMapper:
    """
    Map a DeviceClassification to a full regulatory pathway with milestones.

    Usage:
        from regulatory_engine.device_classifier import DeviceClassifier
        from regulatory_engine.pathway_mapper import PathwayMapper

        clf = DeviceClassifier()
        dc  = clf.classify("implant", "permanent", has_drug=False)
        pw  = PathwayMapper().map(dc)
        for m in pw.milestones:
            print(m.phase, m.duration_months, "months")
    """

    def map(self, classification: DeviceClassification) -> RegulatoryPathway:
        s = classification.scenario
        if s == "A":
            return self._pathway_a(classification)
        if s == "B":
            return self._pathway_b(classification)
        if s == "C":
            return self._pathway_c(classification)
        if s == "D":
            return self._pathway_d(classification)
        raise ValueError(f"Unknown scenario: {s}")

    # ── Scenario A ─────────────────────────────────────────────────────────────

    def _pathway_a(self, dc: DeviceClassification) -> RegulatoryPathway:
        fda = dc.fda_class

        if fda == "Class I":
            milestones = [
                RegulatoryMilestone(
                    "Establishment Registration", "FDA facility registration + device listing",
                    "1-2", "$0-5k", key_docs=["FDA 510(k) exemption check", "Device listing form 2892"],
                ),
                RegulatoryMilestone(
                    "Technical File (EU)", "EU MDR Class I technical documentation",
                    "3-6", "$20-50k", fda_relevant=False,
                    key_docs=["EU MDR Annex II technical file", "Declaration of Conformity"],
                ),
                RegulatoryMilestone(
                    "Market Launch", "Commercial distribution",
                    "0", "$0", key_docs=[],
                ),
            ]
            return RegulatoryPathway(
                scenario="A", device_class=fda,
                pathway_name="Class I — General Controls / 510(k) Exempt",
                lead_fda_center="CDRH", lead_eu_body="Notified Body (Class I — self-cert)",
                total_duration_estimate="4-8 months",
                total_cost_estimate="$30-80k",
                milestones=milestones,
                key_submissions=["FDA Device Listing", "EU Declaration of Conformity"],
                key_risks=["Misclassification to Class II", "Predicate device identification"],
            )

        if fda == "Class II":
            milestones = [
                RegulatoryMilestone(
                    "Pre-submission (Q-Sub)", "Pre-Sub meeting with FDA to align on predicate + testing",
                    "3-4", "$10-30k", eu_relevant=False,
                    key_docs=["Q-Sub request", "Draft 510(k) outline"],
                ),
                RegulatoryMilestone(
                    "Biocompatibility Testing", "ISO 10993 test programme",
                    "3-9", "$50-200k",
                    key_docs=["ISO 10993-1 risk-based plan", "Test reports"],
                ),
                RegulatoryMilestone(
                    "510(k) Preparation", "Compile substantial equivalence submission",
                    "3-6", "$50-150k",
                    key_docs=["510(k) summary", "Performance testing", "Labelling"],
                ),
                RegulatoryMilestone(
                    "FDA 510(k) Review", "FDA review cycle (target: 90 days)",
                    "3-6", "$20k (FDA fee)", eu_relevant=False,
                    key_docs=["510(k) Additional Information response"],
                ),
                RegulatoryMilestone(
                    "EU Notified Body Review", "MDR Class IIa/IIb technical file review",
                    "6-12", "$80-200k", fda_relevant=False,
                    key_docs=["EU Technical File", "Clinical Evaluation Report (CER)"],
                ),
            ]
            return RegulatoryPathway(
                scenario="A", device_class=fda,
                pathway_name="Class II — 510(k) Premarket Notification",
                lead_fda_center="CDRH", lead_eu_body="Notified Body",
                total_duration_estimate="12-24 months",
                total_cost_estimate="$200-600k",
                milestones=milestones,
                key_submissions=["FDA 510(k)", "EU MDR Technical File + CER"],
                key_risks=[
                    "No suitable predicate → De Novo pathway",
                    "Clinical data required if insufficient bench data",
                    "Post-market surveillance plan required (EU)",
                ],
            )

        # Class III
        milestones = [
            RegulatoryMilestone(
                "Pre-IDE / Pre-Sub", "Pre-IDE meeting with FDA to align on clinical trial design",
                "3-6", "$20-50k", eu_relevant=False,
                key_docs=["Pre-IDE request", "Proposed clinical protocol"],
            ),
            RegulatoryMilestone(
                "Biocompatibility & Preclinical", "Full ISO 10993 + animal implantation studies",
                "12-24", "$500k-2M",
                key_docs=["ISO 10993 test battery", "GLP animal study reports", "Bench testing"],
            ),
            RegulatoryMilestone(
                "IDE — Investigational Device Exemption", "FDA approval to conduct clinical trial",
                "3-6", "$50-100k", eu_relevant=False,
                key_docs=["IDE application", "Investigational plan", "IRB approval"],
            ),
            RegulatoryMilestone(
                "Clinical Trial", "Pivotal study (typically 100-500 subjects, 1-3 year follow-up)",
                "24-60", "$2-20M",
                key_docs=["Clinical protocol", "CRF", "Interim safety reports"],
            ),
            RegulatoryMilestone(
                "PMA Submission (FDA)", "Premarket Approval submission",
                "6-12", "$200-500k",
                key_docs=["PMA modules (device, non-clinical, clinical, manufacturing)"],
            ),
            RegulatoryMilestone(
                "EU MDR Class III Review", "Notified Body + competent authority scrutiny",
                "12-18", "$300-600k", fda_relevant=False,
                key_docs=["Technical File", "Clinical Evaluation Report", "SSCP"],
            ),
        ]
        return RegulatoryPathway(
            scenario="A", device_class=fda,
            pathway_name="Class III — PMA (Premarket Approval)",
            lead_fda_center="CDRH", lead_eu_body="Notified Body + Competent Authority",
            total_duration_estimate="5-10 years",
            total_cost_estimate="$5-50M",
            milestones=milestones,
            key_submissions=["IDE", "FDA PMA", "EU MDR Technical File + CER"],
            key_risks=[
                "PMA Advisory Panel review may be required",
                "Post-approval studies typically mandated",
                "Clinical trial failure can reset timeline",
            ],
        )

    # ── Scenario B ─────────────────────────────────────────────────────────────

    def _pathway_b(self, dc: DeviceClassification) -> RegulatoryPathway:
        milestones = [
            RegulatoryMilestone(
                "Combination Product Designation",
                "FDA Request for Designation (RFD) to determine lead center (CDRH vs CDER/CBER)",
                "3-6", "$0", eu_relevant=False,
                key_docs=["RFD submission", "Mode of action analysis"],
            ),
            RegulatoryMilestone(
                "Pre-Submission Meetings",
                "Separate meetings with lead center + consult center to align on package requirements",
                "6-12", "$30-80k",
                key_docs=["Q-Sub (FDA)", "Scientific Advice (EMA)"],
            ),
            RegulatoryMilestone(
                "Biocompatibility + ADMET Testing",
                "Full ISO 10993 + drug ADMET characterisation + extractables/leachables",
                "12-18", "$500k-1.5M",
                key_docs=["ISO 10993 plan", "E&L study (ICH Q3C)", "ADMET package"],
            ),
            RegulatoryMilestone(
                "Drug Component IND / IMPD",
                "IND (FDA) or IMPD (EU) for clinical use of drug component",
                "3-6", "$50-100k",
                key_docs=["IND application", "Phase I safety data", "CMC section"],
            ),
            RegulatoryMilestone(
                "Clinical Trials (Phase I-III)",
                "Clinical programme covering safety, PK/PD of drug release, and efficacy",
                "36-84", "$10-100M",
                key_docs=["IDE/IND", "Pivotal trial protocol", "PK/PD modelling"],
            ),
            RegulatoryMilestone(
                "PMA / NDA + CHMP Consultation (EU)",
                "PMA submission (FDA) + EU CHMP consultation on drug component",
                "12-18", "$500k-2M",
                key_docs=["PMA (FDA)", "Technical File (EU)", "CHMP opinion"],
            ),
        ]
        return RegulatoryPathway(
            scenario="B", device_class="Class III / Combination",
            pathway_name="Drug-Device Combination Product — PMA + IND/NDA",
            lead_fda_center="CDRH (if device primary) or CDER (if drug primary)",
            lead_eu_body="Notified Body + EMA CHMP consultation",
            total_duration_estimate="8-15 years",
            total_cost_estimate="$20-200M",
            milestones=milestones,
            key_submissions=["RFD (FDA)", "IND/IDE", "PMA + NDA", "EU Technical File + CHMP consultation"],
            key_risks=[
                "Jurisdiction dispute between CDRH and CDER",
                "Drug PK in vivo may differ from in vitro release model",
                "Extractables/leachables from scaffold may affect drug stability",
                "Two separate GMP regimes: device manufacturing + pharmaceutical manufacturing",
            ],
            notes=(
                "EU: Article 1(8) of MDR 2017/745 requires mandatory CHMP consultation "
                "when a drug is integral to the device. The notified body must request this."
            ),
        )

    # ── Scenario C ─────────────────────────────────────────────────────────────

    def _pathway_c(self, dc: DeviceClassification) -> RegulatoryPathway:
        milestones = [
            RegulatoryMilestone(
                "ATMP Classification",
                "EMA CAT (Committee for Advanced Therapies) classification opinion; "
                "FDA BLA pre-submission to CBER",
                "3-6", "$0-30k",
                key_docs=["CAT classification request (EU)", "CBER pre-BLA meeting (FDA)"],
            ),
            RegulatoryMilestone(
                "Scientific Advice / Pre-BLA",
                "EMA Scientific Advice + PRIME designation if applicable; FDA pre-BLA meeting",
                "6-12", "$50-150k",
                key_docs=["EMA Scientific Advice", "PRIME application", "Pre-BLA meeting package"],
            ),
            RegulatoryMilestone(
                "Cell Bank & Process Development",
                "Master cell bank + working cell bank establishment; manufacturing process lock",
                "12-24", "$1-5M",
                key_docs=["MCB/WCB characterisation", "GMP process validation", "ICH Q5A-D"],
            ),
            RegulatoryMilestone(
                "IND / CTA Filing",
                "IND (FDA) or CTA (EU) to begin first-in-human Phase I",
                "3-6", "$100-300k",
                key_docs=["IND/CTA", "Phase I protocol", "IMPD", "GMP certificate"],
            ),
            RegulatoryMilestone(
                "Phase I — Safety",
                "First-in-human: small cohort, dose escalation, safety + engraftment",
                "24-36", "$5-20M",
                key_docs=["DSMB reports", "SUSAR reporting", "Phase I final report"],
            ),
            RegulatoryMilestone(
                "Phase II — Proof of Concept",
                "Expanded safety + preliminary efficacy signals",
                "24-48", "$20-80M",
                key_docs=["Phase II protocol", "Surrogate endpoint justification"],
            ),
            RegulatoryMilestone(
                "Phase III — Pivotal",
                "Randomised controlled trial vs SoC; primary efficacy endpoint",
                "36-72", "$50-300M",
                key_docs=["Phase III protocol", "Statistical analysis plan", "DMC"],
            ),
            RegulatoryMilestone(
                "BLA / MAA Submission",
                "BLA (FDA CBER) + MAA (EMA) submission",
                "6-12", "$1-5M",
                key_docs=["BLA/MAA modules", "Risk Management Plan", "REMS if required"],
            ),
        ]
        return RegulatoryPathway(
            scenario="C", device_class="ATMP / BLA",
            pathway_name="ATMP — Tissue Engineered Product (EU) / BLA (FDA)",
            lead_fda_center="CBER (Center for Biologics Evaluation and Research)",
            lead_eu_body="EMA CAT + CHMP",
            total_duration_estimate="12-20 years",
            total_cost_estimate="$100M-1B+",
            milestones=milestones,
            key_submissions=[
                "CAT classification opinion (EU)", "EMA PRIME designation",
                "IND (FDA) / CTA (EU)", "BLA (FDA) / MAA (EMA)",
            ],
            key_risks=[
                "Long-term engraftment and safety data (5-15 years follow-up typical)",
                "Manufacturing consistency at scale for cell therapies",
                "Hospital exemption may allow academic studies but not commercialisation",
                "Immunogenicity of allogeneic cells",
                "Tumorigenicity risk for iPSC-derived products",
            ],
            notes=(
                "Hospital Exemption (EU Art. 28, Reg. 1394/2007) allows unlicensed ATMP "
                "use under named-patient basis at academic centres — useful for early evidence."
            ),
        )

    # ── Scenario D ─────────────────────────────────────────────────────────────

    def _pathway_d(self, dc: DeviceClassification) -> RegulatoryPathway:
        milestones = [
            RegulatoryMilestone(
                "Contained Use Risk Assessment",
                "Class 1/2/3 contained use risk assessment for GMO manufacturing facility",
                "3-6", "$20-80k",
                key_docs=["EU Dir 2009/41 notification", "Risk assessment report"],
            ),
            RegulatoryMilestone(
                "Competent Authority Notification",
                "Notify national CA for contained use of GMO (EU) or apply to EPA/USDA (FDA)",
                "6-12", "$10-50k",
                key_docs=["Contained use notification", "OGTR consent (Australia)"],
            ),
            RegulatoryMilestone(
                "Material Characterisation",
                "Demonstrate final product is free of viable GMO / recombinant DNA",
                "6-12", "$100-300k",
                key_docs=["Analytical characterisation", "Clearance study for GM-derived components"],
            ),
            RegulatoryMilestone(
                "Standard Device Pathway",
                f"Final product follows {dc.fda_class} device pathway (Scenario A)",
                "varies", "varies",
                key_docs=["510(k) or PMA as appropriate"],
            ),
        ]
        return RegulatoryPathway(
            scenario="D", device_class=dc.fda_class,
            pathway_name=f"GMO Manufacturing + {dc.fda_class} Device Pathway",
            lead_fda_center="CDRH (device) + EPA/USDA (GMO manufacturing)",
            lead_eu_body="National Competent Authority (contained use) + Notified Body (device)",
            total_duration_estimate="2-4 years additional to standard device timeline",
            total_cost_estimate="$500k-5M additional to device costs",
            milestones=milestones,
            key_submissions=[
                "EU Directive 2009/41 notification",
                "Standard device submission (510(k)/PMA)",
            ],
            key_risks=[
                "Public perception of GMO-derived implants",
                "Analytical methods must demonstrate no viable GMO in final product",
                "Traceability requirements for GM-derived material throughout supply chain",
            ],
            notes=(
                "The final device is classified and regulated as a standard medical device "
                "(Scenario A) if the product contains no living GMO cells. "
                "The GMO manufacturing step is regulated separately under contained use legislation."
            ),
        )
