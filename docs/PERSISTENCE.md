# Project Persistence Architecture

Built across sessions to support Friday→Sunday hackathon workflow.

## Goal
App remembers: which project is active, all searches run, all strategic findings written
per module — so nothing is lost between sessions and the Sunday briefing can synthesise everything.

## Database tables added

### `search_history`
```sql
id, project_id, tab, query, filters_json, result_count, searched_at
```
- Logged automatically on every successful PubMed search (`_on_search_finished`)
- Index on `(tab, searched_at)`

### `module_findings`
```sql
id, project_id, module, findings TEXT, saved_at
```
- One row per project+module (upserted, not appended)
- Index on `(project_id, module)`

## CRUD functions added (src/data_manager/crud.py)

| Function | Purpose |
|---|---|
| `log_search(tab, query, result_count, project_id, filters)` | Write search to history |
| `get_recent_searches(tab, project_id, limit)` | Read back deduped recent queries |
| `get_latest_project()` | Return most recently modified project row |
| `save_findings(module, findings, project_id)` | Upsert findings text |
| `get_findings(module, project_id)` | Read findings (one module or all) |

## Multi-project UI (main_window.py)

### New Project dialog (`_NewProjectDialog`)
- Fields: name, target tissue (13 options), regulatory scenario A/B/C/D, notes
- On accept: calls `crud.create_project()`, stores `self._project_id`

### Open Project dialog (`_OpenProjectDialog`)
- Lists all saved projects sorted by `last_modified DESC`
- Shows: name, tissue, scenario, date inline
- Double-click or OK loads the project
- Calls `_propagate_project_id()` after load

### `_load_last_project()`
- Called at end of `MainWindow.__init__`
- Restores window title, tissue combo, experimental tab prefill from DB
- Propagates project ID to all tabs

### `_propagate_project_id()`
Calls `tab.set_project_id(self._project_id)` on all 11 tabs:
```
literature_tab, researcher_tab, materials_tab, business_tab, bio_tab,
drug_tab, regulatory_tab, experimental_tab, tox_tab, synbio_tab, briefing_tab
```

## Literature tab extras (src/ui/literature_tab.py)
- `_last_query` captured in `perform_search()`
- `_on_search_finished` logs search + refreshes recent dropdown
- "Recent:" row (Row 4 of grid) — `QComboBox` pre-filled from `search_history`
- Clicking a recent item fills the search box
- `set_project_id()` updates `_project_id`, refreshes findings + recent searches