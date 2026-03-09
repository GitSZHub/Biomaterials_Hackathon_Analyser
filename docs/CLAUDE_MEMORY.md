# Biomaterials Hackathon Analyser — Session Memory
<!-- Canonical copy. On a new machine read this + docs/PERSISTENCE.md + docs/FINDINGS.md -->
**Last updated: 2026-03-09**

## Project Location
`c:\Users\szaha\Python_Projects\Biomaterials_Hackathon_Analyser\`
Entry point: `python main.py` from repo root.

## Current Status
**ALL STEPS COMPLETE. Feature-complete, 0 import errors, launches cleanly.**
12 UI tabs. 14 engine packages.

---

## How to Run

```bash
cd "c:\Users\szaha\Python_Projects\Biomaterials_Hackathon_Analyser"
.venv\Scripts\activate
python main.py
```

API keys in `config/.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
EPA_COMPTOX_API_KEY=...   # optional
```

DO NOT `pip install -r requirements.txt` -- broken entries. Install only:
```bash
pip install PyQt6 qtawesome pandas numpy scipy matplotlib python-dotenv
```

---

## Modules Built Status

| # | Module | Backend | UI Tab | Notes |
|---|--------|---------|--------|-------|
| 1 | Literature Engine | BUILT | BUILT | PubMed, researcher tracker, seeds 3 researchers |
| 2 | Researcher Network | BUILT | BUILT | manual add, PubMed sync, network graph |
| 3 | Materials Engine | BUILT | BUILT | 26-node topic tree, AI cards, comparison, seeds 5 materials |
| 4 | Bio Engine | BUILT | BUILT | GEO query, transcriptomics, volcano plots |
| 5 | Drug Engine | BUILT | BUILT | PubChem/ChEMBL, Level 1-3 PK curves |
| 6 | Experimental Engine | BUILT | BUILT | cell/organism KB, DBTL tracker, assay wizard |
| 7 | Regulatory Engine | BUILT | BUILT | device classifier, ISO 10993 (via tox_engine), pathway mapper |
| 8 | AI Engine | BUILT | -- | llm_client (urllib, no SDK), paper summariser, knowledge cards |
| 9 | Business Intelligence | BUILT | BUILT | market KB, stakeholders, SWOT, Claude synthesis, patent browser |
| 10 | Briefing Generator | BUILT | BUILT | 10 tech + 10 exec sections, editable prompts, MD/HTML/TXT export |
| 11 | Tox Engine | BUILT | BUILT | ADMET/CompTox/AOP/PBPK MCP servers (ports 8082-8085) |
| 12 | Synthetic Biology | BUILT | BUILT | iGEM/SynBioHub/Addgene, DBTL wizard, genetic editor, living materials |
| 13 | Simulation Engine | BUILT | BUILT | ODE degradation (6 polymers) + drug release (7 models) |
| 14 | Data Management | BUILT | -- | 31-table SQLite (WAL), ProjectContext, CRUD, findings/search history |

---

## Tab Order (main_window.py)

1. Literature
2. Researcher Network
3. Materials Modeling
4. Business Intelligence
5. Bio Analysis
6. Drug Delivery
7. Regulatory
8. Experimental Design
9. Synthetic Biology
10. Toxicology
11. Briefing Generator
12. Simulation

---

## Key Architecture Facts

- DB: `projects` table (plural). `materials.class` column (not `material_class`).
- Connection: `with get_db().connection() as conn:` context manager (auto-commit/rollback)
- AI: `llm_client.py` uses `urllib.request` -- no `anthropic` package needed to import
- Seeds: Called by tabs on first visit (`seed_if_empty()`), not from main.py
- Tab wiring:
  - `regulatory_tab.set_tox_tab(tox_tab)` -- live MCP clients enrich ISO 10993
  - `regulatory_tab.set_experimental_tab(experimental_tab)` -- classification prefills wizard
  - `briefing_tab.set_module_tabs(business_tab, experimental_tab)`
  - `synbio_tab.scenario_c_changed` signal -> `_on_scenario_c_changed`
- Findings: `FindingsWidget` in each tab -- persists notes to `module_findings` table
- `pyrightconfig.json` at repo root -- required for Pylance
- `cell_models_db.py` exports `CellModel`, not `CellModelsDB`

---

## Persistence System (see docs/PERSISTENCE.md for full detail)

- `search_history` table: every PubMed search logged with tab/query/result_count
- `module_findings` table: one row per project+module (upserted)
- `_load_last_project()` in main_window: restores most recently modified project on startup
- `_OpenProjectDialog`: lists all saved projects from DB

---

## Findings System (see docs/FINDINGS.md for full detail)

- `FindingsWidget` -- reusable amber QFrame, collapsible, 2s autosave debounce
- `set_project_id(id)` loads existing text, auto-expands if content exists
- Wired to Briefing Generator: BriefingTab.set_module_tabs() receives live tab refs

---

## Simulation Engine (added 2026-03-09)

`simulation_engine/degradation_models.py`:
- 6 presets: PLGA 50:50 (~40d fragment), PLGA 75:25 (~106d), PLA (~320d half-life), PCL (>1yr), Chitosan, Alginate
- 4 ODE model types: autocatalytic (Batycky), first-order, enzymatic (Michaelis-Menten), ionic erosion
- Arrhenius (Ea=75 kJ/mol) + pH corrections on all rate constants

`simulation_engine/drug_release.py`:
- 7 models: Zero Order, First Order, Higuchi, Korsmeyer-Peppas, Weibull, Hixson-Crowell, Biexponential (burst+sustained)
- Returns t50, t80, burst fraction (1h), release rate curve

---

## Tox Engine (ports)

- admet: 8082 -- no key needed
- comptox: 8083 -- requires EPA_COMPTOX_API_KEY
- aop: 8084 -- no key needed
- pbpk: 8085 -- no key needed

---

## Regulatory Scenarios

- A: Inert scaffold -- Class I/II/III device
- B: Scaffold + drug -- Drug-device combination, PMA
- C: Scaffold + engineered living cells -- ATMP (gene/cell therapy)
- D: Engineered organism manufactures material -- GMO regs only

---

## Key Researchers (seeded)

- Jos Malda (UMC Utrecht) -- musculoskeletal biofab, MEW, volumetric bioprinting
- Riccardo Levato (UMC Utrecht) -- GRACE project, ERC Consolidator, pancreas VBP
- Miguel Castilho (TU/e) -- Xolography, bone regeneration

---

## Non-Critical Missing Files (nothing imports these)

- `drug_engine/drugbank_client.py`
- `business_intelligence/clinicaltrials_client.py`
- `business_intelligence/patent_analyzer.py`
- `utils/export.py` (briefing_tab handles MD/HTML/TXT inline)
- `regulatory_engine/iso10993.py` (covered by tox_engine/iso10993_assessor.py)
- `data_manager/schema.py` -- leftover stub, safe to delete

---

## Cleanup (safe to delete)

- `src/_tmp_new/` -- temp dir from early build session
- `src/_tmp_pctx/` -- temp dir from early build session
- `src/data_manager/schema.py` -- superseded by database.py

---

## User Preferences

- No emojis
- Concise responses
- Platform: Windows 11, VSCode, bash shell
