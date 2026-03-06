"""
Main Window UI for Biomaterials Hackathon Analyser
Desktop application main interface with tabbed modules
"""

from PyQt6.QtWidgets import (QMainWindow, QTabWidget, QVBoxLayout,
                             QHBoxLayout, QWidget, QPushButton, QLabel,
                             QMenuBar, QStatusBar, QFrame, QGridLayout,
                             QDialog, QFormLayout, QLineEdit, QComboBox,
                             QDialogButtonBox, QTextEdit, QFileDialog,
                             QMessageBox, QListWidget, QListWidgetItem,
                             QAbstractItemView)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QAction
import qtawesome as qta

from .literature_tab import LiteratureTab
from .researcher_network_tab import ResearcherNetworkTab
from .materials_tab import MaterialsTab
from .business_tab import BusinessTab
from .bio_analysis_tab import BioAnalysisTab
from .drug_tab import DrugTab
from .regulatory_tab import RegulatoryTab
from .experimental_tab import ExperimentalTab
from .briefing_tab import BriefingTab
from .tox_tab import ToxTab
from .synbio_tab import SynBioTab


class _NewProjectDialog(QDialog):
    """Dialog to initialise a new project with basic context."""

    _TISSUES = [
        "Bone", "Cartilage", "Skin", "Cardiac", "Vascular",
        "Neural", "Liver", "Kidney", "Lung", "Tendon/Ligament",
        "Cornea", "Intervertebral disc", "Other",
    ]
    _SCENARIOS = [
        ("A — Inert scaffold (Class I/II/III device)", "A"),
        ("B — Scaffold + drug combination", "B"),
        ("C — Scaffold + engineered living cells (ATMP)", "C"),
        ("D — Engineered organism produces material (GMO manufacturing)", "D"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. GelMA Cartilage Scaffold")
        form.addRow("Project name:", self._name_edit)

        self._tissue_combo = QComboBox()
        for t in self._TISSUES:
            self._tissue_combo.addItem(t)
        form.addRow("Target tissue:", self._tissue_combo)

        self._scenario_combo = QComboBox()
        for label, _ in self._SCENARIOS:
            self._scenario_combo.addItem(label)
        form.addRow("Regulatory scenario:", self._scenario_combo)

        self._notes_edit = QTextEdit()
        self._notes_edit.setPlaceholderText(
            "Optional: key materials, clinical indication, team resources ...")
        self._notes_edit.setMaximumHeight(80)
        form.addRow("Notes:", self._notes_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self):
        if not self._name_edit.text().strip():
            QMessageBox.warning(self, "Required", "Enter a project name.")
            return
        self.accept()

    def project_name(self) -> str:
        return self._name_edit.text().strip()

    def target_tissue(self) -> str:
        return self._tissue_combo.currentText()

    def regulatory_scenario(self) -> str:
        return self._SCENARIOS[self._scenario_combo.currentIndex()][1]

    def notes(self) -> str:
        return self._notes_edit.toPlainText().strip()


class _OpenProjectDialog(QDialog):
    """Lists all saved projects and lets the user pick one."""

    def __init__(self, projects: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Open Project")
        self.setMinimumSize(520, 320)
        self._selected: dict = {}

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select a project to open:"))

        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.itemDoubleClicked.connect(self._on_accept)
        for p in projects:
            name     = p.get("name", "Unnamed")
            tissue   = p.get("target_tissue", "") or ""
            scenario = p.get("regulatory_scenario", "") or ""
            modified = (p.get("last_modified") or "")[:10]
            text = f"{name}   [{tissue}  ·  Scenario {scenario}  ·  {modified}]"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, p)
            self._list.addItem(item)
        if self._list.count():
            self._list.setCurrentRow(0)
        layout.addWidget(self._list)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self):
        item = self._list.currentItem()
        if item:
            self._selected = item.data(Qt.ItemDataRole.UserRole)
            self.accept()

    def selected_project(self) -> dict:
        return self._selected


class MainWindow(QMainWindow):
    """Main application window with tabbed interface"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Biomaterials Hackathon Analyser v1.0")
        self.setGeometry(100, 100, 1400, 900)
        self._project_id: int = 1   # overwritten by _load_last_project

        self.init_ui()
        self.init_menu_bar()
        self.init_status_bar()
        self.setup_styling()
        self._load_last_project()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # ── Header ────────────────────────────────────────────────────
        header_frame = QFrame()
        header_frame.setMaximumHeight(80)
        header_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2E86AB, stop:1 #A23B72);
                border-radius: 10px;
            }
        """)
        header_layout = QHBoxLayout(header_frame)

        title_label = QLabel("🧬 Biomaterials Hackathon Analyser")
        title_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title_label.setStyleSheet("color: white; padding: 10px;")

        btn_style = """
            QPushButton {
                background-color: rgba(255,255,255,0.2);
                color: white; border: 1px solid white;
                border-radius: 5px; padding: 8px 15px; font-weight: bold;
            }
            QPushButton:hover { background-color: rgba(255,255,255,0.35); }
        """
        quick_actions = QHBoxLayout()
        for label, icon, slot in [
            ("New Project",    'fa5s.plus',          self.new_project),
            ("Open Project",   'fa5s.folder-open',   self.open_project),
            ("Export Results", 'fa5s.download',       self.export_results),
        ]:
            btn = QPushButton(label)
            btn.setIcon(qta.icon(icon, color='white'))
            btn.setStyleSheet(btn_style)
            btn.clicked.connect(slot)
            quick_actions.addWidget(btn)

        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addLayout(quick_actions)
        main_layout.addWidget(header_frame)

        # ── Tab widget ────────────────────────────────────────────────
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.North)

        self.literature_tab   = LiteratureTab()
        self.researcher_tab   = ResearcherNetworkTab()
        self.materials_tab    = MaterialsTab()
        self.business_tab     = BusinessTab()
        self.bio_tab          = BioAnalysisTab()
        self.drug_tab         = DrugTab()
        self.regulatory_tab   = RegulatoryTab()
        self.experimental_tab = ExperimentalTab()
        self.briefing_tab     = BriefingTab()
        self.tox_tab          = ToxTab()
        self.synbio_tab       = SynBioTab()

        # Wire ToxTab -> RegulatoryTab so live MCP clients enrich ISO 10993 / biocompat
        self.regulatory_tab.set_tox_tab(self.tox_tab)
        # Wire RegulatoryTab -> ExperimentalTab so classification prefills wizard
        self.regulatory_tab.set_experimental_tab(self.experimental_tab)
        # Wire BusinessTab + ExperimentalTab -> BriefingTab so context assembly sees live objects
        self.briefing_tab.set_module_tabs(self.business_tab, self.experimental_tab)

        # Wire SynBio Scenario C -> RegulatoryTab notification
        self.synbio_tab.scenario_c_changed.connect(self._on_scenario_c_changed)

        self.tab_widget.addTab(self.literature_tab,
                               qta.icon('fa5s.book'),         "Literature")
        self.tab_widget.addTab(self.researcher_tab,
                               qta.icon('fa5s.users'),        "Researcher Network")
        self.tab_widget.addTab(self.materials_tab,
                               qta.icon('fa5s.cogs'),         "Materials Modeling")
        self.tab_widget.addTab(self.business_tab,
                               qta.icon('fa5s.chart-line'),   "Business Intelligence")
        self.tab_widget.addTab(self.bio_tab,
                               qta.icon('fa5s.flask'),        "Bio Analysis")
        self.tab_widget.addTab(self.drug_tab,
                               qta.icon('fa5s.pills'),        "Drug Delivery")
        self.tab_widget.addTab(self.regulatory_tab,
                               qta.icon('fa5s.shield-alt'),       "Regulatory")
        self.tab_widget.addTab(self.experimental_tab,
                               qta.icon('fa5s.flask'),        "Experimental Design")
        self.tab_widget.addTab(self.synbio_tab,
                               qta.icon('fa5s.dna'),          "Synthetic Biology")
        self.tab_widget.addTab(self.tox_tab,
                               qta.icon('fa5s.exclamation-triangle'),      "Toxicology")
        self.tab_widget.addTab(self.briefing_tab,
                               qta.icon('fa5s.star'),         "Briefing Generator")

        main_layout.addWidget(self.tab_widget)

        # ── Status strip ──────────────────────────────────────────────
        status_frame = QFrame()
        status_frame.setMinimumHeight(80)
        status_frame.setMaximumHeight(90)
        status_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 5px;
                padding: 4px;
            }
        """)
        status_layout = QGridLayout(status_frame)
        status_layout.setContentsMargins(8, 6, 8, 6)

        self._papers_label      = self._make_stat(status_layout, "Papers Indexed",     "0", 0, 0)
        self._materials_label   = self._make_stat(status_layout, "Materials Analyzed", "0", 0, 1)
        self._researchers_label = self._make_stat(status_layout, "Researchers",        "0", 0, 2)
        self._projects_label    = self._make_stat(status_layout, "Active Projects",    "1", 0, 3)

        main_layout.addWidget(status_frame)
        self._refresh_stats()

    def _make_stat(self, layout, label, value, row, col):
        container = QFrame()
        cl = QVBoxLayout(container)
        cl.setContentsMargins(4, 4, 4, 4)
        cl.setSpacing(2)
        cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val = QLabel(value)
        val.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val.setStyleSheet("color: #2E86AB;")
        desc = QLabel(label)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color: #6c757d; font-size: 10px;")
        cl.addWidget(val)
        cl.addWidget(desc)
        layout.addWidget(container, row, col)
        return val

    def _refresh_stats(self):
        try:
            from data_manager import crud, get_db
            with get_db().connection() as conn:
                papers      = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
                materials   = conn.execute("SELECT COUNT(*) FROM materials").fetchone()[0]
                researchers = conn.execute("SELECT COUNT(*) FROM researchers").fetchone()[0]
            self._papers_label.setText(str(papers))
            self._materials_label.setText(str(materials))
            self._researchers_label.setText(str(researchers))
        except Exception:
            pass

    # ── Menu bar ──────────────────────────────────────────────────────
    def init_menu_bar(self):
        menubar = self.menuBar()
        assert menubar is not None

        file_menu = menubar.addMenu('File')
        assert file_menu is not None
        for label, shortcut, icon, slot in [
            ('New Project',  'Ctrl+N', 'fa5s.plus',        self.new_project),
            ('Open Project', 'Ctrl+O', 'fa5s.folder-open', self.open_project),
            ('Save Project', 'Ctrl+S', 'fa5s.save',        self.save_project),
        ]:
            action = QAction(qta.icon(icon), label, self)
            action.setShortcut(shortcut)
            action.triggered.connect(slot)
            file_menu.addAction(action)

        tools_menu = menubar.addMenu('Tools')
        assert tools_menu is not None
        settings_action = QAction(qta.icon('fa5s.cog'), 'Settings', self)
        settings_action.triggered.connect(self.open_settings)
        db_action = QAction(qta.icon('fa5s.database'), 'Database Manager', self)
        db_action.triggered.connect(self.open_db_manager)
        tools_menu.addAction(settings_action)
        tools_menu.addAction(db_action)

        help_menu = menubar.addMenu('Help')
        assert help_menu is not None
        about_action = QAction(qta.icon('fa5s.info'), 'About', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    # ── Status bar ────────────────────────────────────────────────────
    def init_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready — Biomaterials Hackathon Analyser")
        self.connection_label = QLabel("🔴 Offline")
        self.status_bar.addPermanentWidget(self.connection_label)

    # ── Styling ───────────────────────────────────────────────────────
    def setup_styling(self):
        self.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #c0c0c0;
                background-color: white;
            }
            QTabBar::tab {
                background: #e1e1e1;
                border: 1px solid #c0c0c0;
                padding: 8px 16px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: white;
                border-bottom: 1px solid white;
                font-weight: bold;
            }
            QTabBar::tab:hover { background: #f0f0f0; }
        """)

    def closeEvent(self, event):
        """Stop all MCP servers on app exit."""
        try:
            from .tox_tab import get_tox_manager
            mgr = get_tox_manager()
            if mgr is not None:
                mgr.stop_all()
        except Exception:
            pass
        super().closeEvent(event)

    def _on_scenario_c_changed(self, is_scenario_c: bool):
        """Notify status bar when Living Materials triggers/clears Scenario C."""
        if is_scenario_c:
            self.status_bar.showMessage(
                "Synthetic Biology: Scenario C (ATMP) detected — check Regulatory tab.")
        else:
            self.status_bar.showMessage(
                "Synthetic Biology: Scenario C cleared.")

    # ── Project actions ───────────────────────────────────────────────
    def _load_last_project(self):
        """Restore the most recently modified project from the database."""
        try:
            from data_manager import crud
            project = crud.get_latest_project()
            if not project:
                return
            self._project_id = project.get("id", 1)
            name     = project.get("name", "")
            tissue   = project.get("target_tissue", "") or ""
            scenario = project.get("regulatory_scenario", "") or ""
            if name:
                self.setWindowTitle(f"Biomaterials Hackathon Analyser — {name}")
                self.status_bar.showMessage(
                    f"Restored: '{name}'  |  Tissue: {tissue}  |  Scenario: {scenario}"
                )
            try:
                if tissue:
                    self.regulatory_tab._tissue_combo.setCurrentText(tissue)
            except Exception:
                pass
            try:
                if tissue or scenario:
                    self.experimental_tab.prefill(tissue=tissue, scenario=scenario)
            except Exception:
                pass
            self._propagate_project_id()
        except Exception:
            pass

    def _propagate_project_id(self):
        """Push current project ID to all tabs."""
        for tab in [
            self.literature_tab, self.researcher_tab, self.materials_tab,
            self.business_tab, self.bio_tab, self.drug_tab,
            self.regulatory_tab, self.experimental_tab,
            self.tox_tab, self.synbio_tab, self.briefing_tab,
        ]:
            try:
                tab.set_project_id(self._project_id)
            except Exception:
                pass

    def new_project(self):
        dlg = _NewProjectDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        name     = dlg.project_name()
        tissue   = dlg.target_tissue()
        scenario = dlg.regulatory_scenario()
        notes    = dlg.notes()

        # Persist to database
        try:
            from data_manager import crud
            self._project_id = crud.create_project(
                name=name,
                target_tissue=tissue,
                regulatory_scenario=scenario,
                notes=notes,
            )
        except Exception:
            pass

        self._propagate_project_id()
        self.setWindowTitle(f"Biomaterials Hackathon Analyser — {name}")
        self.status_bar.showMessage(
            f"Project '{name}' created  |  Tissue: {tissue}  |  Scenario: {scenario}"
        )

        # Prefill Regulatory + Experimental tabs with project context
        try:
            self.regulatory_tab._tissue_combo.setCurrentText(tissue)
        except Exception:
            pass
        try:
            self.experimental_tab.prefill(tissue=tissue, scenario=scenario)
        except Exception:
            pass

        self._refresh_stats()

    def open_project(self):
        try:
            from data_manager import crud
            projects = crud.list_projects()
        except Exception as e:
            QMessageBox.warning(self, "Database error", str(e))
            return
        if not projects:
            QMessageBox.information(self, "No projects",
                                    "No saved projects found. Create one with New Project.")
            return
        dlg = _OpenProjectDialog(projects, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        project = dlg.selected_project()
        if not project:
            return

        self._project_id = project.get("id", 1)
        name     = project.get("name", "")
        tissue   = project.get("target_tissue", "") or ""
        scenario = project.get("regulatory_scenario", "") or ""

        self.setWindowTitle(f"Biomaterials Hackathon Analyser — {name}")
        self.status_bar.showMessage(
            f"Opened: '{name}'  |  Tissue: {tissue}  |  Scenario: {scenario}"
        )
        try:
            if tissue:
                self.regulatory_tab._tissue_combo.setCurrentText(tissue)
        except Exception:
            pass
        try:
            if tissue or scenario:
                self.experimental_tab.prefill(tissue=tissue, scenario=scenario)
        except Exception:
            pass
        self._propagate_project_id()
        self._refresh_stats()

    def save_project(self):
        self.status_bar.showMessage("Save Project — not yet implemented.")

    def export_results(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Results", "hackathon_results.txt",
            "Text files (*.txt);;All files (*)"
        )
        if not path:
            return
        try:
            lines = [
                "Biomaterials Hackathon Analyser — Export",
                "=" * 50,
                "",
            ]
            # Briefing content if available
            try:
                text = self.briefing_tab._output_box.toPlainText()
                if text:
                    lines += ["=== Briefing ===", text, ""]
            except Exception:
                pass
            # Regulatory classification if available
            try:
                reg_text = self.regulatory_tab._result_display.toPlainText()
                if reg_text:
                    lines += ["=== Regulatory Classification ===", reg_text, ""]
            except Exception:
                pass
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self.status_bar.showMessage(f"Results exported to {path}")
        except Exception as e:
            QMessageBox.warning(self, "Export failed", str(e))

    def open_settings(self):
        pass

    def open_db_manager(self):
        pass

    def show_about(self):
        pass