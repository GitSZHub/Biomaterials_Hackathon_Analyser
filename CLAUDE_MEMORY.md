# Biomaterials Hackathon Analyser — Session Memory

## Project Location
`c:\Users\szaha\OneDrive\Documents\R_Py_Projects\Biomaterials_Hackathon_Analyser\`
(root — files live directly here, not in a nested subdir)

## Current Status
**BUILD PHASE. Steps 1-12 complete.**
Full build across multiple sessions. See `ARCHITECTURE_DECISIONS.md` for all detail.

## Key Decisions Made

### Framework
- PyQt6 desktop app (already scaffolded)
- Python backend, SQLite + HDF5 storage
- Plotly (interactive) + Matplotlib/Seaborn (publication figures)
- Scanpy for single-cell analysis

### AI Integration
- Claude PRIMARY, GPT-4o FALLBACK
- Prompts VISIBLE and EDITABLE (Option C confirmed)
- Briefing: Technical mode (teammates) + Executive mode (investors)

### Search Architecture
- Option A: Literature = global topic search, Researcher Network = passive feed
- Share same SQLite paper database

### GEO / Transcriptomics
- Full dataset download + local analysis (Option B)
- Cached HDF5, background thread, progress bar
- Single-cell readiness from day one (CELLxGENE, Scanpy)
- Matrigel as baseline — persistent caveat banner always shown

### Biocompatibility Scoring
- Options B + C: user data + AI structural analogy prediction
- Confidence tier: own data > in vivo > in vitro primary > cell lines > AI prediction
- BiocCompatScorer: 40% CompTox + 30% ADMET + 30% AOP (enriched when MCP servers running)

### Project Level Context
- Project-scoped: target tissue, resources, regulatory aim, material set at creation
- Every module reads project context and filters accordingly

## Modules — Built Status

| # | Module | Backend | UI Tab | Notes |
|---|--------|---------|--------|-------|
| 1 | Literature Engine | BUILT | BUILT | PubMed, DOI, knowledge extractor |
| 2 | Researcher Network | BUILT | BUILT | manual add, feed, graph |
| 3 | Materials Engine | BUILT | BUILT | topic tree, AI cards, comparison |
| 4 | Bio Engine | BUILT | BUILT | GEO, CELLxGENE, Scanpy; metabolomics/proteomics/flow NOT YET |
| 5 | Drug Engine | BUILT | BUILT | PubChem/ChEMBL/DrugBank, Level 1-3 PK |
| 6 | Experimental Engine | BUILT | BUILT | cell/organism KB, DBTL tracker, roadmap |
| 7 | Regulatory Engine | BUILT | BUILT | device classifier, ISO 10993, biocompat, pathway, AI narrative |
| 8 | AI Engine | BUILT | — | llm_client, prompt templates, knowledge cards |
| 9 | Business Intelligence | BUILT | BUILT | market KB, stakeholders, SWOT, Claude synthesis |
| 10 | Briefing Generator | BUILT | BUILT | flagship — 10 tech + 10 exec sections, editable prompts |
| 11 | Tox Engine | BUILT | BUILT | ADMET/CompTox/AOP/PBPK MCP servers, server control panel |
| 12 | Synthetic Biology | NOT YET | NOT YET | next priority |
| 13 | Data Management | BUILT (basic) | NOT YET | ProjectContext, DB, CRUD |

## Tox Engine Architecture (critical — added last session)

tox_engine/ — 8 files, all built:
- `server_manager.py` — ToxServerManager singleton, 4 MCP servers
  - admet:8082, comptox:8083, aop:8084, pbpk:8085
  - get_tox_manager() in tox_tab.py returns singleton
- `mcp_client.py` — MCPClient.call_tool()
- `admet_client.py` — predict_admet(smiles), render_structure(smiles), no API key
- `comptox_client.py` — lookup_by_name(), EPA_COMPTOX_API_KEY required
- `aop_client.py` — map_chemical_to_aops(), AOP-Wiki, no API key
- `pbpk_client.py` — load_model(.pkml), run_simulation(), OSP Suite, no API key
- `iso10993_assessor.py` — ISO10993Assessor(comptox, aop, admet)
- `workers.py` — all QThread workers pre-built

ToxTab wired to RegulatoryTab via:
  `main_window.py`: `regulatory_tab.set_tox_tab(self.tox_tab)`
  regulatory_tab workers call `self._get_live_clients()` before running

## Tab Order in main_window.py
Literature → Researcher Network → Materials Modeling → Business Intelligence →
Bio Analysis → Drug Delivery → Regulatory → Experimental Design → Toxicology → Briefing Generator

## Regulatory Scenarios (4 defined)
- A: Inert scaffold -> Class I/II/III device pathway
- B: Scaffold + drug -> Drug-device combination, PMA + CDER/CBER
- C: Scaffold + engineered living cells -> ATMP (gene/cell therapy pathway)
- D: Engineered organism produces material -> GMO manufacturing regs only

## Key Researchers
- Jos Malda (UMC Utrecht) — musculoskeletal biofab, MEW, VBP
- Riccardo Levato (UMC Utrecht) — GRACE, ERC Consolidator (pancreas VBP)
- Miguel Castilho (TU/e) — Xolography, bone regeneration
- Dutch biofab cluster — dominant 2025 theme: volumetric bioprinting

## Next Session Priority
1. Synthetic Biology tab (iGEM, SynBioHub, Addgene, DBTL wizard, living materials,
   genetic editor, delivery advisor, bioproduction planner)
2. Assay Recommender + Microscopy Advisor + Proteomics Advisor + Flow Cytometry Advisor

## How to Run the App

### Setup (first time)
```bash
cd "c:\Users\szaha\OneDrive\Documents\R_Py_Projects\Biomaterials_Hackathon_Analyser"
python -m venv .venv
.venv\Scripts\activate
pip install PyQt6 qtawesome anthropic requests pandas numpy matplotlib plotly python-dotenv
python main.py
```

### Subsequent runs
```bash
cd "c:\Users\szaha\OneDrive\Documents\R_Py_Projects\Biomaterials_Hackathon_Analyser"
.venv\Scripts\activate
python main.py
```

### Install packages on-demand (NOT from requirements.txt)
requirements.txt has broken/heavy packages — install only as needed:
- `pip install PyQt6 qtawesome` — GUI (required)
- `pip install anthropic` — Claude API (required for AI features)
- `pip install requests pandas numpy` — core data (required)
- `pip install matplotlib plotly` — visualisation
- `pip install python-dotenv` — reads config/.env for API keys
- `pip install biopython pubchempy` — bio/drug modules
- `pip install scanpy anndata` — single-cell analysis
- `pip install pdfplumber pymupdf` — PDF extraction

DO NOT run `pip install -r requirements.txt` — it will fail on:
- `rdkit` (needs conda or wheel, not pip)
- `pymatgen`, `matminer` (large, slow, not needed yet)
- `comptox-mcp`, `aop-mcp`, `pbpk-mcp` (don't exist on PyPI — placeholders)
- `textract`, `psycopg2-binary`, `pymongo` (unnecessary)

### API keys
Put in `config/.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
EPA_COMPTOX_API_KEY=...   # optional, CompTox enrichment only
```

## User Preferences
- No emojis
- Concise responses
- Architecture-first before coding
- Platform: Windows 11, VSCode, bash shell
