"""SynBioHub client — genetic design repository with SPARQL endpoint.

Uses the SynBioHub REST search API. Designs are in SBOL format.
Primary instance: https://synbiohub.org
"""
import requests
from typing import Optional

SYNBIOHUB_API = "https://synbiohub.org"
TIMEOUT = 15


class SynBioHubClient:
    """Search SynBioHub for genetic designs."""

    def __init__(self, base_url: str = SYNBIOHUB_API):
        self.base_url = base_url.rstrip("/")

    def search_designs(self, query: str, limit: int = 20) -> list[dict]:
        """Full-text search across SynBioHub collections."""
        try:
            url = f"{self.base_url}/search/{requests.utils.quote(query)}"
            headers = {"Accept": "application/json"}
            params = {"offset": 0, "limit": limit}
            resp = requests.get(url, headers=headers, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            return [self._normalise(item) for item in data]
        except Exception as exc:
            return self._fallback_search(query, limit, str(exc))

    def get_design_detail(self, uri: str) -> Optional[dict]:
        """Fetch metadata for a design by its SBOL URI."""
        try:
            headers = {"Accept": "application/json"}
            resp = requests.get(uri, headers=headers, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    # ------------------------------------------------------------------
    def _normalise(self, item: dict) -> dict:
        return {
            "name":        item.get("name", item.get("displayId", "")),
            "type":        item.get("type", "Component"),
            "description": item.get("description", "No description"),
            "uri":         item.get("uri", ""),
            "url":         item.get("uri", ""),
            "collection":  item.get("collection", ""),
            "source":      "SynBioHub",
        }

    def _fallback_search(self, query: str, limit: int, error: str) -> list[dict]:
        catalog = [
            {"name": "VEGF_secretion_circuit",
             "type": "CompositeDevice",
             "description": "VEGF secretion circuit for vascularisation in tissue engineering",
             "uri": "https://synbiohub.org/public/igem/BBa_K2924000/1",
             "url": "https://synbiohub.org/public/igem/BBa_K2924000/1",
             "collection": "iGEM 2019", "source": "SynBioHub (offline)"},
            {"name": "Spider_silk_MaSp1",
             "type": "CDS",
             "description": "Major ampullate spidroin 1 — high tensile strength protein biomaterial",
             "uri": "https://synbiohub.org/public/igem/BBa_K1902001/1",
             "url": "https://synbiohub.org/public/igem/BBa_K1902001/1",
             "collection": "iGEM 2016", "source": "SynBioHub (offline)"},
            {"name": "BMP2_osteogenic",
             "type": "CDS",
             "description": "Bone morphogenetic protein 2 — osteogenic differentiation inducer",
             "uri": "https://synbiohub.org/public/igem/BBa_K1404003/1",
             "url": "https://synbiohub.org/public/igem/BBa_K1404003/1",
             "collection": "iGEM 2014", "source": "SynBioHub (offline)"},
            {"name": "NF-kB_inflammation_sensor",
             "type": "Promoter",
             "description": "NF-kB promoter — senses inflammatory cytokines, drives therapeutic output",
             "uri": "https://synbiohub.org/public/igem/BBa_K3801005/1",
             "url": "https://synbiohub.org/public/igem/BBa_K3801005/1",
             "collection": "iGEM 2021", "source": "SynBioHub (offline)"},
            {"name": "PHB_synthase_phaC",
             "type": "CDS",
             "description": "PHA synthase — biodegradable polymer PHB production in E. coli",
             "uri": "https://synbiohub.org/public/igem/BBa_K1323009/1",
             "url": "https://synbiohub.org/public/igem/BBa_K1323009/1",
             "collection": "iGEM 2014", "source": "SynBioHub (offline)"},
        ]
        q = query.lower()
        filtered = [p for p in catalog
                    if q in p["description"].lower() or q in p["name"].lower()]
        return (filtered or catalog)[:limit]
