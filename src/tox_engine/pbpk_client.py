"""
PBPK MCP Client (Physiologically-Based Pharmacokinetics)

Wraps the PBPK MCP server, which provides an interface to the Open Systems
Pharmacology (OSP) Suite for pharmacokinetic simulations.
No API key required.

Key use cases for biomaterials:
  - Drug-eluting scaffolds: model drug release from device -> tissue -> systemic
  - Predict Cmax and AUC from local delivery to assess systemic exposure
  - Required for combination product (drug + device) regulatory submissions
  - Sensitivity analysis: which material properties most affect PK?

Workflow:
  1. Load a PBPK model file (.pkml or .pksim5)
  2. Edit parameters (dose, release rate, tissue compartment properties)
  3. Run simulation -> get time-concentration profiles
  4. Extract PK metrics: Cmax, Tmax, AUC, T1/2

Default port: 8085
Install:  pip install pbpk-mcp
Start:    python -m pbpk_mcp --port 8085
"""

import logging
from dataclasses import dataclass, field
from typing import Optional
from .mcp_client import MCPClient, MCPToolResult

logger = logging.getLogger(__name__)


@dataclass
class PKMetrics:
    """Key pharmacokinetic metrics from a simulation run."""
    cmax: Optional[float] = None        # peak concentration (mg/L or nmol/L)
    tmax: Optional[float] = None        # time to peak (hours)
    auc: Optional[float] = None         # area under curve (mg*h/L)
    half_life: Optional[float] = None   # T1/2 (hours)
    clearance: Optional[float] = None   # mL/min/kg
    units: dict = field(default_factory=dict)


@dataclass
class SimulationResult:
    """Result of a PBPK simulation run."""
    job_id: str
    status: str = "pending"             # pending / running / complete / failed
    pk_metrics: PKMetrics = field(default_factory=PKMetrics)
    time_points: list = field(default_factory=list)       # hours
    concentrations: list = field(default_factory=list)    # paired with time_points
    compartment: str = ""               # which compartment was simulated
    population: Optional[dict] = None  # population stats if pop simulation
    success: bool = True
    error: Optional[str] = None


class PBPKClient:
    """
    Client for the PBPK MCP server.
    Obtain via: ToxServerManager.get_client("pbpk")
    """

    def __init__(self, client: MCPClient):
        self._c = client

    def load_model(self, model_path: str) -> Optional[str]:
        """
        Load a PBPK model file (.pkml or .pksim5).
        Returns a model_id string for subsequent calls, or None on failure.
        """
        result: MCPToolResult = self._c.call_tool("load_model", {"path": model_path})
        if not result.success:
            logger.error("Failed to load PBPK model %s: %s", model_path, result.error)
            return None
        data = result.content if isinstance(result.content, dict) else {}
        return data.get("model_id")

    def list_parameters(self, model_id: str) -> list:
        """Return all editable parameters for a loaded model."""
        result: MCPToolResult = self._c.call_tool(
            "list_parameters", {"model_id": model_id}
        )
        if not result.success:
            return []
        return result.content if isinstance(result.content, list) else []

    def set_parameter(self, model_id: str, param_path: str, value: float) -> bool:
        """Set a model parameter value. Returns True on success."""
        result: MCPToolResult = self._c.call_tool("set_parameter", {
            "model_id": model_id,
            "path": param_path,
            "value": value,
        })
        return result.success

    def run_simulation(self, model_id: str, end_time_h: float = 24.0,
                       resolution: int = 100) -> SimulationResult:
        """
        Run a deterministic simulation.

        Args:
            model_id:    ID from load_model()
            end_time_h:  Simulation duration in hours
            resolution:  Number of time points to output

        Returns SimulationResult with PK metrics and time-concentration data.
        """
        result: MCPToolResult = self._c.call_tool("run_simulation", {
            "model_id": model_id,
            "end_time": end_time_h,
            "resolution": resolution,
        })
        if not result.success:
            return SimulationResult(job_id="", success=False, error=result.error)

        data = result.content if isinstance(result.content, dict) else {}
        return self._parse_simulation(data)

    def run_population_simulation(self, model_id: str, population_size: int = 100,
                                   end_time_h: float = 24.0) -> SimulationResult:
        """Run a population-based simulation and return aggregate PK statistics."""
        result: MCPToolResult = self._c.call_tool("run_population_simulation", {
            "model_id": model_id,
            "population_size": population_size,
            "end_time": end_time_h,
        })
        if not result.success:
            return SimulationResult(job_id="", success=False, error=result.error)
        data = result.content if isinstance(result.content, dict) else {}
        sim = self._parse_simulation(data)
        sim.population = data.get("population_stats")
        return sim

    def sensitivity_analysis(self, model_id: str, param_paths: list,
                              variation_pct: float = 50.0) -> dict:
        """
        Run a sensitivity analysis sweeping listed parameters +/- variation_pct.
        Returns dict of param_path -> sensitivity_index.
        """
        result: MCPToolResult = self._c.call_tool("sensitivity_analysis", {
            "model_id": model_id,
            "parameters": param_paths,
            "variation_percent": variation_pct,
        })
        if not result.success:
            return {}
        return result.content if isinstance(result.content, dict) else {}

    def _parse_simulation(self, data: dict) -> SimulationResult:
        pk_raw = data.get("pk_metrics", {})
        pk = PKMetrics(
            cmax=pk_raw.get("cmax"),
            tmax=pk_raw.get("tmax"),
            auc=pk_raw.get("auc"),
            half_life=pk_raw.get("half_life"),
            clearance=pk_raw.get("clearance"),
            units=pk_raw.get("units", {}),
        )
        return SimulationResult(
            job_id=data.get("job_id", ""),
            status=data.get("status", "complete"),
            pk_metrics=pk,
            time_points=data.get("time_points", []),
            concentrations=data.get("concentrations", []),
            compartment=data.get("compartment", ""),
            success=True,
        )
