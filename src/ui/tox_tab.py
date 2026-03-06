"""
Toxicology Tab — full power of the tox_engine in the UI.

Sub-tabs:
  1. Server Control  — start/stop each MCP server; live health indicators
  2. CompTox         — EPA CompTox chemical hazard screening
  3. ADMET           — ADMET prediction from SMILES
  4. AOP             — Adverse Outcome Pathway mapping
  5. PBPK            — PBPK simulation (OSP Suite)

Architecture:
  - One shared ToxServerManager instance lives here (passed out to main_window).
  - All heavy calls use pre-built workers from tox_engine/workers.py.
  - QTimer polls server health every 10 s and after start/stop actions.
"""

from __future__ import annotations

import logging
import os
from typing import Optional, Dict, List

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QProgressBar, QPushButton, QScrollArea,
    QSizePolicy, QSplitter, QTabWidget, QTableWidget, QTableWidgetItem,
    QTextEdit, QVBoxLayout, QWidget,
)
import qtawesome as qta

logger = logging.getLogger(__name__)

_GREEN = "#27ae60"
_AMBER = "#f39c12"
_RED   = "#e74c3c"
_GREY  = "#95a5a6"


# ── Singleton ToxServerManager ────────────────────────────────────────────────

_MANAGER = None

def get_tox_manager():
    """Return (or create) the singleton ToxServerManager."""
    global _MANAGER
    if _MANAGER is None:
        try:
            from tox_engine.server_manager import ToxServerManager
            _MANAGER = ToxServerManager()
        except ImportError:
            logger.warning("tox_engine not installed — ToxTab will be degraded.")
    return _MANAGER


# ── Start/Stop worker (can't do subprocess ops in main thread safely) ─────────

class _StartServerWorker(QThread):
    done = pyqtSignal(str, bool)   # server_name, success

    def __init__(self, manager, server_name: str):
        super().__init__()
        self._manager = manager
        self._server_name = server_name

    def run(self):
        ok = self._manager.start_server(self._server_name)
        import time; time.sleep(1)           # brief settle time
        alive = self._manager.is_alive(self._server_name)
        self.done.emit(self._server_name, alive)


class _StopServerWorker(QThread):
    done = pyqtSignal(str)   # server_name

    def __init__(self, manager, server_name: str):
        super().__init__()
        self._manager = manager
        self._server_name = server_name

    def run(self):
        # stop individual server by stopping all then note its config
        try:
            cfg = self._manager._servers[self._server_name]
            if cfg._process:
                cfg._process.terminate()
                cfg._process.wait(timeout=5)
                cfg._process = None
        except Exception as e:
            logger.warning("Stop %s: %s", self._server_name, e)
        self.done.emit(self._server_name)


class _HealthWorker(QThread):
    status_ready = pyqtSignal(dict)

    def __init__(self, manager):
        super().__init__()
        self._manager = manager

    def run(self):
        try:
            status = self._manager.get_status()
            self.status_ready.emit(status)
        except Exception:
            self.status_ready.emit({})


# ── PBPK simulation worker ────────────────────────────────────────────────────

class _PBPKWorker(QThread):
    result_ready   = pyqtSignal(object)   # SimulationResult
    error_occurred = pyqtSignal(str)
    progress       = pyqtSignal(int, str)

    def __init__(self, pbpk_client, model_path: str, params: dict,
                 population: bool, n_subjects: int):
        super().__init__()
        self._client     = pbpk_client
        self._model_path = model_path
        self._params     = params
        self._population = population
        self._n_subjects = n_subjects

    def run(self):
        try:
            self.progress.emit(10, "Loading model ...")
            load_result = self._client.load_model(self._model_path)
            if not load_result.get("success"):
                self.error_occurred.emit(f"Model load failed: {load_result.get('error', 'unknown')}")
                return

            self.progress.emit(30, "Setting parameters ...")
            for name, value in self._params.items():
                self._client.set_parameter(name, value)

            self.progress.emit(60, "Running simulation ...")
            if self._population:
                result = self._client.run_population_simulation(n_subjects=self._n_subjects)
            else:
                result = self._client.run_simulation()

            self.progress.emit(100, "Simulation complete")
            self.result_ready.emit(result)
        except Exception as e:
            logger.exception("PBPKWorker error")
            self.error_occurred.emit(str(e))


# ── Main ToxTab ───────────────────────────────────────────────────────────────

class ToxTab(QWidget):
    """Full toxicology analysis: server control, CompTox, ADMET, AOP, PBPK."""

    def __init__(self):
        super().__init__()
        self._manager = get_tox_manager()
        self._health_worker: Optional[_HealthWorker]     = None
        self._start_worker: Optional[_StartServerWorker] = None
        self._stop_worker: Optional[_StopServerWorker]   = None
        self._comptox_worker = None
        self._admet_worker   = None
        self._aop_worker     = None
        self._pbpk_worker: Optional[_PBPKWorker]         = None

        self._server_indicators: Dict[str, QLabel] = {}
        self._server_status_cache: Dict[str, bool] = {}

        self._pbpk_model_path: Optional[str] = None
        self._pbpk_params: Dict[str, float] = {}

        self._init_ui()

        # Poll health every 10 seconds
        self._health_timer = QTimer(self)
        self._health_timer.timeout.connect(self._refresh_health)
        self._health_timer.start(10_000)
        # Initial check
        QTimer.singleShot(500, self._refresh_health)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_server_tab(), qta.icon("fa.server"),    "Server Control")
        self._tabs.addTab(self._build_comptox_tab(), qta.icon("fa.flask"),    "CompTox")
        self._tabs.addTab(self._build_admet_tab(),   qta.icon("fa.heartbeat"),"ADMET")
        self._tabs.addTab(self._build_aop_tab(),     qta.icon("fa.sitemap"),  "AOP")
        self._tabs.addTab(self._build_pbpk_tab(),    qta.icon("fa.line-chart"),"PBPK")
        layout.addWidget(self._tabs)

    # ── Server Control tab ────────────────────────────────────────────────────

    def _build_server_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        info = QLabel(
            "<b>ToxMCP Server Control</b><br>"
            "Each MCP server is a local HTTP process. Start them to enable live hazard data in "
            "CompTox, ADMET, AOP, PBPK sub-tabs and to enrich ISO 10993 / Biocompat scoring in "
            "the Regulatory tab."
        )
        info.setWordWrap(True)
        info.setStyleSheet("padding: 8px; background: #f0f4ff; border-radius: 4px;")
        layout.addWidget(info)

        # Server cards
        servers = [
            ("admet",   "ADMETlab MCP",  "Port 8082", "Absorption/Distribution/Metabolism/Excretion/Toxicity from SMILES. No API key required.", False),
            ("comptox", "CompTox MCP",   "Port 8083", "EPA CompTox chemical hazard database. Requires EPA_COMPTOX_API_KEY.", True),
            ("aop",     "AOP MCP",       "Port 8084", "AOP-Wiki Adverse Outcome Pathway mapping. No API key required.", False),
            ("pbpk",    "PBPK MCP",      "Port 8085", "OSP Suite PBPK simulations. No API key required.", False),
        ]

        self._server_cards: Dict[str, QFrame] = {}
        for key, name, port, desc, needs_key in servers:
            card = self._make_server_card(key, name, port, desc, needs_key)
            layout.addWidget(card)
            self._server_cards[key] = card

        # Bulk actions
        bulk_row = QHBoxLayout()
        start_all_btn = QPushButton("Start All Available")
        start_all_btn.setIcon(qta.icon("fa.play-circle"))
        start_all_btn.setStyleSheet("QPushButton { background: #27ae60; color: white; font-weight: bold; border-radius: 4px; padding: 6px 14px; }")
        start_all_btn.clicked.connect(self._start_all_available)
        stop_all_btn = QPushButton("Stop All")
        stop_all_btn.setIcon(qta.icon("fa.stop-circle"))
        stop_all_btn.setStyleSheet("QPushButton { background: #e74c3c; color: white; font-weight: bold; border-radius: 4px; padding: 6px 14px; }")
        stop_all_btn.clicked.connect(self._stop_all)
        refresh_btn = QPushButton("Refresh Status")
        refresh_btn.setIcon(qta.icon("fa.refresh"))
        refresh_btn.clicked.connect(self._refresh_health)
        bulk_row.addWidget(start_all_btn)
        bulk_row.addWidget(stop_all_btn)
        bulk_row.addWidget(refresh_btn)
        bulk_row.addStretch()
        layout.addLayout(bulk_row)

        self._server_log = QPlainTextEdit()
        self._server_log.setReadOnly(True)
        self._server_log.setMaximumHeight(120)
        self._server_log.setPlaceholderText("Server events will be logged here ...")
        layout.addWidget(self._server_log)

        layout.addStretch()
        return w

    def _make_server_card(self, key: str, name: str, port: str,
                          desc: str, needs_key: bool) -> QFrame:
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setStyleSheet("QFrame { background: #fafafa; border-radius: 6px; }")
        h = QHBoxLayout(card)
        h.setContentsMargins(12, 8, 12, 8)

        # Status indicator circle
        indicator = QLabel("●")
        indicator.setFont(QFont("Arial", 18))
        indicator.setFixedWidth(28)
        indicator.setStyleSheet(f"color: {_GREY};")
        self._server_indicators[key] = indicator
        h.addWidget(indicator)

        # Text block
        v = QVBoxLayout()
        title = QLabel(f"<b>{name}</b>  <span style='color:#888; font-size:11px;'>{port}</span>")
        desc_lbl = QLabel(desc)
        desc_lbl.setStyleSheet("color: #555; font-size: 11px;")
        desc_lbl.setWordWrap(True)
        if needs_key:
            key_set = bool(os.getenv("EPA_COMPTOX_API_KEY"))
            key_lbl = QLabel(
                "<span style='color: #27ae60;'>EPA_COMPTOX_API_KEY set</span>"
                if key_set else
                "<span style='color: #e74c3c;'>EPA_COMPTOX_API_KEY not set — CompTox will run in demo mode</span>"
            )
            key_lbl.setStyleSheet("font-size: 11px;")
            v.addWidget(key_lbl)
        v.addWidget(title)
        v.addWidget(desc_lbl)
        h.addLayout(v)
        h.addStretch()

        # Start / Stop buttons
        start_btn = QPushButton("Start")
        start_btn.setIcon(qta.icon("fa.play", color="white"))
        start_btn.setStyleSheet("QPushButton { background: #27ae60; color: white; border-radius: 4px; padding: 5px 12px; }"
                                "QPushButton:hover { background: #1e8449; }")
        start_btn.clicked.connect(lambda checked, k=key: self._start_server(k))
        stop_btn = QPushButton("Stop")
        stop_btn.setIcon(qta.icon("fa.stop", color="white"))
        stop_btn.setStyleSheet("QPushButton { background: #e74c3c; color: white; border-radius: 4px; padding: 5px 12px; }"
                               "QPushButton:hover { background: #c0392b; }")
        stop_btn.clicked.connect(lambda checked, k=key: self._stop_server(k))
        h.addWidget(start_btn)
        h.addWidget(stop_btn)
        return card

    # ── CompTox tab ───────────────────────────────────────────────────────────

    def _build_comptox_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        desc = QLabel(
            "Screen material components against EPA CompTox chemical hazard database. "
            "Returns GHS codes, NOAEL/LOAEL, carcinogenicity, acute toxicity, and OPERA predictions."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("padding: 6px; background: #f0f4ff; border-radius: 4px;")
        layout.addWidget(desc)

        input_row = QHBoxLayout()
        input_row.addWidget(QLabel("Components (comma-separated):"))
        self._comptox_input = QLineEdit()
        self._comptox_input.setPlaceholderText(
            "e.g. gelatin, methacrylic anhydride, lithium phenyl phosphinate"
        )
        input_row.addWidget(self._comptox_input)
        run_btn = QPushButton("Screen Components")
        run_btn.setIcon(qta.icon("fa.search"))
        run_btn.setStyleSheet("QPushButton { font-weight: bold; background: #2980b9; color: white; "
                              "border-radius: 4px; padding: 6px 14px; }")
        run_btn.clicked.connect(self._run_comptox)
        input_row.addWidget(run_btn)
        layout.addLayout(input_row)

        self._comptox_progress = QProgressBar()
        self._comptox_progress.setVisible(False)
        self._comptox_status  = QLabel("Start CompTox MCP server first, then enter components.")
        layout.addWidget(self._comptox_progress)
        layout.addWidget(self._comptox_status)

        self._comptox_table = QTableWidget(0, 7)
        self._comptox_table.setHorizontalHeaderLabels([
            "Component", "Risk Tier", "GHS Codes", "Carcinogen",
            "Acute Tox", "NOAEL", "OPERA Flags",
        ])
        self._comptox_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._comptox_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._comptox_table.setAlternatingRowColors(True)
        self._comptox_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self._comptox_table)

        # Detail panel
        self._comptox_detail = QTextEdit()
        self._comptox_detail.setReadOnly(True)
        self._comptox_detail.setMaximumHeight(140)
        self._comptox_detail.setPlaceholderText("Click a row to see full hazard profile ...")
        self._comptox_table.itemSelectionChanged.connect(self._on_comptox_row_selected)
        layout.addWidget(self._comptox_detail)

        return w

    # ── ADMET tab ─────────────────────────────────────────────────────────────

    def _build_admet_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        desc = QLabel(
            "Predict full ADMET profile from a SMILES string using ADMETlab. "
            "Covers absorption, distribution, metabolism, excretion, and 30+ toxicity endpoints."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("padding: 6px; background: #f0f4ff; border-radius: 4px;")
        layout.addWidget(desc)

        input_row = QHBoxLayout()
        input_row.addWidget(QLabel("SMILES:"))
        self._admet_input = QLineEdit()
        self._admet_input.setPlaceholderText(
            "e.g. CC(=O)Oc1ccccc1C(=O)O   (aspirin)"
        )
        self._admet_input.setFont(QFont("Courier New", 10))
        input_row.addWidget(self._admet_input)
        render_btn = QPushButton("Predict ADMET")
        render_btn.setIcon(qta.icon("fa.heartbeat"))
        render_btn.setStyleSheet("QPushButton { font-weight: bold; background: #8e44ad; color: white; "
                                 "border-radius: 4px; padding: 6px 14px; }")
        render_btn.clicked.connect(self._run_admet)
        input_row.addWidget(render_btn)
        layout.addLayout(input_row)

        self._admet_status = QLabel("Start ADMETlab MCP server first, then enter a SMILES string.")
        layout.addWidget(self._admet_status)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: molecule SVG render
        mol_frame = QFrame()
        mol_frame.setFrameShape(QFrame.Shape.StyledPanel)
        mol_frame.setMinimumWidth(220)
        mol_frame.setMinimumHeight(220)
        mol_layout = QVBoxLayout(mol_frame)
        mol_layout.addWidget(QLabel("<b>Structure</b>"))
        self._mol_svg_label = QLabel("Structure preview\nrequires ADMETlab server")
        self._mol_svg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._mol_svg_label.setStyleSheet("color: #888; font-size: 12px; background: white;")
        mol_layout.addWidget(self._mol_svg_label)
        splitter.addWidget(mol_frame)

        # Right: ADMET properties table
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self._admet_table = QTableWidget(0, 3)
        self._admet_table.setHorizontalHeaderLabels(["Property", "Value", "Flag"])
        self._admet_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._admet_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._admet_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._admet_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._admet_table.setAlternatingRowColors(True)
        right_layout.addWidget(self._admet_table)

        self._admet_tox_summary = QTextEdit()
        self._admet_tox_summary.setReadOnly(True)
        self._admet_tox_summary.setMaximumHeight(80)
        self._admet_tox_summary.setPlaceholderText("Toxicity flags summary will appear here ...")
        right_layout.addWidget(self._admet_tox_summary)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter)

        return w

    # ── AOP tab ───────────────────────────────────────────────────────────────

    def _build_aop_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        desc = QLabel(
            "Map material components to Adverse Outcome Pathways from AOP-Wiki. "
            "Shows Molecular Initiating Events → Key Events → Adverse Outcomes."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("padding: 6px; background: #f0f4ff; border-radius: 4px;")
        layout.addWidget(desc)

        input_row = QHBoxLayout()
        input_row.addWidget(QLabel("Components (comma-separated):"))
        self._aop_input = QLineEdit()
        self._aop_input.setPlaceholderText(
            "e.g. PLGA, polylactic acid, polyglycolic acid"
        )
        input_row.addWidget(self._aop_input)
        run_btn = QPushButton("Map AOPs")
        run_btn.setIcon(qta.icon("fa.sitemap"))
        run_btn.setStyleSheet("QPushButton { font-weight: bold; background: #16a085; color: white; "
                              "border-radius: 4px; padding: 6px 14px; }")
        run_btn.clicked.connect(self._run_aop)
        input_row.addWidget(run_btn)
        layout.addLayout(input_row)

        self._aop_progress = QProgressBar()
        self._aop_progress.setVisible(False)
        self._aop_status = QLabel("Start AOP MCP server first, then enter components.")
        layout.addWidget(self._aop_progress)
        layout.addWidget(self._aop_status)

        self._aop_table = QTableWidget(0, 5)
        self._aop_table.setHorizontalHeaderLabels([
            "Component", "AOP ID", "AOP Name", "MIE", "Adverse Outcome",
        ])
        self._aop_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._aop_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._aop_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._aop_table.setAlternatingRowColors(True)
        layout.addWidget(self._aop_table)

        # Key events detail
        self._aop_ke_label = QLabel("<b>Key Events (click a row):</b>")
        layout.addWidget(self._aop_ke_label)
        self._aop_ke_text = QTextEdit()
        self._aop_ke_text.setReadOnly(True)
        self._aop_ke_text.setMaximumHeight(110)
        self._aop_table.itemSelectionChanged.connect(self._on_aop_row_selected)
        layout.addWidget(self._aop_ke_text)

        # Store raw results for detail view
        self._aop_raw_results: Dict = {}

        return w

    # ── PBPK tab ──────────────────────────────────────────────────────────────

    def _build_pbpk_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        desc = QLabel(
            "Run PBPK simulations using OSP Suite PK-Sim models. "
            "Load a .pkml model file, set physiological parameters, then run individual or population simulations."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("padding: 6px; background: #f0f4ff; border-radius: 4px;")
        layout.addWidget(desc)

        # Model file loader
        file_row = QHBoxLayout()
        file_row.addWidget(QLabel("Model file (.pkml):"))
        self._pbpk_path_label = QLabel("<i>No model loaded</i>")
        self._pbpk_path_label.setStyleSheet("color: #888; font-size: 11px;")
        file_row.addWidget(self._pbpk_path_label)
        browse_btn = QPushButton("Browse ...")
        browse_btn.setIcon(qta.icon("fa.folder-open"))
        browse_btn.clicked.connect(self._browse_pbpk_model)
        file_row.addWidget(browse_btn)
        layout.addLayout(file_row)

        # Simulation type
        sim_type_row = QHBoxLayout()
        sim_type_row.addWidget(QLabel("Simulation type:"))
        self._pbpk_sim_combo = QComboBox()
        self._pbpk_sim_combo.addItems(["Individual", "Population"])
        sim_type_row.addWidget(self._pbpk_sim_combo)
        sim_type_row.addWidget(QLabel("N subjects (population):"))
        self._pbpk_n_subjects = QLineEdit("100")
        self._pbpk_n_subjects.setFixedWidth(60)
        sim_type_row.addWidget(self._pbpk_n_subjects)
        sim_type_row.addStretch()
        layout.addLayout(sim_type_row)

        # Parameter editor
        param_group = QGroupBox("Simulation Parameters")
        param_layout = QVBoxLayout(param_group)
        param_hint = QLabel("Enter parameter overrides as  name = value  pairs, one per line:")
        param_hint.setStyleSheet("font-size: 11px; color: #555;")
        param_layout.addWidget(param_hint)
        self._pbpk_params_edit = QPlainTextEdit()
        self._pbpk_params_edit.setPlaceholderText(
            "BodyWeight = 70\n"
            "Age = 30\n"
            "Dose = 0.001\n"
        )
        self._pbpk_params_edit.setMaximumHeight(100)
        self._pbpk_params_edit.setFont(QFont("Courier New", 10))
        param_layout.addWidget(self._pbpk_params_edit)
        layout.addWidget(param_group)

        run_row = QHBoxLayout()
        self._pbpk_run_btn = QPushButton("Run Simulation")
        self._pbpk_run_btn.setIcon(qta.icon("fa.play"))
        self._pbpk_run_btn.setStyleSheet("QPushButton { font-weight: bold; background: #2980b9; color: white; "
                                         "border-radius: 4px; padding: 6px 14px; }")
        self._pbpk_run_btn.clicked.connect(self._run_pbpk)
        run_row.addWidget(self._pbpk_run_btn)
        run_row.addStretch()
        layout.addLayout(run_row)

        self._pbpk_progress = QProgressBar()
        self._pbpk_progress.setVisible(False)
        self._pbpk_status = QLabel("Start PBPK MCP server and load a model file first.")
        layout.addWidget(self._pbpk_progress)
        layout.addWidget(self._pbpk_status)

        # Results: PK metrics + plot placeholder
        results_splitter = QSplitter(Qt.Orientation.Horizontal)

        # PK metrics table
        metrics_frame = QFrame()
        metrics_frame.setFrameShape(QFrame.Shape.StyledPanel)
        metrics_layout = QVBoxLayout(metrics_frame)
        metrics_layout.addWidget(QLabel("<b>PK Metrics</b>"))
        self._pk_metrics_table = QTableWidget(0, 2)
        self._pk_metrics_table.setHorizontalHeaderLabels(["Parameter", "Value"])
        self._pk_metrics_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._pk_metrics_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._pk_metrics_table.setAlternatingRowColors(True)
        metrics_layout.addWidget(self._pk_metrics_table)
        results_splitter.addWidget(metrics_frame)

        # PK curve plot area (matplotlib embedded when results arrive)
        plot_frame = QFrame()
        plot_frame.setFrameShape(QFrame.Shape.StyledPanel)
        plot_frame.setObjectName("pbpk_plot_frame")
        self._plot_layout = QVBoxLayout(plot_frame)
        self._plot_layout.addWidget(QLabel("<b>PK Concentration-Time Curve</b>"))
        self._pk_plot_placeholder = QLabel(
            "Concentration-time curve will appear here after simulation."
        )
        self._pk_plot_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pk_plot_placeholder.setStyleSheet("color: #888; font-size: 12px;")
        self._plot_layout.addWidget(self._pk_plot_placeholder)
        results_splitter.addWidget(plot_frame)
        results_splitter.setStretchFactor(0, 1)
        results_splitter.setStretchFactor(1, 2)
        layout.addWidget(results_splitter)

        return w

    # ── Server control slots ──────────────────────────────────────────────────

    def _start_server(self, key: str):
        if self._manager is None:
            self._log(f"tox_engine not available.")
            return
        self._log(f"Starting {key} ...")
        self._server_indicators[key].setStyleSheet(f"color: {_AMBER};")
        self._start_worker = _StartServerWorker(self._manager, key)
        self._start_worker.done.connect(self._on_server_started)
        self._start_worker.start()

    def _on_server_started(self, key: str, alive: bool):
        color = _GREEN if alive else _RED
        self._server_indicators[key].setStyleSheet(f"color: {color};")
        self._server_status_cache[key] = alive
        self._log(f"{key}: {'running' if alive else 'failed to start'}")

    def _stop_server(self, key: str):
        if self._manager is None:
            return
        self._log(f"Stopping {key} ...")
        self._stop_worker = _StopServerWorker(self._manager, key)
        self._stop_worker.done.connect(self._on_server_stopped)
        self._stop_worker.start()

    def _on_server_stopped(self, key: str):
        self._server_indicators[key].setStyleSheet(f"color: {_GREY};")
        self._server_status_cache[key] = False
        self._log(f"{key}: stopped")

    def _start_all_available(self):
        if self._manager is None:
            return
        for key in self._manager.available_servers:
            self._start_server(key)

    def _stop_all(self):
        if self._manager is None:
            return
        for key in self._manager.available_servers:
            self._stop_server(key)

    def _refresh_health(self):
        if self._manager is None or (self._health_worker and self._health_worker.isRunning()):
            return
        self._health_worker = _HealthWorker(self._manager)
        self._health_worker.status_ready.connect(self._on_health_status)
        self._health_worker.start()

    def _on_health_status(self, status: Dict[str, bool]):
        self._server_status_cache = status
        for key, alive in status.items():
            if key in self._server_indicators:
                color = _GREEN if alive else _GREY
                self._server_indicators[key].setStyleSheet(f"color: {color};")

    def _log(self, msg: str):
        self._server_log.appendPlainText(msg)

    # ── CompTox slots ─────────────────────────────────────────────────────────

    def _run_comptox(self):
        if self._manager is None:
            QMessageBox.warning(self, "Not available", "tox_engine is not installed.")
            return
        text = self._comptox_input.text().strip()
        if not text:
            return
        components = [c.strip() for c in text.split(",") if c.strip()]

        client_raw = self._manager.get_client("comptox")
        try:
            from tox_engine.comptox_client import CompToxClient
            comptox = CompToxClient(client_raw)
        except Exception as e:
            self._comptox_status.setText(f"CompTox client error: {e}")
            return

        from tox_engine.workers import CompToxWorker
        self._comptox_progress.setVisible(True)
        self._comptox_progress.setValue(0)
        self._comptox_status.setText("Screening components ...")
        self._comptox_worker = CompToxWorker(comptox, components)
        self._comptox_worker.result_ready.connect(self._on_comptox_results)
        self._comptox_worker.error_occurred.connect(self._on_comptox_error)
        self._comptox_worker.progress.connect(
            lambda pct, msg: (self._comptox_progress.setValue(pct),
                              self._comptox_status.setText(msg))
        )
        self._comptox_worker.start()

    def _on_comptox_results(self, profiles: list):
        self._comptox_progress.setVisible(False)
        self._comptox_status.setText(f"{len(profiles)} component(s) screened.")
        self._comptox_table.setRowCount(0)
        self._comptox_profiles = profiles
        for p in profiles:
            row = self._comptox_table.rowCount()
            self._comptox_table.insertRow(row)
            self._comptox_table.setItem(row, 0, QTableWidgetItem(getattr(p, "name", "?")))
            risk = getattr(p, "risk_tier", "unknown")
            risk_item = QTableWidgetItem(risk)
            color = {
                "high":   QColor(_RED),
                "medium": QColor(_AMBER),
                "low":    QColor(_GREEN),
            }.get(risk.lower(), QColor(_GREY))
            risk_item.setForeground(color)
            if risk.lower() == "high":
                risk_item.setFont(QFont("Arial", -1, QFont.Weight.Bold))
            self._comptox_table.setItem(row, 1, risk_item)
            ghs = getattr(p, "ghs_codes", [])
            self._comptox_table.setItem(row, 2, QTableWidgetItem(", ".join(ghs) if ghs else "—"))
            carc = getattr(p, "carcinogenicity", "")
            self._comptox_table.setItem(row, 3, QTableWidgetItem(str(carc) if carc else "—"))
            acute = getattr(p, "acute_toxicity", "")
            self._comptox_table.setItem(row, 4, QTableWidgetItem(str(acute) if acute else "—"))
            noael = getattr(p, "noael", "")
            self._comptox_table.setItem(row, 5, QTableWidgetItem(str(noael) if noael else "—"))
            opera = getattr(p, "opera_predictions", {})
            flags = [f"{k}: {v}" for k, v in opera.items()] if isinstance(opera, dict) else []
            self._comptox_table.setItem(row, 6, QTableWidgetItem("; ".join(flags[:3]) if flags else "—"))

    def _on_comptox_error(self, msg: str):
        self._comptox_progress.setVisible(False)
        self._comptox_status.setText(f"Error: {msg}")

    def _on_comptox_row_selected(self):
        rows = self._comptox_table.selectedItems()
        if not rows:
            return
        row_idx = self._comptox_table.currentRow()
        if not hasattr(self, "_comptox_profiles") or row_idx >= len(self._comptox_profiles):
            return
        p = self._comptox_profiles[row_idx]
        lines = [f"<b>{getattr(p, 'name', '?')}</b>"]
        for attr in ["dtxsid", "casrn", "risk_tier", "ghs_codes", "ghs_hazard_statements",
                     "carcinogenicity", "mutagenicity", "reproductive_toxicity",
                     "acute_toxicity", "noael", "loael", "opera_predictions"]:
            val = getattr(p, attr, None)
            if val is not None and val != "" and val != [] and val != {}:
                lines.append(f"<b>{attr}:</b> {val}")
        self._comptox_detail.setHtml("<br>".join(lines))

    # ── ADMET slots ───────────────────────────────────────────────────────────

    def _run_admet(self):
        if self._manager is None:
            QMessageBox.warning(self, "Not available", "tox_engine is not installed.")
            return
        smiles = self._admet_input.text().strip()
        if not smiles:
            return

        client_raw = self._manager.get_client("admet")
        try:
            from tox_engine.admet_client import ADMETClient
            admet = ADMETClient(client_raw)
        except Exception as e:
            self._admet_status.setText(f"ADMET client error: {e}")
            return

        from tox_engine.workers import ADMETWorker
        self._admet_status.setText("Predicting ADMET properties ...")
        self._admet_worker = ADMETWorker(admet, smiles)
        self._admet_worker.result_ready.connect(self._on_admet_result)
        self._admet_worker.error_occurred.connect(
            lambda e: self._admet_status.setText(f"Error: {e}")
        )
        self._admet_worker.start()

        # Also request SVG render
        self._request_mol_render(admet, smiles)

    def _request_mol_render(self, admet_client, smiles: str):
        """Render molecule SVG in a thread."""
        class RenderWorker(QThread):
            done = pyqtSignal(str)

            def __init__(self, client, smi):
                super().__init__()
                self._client = client
                self._smi = smi

            def run(self):
                try:
                    svg = self._client.render_structure(self._smi)
                    self.done.emit(svg or "")
                except Exception:
                    self.done.emit("")

        self._render_worker = RenderWorker(admet_client, smiles)
        self._render_worker.done.connect(self._on_mol_render)
        self._render_worker.start()

    def _on_mol_render(self, svg: str):
        if svg:
            self._mol_svg_label.setText(svg)  # QLabel can render SVG via HTML
        else:
            self._mol_svg_label.setText("(Structure render not available)")

    def _on_admet_result(self, result):
        self._admet_status.setText(
            f"ADMET complete — toxicity flags: "
            f"{'Yes' if getattr(result, 'has_toxicity_flags', False) else 'None detected'}"
        )
        self._admet_table.setRowCount(0)

        # Populate from result attributes
        props = {}
        for attr in ["mw", "logp", "hbd", "hba", "tpsa", "rotatable_bonds",
                     "bioavailability", "caco2_permeability", "pgp_substrate",
                     "cyp3a4_inhibitor", "cyp2d6_inhibitor", "half_life",
                     "clearance", "vd", "bbb_penetration",
                     "ames_mutagenicity", "herg_inhibition", "hepatotoxicity",
                     "skin_sensitization", "eye_irritation", "ld50"]:
            val = getattr(result, attr, None)
            if val is not None:
                props[attr] = val

        # Also try pulling from a dict field
        if hasattr(result, "properties") and isinstance(result.properties, dict):
            props.update(result.properties)

        _tox_attrs = {"ames_mutagenicity", "herg_inhibition", "hepatotoxicity",
                      "skin_sensitization", "eye_irritation", "ld50",
                      "cyp3a4_inhibitor", "cyp2d6_inhibitor", "pgp_substrate"}

        for name, val in props.items():
            row = self._admet_table.rowCount()
            self._admet_table.insertRow(row)
            self._admet_table.setItem(row, 0, QTableWidgetItem(name.replace("_", " ").title()))
            self._admet_table.setItem(row, 1, QTableWidgetItem(str(val)))
            is_tox = name.lower() in _tox_attrs
            flag_text = ""
            if is_tox:
                positive = str(val).lower() in ("true", "1", "yes", "positive", "active")
                flag_text = "FLAG" if positive else ""
                if flag_text:
                    flag_item = QTableWidgetItem(flag_text)
                    flag_item.setForeground(QColor(_RED))
                    flag_item.setFont(QFont("Arial", -1, QFont.Weight.Bold))
                    self._admet_table.setItem(row, 2, flag_item)
            else:
                self._admet_table.setItem(row, 2, QTableWidgetItem(""))

        summary = getattr(result, "toxicity_summary", "")
        self._admet_tox_summary.setPlainText(summary or "No toxicity summary available.")

    # ── AOP slots ─────────────────────────────────────────────────────────────

    def _run_aop(self):
        if self._manager is None:
            QMessageBox.warning(self, "Not available", "tox_engine is not installed.")
            return
        text = self._aop_input.text().strip()
        if not text:
            return
        components = [c.strip() for c in text.split(",") if c.strip()]

        client_raw = self._manager.get_client("aop")
        try:
            from tox_engine.aop_client import AOPClient
            aop = AOPClient(client_raw)
        except Exception as e:
            self._aop_status.setText(f"AOP client error: {e}")
            return

        from tox_engine.workers import AOPWorker
        self._aop_progress.setVisible(True)
        self._aop_progress.setValue(0)
        self._aop_status.setText("Mapping AOPs ...")
        self._aop_worker = AOPWorker(aop, components)
        self._aop_worker.result_ready.connect(self._on_aop_results)
        self._aop_worker.error_occurred.connect(self._on_aop_error)
        self._aop_worker.progress.connect(
            lambda pct, msg: (self._aop_progress.setValue(pct),
                              self._aop_status.setText(msg))
        )
        self._aop_worker.start()

    def _on_aop_results(self, results: dict):
        self._aop_raw_results = results
        self._aop_progress.setVisible(False)
        total_aops = sum(
            len(getattr(r, "aops", [])) for r in results.values()
        )
        self._aop_status.setText(f"Found {total_aops} AOP mappings across {len(results)} component(s).")
        self._aop_table.setRowCount(0)

        for comp, mapping in results.items():
            aops = getattr(mapping, "aops", [])
            if not aops:
                row = self._aop_table.rowCount()
                self._aop_table.insertRow(row)
                self._aop_table.setItem(row, 0, QTableWidgetItem(comp))
                self._aop_table.setItem(row, 1, QTableWidgetItem("—"))
                self._aop_table.setItem(row, 2, QTableWidgetItem("No AOPs found"))
                self._aop_table.setItem(row, 3, QTableWidgetItem("—"))
                self._aop_table.setItem(row, 4, QTableWidgetItem("—"))
                continue
            for aop_item in aops:
                row = self._aop_table.rowCount()
                self._aop_table.insertRow(row)
                self._aop_table.setItem(row, 0, QTableWidgetItem(comp))
                aop_id = getattr(aop_item, "aop_id", getattr(aop_item, "id", "?"))
                self._aop_table.setItem(row, 1, QTableWidgetItem(str(aop_id)))
                aop_name = getattr(aop_item, "name", getattr(aop_item, "title", ""))
                self._aop_table.setItem(row, 2, QTableWidgetItem(aop_name))
                mie = getattr(aop_item, "mie", getattr(aop_item, "molecular_initiating_event", ""))
                self._aop_table.setItem(row, 3, QTableWidgetItem(str(mie)))
                ao = getattr(aop_item, "adverse_outcome", getattr(aop_item, "ao", ""))
                ao_item = QTableWidgetItem(str(ao))
                if ao:
                    ao_item.setForeground(QColor(_RED))
                self._aop_table.setItem(row, 4, ao_item)

    def _on_aop_error(self, msg: str):
        self._aop_progress.setVisible(False)
        self._aop_status.setText(f"Error: {msg}")

    def _on_aop_row_selected(self):
        rows = self._aop_table.selectedItems()
        if not rows:
            return
        row_idx = self._aop_table.currentRow()
        comp_name = self._aop_table.item(row_idx, 0)
        if not comp_name:
            return
        comp = comp_name.text()
        mapping = self._aop_raw_results.get(comp)
        if not mapping:
            return
        aops = getattr(mapping, "aops", [])
        aop_id_item = self._aop_table.item(row_idx, 1)
        aop_id = aop_id_item.text() if aop_id_item else None
        target_aop = next(
            (a for a in aops if str(getattr(a, "aop_id", getattr(a, "id", ""))) == aop_id),
            None
        )
        if not target_aop:
            return
        kes = getattr(target_aop, "key_events", [])
        if kes:
            lines = [f"Key Events for AOP {aop_id}:"]
            for ke in kes:
                ke_id   = getattr(ke, "ke_id", getattr(ke, "id", "?"))
                ke_name = getattr(ke, "name", getattr(ke, "title", str(ke)))
                ke_type = getattr(ke, "type", "")
                lines.append(f"  KE{ke_id}: {ke_name}" + (f" [{ke_type}]" if ke_type else ""))
            self._aop_ke_text.setPlainText("\n".join(lines))
        else:
            self._aop_ke_text.setPlainText("No key event detail available.")

    # ── PBPK slots ────────────────────────────────────────────────────────────

    def _browse_pbpk_model(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select PBPK Model", "", "PKml files (*.pkml);;All files (*)"
        )
        if path:
            self._pbpk_model_path = path
            self._pbpk_path_label.setText(path)
            self._pbpk_path_label.setStyleSheet("color: #2c3e50; font-size: 11px;")

    def _parse_pbpk_params(self) -> Dict[str, float]:
        params = {}
        for line in self._pbpk_params_edit.toPlainText().splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                name, _, val_str = line.partition("=")
                try:
                    params[name.strip()] = float(val_str.strip())
                except ValueError:
                    pass
        return params

    def _run_pbpk(self):
        if self._manager is None:
            QMessageBox.warning(self, "Not available", "tox_engine is not installed.")
            return
        if not self._pbpk_model_path:
            QMessageBox.information(self, "No model", "Browse for a .pkml model file first.")
            return

        client_raw = self._manager.get_client("pbpk")
        try:
            from tox_engine.pbpk_client import PBPKClient
            pbpk = PBPKClient(client_raw)
        except Exception as e:
            self._pbpk_status.setText(f"PBPK client error: {e}")
            return

        params = self._parse_pbpk_params()
        pop_mode = self._pbpk_sim_combo.currentText() == "Population"
        try:
            n_subjects = int(self._pbpk_n_subjects.text())
        except ValueError:
            n_subjects = 100

        self._pbpk_progress.setVisible(True)
        self._pbpk_progress.setValue(0)
        self._pbpk_status.setText("Running simulation ...")
        self._pbpk_run_btn.setEnabled(False)

        self._pbpk_worker = _PBPKWorker(
            pbpk, self._pbpk_model_path, params, pop_mode, n_subjects
        )
        self._pbpk_worker.result_ready.connect(self._on_pbpk_result)
        self._pbpk_worker.error_occurred.connect(self._on_pbpk_error)
        self._pbpk_worker.progress.connect(
            lambda pct, msg: (self._pbpk_progress.setValue(pct),
                              self._pbpk_status.setText(msg))
        )
        self._pbpk_worker.start()

    def _on_pbpk_result(self, result):
        self._pbpk_progress.setVisible(False)
        self._pbpk_run_btn.setEnabled(True)
        self._pbpk_status.setText("Simulation complete.")

        # Populate PK metrics table
        self._pk_metrics_table.setRowCount(0)
        metrics = getattr(result, "pk_metrics", None)
        if metrics is None:
            metrics = result if isinstance(result, dict) else {}

        metric_attrs = ["cmax", "tmax", "auc", "t_half", "cl", "vd",
                        "bioavailability", "mrt", "cmax_population_mean",
                        "auc_population_mean"]
        if hasattr(metrics, "__dict__"):
            for attr in metric_attrs:
                val = getattr(metrics, attr, None)
                if val is not None:
                    row = self._pk_metrics_table.rowCount()
                    self._pk_metrics_table.insertRow(row)
                    self._pk_metrics_table.setItem(row, 0, QTableWidgetItem(attr.upper()))
                    self._pk_metrics_table.setItem(row, 1, QTableWidgetItem(f"{val:.4g}" if isinstance(val, float) else str(val)))
        elif isinstance(metrics, dict):
            for k, v in metrics.items():
                row = self._pk_metrics_table.rowCount()
                self._pk_metrics_table.insertRow(row)
                self._pk_metrics_table.setItem(row, 0, QTableWidgetItem(str(k).upper()))
                self._pk_metrics_table.setItem(row, 1, QTableWidgetItem(f"{v:.4g}" if isinstance(v, float) else str(v)))

        # Attempt to plot concentration-time data
        time_pts  = getattr(result, "time_points", None)
        conc_pts  = getattr(result, "concentrations", None)
        if time_pts is not None and conc_pts is not None:
            self._plot_pk_curve(time_pts, conc_pts)

    def _on_pbpk_error(self, msg: str):
        self._pbpk_progress.setVisible(False)
        self._pbpk_run_btn.setEnabled(True)
        self._pbpk_status.setText(f"Simulation error: {msg}")

    def _plot_pk_curve(self, time_pts, conc_pts):
        """Embed a matplotlib PK curve into the PBPK plot area."""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

            fig, ax = plt.subplots(figsize=(5, 3))
            ax.plot(time_pts, conc_pts, color="#2980b9", linewidth=2)
            ax.set_xlabel("Time (h)")
            ax.set_ylabel("Concentration (mg/L)")
            ax.set_title("PK Concentration-Time Profile")
            ax.grid(True, alpha=0.3)
            fig.tight_layout()

            canvas = FigureCanvasQTAgg(fig)

            # Remove placeholder, add canvas
            self._pk_plot_placeholder.setVisible(False)
            self._plot_layout.addWidget(canvas)
        except ImportError:
            self._pk_plot_placeholder.setText(
                "Install matplotlib for PK curve plotting.\n"
                f"Simulation completed — see PK Metrics table."
            )
        except Exception as e:
            self._pk_plot_placeholder.setText(f"Plot error: {e}")

    # ── Public API for regulatory_tab ─────────────────────────────────────────

    def get_live_clients(self) -> dict:
        """
        Return dict of live MCP-wrapped clients for use by regulatory_tab.
        Only returns clients for servers that are actually running.
        Keys: "comptox", "admet", "aop" (pbpk not used in regulatory scoring).
        """
        if self._manager is None:
            return {}
        clients = {}
        try:
            if self._server_status_cache.get("comptox"):
                from tox_engine.comptox_client import CompToxClient
                clients["comptox"] = CompToxClient(self._manager.get_client("comptox"))
        except Exception:
            pass
        try:
            if self._server_status_cache.get("admet"):
                from tox_engine.admet_client import ADMETClient
                clients["admet"] = ADMETClient(self._manager.get_client("admet"))
        except Exception:
            pass
        try:
            if self._server_status_cache.get("aop"):
                from tox_engine.aop_client import AOPClient
                clients["aop"] = AOPClient(self._manager.get_client("aop"))
        except Exception:
            pass
        return clients
