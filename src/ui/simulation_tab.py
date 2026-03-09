"""
Simulation Tab — Polymer Degradation & Drug Release
======================================================
Two sub-tabs:
  1. Polymer Degradation  — ODE-based MW + mass-loss curves
  2. Drug Release Kinetics — cumulative release for 7 standard models

All computation in background QThread — UI never blocks.
No external deps beyond numpy + matplotlib (already in requirements).
"""

from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
import qtawesome as qta

logger = logging.getLogger(__name__)

# ── Matplotlib canvas ─────────────────────────────────────────────────────────

try:
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    MPL_OK = True
except ImportError:
    MPL_OK = False


class _MplCanvas(QWidget):
    """Thin wrapper around a matplotlib Figure embedded in Qt."""

    def __init__(self, parent=None, nrows: int = 1, ncols: int = 1):
        super().__init__(parent)
        if not MPL_OK:
            lbl = QLabel("matplotlib not installed — pip install matplotlib")
            QVBoxLayout(self).addWidget(lbl)
            self.axes = None
            self.canvas = None
            return

        self.fig    = Figure(figsize=(6, 4), tight_layout=True)
        self.axes   = self.fig.subplots(nrows, ncols, squeeze=True)
        self.canvas = FigureCanvas(self.fig)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)

    def draw(self):
        if self.canvas:
            self.canvas.draw()

    def clear_axes(self):
        if self.axes is None:
            return
        if hasattr(self.axes, "__iter__"):
            for ax in self.axes:
                ax.cla()
        else:
            self.axes.cla()


# ── Worker threads ─────────────────────────────────────────────────────────────

class _DegradationWorker(QThread):
    finished = pyqtSignal(object)   # DegradationResult
    error    = pyqtSignal(str)

    def __init__(self, material, days, ph, temperature):
        super().__init__()
        self.material    = material
        self.days        = days
        self.ph          = ph
        self.temperature = temperature

    def run(self):
        try:
            from simulation_engine.degradation_models import DegradationModel
            result = DegradationModel(
                material=self.material,
                days=self.days,
                ph=self.ph,
                temperature=self.temperature,
            ).run()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class _ReleaseWorker(QThread):
    finished = pyqtSignal(object)   # DrugReleaseResult
    error    = pyqtSignal(str)

    def __init__(self, model_name, hours, initial_dose, custom_params):
        super().__init__()
        self.model_name    = model_name
        self.hours         = hours
        self.initial_dose  = initial_dose
        self.custom_params = custom_params

    def run(self):
        try:
            from simulation_engine.drug_release import DrugReleaseModel
            result = DrugReleaseModel(
                model_name=self.model_name,
                hours=self.hours,
                initial_dose=self.initial_dose,
                custom_params=self.custom_params,
            ).run()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


# ── Degradation sub-tab ────────────────────────────────────────────────────────

class _DegradationWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: Optional[_DegradationWorker] = None
        self._build()

    def _build(self):
        root = QHBoxLayout(self)

        # ── Left panel: controls ──────────────────────────────────────────────
        ctrl = QGroupBox("Parameters")
        ctrl.setFixedWidth(260)
        form = QFormLayout(ctrl)

        from simulation_engine.degradation_models import MATERIAL_PRESETS
        self._material_cb = QComboBox()
        self._material_cb.addItems(list(MATERIAL_PRESETS.keys()))
        form.addRow("Material:", self._material_cb)

        self._days_sb = QSpinBox()
        self._days_sb.setRange(7, 1000)
        self._days_sb.setValue(90)
        self._days_sb.setSuffix(" days")
        form.addRow("Duration:", self._days_sb)

        self._mw0_sb = QDoubleSpinBox()
        self._mw0_sb.setRange(0, 1_000_000)
        self._mw0_sb.setValue(0)
        self._mw0_sb.setSuffix(" Da (0 = preset)")
        self._mw0_sb.setDecimals(0)
        form.addRow("Initial Mn:", self._mw0_sb)

        self._ph_sb = QDoubleSpinBox()
        self._ph_sb.setRange(1.0, 14.0)
        self._ph_sb.setValue(7.4)
        self._ph_sb.setSingleStep(0.1)
        form.addRow("pH:", self._ph_sb)

        self._temp_sb = QDoubleSpinBox()
        self._temp_sb.setRange(273.15, 373.15)
        self._temp_sb.setValue(310.15)
        self._temp_sb.setSuffix(" K")
        self._temp_sb.setSingleStep(0.5)
        form.addRow("Temperature:", self._temp_sb)

        self._run_btn = QPushButton(qta.icon("fa5s.play"), " Run Simulation")
        self._run_btn.clicked.connect(self._run)
        form.addRow(self._run_btn)

        self._status_lbl = QLabel("")
        self._status_lbl.setWordWrap(True)
        form.addRow(self._status_lbl)

        # Summary box
        self._summary = QTextEdit()
        self._summary.setReadOnly(True)
        self._summary.setFont(QFont("Courier", 9))
        self._summary.setMaximumHeight(180)
        summary_grp = QGroupBox("Summary")
        QVBoxLayout(summary_grp).addWidget(self._summary)

        left = QVBoxLayout()
        left.addWidget(ctrl)
        left.addWidget(summary_grp)
        left.addStretch()

        # ── Right panel: plots ────────────────────────────────────────────────
        self._canvas = _MplCanvas(nrows=2, ncols=1)

        root.addLayout(left)
        root.addWidget(self._canvas, 1)

    def _run(self):
        self._run_btn.setEnabled(False)
        self._status_lbl.setText("Running…")
        self._worker = _DegradationWorker(
            material    = self._material_cb.currentText(),
            days        = self._days_sb.value(),
            ph          = self._ph_sb.value(),
            temperature = self._temp_sb.value(),
        )
        self._worker.finished.connect(self._on_result)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_result(self, result):
        self._run_btn.setEnabled(True)
        self._status_lbl.setText("Done.")
        self._plot(result)
        self._update_summary(result)

    def _on_error(self, msg):
        self._run_btn.setEnabled(True)
        self._status_lbl.setText(f"Error: {msg}")
        QMessageBox.warning(self, "Simulation error", msg)

    def _plot(self, result):
        if not MPL_OK or self._canvas.axes is None:
            return
        ax1, ax2 = self._canvas.axes[0], self._canvas.axes[1]
        ax1.cla(); ax2.cla()

        color = "#2E86AB"

        ax1.plot(result.t_days, result.mw / 1000, color=color, lw=2)
        ax1.set_ylabel("Mn (kDa)")
        ax1.set_title(f"{result.material} — MW Decay")
        ax1.axhline(result.mw_critical / 1000, color="tomato",
                    ls="--", lw=1, label=f"Critical Mn ({result.mw_critical/1000:.0f} kDa)")
        ax1.legend(fontsize=8)
        ax1.set_xlabel("Time (days)")
        ax1.grid(True, alpha=0.3)

        ax2.fill_between(result.t_days, result.mass_remaining * 100,
                         alpha=0.25, color=color)
        ax2.plot(result.t_days, result.mass_remaining * 100, color=color, lw=2)
        ax2.set_ylabel("Mass remaining (%)")
        ax2.set_xlabel("Time (days)")
        ax2.set_title("Mass Erosion")
        ax2.set_ylim(0, 105)
        ax2.grid(True, alpha=0.3)

        self._canvas.fig.tight_layout()
        self._canvas.draw()

    def _update_summary(self, result):
        d = result.to_dict()
        frag  = f"{d['fragmentation_day']:.1f} d" if d["fragmentation_day"] else "not reached"
        t50   = f"{d['half_life_day']:.1f} d"     if d["half_life_day"]     else "not reached"
        lines = [
            f"Material:          {result.material}",
            f"Model:             {result.model_type}",
            f"Fragmentation day: {frag}",
            f"50 % mass loss:    {t50}",
            f"Final mass frac:   {d['final_mass_frac']*100:.1f} %",
            "",
        ] + result.notes
        self._summary.setPlainText("\n".join(lines))


# ── Drug release sub-tab ───────────────────────────────────────────────────────

class _ReleaseWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: Optional[_ReleaseWorker] = None
        self._build()

    def _build(self):
        root = QHBoxLayout(self)

        # ── Left panel: controls ──────────────────────────────────────────────
        ctrl = QGroupBox("Parameters")
        ctrl.setFixedWidth(280)
        form = QFormLayout(ctrl)

        from simulation_engine.drug_release import MODEL_INFO
        self._model_cb = QComboBox()
        self._model_cb.addItems(list(MODEL_INFO.keys()))
        self._model_cb.currentTextChanged.connect(self._update_param_hints)
        form.addRow("Model:", self._model_cb)

        self._hours_sb = QSpinBox()
        self._hours_sb.setRange(1, 2160)   # up to 90 days
        self._hours_sb.setValue(72)
        self._hours_sb.setSuffix(" h")
        form.addRow("Duration:", self._hours_sb)

        self._dose_sb = QDoubleSpinBox()
        self._dose_sb.setRange(0.001, 1_000_000)
        self._dose_sb.setValue(100.0)
        self._dose_sb.setSuffix(" µg")
        form.addRow("Drug dose:", self._dose_sb)

        # Model-specific parameter overrides
        self._n_row_lbl = QLabel("Exponent n:")
        self._n_sb = QDoubleSpinBox()
        self._n_sb.setRange(0.01, 2.0)
        self._n_sb.setValue(0.45)
        self._n_sb.setSingleStep(0.05)
        form.addRow(self._n_row_lbl, self._n_sb)

        self._k_row_lbl = QLabel("Rate k:")
        self._k_sb = QDoubleSpinBox()
        self._k_sb.setRange(0.0001, 10.0)
        self._k_sb.setValue(0.10)
        self._k_sb.setSingleStep(0.01)
        self._k_sb.setDecimals(4)
        form.addRow(self._k_row_lbl, self._k_sb)

        self._run_btn = QPushButton(qta.icon("fa5s.play"), " Run Simulation")
        self._run_btn.clicked.connect(self._run)
        form.addRow(self._run_btn)

        self._status_lbl = QLabel("")
        self._status_lbl.setWordWrap(True)
        form.addRow(self._status_lbl)

        # Hint box
        self._hint_lbl = QLabel("")
        self._hint_lbl.setWordWrap(True)
        self._hint_lbl.setStyleSheet("color: #666; font-size: 10px;")
        self._hint_lbl.setMaximumWidth(260)
        hint_grp = QGroupBox("Model Info")
        QVBoxLayout(hint_grp).addWidget(self._hint_lbl)

        # Summary box
        self._summary = QTextEdit()
        self._summary.setReadOnly(True)
        self._summary.setFont(QFont("Courier", 9))
        self._summary.setMaximumHeight(160)
        summary_grp = QGroupBox("Summary")
        QVBoxLayout(summary_grp).addWidget(self._summary)

        left = QVBoxLayout()
        left.addWidget(ctrl)
        left.addWidget(hint_grp)
        left.addWidget(summary_grp)
        left.addStretch()

        # ── Right panel: plots ────────────────────────────────────────────────
        self._canvas = _MplCanvas(nrows=2, ncols=1)

        root.addLayout(left)
        root.addWidget(self._canvas, 1)

        self._update_param_hints(self._model_cb.currentText())

    def _update_param_hints(self, model_name: str):
        from simulation_engine.drug_release import MODEL_INFO
        info = MODEL_INFO.get(model_name, {})

        # Show/hide exponent n (only for KP and Higuchi)
        show_n = model_name in ("Korsmeyer-Peppas", "Higuchi")
        self._n_row_lbl.setVisible(show_n)
        self._n_sb.setVisible(show_n)

        # Update hint
        self._hint_lbl.setText(info.get("description", "") or "")

    def _run(self):
        self._run_btn.setEnabled(False)
        self._status_lbl.setText("Running…")

        model_name = self._model_cb.currentText()
        custom: dict = {"k_KP": self._k_sb.value(), "k0": self._k_sb.value(),
                        "k1": self._k_sb.value(), "k_H": self._k_sb.value(),
                        "k_HC": self._k_sb.value()}
        if self._n_sb.isVisible():
            custom["n"] = self._n_sb.value()

        self._worker = _ReleaseWorker(
            model_name   = model_name,
            hours        = self._hours_sb.value(),
            initial_dose = self._dose_sb.value(),
            custom_params = custom,
        )
        self._worker.finished.connect(self._on_result)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_result(self, result):
        self._run_btn.setEnabled(True)
        self._status_lbl.setText("Done.")
        self._plot(result)
        self._update_summary(result)

    def _on_error(self, msg):
        self._run_btn.setEnabled(True)
        self._status_lbl.setText(f"Error: {msg}")
        QMessageBox.warning(self, "Simulation error", msg)

    def _plot(self, result):
        if not MPL_OK or self._canvas.axes is None:
            return
        ax1, ax2 = self._canvas.axes[0], self._canvas.axes[1]
        ax1.cla(); ax2.cla()

        color = "#A23B72"
        t = result.t_hours

        ax1.plot(t, result.Q_fraction * 100, color=color, lw=2)
        ax1.fill_between(t, result.Q_fraction * 100, alpha=0.15, color=color)
        ax1.set_ylabel("Cumulative release (%)")
        ax1.set_title(f"{result.model_name}")
        ax1.set_ylim(0, 105)
        ax1.axhline(80, color="tomato", ls="--", lw=1, label="80 %")
        ax1.axhline(50, color="orange", ls="--", lw=1, label="50 %")
        ax1.legend(fontsize=8)
        ax1.set_xlabel("Time (h)")
        ax1.grid(True, alpha=0.3)

        # Release rate (derivative)
        rate = np.gradient(result.Q_fraction * result.initial_dose, t)
        ax2.plot(t, np.maximum(rate, 0), color=color, lw=2)
        ax2.set_ylabel(f"Release rate (µg/h)")
        ax2.set_xlabel("Time (h)")
        ax2.set_title("Release Rate")
        ax2.grid(True, alpha=0.3)

        self._canvas.fig.tight_layout()
        self._canvas.draw()

    def _update_summary(self, result):
        d = result.to_dict()
        t50 = f"{d['t50_hours']:.1f} h" if d["t50_hours"] else "not reached"
        t80 = f"{d['t80_hours']:.1f} h" if d["t80_hours"] else "not reached"
        lines = [
            f"Model:          {result.model_name}",
            f"Initial dose:   {result.initial_dose:.2f} µg",
            f"t50:            {t50}",
            f"t80:            {t80}",
            f"Burst (1 h):    {d['burst_1h']*100:.1f} %",
            f"Final release:  {d['final_release']*100:.1f} %",
            "",
        ] + result.notes
        self._summary.setPlainText("\n".join(lines))


import numpy as np


# ── Main SimulationTab ─────────────────────────────────────────────────────────

class SimulationTab(QWidget):
    """
    Biomaterial Simulation tab:
      • Polymer Degradation — MW + mass loss over time
      • Drug Release Kinetics — cumulative release profiles
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project_id: Optional[int] = None
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Header
        hdr = QLabel("Biomaterial Simulation")
        hdr.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        hdr.setStyleSheet("color: #2E86AB; padding: 4px 0;")
        layout.addWidget(hdr)

        sub = QLabel(
            "ODE-based polymer degradation and drug release kinetics. "
            "Select a material / model, adjust parameters, and click Run."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet("color: #555; font-size: 11px;")
        layout.addWidget(sub)

        # Sub-tabs
        tabs = QTabWidget()
        tabs.addTab(_DegradationWidget(), qta.icon("fa5s.chart-line"), "Polymer Degradation")
        tabs.addTab(_ReleaseWidget(),     qta.icon("fa5s.capsules"),   "Drug Release Kinetics")
        layout.addWidget(tabs)

    def set_project_id(self, project_id: int):
        self._project_id = project_id
