# Biomaterials Hackathon Analyser — Session Memory
**Last updated: 2026-03-09**

## Project Location
`c:\Users\szaha\Python_Projects\Biomaterials_Hackathon_Analyser\`
Entry point: `python main.py` from repo root (adds `src/` to sys.path).

## Current Status
**ALL STEPS COMPLETE. App is feature-complete, 0 import errors, launches cleanly.**
12 UI tabs. 14 engine packages. All smoke tests pass.

---

## How to Run

```bash
cd "c:\Users\szaha\Python_Projects\Biomaterials_Hackathon_Analyser"
.venv\Scripts\activate
python main.py
```

API keys in `config/.env`:
```
ANTHROPIC_API_KEY=sk-ant-...          # Claude (primary AI)
EPA_COMPTOX_API_KEY=...               # optional, CompTox enrichment only
```

DO NOT run `pip install -r requirements.txt` — broken entries. Install only:
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

1. Literature (fa5s.book)
2. Researcher Network (fa5s.users)
3. Materials Modeling (fa5s.cogs)
4. Business Intelligence (fa5s.chart-line)
5. Bio Analysis (fa5s.flask)
6. Drug Delivery (fa5s.pills)
7. Regulatory (fa5s.shield-alt)
8. Experimental Design (fa5s.flask)
9. Synthetic Biology (fa5s.dna)
10. Toxicology (fa5s.exclamation-triangle)
11. Briefing Generator (fa5s.star)
12. Simulation (fa5s.chart-bar)

---

## Key Architecture Facts

- DB: `projects` table (plural). `materials.class` column (not `material_class`).
- Connection: `with get_db().connection() as conn:` context manager
- AI: `llm_client.py` uses `urllib.request` -- no `anthropic` package needed to start
- Seeds: Called by tabs on first visit (`seed_if_empty()`), not from main.py
- Tab wiring: `regulatory_tab.set_tox_tab()`, `briefing_tab.set_module_tabs()`, `synbio_tab.scenario_c_changed` signal
- Findings: `FindingsWidget` in each tab -- persists notes to `module_findings` table per project+module
- `pyrightconfig.json` at repo root -- required for Pylance import resolution
- `cell_models_db.py` exports `CellModel`, not `CellModelsDB`

---

## Simulation Engine (added 2026-03-09)

`simulation_engine/degradation_models.py`:
- 6 presets: PLGA 50:50 (~40d fragment), PLGA 75:25 (~106d), PLA (~320d half-life), PCL (>1yr), Chitosan, Alginate
- 4 ODE model types: autocatalytic (Batycky), first-order, enzymatic (Michaelis-Menten), ionic erosion
- Arrhenius (Ea=75 kJ/mol) + pH corrections

`simulation_engine/drug_release.py`:
- 7 models: Zero Order, First Order, Higuchi, Korsmeyer-Peppas, Weibull, Hixson-Crowell, Biexponential
- Returns t50, t80, burst fraction (1h), release rate curve

---

## Tox Engine Ports

- admet: 8082
- comptox: 8083 (requires EPA_COMPTOX_API_KEY)
- aop: 8084
- pbpk: 8085

---

## Regulatory Scenarios

- A: Inert scaffold -- Class I/II/III device
- B: Scaffold + drug -- Drug-device combination, PMA
- C: Scaffold + engineered living cells -- ATMP
- D: Engineered organism manufactures material -- GMO regs

---

## Key Researchers (seeded)

- Jos Malda (UMC Utrecht) -- musculoskeletal biofab, MEW, VBP
- Riccardo Levato (UMC Utrecht) -- GRACE project, ERC Consolidator, pancreas VBP
- Miguel Castilho (TU/e) -- Xolography, bone regeneration

---

## Non-Critical Missing Files (nothing imports these)

- `drug_engine/drugbank_client.py`
- `business_intelligence/clinicaltrials_client.py`
- `business_intelligence/patent_analyzer.py`
- `utils/export.py` (briefing_tab handles MD/HTML/TXT inline)
- `regulatory_engine/iso10993.py` (covered by tox_engine/iso10993_assessor.py)

---

## User Preferences

- No emojis
- Concise responses
- Platform: Windows 11, VSCode, bash shell
