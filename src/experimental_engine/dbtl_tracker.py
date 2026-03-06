"""
DBTL Cycle Tracker
==================
Records Design-Build-Test-Learn iterations for a biomaterials project.
Each cycle captures the hypothesis, actions taken, results, and lessons learned,
building an iterative evidence base that feeds back into the next design cycle.

Persistence is via the project's SQLite database (data_manager CRUD layer).
Falls back to in-memory list if the database is unavailable.

Usage:
    from experimental_engine.dbtl_tracker import DBTLTracker, DBTLCycle

    tracker = DBTLTracker(project_id=1)
    cycle_id = tracker.add_cycle(
        iteration=1,
        design_hypothesis="HA coating at 20% w/w will improve osteoblast adhesion",
        design_decisions=["HA 20% w/w", "electrospun PCL base", "72h coating"],
        build_actions=["Electrospun PCL scaffold", "Dip-coat in HA suspension", "SEM verification"],
        test_plan=["ISO 10993-5 cytotoxicity", "ALP activity at day 7/14", "Alizarin Red day 21"],
    )
    tracker.record_results(cycle_id, results={"ALP_d14": 1.8, "viability": 95.2})
    tracker.record_learning(cycle_id, learning="ALP improved 1.8x vs control; increase HA to 30% for next cycle")
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class DBTLCycle:
    cycle_id:            int
    project_id:          int
    iteration:           int
    status:              str                 # design / build / test / learn / complete
    created_at:          str                 # ISO datetime string
    updated_at:          str

    # Design phase
    design_hypothesis:   str = ""
    design_decisions:    List[str] = field(default_factory=list)
    material_composition: str = ""
    target_tissue:       str = ""

    # Build phase
    build_actions:       List[str] = field(default_factory=list)
    fabrication_method:  str = ""
    batch_id:            str = ""

    # Test phase
    test_plan:           List[str] = field(default_factory=list)
    cell_models_used:    List[str] = field(default_factory=list)
    organism_models_used: List[str] = field(default_factory=list)

    # Learn phase
    results:             Dict[str, Any] = field(default_factory=dict)
    learning:            str = ""
    go_nogo_decision:    str = ""      # "go" / "no-go" / "pivot" / "pending"
    next_iteration_notes: str = ""


# ── Tracker ────────────────────────────────────────────────────────────────────

class DBTLTracker:
    """
    Manage DBTL cycle records for a project.

    Attempts to persist via data_manager SQLite; falls back to in-memory
    store so the UI always works even without a database connection.
    """

    def __init__(self, project_id: int = 1):
        self._project_id = project_id
        self._memory_store: List[DBTLCycle] = []   # fallback
        self._next_id = 1
        self._db_available = self._check_db()

    # ── Public API ─────────────────────────────────────────────────────────────

    def add_cycle(
        self,
        iteration: int,
        design_hypothesis: str = "",
        design_decisions: Optional[List[str]] = None,
        build_actions: Optional[List[str]] = None,
        test_plan: Optional[List[str]] = None,
        material_composition: str = "",
        target_tissue: str = "",
        fabrication_method: str = "",
        batch_id: str = "",
    ) -> int:
        """
        Create a new DBTL cycle in Design phase.  Returns the cycle_id.
        """
        now = datetime.now().isoformat(timespec="seconds")
        cycle = DBTLCycle(
            cycle_id=self._next_id,
            project_id=self._project_id,
            iteration=iteration,
            status="design",
            created_at=now,
            updated_at=now,
            design_hypothesis=design_hypothesis,
            design_decisions=design_decisions or [],
            material_composition=material_composition,
            target_tissue=target_tissue,
            build_actions=build_actions or [],
            fabrication_method=fabrication_method,
            batch_id=batch_id,
            test_plan=test_plan or [],
        )
        self._save(cycle)
        self._next_id += 1
        return cycle.cycle_id

    def advance_phase(self, cycle_id: int, new_phase: str) -> bool:
        """Advance a cycle to the next DBTL phase: design->build->test->learn->complete."""
        cycle = self.get_cycle(cycle_id)
        if cycle is None:
            return False
        cycle.status = new_phase
        cycle.updated_at = datetime.now().isoformat(timespec="seconds")
        self._update(cycle)
        return True

    def record_results(
        self,
        cycle_id: int,
        results: Dict[str, Any],
        cell_models_used: Optional[List[str]] = None,
        organism_models_used: Optional[List[str]] = None,
    ) -> bool:
        cycle = self.get_cycle(cycle_id)
        if cycle is None:
            return False
        cycle.results = results
        if cell_models_used:
            cycle.cell_models_used = cell_models_used
        if organism_models_used:
            cycle.organism_models_used = organism_models_used
        cycle.status = "learn"
        cycle.updated_at = datetime.now().isoformat(timespec="seconds")
        self._update(cycle)
        return True

    def record_learning(
        self,
        cycle_id: int,
        learning: str,
        go_nogo: str = "pending",
        next_notes: str = "",
    ) -> bool:
        cycle = self.get_cycle(cycle_id)
        if cycle is None:
            return False
        cycle.learning = learning
        cycle.go_nogo_decision = go_nogo
        cycle.next_iteration_notes = next_notes
        cycle.status = "complete" if go_nogo in ("go", "no-go", "pivot") else "learn"
        cycle.updated_at = datetime.now().isoformat(timespec="seconds")
        self._update(cycle)
        return True

    def get_cycle(self, cycle_id: int) -> Optional[DBTLCycle]:
        # Try DB first
        if self._db_available:
            row = self._db_get(cycle_id)
            if row:
                return row
        # Fallback memory
        return next((c for c in self._memory_store if c.cycle_id == cycle_id), None)

    def get_all_cycles(self) -> List[DBTLCycle]:
        if self._db_available:
            rows = self._db_get_all()
            if rows:
                return rows
        return list(self._memory_store)

    def get_latest_cycle(self) -> Optional[DBTLCycle]:
        all_cycles = self.get_all_cycles()
        return all_cycles[-1] if all_cycles else None

    def summary_table(self) -> List[Dict[str, str]]:
        """Return a flat list of dicts suitable for table display."""
        rows = []
        for c in self.get_all_cycles():
            rows.append({
                "Iteration": str(c.iteration),
                "Status": c.status.capitalize(),
                "Hypothesis": c.design_hypothesis[:60] + ("..." if len(c.design_hypothesis) > 60 else ""),
                "Material": c.material_composition[:40] + ("..." if len(c.material_composition) > 40 else ""),
                "Go/No-Go": c.go_nogo_decision or "pending",
                "Updated": c.updated_at[:10],
            })
        return rows

    # ── Persistence helpers ────────────────────────────────────────────────────

    def _check_db(self) -> bool:
        try:
            from data_manager import get_db   # type: ignore
            get_db()
            return True
        except Exception:
            return False

    def _save(self, cycle: DBTLCycle) -> None:
        self._memory_store.append(cycle)
        if self._db_available:
            try:
                from data_manager import get_db   # type: ignore
                db = get_db()
                with db.connection() as conn:
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS dbtl_cycles (
                            id INTEGER PRIMARY KEY,
                            project_id INTEGER,
                            data TEXT,
                            created_at TEXT,
                            updated_at TEXT
                        )
                    """)
                    conn.execute(
                        "INSERT INTO dbtl_cycles (id, project_id, data, created_at, updated_at) VALUES (?,?,?,?,?)",
                        (cycle.cycle_id, cycle.project_id,
                         json.dumps(asdict(cycle)), cycle.created_at, cycle.updated_at)
                    )
            except Exception as e:
                logger.warning("DBTL DB save failed: %s", e)

    def _update(self, cycle: DBTLCycle) -> None:
        # Update in-memory store
        for i, c in enumerate(self._memory_store):
            if c.cycle_id == cycle.cycle_id:
                self._memory_store[i] = cycle
                break
        if self._db_available:
            try:
                from data_manager import get_db   # type: ignore
                db = get_db()
                with db.connection() as conn:
                    conn.execute(
                        "UPDATE dbtl_cycles SET data=?, updated_at=? WHERE id=?",
                        (json.dumps(asdict(cycle)), cycle.updated_at, cycle.cycle_id)
                    )
            except Exception as e:
                logger.warning("DBTL DB update failed: %s", e)

    def _db_get(self, cycle_id: int) -> Optional[DBTLCycle]:
        try:
            from data_manager import get_db   # type: ignore
            db = get_db()
            with db.connection() as conn:
                row = conn.execute(
                    "SELECT data FROM dbtl_cycles WHERE id=? AND project_id=?",
                    (cycle_id, self._project_id)
                ).fetchone()
            if row:
                return DBTLCycle(**json.loads(row[0]))
        except Exception:
            pass
        return None

    def _db_get_all(self) -> List[DBTLCycle]:
        try:
            from data_manager import get_db   # type: ignore
            db = get_db()
            with db.connection() as conn:
                rows = conn.execute(
                    "SELECT data FROM dbtl_cycles WHERE project_id=? ORDER BY id",
                    (self._project_id,)
                ).fetchall()
            return [DBTLCycle(**json.loads(r[0])) for r in rows]
        except Exception:
            pass
        return []
