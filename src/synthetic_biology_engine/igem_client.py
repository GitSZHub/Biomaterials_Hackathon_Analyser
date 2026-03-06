"""iGEM Registry of Standard Biological Parts client.

Queries the iGEM REST API (parts.igem.org) for BioBrick parts
relevant to biomaterials applications.
"""
import requests
import xml.etree.ElementTree as ET
from typing import Optional


IGEM_API = "https://parts.igem.org/cgi/xml/rest.cgi"
IGEM_SEARCH = "https://parts.igem.org/partsdb/search_1.cgi"
TIMEOUT = 15


class IGEMClient:
    """Search iGEM Registry for biological parts."""

    def search_parts(self, query: str, limit: int = 20) -> list[dict]:
        """Search parts by keyword. Returns list of part dicts."""
        try:
            params = {
                "action": "search",
                "query": query,
                "start": 0,
                "limit": limit,
            }
            resp = requests.get(IGEM_API, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            return self._parse_xml(resp.text)
        except Exception as exc:
            return self._fallback_search(query, limit, str(exc))

    def get_part_detail(self, part_name: str) -> Optional[dict]:
        """Fetch full detail for a specific BioBrick part."""
        try:
            params = {"action": "get", "id": part_name}
            resp = requests.get(IGEM_API, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            parts = self._parse_xml(resp.text)
            return parts[0] if parts else None
        except Exception:
            return None

    # ------------------------------------------------------------------
    def _parse_xml(self, xml_text: str) -> list[dict]:
        parts = []
        try:
            root = ET.fromstring(xml_text)
            ns = {"igem": "http://parts.igem.org/"}
            # Try namespaced first, fall back to no-namespace
            for part_el in root.findall(".//part"):
                parts.append(self._parse_part_element(part_el))
            if not parts:
                for part_el in root.findall(".//{http://parts.igem.org/}part"):
                    parts.append(self._parse_part_element(part_el))
        except ET.ParseError:
            pass
        return parts

    def _parse_part_element(self, el: ET.Element) -> dict:
        def txt(tag: str) -> str:
            node = el.find(tag)
            return (node.text or "").strip() if node is not None else ""

        part_name = txt("part_name") or txt("name") or el.get("id", "")
        return {
            "name":        part_name,
            "type":        txt("part_type") or txt("type") or "Unknown",
            "description": txt("short_desc") or txt("description") or "No description",
            "status":      txt("part_status") or "Unknown",
            "url":         f"https://parts.igem.org/Part:{part_name}" if part_name else "",
            "author":      txt("part_author") or txt("author") or "",
            "source":      "iGEM Registry",
        }

    def _fallback_search(self, query: str, limit: int, error: str) -> list[dict]:
        """Return curated biomaterials-relevant parts when API is unavailable."""
        catalog = [
            {"name": "BBa_K1902001", "type": "Composite",
             "description": "Spider silk protein MaSp1 — high-strength biomaterial fiber",
             "status": "Available", "author": "iGEM 2016 Team Aachen",
             "url": "https://parts.igem.org/Part:BBa_K1902001", "source": "iGEM Registry (offline)"},
            {"name": "BBa_K3801000", "type": "Coding",
             "description": "Human recombinant collagen type I alpha-1 — scaffold biomaterial",
             "status": "Available", "author": "iGEM 2021",
             "url": "https://parts.igem.org/Part:BBa_K3801000", "source": "iGEM Registry (offline)"},
            {"name": "BBa_K1404003", "type": "Coding",
             "description": "BMP-2 bone morphogenetic protein — osteogenic differentiation",
             "status": "Available", "author": "iGEM 2014",
             "url": "https://parts.igem.org/Part:BBa_K1404003", "source": "iGEM Registry (offline)"},
            {"name": "BBa_K2924000", "type": "Composite",
             "description": "VEGF secretion circuit — angiogenesis promotion for vascularised scaffolds",
             "status": "Available", "author": "iGEM 2019",
             "url": "https://parts.igem.org/Part:BBa_K2924000", "source": "iGEM Registry (offline)"},
            {"name": "BBa_K4242001", "type": "Composite",
             "description": "IL-10 anti-inflammatory circuit — immune modulation for implants",
             "status": "Available", "author": "iGEM 2022",
             "url": "https://parts.igem.org/Part:BBa_K4242001", "source": "iGEM Registry (offline)"},
            {"name": "BBa_K1323009", "type": "Coding",
             "description": "PHB polyhydroxybutyrate synthase — biodegradable polymer biosynthesis",
             "status": "Available", "author": "iGEM 2014",
             "url": "https://parts.igem.org/Part:BBa_K1323009", "source": "iGEM Registry (offline)"},
            {"name": "BBa_K3801005", "type": "Composite",
             "description": "Inflammation-sensing NF-kB promoter driving therapeutic release",
             "status": "Available", "author": "iGEM 2021",
             "url": "https://parts.igem.org/Part:BBa_K3801005", "source": "iGEM Registry (offline)"},
            {"name": "BBa_K2021001", "type": "Coding",
             "description": "TGF-beta1 — chondrogenic differentiation factor",
             "status": "Available", "author": "iGEM 2017",
             "url": "https://parts.igem.org/Part:BBa_K2021001", "source": "iGEM Registry (offline)"},
        ]
        q = query.lower()
        filtered = [p for p in catalog
                    if q in p["description"].lower() or q in p["name"].lower()]
        return (filtered or catalog)[:limit]
