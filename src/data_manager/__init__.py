"""
data_manager — SQLite-backed persistence layer for the Biomaterials Analyser.

Public surface:
    from data_manager import db, ProjectContext

    db: DatabaseManager  — singleton, call db.init(path) once at startup.
    ProjectContext       — dataclass holding the active project's scope.
"""

from .database import DatabaseManager
from .project_context import ProjectContext

db: DatabaseManager = DatabaseManager()

__all__ = ["db", "DatabaseManager", "ProjectContext"]
