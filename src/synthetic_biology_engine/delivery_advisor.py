"""Delivery system advisor for genetic constructs and CRISPR reagents.

Recommends delivery method based on cell type and target tissue,
with regulatory credibility notes.
"""

# ── Delivery knowledge base ───────────────────────────────────────────────────
DELIVERY_KB: dict[str, dict] = {
    # Viral vectors
    "AAV": {
        "full_name": "Adeno-Associated Virus",
        "mechanism": "Single-stranded DNA, episomal (largely), serotype-dependent tropism",
        "payload_limit": "~4.7 kb",
        "integration_risk": "Very low (episomal, rare random integration)",
        "immunogenicity": "Low-moderate (pre-existing antibodies common in humans)",
        "clinical_status": "Approved products (Luxturna, Zolgensma, Hemgenix)",
        "cell_types": ["primary neurons", "RPE cells", "muscle cells", "hepatocytes",
                       "cardiomyocytes"],
        "serotype_guide": {
            "CNS": "AAV9, AAVrh10, AAV-PHP.eB",
            "Eye (RPE)": "AAV2, AAV5 (subretinal)",
            "Liver": "AAV8",
            "Muscle": "AAV6, AAV9",
        },
        "regulatory_path": "IND required; GMP manufacturing; clinical trial",
        "url": "https://www.addgene.org/viral-vectors/aav/",
    },
    "Lentiviral": {
        "full_name": "Lentiviral vector (HIV-1 derived, VSV-G pseudotyped)",
        "mechanism": "RNA virus — stable chromosomal integration",
        "payload_limit": "~8 kb",
        "integration_risk": "Moderate (semi-random integration; SIN vectors reduce risk)",
        "immunogenicity": "Moderate",
        "clinical_status": "Approved (CAR-T, gene therapies: Kymriah, Strimvelis)",
        "cell_types": ["T cells", "HSCs", "iPSC", "organoids", "primary hepatocytes"],
        "serotype_guide": {},
        "regulatory_path": "IND required; BSL-2 handling; GMP for clinical",
        "url": "https://www.addgene.org/viral-vectors/lentivirus/",
    },
    # Non-viral
    "LNP": {
        "full_name": "Lipid Nanoparticle",
        "mechanism": "Encapsulates mRNA or pDNA; endosomal escape delivers cargo to cytoplasm",
        "payload_limit": "No hard limit for mRNA; ~4-5 kb practical for pDNA",
        "integration_risk": "None (transient)",
        "immunogenicity": "Low-moderate; PEGylation reduces immune response",
        "clinical_status": "Approved (Onpattro, mRNA vaccines, siRNA therapies)",
        "cell_types": ["hepatocytes", "primary cells", "iPSC", "DCs", "muscle"],
        "serotype_guide": {},
        "regulatory_path": "No BSL requirements; favorable regulatory precedent from mRNA vaccines",
        "url": "https://www.addgene.org/guides/lnp/",
    },
    "RNP Electroporation": {
        "full_name": "Ribonucleoprotein electroporation (Cas9 protein + gRNA complex)",
        "mechanism": "Pre-formed protein-RNA complex delivered by electroporation; degrades after editing",
        "payload_limit": "N/A (protein complex)",
        "integration_risk": "None (protein degrades within 24-48 h)",
        "immunogenicity": "Very low",
        "clinical_status": "Now standard for clinical ex vivo CRISPR (CAR-T, HSC editing)",
        "cell_types": ["T cells", "HSCs", "NK cells", "primary cells", "iPSC"],
        "serotype_guide": {},
        "regulatory_path": "Preferred for clinical CRISPR; no viral manufacturing burden",
        "url": "https://www.idtdna.com/pages/products/crispr-genome-editing/alt-r-crispr-cas9-system",
    },
    "Lipofection": {
        "full_name": "Cationic lipid transfection (Lipofectamine 2000/3000)",
        "mechanism": "Cationic lipid-DNA complex; endosomal uptake",
        "payload_limit": "No hard limit",
        "integration_risk": "Low (transient unless stable selection)",
        "immunogenicity": "Moderate (lipid component)",
        "clinical_status": "Research use; not approved for in vivo clinical use",
        "cell_types": ["HEK293", "CHO", "COS-7", "many adherent cell lines"],
        "serotype_guide": {},
        "regulatory_path": "Research only; not for clinical delivery",
        "url": "https://www.thermofisher.com/order/catalog/product/11668019",
    },
    "Electroporation": {
        "full_name": "Nucleofection / electroporation (Lonza 4D, Bio-Rad)",
        "mechanism": "Electric pulse creates transient membrane pores; DNA/RNA enters",
        "payload_limit": "No hard limit",
        "integration_risk": "Low (transient unless stable selection or HDR)",
        "immunogenicity": "Low",
        "clinical_status": "Approved for ex vivo cell editing (CAR-T manufacturing)",
        "cell_types": ["T cells", "NK cells", "iPSC", "primary cells", "hard-to-transfect"],
        "serotype_guide": {},
        "regulatory_path": "Approved ex vivo; not suitable for in vivo",
        "url": "https://bioscience.lonza.com/lonza_bs/CH/en/Nucleofection-Technology",
    },
    "Yeast Transformation": {
        "full_name": "Lithium acetate / PEG / heat shock (S. cerevisiae)",
        "mechanism": "Chemical treatment permeabilises yeast cell wall; DNA enters by HR",
        "payload_limit": "No hard limit",
        "integration_risk": "High (intentional, HR-mediated genomic integration)",
        "immunogenicity": "N/A (in vitro production organism)",
        "clinical_status": "Industrial fermentation use; yeast not implanted",
        "cell_types": ["S. cerevisiae", "P. pastoris"],
        "serotype_guide": {},
        "regulatory_path": "GMO manufacturing regulations; product may be pharmaceutically relevant",
        "url": "https://www.addgene.org/protocols/yeast-transformation/",
    },
    "Heat shock (E. coli)": {
        "full_name": "Heat shock transformation (42°C, competent E. coli)",
        "mechanism": "Thermal stress creates transient membrane permeability",
        "payload_limit": "No hard limit",
        "integration_risk": "Low (plasmid episomal); High if genomic editing intended",
        "immunogenicity": "N/A (production organism)",
        "clinical_status": "Industrial use; E. coli not implanted",
        "cell_types": ["E. coli", "other bacteria"],
        "serotype_guide": {},
        "regulatory_path": "Contained use GMO; product (protein, polymer) may require drug approval",
        "url": "",
    },
}

# Cell type -> recommended delivery system
CELL_TYPE_MAP: dict[str, list[str]] = {
    "primary neurons":    ["AAV"],
    "RPE cells":          ["AAV"],
    "muscle cells":       ["AAV", "LNP"],
    "hepatocytes":        ["LNP", "AAV"],
    "T cells":            ["RNP Electroporation", "Lentiviral"],
    "NK cells":           ["RNP Electroporation", "Electroporation"],
    "HSCs":               ["RNP Electroporation", "Lentiviral"],
    "iPSC":               ["RNP Electroporation", "LNP", "Lentiviral"],
    "iPSC / Primary cells": ["RNP Electroporation", "LNP", "Lentiviral"],
    "organoids":          ["LNP", "Lentiviral"],
    "CHO cells":          ["Lipofection", "Electroporation"],
    "HEK293":             ["Lipofection", "Electroporation"],
    "E. coli":            ["Heat shock (E. coli)"],
    "S. cerevisiae":      ["Yeast Transformation"],
    "Pichia pastoris":    ["Yeast Transformation"],
}


class DeliveryAdvisor:
    """Recommend delivery systems for a given cell type and editing goal."""

    def recommend(self, cell_type: str, goal: str = "") -> list[dict]:
        """Return ordered list of recommended delivery systems with rationale."""
        recommendations = []
        ct = cell_type.strip().lower()

        # Lookup by cell type
        for known_ct, methods in CELL_TYPE_MAP.items():
            if known_ct.lower() in ct or ct in known_ct.lower():
                for m in methods:
                    if m in DELIVERY_KB:
                        entry = dict(DELIVERY_KB[m])
                        entry["method"] = m
                        entry["match_reason"] = f"Recommended for {known_ct}"
                        recommendations.append(entry)
                break

        # Fallback
        if not recommendations:
            for method in ["LNP", "Electroporation"]:
                entry = dict(DELIVERY_KB[method])
                entry["method"] = method
                entry["match_reason"] = "General fallback recommendation"
                recommendations.append(entry)

        return recommendations

    def get_all_methods(self) -> list[str]:
        return list(DELIVERY_KB.keys())

    def get_method_detail(self, method: str) -> dict:
        return DELIVERY_KB.get(method, {})
