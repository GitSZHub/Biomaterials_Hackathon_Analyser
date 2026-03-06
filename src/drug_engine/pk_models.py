"""
PK / Release Models — Level 1-3 pharmacokinetic and drug-release models.

Level 1: First-order release (single compartment, exponential decay)
Level 2: Biphasic release (burst + sustained; two-compartment)
Level 3: Higuchi diffusion model (matrix-controlled, sqrt(t) kinetics)

All models return (time_array, concentration_array) tuples suitable for
direct plotting with matplotlib or Plotly.

Public API:
    from drug_engine.pk_models import PKLevel1, PKLevel2, PKLevel3, simulate_release

    model  = PKLevel1(dose=10.0, k_el=0.1)
    t, c   = model.simulate(t_max=48)

    result = simulate_release("higuchi", dose=10.0, D=0.01, A=50.0, t_max=24)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np


# ── Level 1: First-order (single compartment) ─────────────────────────────────

@dataclass
class PKLevel1:
    """
    First-order single-compartment model.

    C(t) = (Dose / Vd) * exp(-k_el * t)

    Args:
        dose:   initial dose in the compartment (mg)
        k_el:   elimination rate constant (1/h)
        vd:     volume of distribution (L); defaults to 1.0
        t_lag:  lag time before release starts (h)
    """
    dose:  float
    k_el:  float
    vd:    float = 1.0
    t_lag: float = 0.0

    def simulate(self, t_max: float = 24.0,
                 n_points: int = 200) -> Tuple[np.ndarray, np.ndarray]:
        """Return (t, C) arrays over [0, t_max] hours."""
        t = np.linspace(0, t_max, n_points)
        c = np.where(
            t >= self.t_lag,
            (self.dose / self.vd) * np.exp(-self.k_el * (t - self.t_lag)),
            0.0,
        )
        return t, c

    def half_life(self) -> float:
        """Return t½ in hours."""
        return math.log(2) / self.k_el if self.k_el > 0 else float("inf")

    def auc(self, t_max: float = float("inf")) -> float:
        """AUC from 0 to t_max (analytic solution)."""
        c0 = self.dose / self.vd
        if t_max == float("inf"):
            return c0 / self.k_el
        return (c0 / self.k_el) * (1 - math.exp(-self.k_el * (t_max - self.t_lag)))

    def summary(self) -> Dict:
        return {
            "model":     "First-order (Level 1)",
            "half_life": f"{self.half_life():.2f} h",
            "cmax":      f"{self.dose / self.vd:.3f} mg/L",
            "auc_inf":   f"{self.auc():.3f} mg·h/L",
        }


# ── Level 2: Biphasic (burst + sustained) ──────────────────────────────────────

@dataclass
class PKLevel2:
    """
    Biphasic two-phase release model.

    C(t) = C_burst * exp(-k_fast * t)  +  C_sustained * exp(-k_slow * t)

    Models scaffolds / nanoparticles with:
      - burst phase: rapid initial release of surface-adsorbed drug
      - sustained phase: diffusion-controlled slow release from matrix

    Args:
        dose:        total dose (mg)
        burst_frac:  fraction released in burst phase (0–1)
        k_fast:      burst phase rate constant (1/h)
        k_slow:      sustained phase rate constant (1/h)
        vd:          apparent volume of distribution (L)
    """
    dose:       float
    burst_frac: float = 0.3
    k_fast:     float = 1.0
    k_slow:     float = 0.05
    vd:         float = 1.0

    def simulate(self, t_max: float = 72.0,
                 n_points: int = 300) -> Tuple[np.ndarray, np.ndarray]:
        t   = np.linspace(0, t_max, n_points)
        c_b = (self.dose * self.burst_frac / self.vd) * np.exp(-self.k_fast * t)
        c_s = (self.dose * (1 - self.burst_frac) / self.vd) * np.exp(-self.k_slow * t)
        return t, c_b + c_s

    def burst_duration(self) -> float:
        """Time at which burst contribution falls below 5% of initial."""
        c0_burst = self.dose * self.burst_frac / self.vd
        if c0_burst <= 0 or self.k_fast <= 0:
            return 0.0
        return math.log(20) / self.k_fast   # exp(-k*t) = 0.05 → t = ln(20)/k

    def summary(self) -> Dict:
        return {
            "model":          "Biphasic burst+sustained (Level 2)",
            "burst_fraction": f"{self.burst_frac * 100:.0f}%",
            "burst_duration": f"{self.burst_duration():.1f} h",
            "t_half_fast":    f"{math.log(2) / self.k_fast:.2f} h" if self.k_fast else "∞",
            "t_half_slow":    f"{math.log(2) / self.k_slow:.2f} h" if self.k_slow else "∞",
        }


# ── Level 3: Higuchi diffusion model ──────────────────────────────────────────

@dataclass
class PKLevel3:
    """
    Higuchi matrix release model (diffusion-controlled).

    Q(t) = sqrt(D * (2A - Cs) * Cs * t)

    Where:
        D:  diffusion coefficient (cm²/h)
        A:  initial drug loading (mg/cm³)  — must be > Cs
        Cs: drug solubility in matrix (mg/cm³)

    Output: cumulative fraction released (0–1) over time.

    Args:
        dose:  total drug mass (mg) — used to convert Q → concentration
        D:     diffusion coefficient (cm²/h)
        A:     total drug loading in matrix (mg/cm³)
        Cs:    drug solubility in polymer matrix (mg/cm³)
        vd:    apparent volume (L) for converting to plasma concentration
    """
    dose: float
    D:    float = 1e-4    # cm²/h (typical hydrogel)
    A:    float = 100.0   # mg/cm³
    Cs:   float = 10.0    # mg/cm³
    vd:   float = 1.0

    def simulate(self, t_max: float = 168.0,
                 n_points: int = 300) -> Tuple[np.ndarray, np.ndarray]:
        """Return (t, cumulative_fraction_released) over [0, t_max] hours."""
        if self.A <= self.Cs:
            raise ValueError("A must be greater than Cs for Higuchi model")
        t = np.linspace(0, t_max, n_points)
        # Q in mg/cm²
        Q = np.sqrt(self.D * (2 * self.A - self.Cs) * self.Cs * t)
        # Normalise to fraction of total dose (approximate: Q_max = A * thickness)
        # For display, return cumulative fraction clipped at 1.0
        q_max = self.A   # when fully depleted
        frac = np.clip(Q / q_max, 0, 1)
        return t, frac

    def t90(self) -> float:
        """Time to 90% cumulative release (hours)."""
        q_target = 0.9 * self.A
        # Q = sqrt(D*(2A-Cs)*Cs*t) => t = Q²/(D*(2A-Cs)*Cs)
        return (q_target ** 2) / (self.D * (2 * self.A - self.Cs) * self.Cs)

    def summary(self) -> Dict:
        return {
            "model": "Higuchi diffusion (Level 3)",
            "D":     f"{self.D:.2e} cm²/h",
            "A":     f"{self.A:.1f} mg/cm³",
            "Cs":    f"{self.Cs:.1f} mg/cm³",
            "t90":   f"{self.t90():.1f} h",
        }


# ── Convenience dispatcher ─────────────────────────────────────────────────────

def simulate_release(model_type: str, **kwargs) -> Tuple[np.ndarray, np.ndarray]:
    """
    Convenience function to run any PK model by name.

    Args:
        model_type: "first_order" | "biphasic" | "higuchi"
        **kwargs:   passed directly to the model dataclass constructor +
                    t_max (float) and n_points (int) for simulate()

    Returns:
        (t, c) arrays
    """
    t_max    = kwargs.pop("t_max",    72.0)
    n_points = kwargs.pop("n_points", 300)

    model_map = {
        "first_order": PKLevel1,
        "biphasic":    PKLevel2,
        "higuchi":     PKLevel3,
    }
    cls = model_map.get(model_type)
    if cls is None:
        raise ValueError(f"Unknown model_type: {model_type!r}. "
                         f"Choose from {list(model_map)}")
    model = cls(**kwargs)
    return model.simulate(t_max=t_max, n_points=n_points)


def fit_higuchi(time: np.ndarray,
                cumulative_fraction: np.ndarray) -> Dict:
    """
    Fit the Higuchi model to experimental release data using least-squares.

    Args:
        time:                 time array (h)
        cumulative_fraction:  measured cumulative release (0–1)

    Returns:
        dict with: k_higuchi (Higuchi rate constant), r_squared, t90_pred
        The Higuchi equation simplifies to: F = k * sqrt(t)
    """
    sqrt_t = np.sqrt(time[1:])          # skip t=0 to avoid zero
    frac   = cumulative_fraction[1:]

    # Linear regression: F ~ k * sqrt(t)
    # Using numpy least squares: k = (sqrt_t · frac) / (sqrt_t · sqrt_t)
    if len(sqrt_t) < 2 or np.sum(sqrt_t ** 2) == 0:
        return {"k_higuchi": 0.0, "r_squared": 0.0, "t90_pred": float("inf")}

    k = float(np.dot(sqrt_t, frac) / np.dot(sqrt_t, sqrt_t))
    frac_pred = k * sqrt_t
    ss_res = float(np.sum((frac - frac_pred) ** 2))
    ss_tot = float(np.sum((frac - frac.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

    # t90: k*sqrt(t) = 0.9 → t = (0.9/k)²
    t90 = (0.9 / k) ** 2 if k > 0 else float("inf")

    return {
        "k_higuchi": round(k, 6),
        "r_squared": round(r2, 4),
        "t90_pred":  round(t90, 2),
    }
