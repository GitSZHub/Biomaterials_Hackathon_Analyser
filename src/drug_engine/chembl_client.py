"""
ChEMBL Client — bioactivity and target data retrieval.

Uses the ChEMBL REST API (free, no API key).
Base URL: https://www.ebi.ac.uk/chembl/api/data/

Public API:
    client = ChEMBLClient()
    results = client.search_molecule("dexamethasone")
    activity = client.get_bioactivity(chembl_id="CHEMBL1536", target_type="IC50")
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

_BASE  = "https://www.ebi.ac.uk/chembl/api/data"
_DELAY = 0.5   # be polite to ChEMBL servers


class ChEMBLClient:
    """Query ChEMBL for drug molecules, bioactivity, and target information."""

    def __init__(self):
        self._last = 0.0
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/json",
            "User-Agent": "BioHackathonAnalyser/1.0",
        })

    # ── Public ────────────────────────────────────────────────────────────────

    def search_molecule(self, name: str, max_results: int = 10) -> List[Dict]:
        """
        Search ChEMBL for a molecule by name or synonym.

        Returns list of dicts with: chembl_id, name, mw, alogp, hbd, hba,
        ro5_violations, max_phase, indication_class.
        """
        self._rate_limit()
        params = {
            "molecule_synonyms__molecule_synonym__icontains": name,
            "format": "json",
            "limit": max_results,
        }
        try:
            resp = self._session.get(f"{_BASE}/molecule.json", params=params, timeout=30)
            if not resp.ok:
                # Fallback: search by preferred name
                params = {"pref_name__icontains": name, "format": "json",
                          "limit": max_results}
                resp = self._session.get(f"{_BASE}/molecule.json",
                                         params=params, timeout=30)
            if resp.ok:
                mols = resp.json().get("molecules", [])
                return [self._parse_molecule(m) for m in mols]
        except Exception as e:
            logger.error(f"ChEMBL molecule search failed for '{name}': {e}")
        return []

    def get_molecule(self, chembl_id: str) -> Dict:
        """Fetch a single molecule record by ChEMBL ID."""
        self._rate_limit()
        try:
            resp = self._session.get(
                f"{_BASE}/molecule/{chembl_id}.json", timeout=20
            )
            if resp.ok:
                return self._parse_molecule(resp.json())
        except Exception as e:
            logger.error(f"ChEMBL get_molecule failed for {chembl_id}: {e}")
        return {}

    def get_bioactivity(self, chembl_id: str,
                        standard_type: Optional[str] = None,
                        max_results: int = 50) -> List[Dict]:
        """
        Retrieve bioactivity records for a ChEMBL molecule ID.

        Args:
            chembl_id:     e.g. "CHEMBL1536"
            standard_type: filter e.g. "IC50", "EC50", "Ki" — or None for all
            max_results:   cap on results

        Returns list of dicts: target_name, target_type, standard_type,
        standard_value, standard_units, assay_description.
        """
        self._rate_limit()
        params: Dict = {
            "molecule_chembl_id": chembl_id,
            "format": "json",
            "limit": max_results,
        }
        if standard_type:
            params["standard_type"] = standard_type
        try:
            resp = self._session.get(f"{_BASE}/activity.json",
                                     params=params, timeout=30)
            if resp.ok:
                acts = resp.json().get("activities", [])
                return [self._parse_activity(a) for a in acts]
        except Exception as e:
            logger.error(f"ChEMBL bioactivity fetch failed for {chembl_id}: {e}")
        return []

    def get_cytotoxicity_flags(self, chembl_id: str) -> Dict:
        """
        Return a simple cytotoxicity summary: IC50 in common cell lines if available.
        Looks for IC50 activity values with cell_chembl_id populated.
        """
        acts = self.get_bioactivity(chembl_id, standard_type="IC50", max_results=100)
        cell_ic50s = [a for a in acts if a.get("target_type") == "CELL-LINE"
                      and a.get("standard_value") is not None]
        if not cell_ic50s:
            return {"available": False, "records": []}
        return {
            "available": True,
            "records": cell_ic50s[:10],
            "min_ic50": min(a["standard_value"] for a in cell_ic50s
                            if a["standard_value"]),
        }

    # ── Internals ─────────────────────────────────────────────────────────────

    def _rate_limit(self):
        elapsed = time.time() - self._last
        if elapsed < _DELAY:
            time.sleep(_DELAY - elapsed)
        self._last = time.time()

    @staticmethod
    def _parse_molecule(m: Dict) -> Dict:
        props = m.get("molecule_properties") or {}
        return {
            "chembl_id":        m.get("molecule_chembl_id", ""),
            "name":             m.get("pref_name", ""),
            "mw":               float(props.get("full_mwt") or 0),
            "alogp":            float(props.get("alogp") or 0),
            "hbd":              int(props.get("hbd") or 0),
            "hba":              int(props.get("hba") or 0),
            "ro5_violations":   int(props.get("num_ro5_violations") or 0),
            "max_phase":        m.get("max_phase", 0),
            "indication_class": m.get("indication_class", ""),
            "smiles":           (m.get("molecule_structures") or {}).get(
                                    "canonical_smiles", ""),
        }

    @staticmethod
    def _parse_activity(a: Dict) -> Dict:
        val = a.get("standard_value")
        try:
            val = float(val) if val is not None else None
        except (ValueError, TypeError):
            val = None
        return {
            "target_name":       a.get("target_pref_name", ""),
            "target_type":       a.get("target_organism", ""),
            "standard_type":     a.get("standard_type", ""),
            "standard_value":    val,
            "standard_units":    a.get("standard_units", ""),
            "assay_description": (a.get("assay_description") or "")[:200],
            "document_year":     a.get("document_year"),
        }
