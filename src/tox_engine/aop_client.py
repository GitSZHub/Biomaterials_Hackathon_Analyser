"""
AOP MCP Client (Adverse Outcome Pathways)

Wraps the AOP MCP server for mechanistic toxicity pathway discovery.
No API key required.

What is an AOP?
  An Adverse Outcome Pathway is a structured causal chain:
  Molecular Initiating Event (MIE) -> Key Events (KEs) -> Adverse Outcome (AO)
  e.g. titanium ion release -> ROS generation -> mitochondrial dysfunction ->
       apoptosis -> tissue necrosis

Key capabilities for biomaterials:
  - Identify which AOPs are triggered by material components
  - Map the mechanistic pathway from material-cell contact to adverse outcome
  - Find key events that are measurable in in vitro assays (informs assay selection)
  - Strengthen the biological rationale in regulatory submissions and briefings
  - Links to CompTox assay data for key event evidence

Default port: 8084
Install:  pip install aop-mcp
Start:    python -m aop_mcp --port 8084
"""

import logging
from dataclasses import dataclass, field
from typing import Optional
from .mcp_client import MCPClient, MCPToolResult

logger = logging.getLogger(__name__)


@dataclass
class KeyEvent:
    """A single key event within an AOP."""
    ke_id: str
    title: str
    biological_level: str   # e.g. "Molecular", "Cellular", "Tissue", "Organ"
    organ: str = ""
    evidence_level: str = ""


@dataclass
class AOPSummary:
    """Summary of a single Adverse Outcome Pathway."""
    aop_id: str
    title: str
    status: str = ""        # e.g. "OECD Approved", "Under Development"
    mie: str = ""           # Molecular Initiating Event description
    adverse_outcome: str = ""
    key_events: list = field(default_factory=list)   # list[KeyEvent]
    stressors: list = field(default_factory=list)    # chemical names/DTXSIDs
    assay_links: list = field(default_factory=list)  # related in vitro assays
    aopwiki_url: str = ""


@dataclass
class AOPMappingResult:
    """Result of mapping a chemical or material component to relevant AOPs."""
    query: str                          # chemical name or DTXSID queried
    aops: list = field(default_factory=list)   # list[AOPSummary]
    mie_summary: str = ""               # combined MIE descriptions
    adverse_outcome_summary: str = ""   # combined AO descriptions
    relevant_assays: list = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None

    @property
    def aop_count(self) -> int:
        return len(self.aops)

    @property
    def biological_concern_summary(self) -> str:
        """One-line summary suitable for the briefing doc."""
        if not self.aops:
            return "No known Adverse Outcome Pathways identified."
        outcomes = list({a.adverse_outcome for a in self.aops if a.adverse_outcome})
        return f"{len(self.aops)} AOP(s) identified. Adverse outcomes: {'; '.join(outcomes[:3])}."


class AOPClient:
    """
    Client for the AOP MCP server.
    Obtain via: ToxServerManager.get_client("aop")
    """

    def __init__(self, client: MCPClient):
        self._c = client

    def search_aops(self, query: str, limit: int = 10) -> list:
        """Search AOP-Wiki by keyword. Returns list[AOPSummary]."""
        result: MCPToolResult = self._c.call_tool(
            "search_aops", {"query": query, "limit": limit}
        )
        if not result.success:
            logger.warning("AOP search failed for %r: %s", query, result.error)
            return []
        items = result.content if isinstance(result.content, list) else []
        return [self._parse_aop(item) for item in items]

    def get_aop_detail(self, aop_id: str) -> Optional[AOPSummary]:
        """Fetch full details for a specific AOP by ID."""
        result: MCPToolResult = self._c.call_tool("get_aop", {"aop_id": aop_id})
        if not result.success:
            return None
        data = result.content if isinstance(result.content, dict) else {}
        return self._parse_aop(data)

    def map_chemical_to_aops(self, dtxsid_or_name: str) -> AOPMappingResult:
        """
        Find all AOPs triggered by a specific chemical/stressor.
        Input can be a DTXSID (preferred) or chemical name.
        """
        result: MCPToolResult = self._c.call_tool(
            "map_chemical_to_aops", {"stressor": dtxsid_or_name}
        )
        if not result.success:
            return AOPMappingResult(query=dtxsid_or_name, success=False, error=result.error)

        data = result.content if isinstance(result.content, dict) else {}
        aops = [self._parse_aop(a) for a in data.get("aops", [])]
        assays = data.get("assay_links", [])

        return AOPMappingResult(
            query=dtxsid_or_name,
            aops=aops,
            mie_summary=data.get("mie_summary", ""),
            adverse_outcome_summary=data.get("adverse_outcome_summary", ""),
            relevant_assays=assays,
            success=True,
        )

    def map_material_components(self, components: list) -> dict:
        """
        Map a list of material components (names or DTXSIDs) to AOPs.
        Returns dict of component -> AOPMappingResult.
        """
        return {c: self.map_chemical_to_aops(c) for c in components}

    def get_key_events_for_aop(self, aop_id: str) -> list:
        """Return list[KeyEvent] for a given AOP."""
        detail = self.get_aop_detail(aop_id)
        return detail.key_events if detail else []

    def _parse_aop(self, data: dict) -> AOPSummary:
        kes = [
            KeyEvent(
                ke_id=ke.get("id", ""),
                title=ke.get("title", ""),
                biological_level=ke.get("biological_organisation", ""),
                organ=ke.get("organ", ""),
                evidence_level=ke.get("evidence", ""),
            )
            for ke in data.get("key_events", [])
        ]
        return AOPSummary(
            aop_id=str(data.get("id", "")),
            title=data.get("title", data.get("short_name", "")),
            status=data.get("status", ""),
            mie=data.get("mie", data.get("molecular_initiating_event", "")),
            adverse_outcome=data.get("adverse_outcome", ""),
            key_events=kes,
            stressors=data.get("stressors", []),
            assay_links=data.get("assay_links", []),
            aopwiki_url=data.get("url", f"https://aopwiki.org/aops/{data.get('id', '')}"),
        )
