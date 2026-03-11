"""
Simulation Engine — Base Model
================================
Abstract base class for all ODE simulation models.
Provides Parameter dataclass, SimulationResult, and
standardised run/plot interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass
class Parameter:
    """A tuneable simulation parameter."""
    name: str
    default: float
    min_val: float
    max_val: float
    unit: str
    description: str
    step: float = 0.0       # slider step size (0 = auto)

    def __post_init__(self):
        if self.step == 0:
            self.step = (self.max_val - self.min_val) / 100.0


@dataclass
class SimulationResult:
    """Output of a simulation run."""
    model_name: str
    t: np.ndarray                              # time array
    curves: Dict[str, np.ndarray]              # name -> values
    curve_labels: Dict[str, str]               # name -> display label
    curve_units: Dict[str, str]                # name -> unit string
    t_unit: str = "days"
    annotations: List[str] = field(default_factory=list)  # key insights


class SimulationModel(ABC):
    """Abstract base for simulation models."""

    name: str = "Unnamed Model"
    description: str = ""

    @abstractmethod
    def get_parameters(self) -> Dict[str, Parameter]:
        """Return parameter definitions."""
        ...

    @abstractmethod
    def run(self, params: Dict[str, float], t_end: float = 30.0,
            n_points: int = 500) -> SimulationResult:
        """Run the simulation with given parameter values."""
        ...

    def get_defaults(self) -> Dict[str, float]:
        """Return default parameter values."""
        return {k: p.default for k, p in self.get_parameters().items()}
