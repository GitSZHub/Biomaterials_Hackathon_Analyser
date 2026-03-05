"""
CRUD helpers — one clean function per common operation.
Every module imports from here instead of writing raw SQL.
All functions accept/return plain dicts or lists of dicts.
JSON columns are automatically serialised/deserialised.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from .database import get_db

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _row_to_dict(row) -> Dict:
    """Convert sqlite3.Row to plain dict."""
    return dict(row) if row else {}


def _rows_to_dicts(rows) -> List[Dict]:
    return [_row_to_dict(r) for r in rows]


def _j(value) -> Optional[str]:
    """Serialise to JSON string, None-safe."""
    return json.dumps(value) if value is not None else None


def _dj(value: Optional[str]) -> Any:
    """Deserialise JSON string, None-safe."""
    if value is None:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


def _deserialise_json_fields(record: Dict, json_fields: List[str]) -> Dict:
    """Deserialise all known JSON columns in a record dict."""
    for field in json_fields:
        if field in record:
            record[field] = _dj(record[field])
    return record


# ──────────────────────────────────────────────────────────────────────────────
# Projects
# ──────────────────────────────────────────────────────────────────────────────

_PROJECT_JSON = ["resources_json", "markets"]


def create_project(name: str, **kwargs) -> int:
    """Insert a new project, return its id."""
    db = get_db()
    with db.connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO projects (name, target_tissue, clinical_indication,
                resources_json, regulatory_class, markets)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                kwargs.get("target_tissue"),
                kwargs.get("clinical_indication"),
                _j(kwargs.get("resources")),
                kwargs.get("regulatory_class"),
                _j(kwargs.get("markets")),
            ),
        )
        return cur.lastrowid


def get_project(project_id: int) -> Dict:
    db = get_db()
    with db.connection() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    return _deserialise_json_fields(_row_to_dict(row), _PROJECT_JSON)


def list_projects() -> List[Dict]:
    db = get_db()
    with db.connection() as conn:
        rows = conn.execute("SELECT * FROM projects ORDER BY last_modified DESC").fetchall()
    return [_deserialise_json_fields(_row_to_dict(r), _PROJECT_JSON) for r in rows]


def update_project(project_id: int, **kwargs) -> None:
    db = get_db()
    with db.connection() as conn:
        conn.execute(
            "UPDATE projects SET last_modified=CURRENT_TIMESTAMP WHERE id=?",
            (project_id,),
        )
        for key, value in kwargs.items():
            if key in ("resources", "markets"):
                value = _j(value)
                key = key + "_json"
            conn.execute(
                f"UPDATE projects SET {key}=? WHERE id=?", (value, project_id)
            )


# ──────────────────────────────────────────────────────────────────────────────
# Papers
# ──────────────────────────────────────────────────────────────────────────────

_PAPER_JSON = ["authors_json", "keywords_json"]


def upsert_paper(paper: Dict) -> str:
    """
    Insert or update a paper record. Key is pmid.
    Accepts the dict returned by PubMedCrawler.get_paper_details().
    Returns pmid.
    """
    db = get_db()
    pmid = str(paper.get("pmid", ""))
    if not pmid:
        raise ValueError("Paper must have a pmid")

    # Parse year from publication_date if present
    year = paper.get("year")
    if year is None and paper.get("publication_date"):
        try:
            year = int(str(paper["publication_date"])[:4])
        except (ValueError, TypeError):
            year = None

    with db.connection() as conn:
        conn.execute(
            """
            INSERT INTO papers
                (pmid, doi, title, authors_json, journal, year,
                 abstract, keywords_json, pdf_path, full_text_extracted)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(pmid) DO UPDATE SET
                doi=excluded.doi,
                title=excluded.title,
                authors_json=excluded.authors_json,
                journal=excluded.journal,
                year=excluded.year,
                abstract=excluded.abstract,
                keywords_json=excluded.keywords_json
            """,
            (
                pmid,
                paper.get("doi"),
                paper.get("title", ""),
                _j(paper.get("authors", [])),
                paper.get("journal"),
                year,
                paper.get("abstract"),
                _j(paper.get("keywords", [])),
                paper.get("pdf_path"),
                int(paper.get("full_text_extracted", False)),
            ),
        )
    return pmid


def get_paper(pmid: str) -> Dict:
    db = get_db()
    with db.connection() as conn:
        row = conn.execute("SELECT * FROM papers WHERE pmid=?", (pmid,)).fetchone()
    return _deserialise_json_fields(_row_to_dict(row), _PAPER_JSON)


def search_papers_local(query: str, limit: int = 100) -> List[Dict]:
    """Full-text search across title + abstract in local cache."""
    db = get_db()
    like = f"%{query}%"
    with db.connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM papers
            WHERE title LIKE ? OR abstract LIKE ?
            ORDER BY year DESC
            LIMIT ?
            """,
            (like, like, limit),
        ).fetchall()
    return [_deserialise_json_fields(_row_to_dict(r), _PAPER_JSON) for r in rows]


def count_papers() -> int:
    db = get_db()
    with db.connection() as conn:
        return conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]


# ──────────────────────────────────────────────────────────────────────────────
# Paper annotations
# ──────────────────────────────────────────────────────────────────────────────

def add_annotation(paper_id: str, project_id: int, annotation_type: str,
                   content: Any, confidence_tier: int = 2,
                   human_verified: bool = False,
                   linked_material_id: Optional[int] = None,
                   linked_researcher_id: Optional[int] = None) -> int:
    db = get_db()
    with db.connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO paper_annotations
                (paper_id, project_id, annotation_type, content_json,
                 linked_material_id, linked_researcher_id,
                 confidence_tier, human_verified)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (paper_id, project_id, annotation_type, _j(content),
             linked_material_id, linked_researcher_id,
             confidence_tier, int(human_verified)),
        )
        return cur.lastrowid


def get_annotations(paper_id: str, project_id: Optional[int] = None) -> List[Dict]:
    db = get_db()
    with db.connection() as conn:
        if project_id:
            rows = conn.execute(
                "SELECT * FROM paper_annotations WHERE paper_id=? AND project_id=?",
                (paper_id, project_id),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM paper_annotations WHERE paper_id=?", (paper_id,)
            ).fetchall()
    results = _rows_to_dicts(rows)
    for r in results:
        r["content"] = _dj(r.get("content_json"))
    return results


# ──────────────────────────────────────────────────────────────────────────────
# Researchers
# ──────────────────────────────────────────────────────────────────────────────

_RESEARCHER_JSON = ["tags_json"]


def add_researcher(name: str, **kwargs) -> int:
    db = get_db()
    with db.connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO researchers
                (name, orcid, pubmed_query, institution,
                 group_id, google_scholar_id, tags_json)
            VALUES (?,?,?,?,?,?,?)
            """,
            (
                name,
                kwargs.get("orcid"),
                kwargs.get("pubmed_query"),
                kwargs.get("institution"),
                kwargs.get("group_id"),
                kwargs.get("google_scholar_id"),
                _j(kwargs.get("tags", [])),
            ),
        )
        return cur.lastrowid


def get_researcher(researcher_id: int) -> Dict:
    db = get_db()
    with db.connection() as conn:
        row = conn.execute(
            "SELECT * FROM researchers WHERE id=?", (researcher_id,)
        ).fetchone()
    return _deserialise_json_fields(_row_to_dict(row), _RESEARCHER_JSON)


def list_researchers(group_id: Optional[int] = None) -> List[Dict]:
    db = get_db()
    with db.connection() as conn:
        if group_id:
            rows = conn.execute(
                "SELECT * FROM researchers WHERE group_id=? ORDER BY name", (group_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM researchers ORDER BY name"
            ).fetchall()
    return [_deserialise_json_fields(_row_to_dict(r), _RESEARCHER_JSON) for r in rows]


def update_researcher_sync(researcher_id: int, paper_count: int) -> None:
    db = get_db()
    with db.connection() as conn:
        conn.execute(
            "UPDATE researchers SET last_synced=CURRENT_TIMESTAMP, paper_count=? WHERE id=?",
            (paper_count, researcher_id),
        )


def add_co_authorship(id_a: int, id_b: int, last_paper_year: Optional[int] = None) -> None:
    """Increment co-authorship count between two researchers."""
    # Always store with lower id first for deduplication
    a, b = min(id_a, id_b), max(id_a, id_b)
    db = get_db()
    with db.connection() as conn:
        conn.execute(
            """
            INSERT INTO co_authorship (researcher_id_a, researcher_id_b, paper_count, last_paper_year)
            VALUES (?,?,1,?)
            ON CONFLICT(researcher_id_a, researcher_id_b) DO UPDATE SET
                paper_count=paper_count+1,
                last_paper_year=MAX(last_paper_year, excluded.last_paper_year)
            """,
            (a, b, last_paper_year),
        )


# ──────────────────────────────────────────────────────────────────────────────
# Materials
# ──────────────────────────────────────────────────────────────────────────────

_MATERIAL_JSON = ["properties_json", "biocompat_scores_json", "fabrication_compat_json"]


def upsert_material(name: str, material_class: str, **kwargs) -> int:
    db = get_db()
    with db.connection() as conn:
        # Check if exists
        row = conn.execute(
            "SELECT id FROM materials WHERE name=? AND class=?", (name, material_class)
        ).fetchone()
        if row:
            mid = row["id"]
            conn.execute(
                """
                UPDATE materials SET
                    subclass=?, properties_json=?, biocompat_scores_json=?,
                    fabrication_compat_json=?, last_reviewed=CURRENT_TIMESTAMP,
                    ai_generated=?, human_verified=?
                WHERE id=?
                """,
                (
                    kwargs.get("subclass"),
                    _j(kwargs.get("properties")),
                    _j(kwargs.get("biocompat_scores")),
                    _j(kwargs.get("fabrication_compat")),
                    int(kwargs.get("ai_generated", True)),
                    int(kwargs.get("human_verified", False)),
                    mid,
                ),
            )
            return mid
        else:
            cur = conn.execute(
                """
                INSERT INTO materials
                    (name, class, subclass, properties_json, biocompat_scores_json,
                     fabrication_compat_json, ai_generated, human_verified)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    name, material_class,
                    kwargs.get("subclass"),
                    _j(kwargs.get("properties")),
                    _j(kwargs.get("biocompat_scores")),
                    _j(kwargs.get("fabrication_compat")),
                    int(kwargs.get("ai_generated", True)),
                    int(kwargs.get("human_verified", False)),
                ),
            )
            return cur.lastrowid


def get_material(material_id: int) -> Dict:
    db = get_db()
    with db.connection() as conn:
        row = conn.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
    return _deserialise_json_fields(_row_to_dict(row), _MATERIAL_JSON)


def list_materials(material_class: Optional[str] = None) -> List[Dict]:
    db = get_db()
    with db.connection() as conn:
        if material_class:
            rows = conn.execute(
                "SELECT * FROM materials WHERE class=? ORDER BY name", (material_class,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM materials ORDER BY class, name").fetchall()
    return [_deserialise_json_fields(_row_to_dict(r), _MATERIAL_JSON) for r in rows]


# ──────────────────────────────────────────────────────────────────────────────
# Regulatory assessments
# ──────────────────────────────────────────────────────────────────────────────

_REG_JSON = ["required_tests_json", "missing_evidence_json"]


def save_regulatory_assessment(project_id: int, material: str, scenario: str,
                                device_class: str, contact_type: str,
                                duration: str, required_tests: List,
                                missing_evidence: Optional[List] = None,
                                biocompat_score: Optional[float] = None,
                                combination_product: bool = False,
                                atmp_flag: bool = False) -> int:
    db = get_db()
    with db.connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO regulatory_assessments
                (project_id, material, scenario, device_class, contact_type,
                 duration, required_tests_json, biocompat_score,
                 missing_evidence_json, combination_product, atmp_flag)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                project_id, material, scenario, device_class, contact_type,
                duration, _j(required_tests), biocompat_score,
                _j(missing_evidence or []),
                int(combination_product), int(atmp_flag),
            ),
        )
        return cur.lastrowid


def get_regulatory_assessments(project_id: int) -> List[Dict]:
    db = get_db()
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT * FROM regulatory_assessments WHERE project_id=? ORDER BY created_date DESC",
            (project_id,),
        ).fetchall()
    return [_deserialise_json_fields(_row_to_dict(r), _REG_JSON) for r in rows]


# ──────────────────────────────────────────────────────────────────────────────
# Experimental roadmaps
# ──────────────────────────────────────────────────────────────────────────────

def save_roadmap(project_id: int, material: str, target_tissue: str,
                 steps: List, dbtl_cycle: int = 1) -> int:
    db = get_db()
    # Auto-increment version
    with db.connection() as conn:
        row = conn.execute(
            "SELECT MAX(version) as v FROM experimental_roadmaps WHERE project_id=?",
            (project_id,),
        ).fetchone()
        version = (row["v"] or 0) + 1
        cur = conn.execute(
            """
            INSERT INTO experimental_roadmaps
                (project_id, material, target_tissue, steps_json, dbtl_cycle, version)
            VALUES (?,?,?,?,?,?)
            """,
            (project_id, material, target_tissue, _j(steps), dbtl_cycle, version),
        )
        return cur.lastrowid


def get_roadmaps(project_id: int) -> List[Dict]:
    db = get_db()
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT * FROM experimental_roadmaps WHERE project_id=? ORDER BY version DESC",
            (project_id,),
        ).fetchall()
    results = _rows_to_dicts(rows)
    for r in results:
        r["steps"] = _dj(r.get("steps_json"))
    return results


# ──────────────────────────────────────────────────────────────────────────────
# Briefings
# ──────────────────────────────────────────────────────────────────────────────

def save_briefing(project_id: int, mode: str, content: str,
                  modules_included: List, prompt_used: str) -> int:
    db = get_db()
    with db.connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO briefings
                (project_id, mode, content, modules_included_json, prompt_used)
            VALUES (?,?,?,?,?)
            """,
            (project_id, mode, content, _j(modules_included), prompt_used),
        )
        return cur.lastrowid


def list_briefings(project_id: int) -> List[Dict]:
    db = get_db()
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT id, project_id, mode, created_date FROM briefings WHERE project_id=? ORDER BY created_date DESC",
            (project_id,),
        ).fetchall()
    return _rows_to_dicts(rows)


def get_briefing(briefing_id: int) -> Dict:
    db = get_db()
    with db.connection() as conn:
        row = conn.execute("SELECT * FROM briefings WHERE id=?", (briefing_id,)).fetchone()
    r = _row_to_dict(row)
    r["modules_included"] = _dj(r.get("modules_included_json"))
    return r


# ──────────────────────────────────────────────────────────────────────────────
# Drug cache
# ──────────────────────────────────────────────────────────────────────────────

def cache_drug(compound_id: str, source: str, name: str, data: Dict) -> None:
    db = get_db()
    with db.connection() as conn:
        conn.execute(
            """
            INSERT INTO drug_cache (compound_id, source, name, data_json)
            VALUES (?,?,?,?)
            ON CONFLICT(compound_id, source) DO UPDATE SET
                name=excluded.name,
                data_json=excluded.data_json,
                cached_date=CURRENT_TIMESTAMP
            """,
            (compound_id, source, name, _j(data)),
        )


def get_cached_drug(compound_id: str, source: str) -> Optional[Dict]:
    db = get_db()
    with db.connection() as conn:
        row = conn.execute(
            "SELECT * FROM drug_cache WHERE compound_id=? AND source=?",
            (compound_id, source),
        ).fetchone()
    if not row:
        return None
    r = _row_to_dict(row)
    r["data"] = _dj(r.get("data_json"))
    return r


# ──────────────────────────────────────────────────────────────────────────────
# SWOT
# ──────────────────────────────────────────────────────────────────────────────

_SWOT_JSON = ["strengths_json", "weaknesses_json", "opportunities_json", "threats_json"]


def save_swot(project_id: int, strengths: List, weaknesses: List,
              opportunities: List, threats: List,
              strategic_insight: str = "") -> int:
    db = get_db()
    with db.connection() as conn:
        row = conn.execute(
            "SELECT MAX(version) as v FROM swot_analyses WHERE project_id=?",
            (project_id,),
        ).fetchone()
        version = (row["v"] or 0) + 1
        cur = conn.execute(
            """
            INSERT INTO swot_analyses
                (project_id, version, strengths_json, weaknesses_json,
                 opportunities_json, threats_json, strategic_insight)
            VALUES (?,?,?,?,?,?,?)
            """,
            (project_id, version,
             _j(strengths), _j(weaknesses), _j(opportunities), _j(threats),
             strategic_insight),
        )
        return cur.lastrowid


def get_swot(project_id: int, version: Optional[int] = None) -> Optional[Dict]:
    db = get_db()
    with db.connection() as conn:
        if version:
            row = conn.execute(
                "SELECT * FROM swot_analyses WHERE project_id=? AND version=?",
                (project_id, version),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM swot_analyses WHERE project_id=? ORDER BY version DESC LIMIT 1",
                (project_id,),
            ).fetchone()
    return _deserialise_json_fields(_row_to_dict(row), _SWOT_JSON) if row else None


# ──────────────────────────────────────────────────────────────────────────────
# GEO datasets
# ──────────────────────────────────────────────────────────────────────────────

def upsert_geo_dataset(gse_id: str, title: str, organism: str, tissue: str,
                        experiment_type: str, file_path: Optional[str] = None,
                        culture_condition: Optional[str] = None) -> None:
    db = get_db()
    with db.connection() as conn:
        conn.execute(
            """
            INSERT INTO geo_datasets
                (gse_id, title, organism, tissue, experiment_type, file_path,
                 culture_condition, cached_date)
            VALUES (?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(gse_id) DO UPDATE SET
                title=excluded.title,
                file_path=excluded.file_path,
                cached_date=CURRENT_TIMESTAMP
            """,
            (gse_id, title, organism, tissue, experiment_type, file_path, culture_condition),
        )


def list_geo_datasets(tissue: Optional[str] = None) -> List[Dict]:
    db = get_db()
    with db.connection() as conn:
        if tissue:
            rows = conn.execute(
                "SELECT * FROM geo_datasets WHERE tissue LIKE ? ORDER BY cached_date DESC",
                (f"%{tissue}%",),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM geo_datasets ORDER BY cached_date DESC"
            ).fetchall()
    return _rows_to_dicts(rows)


# ──────────────────────────────────────────────────────────────────────────────
# Stakeholders
# ──────────────────────────────────────────────────────────────────────────────

def save_stakeholder_analysis(project_id: int, stakeholders: List, matrix: Dict) -> int:
    db = get_db()
    with db.connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO stakeholder_analyses (project_id, stakeholders_json, matrix_json)
            VALUES (?,?,?)
            """,
            (project_id, _j(stakeholders), _j(matrix)),
        )
        return cur.lastrowid


def get_stakeholder_analysis(project_id: int) -> Optional[Dict]:
    db = get_db()
    with db.connection() as conn:
        row = conn.execute(
            "SELECT * FROM stakeholder_analyses WHERE project_id=? ORDER BY created_date DESC LIMIT 1",
            (project_id,),
        ).fetchone()
    if not row:
        return None
    r = _row_to_dict(row)
    r["stakeholders"] = _dj(r.get("stakeholders_json"))
    r["matrix"] = _dj(r.get("matrix_json"))
    return r