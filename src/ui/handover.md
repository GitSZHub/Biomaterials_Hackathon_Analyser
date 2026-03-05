# Biomaterials Hackathon Analyser — Build Handover
**Date:** 2026-03-05  
**Session:** Steps 0–5 complete. Ready to resume at Step 6.

---

## Current State

All files verified with `ast.parse()` and runtime smoke tests before delivery.
Zero Pylance errors outstanding as of last update.

---

## Files Delivered This Session

### New folders to create in repo
```
src/ai_engine/
src/materials_engine/
```

### File list (all go into repo under src/ unless noted)

| File | Status | Notes |
|------|--------|-------|
| `pyrightconfig.json` | NEW — root of repo | Fixes all Pylance import warnings |
| `data_manager/database.py` | NEW | 31-table SQLite schema, WAL mode |
| `data_manager/crud.py` | NEW | Full CRUD API, JSON auto-serialisation |
| `data_manager/__init__.py` | NEW | Exports get_db, crud, ProjectContext |
| `ai_engine/__init__.py` | NEW | |
| `ai_engine/llm_client.py` | NEW | Claude primary, GPT-4o fallback, retries |
| `ai_engine/paper_summariser.py` | NEW | Structured paper summaries via Claude |
| `ai_engine/knowledge_card_gen.py` | NEW | Material knowledge cards via Claude |
| `literature_engine/pubmed_crawler.py` | EXISTS — unchanged | |
| `literature_engine/researcher_tracker.py` | NEW | PubMed sync, seeds 3 researchers |
| `materials_engine/__init__.py` | NEW | |
| `materials_engine/topic_tree.py` | NEW | 26-node taxonomy |
| `materials_engine/materials_db.py` | NEW | Seeds 5 materials, comparison logic |
| `ui/__init__.py` | UPDATED | Adds ResearcherNetworkTab |
| `ui/main_window.py` | UPDATED | Adds Researcher Network tab |
| `ui/literature_tab.py` | UPDATED | Wired to real PubMed + AI Summary button |
| `ui/researcher_network_tab.py` | NEW | Full researcher management UI |
| `ui/materials_tab.py` | UPDATED | Topic tree, knowledge cards, comparison |

### Delete from repo
- `data_manager/schema.py` — superseded by database.py

---

## Schema Notes

The `materials` table uses `class` (not `material_class`) and `subclass` (not `topic_key`).  
Our code uses `subclass` to store the topic tree key (e.g. `"titanium_alloys"`).  
`upsert_material()` in crud.py takes `material_class` as a positional arg — maps to `class` column internally.

---

## Known Gotchas

1. **`pyrightconfig.json` must be at repo root** (same level as `main.py`), not inside `src/`.

2. **API key** — add to `config/.env`:
   ```
   ANTHROPIC_API_KEY=your_key_here
   ```
   Without it the app runs fine, AI features just disable themselves gracefully.

3. **`requirements.txt` has a bad line** — `admetlab-mcp>=0.1.0` doesn't exist on PyPI.  
   Remove it. Install with:
   ```bash
   pip install PyQt6 qtawesome pandas numpy scipy scikit-learn networkx biopython requests beautifulsoup4 pypdf2 spacy plotly matplotlib seaborn sqlalchemy python-dotenv aiohttp
   ```

4. **`data_manager/project_context.py`** — already exists in repo, do not overwrite.  
   It's a good dataclass, our schema was updated to match it.

5. **`materials_db.py` was briefly in the wrong path** (`src/literature_engine/materials_enginer/`) in Pylance output — confirm it is at `src/materials_engine/materials_db.py`.

---

## Build Order — Remaining Steps

### Step 6: Bio Engine
Files to create:
- `bio_engine/__init__.py`
- `bio_engine/geo_client.py` — GEO dataset query + download (HDF5 cache)
- `bio_engine/transcriptomics.py` — bulk DEG analysis, volcano plot, heatmap
- `ui/bio_analysis_tab.py` — UPDATED with real GEO search + volcano viz

Dependencies to install first: `GEOparse`, `pydeseq2` or `scipy` for DEG, `plotly` for viz.

### Step 7: Drug Engine
Files to create:
- `drug_engine/__init__.py`
- `drug_engine/pubchem_client.py`
- `drug_engine/chembl_client.py`
- `drug_engine/drugbank_client.py`
- `drug_engine/pk_models.py` — Level 1-3 PK curves
- `ui/drug_tab.py` — NEW tab

### Step 8: Regulatory Engine
Files to create:
- `regulatory_engine/__init__.py`
- `regulatory_engine/device_classifier.py`
- `regulatory_engine/iso10993.py` — full test matrix
- `regulatory_engine/biocompat_scorer.py`
- `regulatory_engine/pathway_mapper.py`
- `ui/regulatory_tab.py` — NEW tab

### Step 9: Experimental Design
Files to create:
- `experimental_engine/__init__.py`
- `experimental_engine/cell_models_db.py`
- `experimental_engine/organism_models_db.py`
- `experimental_engine/experimental_designer.py`
- `experimental_engine/dbtl_tracker.py`
- `ui/experimental_tab.py` — NEW tab

### Step 10: Business Intelligence
Files to create:
- `business_intelligence/market_intelligence.py`
- `business_intelligence/clinicaltrials_client.py`
- `business_intelligence/patent_analyzer.py`
- `business_intelligence/stakeholder_mapper.py`
- `business_intelligence/swot_generator.py`
- `ui/business_tab.py` — UPDATED (currently a stub)

### Step 11: Briefing Generator
Files to create:
- `ai_engine/briefing_gen.py`
- `ui/briefing_tab.py` — NEW tab (flagship feature)
- `utils/export.py` — PDF + Markdown export

---

## Architecture Decisions Made This Session

- **SQLite WAL mode** — better concurrent reads during background sync threads
- **All AI calls lazy-import** the client inside functions — app starts even with no API key
- **Background QThreads** for all network ops (PubMed search, researcher sync, card generation) — UI never blocks
- **Seed-if-empty pattern** — all KB modules (researchers, materials) self-populate on first run
- **`subclass` column** used for topic tree keys in materials table — avoids schema migration
- **`assert menu is not None`** pattern used after Qt's `addMenu()`/`menuBar()` — satisfies Pylance without hiding real bugs

---

## How to Resume

1. Pull latest from repo
2. Confirm all files from the table above are in place
3. Run smoke test:
   ```bash
   cd src
   python3 -c "
   import sys; sys.path.insert(0, '.')
   from data_manager import get_db, crud
   from materials_engine.materials_db import MaterialsDB
   from literature_engine.researcher_tracker import ResearcherTracker
   from ai_engine.llm_client import get_client
   get_db()
   print('DB OK')
   print(f'Materials: {len(MaterialsDB().list_all())}')
   print(f'Researchers: {len(crud.list_researchers())}')
   print(f'AI available: {get_client().is_available()}')
   "
   ```
4. Tell Claude: **"resuming Biomaterials Hackathon Analyser build, ready for Step 6"**
   and paste this document — Claude will pick up exactly where we left off.