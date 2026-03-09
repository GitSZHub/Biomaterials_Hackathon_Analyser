"""
Drug Release Kinetic Models
============================
Standard pharmacokinetic / drug-delivery models for controlled-release
biomaterials. No external dependencies beyond numpy.

Models implemented
------------------
  Zero order      — constant release rate (membrane-controlled systems)
  First order     — rate proportional to remaining drug (porous matrices)
  Higuchi         — diffusion from matrix (√t relationship)
  Korsmeyer-Peppas— power-law; exponent n distinguishes Fickian vs anomalous
  Weibull         — general empirical fit
  Hixson-Crowell  — surface erosion (sphere / cube root model)
  Biexponential   — burst + sustained phases (drug-loaded NPs)

Usage:
    from simulation_engine.drug_release import run_drug_release

    t, Q, params = run_drug_release("Korsmeyer-Peppas", hours=72,
                                    initial_dose=10.0, n=0.45)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ── Model metadata ─────────────────────────────────────────────────────────────

MODEL_INFO: Dict[str, Dict[str, Any]] = {
    "Zero Order": {
        "params":      {"k0": 0.05},        # fraction/hour
        "description": "Constant release — membrane-controlled reservoir systems.",
        "exponent_n":  None,
        "citation":    "Baker & Lonsdale (1974)",
    },
    "First Order": {
        "params":      {"k1": 0.05},        # 1/hour
        "description": "Rate proportional to remaining drug — porous matrices.",
        "exponent_n":  None,
        "citation":    "Wagner (1969)",
    },
    "Higuchi": {
        "params":      {"k_H": 0.12},       # fraction/√hour
        "description": "Matrix diffusion — Q ∝ √t. Fickian diffusion from slab.",
        "exponent_n":  0.5,
        "citation":    "Higuchi (1961) J Pharm Sci 50:874",
    },
    "Korsmeyer-Peppas": {
        "params":      {"k_KP": 0.10, "n": 0.45},
        "description": (
            "Power-law Q/Q∞ = k·tⁿ. "
            "n≤0.5: Fickian diffusion; 0.5<n<1: anomalous; n=1: Case II."
        ),
        "exponent_n":  0.45,
        "citation":    "Korsmeyer et al. (1983) Int J Pharm 15:25",
    },
    "Weibull": {
        "params":      {"a": 0.03, "b": 0.75},
        "description": "Empirical cumulative release Q = 1 - exp(-a·tᵇ).",
        "exponent_n":  None,
        "citation":    "Weibull (1951); Papadopoulou et al. (2006)",
    },
    "Hixson-Crowell": {
        "params":      {"k_HC": 0.02},
        "description": "Erosion of spherical particles — cube-root law.",
        "exponent_n":  None,
        "citation":    "Hixson & Crowell (1931) Ind Eng Chem 23:923",
    },
    "Biexponential (burst + sustained)": {
        "params":      {"A1": 0.40, "k1": 0.30, "A2": 0.60, "k2": 0.008},
        "description": (
            "Biphasic: burst release (A1, fast k1) + "
            "sustained (A2, slow k2). Typical of NPs / microparticles."
        ),
        "exponent_n":  None,
        "citation":    "Raman et al. (2005) J Control Release 103:149",
    },
}


@dataclass
class DrugReleaseResult:
    """Results from a drug release simulation."""
    model_name:     str
    t_hours:        np.ndarray      # time axis (hours)
    Q_fraction:     np.ndarray      # cumulative release fraction (0–1)
    Q_amount:       np.ndarray      # cumulative release amount (same units as initial_dose)
    initial_dose:   float           # µg or mg — user-supplied
    params_used:    Dict[str, Any]  # actual parameter values used
    notes:          List[str] = field(default_factory=list)

    @property
    def t50_hours(self) -> Optional[float]:
        """Time to 50 % release."""
        idx = np.where(self.Q_fraction >= 0.50)[0]
        return float(self.t_hours[idx[0]]) if len(idx) else None

    @property
    def t80_hours(self) -> Optional[float]:
        """Time to 80 % release."""
        idx = np.where(self.Q_fraction >= 0.80)[0]
        return float(self.t_hours[idx[0]]) if len(idx) else None

    @property
    def burst_fraction_1h(self) -> float:
        """Fraction released within the first hour (burst index)."""
        idx = np.where(self.t_hours >= 1.0)[0]
        return float(self.Q_fraction[idx[0]]) if len(idx) else 0.0

    def to_dict(self) -> dict:
        return {
            "model":          self.model_name,
            "t50_hours":      self.t50_hours,
            "t80_hours":      self.t80_hours,
            "burst_1h":       self.burst_fraction_1h,
            "final_release":  float(self.Q_fraction[-1]),
            "params":         self.params_used,
        }


@dataclass
class DrugReleaseModel:
    """
    Configure and run a drug release simulation.

    Parameters
    ----------
    model_name : str
        One of the keys in MODEL_INFO (or "Custom").
    hours : int
        Simulation duration in hours.
    initial_dose : float
        Total drug loaded (e.g. µg or mg — units preserved in output).
    custom_params : dict, optional
        Override default model parameters (e.g. {"n": 0.7, "k_KP": 0.08}).
    """

    model_name:    str   = "Korsmeyer-Peppas"
    hours:         int   = 72
    initial_dose:  float = 100.0    # µg
    custom_params: Optional[Dict[str, Any]] = None

    def run(self) -> DrugReleaseResult:
        if self.model_name not in MODEL_INFO:
            raise ValueError(
                f"Unknown model '{self.model_name}'. "
                f"Choose from: {list(MODEL_INFO)}"
            )
        info   = MODEL_INFO[self.model_name]
        params = dict(info["params"])
        if self.custom_params:
            params.update(self.custom_params)

        t = np.linspace(0, self.hours, self.hours * 4 + 1)
        Q = self._compute(t, params)

        notes = [f"Model: {self.model_name}"]
        if info.get("citation"):
            notes.append(f"Reference: {info['citation']}")
        if info.get("description"):
            notes.append(info["description"])

        return DrugReleaseResult(
            model_name=self.model_name,
            t_hours=t,
            Q_fraction=Q,
            Q_amount=Q * self.initial_dose,
            initial_dose=self.initial_dose,
            params_used=params,
            notes=notes,
        )

    # ── Model implementations ─────────────────────────────────────────────────

    def _compute(self, t: np.ndarray, p: Dict) -> np.ndarray:
        name = self.model_name
        if name == "Zero Order":
            Q = np.minimum(p["k0"] * t, 1.0)

        elif name == "First Order":
            Q = 1.0 - np.exp(-p["k1"] * t)

        elif name == "Higuchi":
            Q = np.minimum(p["k_H"] * np.sqrt(t), 1.0)

        elif name == "Korsmeyer-Peppas":
            n    = p["n"]
            k_KP = p["k_KP"]
            # Only valid for Q/Q∞ ≤ 0.60 strictly; extrapolate beyond
            Q = np.minimum(k_KP * (t ** n), 1.0)

        elif name == "Weibull":
            a, b = p["a"], p["b"]
            Q = 1.0 - np.exp(-a * (t ** b))

        elif name == "Hixson-Crowell":
            k_HC = p["k_HC"]
            # Q = 1 - (1 - k_HC * t)^3 — clamp to [0,1]
            inner = np.maximum(1.0 - k_HC * t, 0.0)
            Q = 1.0 - inner ** 3

        elif name == "Biexponential (burst + sustained)":
            A1, k1 = p["A1"], p["k1"]
            A2, k2 = p["A2"], p["k2"]
            Q = A1 * (1.0 - np.exp(-k1 * t)) + A2 * (1.0 - np.exp(-k2 * t))
            Q = np.minimum(Q, 1.0)

        else:
            raise ValueError(f"No implementation for model: {name}")

        return np.clip(Q, 0.0, 1.0)


# ── Convenience function ───────────────────────────────────────────────────────

def run_drug_release(
    model_name:   str   = "Korsmeyer-Peppas",
    hours:        int   = 72,
    initial_dose: float = 100.0,
    **custom_params,
) -> DrugReleaseResult:
    """
    One-liner helper.

    Example
    -------
    result = run_drug_release("Korsmeyer-Peppas", hours=72, n=0.6)
    plt.plot(result.t_hours, result.Q_fraction)
    """
    cp = custom_params if custom_params else None
    return DrugReleaseModel(
        model_name=model_name,
        hours=hours,
        initial_dose=initial_dose,
        custom_params=cp,
    ).run()
