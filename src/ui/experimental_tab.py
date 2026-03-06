"""
Experimental Design Tab
=======================
Five sub-tabs:
  1. Design Wizard      -- generate a staged roadmap for tissue + scenario
  2. Cell Models        -- browse / filter in vitro cell model knowledge base
  3. Organism Models    -- browse / filter in vivo organism model knowledge base
  4. DBTL Tracker       -- record and review Design-Build-Test-Learn iterations
  5. AI Advisor         -- Claude interprets roadmap and advises on 3Rs / priorities
"""

from __future__ import annotations

import logging
from typing import List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel, QPushButton,
    QComboBox, QCheckBox, QSpinBox, QTextEdit, QTableWidget, QTableWidgetItem,
    QScrollArea, QFrame, QFormLayout, QLineEdit, QSplitter, QHeaderView,
    QGroupBox, QDialog, QDialogButtonBox, QPlainTextEdit,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor
import qtawesome as qta

logger = logging.getLogger(__name__)

# ── Safe imports ───────────────────────────────────────────────────────────────

try:
    from experimental_engine import (
        ExperimentalDesigner, ExperimentalRoadmap, RoadmapStage,
        DBTLTracker, DBTLCycle,
        get_cell_models_for_tissue, get_organism_models_for_tissue,
        ALL_CELL_MODELS, ALL_ORGANISM_MODELS,
        search_cell_models, list_cell_tissues,
        get_small_animal_models, get_large_animal_models, get_alternatives,
        CellModel, OrganismModel,
    )
    _ENGINE_OK = True
except ImportError as e:
    logger.warning("experimental_engine not available: %s", e)
    _ENGINE_OK = False

try:
    from ai_engine.llm_client import LLMClient
    _LLM_OK = True
except ImportError:
    _LLM_OK = False


# ── Worker threads ─────────────────────────────────────────────────────────────

class RoadmapWorker(QThread):
    finished = pyqtSignal(object)   # ExperimentalRoadmap
    error    = pyqtSignal(str)

    def __init__(self, tissue, scenario, has_cell, has_animal, has_gmp, months):
        super().__init__()
        self.tissue = tissue; self.scenario = scenario
        self.has_cell = has_cell; self.has_animal = has_animal
        self.has_gmp = has_gmp; self.months = months

    def run(self):
        try:
            roadmap = ExperimentalDesigner().generate(
                tissue=self.tissue,
                scenario=self.scenario,
                has_cell_lab=self.has_cell,
                has_animal_facility=self.has_animal,
                has_gmp=self.has_gmp,
                timeline_months=self.months,
            )
            self.finished.emit(roadmap)
        except Exception as e:
            self.error.emit(str(e))


class AIAdvisorWorker(QThread):
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, context: str):
        super().__init__()
        self._context = context

    def run(self):
        if not _LLM_OK:
            self.error.emit("AI engine not available"); return
        try:
            client = LLMClient()
            prompt = (
                "You are an expert in biomaterials preclinical research, 3Rs principles, and ISO 10993 compliance.\n\n"
                "Review the following experimental roadmap and provide concise, actionable advice on:\n"
                "1. The appropriateness of the model selection for the target tissue\n"
                "2. 3Rs opportunities (replacement/reduction/refinement)\n"
                "3. Any missing critical experiments or endpoints\n"
                "4. The most likely scientific or regulatory bottleneck\n"
                "5. One concrete suggestion to accelerate the programme\n\n"
                f"ROADMAP CONTEXT:\n{self._context}"
            )
            response = client.complete(prompt, max_tokens=800)
            self.finished.emit(response)
        except Exception as e:
            self.error.emit(str(e))


# ── Main tab ───────────────────────────────────────────────────────────────────

class ExperimentalTab(QWidget):

    TISSUES = [
        "bone", "cartilage", "skin", "cardiovascular", "cardiac",
        "neural", "liver", "eye", "tendon", "adipose", "general",
    ]
    SCENARIOS = [
        ("A — Inert scaffold / medical device", "A"),
        ("B — Scaffold + drug (combination product)", "B"),
        ("C — Scaffold + living cells (ATMP)", "C"),
        ("D — GMO manufacturing (standard device product)", "D"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._roadmap: Optional[ExperimentalRoadmap] = None
        self._dbtl = DBTLTracker() if _ENGINE_OK else None
        self._worker: Optional[QThread] = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()
        tabs.addTab(self._build_wizard_tab(),    qta.icon('fa5s.map'),         "Design Wizard")
        tabs.addTab(self._build_cell_tab(),      qta.icon('fa5.circle'),    "Cell Models")
        tabs.addTab(self._build_organism_tab(),  qta.icon('fa5s.paw'),         "Organism Models")
        tabs.addTab(self._build_dbtl_tab(),      qta.icon('fa5s.sync'),     "DBTL Tracker")
        tabs.addTab(self._build_ai_tab(),        qta.icon('fa5s.lightbulb'), "AI Advisor")
        layout.addWidget(tabs)

    # ── Sub-tab 1: Design Wizard ───────────────────────────────────────────────

    def _build_wizard_tab(self) -> QWidget:
        w = QWidget()
        main = QHBoxLayout(w)

        # Left panel — controls
        left = QFrame()
        left.setMaximumWidth(300)
        left.setStyleSheet("QFrame { background:#f8f9fa; border-right:1px solid #dee2e6; }")
        form_layout = QVBoxLayout(left)
        form_layout.setContentsMargins(12, 12, 12, 12)

        form_layout.addWidget(self._section_label("Target Tissue"))
        self._tissue_combo = QComboBox()
        self._tissue_combo.addItems([t.title() for t in self.TISSUES])
        form_layout.addWidget(self._tissue_combo)

        form_layout.addWidget(self._section_label("Regulatory Scenario"))
        self._scenario_combo = QComboBox()
        for label, _ in self.SCENARIOS:
            self._scenario_combo.addItem(label)
        form_layout.addWidget(self._scenario_combo)

        form_layout.addWidget(self._section_label("Available Resources"))
        self._chk_cell  = QCheckBox("Cell culture laboratory")
        self._chk_animal= QCheckBox("Animal facility (licensed)")
        self._chk_gmp   = QCheckBox("GMP manufacturing")
        self._chk_cell.setChecked(True)
        self._chk_animal.setChecked(True)
        for chk in (self._chk_cell, self._chk_animal, self._chk_gmp):
            form_layout.addWidget(chk)

        form_layout.addWidget(self._section_label("Timeline Constraint (months)"))
        self._timeline_spin = QSpinBox()
        self._timeline_spin.setRange(6, 240)
        self._timeline_spin.setValue(24)
        form_layout.addWidget(self._timeline_spin)

        form_layout.addStretch()

        self._gen_btn = QPushButton(qta.icon('fa5s.play'), "  Generate Roadmap")
        self._gen_btn.setStyleSheet(self._primary_btn_style())
        self._gen_btn.clicked.connect(self._generate_roadmap)
        form_layout.addWidget(self._gen_btn)

        main.addWidget(left)

        # Right panel — roadmap display
        right = QWidget()
        right_layout = QVBoxLayout(right)

        self._roadmap_header = QLabel("Configure parameters and click Generate Roadmap.")
        self._roadmap_header.setWordWrap(True)
        self._roadmap_header.setStyleSheet("font-size:13px; color:#495057; padding:8px;")
        right_layout.addWidget(self._roadmap_header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._roadmap_container = QWidget()
        self._roadmap_layout = QVBoxLayout(self._roadmap_container)
        self._roadmap_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._roadmap_container)
        right_layout.addWidget(scroll)

        main.addWidget(right)
        return w

    def _generate_roadmap(self):
        if not _ENGINE_OK:
            self._roadmap_header.setText("Experimental engine not available.")
            return
        tissue = self.TISSUES[self._tissue_combo.currentIndex()]
        _, scenario = self.SCENARIOS[self._scenario_combo.currentIndex()]
        self._gen_btn.setEnabled(False)
        self._gen_btn.setText("  Generating...")
        self._worker = RoadmapWorker(
            tissue, scenario,
            self._chk_cell.isChecked(),
            self._chk_animal.isChecked(),
            self._chk_gmp.isChecked(),
            self._timeline_spin.value(),
        )
        self._worker.finished.connect(self._on_roadmap_ready)
        self._worker.error.connect(self._on_roadmap_error)
        self._worker.start()

    def _on_roadmap_ready(self, roadmap: ExperimentalRoadmap):
        self._roadmap = roadmap
        self._gen_btn.setEnabled(True)
        self._gen_btn.setText("  Generate Roadmap")
        self._roadmap_header.setText(
            f"Roadmap: {roadmap.tissue.title()} tissue  |  Scenario {roadmap.scenario}  "
            f"|  Estimated total: {roadmap.total_duration}\n"
            f"Critical path: {roadmap.critical_path}"
        )
        # Clear and repopulate
        for i in reversed(range(self._roadmap_layout.count())):
            item = self._roadmap_layout.itemAt(i)
            if item and item.widget():
                item.widget().deleteLater()
        for stage in roadmap.stages:
            self._roadmap_layout.addWidget(self._make_stage_card(stage))

    def _on_roadmap_error(self, msg: str):
        self._gen_btn.setEnabled(True)
        self._gen_btn.setText("  Generate Roadmap")
        self._roadmap_header.setText(f"Error: {msg}")

    def _make_stage_card(self, stage: RoadmapStage) -> QFrame:
        phase_colors = {
            "in_vitro": "#d4edda", "in_vivo": "#fff3cd",
            "regulatory": "#cce5ff", "clinical": "#f8d7da",
        }
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {phase_colors.get(stage.phase, '#f8f9fa')};
                border: 1px solid #dee2e6;
                border-left: 4px solid #2E86AB;
                border-radius: 6px;
                margin: 4px 0;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 8)

        # Header row
        hdr = QHBoxLayout()
        title = QLabel(f"Stage {stage.stage_number}: {stage.name}")
        title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        hdr.addWidget(title)
        hdr.addStretch()
        dur = QLabel(f"{stage.duration_weeks} weeks")
        dur.setStyleSheet("color:#6c757d; font-size:10px;")
        hdr.addWidget(dur)
        layout.addLayout(hdr)

        # Objective
        obj = QLabel(stage.objective)
        obj.setWordWrap(True)
        obj.setStyleSheet("color:#495057; font-size:10px; margin-top:2px;")
        layout.addWidget(obj)

        # Assays
        if stage.assays:
            assay_label = QLabel("Assays: " + "  |  ".join(stage.assays[:5]) +
                                 (f"  +{len(stage.assays)-5} more" if len(stage.assays) > 5 else ""))
            assay_label.setWordWrap(True)
            assay_label.setStyleSheet("color:#212529; font-size:10px;")
            layout.addWidget(assay_label)

        # Models
        models_parts = []
        if stage.cell_models:
            models_parts.append("Cells: " + ", ".join(m.name for m in stage.cell_models))
        if stage.organism_models:
            models_parts.append("In vivo: " + ", ".join(m.name for m in stage.organism_models))
        if models_parts:
            ml = QLabel("  |  ".join(models_parts))
            ml.setStyleSheet("color:#6c757d; font-size:10px; font-style:italic;")
            layout.addWidget(ml)

        # Milestone
        if stage.milestone:
            ms = QLabel(f"Go/No-Go: {stage.milestone}")
            ms.setWordWrap(True)
            ms.setStyleSheet("color:#155724; font-size:10px; font-weight:bold;")
            layout.addWidget(ms)

        # ISO refs
        if stage.iso_standards:
            iso_lbl = QLabel("ISO: " + ", ".join(stage.iso_standards))
            iso_lbl.setStyleSheet("color:#004085; font-size:10px;")
            layout.addWidget(iso_lbl)

        return card

    # ── Sub-tab 2: Cell Models ─────────────────────────────────────────────────

    def _build_cell_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        # Filter bar
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Tissue:"))
        self._cell_tissue_filter = QComboBox()
        self._cell_tissue_filter.addItem("All")
        if _ENGINE_OK:
            self._cell_tissue_filter.addItems([t.title() for t in list_cell_tissues()])
        self._cell_tissue_filter.currentTextChanged.connect(self._filter_cell_models)
        bar.addWidget(self._cell_tissue_filter)

        bar.addWidget(QLabel("Search:"))
        self._cell_search = QLineEdit()
        self._cell_search.setPlaceholderText("Name, cell type, assay...")
        self._cell_search.textChanged.connect(self._filter_cell_models)
        bar.addWidget(self._cell_search)

        self._iso_only_chk = QCheckBox("ISO 10993 only")
        self._iso_only_chk.stateChanged.connect(self._filter_cell_models)
        bar.addWidget(self._iso_only_chk)
        bar.addStretch()
        layout.addLayout(bar)

        # Table
        self._cell_table = QTableWidget()
        self._cell_table.setColumnCount(7)
        self._cell_table.setHorizontalHeaderLabels([
            "Name", "Species", "Cell Type", "Tissues", "ISO 10993", "Relevance", "3Rs"
        ])
        self._cell_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._cell_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._cell_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._cell_table.itemSelectionChanged.connect(self._show_cell_detail)
        layout.addWidget(self._cell_table)

        # Detail panel
        self._cell_detail = QTextEdit()
        self._cell_detail.setMaximumHeight(140)
        self._cell_detail.setReadOnly(True)
        self._cell_detail.setPlaceholderText("Select a row for cell model details...")
        layout.addWidget(self._cell_detail)

        self._populate_cell_table(list(ALL_CELL_MODELS.values()) if _ENGINE_OK else [])
        return w

    def _filter_cell_models(self):
        if not _ENGINE_OK:
            return
        tissue_txt = self._cell_tissue_filter.currentText()
        query = self._cell_search.text().strip()
        iso_only = self._iso_only_chk.isChecked()

        if query:
            models = search_cell_models(query)
        elif tissue_txt and tissue_txt != "All":
            models = get_cell_models_for_tissue(tissue_txt.lower())
        else:
            models = list(ALL_CELL_MODELS.values())

        if iso_only:
            models = [m for m in models if m.iso10993]

        self._populate_cell_table(models)

    def _populate_cell_table(self, models: list):
        self._cell_table.setRowCount(0)
        for m in models:
            r = self._cell_table.rowCount()
            self._cell_table.insertRow(r)
            self._cell_table.setItem(r, 0, QTableWidgetItem(m.name))
            self._cell_table.setItem(r, 1, QTableWidgetItem(m.species))
            self._cell_table.setItem(r, 2, QTableWidgetItem(m.cell_type))
            self._cell_table.setItem(r, 3, QTableWidgetItem(", ".join(m.tissues)))
            iso_item = QTableWidgetItem("Yes" if m.iso10993 else "No")
            if m.iso10993:
                iso_item.setForeground(QColor("#155724"))
            self._cell_table.setItem(r, 4, iso_item)
            self._cell_table.setItem(r, 5, QTableWidgetItem(m.translational_relevance))
            self._cell_table.setItem(r, 6, QTableWidgetItem(m.three_rs_score))
            self._cell_table.item(r, 0).setData(Qt.ItemDataRole.UserRole, m)

    def _show_cell_detail(self):
        sel = self._cell_table.selectedItems()
        if not sel:
            return
        m: CellModel = self._cell_table.item(sel[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        if m is None:
            return
        lines = [
            f"<b>{m.full_name}</b>",
            f"Species: {m.species}  |  Source: {m.source}",
            f"ISO 10993 tests: {', '.join(m.iso_tests) if m.iso_tests else 'None'}",
            f"Translational relevance: {m.translational_relevance}",
            f"Culture notes: {m.culture_notes}",
            "<b>Typical assays:</b> " + "; ".join(m.typical_assays),
        ]
        self._cell_detail.setHtml("<br>".join(lines))

    # ── Sub-tab 3: Organism Models ─────────────────────────────────────────────

    def _build_organism_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        # Filter bar
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Filter:"))
        self._org_filter = QComboBox()
        self._org_filter.addItems(["All", "Small Animal", "Large Animal", "3Rs Alternatives", "ISO 10993"])
        self._org_filter.currentTextChanged.connect(self._filter_org_models)
        bar.addWidget(self._org_filter)

        self._org_tissue_filter = QComboBox()
        self._org_tissue_filter.addItem("All tissues")
        self._org_tissue_filter.addItems([t.title() for t in ["bone", "cartilage", "skin", "general", "neural"]])
        self._org_tissue_filter.currentTextChanged.connect(self._filter_org_models)
        bar.addWidget(self._org_tissue_filter)
        bar.addStretch()
        layout.addLayout(bar)

        # Table
        self._org_table = QTableWidget()
        self._org_table.setColumnCount(7)
        self._org_table.setHorizontalHeaderLabels([
            "Model", "Species", "Model Type", "Tissues", "ISO 10993", "Regulatory", "3Rs"
        ])
        self._org_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._org_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._org_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._org_table.itemSelectionChanged.connect(self._show_org_detail)
        layout.addWidget(self._org_table)

        # Detail panel
        self._org_detail = QTextEdit()
        self._org_detail.setMaximumHeight(160)
        self._org_detail.setReadOnly(True)
        self._org_detail.setPlaceholderText("Select a row for model details...")
        layout.addWidget(self._org_detail)

        self._populate_org_table(list(ALL_ORGANISM_MODELS.values()) if _ENGINE_OK else [])
        return w

    def _filter_org_models(self):
        if not _ENGINE_OK:
            return
        f = self._org_filter.currentText()
        tissue_txt = self._org_tissue_filter.currentText()

        if f == "Small Animal":
            models = get_small_animal_models()
        elif f == "Large Animal":
            models = get_large_animal_models()
        elif f == "3Rs Alternatives":
            models = get_alternatives()
        elif f == "ISO 10993":
            from experimental_engine import get_iso10993_organism_models
            models = get_iso10993_organism_models()
        else:
            models = list(ALL_ORGANISM_MODELS.values())

        if tissue_txt and tissue_txt != "All tissues":
            models = [m for m in models
                      if any(tissue_txt.lower() in t.lower() for t in m.tissues)]
        self._populate_org_table(models)

    def _populate_org_table(self, models: list):
        self._org_table.setRowCount(0)
        for m in models:
            r = self._org_table.rowCount()
            self._org_table.insertRow(r)
            self._org_table.setItem(r, 0, QTableWidgetItem(m.name))
            self._org_table.setItem(r, 1, QTableWidgetItem(m.species))
            self._org_table.setItem(r, 2, QTableWidgetItem(m.model_type))
            self._org_table.setItem(r, 3, QTableWidgetItem(", ".join(m.tissues)))
            iso_item = QTableWidgetItem("Yes" if m.iso10993 else "No")
            if m.iso10993:
                iso_item.setForeground(QColor("#155724"))
            self._org_table.setItem(r, 4, iso_item)
            self._org_table.setItem(r, 5, QTableWidgetItem(m.regulatory_acceptance))
            self._org_table.setItem(r, 6, QTableWidgetItem(m.three_rs_category))
            self._org_table.item(r, 0).setData(Qt.ItemDataRole.UserRole, m)

    def _show_org_detail(self):
        sel = self._org_table.selectedItems()
        if not sel:
            return
        m: OrganismModel = self._org_table.item(sel[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        if m is None:
            return
        lines = [
            f"<b>{m.name}</b> ({m.species} — {m.strain})",
            f"Model type: {m.model_type}  |  Implant duration: {m.implant_duration}",
        ]
        if m.defect_size:
            lines.append(f"Defect size: {m.defect_size}")
        if m.iso_parts:
            lines.append(f"ISO standards: {', '.join(m.iso_parts)}")
        lines.append("<b>Endpoint assays:</b> " + "; ".join(m.endpoint_assays[:5]))
        lines.append("<b>Strengths:</b> " + "; ".join(m.strengths[:3]))
        lines.append("<b>Limitations:</b> " + "; ".join(m.limitations[:3]))
        self._org_detail.setHtml("<br>".join(lines))

    # ── Sub-tab 4: DBTL Tracker ────────────────────────────────────────────────

    def _build_dbtl_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        # Toolbar
        bar = QHBoxLayout()
        add_btn = QPushButton(qta.icon('fa5s.plus'), " Add Cycle")
        add_btn.clicked.connect(self._add_dbtl_cycle)
        add_btn.setStyleSheet(self._primary_btn_style())
        refresh_btn = QPushButton(qta.icon('fa5s.sync'), " Refresh")
        refresh_btn.clicked.connect(self._refresh_dbtl)
        bar.addWidget(add_btn)
        bar.addWidget(refresh_btn)
        bar.addStretch()
        layout.addLayout(bar)

        # Table
        self._dbtl_table = QTableWidget()
        self._dbtl_table.setColumnCount(6)
        self._dbtl_table.setHorizontalHeaderLabels([
            "Iteration", "Status", "Hypothesis", "Material", "Go/No-Go", "Updated"
        ])
        self._dbtl_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._dbtl_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._dbtl_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._dbtl_table.itemSelectionChanged.connect(self._show_dbtl_detail)
        layout.addWidget(self._dbtl_table)

        # Detail panel
        self._dbtl_detail = QTextEdit()
        self._dbtl_detail.setMaximumHeight(200)
        self._dbtl_detail.setReadOnly(True)
        self._dbtl_detail.setPlaceholderText("Select a cycle to view full details...")
        layout.addWidget(self._dbtl_detail)

        # Action bar for selected cycle
        action_bar = QHBoxLayout()
        self._advance_btn = QPushButton(qta.icon('fa5s.arrow-right'), " Advance Phase")
        self._advance_btn.clicked.connect(self._advance_phase)
        self._record_btn  = QPushButton(qta.icon('fa5s.pencil-alt'),      " Record Results")
        self._record_btn.clicked.connect(self._record_results)
        self._learn_btn   = QPushButton(qta.icon('fa5s.graduation-cap'), " Record Learning")
        self._learn_btn.clicked.connect(self._record_learning)
        for btn in (self._advance_btn, self._record_btn, self._learn_btn):
            action_bar.addWidget(btn)
        action_bar.addStretch()
        layout.addLayout(action_bar)

        self._refresh_dbtl()
        return w

    def _refresh_dbtl(self):
        if not self._dbtl:
            return
        rows = self._dbtl.summary_table()
        self._dbtl_table.setRowCount(0)
        for row in rows:
            r = self._dbtl_table.rowCount()
            self._dbtl_table.insertRow(r)
            for col, key in enumerate(["Iteration", "Status", "Hypothesis", "Material", "Go/No-Go", "Updated"]):
                item = QTableWidgetItem(row.get(key, ""))
                if key == "Status":
                    colors = {"Design": "#cce5ff", "Build": "#fff3cd",
                              "Test": "#d4edda", "Learn": "#f8d7da", "Complete": "#d1ecf1"}
                    item.setBackground(QColor(colors.get(row.get("Status", ""), "#ffffff")))
                self._dbtl_table.setItem(r, col, item)

    def _show_dbtl_detail(self):
        if not self._dbtl:
            return
        sel = self._dbtl_table.selectedItems()
        if not sel:
            return
        iteration = int(self._dbtl_table.item(sel[0].row(), 0).text())
        all_cycles = self._dbtl.get_all_cycles()
        cycle = next((c for c in all_cycles if c.iteration == iteration), None)
        if cycle is None:
            return
        lines = [
            f"<b>Iteration {cycle.iteration} — {cycle.status.capitalize()}</b>",
            f"<b>Hypothesis:</b> {cycle.design_hypothesis or '(none)'}",
            f"<b>Material:</b> {cycle.material_composition or '(not specified)'}",
            f"<b>Fabrication:</b> {cycle.fabrication_method or '(not specified)'}",
            f"<b>Design decisions:</b> {'; '.join(cycle.design_decisions) or '(none)'}",
            f"<b>Test plan:</b> {'; '.join(cycle.test_plan) or '(none)'}",
        ]
        if cycle.results:
            results_str = ", ".join(f"{k}={v}" for k, v in cycle.results.items())
            lines.append(f"<b>Results:</b> {results_str}")
        if cycle.learning:
            lines.append(f"<b>Learning:</b> {cycle.learning}")
        if cycle.go_nogo_decision:
            lines.append(f"<b>Go/No-Go:</b> {cycle.go_nogo_decision.upper()}")
        if cycle.next_iteration_notes:
            lines.append(f"<b>Next cycle notes:</b> {cycle.next_iteration_notes}")
        self._dbtl_detail.setHtml("<br>".join(lines))

    def _add_dbtl_cycle(self):
        if not self._dbtl:
            return
        dlg = _DBTLAddDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            all_cycles = self._dbtl.get_all_cycles()
            iteration = (max(c.iteration for c in all_cycles) + 1) if all_cycles else 1
            self._dbtl.add_cycle(
                iteration=iteration,
                design_hypothesis=data["hypothesis"],
                material_composition=data["material"],
                fabrication_method=data["fabrication"],
                design_decisions=[d.strip() for d in data["decisions"].split(";") if d.strip()],
                test_plan=[t.strip() for t in data["test_plan"].split(";") if t.strip()],
            )
            self._refresh_dbtl()

    def _advance_phase(self):
        if not self._dbtl:
            return
        sel = self._dbtl_table.selectedItems()
        if not sel:
            return
        iteration = int(self._dbtl_table.item(sel[0].row(), 0).text())
        all_cycles = self._dbtl.get_all_cycles()
        cycle = next((c for c in all_cycles if c.iteration == iteration), None)
        if cycle is None:
            return
        phases = ["design", "build", "test", "learn", "complete"]
        try:
            idx = phases.index(cycle.status)
            next_phase = phases[min(idx + 1, len(phases) - 1)]
        except ValueError:
            return
        self._dbtl.advance_phase(cycle.cycle_id, next_phase)
        self._refresh_dbtl()

    def _record_results(self):
        if not self._dbtl:
            return
        sel = self._dbtl_table.selectedItems()
        if not sel:
            return
        iteration = int(self._dbtl_table.item(sel[0].row(), 0).text())
        all_cycles = self._dbtl.get_all_cycles()
        cycle = next((c for c in all_cycles if c.iteration == iteration), None)
        if cycle is None:
            return
        dlg = _ResultsDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            results = dlg.get_results()
            self._dbtl.record_results(cycle.cycle_id, results)
            self._refresh_dbtl()

    def _record_learning(self):
        if not self._dbtl:
            return
        sel = self._dbtl_table.selectedItems()
        if not sel:
            return
        iteration = int(self._dbtl_table.item(sel[0].row(), 0).text())
        all_cycles = self._dbtl.get_all_cycles()
        cycle = next((c for c in all_cycles if c.iteration == iteration), None)
        if cycle is None:
            return
        dlg = _LearningDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            self._dbtl.record_learning(
                cycle.cycle_id,
                learning=data["learning"],
                go_nogo=data["go_nogo"],
                next_notes=data["next_notes"],
            )
            self._refresh_dbtl()

    # ── Sub-tab 5: AI Advisor ──────────────────────────────────────────────────

    def _build_ai_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        desc = QLabel(
            "Claude reviews the current roadmap and DBTL history to provide concise scientific advice, "
            "3Rs opportunities, and regulatory risk flags."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#495057; font-size:11px; padding:8px;")
        layout.addWidget(desc)

        btn_bar = QHBoxLayout()
        self._ai_btn = QPushButton(qta.icon('fa5s.lightbulb'), "  Get AI Advice")
        self._ai_btn.setStyleSheet(self._primary_btn_style())
        self._ai_btn.clicked.connect(self._run_ai_advisor)
        btn_bar.addWidget(self._ai_btn)
        btn_bar.addStretch()
        layout.addLayout(btn_bar)

        self._ai_output = QTextEdit()
        self._ai_output.setReadOnly(True)
        self._ai_output.setPlaceholderText("AI advice will appear here. Generate a roadmap first.")
        layout.addWidget(self._ai_output)
        return w

    def _run_ai_advisor(self):
        context_parts = []

        if self._roadmap:
            r = self._roadmap
            context_parts.append(f"Target tissue: {r.tissue}")
            context_parts.append(f"Regulatory scenario: {r.scenario}")
            context_parts.append(f"Estimated duration: {r.total_duration}")
            context_parts.append(f"Critical path: {r.critical_path}")
            for s in r.stages:
                context_parts.append(
                    f"\nStage {s.stage_number}: {s.name} ({s.duration_weeks} weeks)"
                )
                context_parts.append(f"  Objective: {s.objective}")
                if s.cell_models:
                    context_parts.append(f"  Cell models: {', '.join(m.name for m in s.cell_models)}")
                if s.organism_models:
                    context_parts.append(f"  In vivo models: {', '.join(m.name for m in s.organism_models)}")
                if s.milestone:
                    context_parts.append(f"  Milestone: {s.milestone}")
        else:
            context_parts.append("No roadmap generated yet — provide general advice for a bone tissue engineering scaffold (Scenario A).")

        if self._dbtl:
            cycles = self._dbtl.get_all_cycles()
            if cycles:
                context_parts.append(f"\nDBTL cycles completed: {len(cycles)}")
                latest = cycles[-1]
                context_parts.append(f"Latest iteration: {latest.iteration} ({latest.status})")
                if latest.learning:
                    context_parts.append(f"Latest learning: {latest.learning}")

        self._ai_btn.setEnabled(False)
        self._ai_btn.setText("  Analysing...")
        self._ai_output.setPlainText("Waiting for AI response...")

        worker = AIAdvisorWorker("\n".join(context_parts))
        worker.finished.connect(self._on_ai_done)
        worker.error.connect(self._on_ai_error)
        worker.finished.connect(lambda: setattr(self, '_ai_worker', None))
        self._ai_worker = worker
        worker.start()

    def _on_ai_done(self, text: str):
        self._ai_btn.setEnabled(True)
        self._ai_btn.setText("  Get AI Advice")
        self._ai_output.setPlainText(text)

    def _on_ai_error(self, msg: str):
        self._ai_btn.setEnabled(True)
        self._ai_btn.setText("  Get AI Advice")
        self._ai_output.setPlainText(f"Error: {msg}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        lbl.setStyleSheet("color:#495057; margin-top:8px;")
        return lbl

    @staticmethod
    def _primary_btn_style() -> str:
        return """
            QPushButton {
                background-color: #2E86AB; color: white;
                border: none; border-radius: 4px; padding: 6px 14px; font-weight: bold;
            }
            QPushButton:hover { background-color: #1d6e8f; }
            QPushButton:disabled { background-color: #adb5bd; }
        """


# ── Helper dialogs ─────────────────────────────────────────────────────────────

class _DBTLAddDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add DBTL Cycle")
        self.setMinimumWidth(480)
        layout = QFormLayout(self)
        self._hyp  = QLineEdit(); layout.addRow("Hypothesis:", self._hyp)
        self._mat  = QLineEdit(); layout.addRow("Material composition:", self._mat)
        self._fab  = QLineEdit(); layout.addRow("Fabrication method:", self._fab)
        self._dec  = QLineEdit(); self._dec.setPlaceholderText("semicolon-separated")
        layout.addRow("Design decisions:", self._dec)
        self._test = QLineEdit(); self._test.setPlaceholderText("semicolon-separated")
        layout.addRow("Test plan:", self._test)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def get_data(self) -> dict:
        return {
            "hypothesis": self._hyp.text(),
            "material": self._mat.text(),
            "fabrication": self._fab.text(),
            "decisions": self._dec.text(),
            "test_plan": self._test.text(),
        }


class _ResultsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Record Results")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Enter results as key=value pairs, one per line:"))
        self._text = QPlainTextEdit()
        self._text.setPlaceholderText("viability=95.2\nALP_d14=1.8\n...")
        layout.addWidget(self._text)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_results(self) -> dict:
        results = {}
        for line in self._text.toPlainText().splitlines():
            if "=" in line:
                k, _, v = line.partition("=")
                try:
                    results[k.strip()] = float(v.strip())
                except ValueError:
                    results[k.strip()] = v.strip()
        return results


class _LearningDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Record Learning")
        self.setMinimumWidth(480)
        layout = QFormLayout(self)

        self._learning = QPlainTextEdit()
        self._learning.setMaximumHeight(80)
        layout.addRow("Learning summary:", self._learning)

        self._go_nogo = QComboBox()
        self._go_nogo.addItems(["pending", "go", "no-go", "pivot"])
        layout.addRow("Go/No-Go decision:", self._go_nogo)

        self._next = QLineEdit()
        layout.addRow("Next iteration notes:", self._next)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def get_data(self) -> dict:
        return {
            "learning": self._learning.toPlainText(),
            "go_nogo": self._go_nogo.currentText(),
            "next_notes": self._next.text(),
        }
