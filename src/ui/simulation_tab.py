"""
Simulation Tab
===============
Interactive ODE simulation with live parameter sliders and matplotlib plots.

Sub-structure:
  - Model selector (left panel)
  - Parameter sliders + spinboxes (left panel)
  - Live plot canvas (right panel)
  - Annotations / key insights (below plot)
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QScrollArea, QSlider, QSplitter,
    QTextEdit, QVBoxLayout, QWidget,
)
import qtawesome as qta

logger = logging.getLogger(__name__)

# matplotlib embedding
try:
    import matplotlib
    matplotlib.use("QtAgg")
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    _MPL_OK = True
except ImportError:
    _MPL_OK = False
    logger.warning("matplotlib not available; simulation plots disabled")


class SimulationTab(QWidget):
    """Interactive ODE simulation environment."""

    def __init__(self):
        super().__init__()
        self._current_model = None
        self._current_model_key = ""
        self._param_widgets: Dict[str, dict] = {}  # name -> {slider, spinbox}
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(200)
        self._debounce_timer.timeout.connect(self._run_simulation)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        header = QLabel("Simulation")
        header.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(header)

        # Main splitter: left (controls) | right (plot + annotations)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Left panel: model selector + parameters ──
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Model selector
        model_group = QGroupBox("Model Library")
        model_layout = QVBoxLayout(model_group)
        self._model_combo = QComboBox()

        from src.simulation_engine import MODEL_REGISTRY
        for key, cls in MODEL_REGISTRY.items():
            model = cls()
            self._model_combo.addItem(model.name, key)
        self._model_combo.currentIndexChanged.connect(self._on_model_changed)
        model_layout.addWidget(self._model_combo)

        self._model_desc = QLabel("")
        self._model_desc.setWordWrap(True)
        self._model_desc.setStyleSheet("color: #555; font-size: 11px;")
        model_layout.addWidget(self._model_desc)
        left_layout.addWidget(model_group)

        # Time range control
        time_group = QGroupBox("Time Range")
        time_layout = QHBoxLayout(time_group)
        time_layout.addWidget(QLabel("End:"))
        self._t_end_spin = QDoubleSpinBox()
        self._t_end_spin.setRange(1, 1000)
        self._t_end_spin.setValue(30)
        self._t_end_spin.setSuffix(" (see unit)")
        self._t_end_spin.valueChanged.connect(self._schedule_update)
        time_layout.addWidget(self._t_end_spin)
        left_layout.addWidget(time_group)

        # Parameter scroll area
        param_group = QGroupBox("Parameters")
        self._param_scroll = QScrollArea()
        self._param_scroll.setWidgetResizable(True)
        self._param_container = QWidget()
        self._param_layout = QGridLayout(self._param_container)
        self._param_layout.setSpacing(4)
        self._param_scroll.setWidget(self._param_container)
        param_inner = QVBoxLayout(param_group)
        param_inner.addWidget(self._param_scroll)
        left_layout.addWidget(param_group, stretch=1)

        splitter.addWidget(left)

        # ── Right panel: plot + annotations ──
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        if _MPL_OK:
            self._fig = Figure(figsize=(8, 5), dpi=100)
            self._canvas = FigureCanvas(self._fig)
            right_layout.addWidget(self._canvas, stretch=3)
        else:
            right_layout.addWidget(QLabel("matplotlib not available"))

        # Annotations
        self._annotations = QTextEdit()
        self._annotations.setReadOnly(True)
        self._annotations.setMaximumHeight(150)
        self._annotations.setPlaceholderText("Key insights from simulation will appear here.")
        right_layout.addWidget(self._annotations, stretch=1)

        splitter.addWidget(right)
        splitter.setSizes([300, 600])
        layout.addWidget(splitter)

        # Load first model
        if self._model_combo.count() > 0:
            self._on_model_changed(0)

    def _on_model_changed(self, index: int):
        key = self._model_combo.currentData()
        if not key:
            return

        from src.simulation_engine import MODEL_REGISTRY
        cls = MODEL_REGISTRY.get(key)
        if not cls:
            return

        self._current_model = cls()
        self._current_model_key = key
        self._model_desc.setText(self._current_model.description)

        # Set appropriate default time range
        defaults_t = {
            "cell_proliferation": 30,
            "drug_release": 30,
            "gene_circuit": 48,
            "diffusion": 1,
            "tissue_response": 24,
            "metabolic_flux": 72,
        }
        self._t_end_spin.setValue(defaults_t.get(key, 30))

        # Rebuild parameter widgets
        self._build_param_widgets()
        self._run_simulation()

    def _build_param_widgets(self):
        """Rebuild parameter sliders for the current model."""
        # Clear existing
        while self._param_layout.count():
            item = self._param_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._param_widgets.clear()

        if not self._current_model:
            return

        params = self._current_model.get_parameters()
        for row, (name, param) in enumerate(params.items()):
            # Label
            label = QLabel(f"{param.description} ({param.unit}):")
            label.setToolTip(f"{param.name}: range [{param.min_val}, {param.max_val}]")
            self._param_layout.addWidget(label, row, 0)

            # Slider (integer-mapped)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setMinimum(0)
            slider.setMaximum(200)  # 200 steps
            # Map default to slider position
            if param.max_val != param.min_val:
                pos = int(200 * (param.default - param.min_val) / (param.max_val - param.min_val))
            else:
                pos = 100
            slider.setValue(pos)
            self._param_layout.addWidget(slider, row, 1)

            # Spinbox
            spinbox = QDoubleSpinBox()
            spinbox.setRange(param.min_val, param.max_val)
            spinbox.setValue(param.default)
            spinbox.setSingleStep(param.step)
            # Set decimal places based on range
            if param.max_val - param.min_val < 1:
                spinbox.setDecimals(4)
            elif param.max_val - param.min_val < 100:
                spinbox.setDecimals(2)
            else:
                spinbox.setDecimals(1)
            self._param_layout.addWidget(spinbox, row, 2)

            # Connect slider <-> spinbox bidirectionally
            def make_slider_handler(n, s, sb, p):
                def handler(val):
                    real_val = p.min_val + (p.max_val - p.min_val) * val / 200.0
                    sb.blockSignals(True)
                    sb.setValue(real_val)
                    sb.blockSignals(False)
                    self._schedule_update()
                return handler

            def make_spinbox_handler(n, s, sb, p):
                def handler(val):
                    if p.max_val != p.min_val:
                        pos = int(200 * (val - p.min_val) / (p.max_val - p.min_val))
                    else:
                        pos = 100
                    s.blockSignals(True)
                    s.setValue(pos)
                    s.blockSignals(False)
                    self._schedule_update()
                return handler

            slider.valueChanged.connect(make_slider_handler(name, slider, spinbox, param))
            spinbox.valueChanged.connect(make_spinbox_handler(name, slider, spinbox, param))

            self._param_widgets[name] = {"slider": slider, "spinbox": spinbox, "param": param}

    def _schedule_update(self):
        """Debounce: restart timer on each change."""
        self._debounce_timer.start()

    def _get_current_params(self) -> Dict[str, float]:
        """Read current parameter values from spinboxes."""
        return {
            name: widgets["spinbox"].value()
            for name, widgets in self._param_widgets.items()
        }

    def _run_simulation(self):
        """Execute simulation and update plot."""
        if not self._current_model or not _MPL_OK:
            return

        params = self._get_current_params()
        t_end = self._t_end_spin.value()

        try:
            result = self._current_model.run(params, t_end=t_end)
            self._update_plot(result)
            self._update_annotations(result)
        except Exception as e:
            logger.error("Simulation error: %s", e)
            self._annotations.setText(f"Simulation error: {e}")

    def _update_plot(self, result):
        """Redraw matplotlib plot with simulation results."""
        self._fig.clear()

        curves = result.curves
        n_curves = len(curves)

        if n_curves == 1:
            ax = self._fig.add_subplot(111)
            name = list(curves.keys())[0]
            ax.plot(result.t, curves[name], linewidth=2, color="#2196F3")
            ax.set_ylabel(f"{result.curve_labels[name]} ({result.curve_units[name]})")
            ax.set_xlabel(result.t_unit)
            ax.set_title(result.model_name)
            ax.grid(True, alpha=0.3)
        elif n_curves == 2:
            names = list(curves.keys())
            colors = ["#2196F3", "#FF5722"]
            ax1 = self._fig.add_subplot(111)
            ax1.plot(result.t, curves[names[0]], linewidth=2, color=colors[0],
                     label=result.curve_labels[names[0]])
            ax1.set_ylabel(f"{result.curve_labels[names[0]]} ({result.curve_units[names[0]]})",
                          color=colors[0])
            ax1.set_xlabel(result.t_unit)
            ax1.tick_params(axis='y', labelcolor=colors[0])

            ax2 = ax1.twinx()
            ax2.plot(result.t, curves[names[1]], linewidth=2, color=colors[1],
                     label=result.curve_labels[names[1]], linestyle="--")
            ax2.set_ylabel(f"{result.curve_labels[names[1]]} ({result.curve_units[names[1]]})",
                          color=colors[1])
            ax2.tick_params(axis='y', labelcolor=colors[1])

            # Combined legend
            lines1, labels1 = ax1.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax1.legend(lines1 + lines2, labels1 + labels2, loc="best", fontsize=8)
            ax1.set_title(result.model_name)
            ax1.grid(True, alpha=0.3)
        else:
            # 3+ curves: subplots
            colors = ["#2196F3", "#FF5722", "#4CAF50", "#9C27B0"]
            names = list(curves.keys())
            for i, name in enumerate(names):
                ax = self._fig.add_subplot(n_curves, 1, i + 1)
                ax.plot(result.t, curves[name], linewidth=2,
                       color=colors[i % len(colors)])
                ax.set_ylabel(f"{result.curve_labels[name]}", fontsize=8)
                ax.grid(True, alpha=0.3)
                ax.tick_params(labelsize=7)
                if i == 0:
                    ax.set_title(result.model_name, fontsize=10)
                if i == n_curves - 1:
                    ax.set_xlabel(result.t_unit, fontsize=8)

        self._fig.tight_layout()
        self._canvas.draw()

    def _update_annotations(self, result):
        """Display key insights from simulation."""
        html = "<h4>Key Insights</h4><ul>"
        for ann in result.annotations:
            if "WARNING" in ann or "POOR" in ann:
                html += f"<li style='color:#dc3545'><b>{ann}</b></li>"
            elif "GOOD" in ann:
                html += f"<li style='color:#155724'><b>{ann}</b></li>"
            else:
                html += f"<li>{ann}</li>"
        html += "</ul>"
        self._annotations.setHtml(html)
