"""
Tissue Inflammatory Response
==============================
Semi-empirical ODE: acute inflammation -> resolution -> integration.
Output: inflammation index + integration index vs weeks post-implant.
"""

from __future__ import annotations
from typing import Dict

import numpy as np
from scipy.integrate import odeint

from .base_model import SimulationModel, Parameter, SimulationResult


class TissueResponseModel(SimulationModel):
    name = "Tissue Inflammatory Response"
    description = (
        "ODE model of the foreign body response. Tracks inflammation "
        "and tissue integration indices over weeks post-implantation."
    )

    def get_parameters(self) -> Dict[str, Parameter]:
        return {
            "biocompat": Parameter("Biocompatibility score", 70.0, 0.0, 100.0, "",
                                   "Material biocompatibility (0-100). Higher = less inflammation."),
            "k_deg": Parameter("Degradation rate", 0.05, 0.0, 0.5, "1/week",
                               "Scaffold degradation rate (debris drives inflammation)"),
            "k_vasc": Parameter("Vascularisation rate", 0.1, 0.01, 0.5, "1/week",
                                "Rate of new vessel formation (promotes resolution)"),
            "fbr_intensity": Parameter("FBR intensity", 0.5, 0.0, 2.0, "",
                                       "Foreign body response intensity (material-dependent)"),
            "resolution_rate": Parameter("Resolution rate", 0.15, 0.01, 0.5, "1/week",
                                         "M1->M2 macrophage transition rate"),
            "I0": Parameter("Initial inflammation", 0.8, 0.1, 1.0, "",
                            "Acute inflammation level at t=0 (surgical trauma)"),
        }

    def run(self, params: Dict[str, float], t_end: float = 24.0,
            n_points: int = 500) -> SimulationResult:
        p = {**self.get_defaults(), **params}
        t = np.linspace(0, t_end, n_points)

        # Biocompatibility modulates inflammation: higher score = faster resolution
        biocompat_factor = p["biocompat"] / 100.0

        def odes(y, t_val):
            I, G = y  # I = inflammation, G = integration (0-1 each)

            # Degradation debris drives inflammation
            debris = p["k_deg"] * np.exp(-p["k_deg"] * t_val)

            # Inflammation dynamics
            # Driven by debris + FBR, resolved by M2 transition + biocompatibility
            dIdt = (
                p["fbr_intensity"] * debris
                - p["resolution_rate"] * biocompat_factor * I
                - 0.05 * I * G  # integration suppresses inflammation
            )

            # Integration dynamics
            # Driven by vascularisation + resolution, suppressed by inflammation
            dGdt = (
                p["k_vasc"] * (1 - G) * biocompat_factor
                - 0.3 * I * G  # inflammation hinders integration
            )

            return [dIdt, dGdt]

        y0 = [p["I0"], 0.0]
        sol = odeint(odes, y0, t)
        I = np.clip(sol[:, 0], 0, None)
        G = np.clip(sol[:, 1], 0, 1)

        # Find key timepoints
        annotations = []

        # Peak inflammation
        peak_idx = np.argmax(I)
        annotations.append(f"Peak inflammation: {I[peak_idx]:.2f} at week {t[peak_idx]:.1f}")

        # Time to inflammation < 0.1 (resolved)
        resolved = np.where(I < 0.1)[0]
        if len(resolved) > 0 and resolved[0] > 0:
            annotations.append(f"Inflammation resolves (<0.1) at week {t[resolved[0]]:.1f}")
        elif I[-1] >= 0.1:
            annotations.append("WARNING: Inflammation not resolved by end of simulation")

        # Final integration level
        annotations.append(f"Final integration index: {G[-1]:.2f}")
        if G[-1] > 0.7:
            annotations.append("Outcome: GOOD INTEGRATION (>0.7)")
        elif G[-1] > 0.4:
            annotations.append("Outcome: PARTIAL INTEGRATION (0.4-0.7)")
        else:
            annotations.append("Outcome: POOR INTEGRATION / ENCAPSULATION (<0.4)")

        return SimulationResult(
            model_name=self.name,
            t=t,
            curves={"inflammation": I, "integration": G},
            curve_labels={"inflammation": "Inflammation Index",
                          "integration": "Integration Index"},
            curve_units={"inflammation": "", "integration": ""},
            t_unit="weeks",
            annotations=annotations,
        )
