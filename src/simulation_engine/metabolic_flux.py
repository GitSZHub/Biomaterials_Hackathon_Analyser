"""
Metabolic Flux (simplified)
============================
Altered gene expression -> changed enzyme levels -> pathway flux shift.
Models relative flux through metabolic nodes after a perturbation.
"""

from __future__ import annotations
from typing import Dict

import numpy as np
from scipy.integrate import odeint

from .base_model import SimulationModel, Parameter, SimulationResult


class MetabolicFluxModel(SimulationModel):
    name = "Metabolic Flux (simplified)"
    description = (
        "Models how a gene expression change (e.g. from CRISPR edit) "
        "alters enzyme levels and shifts metabolic pathway flux."
    )

    def get_parameters(self) -> Dict[str, Parameter]:
        return {
            "baseline_flux": Parameter("Baseline flux", 1.0, 0.1, 10.0, "a.u.",
                                       "Normal pathway flux (arbitrary units)"),
            "fold_change": Parameter("Enzyme fold-change", 2.0, 0.1, 10.0, "x",
                                     "Fold-change in enzyme level from gene edit"),
            "enzyme_response_time": Parameter("Enzyme response time", 6.0, 1.0, 48.0, "hr",
                                              "Time constant for enzyme level change"),
            "flux_sensitivity": Parameter("Flux sensitivity", 0.7, 0.1, 1.0, "",
                                          "Flux control coefficient (0-1, how much enzyme change affects flux)"),
            "feedback_strength": Parameter("Feedback strength", 0.2, 0.0, 1.0, "",
                                           "Product inhibition feedback (0=none, 1=strong)"),
            "pathway_type": Parameter("Pathway (0=series, 1=branch)", 0, 0, 1, "",
                                      "Series pathway (bottleneck) vs branched (distributed)"),
        }

    def run(self, params: Dict[str, float], t_end: float = 72.0,
            n_points: int = 500) -> SimulationResult:
        p = {**self.get_defaults(), **params}
        t = np.linspace(0, t_end, n_points)

        is_branched = int(round(p["pathway_type"]))

        def odes(y, t_val):
            E, F, P = y  # E=enzyme level, F=flux, P=product

            # Enzyme level changes with time constant
            E_target = p["fold_change"]
            tau = p["enzyme_response_time"]
            dEdt = (E_target - E) / tau

            # Flux depends on enzyme level and feedback
            if is_branched:
                # Branched: flux distributed, less sensitive to single enzyme
                flux_target = p["baseline_flux"] * (E ** (p["flux_sensitivity"] * 0.5))
            else:
                # Series: bottleneck, more sensitive
                flux_target = p["baseline_flux"] * (E ** p["flux_sensitivity"])

            # Product feedback inhibition
            feedback = 1.0 / (1.0 + p["feedback_strength"] * P)
            flux_target *= feedback

            dFdt = (flux_target - F) / 2.0  # flux adjusts with lag

            # Product accumulates from flux, cleared with first-order kinetics
            dPdt = F - 0.1 * P

            return [dEdt, dFdt, dPdt]

        y0 = [1.0, p["baseline_flux"], p["baseline_flux"] / 0.1]
        sol = odeint(odes, y0, t)
        E = sol[:, 0]
        F = sol[:, 1]
        P = sol[:, 2]

        # Relative flux
        F_rel = F / p["baseline_flux"]

        pathway_label = "Branched" if is_branched else "Series"
        annotations = [
            f"Pathway type: {pathway_label}",
            f"Enzyme fold-change: {p['fold_change']:.1f}x",
            f"Final relative flux: {F_rel[-1]:.2f}x baseline",
            f"Final enzyme level: {E[-1]:.2f}x",
        ]
        if F_rel[-1] > 1.5:
            annotations.append("Significant flux INCREASE detected")
        elif F_rel[-1] < 0.67:
            annotations.append("Significant flux DECREASE detected")

        return SimulationResult(
            model_name=self.name,
            t=t,
            curves={
                "enzyme": E,
                "relative_flux": F_rel,
                "product": P / (p["baseline_flux"] / 0.1),  # normalise
            },
            curve_labels={
                "enzyme": "Enzyme Level (fold)",
                "relative_flux": "Relative Flux",
                "product": "Product Level (fold)",
            },
            curve_units={
                "enzyme": "x baseline",
                "relative_flux": "x baseline",
                "product": "x baseline",
            },
            t_unit="hours",
            annotations=annotations,
        )
