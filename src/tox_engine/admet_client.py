"""
ADMETlab MCP Client

Wraps the ADMETlab 3.0 MCP server for ADMET property prediction.
No API key required -- lowest-friction ToxMCP server for hackathon day one.

ADMET = Absorption, Distribution, Metabolism, Excretion, Toxicity

Key use cases in biomaterials:
  - Predict toxicity of drug molecules loaded into a scaffold
  - Screen degradation products of biodegradable polymers
  - Assess leachables from polymer or ceramic matrices

Default port: 8082
Install:  pip install admetlab-mcp
Start:    python -m admetlab_mcp --port 8082
"""

import logging
from dataclasses import dataclass
from typing import Optional
from .mcp_client import MCPClient, MCPToolResult

logger = logging.getLogger(__name__)


@dataclass
class ADMETResult:
    """Parsed ADMET prediction for a single compound."""
    smiles: str
    cleaned_smiles: str = ""
    # Absorption
    caco2_permeability: Optional[float] = None      # cm/s, GI absorption proxy
    hia: Optional[float] = None                      # human intestinal absorption %
    # Distribution
    bbb_penetration: Optional[float] = None          # blood-brain barrier score
    vd: Optional[float] = None                       # volume of distribution L/kg
    plasma_protein_binding: Optional[float] = None   # % bound
    # Metabolism
    cyp3a4_substrate: Optional[str] = None           # Yes/No/Moderate
    cyp2d6_substrate: Optional[str] = None
    # Excretion
    half_life: Optional[float] = None                # hours
    clearance: Optional[float] = None                # mL/min/kg
    # Toxicity flags
    herg_inhibition: Optional[str] = None            # cardiac safety flag
    ames_mutagenicity: Optional[str] = None          # genotoxicity flag
    acute_oral_toxicity: Optional[str] = None        # LD50 class
    hepatotoxicity: Optional[str] = None
    # Raw full response for display
    full_panel: dict = None
    svg_structure: str = ""                          # SVG rendering of molecule
    success: bool = True
    error: Optional[str] = None

    def __post_init__(self):
        if self.full_panel is None:
            self.full_panel = {}

    @property
    def has_toxicity_flags(self) -> bool:
        """True if any toxicity endpoint returned a positive flag."""
        flags = [self.herg_inhibition, self.ames_mutagenicity, self.hepatotoxicity]
        positive = {"yes", "positive", "active", "toxic", "high"}
        return any(str(f).lower() in positive for f in flags if f)

    @property
    def toxicity_summary(self) -> str:
        """Short human-readable toxicity summary for the UI."""
        issues = []
        if str(self.ames_mutagenicity or "").lower() in ("yes", "positive", "active"):
            issues.append("Ames mutagenic")
        if str(self.herg_inhibition or "").lower() in ("yes", "active", "high"):
            issues.append("hERG inhibitor (cardiac risk)")
        if str(self.hepatotoxicity or "").lower() in ("yes", "toxic"):
            issues.append("Hepatotoxic")
        if not issues:
            return "No major flags detected"
        return "; ".join(issues)


class ADMETClient:
    """
    Client for the ADMETlab MCP server.

    Args:
        client: MCPClient pointed at the ADMETlab server.
                Obtain via ToxServerManager.get_client("admet").
    """

    def __init__(self, client: MCPClient):
        self._c = client

    def wash_molecule(self, smiles: str) -> str:
        """
        Standardise a SMILES string using ADMETlab's molecule washer.
        Returns the cleaned SMILES, or the original on failure.
        """
        result: MCPToolResult = self._c.call_tool("wash_molecule", {"smiles": smiles})
        if not result.success:
            logger.warning("wash_molecule failed for %s: %s", smiles, result.error)
            return smiles
        if isinstance(result.content, dict):
            return result.content.get("cleaned_smiles", smiles)
        return smiles

    def predict_admet(self, smiles: str, wash_first: bool = True) -> ADMETResult:
        """
        Run the full ADMET panel for a SMILES compound.

        Args:
            smiles:      SMILES string for the compound
            wash_first:  Standardise SMILES before prediction (recommended)

        Returns:
            ADMETResult with all predicted properties populated.
        """
        cleaned = self.wash_molecule(smiles) if wash_first else smiles

        result: MCPToolResult = self._c.call_tool("predict_admet", {"smiles": cleaned})
        if not result.success:
            return ADMETResult(smiles=smiles, cleaned_smiles=cleaned,
                               success=False, error=result.error)

        raw = result.content if isinstance(result.content, dict) else {}
        return self._parse_admet(smiles, cleaned, raw)

    def render_structure(self, smiles: str) -> str:
        """
        Return an SVG string rendering of the molecule for display in the UI.
        Returns empty string on failure.
        """
        result: MCPToolResult = self._c.call_tool("render_molecule_svg", {"smiles": smiles})
        if not result.success:
            return ""
        if isinstance(result.content, dict):
            return result.content.get("svg", "")
        if isinstance(result.content, str) and result.content.startswith("<svg"):
            return result.content
        return ""

    def predict_batch(self, smiles_list: list[str]) -> list[ADMETResult]:
        """
        Predict ADMET for multiple SMILES (up to 1000 per ADMETlab limits).
        Returns list of ADMETResult in the same order as input.
        """
        results = []
        for smiles in smiles_list:
            results.append(self.predict_admet(smiles))
        return results

    def _parse_admet(self, original: str, cleaned: str, raw: dict) -> ADMETResult:
        """Map ADMETlab response keys to ADMETResult fields."""
        props = raw.get("properties", raw)  # handle nested or flat response

        def _get(*keys):
            for k in keys:
                v = props.get(k)
                if v is not None:
                    return v
            return None

        return ADMETResult(
            smiles=original,
            cleaned_smiles=cleaned,
            caco2_permeability=_get("Caco-2", "caco2"),
            hia=_get("HIA", "human_intestinal_absorption"),
            bbb_penetration=_get("BBB", "bbb_penetration"),
            vd=_get("VD", "volume_of_distribution"),
            plasma_protein_binding=_get("PPB", "plasma_protein_binding"),
            cyp3a4_substrate=_get("CYP3A4-substrate", "cyp3a4_substrate"),
            cyp2d6_substrate=_get("CYP2D6-substrate", "cyp2d6_substrate"),
            half_life=_get("T1/2", "half_life"),
            clearance=_get("CL", "clearance"),
            herg_inhibition=_get("hERG", "herg_inhibition"),
            ames_mutagenicity=_get("AMES", "ames_mutagenicity"),
            acute_oral_toxicity=_get("LD50", "acute_oral_toxicity"),
            hepatotoxicity=_get("DILI", "hepatotoxicity"),
            full_panel=raw,
            success=True,
        )
