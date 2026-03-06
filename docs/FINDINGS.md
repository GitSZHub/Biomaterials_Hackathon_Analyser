# Findings & Strategy Notes System

## Purpose
Allows the user to record strategic insights per module (e.g. "target HIF-1 pathway",
"GelMA preferred over alginate for this tissue", "CRISPR-Cas9 delivery via AAV9").
These persist across sessions and feed directly into the Sunday Briefing Generator.

## Component: FindingsWidget (src/ui/findings_widget.py)

Reusable `QFrame` subclass. Drop into any tab with:
```python
self._findings = FindingsWidget("module_name", placeholder="...")
layout.addWidget(self._findings)
```

### Features
- Collapsible amber panel (chevron toggle)
- Auto-saves 2 s after last keystroke (debounce timer)
- Explicit save button (fa5s.save icon)
- Shows "saved HH:MM" / "unsaved" status label
- `set_project_id(id)` loads existing text from DB + auto-expands if text exists
- `get_text()` returns current text for external use

### Styling
- Background: `#fffbf0` (amber tint)
- Title: "Findings & Strategy Notes" in bold `#856404`
- Font: Consolas 9pt for the text area

## Tabs with FindingsWidget

| Tab file | Module key | Placeholder focus |
|---|---|---|
| literature_tab.py | `"literature"` | papers, themes, targets, gaps |
| researcher_network_tab.py | `"researchers"` | contacts, collaborators |
| materials_tab.py | `"materials"` | lead materials, fabrication decisions |
| business_tab.py | `"business"` | market, IP, SWOT conclusions |
| bio_analysis_tab.py | `"bio_analysis"` | DEGs, pathways, gene targets, strategy |
| drug_tab.py | `"drug"` | lead compounds, ADMET, PK, CRISPR strategy |
| regulatory_tab.py | `"regulatory"` | device class, ISO tests, pathway |
| experimental_tab.py | `"experimental"` | cell models, DBTL plan, assays |
| tox_tab.py | `"toxicology"` | hazards, CompTox flags, mitigations |
| synbio_tab.py | `"synbio"` | parts, chassis, DBTL, Scenario C |

Each tab also has `set_project_id(project_id)` which delegates to `self._findings.set_project_id()`.

## Briefing Generator integration (src/ui/briefing_tab.py)

`BriefingTab.set_project_id(project_id)` stores `self._project_id`.

In `_on_context_ready()`, after context is assembled:
```python
findings_rows = crud.get_findings(project_id=project_id)
# Appended to ctx.user_context as:
# === DRUG FINDINGS ===
# <text>
# === BIO_ANALYSIS FINDINGS ===
# <text>
# ...
```
Claude sees all findings when generating every section.
The "Context / Prompt" tab in the Briefing Generator shows the full assembled context
including findings — user can edit before generating.

## Data flow summary
```
User types in FindingsWidget
  → debounce 2s → crud.save_findings(module, text, project_id)
  → stored in module_findings table

On "Refresh Context" in Briefing Generator:
  → crud.get_findings(project_id) → all modules
  → appended to BriefingContext.user_context
  → Claude generates briefing with full strategic context
```