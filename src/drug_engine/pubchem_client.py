"""
PubChem Client — compound search and property retrieval.

Uses the PubChem REST API (free, no API key).
Base URL: https://pubchem.ncbi.nlm.nih.gov/rest/pug/

Public API:
    client = PubChemClient()
    results = client.search("dexamethasone")
    props   = client.get_properties(cid=1234)
    sdf     = client.get_sdf(cid=1234)
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

_BASE     = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
_DELAY    = 0.2   # PubChem rate limit: 5 req/s


class PubChemClient:
    """Search PubChem for compounds and retrieve physicochemical properties."""

    _PROPERTIES = (
        "MolecularFormula,MolecularWeight,XLogP,TPSA,"
        "HBondDonorCount,HBondAcceptorCount,RotatableBondCount,"
        "Complexity,Charge,IUPACName,CanonicalSMILES"
    )

    def __init__(self):
        self._last = 0.0

    # ── Public ────────────────────────────────────────────────────────────────

    def search(self, name: str, max_results: int = 10) -> List[Dict]:
        """
        Search PubChem by compound name.

        Returns list of dicts with: cid, name, formula, mw, smiles, iupac_name,
        xlogp, tpsa, hbd, hba, drug_likeness (Lipinski pass/fail).
        """
        cids = self._name_to_cids(name, max_results)
        if not cids:
            return []
        return self._get_compound_records(cids)

    def get_properties(self, cid: int) -> Dict:
        """
        Fetch physicochemical properties for a single compound CID.
        Returns property dict, or empty dict on failure.
        """
        records = self._get_compound_records([cid])
        return records[0] if records else {}

    def get_sdf(self, cid: int) -> Optional[str]:
        """Return SDF (structure data file) string for a CID, or None."""
        self._rate_limit()
        url = f"{_BASE}/compound/cid/{cid}/SDF"
        try:
            resp = requests.get(url, timeout=20,
                                headers={"User-Agent": "BioHackathonAnalyser/1.0"})
            if resp.ok:
                return resp.text
        except Exception as e:
            logger.error(f"SDF fetch failed for CID {cid}: {e}")
        return None

    def get_bioassay_summary(self, cid: int) -> Dict:
        """
        Return a brief bioassay activity summary for a CID.
        Keys: active_count, inactive_count, tested_count.
        """
        self._rate_limit()
        url = f"{_BASE}/compound/cid/{cid}/assaysummary/JSON"
        try:
            resp = requests.get(url, timeout=20,
                                headers={"User-Agent": "BioHackathonAnalyser/1.0"})
            if resp.ok:
                data = resp.json()
                rows = data.get("Table", {}).get("Row", [])
                active   = sum(1 for r in rows if r.get("Cell", [""])[3] == "Active")
                inactive = sum(1 for r in rows if r.get("Cell", [""])[3] == "Inactive")
                return {"active_count": active, "inactive_count": inactive,
                        "tested_count": len(rows)}
        except Exception as e:
            logger.warning(f"Bioassay summary failed for CID {cid}: {e}")
        return {"active_count": 0, "inactive_count": 0, "tested_count": 0}

    # ── Internals ─────────────────────────────────────────────────────────────

    def _rate_limit(self):
        elapsed = time.time() - self._last
        if elapsed < _DELAY:
            time.sleep(_DELAY - elapsed)
        self._last = time.time()

    def _name_to_cids(self, name: str, max_results: int) -> List[int]:
        self._rate_limit()
        url = f"{_BASE}/compound/name/{requests.utils.quote(name)}/cids/JSON"
        try:
            resp = requests.get(url, timeout=20,
                                headers={"User-Agent": "BioHackathonAnalyser/1.0"})
            if resp.ok:
                cids = resp.json().get("IdentifierList", {}).get("CID", [])
                return cids[:max_results]
        except Exception as e:
            logger.error(f"PubChem name search failed for '{name}': {e}")
        return []

    def _get_compound_records(self, cids: List[int]) -> List[Dict]:
        if not cids:
            return []
        self._rate_limit()
        cid_str = ",".join(str(c) for c in cids)
        url = (f"{_BASE}/compound/cid/{cid_str}/property/"
               f"{self._PROPERTIES}/JSON")
        try:
            resp = requests.get(url, timeout=30,
                                headers={"User-Agent": "BioHackathonAnalyser/1.0"})
            if not resp.ok:
                return []
            props_list = resp.json().get("PropertyTable", {}).get("Properties", [])
            return [self._parse_props(p) for p in props_list]
        except Exception as e:
            logger.error(f"PubChem property fetch failed: {e}")
            return []

    @staticmethod
    def _parse_props(p: Dict) -> Dict:
        mw   = float(p.get("MolecularWeight", 0) or 0)
        xlogp = float(p.get("XLogP", 0) or 0)
        hbd  = int(p.get("HBondDonorCount", 0) or 0)
        hba  = int(p.get("HBondAcceptorCount", 0) or 0)

        # Lipinski Rule of Five
        lipinski = (mw <= 500 and xlogp <= 5 and hbd <= 5 and hba <= 10)

        return {
            "cid":          p.get("CID"),
            "name":         p.get("IUPACName", ""),
            "formula":      p.get("MolecularFormula", ""),
            "mw":           mw,
            "smiles":       p.get("CanonicalSMILES", ""),
            "iupac_name":   p.get("IUPACName", ""),
            "xlogp":        xlogp,
            "tpsa":         float(p.get("TPSA", 0) or 0),
            "hbd":          hbd,
            "hba":          hba,
            "rotatable_bonds": int(p.get("RotatableBondCount", 0) or 0),
            "complexity":   float(p.get("Complexity", 0) or 0),
            "drug_likeness": "Pass" if lipinski else "Fail (Lipinski)",
        }
