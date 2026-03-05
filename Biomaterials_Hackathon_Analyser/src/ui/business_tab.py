"""
Business Intelligence Tab - Priority 3 Module
Market analysis, patent research, and business model generation
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QLabel, QLineEdit, QPushButton, QComboBox,
                             QTableWidget, QTextEdit, QFrame, QTabWidget)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import qtawesome as qta

class BusinessTab(QWidget):
    """Business Intelligence and Market Analysis Interface"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        """Initialize the business intelligence interface"""
        
        layout = QVBoxLayout(self)
        
        # Header
        header_label = QLabel("📈 Business Intelligence & Market Analysis")
        header_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(header_label)
        
        # Main tabs
        tab_widget = QTabWidget()
        
        # Market Research tab
        market_tab = QWidget()
        self.setup_market_tab(market_tab)
        tab_widget.addTab(market_tab, qta.icon('fa.chart-pie'), "Market Research")
        
        # Patent Analysis tab
        patent_tab = QWidget()
        self.setup_patent_tab(patent_tab)
        tab_widget.addTab(patent_tab, qta.icon('fa.legal'), "Patent Landscape")
        
        # Business Model tab
        business_tab = QWidget()
        self.setup_business_tab(business_tab)
        tab_widget.addTab(business_tab, qta.icon('fa.briefcase'), "Business Model")
        
        layout.addWidget(tab_widget)
        
    def setup_market_tab(self, tab):
        """Setup market research tab"""
        layout = QVBoxLayout(tab)
        
        # Market parameters
        params_frame = QFrame()
        params_layout = QGridLayout(params_frame)
        
        params_layout.addWidget(QLabel("Market Segment:"), 0, 0)
        segment_combo = QComboBox()
        segment_combo.addItems(["Orthopedic Implants", "Cardiovascular Devices", "Dental Materials", "Wound Care"])
        params_layout.addWidget(segment_combo, 0, 1)
        
        params_layout.addWidget(QLabel("Geographic Region:"), 0, 2)
        region_combo = QComboBox()
        region_combo.addItems(["Global", "North America", "Europe", "Asia-Pacific"])
        params_layout.addWidget(region_combo, 0, 3)
        
        analyze_market_btn = QPushButton("Analyze Market")
        analyze_market_btn.setIcon(qta.icon('fa.search'))
        params_layout.addWidget(analyze_market_btn, 1, 0, 1, 4)
        
        layout.addWidget(params_frame)
        
        # Market analysis results
        market_results = QTextEdit()
        market_results.setPlaceholderText("Market analysis results will be displayed here...")
        layout.addWidget(market_results)
        
    def setup_patent_tab(self, tab):
        """Setup patent analysis tab"""
        layout = QVBoxLayout(tab)
        
        # Patent search
        search_frame = QFrame()
        search_layout = QHBoxLayout(search_frame)
        
        search_layout.addWidget(QLabel("Patent Search:"))
        patent_search = QLineEdit()
        patent_search.setPlaceholderText("Enter technology keywords...")
        search_layout.addWidget(patent_search)
        
        search_btn = QPushButton("Search Patents")
        search_btn.setIcon(qta.icon('fa.search'))
        search_layout.addWidget(search_btn)
        
        layout.addWidget(search_frame)
        
        # Patent results
        patent_table = QTableWidget()
        patent_table.setColumnCount(5)
        patent_table.setHorizontalHeaderLabels(["Patent ID", "Title", "Assignee", "Date", "Citations"])
        layout.addWidget(patent_table)
        
    def setup_business_tab(self, tab):
        """Setup business model generation tab"""
        layout = QVBoxLayout(tab)
        
        # Business model canvas
        canvas_frame = QFrame()
        canvas_layout = QGridLayout(canvas_frame)
        
        # Key sections of business model canvas
        sections = [
            ("Key Partners", 0, 0), ("Key Activities", 0, 1), ("Value Propositions", 0, 2),
            ("Customer Relationships", 0, 3), ("Customer Segments", 0, 4),
            ("Key Resources", 1, 1), ("Channels", 1, 3),
            ("Cost Structure", 2, 0, 1, 2), ("Revenue Streams", 2, 2, 1, 3)
        ]
        
        for section in sections:
            label = QLabel(section[0])
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("background-color: #e9ecef; border: 1px solid #ced4da; padding: 5px;")
            
            if len(section) == 5:  # Spanning multiple columns
                canvas_layout.addWidget(label, section[1], section[2], section[3], section[4])
            else:
                canvas_layout.addWidget(label, section[1], section[2])
        
        layout.addWidget(canvas_frame)
        
        # Generate button
        generate_btn = QPushButton("Generate Business Plan")
        generate_btn.setIcon(qta.icon('fa.magic'))
        layout.addWidget(generate_btn)
