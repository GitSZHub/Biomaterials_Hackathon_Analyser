"""
Drug Delivery Tab
=================
UI for compound search (PubChem + ChEMBL) and PK / release-profile modelling.

Sub-tabs:
  1. Compound Search  — search PubChem + ChEMBL, view properties, Lipinski flags
  2. PK Modelling     — configure Level 1/2/3 model, plot release curve
  3. AI Insight       — Claude interprets release profile in biomaterial context

Architecture:
  - All network calls in QThread workers (UI never blocks).
  - Matplotlib embedded via FigureCanvas for the PK plot.
  - PubChem + ChEMBL results displayed in a merged table.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFormLayout, QFrame, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QPushButton, QSplitter, QTabWidget, QTableWidget, QTableWidgetItem,
    QTextEdit, QVBoxLayout, QWidget,
)
import qtawesome as qta

logger = logging.getLogger(__name__)

# ── matplotlib ─────────────────────────────────────────────────────────────────
try:
    import matplotlib
    matplotlib.use("QtAgg")
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    _MPL_OK = True
except ImportError:
    _MPL_OK = False
    logger.warning("matplotlib unavailable — PK plot disabled")


# ── Workers ────────────────────────────────────────────────────────────────────

class PubChemSearchWorker(QThread):
    results_ready = pyqtSignal(list)
    error         = pyqtSignal(str)

    def __init__(self, query: str, max_results: int = 10):
        super().__init__()
        self.query       = query
        self.max_results = max_results

    def run(self):
        try:
            from drug_engine.pubchem_client import PubChemClient
            client  = PubChemClient()
            results = client.search(self.query, self.max_results)
            self.results_ready.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class ChEMBLSearchWorker(QThread):
    results_ready = pyqtSignal(list)
    error         = pyqtSignal(str)

    def __init__(self, query: str, max_results: int = 10):
        super().__init__()
        self.query       = query
        self.max_results = max_results

    def run(self):
        try:
            from drug_engine.chembl_client import ChEMBLClient
            client  = ChEMBLClient()
            results = client.search_molecule(self.query, self.max_results)
            self.results_ready.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class AIReleaseWorker(QThread):
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, model_name: str, summary: Dict,
                 compound_name: str, context: str):
        super().__init__()
        self.model_name    = model_name
        self.summary       = summary
        self.compound_name = compound_name
        self.context       = context

    def run(self):
        try:
            from ai_engine.llm_client import get_client
            s = self.summary
            prompt = (
                f"You are a biomaterials scientist specialising in drug delivery.\n"
                f"Compound: {self.compound_name or 'unknown'}.\n"
                f"PK model: {self.model_name}.\n"
                f"Model parameters: {s}.\n"
                f"Project context: {self.context or 'biomaterial scaffold for local drug delivery'}.\n\n"
                f"Provide a concise 3-paragraph interpretation:\n"
                f"1. Is the release profile suitable for the intended application? "
                f"   Comment on burst release, sustained phase, and therapeutic window.\n"
                f"2. What are the key risks (toxicity, subtherapeutic window, degradation)?\n"
                f"3. Recommended formulation adjustments or follow-up experiments."
            )
            client = get_client()
            text   = client.complete(prompt=prompt, max_tokens=500)
            self.finished.emit(text)
        except Exception as e:
            self.error.emit(str(e))


# ── Main Tab ───────────────────────────────────────────────────────────────────

class DrugTab(QWidget):
    """Drug Delivery: compound search + PK modelling + AI insight."""

    def __init__(self):
        super().__init__()
        self._pubchem_worker: Optional[PubChemSearchWorker] = None
        self._chembl_worker:  Optional[ChEMBLSearchWorker]  = None
        self._ai_worker:      Optional[AIReleaseWorker]     = None
        self._selected_compound: Dict = {}
        self._current_model_summary: Dict = {}
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        header = QLabel("Drug Delivery")
        header.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(header)

        tabs = QTabWidget()
        tabs.addTab(self._build_search_tab(),
                    qta.icon("fa5s.search"),    "Compound Search")
        tabs.addTab(self._build_pk_tab(),
                    qta.icon("fa5s.chart-line"), "PK Modelling")
        tabs.addTab(self._build_ai_tab(),
                    qta.icon("fa5s.magic"),     "AI Insight")
        self._tabs = tabs
        layout.addWidget(tabs)

    # ── Compound Search tab ────────────────────────────────────────────────────

    def _build_search_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        # Search bar
        bar = QFrame()
        bar.setFrameShape(QFrame.Shape.StyledPanel)
        bar_layout = QHBoxLayout(bar)
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(
            "e.g. dexamethasone  |  gentamicin  |  BMP-2  |  VEGF"
        )
        self._search_input.returnPressed.connect(self._run_search)
        bar_layout.addWidget(self._search_input, 3)

        search_btn = QPushButton("Search")
        search_btn.setIcon(qta.icon("fa5s.search"))
        search_btn.clicked.connect(self._run_search)
        bar_layout.addWidget(search_btn)
        layout.addWidget(bar)

        self._search_status = QLabel("Enter a drug or growth factor name to search.")
        layout.addWidget(self._search_status)

        # Results: PubChem + ChEMBL side by side
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # PubChem pane
        pc_frame = QFrame()
        pc_frame.setFrameShape(QFrame.Shape.StyledPanel)
        pc_layout = QVBoxLayout(pc_frame)
        pc_layout.addWidget(QLabel("<b>PubChem</b>"))
        self._pubchem_table = self._make_compound_table(
            ["CID", "Formula", "MW", "XLogP", "TPSA", "Lipinski"]
        )
        pc_layout.addWidget(self._pubchem_table)
        splitter.addWidget(pc_frame)

        # ChEMBL pane
        ch_frame = QFrame()
        ch_frame.setFrameShape(QFrame.Shape.StyledPanel)
        ch_layout = QVBoxLayout(ch_frame)
        ch_layout.addWidget(QLabel("<b>ChEMBL</b>"))
        self._chembl_table = self._make_compound_table(
            ["ChEMBL ID", "Name", "MW", "ALogP", "Max Phase", "RO5 violations"]
        )
        ch_layout.addWidget(self._chembl_table)
        splitter.addWidget(ch_frame)

        layout.addWidget(splitter)

        # Property detail panel
        detail_box = QGroupBox("Selected compound properties")
        detail_layout = QVBoxLayout(detail_box)
        self._detail_text = QTextEdit()
        self._detail_text.setReadOnly(True)
        self._detail_text.setMaximumHeight(120)
        self._detail_text.setPlaceholderText("Click a row to see full properties.")
        detail_layout.addWidget(self._detail_text)

        detail_btns = QHBoxLayout()
        use_btn = QPushButton("Use in PK Modelling")
        use_btn.setIcon(qta.icon("fa5s.arrow-right"))
        use_btn.clicked.connect(self._use_in_pk)
        detail_btns.addWidget(use_btn)

        self._open_pubchem_btn = QPushButton("Open in PubChem")
        self._open_pubchem_btn.setIcon(qta.icon("fa5s.external-link-alt"))
        self._open_pubchem_btn.setEnabled(False)
        self._open_pubchem_btn.clicked.connect(self._open_in_pubchem)
        detail_btns.addWidget(self._open_pubchem_btn)

        self._open_chembl_btn = QPushButton("Open in ChEMBL")
        self._open_chembl_btn.setIcon(qta.icon("fa5s.external-link-alt"))
        self._open_chembl_btn.setEnabled(False)
        self._open_chembl_btn.clicked.connect(self._open_in_chembl)
        detail_btns.addWidget(self._open_chembl_btn)

        detail_btns.addStretch()
        detail_layout.addLayout(detail_btns)
        layout.addWidget(detail_box)

        return w

    def _make_compound_table(self, headers: List[str]) -> QTableWidget:
        t = QTableWidget(0, len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        t.setAlternatingRowColors(True)
        t.itemSelectionChanged.connect(self._on_row_selected)
        return t

    # ── PK Modelling tab ───────────────────────────────────────────────────────

    def _build_pk_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        # Compound info strip
        self._pk_compound_label = QLabel("No compound selected. Search first (optional).")
        self._pk_compound_label.setWordWrap(True)
        layout.addWidget(self._pk_compound_label)

        # Model selector + parameters
        ctrl_layout = QHBoxLayout()

        model_box = QGroupBox("Model")
        model_v = QVBoxLayout(model_box)
        self._model_combo = QComboBox()
        self._model_combo.addItems([
            "Level 1 — First-order",
            "Level 2 — Biphasic (burst + sustained)",
            "Level 3 — Higuchi diffusion",
        ])
        self._model_combo.currentIndexChanged.connect(self._refresh_param_panel)
        model_v.addWidget(self._model_combo)
        ctrl_layout.addWidget(model_box)

        # Parameter panel (switches with model)
        self._param_box = QGroupBox("Parameters")
        self._param_layout = QFormLayout(self._param_box)
        ctrl_layout.addWidget(self._param_box, 2)

        # Simulation range
        sim_box = QGroupBox("Simulation")
        sim_v = QVBoxLayout(sim_box)
        sim_form = QFormLayout()
        self._tmax_spin = QDoubleSpinBox()
        self._tmax_spin.setRange(1, 8760)
        self._tmax_spin.setValue(72)
        self._tmax_spin.setSuffix(" h")
        sim_form.addRow("Duration:", self._tmax_spin)
        sim_v.addLayout(sim_form)
        run_btn = QPushButton("Run Model")
        run_btn.setIcon(qta.icon("fa5s.play"))
        run_btn.setStyleSheet("QPushButton { font-weight: bold; }")
        run_btn.clicked.connect(self._run_pk)
        sim_v.addWidget(run_btn)
        ctrl_layout.addWidget(sim_box)

        layout.addLayout(ctrl_layout)

        # Plot
        if _MPL_OK:
            self._pk_fig    = Figure(figsize=(9, 4), tight_layout=True)
            self._pk_canvas = FigureCanvas(self._pk_fig)
            layout.addWidget(self._pk_canvas)
        else:
            layout.addWidget(QLabel("Install matplotlib for the release plot."))

        # Summary
        self._pk_summary = QLabel("")
        self._pk_summary.setWordWrap(True)
        layout.addWidget(self._pk_summary)

        # Build initial parameter widgets
        self._param_widgets: Dict[str, QDoubleSpinBox] = {}
        self._refresh_param_panel(0)

        return w

    def _refresh_param_panel(self, idx: int):
        # Clear old widgets
        for i in reversed(range(self._param_layout.count())):
            item = self._param_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)   # type: ignore[arg-type]
        self._param_widgets.clear()

        model_params = [
            # Level 1
            [("dose (mg)",   "dose",    10.0,  0.001, 10000, 3, " mg"),
             ("k_el (1/h)",  "k_el",    0.1,   1e-6,  100,   4, " 1/h"),
             ("Vd (L)",      "vd",      1.0,   0.001, 1000,  3, " L"),
             ("Lag time (h)","t_lag",   0.0,   0.0,   24,    2, " h")],
            # Level 2
            [("dose (mg)",       "dose",       10.0,  0.001, 10000, 3, " mg"),
             ("Burst fraction",  "burst_frac", 0.3,   0.0,   1.0,   2, ""),
             ("k_fast (1/h)",    "k_fast",     1.0,   1e-4,  100,   4, " 1/h"),
             ("k_slow (1/h)",    "k_slow",     0.05,  1e-5,  10,    4, " 1/h"),
             ("Vd (L)",          "vd",         1.0,   0.001, 1000,  3, " L")],
            # Level 3
            [("dose (mg)",       "dose",  10.0,  0.001, 10000, 3, " mg"),
             ("D (cm²/h)",       "D",     1e-4,  1e-8,  1.0,   6, " cm²/h"),
             ("A (mg/cm³)",      "A",     100.0, 0.01,  5000,  2, " mg/cm³"),
             ("Cs (mg/cm³)",     "Cs",    10.0,  0.001, 1000,  3, " mg/cm³"),
             ("Vd (L)",          "vd",    1.0,   0.001, 1000,  3, " L")],
        ]

        for label, key, default, lo, hi, decimals, suffix in model_params[idx]:
            spin = QDoubleSpinBox()
            spin.setRange(lo, hi)
            spin.setValue(default)
            spin.setDecimals(decimals)
            if suffix:
                spin.setSuffix(suffix)
            self._param_layout.addRow(label, spin)
            self._param_widgets[key] = spin

    # ── AI Insight tab ─────────────────────────────────────────────────────────

    def _build_ai_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        ctx_layout = QHBoxLayout()
        ctx_layout.addWidget(QLabel("Project context:"))
        self._ai_context = QLineEdit()
        self._ai_context.setPlaceholderText(
            "e.g. controlled release from GelMA scaffold, post-surgical wound healing"
        )
        ctx_layout.addWidget(self._ai_context)
        layout.addLayout(ctx_layout)

        btn_layout = QHBoxLayout()
        self._ai_btn = QPushButton("Interpret Release Profile with AI")
        self._ai_btn.setIcon(qta.icon("fa5s.magic"))
        self._ai_btn.clicked.connect(self._run_ai)
        btn_layout.addWidget(self._ai_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self._ai_output = QTextEdit()
        self._ai_output.setReadOnly(True)
        self._ai_output.setPlaceholderText(
            "AI interpretation will appear here.\n\n"
            "Run a PK model first (PK Modelling tab), then click the button above."
        )
        layout.addWidget(self._ai_output)

        return w

    # ── Slots: Compound Search ─────────────────────────────────────────────────

    def _run_search(self):
        query = self._search_input.text().strip()
        if not query:
            return
        self._search_status.setText(f"Searching PubChem + ChEMBL for: {query} ...")
        self._pubchem_table.setRowCount(0)
        self._chembl_table.setRowCount(0)
        self._detail_text.clear()

        self._pubchem_worker = PubChemSearchWorker(query)
        self._pubchem_worker.results_ready.connect(self._on_pubchem_results)
        self._pubchem_worker.error.connect(lambda e: self._search_status.setText(
            f"PubChem error: {e}"))
        self._pubchem_worker.start()

        self._chembl_worker = ChEMBLSearchWorker(query)
        self._chembl_worker.results_ready.connect(self._on_chembl_results)
        self._chembl_worker.error.connect(lambda e: logger.warning(
            f"ChEMBL error: {e}"))
        self._chembl_worker.start()

    def _on_pubchem_results(self, results: list):
        self._search_status.setText(
            f"PubChem: {len(results)} result(s). ChEMBL: searching ..."
        )
        self._pubchem_table.setRowCount(0)
        for r in results:
            row = self._pubchem_table.rowCount()
            self._pubchem_table.insertRow(row)
            self._pubchem_table.setItem(row, 0, QTableWidgetItem(str(r.get("cid", ""))))
            self._pubchem_table.setItem(row, 1, QTableWidgetItem(r.get("formula", "")))
            self._pubchem_table.setItem(row, 2, QTableWidgetItem(f"{r.get('mw', 0):.1f}"))
            self._pubchem_table.setItem(row, 3, QTableWidgetItem(f"{r.get('xlogp', 0):.2f}"))
            self._pubchem_table.setItem(row, 4, QTableWidgetItem(f"{r.get('tpsa', 0):.1f}"))
            lip = r.get("drug_likeness", "")
            lip_item = QTableWidgetItem(lip)
            lip_item.setForeground(
                QColor("#27ae60") if lip == "Pass" else QColor("#c0392b")
            )
            self._pubchem_table.setItem(row, 5, lip_item)
            # Store full record in hidden role for detail view
            self._pubchem_table.item(row, 0).setData(
                Qt.ItemDataRole.UserRole, r
            )

    def _on_chembl_results(self, results: list):
        self._search_status.setText(
            f"Search complete. PubChem + ChEMBL results shown."
        )
        self._chembl_table.setRowCount(0)
        for r in results:
            row = self._chembl_table.rowCount()
            self._chembl_table.insertRow(row)
            self._chembl_table.setItem(row, 0, QTableWidgetItem(r.get("chembl_id", "")))
            self._chembl_table.setItem(row, 1, QTableWidgetItem(r.get("name", "")))
            self._chembl_table.setItem(row, 2, QTableWidgetItem(f"{r.get('mw', 0):.1f}"))
            self._chembl_table.setItem(row, 3, QTableWidgetItem(f"{r.get('alogp', 0):.2f}"))
            phase = r.get("max_phase", 0)
            phase_item = QTableWidgetItem(str(phase) if phase else "—")
            if phase and int(phase) >= 3:
                phase_item.setForeground(QColor("#27ae60"))
            self._chembl_table.setItem(row, 4, phase_item)
            self._chembl_table.setItem(row, 5,
                QTableWidgetItem(str(r.get("ro5_violations", ""))))
            self._chembl_table.item(row, 0).setData(
                Qt.ItemDataRole.UserRole, r
            )

    def _on_row_selected(self):
        sender = self.sender()
        if not sender:
            return
        rows = sender.selectedItems()
        if not rows:
            return
        # Get the first column of the selected row
        row_idx = rows[0].row()
        item = sender.item(row_idx, 0)
        if not item:
            return
        record = item.data(Qt.ItemDataRole.UserRole)
        if not record:
            return
        self._selected_compound = record
        lines = [f"<b>{record.get('name') or record.get('iupac_name') or 'Unknown'}</b>"]
        for k, v in record.items():
            if k not in ("smiles",):
                lines.append(f"<b>{k}:</b> {v}")
        self._detail_text.setHtml("<br>".join(lines))

        # Enable relevant browser button
        self._open_pubchem_btn.setEnabled(bool(record.get("cid")))
        self._open_chembl_btn.setEnabled(bool(record.get("chembl_id")))

    def _use_in_pk(self):
        name = (self._selected_compound.get("name")
                or self._selected_compound.get("iupac_name")
                or "Selected compound")
        self._pk_compound_label.setText(f"Compound: <b>{name}</b>")
        self._tabs.setCurrentIndex(1)

    def _open_in_pubchem(self):
        cid = self._selected_compound.get("cid")
        if cid:
            import webbrowser
            webbrowser.open(f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}")

    def _open_in_chembl(self):
        chembl_id = self._selected_compound.get("chembl_id")
        if chembl_id:
            import webbrowser
            webbrowser.open(f"https://www.ebi.ac.uk/chembl/compound_report_card/{chembl_id}/")

    # ── Slots: PK Modelling ───────────────────────────────────────────────────

    def _run_pk(self):
        idx       = self._model_combo.currentIndex()
        model_key = ["first_order", "biphasic", "higuchi"][idx]
        t_max     = self._tmax_spin.value()

        kwargs = {k: w.value() for k, w in self._param_widgets.items()}
        kwargs["t_max"] = t_max

        try:
            from drug_engine.pk_models import simulate_release, PKLevel1, PKLevel2, PKLevel3
            import numpy as np
            t, c = simulate_release(model_key, **kwargs)

            # Build summary
            model_cls = [PKLevel1, PKLevel2, PKLevel3][idx]
            m_kwargs = {k: w.value() for k, w in self._param_widgets.items()}
            model_obj = model_cls(**m_kwargs)
            self._current_model_summary = model_obj.summary()

            self._draw_pk_plot(t, c, model_key, idx)
            self._pk_summary.setText(
                "  |  ".join(f"{k}: {v}"
                             for k, v in self._current_model_summary.items())
            )
        except Exception as e:
            QMessageBox.warning(self, "Model error", str(e))

    def _draw_pk_plot(self, t, c, model_key: str, level_idx: int):
        if not _MPL_OK:
            return
        self._pk_fig.clear()
        ax = self._pk_fig.add_subplot(111)

        y_label = "Cumulative fraction released" if model_key == "higuchi" \
                  else "Concentration (mg/L)"

        ax.plot(t, c, color="#2E86AB", linewidth=2)
        ax.fill_between(t, c, alpha=0.15, color="#2E86AB")
        ax.set_xlabel("Time (h)", fontsize=10)
        ax.set_ylabel(y_label, fontsize=10)

        compound = (self._selected_compound.get("name")
                    or self._selected_compound.get("iupac_name")
                    or "compound")
        title = f"Release profile — {compound}  [{self._model_combo.currentText()}]"
        ax.set_title(title, fontsize=10)
        ax.grid(True, alpha=0.3)

        # Mark t90 for Higuchi
        if model_key == "higuchi":
            ax.axhline(0.9, color="grey", linestyle="--", linewidth=0.8, alpha=0.7,
                       label="90% release")
            ax.legend(fontsize=8)

        self._pk_canvas.draw()

    # ── Slots: AI Insight ──────────────────────────────────────────────────────

    def _run_ai(self):
        if not self._current_model_summary:
            QMessageBox.information(self, "No model",
                                    "Run a PK model first (PK Modelling tab).")
            return
        compound = (self._selected_compound.get("name")
                    or self._selected_compound.get("iupac_name")
                    or "")
        model_name = self._model_combo.currentText()
        context    = self._ai_context.text().strip()

        self._ai_output.setText("Asking AI for interpretation ...")
        self._ai_btn.setEnabled(False)

        self._ai_worker = AIReleaseWorker(
            model_name, self._current_model_summary, compound, context
        )
        self._ai_worker.finished.connect(self._on_ai_finished)
        self._ai_worker.error.connect(self._on_ai_error)
        self._ai_worker.start()

    def _on_ai_finished(self, text: str):
        self._ai_output.setText(text)
        self._ai_btn.setEnabled(True)

    def _on_ai_error(self, msg: str):
        self._ai_output.setText(
            f"AI interpretation unavailable: {msg}\n\n"
            "Check that ANTHROPIC_API_KEY is set."
        )
        self._ai_btn.setEnabled(True)
