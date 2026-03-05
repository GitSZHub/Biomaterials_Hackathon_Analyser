"""
Toxicology Engine — ToxMCP Integration Layer

Wraps the ToxMCP suite of MCP servers for computational toxicology workflows.
Provides synchronous interfaces and QThread workers for PyQt6 UI integration.

Servers integrated:
    - ADMETlab MCP  : ADMET property prediction from SMILES (no API key)
    - CompTox MCP   : EPA chemical hazard, ToxValDB, predictive models (EPA key)
    - AOP MCP       : Adverse Outcome Pathway discovery and mapping (no key)
    - PBPK MCP      : Physiologically-based pharmacokinetic simulation (no key)

Usage:
    from tox_engine.server_manager import ToxServerManager
    from tox_engine.admet_client import ADMETClient
    from tox_engine.comptox_client import CompToxClient
    from tox_engine.aop_client import AOPClient
    from tox_engine.pbpk_client import PBPKClient
    from tox_engine.biocompat_scorer import BioccompatScorer
    from tox_engine.iso10993_assessor import ISO10993Assessor
    from tox_engine.workers import ADMETWorker, CompToxWorker, AOPWorker
"""

from .server_manager import ToxServerManager
from .mcp_client import MCPClient, MCPError, MCPToolResult

__all__ = [
    "ToxServerManager",
    "MCPClient",
    "MCPError",
    "MCPToolResult",
]
