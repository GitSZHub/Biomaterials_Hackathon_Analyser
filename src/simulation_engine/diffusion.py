"""
Scaffold Diffusion (Fick's Law)
================================
1D steady-state and transient diffusion-reaction in a scaffold.
Identifies hypoxic core thickness for thick constructs.
"""

from __future__ import annotations
from typing import Dict

import numpy as np

from .base_model import SimulationModel, Parameter, SimulationResult


class DiffusionModel(SimulationModel):
    name = "Scaffold Diffusion (Fick's Law)"
    description = (
        "1D diffusion-reaction in a scaffold slab. Models oxygen or glucose "
        "penetration depth. Identifies hypoxic core in thick constructs."
    )

    def get_parameters(self) -> Dict[str, Parameter]:
        return {
            "D": Parameter("Diffusion coefficient", 2.0e-5, 1e-6, 1e-4, "cm2/s",
                           "Effective diffusivity in scaffold"),
            "R": Parameter("Consumption rate", 5.0e-8, 1e-9, 1e-6, "mol/cm3/s",
                           "Cell metabolic consumption rate"),
            "C0": Parameter("Surface concentration", 0.2, 0.01, 0.5, "mM",
                            "Concentration at scaffold surface (ambient)"),
            "L": Parameter("Scaffold thickness", 0.5, 0.05, 5.0, "mm",
                           "Total scaffold thickness (half-slab if symmetric)"),
            "cell_density": Parameter("Cell density", 1e6, 1e4, 1e8, "cells/cm3",
                                      "Volumetric cell density (scales consumption)"),
        }

    def run(self, params: Dict[str, float], t_end: float = 1.0,
            n_points: int = 200) -> SimulationResult:
        p = {**self.get_defaults(), **params}

        # Convert L from mm to cm
        L_cm = p["L"] / 10.0

        # Spatial grid (depth into scaffold)
        x = np.linspace(0, L_cm, n_points)  # cm

        # Effective consumption rate (scales with cell density relative to 1e6)
        R_eff = p["R"] * (p["cell_density"] / 1e6)

        # Steady-state analytical solution for diffusion-reaction in a slab
        # d2C/dx2 = R/D  (zero-order consumption)
        # C(0) = C0, dC/dx(L) = 0 (symmetric at centre)
        # C(x) = C0 - (R/2D) * x * (2L - x)
        C = p["C0"] - (R_eff / (2 * p["D"])) * x * (2 * L_cm - x)
        C = np.maximum(C, 0)  # concentration can't be negative

        # Convert x back to mm for display
        x_mm = x * 10.0

        # Find penetration depth (where C drops to 10% of C0)
        threshold = 0.1 * p["C0"]
        below = np.where(C < threshold)[0]
        if len(below) > 0:
            pen_depth = x_mm[below[0]]
        else:
            pen_depth = p["L"]

        # Hypoxic core
        hypoxic = np.where(C < 0.01)[0]  # effectively zero
        if len(hypoxic) > 0:
            hypoxic_start = x_mm[hypoxic[0]]
            core_pct = (p["L"] - hypoxic_start) / p["L"] * 100
        else:
            hypoxic_start = p["L"]
            core_pct = 0

        annotations = [
            f"Penetration depth (to 10% surface): {pen_depth:.2f} mm",
            f"Centre concentration: {C[-1]:.4f} mM ({C[-1]/p['C0']*100:.1f}% of surface)",
        ]
        if core_pct > 0:
            annotations.append(
                f"HYPOXIC CORE: starts at {hypoxic_start:.2f} mm "
                f"({core_pct:.0f}% of scaffold is hypoxic)"
            )
        else:
            annotations.append("No hypoxic core -- oxygen penetrates full thickness")

        # Critical thickness (where centre concentration = 0)
        L_crit_cm = np.sqrt(2 * p["D"] * p["C0"] / R_eff) if R_eff > 0 else float("inf")
        L_crit_mm = L_crit_cm * 10.0
        annotations.append(f"Critical thickness (max before hypoxia): {L_crit_mm:.2f} mm")

        return SimulationResult(
            model_name=self.name,
            t=x_mm,  # spatial axis (depth in mm)
            curves={"concentration": C},
            curve_labels={"concentration": "O2/Glucose Concentration"},
            curve_units={"concentration": "mM"},
            t_unit="depth (mm)",
            annotations=annotations,
        )
