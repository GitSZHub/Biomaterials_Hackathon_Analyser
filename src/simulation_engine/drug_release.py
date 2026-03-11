"""
Drug Release Kinetics
======================
Models: zero-order, first-order, Korsmeyer-Peppas.
Output: cumulative release (%) vs time.
"""

from __future__ import annotations
from typing import Dict

import numpy as np

from .base_model import SimulationModel, Parameter, SimulationResult


class DrugReleaseModel(SimulationModel):
    name = "Drug Release Kinetics"
    description = (
        "Cumulative drug release from scaffold/nanoparticle. "
        "Supports zero-order, first-order, and Korsmeyer-Peppas models."
    )

    def get_parameters(self) -> Dict[str, Parameter]:
        return {
            "model_type": Parameter("Model type (0=zero, 1=first, 2=KP)", 2,
                                    0, 2, "", "Release kinetics model"),
            "k": Parameter("Release rate constant", 0.1, 0.001, 1.0, "1/day or 1/day^n",
                           "Rate constant for release"),
            "burst": Parameter("Burst fraction", 0.1, 0.0, 0.5, "",
                               "Fraction released in initial burst"),
            "n_kp": Parameter("KP diffusion exponent", 0.5, 0.3, 1.0, "",
                              "Korsmeyer-Peppas exponent (0.5=Fickian, 1.0=erosion)"),
            "drug_loading": Parameter("Drug loading", 100.0, 10.0, 1000.0, "ug",
                                      "Total drug loaded in carrier"),
        }

    def run(self, params: Dict[str, float], t_end: float = 30.0,
            n_points: int = 500) -> SimulationResult:
        p = {**self.get_defaults(), **params}
        t = np.linspace(0, t_end, n_points)
        model_type = int(round(p["model_type"]))

        # Calculate fractional release (0-1)
        if model_type == 0:
            # Zero-order: constant release rate
            release = p["burst"] + p["k"] * t
        elif model_type == 1:
            # First-order: exponential approach
            release = 1.0 - (1.0 - p["burst"]) * np.exp(-p["k"] * t)
        else:
            # Korsmeyer-Peppas: power law
            release = p["burst"] + p["k"] * np.power(np.maximum(t, 1e-10), p["n_kp"])

        # Clamp to 0-1
        release = np.clip(release, 0, 1)

        # Convert to percentage and absolute amount
        pct = release * 100.0
        amount = release * p["drug_loading"]

        model_names = {0: "Zero-order", 1: "First-order", 2: "Korsmeyer-Peppas"}
        annotations = [
            f"Model: {model_names.get(model_type, 'Unknown')}",
            f"Burst release: {p['burst']*100:.0f}%",
        ]
        # Time to 50% release
        idx_50 = np.searchsorted(pct, 50.0)
        if idx_50 < len(t):
            annotations.append(f"t50 (50% release): {t[idx_50]:.1f} days")
        # Time to 90% release
        idx_90 = np.searchsorted(pct, 90.0)
        if idx_90 < len(t):
            annotations.append(f"t90 (90% release): {t[idx_90]:.1f} days")

        return SimulationResult(
            model_name=self.name,
            t=t,
            curves={"release_pct": pct, "release_ug": amount},
            curve_labels={"release_pct": "Cumulative Release", "release_ug": "Drug Released"},
            curve_units={"release_pct": "%", "release_ug": "ug"},
            t_unit="days",
            annotations=annotations,
        )
