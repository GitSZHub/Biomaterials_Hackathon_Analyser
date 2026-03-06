"""Genetic editing strategy advisor.

Recommends CRISPR variant, base editing, prime editing, or classical
methods based on target gene, cell type, and editing goal.
"""

# ── Technology knowledge base ─────────────────────────────────────────────────
EDITING_TECH: dict[str, dict] = {
    "CRISPR-Cas9": {
        "mechanism": "Cas9 + sgRNA creates double-strand break (DSB); repaired by NHEJ (KO) or HDR (KI)",
        "best_for": ["knockout", "large insertion", "reporter knock-in"],
        "limitations": "DSB required; HDR efficiency low in non-dividing cells; off-target risk",
        "off_target": "Moderate — profile with NGS (GUIDE-seq or DISCOVER-seq)",
        "cell_breadth": "Very broad",
        "delivery": ["RNP Electroporation", "Lentiviral", "AAV", "Lipofection"],
        "tools": {
            "Guide design": "CRISPOR — https://crispor.tefor.net",
            "Off-target":   "Cas-OFFinder — http://www.rgenome.net/cas-offinder/",
            "Plasmids":     "Addgene — https://www.addgene.org/search/catalog/plasmids/?q=SpCas9",
        },
    },
    "Cas12a (Cpf1)": {
        "mechanism": "Cas12a + crRNA; staggered DSB; preferred for A/T-rich regions",
        "best_for": ["AT-rich target sites", "multiplex editing", "staggered cut applications"],
        "limitations": "Smaller validated dataset vs Cas9; needs TTTN PAM",
        "off_target": "Lower than Cas9 in several studies",
        "cell_breadth": "Broad",
        "delivery": ["RNP Electroporation", "AAV"],
        "tools": {
            "Guide design": "CRISPOR — https://crispor.tefor.net",
            "Plasmids":     "Addgene — https://www.addgene.org/search/catalog/plasmids/?q=Cpf1",
        },
    },
    "Base Editor (CBE / ABE)": {
        "mechanism": "dCas9-deaminase fusion; C->T (CBE) or A->G (ABE) single-base change without DSB",
        "best_for": ["correcting known point mutations", "introducing stop codons", "no DSB needed"],
        "limitations": "Only C->T or A->G changes; bystander edits possible; ~4-8 nt editing window",
        "off_target": "Low DSB-mediated; RNA off-targets possible with some versions",
        "cell_breadth": "Broad — works in non-dividing cells",
        "delivery": ["RNP Electroporation", "AAV (small BE variants)", "LNP (mRNA delivery)"],
        "tools": {
            "Guide design": "BE-Designer — http://www.rgenome.net/be-designer/",
            "Plasmids":     "Addgene — https://www.addgene.org/search/catalog/plasmids/?q=base+editor",
        },
    },
    "Prime Editor (PE3 / PE3b)": {
        "mechanism": "Cas9 nickase + RT fusion + pegRNA; writes new sequence directly via reverse transcription",
        "best_for": ["precise small insertions", "all 12 base substitutions", "no donor template"],
        "limitations": "Lower efficiency than Cas9 KO; pegRNA design complex; large construct",
        "off_target": "Low (nick-based mechanism)",
        "cell_breadth": "Good — works in non-dividing cells",
        "delivery": ["Electroporation (plasmid or mRNA)", "LNP"],
        "tools": {
            "Guide design": "PrimeDesign — https://primedesign.wyss.harvard.edu",
            "Plasmids":     "Addgene — https://www.addgene.org/search/catalog/plasmids/?q=prime+editor",
        },
    },
    "CRISPRi (dCas9-KRAB)": {
        "mechanism": "Catalytically dead Cas9 fused to KRAB repressor; transcriptional silencing without editing",
        "best_for": ["testing gene function before permanent edit", "tunable repression", "essential genes"],
        "limitations": "Reversible only while dCas9 expressed; requires stable expression",
        "off_target": "Off-target silencing possible at high expression",
        "cell_breadth": "Broad",
        "delivery": ["Lentiviral (stable)", "Lipofection", "AAV"],
        "tools": {
            "Guide design": "CRISPOR — https://crispor.tefor.net",
            "Plasmids":     "Addgene — https://www.addgene.org/search/catalog/plasmids/?q=dCas9-KRAB",
        },
    },
    "CRISPRa (dCas9-VPR)": {
        "mechanism": "dCas9 fused to VPR transcriptional activator; gene activation without editing",
        "best_for": ["endogenous gene activation", "overexpression from native promoter", "cell reprogramming"],
        "limitations": "Requires stable expression; context-dependent efficiency",
        "off_target": "Off-target activation possible",
        "cell_breadth": "Broad",
        "delivery": ["Lentiviral (stable)", "Lipofection", "AAV"],
        "tools": {
            "Guide design": "CRISPOR — https://crispor.tefor.net",
            "Plasmids":     "Addgene — https://www.addgene.org/search/catalog/plasmids/?q=dCas9-VPR",
        },
    },
    "Homologous Recombination (Yeast)": {
        "mechanism": "50 bp homology arms sufficient for precise genomic replacement in S. cerevisiae",
        "best_for": ["yeast genome editing", "seamless reporter integration", "metabolic engineering"],
        "limitations": "Yeast only (very inefficient in mammalian cells without Cas9)",
        "off_target": "Very low — HR is precise",
        "cell_breadth": "Yeast only",
        "delivery": ["Yeast Transformation"],
        "tools": {
            "Design": "Saccharomyces Genome Database (SGD) — https://www.yeastgenome.org",
            "Protocol": "Gietz & Schiestl LiAc/PEG transformation",
        },
    },
    "Cre/lox": {
        "mechanism": "Cre recombinase removes DNA flanked by loxP sites; requires pre-floxed allele",
        "best_for": ["conditional knockout from existing floxed mouse lines", "precise excision"],
        "limitations": "Requires pre-existing floxed allele; check MGI database first",
        "off_target": "Very low for canonical loxP sites",
        "cell_breadth": "Good in mammalian cells; used in mouse genetics",
        "delivery": ["Lentiviral (Cre)", "AAV-Cre", "Adenoviral-Cre"],
        "tools": {
            "Check floxed lines": "MGI — https://www.informatics.jax.org",
            "Plasmids": "Addgene — https://www.addgene.org/search/catalog/plasmids/?q=Cre+recombinase",
        },
    },
}

# Goal -> recommended technologies (ordered by preference)
GOAL_MAP: dict[str, list[str]] = {
    "knockout":        ["CRISPR-Cas9", "Cas12a (Cpf1)", "CRISPRi (dCas9-KRAB)"],
    "knock-in":        ["CRISPR-Cas9", "Prime Editor (PE3 / PE3b)"],
    "activate":        ["CRISPRa (dCas9-VPR)"],
    "repress":         ["CRISPRi (dCas9-KRAB)"],
    "point mutation":  ["Base Editor (CBE / ABE)", "Prime Editor (PE3 / PE3b)"],
    "base edit":       ["Base Editor (CBE / ABE)"],
    "small insertion":  ["Prime Editor (PE3 / PE3b)", "CRISPR-Cas9"],
    "reporter":        ["CRISPR-Cas9", "Prime Editor (PE3 / PE3b)"],
    "conditional":     ["Cre/lox", "CRISPR-Cas9"],
    "yeast":           ["Homologous Recombination (Yeast)"],
}


class GeneticEditorAdvisor:
    """Recommend gene editing strategy based on goal and cell type."""

    def recommend(self, goal: str, cell_type: str = "", target_gene: str = "") -> list[dict]:
        """Return ordered list of editing strategies with rationale."""
        goal_lower = goal.lower()
        methods = []
        for key, techs in GOAL_MAP.items():
            if key in goal_lower:
                methods = techs
                break

        if not methods:
            methods = ["CRISPR-Cas9", "Base Editor (CBE / ABE)"]

        # Yeast override
        if "yeast" in cell_type.lower() or "cerevisiae" in cell_type.lower():
            methods = ["Homologous Recombination (Yeast)"] + methods

        results = []
        for method in methods:
            if method in EDITING_TECH:
                entry = dict(EDITING_TECH[method])
                entry["method"] = method
                entry["ensembl_url"] = (
                    f"https://www.ensembl.org/Multi/Search/Results?q={target_gene}"
                    if target_gene else ""
                )
                entry["addgene_url"] = entry.get("tools", {}).get("Plasmids", "")
                results.append(entry)

        return results

    def get_all_technologies(self) -> list[str]:
        return list(EDITING_TECH.keys())

    def get_technology_detail(self, method: str) -> dict:
        return EDITING_TECH.get(method, {})
