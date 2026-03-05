"""
Main Window UI for Biomaterials Hackathon Analyser
Desktop application main interface with tabbed modules
"""

from PyQt6.QtWidgets import (QMainWindow, QTabWidget, QVBoxLayout, 
                             QHBoxLayout, QWidget, QPushButton, QLabel, 
                             QMenuBar, QStatusBar, QSplitter, QTextEdit,
                             QFrame, QGridLayout)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap, QIcon, QAction
import qtawesome as qta

from .literature_tab import LiteratureTab
from .materials_tab import MaterialsTab
from .business_tab import BusinessTab
from .bio_analysis_tab import BioAnalysisTab

class MainWindow(QMainWindow):
    """Main application window with tabbed interface"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Biomaterials Hackathon Analyser v1.0")
        self.setGeometry(100, 100, 1400, 900)
        
        # Initialize UI components
        self.init_ui()
        self.init_menu_bar()
        self.init_status_bar()
        self.setup_styling()
        
    def init_ui(self):
        """Initialize the main user interface"""
        
        # Central widget with main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Header section
        header_frame = QFrame()
        header_frame.setMaximumHeight(80)
        header_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2E86AB, stop:1 #A23B72);
                border-radius: 10px;
                color: white;
            }
        """)
        
        header_layout = QHBoxLayout(header_frame)
        
        # Application title
        title_label = QLabel("🧬 Biomaterials Hackathon Analyser")
        title_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title_label.setStyleSheet("color: white; padding: 10px;")
        
        # Quick action buttons
        quick_actions = QHBoxLayout()
        
        new_project_btn = QPushButton("New Project")
        new_project_btn.setIcon(qta.icon('fa.plus', color='white'))
        new_project_btn.clicked.connect(self.new_project)
        
        open_project_btn = QPushButton("Open Project")
        open_project_btn.setIcon(qta.icon('fa.folder-open', color='white'))
        open_project_btn.clicked.connect(self.open_project)
        
        export_btn = QPushButton("Export Results")
        export_btn.setIcon(qta.icon('fa.download', color='white'))
        export_btn.clicked.connect(self.export_results)
        
        for btn in [new_project_btn, open_project_btn, export_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 255, 255, 0.2);
                    color: white;
                    border: 1px solid white;
                    border-radius: 5px;
                    padding: 8px 15px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.3);
                }
            """)
            quick_actions.addWidget(btn)
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addLayout(quick_actions)
        
        main_layout.addWidget(header_frame)
        
        # Main tabbed interface
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.North)
        
        # Initialize tabs based on priority
        self.literature_tab = LiteratureTab()
        self.materials_tab = MaterialsTab()
        self.business_tab = BusinessTab()
        self.bio_tab = BioAnalysisTab()
        
        # Add tabs in priority order
        self.tab_widget.addTab(self.literature_tab, 
                              qta.icon('fa.book'), "Literature Analysis")
        self.tab_widget.addTab(self.materials_tab, 
                              qta.icon('fa.cogs'), "Materials Modeling")
        self.tab_widget.addTab(self.business_tab, 
                              qta.icon('fa.chart-line'), "Business Intelligence")
        self.tab_widget.addTab(self.bio_tab, 
                              qta.icon('fa.dna'), "Bio Analysis")
        
        main_layout.addWidget(self.tab_widget)
        
        # Status information panel
        status_frame = QFrame()
        status_frame.setMaximumHeight(100)
        status_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 5px;
            }
        """)
        
        status_layout = QGridLayout(status_frame)
        
        # Add status indicators
        self.create_status_indicator(status_layout, "Papers Indexed", "0", 0, 0)
        self.create_status_indicator(status_layout, "Materials Analyzed", "0", 0, 1)
        self.create_status_indicator(status_layout, "Active Projects", "1", 0, 2)
        self.create_status_indicator(status_layout, "Last Update", "Never", 0, 3)
        
        main_layout.addWidget(status_frame)
        
    def create_status_indicator(self, layout, label, value, row, col):
        """Create a status indicator widget"""
        container = QFrame()
        container_layout = QVBoxLayout(container)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        value_label = QLabel(value)
        value_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label.setStyleSheet("color: #2E86AB;")
        
        desc_label = QLabel(label)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setStyleSheet("color: #6c757d; font-size: 10px;")
        
        container_layout.addWidget(value_label)
        container_layout.addWidget(desc_label)
        
        layout.addWidget(container, row, col)
        
    def init_menu_bar(self):
        """Initialize the menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('File')
        
        new_action = QAction(qta.icon('fa.plus'), 'New Project', self)
        new_action.setShortcut('Ctrl+N')
        new_action.triggered.connect(self.new_project)
        
        open_action = QAction(qta.icon('fa.folder-open'), 'Open Project', self)
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self.open_project)
        
        save_action = QAction(qta.icon('fa.save'), 'Save Project', self)
        save_action.setShortcut('Ctrl+S')
        save_action.triggered.connect(self.save_project)
        
        file_menu.addAction(new_action)
        file_menu.addAction(open_action)
        file_menu.addSeparator()
        file_menu.addAction(save_action)
        
        # Tools menu
        tools_menu = menubar.addMenu('Tools')
        
        settings_action = QAction(qta.icon('fa.cog'), 'Settings', self)
        settings_action.triggered.connect(self.open_settings)
        
        db_action = QAction(qta.icon('fa.database'), 'Database Manager', self)
        db_action.triggered.connect(self.open_db_manager)
        
        tools_menu.addAction(settings_action)
        tools_menu.addAction(db_action)
        
        # Help menu
        help_menu = menubar.addMenu('Help')
        
        about_action = QAction(qta.icon('fa.info'), 'About', self)
        about_action.triggered.connect(self.show_about)
        
        help_menu.addAction(about_action)
        
    def init_status_bar(self):
        """Initialize the status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.status_bar.showMessage("Ready - Welcome to Biomaterials Hackathon Analyser")
        
        # Add permanent widgets
        self.connection_label = QLabel("🔴 Offline")
        self.status_bar.addPermanentWidget(self.connection_label)
        
    def setup_styling(self):
        """Setup application styling"""
        self.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #c0c0c0;
                background-color: white;
            }
            
            QTabBar::tab {
                background: #e1e1e1;
                border: 1px solid #c0c0c0;
                padding: 10px 20px;
                margin-right: 2px;
            }
            
            QTabBar::tab:selected {
                background: white;
                border-bottom: 1px solid white;
            }
            
            QTabBar::tab:hover {
                background: #f0f0f0;
            }
        """)
    
    # Event handlers
    def new_project(self):
        """Create a new project"""
        self.status_bar.showMessage("Creating new project...")
        # TODO: Implement new project dialog
        
    def open_project(self):
        """Open an existing project"""
        self.status_bar.showMessage("Opening project...")
        # TODO: Implement project file dialog
        
    def save_project(self):
        """Save current project"""
        self.status_bar.showMessage("Saving project...")
        # TODO: Implement project saving
        
    def export_results(self):
        """Export analysis results"""
        self.status_bar.showMessage("Exporting results...")
        # TODO: Implement export functionality
        
    def open_settings(self):
        """Open application settings"""
        # TODO: Implement settings dialog
        pass
        
    def open_db_manager(self):
        """Open database manager"""
        # TODO: Implement database management interface
        pass
        
    def show_about(self):
        """Show about dialog"""
        # TODO: Implement about dialog
        pass
