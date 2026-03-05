"""
UI Package for Biomaterials Hackathon Analyser
Desktop application interface components
"""

from .main_window import MainWindow
from .literature_tab import LiteratureTab
from .materials_tab import MaterialsTab
from .business_tab import BusinessTab
from .bio_analysis_tab import BioAnalysisTab

__all__ = [
    'MainWindow',
    'LiteratureTab',
    'MaterialsTab', 
    'BusinessTab',
    'BioAnalysisTab'
]
