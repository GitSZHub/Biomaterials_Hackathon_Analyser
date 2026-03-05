"""
SQLite schema for the Biomaterials Hackathon Analyser.
Call create_all_tables(conn) once on startup.
"""

SCHEMA_VERSION = 3

_DDL = [
    "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)",

    """CREATE TABLE IF NOT EXISTS project (
        id              INTEGER PRIMARY KEY,
        name            TEXT    NOT NULL,
        description     TEXT    DEFAULT '',
        target_tissue   TEXT    DEFAULT '',
        regulatory_aim  TEXT    DEFAULT '',
        budget_tier     TEXT    DEFAULT '',
        timeline_months INTEGER DEFAULT 0,
        focus_keywords  TEXT    DEFAULT '',
        created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
        updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
    )""",

    """CREATE TABLE IF NOT EXISTS material (
        id              INTEGER PRIMARY KEY,
        name            TEXT    NOT NULL UNIQUE,
        common_names    TEXT    DEFAULT '',
        material_class  TEXT    DEFAULT '',
        subclass        TEXT    DEFAULT '',
        taxonomy_path   TEXT    DEFAULT '',
        branch_type     TEXT    DEFAULT 'monitoring',
        knowledge_card  TEXT    DEFAULT '',
        card_verified   INTEGER DEFAULT 0,
        card_updated_at TEXT    DEFAULT '',
        smiles          TEXT    DEFAULT '',
        cas_number      TEXT    DEFAULT '',
        created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
    )""",

    """CREATE TABLE IF NOT EXISTS project_material (
        id          INTEGER PRIMARY KEY,
        project_id  INTEGER NOT NULL REFERENCES project(id) ON DELETE CASCADE,
        material_id INTEGER NOT NULL REFERENCES material(id) ON DELETE CASCADE,
        role        TEXT    DEFAULT 'primary',
        UNIQUE(project_id, material_id)
    )""",

    """CREATE TABLE IF NOT EXISTS paper (
        id               INTEGER PRIMARY KEY,
        pmid             TEXT    UNIQUE,
        doi              TEXT    UNIQUE,
        title            TEXT    NOT NULL DEFAULT '',
        journal          TEXT    DEFAULT '',
        year             INTEGER,
        volume           TEXT    DEFAULT '',
        issue            TEXT    DEFAULT '',
        pages            TEXT    DEFAULT '',
        abstract         TEXT    DEFAULT '',
        full_text_path   TEXT    DEFAULT '',
        ai_summary       TEXT    DEFAULT '',
        summary_verified INTEGER DEFAULT 0,
        briefing_flag    INTEGER DEFAULT 0,
        tags             TEXT    DEFAULT '',
        created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
        updated_at       TEXT    NOT NULL DEFAULT (datetime('now'))
    )""",

    """CREATE TABLE IF NOT EXISTS paper_author (
        id               INTEGER PRIMARY KEY,
        paper_id         INTEGER NOT NULL REFERENCES paper(id) ON DELETE CASCADE,
        name             TEXT    NOT NULL,
        position         INTEGER DEFAULT 0,
        is_corresponding INTEGER DEFAULT 0
    )""",

    """CREATE TABLE IF NOT EXISTS paper_annotation (
        id         INTEGER PRIMARY KEY,
        paper_id   INTEGER NOT NULL REFERENCES paper(id) ON DELETE CASCADE,
        project_id INTEGER REFERENCES project(id) ON DELETE SET NULL,
        note       TEXT    NOT NULL DEFAULT '',
        tag        TEXT    DEFAULT '',
        created_at TEXT    NOT NULL DEFAULT (datetime('now'))
    )""",

    """CREATE TABLE IF NOT EXISTS paper_fact (
        id            INTEGER PRIMARY KEY,
        paper_id      INTEGER NOT NULL REFERENCES paper(id) ON DELETE CASCADE,
        material_id   INTEGER REFERENCES material(id) ON DELETE SET NULL,
        cell_model    TEXT    DEFAULT '',
        organism      TEXT    DEFAULT '',
        concentration TEXT    DEFAULT '',
        viability_pct REAL,
        stiffness_kpa REAL,
        key_finding   TEXT    DEFAULT '',
        limitations   TEXT    DEFAULT '',
        confidence    TEXT    DEFAULT 'ai_extracted',
        verified_at   TEXT    DEFAULT '',
        created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
    )""",

    """CREATE TABLE IF NOT EXISTS material_property (
        id              INTEGER PRIMARY KEY,
        material_id     INTEGER NOT NULL REFERENCES material(id) ON DELETE CASCADE,
        property_name   TEXT    NOT NULL,
        value_numeric   REAL,
        value_text      TEXT    DEFAULT '',
        unit            TEXT    DEFAULT '',
        condition       TEXT    DEFAULT '',
        source_paper_id INTEGER REFERENCES paper(id) ON DELETE SET NULL,
        confidence      TEXT    DEFAULT 'literature',
        created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
    )""",

    """CREATE TABLE IF NOT EXISTS researcher (
        id                INTEGER PRIMARY KEY,
        name              TEXT    NOT NULL,
        pubmed_query      TEXT    DEFAULT '',
        orcid             TEXT    DEFAULT '',
        institution       TEXT    DEFAULT '',
        google_scholar_id TEXT    DEFAULT '',
        tags              TEXT    DEFAULT '',
        cluster_group     TEXT    DEFAULT '',
        paper_count       INTEGER DEFAULT 0,
        added_at          TEXT    NOT NULL DEFAULT (datetime('now')),
        last_synced       TEXT    DEFAULT ''
    )""",

    """CREATE TABLE IF NOT EXISTS researcher_paper (
        id            INTEGER PRIMARY KEY,
        researcher_id INTEGER NOT NULL REFERENCES researcher(id) ON DELETE CASCADE,
        paper_id      INTEGER NOT NULL REFERENCES paper(id) ON DELETE CASCADE,
        role          TEXT    DEFAULT 'author',
        UNIQUE(researcher_id, paper_id)
    )""",

    """CREATE TABLE IF NOT EXISTS co_author_edge (
        id            INTEGER PRIMARY KEY,
        researcher_a  INTEGER NOT NULL REFERENCES researcher(id) ON DELETE CASCADE,
        researcher_b  INTEGER NOT NULL REFERENCES researcher(id) ON DELETE CASCADE,
        shared_papers INTEGER DEFAULT 1,
        first_collab  INTEGER,
        last_collab   INTEGER,
        UNIQUE(researcher_a, researcher_b)
    )""",

    """CREATE TABLE IF NOT EXISTS briefing_item (
        id            INTEGER PRIMARY KEY,
        project_id    INTEGER NOT NULL REFERENCES project(id) ON DELETE CASCADE,
        source_type   TEXT    NOT NULL,
        source_id     INTEGER,
        content_md    TEXT    NOT NULL DEFAULT '',
        section_hint  TEXT    DEFAULT '',
        included      INTEGER DEFAULT 1,
        display_order INTEGER DEFAULT 0,
        added_at      TEXT    NOT NULL DEFAULT (datetime('now'))
    )""",

    """CREATE TABLE IF NOT EXISTS api_cache (
        id          INTEGER PRIMARY KEY,
        cache_key   TEXT    NOT NULL UNIQUE,
        endpoint    TEXT    NOT NULL,
        response    TEXT    NOT NULL,
        cached_at   TEXT    NOT NULL DEFAULT (datetime('now')),
        expires_at  TEXT    NOT NULL
    )""",

    "CREATE INDEX IF NOT EXISTS idx_paper_pmid        ON paper(pmid)",
    "CREATE INDEX IF NOT EXISTS idx_paper_doi         ON paper(doi)",
    "CREATE INDEX IF NOT EXISTS idx_paper_year        ON paper(year)",
    "CREATE INDEX IF NOT EXISTS idx_paper_briefing    ON paper(briefing_flag)",
    "CREATE INDEX IF NOT EXISTS idx_paper_fact_mat    ON paper_fact(material_id)",
    "CREATE INDEX IF NOT EXISTS idx_mat_class         ON material(material_class)",
    "CREATE INDEX IF NOT EXISTS idx_mat_taxonomy      ON material(taxonomy_path)",
    "CREATE INDEX IF NOT EXISTS idx_researcher_orcid  ON researcher(orcid)",
    "CREATE INDEX IF NOT EXISTS idx_briefing_project  ON briefing_item(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_cache_key         ON api_cache(cache_key)",
    "CREATE INDEX IF NOT EXISTS idx_cache_expires     ON api_cache(expires_at)",
]


def create_all_tables(conn) -> None:
    """Create all tables and indexes. Safe to call on every startup."""
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    for stmt in _DDL:
        conn.execute(stmt)
    row = conn.execute("SELECT version FROM schema_version").fetchone()
    if row is None:
        conn.execute("INSERT INTO schema_version VALUES (?)", (SCHEMA_VERSION,))
    elif row[0] < SCHEMA_VERSION:
        conn.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION,))
    conn.commit()
