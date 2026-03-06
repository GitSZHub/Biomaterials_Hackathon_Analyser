"""
Database Manager — SQLite schema and connection handling
All tables defined from ARCHITECTURE_DECISIONS.md
Single source of truth for the entire application's local storage.
"""

import sqlite3
import logging
from pathlib import Path
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)

# Default DB path — can be overridden by config
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "biomaterials.db"


def get_db_path() -> Path:
    """Return DB path, creating parent directories if needed."""
    try:
        from utils.config import config
        path = Path(config.database_path)
    except Exception:
        path = DEFAULT_DB_PATH

    path.parent.mkdir(parents=True, exist_ok=True)
    return path


class DatabaseManager:
    """
    Central SQLite manager.
    Use as a context manager or call get_connection() directly.

    Usage:
        db = DatabaseManager()
        with db.connection() as conn:
            conn.execute(...)
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or get_db_path()
        self._initialised = False

    def initialise(self):
        """Create all tables if they don't exist. Safe to call multiple times."""
        if self._initialised:
            return
        with self.connection() as conn:
            self._create_all_tables(conn)
        self._initialised = True
        logger.info(f"Database initialised at {self.db_path}")

    @contextmanager
    def connection(self):
        """Yield a SQLite connection with row_factory and WAL mode enabled."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row          # Access columns by name
        conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent reads
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Schema creation
    # ------------------------------------------------------------------

    def _create_all_tables(self, conn: sqlite3.Connection):
        """Create every table defined in the architecture document."""

        statements = [

            # ── Projects ──────────────────────────────────────────────
            # Columns aligned with ProjectContext dataclass in project_context.py
            """
            CREATE TABLE IF NOT EXISTS projects (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                name                TEXT NOT NULL,
                description         TEXT DEFAULT '',
                target_tissue       TEXT DEFAULT '',
                clinical_indication TEXT DEFAULT '',
                regulatory_aim      TEXT DEFAULT '',   -- e.g. "CE Class IIb", "FDA 510(k)", "ATMP"
                regulatory_class    TEXT DEFAULT '',   -- I / II / III / ATMP / TBD
                budget_tier         TEXT DEFAULT '',   -- academic | startup | industry
                timeline_months     INTEGER DEFAULT 0,
                focus_keywords      TEXT DEFAULT '',   -- comma-separated
                resources_json      TEXT,              -- JSON: available equipment/budget flags
                markets             TEXT,              -- JSON list of target markets
                created             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_modified       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,

            # ── Literature ────────────────────────────────────────────
            """
            CREATE TABLE IF NOT EXISTS papers (
                pmid            TEXT PRIMARY KEY,
                doi             TEXT,
                title           TEXT NOT NULL,
                authors_json    TEXT,           -- JSON list of author strings
                journal         TEXT,
                year            INTEGER,
                abstract        TEXT,
                keywords_json   TEXT,           -- JSON list
                pdf_path        TEXT,           -- local file path if downloaded
                full_text_extracted INTEGER DEFAULT 0,  -- boolean
                cached_date     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS paper_annotations (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id            TEXT REFERENCES papers(pmid),
                project_id          INTEGER REFERENCES projects(id),
                annotation_type     TEXT,       -- 'extracted_fact' | 'manual' | 'briefing_flag'
                content_json        TEXT,       -- structured extraction or free text
                linked_material_id  INTEGER,    -- FK to materials
                linked_researcher_id INTEGER,   -- FK to researchers
                confidence_tier     INTEGER,    -- 1-5 (see arch doc)
                human_verified      INTEGER DEFAULT 0,
                created_date        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,

            # ── Researcher Network ────────────────────────────────────
            """
            CREATE TABLE IF NOT EXISTS researcher_groups (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                description TEXT,
                project_id  INTEGER REFERENCES projects(id)
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS researchers (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                name                TEXT NOT NULL,
                orcid               TEXT,
                pubmed_query        TEXT,       -- e.g. "Malda J[au]"
                institution         TEXT,
                group_id            INTEGER REFERENCES researcher_groups(id),
                google_scholar_id   TEXT,
                tags_json           TEXT,       -- JSON list of topic tags
                added_date          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_synced         TIMESTAMP,
                paper_count         INTEGER DEFAULT 0
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS co_authorship (
                researcher_id_a INTEGER REFERENCES researchers(id),
                researcher_id_b INTEGER REFERENCES researchers(id),
                paper_count     INTEGER DEFAULT 1,
                last_paper_year INTEGER,
                PRIMARY KEY (researcher_id_a, researcher_id_b)
            )
            """,

            # ── Materials ─────────────────────────────────────────────
            """
            CREATE TABLE IF NOT EXISTS materials (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                name                    TEXT NOT NULL,
                class                   TEXT,       -- Metals | Polymers | Ceramics | ...
                subclass                TEXT,
                properties_json         TEXT,       -- JSON: stiffness, degradation, etc.
                biocompat_scores_json   TEXT,       -- JSON: confidence-tiered scores per contact type
                fabrication_compat_json TEXT,       -- JSON: compatible fabrication methods
                last_reviewed           TIMESTAMP,
                ai_generated            INTEGER DEFAULT 1,
                human_verified          INTEGER DEFAULT 0
            )
            """,

            # ── GEO / Transcriptomics ─────────────────────────────────
            """
            CREATE TABLE IF NOT EXISTS geo_datasets (
                gse_id              TEXT PRIMARY KEY,
                title               TEXT,
                organism            TEXT,
                tissue              TEXT,
                experiment_type     TEXT,       -- bulk_rnaseq | scrnaseq | microarray
                culture_condition   TEXT,       -- static | perfused | spinner
                file_path           TEXT,
                cached_date         TIMESTAMP,
                analysis_complete   INTEGER DEFAULT 0
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS geo_analyses (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id          INTEGER REFERENCES projects(id),
                gse_id              TEXT REFERENCES geo_datasets(gse_id),
                material            TEXT,
                baseline            TEXT,
                deg_count           INTEGER,
                results_path        TEXT,
                top_pathways_json   TEXT,
                created_date        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,

            # ── Metabolomics ──────────────────────────────────────────
            """
            CREATE TABLE IF NOT EXISTS metabolomics_datasets (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                source              TEXT,       -- MetaboLights | Metabolomics Workbench
                accession           TEXT,
                title               TEXT,
                organism            TEXT,
                tissue              TEXT,
                platform            TEXT,       -- GC-MS | LC-MS | NMR
                file_path           TEXT,
                cached_date         TIMESTAMP,
                culture_condition   TEXT
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS metabolomics_analyses (
                id                              INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id                      INTEGER REFERENCES projects(id),
                dataset_id                      INTEGER REFERENCES metabolomics_datasets(id),
                material                        TEXT,
                differential_metabolites_json   TEXT,
                pathway_enrichment_json         TEXT,
                created_date                    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,

            # ── Proteomics ────────────────────────────────────────────
            """
            CREATE TABLE IF NOT EXISTS proteomics_datasets (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                source                  TEXT,       -- PRIDE | manual
                accession               TEXT,
                title                   TEXT,
                organism                TEXT,
                tissue                  TEXT,
                acquisition_mode        TEXT,       -- DDA | DIA
                quantification_method   TEXT,       -- LFQ | TMT | SILAC
                file_path               TEXT,
                cached_date             TIMESTAMP
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS proteomics_analyses (
                id                                  INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id                          INTEGER REFERENCES projects(id),
                dataset_id                          INTEGER REFERENCES proteomics_datasets(id),
                material                            TEXT,
                differentially_expressed_proteins_json TEXT,
                protein_corona_json                 TEXT,
                phosphosite_hits_json               TEXT,
                ppi_network_json                    TEXT,
                created_date                        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,

            # ── Flow Cytometry ────────────────────────────────────────
            """
            CREATE TABLE IF NOT EXISTS flow_panels (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT,
                cell_type       TEXT,
                markers_json    TEXT,
                fluorochromes_json TEXT,
                instrument      TEXT,
                acquisition_mode TEXT,   -- conventional | spectral | mass | imaging
                project_id      INTEGER REFERENCES projects(id),
                created_date    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS flow_analyses (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id              INTEGER REFERENCES projects(id),
                panel_id                INTEGER REFERENCES flow_panels(id),
                gating_strategy_json    TEXT,
                population_stats_json   TEXT,
                phospho_data_json       TEXT,
                linked_experiment_id    INTEGER,
                created_date            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,

            # ── Drug Delivery ─────────────────────────────────────────
            """
            CREATE TABLE IF NOT EXISTS drug_cache (
                compound_id TEXT,
                source      TEXT,       -- PubChem | ChEMBL | DrugBank
                name        TEXT,
                data_json   TEXT,
                cached_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (compound_id, source)
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS drug_analyses (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id              INTEGER REFERENCES projects(id),
                compound                TEXT,
                material                TEXT,
                pk_level                INTEGER,    -- 1 | 2 | 3 | 4
                pk_params_json          TEXT,
                release_curve_data      TEXT,       -- JSON array of [time, conc] points
                combination_product_flag INTEGER DEFAULT 0,
                created_date            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,

            # ── Regulatory ────────────────────────────────────────────
            """
            CREATE TABLE IF NOT EXISTS regulatory_assessments (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id          INTEGER REFERENCES projects(id),
                material            TEXT,
                scenario            TEXT,           -- A | B | C | D
                device_class        TEXT,           -- I | II | III
                contact_type        TEXT,           -- surface | external | implant
                duration            TEXT,           -- limited | prolonged | permanent
                required_tests_json TEXT,
                biocompat_score     REAL,
                missing_evidence_json TEXT,
                combination_product INTEGER DEFAULT 0,
                atmp_flag           INTEGER DEFAULT 0,
                created_date        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,

            # ── Experimental Design ───────────────────────────────────
            """
            CREATE TABLE IF NOT EXISTS assay_recommendations (
                id                          INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id                  INTEGER REFERENCES projects(id),
                research_question           TEXT,
                recommended_platforms_json  TEXT,
                rationale                   TEXT,
                cost_flag                   TEXT,   -- low | medium | high
                equipment_flag              TEXT,
                created_date                TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS experimental_roadmaps (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id      INTEGER REFERENCES projects(id),
                material        TEXT,
                target_tissue   TEXT,
                steps_json      TEXT,
                dbtl_cycle      INTEGER DEFAULT 1,
                version         INTEGER DEFAULT 1,
                created_date    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,

            # ── Synthetic Biology ─────────────────────────────────────
            """
            CREATE TABLE IF NOT EXISTS genetic_edit_designs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id      INTEGER REFERENCES projects(id),
                target_gene     TEXT,
                cell_type       TEXT,
                editing_tool    TEXT,   -- Cas9 | Cas12a | base_editor | prime_editor | CRISPRi | CRISPRa
                delivery_method TEXT,   -- AAV | LNP | electroporation | RNP | lentiviral
                guide_rna_notes TEXT,
                off_target_risk TEXT,   -- low | medium | high
                regulatory_flag TEXT,   -- none | scenario_C
                created_date    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS bioproduction_plans (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id          INTEGER REFERENCES projects(id),
                molecule            TEXT,
                organism            TEXT,   -- E. coli | CHO | yeast | HEK293
                bioreactor_type     TEXT,
                scale               TEXT,   -- screening | process_dev | pilot | clinical | commercial
                process_mode        TEXT,   -- batch | fed-batch | perfusion
                cost_estimate_json  TEXT,
                gmp_required        INTEGER DEFAULT 0,
                created_date        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS synbio_designs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id      INTEGER REFERENCES projects(id),
                goal            TEXT,
                parts_json      TEXT,
                chassis         TEXT,
                circuit_design_json TEXT,
                dbtl_phase      TEXT,   -- Design | Build | Test | Learn
                regulatory_flag TEXT,
                created_date    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,

            # ── Business Intelligence ─────────────────────────────────
            """
            CREATE TABLE IF NOT EXISTS stakeholder_analyses (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id          INTEGER REFERENCES projects(id),
                stakeholders_json   TEXT,
                matrix_json         TEXT,
                created_date        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,

            """
            CREATE TABLE IF NOT EXISTS swot_analyses (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id          INTEGER REFERENCES projects(id),
                version             INTEGER DEFAULT 1,
                strengths_json      TEXT,
                weaknesses_json     TEXT,
                opportunities_json  TEXT,
                threats_json        TEXT,
                strategic_insight   TEXT,
                created_date        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,

            # ── AI / Briefings ────────────────────────────────────────
            """
            CREATE TABLE IF NOT EXISTS briefings (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id              INTEGER REFERENCES projects(id),
                mode                    TEXT,   -- technical | executive
                content                 TEXT,
                modules_included_json   TEXT,
                prompt_used             TEXT,
                created_date            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,

            # ── Paper authors (normalised rows, not JSON) ─────────────
            """
            CREATE TABLE IF NOT EXISTS paper_authors (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id    TEXT REFERENCES papers(pmid) ON DELETE CASCADE,
                name        TEXT NOT NULL,
                position    INTEGER DEFAULT 0,
                is_corresponding INTEGER DEFAULT 0
            )
            """,

            # ── Structured AI-extracted facts per paper ───────────────
            """
            CREATE TABLE IF NOT EXISTS paper_facts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id        TEXT REFERENCES papers(pmid) ON DELETE CASCADE,
                material_id     INTEGER REFERENCES materials(id) ON DELETE SET NULL,
                cell_model      TEXT DEFAULT '',
                organism        TEXT DEFAULT '',
                concentration   TEXT DEFAULT '',
                viability_pct   REAL,
                stiffness_kpa   REAL,
                key_finding     TEXT DEFAULT '',
                limitations     TEXT DEFAULT '',
                confidence      TEXT DEFAULT 'ai_extracted',
                verified_at     TIMESTAMP,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,

            # ── Individual material property rows ─────────────────────
            """
            CREATE TABLE IF NOT EXISTS material_properties (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                material_id     INTEGER NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
                property_name   TEXT NOT NULL,
                value_numeric   REAL,
                value_text      TEXT DEFAULT '',
                unit            TEXT DEFAULT '',
                condition       TEXT DEFAULT '',
                source_paper_id TEXT REFERENCES papers(pmid) ON DELETE SET NULL,
                confidence      TEXT DEFAULT 'literature',
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,

            # ── Generic API response cache with expiry ────────────────
            """
            CREATE TABLE IF NOT EXISTS api_cache (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                cache_key   TEXT NOT NULL UNIQUE,
                endpoint    TEXT NOT NULL,
                response    TEXT NOT NULL,
                cached_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at  TIMESTAMP NOT NULL
            )
            """,

            # ── Search history ────────────────────────────────────────
            """
            CREATE TABLE IF NOT EXISTS search_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id  INTEGER REFERENCES projects(id),
                tab         TEXT NOT NULL,
                query       TEXT NOT NULL,
                filters_json TEXT,
                result_count INTEGER DEFAULT 0,
                searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,

            "CREATE INDEX IF NOT EXISTS idx_search_history_tab ON search_history(tab, searched_at)",

            """
            CREATE TABLE IF NOT EXISTS module_findings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id  INTEGER REFERENCES projects(id),
                module      TEXT NOT NULL,
                findings    TEXT NOT NULL DEFAULT '',
                saved_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,

            "CREATE INDEX IF NOT EXISTS idx_findings_project ON module_findings(project_id, module)",

            # ── Indexes ───────────────────────────────────────────────
            "CREATE INDEX IF NOT EXISTS idx_papers_year   ON papers(year)",
            "CREATE INDEX IF NOT EXISTS idx_papers_doi    ON papers(doi)",
            "CREATE INDEX IF NOT EXISTS idx_annotations_paper  ON paper_annotations(paper_id)",
            "CREATE INDEX IF NOT EXISTS idx_annotations_project ON paper_annotations(project_id)",
            "CREATE INDEX IF NOT EXISTS idx_geo_tissue    ON geo_datasets(tissue)",
            "CREATE INDEX IF NOT EXISTS idx_researchers_orcid ON researchers(orcid)",
        ]

        for stmt in statements:
            conn.execute(stmt)

        logger.info("All tables created / verified.")


# Module-level singleton — import this everywhere
_db: Optional[DatabaseManager] = None


def get_db() -> DatabaseManager:
    """Return the application-wide DatabaseManager, initialising once."""
    global _db
    if _db is None:
        _db = DatabaseManager()
        _db.initialise()
    return _db