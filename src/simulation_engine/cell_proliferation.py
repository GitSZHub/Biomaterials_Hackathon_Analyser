"""
Cell Proliferation on Scaffold
===============================
Logistic growth ODE coupled to scaffold degradation.
Output: cell number + scaffold mass vs time.
"""

from __future__ import annotations
from typing import Dict

import numpy as np
from scipy.integrate import odeint

from .base_model import SimulationModel, Parameter, SimulationResult


class CellProliferationModel(SimulationModel):
    name = "Cell Proliferation on Scaffold"
    description = (
        "Logistic cell growth coupled to scaffold degradation. "
        "Carrying capacity decreases as scaffold degrades."
    )

    def get_parameters(self) -> Dict[str, Parameter]:
        return {
            "N0": Parameter("Initial cell count", 1e4, 1e2, 1e6, "cells",
                            "Seeding density"),
            "r": Parameter("Growth rate", 0.5, 0.01, 2.0, "1/day",
                           "Intrinsic growth rate"),
            "K": Parameter("Carrying capacity", 1e6, 1e4, 1e7, "cells",
                           "Max cells scaffold can support"),
            "M0": Parameter("Initial scaffold mass", 100.0, 10.0, 500.0, "mg",
                            "Starting scaffold mass"),
            "k_deg": Parameter("Degradation constant", 0.02, 0.001, 0.2, "1/day",
                               "First-order scaffold degradation rate"),
            "porosity": Parameter("Porosity", 0.7, 0.1, 0.95, "",
                                  "Scaffold porosity (affects carrying capacity)"),
        }

    def run(self, params: Dict[str, float], t_end: float = 30.0,
            n_points: int = 500) -> SimulationResult:
        p = {**self.get_defaults(), **params}
        t = np.linspace(0, t_end, n_points)

        def odes(y, t_val):
            N, M = y
            # Carrying capacity scales with remaining scaffold mass and porosity
            K_eff = p["K"] * (M / p["M0"]) * p["porosity"]
            K_eff = max(K_eff, 1.0)
            dNdt = p["r"] * N * (1 - N / K_eff)
            dMdt = -p["k_deg"] * M
            return [dNdt, dMdt]

        y0 = [p["N0"], p["M0"]]
        sol = odeint(odes, y0, t)
        N = sol[:, 0]
        M = sol[:, 1]

        # Annotations
        annotations = []
        half_life = np.log(2) / p["k_deg"] if p["k_deg"] > 0 else float("inf")
        annotations.append(f"Scaffold half-life: {half_life:.1f} days")
        peak_idx = np.argmax(N)
        annotations.append(f"Peak cell count: {N[peak_idx]:.0f} at day {t[peak_idx]:.1f}")

        return SimulationResult(
            model_name=self.name,
            t=t,
            curves={"cells": N, "scaffold_mass": M},
            curve_labels={"cells": "Cell Count", "scaffold_mass": "Scaffold Mass"},
            curve_units={"cells": "cells", "scaffold_mass": "mg"},
            t_unit="days",
            annotations=annotations,
        )
