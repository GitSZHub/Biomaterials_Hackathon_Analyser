"""
Main Window UI for Biomaterials Hackathon Analyser
Desktop application main interface with tabbed modules
"""

from PyQt6.QtWidgets import (QMainWindow, QTabWidget, QVBoxLayout,
                             QHBoxLayout, QWidget, QPushButton, QLabel,
                             QMenuBar, QStatusBar, QFrame, QGridLayout)
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


class MainWindow(QMainWindow):
    """Main application window with tabbed interface"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Biomaterials Hackathon Analyser v1.0")
        self.setGeometry(100, 100, 1400, 900)

        self.init_ui()
        self.init_menu_bar()
        self.init_status_bar()
        self.setup_styling()

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
        status_frame.setMaximumHeight(70)
        status_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 5px;
            }
        """)
        status_layout = QGridLayout(status_frame)

        self._papers_label      = self._make_stat(status_layout, "Papers Indexed",     "0", 0, 0)
        self._materials_label   = self._make_stat(status_layout, "Materials Analyzed", "0", 0, 1)
        self._researchers_label = self._make_stat(status_layout, "Researchers",        "0", 0, 2)
        self._projects_label    = self._make_stat(status_layout, "Active Projects",    "1", 0, 3)

        main_layout.addWidget(status_frame)
        self._refresh_stats()

    def _make_stat(self, layout, label, value, row, col):
        container = QFrame()
        cl = QVBoxLayout(container)
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

    # ── Stubs ─────────────────────────────────────────────────────────
    def new_project(self):
        self.status_bar.showMessage("Creating new project...")

    def open_project(self):
        self.status_bar.showMessage("Opening project...")

    def save_project(self):
        self.status_bar.showMessage("Saving project...")

    def export_results(self):
        self.status_bar.showMessage("Exporting results...")

    def open_settings(self):
        pass

    def open_db_manager(self):
        pass

    def show_about(self):
        pass