"""
Polymer Degradation Models
===========================
ODE-based models for hydrolytic and enzymatic degradation of biodegradable
polymers commonly used in biomaterials.

Supported materials / models:
  - PLGA  — autocatalytic hydrolytic degradation (Batycky et al., 1997)
  - PLA   — simple first-order hydrolysis
  - PCL   — slow first-order hydrolysis (low k)
  - Chitosan — enzymatic degradation (Michaelis-Menten kinetics)
  - Alginate — ionic cross-link erosion

Usage:
    from simulation_engine.degradation_models import DegradationModel, run_degradation

    t, mw, mass = run_degradation("PLGA", days=90, initial_mw=50000)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ── Material parameter presets ─────────────────────────────────────────────────

MATERIAL_PRESETS: Dict[str, Dict] = {
    "PLGA (50:50)": {
        "model":        "autocatalytic",
        "k_h":          0.025,      # hydrolysis rate constant (1/day) — Mn halves ~28 d
        "k_cat":        2.5,        # autocatalytic amplification factor
        "k_e":          0.018,      # mass erosion rate
        "initial_mw":   50_000,     # Da
        "description":  "PLGA 50:50 — bulk-eroding, fastest degradation (~6 wk to fragment)",
        "citation":     "Batycky et al. (1997) J Pharm Sci 86(12):1464",
    },
    "PLGA (75:25)": {
        "model":        "autocatalytic",
        "k_h":          0.012,
        "k_cat":        2.0,
        "k_e":          0.010,
        "initial_mw":   80_000,
        "description":  "PLGA 75:25 — moderate degradation (~3-4 months)",
        "citation":     "Batycky et al. (1997)",
    },
    "PLA": {
        "model":        "first_order",
        "k_h":          0.004,      # ~6-month half-life
        "k_cat":        0.0,
        "k_e":          0.003,
        "initial_mw":   100_000,
        "description":  "Poly(lactic acid) — slow hydrolytic degradation (~1-2 yr)",
        "citation":     "Li (1999) Biomaterials 20:35",
    },
    "PCL": {
        "model":        "first_order",
        "k_h":          0.0005,     # ~3-year half-life
        "k_cat":        0.0,
        "k_e":          0.0002,
        "initial_mw":   80_000,
        "description":  "Polycaprolactone — very slow degradation (2-3 years)",
        "citation":     "Woodruff & Hutmacher (2010) Prog Polym Sci 35:1",
    },
    "Chitosan": {
        "model":        "enzymatic",
        "v_max":        0.035,      # maximum enzymatic rate (fraction/day)
        "k_m":          0.4,        # Michaelis constant (fraction remaining)
        "k_h":          0.001,      # background hydrolysis
        "k_e":          0.012,
        "initial_mw":   200_000,
        "description":  "Chitosan — lysozyme-mediated enzymatic degradation",
        "citation":     "Nordtveit et al. (1994) Carbohydr Polym 23:253",
    },
    "Alginate": {
        "model":        "ionic_erosion",
        "k_dissoc":     0.05,       # ionic cross-link dissociation rate
        "k_h":          1e-6,
        "k_e":          0.03,
        "initial_mw":   120_000,
        "description":  "Alginate hydrogel — ionic cross-link dissociation",
        "citation":     "Lee & Mooney (2012) Prog Polym Sci 37:106",
    },
}


@dataclass
class DegradationResult:
    """Results from a degradation simulation."""
    material:       str
    model_type:     str
    t_days:         np.ndarray          # time axis (days)
    mw:             np.ndarray          # number-average molecular weight (Da)
    mass_remaining: np.ndarray          # fraction of mass remaining (0–1)
    mw_critical:    float = 5_000.0     # Da — below this the polymer is fragmented
    notes:          List[str] = field(default_factory=list)

    @property
    def fragmentation_day(self) -> Optional[float]:
        """Day when Mn drops below critical MW."""
        idx = np.where(self.mw <= self.mw_critical)[0]
        return float(self.t_days[idx[0]]) if len(idx) else None

    @property
    def half_life_day(self) -> Optional[float]:
        """Day when 50 % of mass is lost."""
        idx = np.where(self.mass_remaining <= 0.5)[0]
        return float(self.t_days[idx[0]]) if len(idx) else None

    def to_dict(self) -> dict:
        return {
            "material":          self.material,
            "model_type":        self.model_type,
            "fragmentation_day": self.fragmentation_day,
            "half_life_day":     self.half_life_day,
            "final_mass_frac":   float(self.mass_remaining[-1]),
        }


@dataclass
class DegradationModel:
    """
    Configure and run a polymer degradation simulation.

    Parameters
    ----------
    material : str
        Name matching a key in MATERIAL_PRESETS, or "Custom".
    days : int
        Simulation duration in days.
    initial_mw : float, optional
        Override the preset initial Mn (Da).
    ph : float
        Effective local pH (modulates k_h by ±20 % per unit from 7.4).
    temperature : float
        Kelvin — Arrhenius correction (Ea = 75 kJ/mol assumed).
    custom_params : dict, optional
        Full override of preset params for "Custom" material.
    """

    material:      str   = "PLGA (50:50)"
    days:          int   = 90
    initial_mw:    float = 0.0        # 0 = use preset
    ph:            float = 7.4
    temperature:   float = 310.15     # 37 °C
    custom_params: Optional[Dict] = None

    # ── Public ────────────────────────────────────────────────────────────────

    def run(self) -> DegradationResult:
        params = self._resolve_params()
        model  = params["model"]
        t      = np.linspace(0, self.days, self.days * 4 + 1)
        mw0    = float(self.initial_mw) if self.initial_mw > 0 else params["initial_mw"]

        k_h = self._corrected_k(params["k_h"])

        if model == "autocatalytic":
            mw, mass = self._autocatalytic(t, mw0, k_h, params)
        elif model == "first_order":
            mw, mass = self._first_order(t, mw0, k_h, params)
        elif model == "enzymatic":
            mw, mass = self._enzymatic(t, mw0, k_h, params)
        elif model == "ionic_erosion":
            mw, mass = self._ionic_erosion(t, mw0, k_h, params)
        else:
            raise ValueError(f"Unknown degradation model: {model}")

        notes = [
            f"pH correction applied: {self.ph:.1f} (ref 7.4)",
            f"Temperature: {self.temperature - 273.15:.1f} °C",
        ]
        if params.get("citation"):
            notes.append(f"Model ref: {params['citation']}")

        return DegradationResult(
            material=self.material,
            model_type=model,
            t_days=t,
            mw=mw,
            mass_remaining=mass,
            notes=notes,
        )

    # ── Models ────────────────────────────────────────────────────────────────

    def _autocatalytic(self, t, mw0, k_h, p) -> Tuple[np.ndarray, np.ndarray]:
        """
        Batycky autocatalytic PLGA degradation.
        dMn/dt = -k_h * Mn * (1 + k_cat * (1 - Mn/Mn0))
        Mass loss coupled via cumulative acid production.
        """
        k_cat = p["k_cat"]
        k_e   = p["k_e"]
        mw    = np.zeros_like(t)
        mw[0] = mw0
        for i in range(1, len(t)):
            dt = t[i] - t[i - 1]
            autocatalytic_term = 1.0 + k_cat * (1.0 - mw[i - 1] / mw0)
            dMw = -k_h * mw[i - 1] * autocatalytic_term
            mw[i] = max(100.0, mw[i - 1] + dMw * dt)

        # Mass erosion: sigmoidal onset after fragmentation threshold
        deg_frac = np.clip(1.0 - mw / mw0, 0, 1)
        mass = np.exp(-k_e * t * deg_frac)
        return mw, np.clip(mass, 0, 1)

    def _first_order(self, t, mw0, k_h, p) -> Tuple[np.ndarray, np.ndarray]:
        """Simple first-order hydrolysis: Mn(t) = Mn0 * exp(-k_h * t)."""
        k_e  = p["k_e"]
        mw   = mw0 * np.exp(-k_h * t)
        mass = np.exp(-k_e * t * (1.0 - mw / mw0))
        return mw, np.clip(mass, 0, 1)

    def _enzymatic(self, t, mw0, k_h, p) -> Tuple[np.ndarray, np.ndarray]:
        """
        Michaelis-Menten enzymatic degradation (lysozyme on chitosan).
        dS/dt = -v_max * S / (k_m + S)  where S = normalised mass
        """
        v_max = p["v_max"]
        k_m   = p["k_m"]
        k_e   = p["k_e"]
        S     = np.zeros_like(t)
        S[0]  = 1.0
        for i in range(1, len(t)):
            dt   = t[i] - t[i - 1]
            dS   = -(v_max * S[i - 1]) / (k_m + S[i - 1])
            dS  -= k_h * S[i - 1]          # background hydrolysis
            S[i] = max(0.0, S[i - 1] + dS * dt)

        mw   = mw0 * S
        mass = S
        return mw, mass

    def _ionic_erosion(self, t, mw0, k_h, p) -> Tuple[np.ndarray, np.ndarray]:
        """
        Alginate: ionic cross-link dissociation leads to bulk swelling then erosion.
        Cross-link density: C(t) = C0 * exp(-k_dissoc * t)
        Swelling / mass loss proportional to lost cross-links.
        """
        k_d  = p["k_dissoc"]
        k_e  = p["k_e"]
        C    = np.exp(-k_d * t)             # normalised cross-link density
        mass = C + (1.0 - C) * np.exp(-k_e * t)
        mw   = mw0 * mass
        return np.clip(mw, 100, None), np.clip(mass, 0, 1)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _resolve_params(self) -> Dict:
        if self.material == "Custom" and self.custom_params:
            return self.custom_params
        if self.material not in MATERIAL_PRESETS:
            raise ValueError(
                f"Unknown material '{self.material}'. "
                f"Choose from: {list(MATERIAL_PRESETS)}"
            )
        return dict(MATERIAL_PRESETS[self.material])

    def _corrected_k(self, k_base: float) -> float:
        """Apply pH and Arrhenius temperature corrections to a rate constant."""
        # pH: assume k ∝ [H+]^0.5 near neutral — ±20 % per unit from 7.4
        ph_factor = 10 ** (0.2 * (7.4 - self.ph))

        # Arrhenius: Ea ≈ 75 kJ/mol for ester hydrolysis, ref T = 310.15 K
        Ea, R = 75_000.0, 8.314
        T_ref = 310.15
        arrhenius = np.exp(-Ea / R * (1.0 / self.temperature - 1.0 / T_ref))

        return k_base * ph_factor * arrhenius


# ── Convenience function ───────────────────────────────────────────────────────

def run_degradation(
    material: str = "PLGA (50:50)",
    days:     int = 90,
    **kwargs,
) -> DegradationResult:
    """
    One-liner helper.

    Returns
    -------
    DegradationResult with .t_days, .mw, .mass_remaining arrays.
    """
    return DegradationModel(material=material, days=days, **kwargs).run()
