"""
Simulation Engine
==================
ODE-based simulation models for biomaterials research.
All models inherit SimulationModel base class and provide
standardised parameter/run/plot interface.
"""

from .base_model import SimulationModel, Parameter, SimulationResult
from .cell_proliferation import CellProliferationModel
from .drug_release import DrugReleaseModel
from .gene_circuit import GeneCircuitModel
from .diffusion import DiffusionModel
from .tissue_response import TissueResponseModel
from .metabolic_flux import MetabolicFluxModel

# Registry of all available models
MODEL_REGISTRY = {
    "cell_proliferation": CellProliferationModel,
    "drug_release": DrugReleaseModel,
    "gene_circuit": GeneCircuitModel,
    "diffusion": DiffusionModel,
    "tissue_response": TissueResponseModel,
    "metabolic_flux": MetabolicFluxModel,
}

__all__ = [
    "SimulationModel", "Parameter", "SimulationResult",
    "CellProliferationModel", "DrugReleaseModel",
    "GeneCircuitModel", "DiffusionModel",
    "TissueResponseModel", "MetabolicFluxModel",
    "MODEL_REGISTRY",
]
