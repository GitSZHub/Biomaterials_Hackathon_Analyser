"""
Researcher Tracker
==================
Manages the researcher network — syncing each researcher's
latest papers from PubMed and building the co-authorship graph.

Three input modes (per architecture doc):
  1. Manual add (name -> PubMed query -> confirm)
  2. Bulk import (CSV/paste — post day one)
  3. Network discovery BFS (post day one)

Pre-configured key researchers seeded on first run:
  - Jos Malda      (UMC Utrecht — biofab, cartilage, MEW)
  - Riccardo Levato (UMC Utrecht — GRACE, VBP, pancreas)
  - Miguel Castilho (TU/e — Xolography, scaffold design)
"""

import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Pre-configured researchers from architecture doc ──────────────────────────

SEED_RESEARCHERS = [
    {
        "name":         "Jos Malda",
        "pubmed_query": "Malda J[au]",
        "orcid":        "0000-0002-1173-0329",
        "institution":  "UMC Utrecht",
        "tags":         ["biofabrication", "cartilage", "MEW", "volumetric bioprinting"],
        "cluster_group":"Dutch Biofab Network",
    },
    {
        "name":         "Riccardo Levato",
        "pubmed_query": "Levato R[au]",
        "orcid":        "0000-0002-0914-0064",
        "institution":  "UMC Utrecht",
        "tags":         ["GRACE", "volumetric bioprinting", "pancreas", "light-based"],
        "cluster_group":"Dutch Biofab Network",
    },
    {
        "name":         "Miguel Castilho",
        "pubmed_query": "Castilho M[au] AND biomaterial",
        "orcid":        "",
        "institution":  "TU/e Eindhoven",
        "tags":         ["Xolography", "scaffold design", "bone regeneration"],
        "cluster_group":"Dutch Biofab Network",
    },
]


class ResearcherTracker:
    """
    Manages researcher records and their paper feeds.
    All data persisted via data_manager.crud.
    """

    def __init__(self):
        from data_manager import get_db
        get_db()   # ensure DB is initialised

    # ── Seeding ───────────────────────────────────────────────────────────────

    def seed_if_empty(self) -> int:
        """
        Add the pre-configured key researchers if the table is empty.
        Returns number of researchers added.
        """
        from data_manager import crud
        existing = crud.list_researchers()
        if existing:
            return 0

        added = 0
        for r in SEED_RESEARCHERS:
            try:
                # Find or create group
                group_id = self._get_or_create_group(r["cluster_group"])
                crud.add_researcher(
                    name         = r["name"],
                    pubmed_query = r["pubmed_query"],
                    orcid        = r["orcid"],
                    institution  = r["institution"],
                    group_id     = group_id,
                    tags         = r["tags"],
                )
                added += 1
                logger.info(f"Seeded researcher: {r['name']}")
            except Exception as e:
                logger.error(f"Failed to seed {r['name']}: {e}")

        return added

    def _get_or_create_group(self, name: str) -> int:
        """Return group id, creating it if needed."""
        from data_manager import get_db
        with get_db().connection() as conn:
            row = conn.execute(
                "SELECT id FROM researcher_groups WHERE name=?", (name,)
            ).fetchone()
            if row:
                return row["id"]
            cur = conn.execute(
                "INSERT INTO researcher_groups (name) VALUES (?)", (name,)
            )
            return cur.lastrowid

    # ── Manual add ────────────────────────────────────────────────────────────

    def add_researcher(self, name: str, pubmed_query: str = "",
                       orcid: str = "", institution: str = "",
                       tags: List[str] = None,
                       group_name: str = "") -> int:
        """
        Add a single researcher manually.
        Auto-constructs pubmed_query from name if not provided.
        Returns researcher id.
        """
        from data_manager import crud

        if not pubmed_query:
            # Auto-build: "Smith J[au]"
            parts = name.strip().split()
            if len(parts) >= 2:
                pubmed_query = f"{parts[-1]} {parts[0][0]}[au]"
            else:
                pubmed_query = f"{name}[au]"

        group_id = None
        if group_name:
            group_id = self._get_or_create_group(group_name)

        rid = crud.add_researcher(
            name         = name,
            pubmed_query = pubmed_query,
            orcid        = orcid,
            institution  = institution,
            group_id     = group_id,
            tags         = tags or [],
        )
        logger.info(f"Added researcher: {name} (id={rid})")
        return rid

    # ── Paper sync ────────────────────────────────────────────────────────────

    def sync_researcher(self, researcher_id: int,
                        max_papers: int = 20,
                        year_from: int = 2020) -> List[Dict]:
        """
        Fetch latest papers for a researcher from PubMed.
        Saves papers to DB and updates researcher.last_synced.
        Returns list of new paper dicts.
        """
        from data_manager import crud
        from literature_engine.pubmed_crawler import PubMedCrawler

        researcher = crud.get_researcher(researcher_id)
        if not researcher:
            raise ValueError(f"Researcher id={researcher_id} not found")

        query = researcher.get("pubmed_query") or researcher["name"]
        logger.info(f"Syncing {researcher['name']} — query: {query}")

        crawler = PubMedCrawler()
        papers  = crawler.search_and_fetch(
            query       = query,
            max_results = max_papers,
            year_from   = year_from,
        )

        saved = 0
        for paper in papers:
            try:
                crud.upsert_paper(paper)
                saved += 1
            except Exception as e:
                logger.warning(f"Failed to save paper {paper.get('pmid')}: {e}")

        crud.update_researcher_sync(researcher_id, paper_count=len(papers))
        logger.info(f"Synced {saved} papers for {researcher['name']}")
        return papers

    def sync_all(self, max_papers: int = 20,
                 year_from: int = 2020,
                 progress_callback=None) -> Dict[str, int]:
        """
        Sync all tracked researchers.
        progress_callback(name, current, total) called per researcher.
        Returns dict of {researcher_name: paper_count}.
        """
        from data_manager import crud
        researchers = crud.list_researchers()
        results = {}

        for i, r in enumerate(researchers):
            if progress_callback:
                progress_callback(r["name"], i + 1, len(researchers))
            try:
                papers = self.sync_researcher(r["id"], max_papers, year_from)
                results[r["name"]] = len(papers)
            except Exception as e:
                logger.error(f"Sync failed for {r['name']}: {e}")
                results[r["name"]] = 0

        return results

    # ── Feed ─────────────────────────────────────────────────────────────────

    def get_feed(self, limit: int = 50,
                 researcher_id: Optional[int] = None) -> List[Dict]:
        """
        Get recent papers from tracked researchers, newest first.
        Optionally filter to a single researcher.
        """
        from data_manager import get_db
        with get_db().connection() as conn:
            if researcher_id:
                rows = conn.execute(
                    """
                    SELECT p.*, r.name as researcher_name
                    FROM papers p
                    JOIN researchers r ON (
                        p.authors_json LIKE '%' || r.name || '%'
                    )
                    WHERE r.id = ?
                    ORDER BY p.year DESC, p.cached_date DESC
                    LIMIT ?
                    """,
                    (researcher_id, limit)
                ).fetchall()
            else:
                # All papers from any tracked researcher
                rows = conn.execute(
                    """
                    SELECT DISTINCT p.*
                    FROM papers p
                    JOIN researchers r ON (
                        p.authors_json LIKE '%' || r.name || '%'
                    )
                    ORDER BY p.year DESC, p.cached_date DESC
                    LIMIT ?
                    """,
                    (limit,)
                ).fetchall()

        import json
        results = []
        for row in rows:
            d = dict(row)
            d["authors"] = json.loads(d.get("authors_json") or "[]")
            d["keywords"] = json.loads(d.get("keywords_json") or "[]")
            results.append(d)
        return results

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict:
        """Summary stats for the status bar."""
        from data_manager import crud, get_db
        researchers = crud.list_researchers()
        with get_db().connection() as conn:
            total_papers = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
        return {
            "researcher_count": len(researchers),
            "total_papers":     total_papers,
        }