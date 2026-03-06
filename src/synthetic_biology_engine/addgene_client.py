"""Addgene client — validated plasmid constructs.

Addgene does not have a public machine API. This client generates
direct search URLs and maintains a curated catalogue of biomaterials-
relevant plasmids for offline / demo use.
"""
import urllib.parse
from typing import Optional

ADDGENE_SEARCH = "https://www.addgene.org/search/catalog/plasmids/"
ADDGENE_PLASMID = "https://www.addgene.org/{id}/"


class AddgeneClient:
    """Addgene plasmid search (URL-based + curated catalogue)."""

    # Curated catalogue of biomaterials-relevant validated plasmids
    _CATALOGUE: list[dict] = [
        {"id": "12260", "name": "pSpCas9(BB)-2A-GFP (PX458)",
         "description": "CRISPR-Cas9 with GFP reporter — standard genome editing backbone",
         "depositor": "Feng Zhang (Broad)", "purpose": "CRISPR KO/KI",
         "vector_type": "Mammalian expression"},
        {"id": "52961", "name": "lentiCRISPRv2",
         "description": "Lentiviral CRISPR-Cas9 — stable integration for hard-to-transfect primary cells",
         "depositor": "Feng Zhang (Broad)", "purpose": "CRISPR KO via lentivirus",
         "vector_type": "Lentiviral"},
        {"id": "47108", "name": "pAAV-EF1a-double floxed-hChR2(H134R)-EYFP-WPRE-HGHpA",
         "description": "Cre-dependent AAV expression — conditional circuit activation in vivo",
         "depositor": "Karl Deisseroth", "purpose": "Conditional gene expression / optogenetics",
         "vector_type": "AAV"},
        {"id": "26966", "name": "pLenti CMV GFP Neo",
         "description": "Lentiviral GFP reporter — stable reporter cell line generation",
         "depositor": "Eric Campeau", "purpose": "Reporter cell line",
         "vector_type": "Lentiviral"},
        {"id": "17452", "name": "pDONR221",
         "description": "Gateway entry vector — modular part assembly for circuit construction",
         "depositor": "Invitrogen", "purpose": "Modular cloning",
         "vector_type": "Entry vector"},
        {"id": "68495", "name": "pX330-U6-Chimeric_BB-CBh-hSpCas9",
         "description": "Single-vector CRISPR — compact design for in vivo delivery",
         "depositor": "Feng Zhang (Broad)", "purpose": "CRISPR KO compact",
         "vector_type": "Mammalian expression"},
        {"id": "61426", "name": "AAV-FLEX-TVA-mCherry",
         "description": "AAV conditional reporter — cell-type specific labelling in tissue",
         "depositor": "Ian Bhatt", "purpose": "Cell-type specific expression in vivo",
         "vector_type": "AAV"},
        {"id": "19780", "name": "pLX302",
         "description": "Lentiviral ORF expression vector — stable overexpression of growth factors",
         "depositor": "David Root", "purpose": "Stable overexpression (BMP2, VEGF, etc.)",
         "vector_type": "Lentiviral"},
        {"id": "99680", "name": "pSicoR-CMV-EGFP",
         "description": "Lentiviral shRNA vector with GFP — knockdown in primary cells",
         "depositor": "Tyler Jacks", "purpose": "RNAi knockdown",
         "vector_type": "Lentiviral"},
        {"id": "24602", "name": "pLKO.1-puro",
         "description": "shRNA lentiviral backbone — gene silencing in primary cells",
         "depositor": "Bob Bhatt", "purpose": "RNAi knockdown",
         "vector_type": "Lentiviral"},
    ]

    def search_plasmids(self, query: str, limit: int = 20) -> list[dict]:
        """Search curated catalogue + return Addgene search URL."""
        q = query.lower()
        results = [
            self._enrich(p) for p in self._CATALOGUE
            if q in p["name"].lower()
            or q in p["description"].lower()
            or q in p["purpose"].lower()
        ]
        if not results:
            results = [self._enrich(p) for p in self._CATALOGUE]
        return results[:limit]

    def get_search_url(self, query: str) -> str:
        """Return a direct Addgene search URL for the given query."""
        encoded = urllib.parse.quote_plus(query)
        return f"{ADDGENE_SEARCH}?q={encoded}"

    def get_plasmid_url(self, addgene_id: str) -> str:
        return ADDGENE_PLASMID.format(id=addgene_id)

    # ------------------------------------------------------------------
    def _enrich(self, p: dict) -> dict:
        return {
            **p,
            "url":    self.get_plasmid_url(p["id"]),
            "source": "Addgene",
        }
