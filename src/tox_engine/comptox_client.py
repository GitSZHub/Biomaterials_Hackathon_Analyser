"""
EPA CompTox MCP Client

Wraps the CompTox MCP server to query the EPA Computational Toxicology database.
Requires a free EPA API key (register at https://comptox.epa.gov/dashboard).

Key capabilities for biomaterials:
  - Identify any chemical component of your material by name or SMILES
  - Retrieve hazard classification, cancer potency, genotoxicity flags
  - Pull toxicity reference values (ToxValDB: RfD, NOAEL, POD)
  - Run predictive toxicology models (TEST, OPERA) on novel structures
  - Feeds directly into ISO 10993 toxicological risk assessment

Default port: 8083
Install:  pip install comptox-mcp
Start:    EPA_COMPTOX_API_KEY=<key> python -m comptox_mcp --port 8083
"""

import logging
from dataclasses import dataclass, field
from typing import Optional
from .mcp_client import MCPClient, MCPToolResult

logger = logging.getLogger(__name__)


@dataclass
class ChemicalHazardProfile:
    """Consolidated hazard profile for a chemical compound."""
    dtxsid: str
    name: str = ""
    smiles: str = ""
    molecular_weight: Optional[float] = None
    carcinogenicity: Optional[str] = None
    genotoxicity: Optional[str] = None
    reproductive_toxicity: Optional[str] = None
    noael_mg_kg: Optional[float] = None
    loael_mg_kg: Optional[float] = None
    ld50_mg_kg: Optional[float] = None
    ghs_hazard_codes: list = field(default_factory=list)
    regulatory_lists: list = field(default_factory=list)
    opera_predictions: dict = field(default_factory=dict)
    raw_hazard: dict = field(default_factory=dict)
    raw_toxvals: list = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None

    @property
    def is_high_concern(self) -> bool:
        high_flags = {"carcinogen", "mutagenic", "genotoxic", "reprotoxic", "group a", "group b"}
        combined = f"{self.carcinogenicity or ''} {self.genotoxicity or ''}".lower()
        return any(f in combined for f in high_flags)

    @property
    def risk_tier(self) -> str:
        """high / moderate / low / unknown -- used for UI colour-coding."""
        if not self.success:
            return "unknown"
        if self.is_high_concern:
            return "high"
        if self.noael_mg_kg is not None and self.noael_mg_kg < 50:
            return "moderate"
        return "low"


class CompToxClient:
    """
    Client for the EPA CompTox MCP server.
    Obtain via: ToxServerManager.get_client("comptox")
    """

    def __init__(self, client: MCPClient):
        self._c = client

    def search_chemical(self, query: str) -> Optional[str]:
        """Search by name, CAS, or SMILES. Returns DTXSID or None."""
        result: MCPToolResult = self._c.call_tool("search_chemicals", {"query": query, "limit": 5})
        if not result.success:
            logger.warning("Chemical search failed for %r: %s", query, result.error)
            return None
        hits = result.content if isinstance(result.content, list) else []
        return hits[0].get("dtxsid") if hits else None

    def get_hazard_profile(self, dtxsid: str) -> ChemicalHazardProfile:
        """Build a full hazard profile from DTXSID. Combines hazard + toxvals + genotox."""
        hazard_r = self._c.call_tool("get_hazard_data", {"dtxsid": dtxsid})
        toxval_r = self._c.call_tool("get_toxicity_values", {"dtxsid": dtxsid})
        genotox_r = self._c.call_tool("get_genetox_summary", {"dtxsid": dtxsid})

        if not hazard_r.success:
            return ChemicalHazardProfile(dtxsid=dtxsid, success=False, error=hazard_r.error)

        hazard = hazard_r.content if isinstance(hazard_r.content, dict) else {}
        toxvals = toxval_r.content if isinstance(toxval_r.content, list) else []
        genotox = genotox_r.content if isinstance(genotox_r.content, dict) else {}
        return self._build_profile(dtxsid, hazard, toxvals, genotox)

    def lookup_by_name(self, chemical_name: str) -> ChemicalHazardProfile:
        """Search by name then fetch full profile."""
        dtxsid = self.search_chemical(chemical_name)
        if not dtxsid:
            return ChemicalHazardProfile(
                dtxsid="", name=chemical_name, success=False,
                error=f"Chemical {chemical_name!r} not found in CompTox"
            )
        profile = self.get_hazard_profile(dtxsid)
        profile.name = chemical_name
        return profile

    def run_opera_predictions(self, smiles: str) -> dict:
        """Run OPERA QSAR model predictions on a SMILES structure."""
        result = self._c.call_tool("run_opera_prediction", {"smiles": smiles})
        if not result.success:
            logger.warning("OPERA prediction failed: %s", result.error)
            return {}
        return result.content if isinstance(result.content, dict) else {}

    def screen_material_components(self, components: list) -> list:
        """
        Screen a list of chemical names/CAS numbers for hazard.
        Returns one ChemicalHazardProfile per component.
        Typical use: screen all monomers, crosslinkers, photoinitiators,
        solvents in a biomaterial formulation for ISO 10993 compliance.
        """
        return [self.lookup_by_name(c) for c in components]

    def _build_profile(self, dtxsid, hazard, toxvals, genotox) -> ChemicalHazardProfile:
        noael = loael = ld50 = None
        for tv in toxvals:
            ep = str(tv.get("toxval_type", "")).upper()
            val = tv.get("toxval_numeric")
            units = str(tv.get("toxval_units", "")).lower()
            if "mg/kg" in units and val is not None:
                if "noael" in ep and noael is None:
                    noael = float(val)
                elif "loael" in ep and loael is None:
                    loael = float(val)
                elif "ld50" in ep and ld50 is None:
                    ld50 = float(val)

        return ChemicalHazardProfile(
            dtxsid=dtxsid,
            name=hazard.get("preferred_name", ""),
            smiles=hazard.get("smiles", ""),
            molecular_weight=hazard.get("molecular_weight"),
            carcinogenicity=hazard.get("carcinogenicity") or hazard.get("cancer_call"),
            genotoxicity=genotox.get("summary") or genotox.get("call"),
            ghs_hazard_codes=hazard.get("ghs_hazard_codes", []),
            regulatory_lists=hazard.get("regulatory_lists", []),
            noael_mg_kg=noael, loael_mg_kg=loael, ld50_mg_kg=ld50,
            raw_hazard=hazard, raw_toxvals=toxvals, success=True,
        )
