"""
Gene Circuit Dynamics
======================
Hill function activator/repressor kinetics.
Represents consequence of CRISPR edit on protein/mRNA level over time.
"""

from __future__ import annotations
from typing import Dict

import numpy as np
from scipy.integrate import odeint

from .base_model import SimulationModel, Parameter, SimulationResult


class GeneCircuitModel(SimulationModel):
    name = "Gene Circuit Dynamics"
    description = (
        "Hill function kinetics for gene regulatory circuit. "
        "Models protein/mRNA response to CRISPR edit or transcription factor change."
    )

    def get_parameters(self) -> Dict[str, Parameter]:
        return {
            "alpha": Parameter("Max production rate", 10.0, 0.1, 100.0, "nM/hr",
                               "Maximum transcription/translation rate"),
            "delta": Parameter("Degradation rate", 0.5, 0.01, 5.0, "1/hr",
                               "Protein/mRNA degradation rate"),
            "K": Parameter("Hill constant (Km)", 5.0, 0.1, 50.0, "nM",
                           "Concentration for half-max activation"),
            "n": Parameter("Hill coefficient", 2.0, 0.5, 8.0, "",
                           "Cooperativity (steepness of response)"),
            "is_repressor": Parameter("Repressor (1) vs Activator (0)", 0, 0, 1, "",
                                      "Toggle activator/repressor logic"),
            "inducer": Parameter("Inducer / TF level", 10.0, 0.0, 100.0, "nM",
                                 "Upstream signal (transcription factor or inducer)"),
            "X0": Parameter("Initial protein level", 0.1, 0.0, 50.0, "nM",
                            "Starting concentration"),
            "basal": Parameter("Basal production", 0.1, 0.0, 5.0, "nM/hr",
                               "Leaky expression even without activator"),
        }

    def run(self, params: Dict[str, float], t_end: float = 48.0,
            n_points: int = 500) -> SimulationResult:
        p = {**self.get_defaults(), **params}
        t = np.linspace(0, t_end, n_points)

        I = p["inducer"]
        is_rep = int(round(p["is_repressor"]))

        def ode(X, t_val):
            if is_rep:
                # Repressor Hill function
                hill = 1.0 / (1.0 + (I / p["K"]) ** p["n"])
            else:
                # Activator Hill function
                hill = (I / p["K"]) ** p["n"] / (1.0 + (I / p["K"]) ** p["n"])
            dXdt = p["basal"] + p["alpha"] * hill - p["delta"] * X
            return dXdt

        sol = odeint(ode, [p["X0"]], t).flatten()

        # Steady state calculation
        if is_rep:
            hill_ss = 1.0 / (1.0 + (I / p["K"]) ** p["n"])
        else:
            hill_ss = (I / p["K"]) ** p["n"] / (1.0 + (I / p["K"]) ** p["n"])
        X_ss = (p["basal"] + p["alpha"] * hill_ss) / p["delta"]
        t_half = np.log(2) / p["delta"]

        circuit = "Repressor" if is_rep else "Activator"
        annotations = [
            f"Circuit type: {circuit}",
            f"Steady-state protein: {X_ss:.2f} nM",
            f"Protein half-life: {t_half:.2f} hr",
            f"Response time (to 90% SS): ~{3.3 * t_half:.1f} hr",
        ]

        return SimulationResult(
            model_name=self.name,
            t=t,
            curves={"protein": sol},
            curve_labels={"protein": "Protein/mRNA Level"},
            curve_units={"protein": "nM"},
            t_unit="hours",
            annotations=annotations,
        )
