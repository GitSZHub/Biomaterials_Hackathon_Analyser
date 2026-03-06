"""Synthetic Biology Tab — iGEM/SynBioHub/Addgene parts browser, DBTL wizard,
genetic editor, living materials, and bioproduction planner.
"""
import sys
import webbrowser
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel, QPushButton,
    QLineEdit, QTextEdit, QTableWidget, QTableWidgetItem, QComboBox,
    QSplitter, QGroupBox, QFormLayout, QCheckBox, QSpinBox,
    QHeaderView, QFrame, QScrollArea, QMessageBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor
import qtawesome as qta

# ── Lazy engine imports ───────────────────────────────────────────────────────
def _igem():
    from src.synthetic_biology_engine.igem_client import IGEMClient
    return IGEMClient()

def _synbiohub():
    from src.synthetic_biology_engine.synbiohub_client import SynBioHubClient
    return SynBioHubClient()

def _addgene():
    from src.synthetic_biology_engine.addgene_client import AddgeneClient
    return AddgeneClient()

def _dbtl():
    from src.synthetic_biology_engine.dbtl_wizard import DBTLWizard, DBTLDesign
    return DBTLWizard(), DBTLDesign

def _genetic_editor():
    from src.synthetic_biology_engine.genetic_editor import GeneticEditorAdvisor
    return GeneticEditorAdvisor()

def _delivery_advisor():
    from src.synthetic_biology_engine.delivery_advisor import DeliveryAdvisor
    return DeliveryAdvisor()

def _living_materials():
    from src.synthetic_biology_engine.living_materials import LivingMaterialsEngine, LivingMaterialDesign
    return LivingMaterialsEngine(), LivingMaterialDesign

def _bioproduction():
    from src.synthetic_biology_engine.bioproduction_planner import BioproductionPlanner
    return BioproductionPlanner()


# ── QThread workers ───────────────────────────────────────────────────────────
class _PartsSearchWorker(QThread):
    results_ready = pyqtSignal(list)
    error         = pyqtSignal(str)

    def __init__(self, query: str, sources: list[str]):
        super().__init__()
        self.query   = query
        self.sources = sources

    def run(self):
        try:
            all_results = []
            if "iGEM" in self.sources:
                all_results += _igem().search_parts(self.query, limit=15)
            if "SynBioHub" in self.sources:
                all_results += _synbiohub().search_designs(self.query, limit=10)
            if "Addgene" in self.sources:
                all_results += _addgene().search_plasmids(self.query, limit=10)
            self.results_ready.emit(all_results)
        except Exception as exc:
            self.error.emit(str(exc))


class _DBTLDocWorker(QThread):
    doc_ready = pyqtSignal(str)
    error     = pyqtSignal(str)

    def __init__(self, design_kwargs: dict):
        super().__init__()
        self.kwargs = design_kwargs

    def run(self):
        try:
            wizard, DBTLDesign = _dbtl()
            design = DBTLDesign(**self.kwargs)
            design.build_protocol = wizard.generate_build_protocol(design)
            design.test_plan      = wizard.generate_test_plan(design)
            design.regulatory_note = (
                "SCENARIO C TRIGGERED — see Regulatory tab."
                if wizard.check_scenario_c(design) else ""
            )
            doc = wizard.generate_design_document(design)
            self.doc_ready.emit(doc)
        except Exception as exc:
            self.error.emit(str(exc))


class _EditorAdvisorWorker(QThread):
    results_ready = pyqtSignal(list, list)  # editing_recs, delivery_recs
    error         = pyqtSignal(str)

    def __init__(self, goal: str, cell_type: str, target_gene: str):
        super().__init__()
        self.goal = goal
        self.cell_type = cell_type
        self.target_gene = target_gene

    def run(self):
        try:
            editing_recs  = _genetic_editor().recommend(self.goal, self.cell_type, self.target_gene)
            delivery_recs = _delivery_advisor().recommend(self.cell_type, self.goal)
            self.results_ready.emit(editing_recs, delivery_recs)
        except Exception as exc:
            self.error.emit(str(exc))


class _LivingMaterialsWorker(QThread):
    plan_ready = pyqtSignal(str, bool)   # plan_text, scenario_c
    error      = pyqtSignal(str)

    def __init__(self, design_kwargs: dict):
        super().__init__()
        self.kwargs = design_kwargs

    def run(self):
        try:
            engine, LMDesign = _living_materials()
            design = LMDesign(**self.kwargs)
            scenario_c = engine.check_scenario_c(design)
            design.scenario_c = scenario_c
            plan = engine.generate_integration_plan(design)
            self.plan_ready.emit(plan, scenario_c)
        except Exception as exc:
            self.error.emit(str(exc))


class _BioproductionWorker(QThread):
    plan_ready = pyqtSignal(str)
    error      = pyqtSignal(str)

    def __init__(self, molecule: str, chassis: str, scale: str, notes: str):
        super().__init__()
        self.molecule = molecule
        self.chassis  = chassis
        self.scale    = scale
        self.notes    = notes

    def run(self):
        try:
            planner = _bioproduction()
            plan = planner.generate_plan(self.molecule, self.chassis, self.scale, self.notes)
            self.plan_ready.emit(plan)
        except Exception as exc:
            self.error.emit(str(exc))


# ── Helper widgets ────────────────────────────────────────────────────────────
def _card_label(text: str, bold: bool = False) -> QLabel:
    lbl = QLabel(text)
    if bold:
        lbl.setFont(QFont("Arial", 9, QFont.Weight.Bold))
    lbl.setWordWrap(True)
    return lbl

def _section_header(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setFont(QFont("Arial", 10, QFont.Weight.Bold))
    lbl.setStyleSheet("color: #2E86AB; padding: 4px 0px;")
    return lbl

def _make_table(columns: list[str]) -> QTableWidget:
    t = QTableWidget(0, len(columns))
    t.setHorizontalHeaderLabels(columns)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    t.setAlternatingRowColors(True)
    t.verticalHeader().setVisible(False)
    return t

def _output_box() -> QTextEdit:
    box = QTextEdit()
    box.setReadOnly(True)
    box.setFont(QFont("Consolas", 9))
    box.setStyleSheet("background: #f8f9fa; border: 1px solid #dee2e6;")
    return box

def _busy_btn(btn: QPushButton, busy: bool):
    btn.setEnabled(not busy)
    if busy:
        btn.setText("  Working...")

SCENARIO_C_STYLE = "background:#fff3cd; border:2px solid #ffc107; border-radius:4px; padding:6px;"
SCENARIO_C_OK_STYLE = "background:#d4edda; border:2px solid #28a745; border-radius:4px; padding:6px;"


# ─────────────────────────────────────────────────────────────────────────────
# 1. PARTS BROWSER TAB
# ─────────────────────────────────────────────────────────────────────────────
class _PartsBrowserTab(QWidget):
    def __init__(self):
        super().__init__()
        self._worker: Optional[_PartsSearchWorker] = None
        self._results: list[dict] = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        root.addWidget(_section_header("Biological Parts Browser"))
        root.addWidget(QLabel(
            "Search iGEM Registry, SynBioHub, and Addgene for parts relevant to biomaterials."))

        # Search row
        search_row = QHBoxLayout()
        self._query_edit = QLineEdit()
        self._query_edit.setPlaceholderText(
            "e.g. collagen, spider silk, VEGF, inflammation, PHB, BMP-2...")
        self._query_edit.returnPressed.connect(self._run_search)
        search_row.addWidget(QLabel("Search:"))
        search_row.addWidget(self._query_edit)

        self._igem_chk    = QCheckBox("iGEM Registry");   self._igem_chk.setChecked(True)
        self._synbio_chk  = QCheckBox("SynBioHub");       self._synbio_chk.setChecked(True)
        self._addgene_chk = QCheckBox("Addgene");         self._addgene_chk.setChecked(True)
        search_row.addWidget(self._igem_chk)
        search_row.addWidget(self._synbio_chk)
        search_row.addWidget(self._addgene_chk)

        self._search_btn = QPushButton(qta.icon('fa5s.search'), "  Search")
        self._search_btn.clicked.connect(self._run_search)
        search_row.addWidget(self._search_btn)
        root.addLayout(search_row)

        # Splitter — results table left, detail right
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self._status_lbl = QLabel("Enter a search term above.")
        ll.addWidget(self._status_lbl)
        self._results_table = _make_table(["Name", "Type", "Description", "Source"])
        self._results_table.selectionModel().selectionChanged.connect(self._on_select)
        ll.addWidget(self._results_table)
        splitter.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(_section_header("Part Detail"))
        self._detail_box = _output_box()
        rl.addWidget(self._detail_box)

        btn_row = QHBoxLayout()
        self._open_url_btn = QPushButton(qta.icon('fa5s.external-link-alt'), "  Open in Browser")
        self._open_url_btn.clicked.connect(self._open_url)
        self._open_url_btn.setEnabled(False)
        self._add_briefing_btn = QPushButton(qta.icon('fa5s.star'), "  Add to Briefing")
        self._add_briefing_btn.clicked.connect(self._add_to_briefing)
        self._add_briefing_btn.setEnabled(False)
        btn_row.addWidget(self._open_url_btn)
        btn_row.addWidget(self._add_briefing_btn)
        btn_row.addStretch()
        rl.addLayout(btn_row)
        splitter.addWidget(right)

        splitter.setSizes([550, 400])
        root.addWidget(splitter)

    def _sources(self) -> list[str]:
        src = []
        if self._igem_chk.isChecked():    src.append("iGEM")
        if self._synbio_chk.isChecked():  src.append("SynBioHub")
        if self._addgene_chk.isChecked(): src.append("Addgene")
        return src

    def _run_search(self):
        query = self._query_edit.text().strip()
        if not query:
            return
        sources = self._sources()
        if not sources:
            self._status_lbl.setText("Select at least one source.")
            return
        _busy_btn(self._search_btn, True)
        self._status_lbl.setText("Searching...")
        self._worker = _PartsSearchWorker(query, sources)
        self._worker.results_ready.connect(self._on_results)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_results(self, results: list[dict]):
        self._results = results
        self._results_table.setRowCount(0)
        for r in results:
            row = self._results_table.rowCount()
            self._results_table.insertRow(row)
            self._results_table.setItem(row, 0, QTableWidgetItem(r.get("name", "")))
            self._results_table.setItem(row, 1, QTableWidgetItem(r.get("type", "")))
            desc = r.get("description", "")
            self._results_table.setItem(row, 2, QTableWidgetItem(desc[:80] + ("..." if len(desc) > 80 else "")))
            self._results_table.setItem(row, 3, QTableWidgetItem(r.get("source", "")))
        self._status_lbl.setText(f"{len(results)} results")
        _busy_btn(self._search_btn, False)
        self._search_btn.setText("  Search")

    def _on_error(self, err: str):
        self._status_lbl.setText(f"Error: {err}")
        _busy_btn(self._search_btn, False)
        self._search_btn.setText("  Search")

    def _on_select(self):
        rows = self._results_table.selectionModel().selectedRows()
        if not rows:
            return
        idx = rows[0].row()
        if idx >= len(self._results):
            return
        part = self._results[idx]
        lines = [
            f"Name:         {part.get('name', '')}",
            f"Type:         {part.get('type', '')}",
            f"Source:       {part.get('source', '')}",
            f"Status:       {part.get('status', part.get('vector_type', 'N/A'))}",
            f"Author:       {part.get('author', part.get('depositor', part.get('collection', 'N/A')))}",
            "",
            "Description:",
            f"  {part.get('description', '')}",
            "",
            f"URL:  {part.get('url', '')}",
        ]
        if part.get("purpose"):
            lines.insert(4, f"Purpose:      {part['purpose']}")
        self._detail_box.setPlainText("\n".join(lines))
        self._open_url_btn.setEnabled(bool(part.get("url")))
        self._add_briefing_btn.setEnabled(True)

    def _open_url(self):
        rows = self._results_table.selectionModel().selectedRows()
        if not rows:
            return
        idx = rows[0].row()
        url = self._results[idx].get("url", "")
        if url:
            webbrowser.open(url)

    def _add_to_briefing(self):
        rows = self._results_table.selectionModel().selectedRows()
        if not rows:
            return
        idx = rows[0].row()
        part = self._results[idx]
        QMessageBox.information(self, "Added",
            f"'{part.get('name')}' added to briefing context.\n\n"
            "It will appear under Synthetic Biology in the next briefing generation.")


# ─────────────────────────────────────────────────────────────────────────────
# 2. DBTL WIZARD TAB
# ─────────────────────────────────────────────────────────────────────────────
class _DBTLWizardTab(QWidget):
    def __init__(self):
        super().__init__()
        self._worker: Optional[_DBTLDocWorker] = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.addWidget(_section_header("DBTL Circuit Design Wizard"))
        root.addWidget(QLabel(
            "Design a genetic circuit in 7 steps: Sense → Output → Chassis → Flag → Protocol → Test → Link."))

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Left: inputs ──────────────────────────────────────────────
        left = QScrollArea()
        left.setWidgetResizable(True)
        left_inner = QWidget()
        ll = QVBoxLayout(left_inner)

        # Step 1: Goal
        ll.addWidget(_section_header("Step 1 — Circuit Goal"))
        self._goal_edit = QTextEdit()
        self._goal_edit.setPlaceholderText(
            "Describe the desired function, e.g.:\n"
            "  'Cells that sense local inflammation and release IL-10'\n"
            "  'E. coli producing spider silk protein for scaffold coating'")
        self._goal_edit.setMaximumHeight(80)
        ll.addWidget(self._goal_edit)

        # Step 2: Sensing component
        ll.addWidget(_section_header("Step 2 — Sensing Component (Promoter)"))
        sensing_row = QHBoxLayout()
        self._sensing_edit = QLineEdit()
        self._sensing_edit.setPlaceholderText("Promoter name or BioBrick ID, e.g. NF-kB, BBa_J23100")
        self._sensing_source_edit = QLineEdit()
        self._sensing_source_edit.setPlaceholderText("Source: iGEM / SynBioHub / custom")
        sensing_row.addWidget(QLabel("Part:"))
        sensing_row.addWidget(self._sensing_edit)
        sensing_row.addWidget(QLabel("Source:"))
        sensing_row.addWidget(self._sensing_source_edit)
        ll.addLayout(sensing_row)

        suggest_sensing_btn = QPushButton(qta.icon('fa5s.lightbulb'), " Suggest sensing parts")
        suggest_sensing_btn.clicked.connect(self._suggest_sensing)
        ll.addWidget(suggest_sensing_btn)
        self._sensing_suggestions = QLabel("")
        self._sensing_suggestions.setWordWrap(True)
        self._sensing_suggestions.setStyleSheet("color: #555; font-size: 8pt; padding: 2px 0;")
        ll.addWidget(self._sensing_suggestions)

        # Step 3: Output component
        ll.addWidget(_section_header("Step 3 — Output Component (CDS)"))
        output_row = QHBoxLayout()
        self._output_edit = QLineEdit()
        self._output_edit.setPlaceholderText("Coding sequence, e.g. IL-10, VEGF, BBa_K2924000")
        self._output_source_edit = QLineEdit()
        self._output_source_edit.setPlaceholderText("Source: iGEM / SynBioHub / custom")
        output_row.addWidget(QLabel("Part:"))
        output_row.addWidget(self._output_edit)
        output_row.addWidget(QLabel("Source:"))
        output_row.addWidget(self._output_source_edit)
        ll.addLayout(output_row)

        suggest_output_btn = QPushButton(qta.icon('fa5s.lightbulb'), " Suggest output parts")
        suggest_output_btn.clicked.connect(self._suggest_output)
        ll.addWidget(suggest_output_btn)
        self._output_suggestions = QLabel("")
        self._output_suggestions.setWordWrap(True)
        self._output_suggestions.setStyleSheet("color: #555; font-size: 8pt; padding: 2px 0;")
        ll.addWidget(self._output_suggestions)

        # Step 4: Chassis
        ll.addWidget(_section_header("Step 4 — Chassis Organism"))
        chassis_row = QHBoxLayout()
        self._chassis_combo = QComboBox()
        wizard, _ = _dbtl()
        for c in wizard.get_chassis_list():
            self._chassis_combo.addItem(c)
        chassis_row.addWidget(QLabel("Chassis:"))
        chassis_row.addWidget(self._chassis_combo)
        self._chassis_info_btn = QPushButton(qta.icon('fa5s.info-circle'), " Info")
        self._chassis_info_btn.clicked.connect(self._show_chassis_info)
        chassis_row.addWidget(self._chassis_info_btn)
        chassis_row.addStretch()
        ll.addLayout(chassis_row)

        self._chassis_info_lbl = QLabel("")
        self._chassis_info_lbl.setWordWrap(True)
        self._chassis_info_lbl.setStyleSheet("color:#555; font-size:8pt; padding:2px 0;")
        ll.addWidget(self._chassis_info_lbl)

        # Step 5-6: DBTL stage + iteration
        ll.addWidget(_section_header("Step 5 — DBTL Stage & Iteration"))
        stage_row = QHBoxLayout()
        self._stage_combo = QComboBox()
        for s in ["Design", "Build", "Test", "Learn"]:
            self._stage_combo.addItem(s)
        self._iter_spin = QSpinBox()
        self._iter_spin.setMinimum(1)
        self._iter_spin.setMaximum(20)
        stage_row.addWidget(QLabel("Stage:"))
        stage_row.addWidget(self._stage_combo)
        stage_row.addWidget(QLabel("Iteration:"))
        stage_row.addWidget(self._iter_spin)
        stage_row.addStretch()
        ll.addLayout(stage_row)

        ll.addWidget(_section_header("Notes"))
        self._notes_edit = QTextEdit()
        self._notes_edit.setPlaceholderText("Any specific constraints, prior iteration results, or observations...")
        self._notes_edit.setMaximumHeight(60)
        ll.addWidget(self._notes_edit)

        self._generate_btn = QPushButton(qta.icon('fa5s.magic'), "  Generate Design Document")
        self._generate_btn.setStyleSheet(
            "background:#2E86AB; color:white; font-weight:bold; padding:8px; border-radius:4px;")
        self._generate_btn.clicked.connect(self._generate)
        ll.addWidget(self._generate_btn)

        self._scenario_c_banner = QLabel("")
        ll.addWidget(self._scenario_c_banner)
        ll.addStretch()
        left.setWidget(left_inner)
        splitter.addWidget(left)

        # ── Right: output doc ──────────────────────────────────────────
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(_section_header("Generated Design Document"))
        self._doc_box = _output_box()
        rl.addWidget(self._doc_box)
        btn_row = QHBoxLayout()
        copy_btn = QPushButton(qta.icon('fa5s.copy'), "  Copy")
        copy_btn.clicked.connect(lambda: _copy_text(self._doc_box))
        btn_row.addWidget(copy_btn)
        btn_row.addStretch()
        rl.addLayout(btn_row)
        splitter.addWidget(right)

        splitter.setSizes([480, 520])
        root.addWidget(splitter)

    def _suggest_sensing(self):
        goal = self._goal_edit.toPlainText()
        wizard, _ = _dbtl()
        # Pick keyword from goal
        kw = "constitutive"
        for k in ["inflammation", "hypoxia", "mechanical", "constitutive"]:
            if k in goal.lower():
                kw = k
                break
        parts = wizard.suggest_sensing_parts(kw)
        if parts:
            text = "Suggestions: " + " | ".join(
                f"{p['name']} ({p['description'][:40]}...)" for p in parts[:3])
            self._sensing_suggestions.setText(text)
            self._sensing_edit.setText(parts[0]["name"])
            self._sensing_source_edit.setText(parts[0]["source"])

    def _suggest_output(self):
        goal = self._goal_edit.toPlainText()
        wizard, _ = _dbtl()
        kw = "reporter"
        for k in ["anti-inflammatory", "vascularisation", "osteogenic",
                  "chondrogenic", "biomaterial", "reporter"]:
            if k.replace("-", " ") in goal.lower() or k in goal.lower():
                kw = k
                break
        parts = wizard.suggest_output_parts(kw)
        if parts:
            text = "Suggestions: " + " | ".join(
                f"{p['name']} ({p['description'][:40]}...)" for p in parts[:3])
            self._output_suggestions.setText(text)
            self._output_edit.setText(parts[0]["name"])
            self._output_source_edit.setText(parts[0]["source"])

    def _show_chassis_info(self):
        chassis = self._chassis_combo.currentText()
        wizard, _ = _dbtl()
        info = wizard.get_chassis_info(chassis)
        if info:
            self._chassis_info_lbl.setText(
                f"{info.get('full_name','')} | {info.get('strengths','')} | "
                f"Doubling time: {info.get('doubling_time','')}")

    def _generate(self):
        goal = self._goal_edit.toPlainText().strip()
        if not goal:
            QMessageBox.warning(self, "Missing input", "Enter a circuit goal first.")
            return
        _busy_btn(self._generate_btn, True)
        kwargs = {
            "goal":           goal,
            "sensing_part":   self._sensing_edit.text().strip(),
            "sensing_source": self._sensing_source_edit.text().strip(),
            "output_part":    self._output_edit.text().strip(),
            "output_source":  self._output_source_edit.text().strip(),
            "chassis":        self._chassis_combo.currentText(),
            "dbtl_stage":     self._stage_combo.currentText(),
            "iteration":      self._iter_spin.value(),
            "notes":          self._notes_edit.toPlainText().strip(),
        }
        self._worker = _DBTLDocWorker(kwargs)
        self._worker.doc_ready.connect(self._on_doc)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_doc(self, doc: str):
        self._doc_box.setPlainText(doc)
        _busy_btn(self._generate_btn, False)
        self._generate_btn.setText("  Generate Design Document")
        # Scenario C banner
        if "SCENARIO C" in doc or "ATMP" in doc:
            self._scenario_c_banner.setText(
                "REGULATORY FLAG: Scenario C (ATMP) triggered. Consult the Regulatory tab.")
            self._scenario_c_banner.setStyleSheet(SCENARIO_C_STYLE)
        else:
            self._scenario_c_banner.setText("")

    def _on_error(self, err: str):
        self._doc_box.setPlainText(f"Error: {err}")
        _busy_btn(self._generate_btn, False)
        self._generate_btn.setText("  Generate Design Document")


# ─────────────────────────────────────────────────────────────────────────────
# 3. GENETIC EDITOR TAB
# ─────────────────────────────────────────────────────────────────────────────
class _GeneticEditorTab(QWidget):
    def __init__(self):
        super().__init__()
        self._worker: Optional[_EditorAdvisorWorker] = None
        self._editing_recs: list[dict] = []
        self._delivery_recs: list[dict] = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.addWidget(_section_header("Genetic Editing Strategy Advisor"))
        root.addWidget(QLabel(
            "Select your editing goal and cell type — get technology recommendation,"
            " delivery method, and direct links to design tools."))

        form = QGroupBox("Inputs")
        fl = QFormLayout(form)

        self._gene_edit = QLineEdit()
        self._gene_edit.setPlaceholderText("e.g. COL1A1, VEGFA, TP53, IL10R ...")
        fl.addRow("Target gene:", self._gene_edit)

        self._goal_combo = QComboBox()
        for g in ["knockout", "knock-in", "activate", "repress",
                  "point mutation", "base edit", "small insertion", "reporter", "conditional", "yeast"]:
            self._goal_combo.addItem(g)
        fl.addRow("Editing goal:", self._goal_combo)

        self._cell_combo = QComboBox()
        for ct in ["iPSC / Primary cells", "T cells", "HSCs", "primary neurons",
                   "hepatocytes", "muscle cells", "RPE cells", "CHO cells",
                   "HEK293", "E. coli", "S. cerevisiae", "Pichia pastoris"]:
            self._cell_combo.addItem(ct)
        fl.addRow("Cell type:", self._cell_combo)

        self._advise_btn = QPushButton(qta.icon('fa5s.magic'), "  Get Recommendations")
        self._advise_btn.setStyleSheet(
            "background:#2E86AB; color:white; font-weight:bold; padding:6px; border-radius:4px;")
        self._advise_btn.clicked.connect(self._run)
        fl.addRow(self._advise_btn)
        root.addWidget(form)

        # Results splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Editing tech table
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(_section_header("Editing Technology"))
        self._editing_table = _make_table(["Method", "Best for", "Off-target"])
        self._editing_table.selectionModel().selectionChanged.connect(self._on_editing_select)
        ll.addWidget(self._editing_table)
        splitter.addWidget(left)

        # Delivery table
        mid = QWidget()
        ml = QVBoxLayout(mid)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.addWidget(_section_header("Delivery Method"))
        self._delivery_table = _make_table(["Method", "Integration risk", "Clinical status"])
        self._delivery_table.selectionModel().selectionChanged.connect(self._on_delivery_select)
        ml.addWidget(self._delivery_table)
        splitter.addWidget(mid)

        # Detail panel
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(_section_header("Detail & Links"))
        self._detail_box = _output_box()
        rl.addWidget(self._detail_box)

        links_row = QHBoxLayout()
        self._crispor_btn = QPushButton(qta.icon('fa5s.external-link-alt'), "  CRISPOR")
        self._crispor_btn.clicked.connect(lambda: webbrowser.open("https://crispor.tefor.net"))
        self._addgene_btn = QPushButton(qta.icon('fa5s.external-link-alt'), "  Addgene plasmids")
        self._addgene_btn.clicked.connect(self._open_addgene)
        self._ensembl_btn = QPushButton(qta.icon('fa5s.external-link-alt'), "  Ensembl gene")
        self._ensembl_btn.clicked.connect(self._open_ensembl)
        links_row.addWidget(self._crispor_btn)
        links_row.addWidget(self._addgene_btn)
        links_row.addWidget(self._ensembl_btn)
        links_row.addStretch()
        rl.addLayout(links_row)
        splitter.addWidget(right)

        splitter.setSizes([280, 280, 360])
        root.addWidget(splitter)

    def _run(self):
        _busy_btn(self._advise_btn, True)
        self._worker = _EditorAdvisorWorker(
            self._goal_combo.currentText(),
            self._cell_combo.currentText(),
            self._gene_edit.text().strip(),
        )
        self._worker.results_ready.connect(self._on_results)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_results(self, editing_recs: list[dict], delivery_recs: list[dict]):
        self._editing_recs  = editing_recs
        self._delivery_recs = delivery_recs

        self._editing_table.setRowCount(0)
        for r in editing_recs:
            row = self._editing_table.rowCount()
            self._editing_table.insertRow(row)
            self._editing_table.setItem(row, 0, QTableWidgetItem(r.get("method", "")))
            best = ", ".join(r.get("best_for", [])[:2])
            self._editing_table.setItem(row, 1, QTableWidgetItem(best))
            self._editing_table.setItem(row, 2, QTableWidgetItem(r.get("off_target", "")))

        self._delivery_table.setRowCount(0)
        for r in delivery_recs:
            row = self._delivery_table.rowCount()
            self._delivery_table.insertRow(row)
            self._delivery_table.setItem(row, 0, QTableWidgetItem(r.get("method", r.get("full_name", ""))))
            self._delivery_table.setItem(row, 1, QTableWidgetItem(r.get("integration_risk", "")))
            self._delivery_table.setItem(row, 2, QTableWidgetItem(r.get("clinical_status", "")[:40]))

        if editing_recs:
            self._editing_table.selectRow(0)

        _busy_btn(self._advise_btn, False)
        self._advise_btn.setText("  Get Recommendations")

    def _on_editing_select(self):
        rows = self._editing_table.selectionModel().selectedRows()
        if not rows or rows[0].row() >= len(self._editing_recs):
            return
        r = self._editing_recs[rows[0].row()]
        tools = r.get("tools", {})
        tool_str = "\n".join(f"  {k}: {v}" for k, v in tools.items())
        lines = [
            f"Method:        {r.get('method', '')}",
            f"Mechanism:     {r.get('mechanism', '')}",
            "",
            f"Best for:      {', '.join(r.get('best_for', []))}",
            f"Limitations:   {r.get('limitations', '')}",
            f"Off-target:    {r.get('off_target', '')}",
            f"Cell breadth:  {r.get('cell_breadth', '')}",
            "",
            "Design tools:",
            tool_str,
        ]
        self._detail_box.setPlainText("\n".join(lines))

    def _on_delivery_select(self):
        rows = self._delivery_table.selectionModel().selectedRows()
        if not rows or rows[0].row() >= len(self._delivery_recs):
            return
        r = self._delivery_recs[rows[0].row()]
        lines = [
            f"Method:           {r.get('method', r.get('full_name', ''))}",
            f"Mechanism:        {r.get('mechanism', '')}",
            f"Payload limit:    {r.get('payload_limit', 'N/A')}",
            f"Integration risk: {r.get('integration_risk', '')}",
            f"Immunogenicity:   {r.get('immunogenicity', '')}",
            f"Clinical status:  {r.get('clinical_status', '')}",
            f"Regulatory path:  {r.get('regulatory_path', '')}",
        ]
        self._detail_box.setPlainText("\n".join(lines))

    def _on_error(self, err: str):
        self._detail_box.setPlainText(f"Error: {err}")
        _busy_btn(self._advise_btn, False)
        self._advise_btn.setText("  Get Recommendations")

    def _open_addgene(self):
        rows = self._editing_table.selectionModel().selectedRows()
        if rows and rows[0].row() < len(self._editing_recs):
            r = self._editing_recs[rows[0].row()]
            url = r.get("tools", {}).get("Plasmids", "")
            if url:
                webbrowser.open(url.split(" — ")[-1].strip())
                return
        webbrowser.open("https://www.addgene.org")

    def _open_ensembl(self):
        gene = self._gene_edit.text().strip()
        if gene:
            webbrowser.open(f"https://www.ensembl.org/Multi/Search/Results?q={gene}")
        else:
            webbrowser.open("https://www.ensembl.org")


# ─────────────────────────────────────────────────────────────────────────────
# 4. LIVING MATERIALS TAB
# ─────────────────────────────────────────────────────────────────────────────
class _LivingMaterialsTab(QWidget):
    scenario_c_changed = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self._worker: Optional[_LivingMaterialsWorker] = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.addWidget(_section_header("Living Materials — Circuit-Scaffold Integration"))
        root.addWidget(QLabel(
            "Connect a genetic circuit to a scaffold material. "
            "Scenario C (ATMP) is automatically flagged when GMO cells are intended for in vivo use."))

        # Scenario C banner (prominent)
        self._scenario_banner = QLabel("Scenario C status: not yet assessed")
        self._scenario_banner.setStyleSheet(SCENARIO_C_OK_STYLE)
        self._scenario_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._scenario_banner)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Left: inputs ──────────────────────────────────────────────
        left = QScrollArea()
        left.setWidgetResizable(True)
        li = QWidget()
        ll = QVBoxLayout(li)

        # Archetypes
        ll.addWidget(_section_header("Archetypes (pre-built integration designs)"))
        self._archetype_combo = QComboBox()
        engine, _ = _living_materials()
        for arch in engine.get_archetypes():
            self._archetype_combo.addItem(arch["name"])
        self._archetype_combo.currentIndexChanged.connect(self._load_archetype)
        load_arch_btn = QPushButton(qta.icon('fa5s.download'), " Load archetype")
        load_arch_btn.clicked.connect(self._load_archetype)
        arch_row = QHBoxLayout()
        arch_row.addWidget(self._archetype_combo)
        arch_row.addWidget(load_arch_btn)
        ll.addLayout(arch_row)

        # Custom inputs
        ll.addWidget(_section_header("Circuit Design"))
        self._goal_edit = QLineEdit()
        self._goal_edit.setPlaceholderText(
            "e.g. cells sensing inflammation + releasing IL-10 in GelMA scaffold in vivo")
        ll.addWidget(QLabel("Circuit goal:"))
        ll.addWidget(self._goal_edit)

        self._trigger_edit = QLineEdit()
        self._trigger_edit.setPlaceholderText("e.g. NF-kB promoter, HRE, constitutive")
        ll.addWidget(QLabel("Trigger / sensing:"))
        ll.addWidget(self._trigger_edit)

        self._output_edit = QLineEdit()
        self._output_edit.setPlaceholderText("e.g. IL-10, VEGF165, spider silk")
        ll.addWidget(QLabel("Output:"))
        ll.addWidget(self._output_edit)

        self._chassis_edit = QLineEdit()
        self._chassis_edit.setPlaceholderText("e.g. iPSC-derived MSCs, primary chondrocytes, E. coli")
        ll.addWidget(QLabel("Chassis / cell type:"))
        ll.addWidget(self._chassis_edit)

        ll.addWidget(_section_header("Scaffold Material"))
        self._scaffold_combo = QComboBox()
        for mat in engine.get_scaffold_list():
            self._scaffold_combo.addItem(mat)
        self._scaffold_combo.currentIndexChanged.connect(self._show_scaffold_info)
        ll.addWidget(self._scaffold_combo)
        self._scaffold_info_lbl = QLabel("")
        self._scaffold_info_lbl.setWordWrap(True)
        self._scaffold_info_lbl.setStyleSheet("color:#555; font-size:8pt;")
        ll.addWidget(self._scaffold_info_lbl)

        ll.addWidget(QLabel("Notes:"))
        self._notes_edit = QTextEdit()
        self._notes_edit.setMaximumHeight(60)
        ll.addWidget(self._notes_edit)

        self._generate_btn = QPushButton(qta.icon('fa5s.magic'), "  Generate Integration Plan")
        self._generate_btn.setStyleSheet(
            "background:#2E86AB; color:white; font-weight:bold; padding:8px; border-radius:4px;")
        self._generate_btn.clicked.connect(self._generate)
        ll.addWidget(self._generate_btn)
        ll.addStretch()
        left.setWidget(li)
        splitter.addWidget(left)

        # ── Right: output ──────────────────────────────────────────────
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(_section_header("Integration Plan"))
        self._plan_box = _output_box()
        rl.addWidget(self._plan_box)
        btn_row = QHBoxLayout()
        copy_btn = QPushButton(qta.icon('fa5s.copy'), "  Copy")
        copy_btn.clicked.connect(lambda: _copy_text(self._plan_box))
        reg_btn = QPushButton(qta.icon('fa5s.shield-alt'), "  Open Regulatory Tab")
        reg_btn.clicked.connect(self._open_regulatory)
        btn_row.addWidget(copy_btn)
        btn_row.addWidget(reg_btn)
        btn_row.addStretch()
        rl.addLayout(btn_row)
        splitter.addWidget(right)

        splitter.setSizes([450, 520])
        root.addWidget(splitter)

        # Init scaffold info
        self._show_scaffold_info()

    def _load_archetype(self):
        engine, _ = _living_materials()
        archetypes = engine.get_archetypes()
        idx = self._archetype_combo.currentIndex()
        if idx < 0 or idx >= len(archetypes):
            return
        arch = archetypes[idx]
        self._goal_edit.setText(arch["description"])
        self._trigger_edit.setText(arch["trigger"])
        self._output_edit.setText(arch["output"])
        self._chassis_edit.setText(arch["chassis"])
        # Set scaffold
        scaffolds = arch.get("scaffold", [])
        if scaffolds:
            idx_s = self._scaffold_combo.findText(scaffolds[0])
            if idx_s >= 0:
                self._scaffold_combo.setCurrentIndex(idx_s)
        # Show regulatory flag
        if arch.get("scenario_c"):
            self._scenario_banner.setText(
                f"REGULATORY FLAG: {arch.get('regulatory_flag', 'Scenario C')} — check Regulatory tab.")
            self._scenario_banner.setStyleSheet(SCENARIO_C_STYLE)
        else:
            self._scenario_banner.setText(f"Regulatory: {arch.get('regulatory_flag', 'Scenario A/D')}")
            self._scenario_banner.setStyleSheet(SCENARIO_C_OK_STYLE)

    def _show_scaffold_info(self):
        engine, _ = _living_materials()
        mat = self._scaffold_combo.currentText()
        info = engine.get_scaffold_detail(mat)
        if info:
            self._scaffold_info_lbl.setText(
                f"Stiffness: {info.get('stiffness_kPa','?')} kPa | "
                f"Crosslink: {info.get('crosslinking','?')} | "
                f"O2: {info.get('oxygen_permeability','?')}")

    def _generate(self):
        goal = self._goal_edit.text().strip()
        if not goal:
            QMessageBox.warning(self, "Missing input", "Enter a circuit goal.")
            return
        _busy_btn(self._generate_btn, True)
        kwargs = {
            "circuit_goal":      goal,
            "trigger":           self._trigger_edit.text().strip(),
            "output":            self._output_edit.text().strip(),
            "chassis":           self._chassis_edit.text().strip(),
            "scaffold_material": self._scaffold_combo.currentText(),
            "notes":             self._notes_edit.toPlainText().strip(),
        }
        self._worker = _LivingMaterialsWorker(kwargs)
        self._worker.plan_ready.connect(self._on_plan)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_plan(self, plan: str, scenario_c: bool):
        self._plan_box.setPlainText(plan)
        _busy_btn(self._generate_btn, False)
        self._generate_btn.setText("  Generate Integration Plan")
        if scenario_c:
            self._scenario_banner.setText(
                "REGULATORY FLAG: Scenario C (ATMP) — GMO cells in implantable device. "
                "Requires IND, Phase I trial, GMP, EMA CAT / FDA CBER.")
            self._scenario_banner.setStyleSheet(SCENARIO_C_STYLE)
            self.scenario_c_changed.emit(True)
        else:
            self._scenario_banner.setText("Regulatory: Scenario A or D — no live GMO cells in device.")
            self._scenario_banner.setStyleSheet(SCENARIO_C_OK_STYLE)
            self.scenario_c_changed.emit(False)

    def _on_error(self, err: str):
        self._plan_box.setPlainText(f"Error: {err}")
        _busy_btn(self._generate_btn, False)
        self._generate_btn.setText("  Generate Integration Plan")

    def _open_regulatory(self):
        # Parent tab widget navigation — find main window
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, 'tab_widget'):
                # Find regulatory tab by title
                tw = parent.tab_widget
                for i in range(tw.count()):
                    if "Regulatory" in tw.tabText(i):
                        tw.setCurrentIndex(i)
                        return
            parent = parent.parent() if hasattr(parent, 'parent') else None


# ─────────────────────────────────────────────────────────────────────────────
# 5. BIOPRODUCTION TAB
# ─────────────────────────────────────────────────────────────────────────────
class _BioproductionTab(QWidget):
    def __init__(self):
        super().__init__()
        self._worker: Optional[_BioproductionWorker] = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.addWidget(_section_header("Bioproduction Planner"))
        root.addWidget(QLabel(
            "Recommend production system, bioreactor, process mode, and scale "
            "for a synthetic biology manufacturing proposal."))

        form = QGroupBox("Production Inputs")
        fl = QFormLayout(form)

        self._molecule_edit = QLineEdit()
        self._molecule_edit.setPlaceholderText("e.g. spider silk protein, recombinant collagen, BMP-2, PHB")
        fl.addRow("Target molecule:", self._molecule_edit)

        self._chassis_combo = QComboBox()
        for c in ["E. coli", "S. cerevisiae", "Pichia pastoris", "CHO cells",
                  "Insect cells", "Cell-free", "(recommend for me)"]:
            self._chassis_combo.addItem(c)
        fl.addRow("Chassis:", self._chassis_combo)

        self._scale_combo = QComboBox()
        for s in ["research / prototype", "pre-clinical (g/month)", "clinical Phase I",
                  "clinical Phase III", "commercial manufacturing"]:
            self._scale_combo.addItem(s)
        fl.addRow("Scale target:", self._scale_combo)

        self._notes_edit = QLineEdit()
        self._notes_edit.setPlaceholderText("Any specific constraints (e.g. glycosylation required, GMP needed)")
        fl.addRow("Notes:", self._notes_edit)

        self._plan_btn = QPushButton(qta.icon('fa5s.industry'), "  Generate Production Plan")
        self._plan_btn.setStyleSheet(
            "background:#2E86AB; color:white; font-weight:bold; padding:6px; border-radius:4px;")
        self._plan_btn.clicked.connect(self._generate)
        fl.addRow(self._plan_btn)
        root.addWidget(form)

        # System comparison table + plan output
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(_section_header("Production Systems — Comparison"))
        self._sys_table = _make_table(["System", "Yield", "Cost", "GMP path"])
        self._sys_table.selectionModel().selectionChanged.connect(self._on_sys_select)
        ll.addWidget(self._sys_table)
        splitter.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(_section_header("Production Plan"))
        self._plan_box = _output_box()
        rl.addWidget(self._plan_box)
        copy_btn = QPushButton(qta.icon('fa5s.copy'), "  Copy")
        copy_btn.clicked.connect(lambda: _copy_text(self._plan_box))
        rl.addWidget(copy_btn)
        splitter.addWidget(right)

        splitter.setSizes([400, 550])
        root.addWidget(splitter)

    def _generate(self):
        mol = self._molecule_edit.text().strip()
        if not mol:
            QMessageBox.warning(self, "Missing input", "Enter a target molecule.")
            return
        _busy_btn(self._plan_btn, True)
        chassis = self._chassis_combo.currentText()
        if chassis == "(recommend for me)":
            chassis = ""
        self._worker = _BioproductionWorker(
            mol,
            chassis,
            self._scale_combo.currentText(),
            self._notes_edit.text().strip(),
        )
        self._worker.plan_ready.connect(self._on_plan)
        self._worker.error.connect(self._on_error)
        self._worker.start()

        # Also populate comparison table from synchronous recommender
        try:
            planner = _bioproduction()
            recs = planner.recommend(mol, chassis)
            self._sys_table.setRowCount(0)
            for r in recs:
                row = self._sys_table.rowCount()
                self._sys_table.insertRow(row)
                self._sys_table.setItem(row, 0, QTableWidgetItem(r.get("system", "")))
                self._sys_table.setItem(row, 1, QTableWidgetItem(r.get("yield", "")))
                self._sys_table.setItem(row, 2, QTableWidgetItem(r.get("cost_tier", "")))
                gmp = r.get("gmp_path", "")[:40]
                self._sys_table.setItem(row, 3, QTableWidgetItem(gmp))
        except Exception:
            pass

    def _on_plan(self, plan: str):
        self._plan_box.setPlainText(plan)
        _busy_btn(self._plan_btn, False)
        self._plan_btn.setText("  Generate Production Plan")

    def _on_sys_select(self):
        rows = self._sys_table.selectionModel().selectedRows()
        if not rows:
            return
        # Show detail from current plan box (plan already contains all detail)

    def _on_error(self, err: str):
        self._plan_box.setPlainText(f"Error: {err}")
        _busy_btn(self._plan_btn, False)
        self._plan_btn.setText("  Generate Production Plan")


# ─────────────────────────────────────────────────────────────────────────────
# Utility
# ─────────────────────────────────────────────────────────────────────────────
def _copy_text(box: QTextEdit):
    from PyQt6.QtWidgets import QApplication
    QApplication.clipboard().setText(box.toPlainText())


# ─────────────────────────────────────────────────────────────────────────────
# MAIN TAB
# ─────────────────────────────────────────────────────────────────────────────
class SynBioTab(QWidget):
    """Synthetic Biology tab — 5 sub-tabs wired to synthetic_biology_engine."""

    #: Emitted when Living Materials detects/clears Scenario C
    scenario_c_changed = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()

        self.parts_tab       = _PartsBrowserTab()
        self.dbtl_tab        = _DBTLWizardTab()
        self.editor_tab      = _GeneticEditorTab()
        self.living_mat_tab  = _LivingMaterialsTab()
        self.bioproduction_tab = _BioproductionTab()

        # Forward Scenario C signal
        self.living_mat_tab.scenario_c_changed.connect(self.scenario_c_changed)

        tabs.addTab(self.parts_tab,         qta.icon('fa5s.dna'),        "Parts Browser")
        tabs.addTab(self.dbtl_tab,          qta.icon('fa5s.project-diagram'), "DBTL Wizard")
        tabs.addTab(self.editor_tab,        qta.icon('fa5s.cut'),        "Genetic Editor")
        tabs.addTab(self.living_mat_tab,    qta.icon('fa5s.seedling'),   "Living Materials")
        tabs.addTab(self.bioproduction_tab, qta.icon('fa5s.industry'),   "Bioproduction")

        layout.addWidget(tabs)
