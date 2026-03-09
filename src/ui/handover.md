# Biomaterials Hackathon Analyser — Build Handover
**Date:** 2026-03-09
**Status:** ALL STEPS COMPLETE. App is feature-complete and launches cleanly.

---

## Quick Start

```bash
cd "c:\Users\szaha\Python_Projects\Biomaterials_Hackathon_Analyser"
.venv\Scripts\activate
python main.py
```

API key (optional — app runs without it, AI features degrade gracefully):
```
# config/.env
ANTHROPIC_API_KEY=sk-ant-...
EPA_COMPTOX_API_KEY=...   # optional, CompTox only
```

---

## Smoke Test

```bash
cd src
python -c "
import sys; sys.path.insert(0, '.')
from data_manager import get_db, crud
from materials_engine.materials_db import MaterialsDB
from literature_engine.researcher_tracker import ResearcherTracker
from ai_engine.llm_client import get_client
get_db()
print('DB OK')
print(f'Materials: {len(MaterialsDB().list_all())}')     # expect 5
print(f'Researchers: {len(crud.list_researchers())}')    # expect 3
print(f'AI available: {get_client().is_available()}')
"
```

---

## All Files Built

### Engine packages (src/)

| Package | Files | Notes |
|---------|-------|-------|
| `data_manager/` | database.py (31-table SQLite, WAL), crud.py, project_context.py, __init__.py | `with get_db().connection() as conn:` pattern |
| `ai_engine/` | llm_client.py, paper_summariser.py, knowledge_card_gen.py | urllib only — no anthropic SDK required |
| `literature_engine/` | pubmed_crawler.py, researcher_tracker.py | Seeds 3 researchers on first run |
| `materials_engine/` | topic_tree.py (26 nodes), materials_db.py | Seeds 5 materials on first run |
| `bio_engine/` | geo_client.py, transcriptomics.py | GEO via NCBI E-utils, 7-day cache |
| `drug_engine/` | pubchem_client.py, chembl_client.py, pk_models.py | Level 1-3 PK curves |
| `regulatory_engine/` | device_classifier.py, pathway_mapper.py | ISO 10993 via tox_engine |
| `experimental_engine/` | cell_models_db.py (exports `CellModel`), organism_models_db.py, experimental_designer.py, dbtl_tracker.py | |
| `business_intelligence/` | market_kb.py, stakeholder_kb.py, swot_engine.py, strategic_summary.py | Patent tab uses browser links, no backend needed |
| `briefing_engine/` | briefing_generator.py, context_assembler.py | 10 tech + 10 exec sections |
| `tox_engine/` | mcp_client.py, server_manager.py, admet_client.py, aop_client.py, comptox_client.py, pbpk_client.py, biocompat_scorer.py, iso10993_assessor.py, workers.py | 4 MCP servers: 8082/8083/8084/8085 |
| `synthetic_biology_engine/` | igem_client.py, synbiohub_client.py, addgene_client.py, genetic_editor.py, delivery_advisor.py, dbtl_wizard.py, living_materials.py, bioproduction_planner.py | |
| `simulation_engine/` | degradation_models.py, drug_release.py, __init__.py | ODE models, numpy only |
| `utils/` | config.py | |

### UI tabs (src/ui/) — 12 tabs total

| Tab class | File | Icon |
|-----------|------|------|
| LiteratureTab | literature_tab.py | fa5s.book |
| ResearcherNetworkTab | researcher_network_tab.py | fa5s.users |
| MaterialsTab | materials_tab.py | fa5s.cogs |
| BusinessTab | business_tab.py | fa5s.chart-line |
| BioAnalysisTab | bio_analysis_tab.py | fa5s.flask |
| DrugTab | drug_tab.py | fa5s.pills |
| RegulatoryTab | regulatory_tab.py | fa5s.shield-alt |
| ExperimentalTab | experimental_tab.py | fa5s.flask |
| SynBioTab | synbio_tab.py | fa5s.dna |
| ToxTab | tox_tab.py | fa5s.exclamation-triangle |
| BriefingTab | briefing_tab.py | fa5s.star |
| SimulationTab | simulation_tab.py | fa5s.chart-bar |

---

## Key Architecture Facts

- **DB:** `projects` table (plural). `materials` table uses `class` column (not `material_class`).
- **Connection pattern:** `with get_db().connection() as conn:` — auto-commits or rolls back
- **AI:** `llm_client.py` uses `urllib.request` directly. No `anthropic` package needed to start.
- **Seeds:** Called by tabs on first visit (`seed_if_empty()`). Nothing in main.py needed.
- **Simulation engine:** `degradation_models.py` — PLGA 50:50 fragments ~40d, PCL >1yr. `drug_release.py` — 7 models (KP, Higuchi, Weibull, Biexponential, etc.)
- **Tab wiring:** `regulatory_tab.set_tox_tab()`, `briefing_tab.set_module_tabs()`, `synbio_tab.scenario_c_changed` signal
- **`pyrightconfig.json`** at repo root — fixes Pylance import warnings

## Known Gotchas

1. `experimental_engine/cell_models_db.py` exports `CellModel`, not `CellModelsDB`
2. `requirements.txt` has broken entries — DO NOT `pip install -r requirements.txt`
   Install only: `pip install PyQt6 qtawesome pandas numpy scipy matplotlib python-dotenv`
3. `data_manager/schema.py` is a leftover stub — safe to delete (superseded by database.py)
4. `src/_tmp_new/` and `src/_tmp_pctx/` are leftover temp dirs — safe to delete

---

## Potential Next Improvements

- PDF export via reportlab (briefing_tab already has MD/HTML/TXT export)
- ClinicalTrials.gov API client (`business_intelligence/clinicaltrials_client.py`)
- DrugBank client (`drug_engine/drugbank_client.py`)
- Simulation parameter save/load to DB
- PBPK model additions to simulation_engine
