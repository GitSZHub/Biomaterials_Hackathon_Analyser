"""
Data Manager Package
====================
Single import point for all database operations.

Usage in any module:
    from data_manager import get_db, crud

    # Initialise (call once at app startup, safe to call multiple times)
    get_db()

    # Use CRUD helpers
    from data_manager.crud import upsert_paper, list_researchers
"""

from .database import DatabaseManager, get_db
from . import crud

__all__ = [
    "DatabaseManager",
    "get_db",
    "crud",
]