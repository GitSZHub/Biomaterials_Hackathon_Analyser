#!/usr/bin/env python3
"""
Biomaterials Hackathon Analyser - Main Application Entry Point
Desktop application for comprehensive biomaterials research analysis
"""

import sys
import os
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QIcon
    PYQT_AVAILABLE = True
except ImportError:
    print("PyQt6 not found. Installing requirements...")
    PYQT_AVAILABLE = False

def main():
    """Main application entry point"""
    if not PYQT_AVAILABLE:
        print("Please install requirements first:")
        print("pip install -r requirements.txt")
        return 1
    
    # Create QApplication
    app = QApplication(sys.argv)
    app.setApplicationName("Biomaterials Hackathon Analyser")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Biomaterials Research Lab")
    
    # Set application style
    app.setStyle('Fusion')  # Modern cross-platform style
    
    # Import and create main window
    from ui.main_window import MainWindow
    
    window = MainWindow()
    window.show()
    
    # Run application
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
