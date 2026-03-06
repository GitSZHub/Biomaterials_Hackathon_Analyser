# Biomaterials Hackathon Analyser — Full Architecture Decisions
# Last updated: 2026-03-06
# Status: BUILD PHASE. Steps 1-11 complete + Toxicology tab built. See Build Order below.

---

## Overview

A PyQt6 desktop application for biomaterials research analysis. Designed for:
- Rapid research and analysis in hackathon environments
- Investor briefing generation (Technical + Executive modes)
- Experimental design decision support
- Regulatory pathway guidance
- Researcher network monitoring
- Business intelligence and stakeholder analysis
- Synthetic biology integration

Primary constraint: 1-day MVP build for hackathon. Architecture designed for
depth-first build — everything that exists on day one works properly.

---

## Core Technology Stack

- GUI: PyQt6 (existing scaffold)
- Database: SQLite (local), HDF5 for cached GEO/single-cell datasets
- Visualisation: Plotly (interactive, exportable) + Matplotlib/Seaborn (publication figures)
- AI: Claude API (primary), GPT-4o (fallback)
- Background jobs: QThread (Qt worker threads, UI never blocks)
- Data: pandas, numpy, scipy, statsmodels, networkx, scanpy, anndata

---

## Architectural Principles

1. Project-scoped — all modules read from project context (target tissue,
   resources, regulatory aim). Set once per project, everything adapts.

2. Option A search model — Literature search is global/topic-driven.
   Researcher network is a separate passive feed. Both share one paper DB.

3. Real data only — no fake placeholders in production. Every score,
   every graph is traceable to source data or clearly flagged as AI prediction.

4. Prompts are first-class — all AI prompt templates are visible and
   editable by the user. Not hidden plumbing.

5. Briefing-first — the flagship feature is the briefing document generator.
   All other modules exist to feed it. Every analysis has an "Add to Briefing" button.

6. DBTL cycle — synthetic biology and experimental design follow the
   Design-Build-Test-Learn engineering cycle explicitly. The app tracks
   iterations across cycles for a project.

---

## Module Map

```
src/
├── literature_engine/
│   ├── pubmed_crawler.py          BUILT — functional, wired to Literature tab
│   ├── researcher_tracker.py      BUILT — researcher DB, sync, feed
│   ├── network_discovery.py       NOT YET — BFS co-author expansion
│   ├── bulk_importer.py           NOT YET — CSV/paste batch resolution
│   ├── knowledge_extractor.py     BUILT — AI fact extraction from papers
│   └── doi_client.py              BUILT — CrossRef + Unpaywall lookup
│
├── materials_engine/
│   ├── topic_tree.py              BUILT — material taxonomy + navigation
│   ├── materials_db.py            BUILT — local SQLite materials KB
│   └── characterisation.py       BUILT — properties + comparison viz
│
├── bio_engine/
│   ├── geo_client.py              BUILT — GEO dataset query + download
│   ├── arrayexpress_client.py     NOT YET — European dataset source
│   ├── cellxgene_client.py        BUILT — single-cell, CELLxGENE Census API
│   ├── single_cell_portal.py      NOT YET — Broad Institute datasets
│   ├── human_cell_atlas.py        NOT YET — reference cell type data
│   ├── transcriptomics.py         BUILT — bulk DEG analysis, volcano, heatmap
│   ├── single_cell.py             BUILT — Scanpy pipeline (QC, UMAP, clustering,
│   │                                       annotation, diff abundance, diff expression)
│   ├── deconvolution.py           NOT YET — bulk RNA -> cell type estimates
│   ├── pathway_analysis.py        NOT YET — KEGG/Reactome enrichment
│   ├── metabolomics.py            NOT YET — pathway overlay, PCA/UMAP
│   ├── metabolomics_client.py     NOT YET — MetaboLights + Metabolomics Workbench
│   ├── sequencing_advisor.py      NOT YET — technology selection logic
│   ├── multiomics_integrator.py   NOT YET — MOFA/MixOmics joint pathway enrichment
│   ├── flow_data_processor.py     NOT YET — FCS file import, gating logic
│   └── tissue_interaction.py      NOT YET — tissue response modelling + timeline
│
├── drug_engine/
│   ├── pubchem_client.py          BUILT — compound lookup (free, no key)
│   ├── chembl_client.py           BUILT — bioactivity + targets (free)
│   ├── drugbank_client.py         BUILT — PK parameters (free academic)
│   └── pk_models.py               BUILT — Level 1-3 PK models
│
├── experimental_engine/
│   ├── cell_models_db.py          BUILT — cell line + organoid KB
│   ├── organism_models_db.py      BUILT — in vivo model KB
│   ├── experimental_designer.py   BUILT — ExperimentalDesigner, ExperimentalRoadmap
│   ├── dbtl_tracker.py            BUILT — DBTLTracker (SQLite + in-memory fallback)
│   ├── protocol_client.py         NOT YET — protocols.io integration
│   ├── assay_recommender.py       NOT YET — assay suggestion engine
│   ├── microscopy_advisor.py      NOT YET — technique selector, public image repos
│   ├── proteomics_client.py       NOT YET — DDA/DIA workflow, PRIDE/STRING queries
│   └── flow_cytometry_advisor.py  NOT YET — panel design, FCS import
│
├── regulatory_engine/
│   ├── iso10993_assessor.py       BUILT — ISO10993Assessor(comptox, aop, admet)
│   ├── device_classifier.py       BUILT — Class I/II/III + ATMP detection
│   ├── pathway_mapper.py          BUILT — FDA/CE/ATMP timeline + milestones
│   ├── biocompat_scorer.py        BUILT — composite 0-100 (40% CompTox + 30% ADMET + 30% AOP)
│   └── combination_products.py    BUILT — drug-device + ATMP combo rules
│
├── tox_engine/                    BUILT — all 8 files (new module, added this session)
│   ├── mcp_client.py              BUILT — MCPClient.call_tool(), MCPError, MCPToolResult
│   ├── server_manager.py          BUILT — ToxServerManager, 4 ServerConfig entries
│   ├── admet_client.py            BUILT — predict_admet(smiles), render_structure()
│   ├── comptox_client.py          BUILT — lookup_by_name(), screen_material_components()
│   ├── aop_client.py              BUILT — map_chemical_to_aops(), search_aops()
│   ├── pbpk_client.py             BUILT — load_model(), set_parameter(), run_simulation()
│   ├── iso10993_assessor.py       BUILT — wraps regulatory_engine version + MCP enrichment
│   ├── biocompat_scorer.py        BUILT — wraps regulatory_engine version + MCP enrichment
│   └── workers.py                 BUILT — ADMETWorker, CompToxWorker, AOPWorker,
│                                          ISO10993Worker, BiocCompatScorerWorker,
│                                          ServerHealthWorker
│
├── ai_engine/
│   ├── llm_client.py              BUILT — Claude primary, GPT-4o fallback
│   ├── prompt_templates.py        BUILT — all prompts, editable, versioned
│   ├── knowledge_card_gen.py      BUILT — material knowledge cards
│   ├── briefing_gen.py            BUILT — Technical + Executive briefings
│   ├── paper_summariser.py        NOT YET — per-paper summaries
│   └── biocompat_predictor.py     NOT YET — structural analogy reasoning
│
├── briefing_engine/               BUILT — new module
│   ├── context_assembler.py       BUILT — BriefingContext, ContextAssembler (8 harvesters)
│   ├── briefing_generator.py      BUILT — 10 Technical + 10 Executive sections
│   └── __init__.py                BUILT
│
├── business_intelligence/         BUILT — full module
│   ├── market_kb.py               BUILT — 7 hardcoded MarketSegment entries
│   ├── stakeholder_kb.py          BUILT — 14 Stakeholder entries, typically_missed flags
│   ├── swot_engine.py             BUILT — SWOTAnalysis, SWOTEngine (versioned)
│   ├── strategic_summary.py       BUILT — StrategicSummaryEngine, 5 audience modes
│   └── __init__.py                BUILT
│
├── synthetic_biology_engine/      NOT YET BUILT
│   └── (see architecture detail below)
│
├── data_manager/                  BUILT — project context, DB, CRUD
│   ├── database_manager.py        BUILT
│   ├── project_context.py         BUILT — ProjectContext dataclass
│   └── crud.py                    BUILT
│
└── utils/
    ├── config.py                  BUILT
    ├── visualisation.py           NOT YET — shared Plotly/Matplotlib helpers
    └── export.py                  NOT YET — PDF, MD, PNG/SVG export
```

---

## UI Tab Structure

Status codes: BUILT = exists and wired | PARTIAL = exists, some sub-tabs stubbed | NOT YET = not started

```
Main Window (main_window.py — BUILT)
├── Literature Analysis            literature_tab.py — BUILT
│   ├── Search                   (global topic search, real PubMed)
│   ├── Paper Detail             (abstract, AI summary, extract data)
│   ├── PDF Inbox                (watched folder, DOI paste)
│   └── Annotations              (your notes, tags, links to KB)
│
├── Researcher Network             researcher_network_tab.py — BUILT
│   ├── My Network               (graph view + researcher list)
│   ├── Feed                     (new papers from tracked researchers)
│   └── Discover                 (network expansion wizard — post hackathon)
│
├── Materials Modeling             materials_tab.py — BUILT
│   ├── Topic Tree               (navigate material taxonomy)
│   ├── Knowledge Card           (AI-generated, editable, confidence tiered)
│   ├── Comparison               (radar charts, tables)
│   └── Fabrication              (method compatibility matrix)
│
├── Business Intelligence          business_tab.py — BUILT (6 sub-tabs)
│   ├── Market Analysis          (7 segments, tissue filter, metric cards)
│   ├── Competitive              (add competitors, stage-coloured table, syncs SWOT)
│   ├── Stakeholders             (14 types, commonly-missed filter, engagement strategy)
│   ├── SWOT                     (4-quadrant, stakeholder-lens selector, add item)
│   ├── Patents                  (Google Patents + Espacenet links, manual tracker)
│   └── Strategic Insight        (Claude synthesis, 5 audience modes, HTML output)
│
├── Bio Analysis                   bio_analysis_tab.py — BUILT
│   ├── Transcriptomics          (GEO query, volcano, heatmap — bulk)
│   ├── Single Cell              (CELLxGENE, UMAP, clustering, diff abundance)
│   ├── Sequencing Advisor       (NOT YET — technology selection)
│   ├── Metabolomics             (NOT YET — pathway overlay, PCA/UMAP)
│   ├── Multi-Omics              (NOT YET — MOFA integration)
│   ├── Proteomics               (NOT YET — DDA/DIA, protein corona, STRING PPI)
│   ├── Flow Cytometry           (NOT YET — panel design, phospho-flow)
│   └── Tissue Interaction       (NOT YET — response timeline, Matrigel caveat)
│
├── Drug Delivery                  drug_tab.py — BUILT
│   ├── Drug Lookup              (PubChem/ChEMBL/DrugBank)
│   ├── Release Kinetics         (PK model curves, Level 1-3)
│   └── Material Compatibility   (drug-material pairing, combination flag)
│
├── Regulatory                     regulatory_tab.py — BUILT (5 sub-tabs)
│   ├── Device Classifier        (Scenarios A/B/C/D, FDA class, ATMP flag)
│   ├── ISO 10993                (required test matrix; enriched by live MCP clients)
│   ├── Biocompat Score          (0-100 composite; enriched by live MCP clients)
│   ├── Pathway Timeline         (milestone cards, duration, cost)
│   └── AI Narrative             (Claude 4-5 paragraph regulatory strategy)
│
│   NOTE: ISO 10993 Assessor and BiocCompatScorer accept live tox_engine clients.
│   When ToxTab MCP servers are running, scoring is enriched automatically.
│   When servers are offline, graceful degradation to rule-based defaults.
│
├── Experimental Design            experimental_tab.py — BUILT (5 sub-tabs)
│   ├── Design Wizard            (tissue/scenario/resources → staged roadmap cards)
│   ├── Cell Models              (filterable table, detail panel)
│   ├── Organism Models          (filter by 3Rs/ISO/size/tissue, detail panel)
│   ├── DBTL Tracker             (phase-coloured table, Add/Advance/Results/Learning)
│   └── AI Advisor               (Claude analyses roadmap + DBTL history)
│
├── Toxicology                     tox_tab.py — BUILT (5 sub-tabs) [NEW]
│   ├── Server Control           (start/stop 4 MCP servers, health polling, bulk actions)
│   ├── CompTox                  (EPA chemical hazard, risk tier, GHS, NOAEL/OPERA)
│   ├── ADMET                    (from SMILES, 30+ endpoints, toxicity flags, SVG render)
│   ├── AOP                      (AOP-Wiki, MIE → Key Events → Adverse Outcome chain)
│   └── PBPK                     (OSP Suite .pkml, param editor, PK curve + metrics)
│
│   KEY ARCHITECTURE:
│   - ToxServerManager singleton (get_tox_manager()) shared across app
│   - ToxTab.get_live_clients() returns {comptox, admet, aop} for running servers
│   - RegulatoryTab wired via set_tox_tab(tox_tab) — live clients injected automatically
│   - MCP servers: admet:8082, comptox:8083, aop:8084, pbpk:8085
│   - CompTox requires EPA_COMPTOX_API_KEY env var (others need no key)
│   - closeEvent on MainWindow stops all MCP server subprocesses cleanly
│
└── Briefing Generator             briefing_tab.py — BUILT (flagship)
    ├── Mode toggle              (Technical / Executive radio buttons)
    ├── Section checklist        (10 sections each, All/None buttons)
    ├── Context panel            (editable QPlainTextEdit, full assembled context)
    ├── Live Output              (QTextEdit, sections append as generated)
    └── Export                   (Markdown / HTML / plain text via QFileDialog)

    KEY ARCHITECTURE:
    - BriefingWorker generates sections one at a time, cancellable via QMutex
    - ContextAssembler.assemble() harvests from all 8 modules (all in try/except)
    - set_live_objects(swot, roadmap, dbtl) passes in-memory objects from other tabs
    - _markdown_to_html() built-in converter, no external deps
```

---

## Researcher Network — Detail

### Three Input Modes
1. Manual add (one-by-one) — type name, search PubMed/ORCID, confirm
2. Bulk import — paste list or upload CSV, batch resolve, confirm table
3. Network discovery — separate BFS process (post day-one)

### Researcher Data Model
```
name              (required to start)
pubmed_query      (auto: "Malda J[au]")
orcid             (optional — golden standard, auto-lookup)
institution       (optional)
google_scholar_id (optional)
tags              (list — e.g. ["biofabrication", "netherlands"])
group/cluster     (e.g. "Dutch Biofab Network")
added_date
last_synced
paper_count
```

### Network Discovery (BFS)
- Controlled breadth-first search on co-author graph
- User sets: hops (1-2), time window, minimum co-authorship count
- Runs as background job with progress indicator
- Produces review table — user approves before anything is added
- Co-authorship stored in edge table in SQLite for graph viz

### Key Researchers (pre-configured)
- Jos Malda — UMC Utrecht, maldalab.org
  Focus: musculoskeletal biofab, cartilage, MEW, volumetric bioprinting
  Recent: Nature 2025 (GRACE), Advanced Healthcare Materials 2025

- Riccardo Levato — UMC Utrecht, levatolab.eu
  Focus: GRACE technology, light-based VBP, pancreas bioprinting
  Recent: Nature 2025 (GRACE co-author), ERC Consolidator Grant (pancreas)

- Miguel Castilho — TU/e Eindhoven
  Focus: Xolography, computational scaffold design, bone regeneration
  Recent: Advanced Materials 2025 (Xolography)

These three form one interconnected Dutch biofabrication cluster.
Dominant 2025 theme: volumetric bioprinting (GRACE + Xolography).
Synthetic biology connection: living materials convergence anticipated.

---

## Literature Engine — Detail

### PDF Pipeline
- User downloads PDFs with institutional access (no scraping needed)
- App watches data/papers/inbox/ folder — auto-matches PDF to paper by title/DOI
- Alternatively: drag PDF onto paper entry in app
- Extraction: pdfplumber or pymupdf (better than PyPDF2)
- Full text sent to Claude for structured fact extraction

### DOI Client
- CrossRef API (free, no key) — metadata from DOI: title, authors, journal, references
- Unpaywall API (free) — checks for legal open-access PDF before manual download
- Resolves DOI -> PMID for PubMed linking

### Knowledge Extraction Flow
User clicks "Extract Data" on a paper ->
Claude reads abstract (or full text if PDF available) ->
Returns structured facts: material, concentration, cell model,
viability, stiffness, key finding, limitations ->
User reviews and confirms ->
Confirmed facts propagate to: Materials KB + Biocompat Scorer +
Experimental Engine KB + Briefing pool

### Paper Annotation Schema
Each paper can carry:
- Extracted facts (AI, confirmed by user)
- Manual annotations (free text + tagged type)
- Links to: material, researcher, project
- Briefing flag (include in next briefing generation)
- Confidence tier (human-verified vs AI-extracted)

Knowledge propagation on confirmation:
  -> Materials KB (properties updated)
  -> Biocompat scorer (new data point, score recalculates)
  -> Experimental engine (new literature precedent)
  -> Researcher network (co-author graph updated)
  -> Briefing pool (available for next generation)

---

## Materials Engine — Detail

### Topic Tree (taxonomy)
```
Biomaterials
├── Metals
│   ├── Titanium & alloys
│   ├── Shape memory (Nitinol)
│   └── Biodegradable metals (Mg, Zn, Fe)
├── Polymers
│   ├── Synthetic (PEEK, PCL, PLGA, PLA, silicone)
│   ├── Hydrogels (PEG, GelMA, alginate, hyaluronic acid)
│   └── Smart/stimuli-responsive
├── Ceramics (HA, bioactive glass, zirconia, TCP)
├── Natural materials (collagen, fibrin, silk, chitosan)
├── Composites & hybrid
├── Carbon-based (graphene, CNT)
├── Soft Robotics & Actuators       MONITORING BRANCH ONLY
│   ├── Pneumatic actuators
│   ├── Shape memory polymers
│   ├── Dielectric elastomers
│   └── Hydrogel actuators
├── Living / Biofabricated Materials
│   ├── Bioinks
│   ├── Organoids
│   └── Decellularised ECM
└── Synthetic Biology Materials     MONITORING BRANCH (promotable)
    ├── Engineered protein materials (spider silk, recombinant collagen)
    ├── Biosynthesised polymers (PHA, PHB)
    └── Living material composites (cells + genetic circuits + scaffold)
```

### Topic Branch Types
- Deep branch: knowledge cards, fabrication compatibility, researcher tracking, full paper feed
- Monitoring branch: live paper feed + brief state-of-field card only
- Promotable: any monitoring branch can be promoted to deep by user action

### Knowledge Card Generation (AI)
Context assembled: material name + class + last 10 PubMed papers +
any properties from structured DB + user's project focus area.
Output sections: what it is / key properties with ranges /
current applications / fabrication compatibility /
frontier developments (last 12 months, grounded in papers only) /
open problems / limitations / key papers linked.
Flagged as AI-generated until human-verified.

### Fabrication Method Taxonomy
- Volumetric/light-based: GRACE, Xolography, Tomographic VBP
- Extrusion-based: FDM, bioprinting, coaxial extrusion
- Electrospinning/writing: MEW (Melt Electrowriting), electrospinning
- Inkjet: drop-on-demand, acoustic droplet ejection
- Laser-based: SLA, LIFT (Laser-Induced Forward Transfer)
- Self-assembly: organoids, spheroids, pre-built unit assembly
- Biological synthesis: fermentation, cell-free expression systems

---

## Biological Analysis Layer — Detail

### Four Layers Around a Material
1. Material Properties & Characterisation
2. Tissue Interaction (physical/chemical interface, dynamic over time)
3. Cellular Response (transcriptomics, metabolomics — bulk + single-cell)
4. Drug Delivery (payload + combined biological effect)

### Data Sources
- GEO (Gene Expression Omnibus) — bulk RNA-seq primary source
- ArrayExpress (EMBL-EBI) — European datasets, overlapping not identical to GEO
- CELLxGENE (Chan Zuckerberg) — single-cell, 50M+ cells, Census API
- Single Cell Portal (Broad) — organoid-specific single-cell datasets
- Human Cell Atlas — reference cell type composition per organ
- MetaboLights (EMBL-EBI) — public metabolomics datasets, queryable like GEO
- Metabolomics Workbench (NIH) — curated metabolomics studies, searchable API

### GEO / Bulk Transcriptomics
- Full dataset download + local analysis confirmed
- Cached in HDF5 format (data/geo_cache/)
- Background download thread, progress bar shown
- Pre-cache script for hackathon prep (run night before)
- Analysis: DEG (t-test, fold change, FDR correction), volcano plots, heatmaps
- Pathway enrichment: KEGG + Reactome

### Single-Cell Pipeline (Scanpy)
- QC filtering (dead cells, doublets)
- Normalisation + log transform
- PCA -> UMAP dimensionality reduction
- Leiden clustering
- Cell type annotation (CellTypist automated)
- Differential abundance (which cell types change in frequency)
- Differential expression per cell type
- Trajectory analysis (optional — differentiation path)

### Matrigel Baseline — Implementation
- Persistent caveat banner on all organoid/scaffold comparisons:
  "Baseline uses Matrigel (mouse-derived, batch-variable,
   clinically non-translatable). Treat as directional signal."
- App flags known Matrigel-response genes separately
- Where defined hydrogel comparisons exist in literature, surfaces as
  higher-quality reference alternative

### Organoid Knowledge Base (per organ type)
Each entry contains:
- Origin (tissue biopsy / iPSC)
- Key cell types + marker genes
- Standard matrix (Matrigel — caveat applied)
- Defined matrix alternatives
- Biomaterial relevance
- Fidelity to in vivo (what it captures, what it misses)
- GEO + CELLxGENE dataset counts
- Relevant researcher network connections
- Protocols.io links

### Organoid Necrotic Core — Critical Caveat

Diffusion limit: oxygen and nutrient penetration by passive diffusion is limited
to ~150-200 um from the organoid surface. Organoids >400-500 um diameter
develop a necrotic core — this is a physics problem, not a biology failure.

Data quality confounder: large static organoids introduce hypoxia gene signatures
(HIF-1alpha pathway, VEGF upregulation, glycolytic shift) that are artefacts of
culture conditions, not material response. App flags this when GEO dataset metadata
indicates static culture of large organoids.

Nutrient delivery strategies (surfaced by assay recommender):

  Tier 1 — Keep organoids small (serial passaging): no equipment, any lab,
            sacrifices maturity. Current standard.

  Tier 2 — Dynamic culture (spinner flask, orbital shaker, rotating wall vessel):
            improves surface exchange, slows necrosis onset, does not solve core
            diffusion. Low cost, any lab.

  Tier 3 — Microfluidic perfusion (organ-on-chip): continuous media flow.
            Mimetas OrganoPlate — passive gravity-driven flow in 384-well plate,
            no pump needed. Emulate Bio, CN Bio for active perfusion.
            Maintains viability weeks/months. GEO datasets from these exist.
            TARGET LEVEL FOR HACKATHON PROOF-OF-CONCEPT.

  Tier 4 — Vascularisation: HUVEC co-culture (self-assembling capillary networks),
            bioprinted vascular channels, MEW scaffold geometry.
            Research frontier — Malda/Levato group directly relevant.

  Tier 5 (future scale-up): hollow fibre bioreactor, bioprinted sacrificial
            channels (Pluronics fugitive ink), volumetric bioprinting for
            vascularised constructs (Levato).

  Supplementary: perfluorocarbon (PFC) emulsions as O2 carrier in media;
                 oxygen-releasing scaffold inclusions (peroxide-based).

Integration notes:
  - Experimental Engine: flag necrotic core risk for organoids >400 um,
    suggest Tier 3 for long-term viability experiments
  - Materials Engine: vascularisation as explicit scaffold design criterion —
    thick tissue constructs without vascularisation strategy flagged incomplete
  - Synthetic Biology: anti-apoptotic modifications (Bcl-2) and oxygen-sensing
    reporters as design options for organoid-use cells
  - Bio Engine: tag GEO datasets with culture condition (static vs perfused),
    surface as data quality indicator

Key biomaterial-relevant pathways to monitor in analysis:
- Inflammatory: NFkB, IL-6/JAK-STAT, TLR signalling
- Fibrosis/foreign body: TGF-beta, Wnt, YAP/TAZ
- Survival/apoptosis: p53, BCL-2, caspase cascade
- Proliferation: MAPK/ERK, PI3K/AKT, cell cycle
- Mechanosensing: YAP/TAZ, integrin signalling, focal adhesion
- Tissue-specific differentiation markers (tissue-dependent)

### Visualisations (all Plotly, interactive, individually exportable)
- Stress-strain curves, degradation profiles
- Radar/spider charts (material comparison)
- Timeline plots (tissue response)
- Heat maps (multi-material vs multi-tissue)
- Volcano plots (DEGs)
- Pathway enrichment bar charts
- GO term enrichment
- PCA/UMAP (bulk metabolomics + single-cell)
- UMAP coloured by cell type / condition (single-cell signature plot)
- Split UMAP (biomaterial vs Matrigel side-by-side)
- Dot plots (marker gene expression per cluster)
- Differential abundance bar charts
- Release kinetics curves (drug delivery)
- Metabolite PCA plots, pathway overlay heatmaps
- Multi-omics factor plots (MOFA latent factors)
- Protein abundance volcano plots
- Protein corona heatmap (adsorbed proteins by material)
- PPI network graph (networkx -> Plotly, hub nodes highlighted)
- Phosphosite occupancy bar charts
- Matrisome category breakdown (fibrous / glycoproteins / regulators)
- Integrin heterodimer + ECM ligand binding matrix
- Flow cytometry population bar charts + UMAP/tSNE (FlowSOM output)
- Phospho-flow signalling state bar charts (pFAK, pYAP, pERK)

---

## Analytical Technologies & Assay Recommendation Engine — Detail

### Purpose
Given a research question and project context, recommend the appropriate analytical
platform, explain what it yields, flag cost and accessibility, and link to public
datasets. Lives in both Experimental Engine (assay_recommender.py) and Bio Analysis
tab (sequencing_advisor.py, metabolomics_client.py, multiomics_integrator.py).

### Sequencing Technology Selector

10x Genomics Chromium (short-read Illumina):
  Best for: cell type composition, gene expression per cell type, material-induced
  cell state shifts. Most GEO/CELLxGENE data is this format.
  Limitation: 3' counting, misses isoforms, cannot detect RNA modifications.

Oxford Nanopore (ONT) — direct RNA sequencing:
  Best for: isoform discovery, alternative splicing, RNA base modifications
  (m6A methylation, pseudouridine). Full-length transcripts, no PCR bias.
  MinION is USB-sized — relatively accessible.
  Biomaterials angle: detects whether material induces alternative splicing
  in stress response genes — short-read entirely misses this.

PacBio HiFi (Iso-Seq):
  Best for: high-accuracy long reads, definitive isoform atlas.
  More expensive than ONT, larger instrument. Likely overkill for most questions.

Spatial Transcriptomics — most directly relevant to biomaterials:
  10x Visium: gene expression mapped to spatial position in tissue section.
  Can show which genes are expressed at scaffold-tissue interface vs 500 um away.
  10x Xenium / Nanostring CosMx: in situ, single-cell resolution, targeted panel.
  Public datasets appearing on GEO. App surfaces these when available for tissue type.

Single-cell ATAC-seq / Multiome (RNA + ATAC):
  Best for: chromatin accessibility, transcription factor activity.
  Relevant when material suspected to alter epigenetic state.

Technology decision logic (Claude-generated):
  "Which genes are changing?"  -> bulk RNA-seq or scRNA-seq
  "WHERE in the tissue?"       -> spatial transcriptomics (Visium/Xenium)
  "Full-length isoforms?"      -> ONT direct RNA or PacBio Iso-Seq
  "Chromatin accessibility?"   -> ATAC-seq or Multiome
  "What metabolites?"          -> LC-MS (untargeted) or GC-MS

### Metabolomics Platforms

GC-MS: volatile/semi-volatile metabolites, fatty acids (FAMEs), amino acids
  (derivatized), TCA cycle intermediates. Well-established libraries (NIST, Golm).
  Biomaterials: scaffold degradation products, membrane fatty acid changes.
  Accessible at most analytical chemistry core facilities.

LC-MS / LC-MS/MS: most powerful untargeted metabolomics platform.
  RP-LC: lipids, drugs, hydrophobic metabolites.
  HILIC: polar metabolites, sugars, nucleotides, amino acids.
  Running both covers most of the metabolome.
  Instruments: Thermo Orbitrap (Q Exactive, Exploris), Bruker timsTOF.
  Biomaterials: drug release quantification, inflammatory mediators
  (prostaglandins, leukotrienes), degradation product identification,
  full metabolic rewiring after material contact.

HPLC-UV/fluorescence: targeted, simpler, cheaper. Standard assay for drug
  release studies from scaffolds. Most biomedical labs have one.

NMR Metabolomics: quantitative, non-destructive, no chromatography needed.
  Good for abundant metabolites (lactate, glucose, glutamine, acetate).
  Accessible at most university NMR facilities.

Simple proxy (suggest as first-pass): lactate/glucose ratio in conditioned media
  measured with basic bench analyser. Shift to aerobic glycolysis (Warburg effect)
  is a cheap early warning before committing to full LC-MS.

### Metabolomics Databases
- HMDB (Human Metabolome Database): metabolite identity, biological roles,
  normal concentrations — primary reference for compound identification
- METLIN: MS/MS spectral library for mass spec compound identification
- MetaboLights (EMBL-EBI): public metabolomics datasets — queryable like GEO
- Metabolomics Workbench (NIH): curated metabolomics studies, searchable API
- LIPID MAPS: lipid database and lipidomics datasets
- Golm Metabolome Database: GC-MS spectral reference library

### Multi-Omics Integration
MOFA (Multi-Omics Factor Analysis): decomposes variation across data layers
  into shared latent factors. Identifies coordinated transcriptome/metabolome
  shifts from material exposure.
MixOmics (R package): PLS-based integration. Widely used in biomaterials.
KEGG joint pathway enrichment: overlay DEGs + differential metabolites onto
  same pathway. Both enzyme mRNA and substrate/product changing = confident
  pathway activity. Removes transcriptomic ambiguity.

### Assay Recommender Decision Logic
Claude reads project context (cell type, material, question, budget flag)
and outputs prioritised experimental stack with cost/equipment flags.

  "Is my material cytotoxic?"
  -> Live/dead staining (day 1, any lab)
  -> Lactate/glucose ratio (basic bench analyser, day 1)
  -> Bulk RNA-seq (stress response pathways, day 3+)

  "How is material changing cell identity?"
  -> scRNA-seq 10x Chromium
  -> Spatial transcriptomics if tissue section available

  "Is drug releasing correctly?"
  -> HPLC-UV (drug in media over time — field standard)
  -> LC-MS/MS (intracellular drug metabolites)

  "What metabolic pathways are active in scaffold-seeded cells?"
  -> Lactate/glucose first (cheap screen)
  -> NMR or GC-MS (primary screen)
  -> LC-MS untargeted (full picture)

  "Toxic degradation products?"
  -> GC-MS conditioned media
  -> LC-MS broad scan
  -> TNF-alpha, IL-6, IL-1beta panel (ELISA or Luminex)

  "Full mechanistic picture?"
  -> scRNA-seq + spatial + LC-MS + proteomics + MOFA integration
  -> Flag: multi-month programme, not day-one

---

## Drug Delivery Engine — Detail

### API Stack
- PubChem: compound lookup, MW, solubility, LogP, structure (free, no key)
- ChEMBL: bioactivity, targets, IC50, mechanism (free)
- DrugBank: half-life, protein binding, clearance, PK parameters (free academic)
- OpenFDA: approved drugs, adverse events (regulatory module feed)

### PK Model Levels
Level 1 — First-order release (day one):
  C(t) = C0 * e^(-k*t)

Level 2 — Biphasic release (day one):
  C(t) = A*e^(-alpha*t) + B*e^(-beta*t)

Level 3 — Higuchi diffusion model (day one):
  Q(t) = A * sqrt(D * (2*C0 - Cs) * Cs * t)

Level 4 — Compartmental with tissue distribution (post day one):
  Local depot -> tissue compartment -> systemic circulation

### Drug Query Flow
User selects material + drug ->
PubChem (compound data) ->
DrugBank (PK params) ->
ChEMBL (targets + mechanism) ->
PubMed ("material + drug + release") ->
PK model runs ->
Output: release curve + therapeutic window overlay +
        key drug facts + papers + combination product flag if applicable

---

## Experimental Design Engine — Detail

### Experimental Hierarchy (DBTL-aware)
1. In Silico (computational, PK modelling) — DESIGN phase
2. In Vitro Simple (immortalised cell lines, 2D) — TEST phase entry
3. In Vitro Complex (primary cells, co-cultures, 3D) — TEST phase
4. In Vitro Advanced (organoids, organ-on-chip, spheroids) — TEST phase
5. Ex Vivo (tissue explants, perfused organs) — TEST phase
6. In Vivo Model Organisms (zebrafish -> mouse -> rat -> large animal) — TEST phase
7. Clinical — TEST phase final

### Key Cell Models in KB
- HEK293: cytotoxicity screen, transfection, NOT tissue-specific
- HeLa: general toxicity, well-characterised, cancer-derived
- L929: ISO 10993 standard cytotoxicity cell line
- ARPE-19: RPE cell line (retinal applications)
- Primary human chondrocytes: cartilage biomaterials
- MSCs: osteogenic/chondrogenic differentiation, scaffold studies
- iPSC-derived RPE: retinal applications, functional readout
- Intestinal organoids: drug delivery, mucosal biomaterials
- Retinal organoids: ocular biomaterials
- Cardiac organoids: cardiovascular devices
- Brain organoids: neural biomaterials
- Pancreatic organoids/islets: endocrine delivery systems

### Key Organism Models in KB
- Zebrafish: toxicity screen, angiogenesis, not load-bearing
- Mouse C57BL/6: subcutaneous implant, calvarial defect, knee defect
- Mouse SCID/nude: human cell implants (immunocompromised)
- RCS rat: inherited RPE dysfunction (AMD model)
- Rat: spinal cord, peripheral nerve, cardiovascular, bone defect
- Sheep/goat: orthopaedic (joint size similar to human, load-bearing)
- Pig: cardiovascular anatomy, skin/wound healing
- Horse (equine): Malda lab model — veterinary + translational

### Roadmap Generation
Input: material + target tissue + existing evidence + available resources
Output: step-by-step experimental plan with:
  - Which model at each step (filtered to user's available resources)
  - Which assays and expected readouts
  - Why this step comes next
  - What each step validates from prior steps
  - DBTL cycle phase labelling (Design/Build/Test/Learn)
  - "Most informative single experiment" flag for sparse-data scenarios
  - Regulatory requirement mapping (which steps satisfy ISO 10993 tests)

---

## Regulatory Engine — Detail

### Four Regulatory Scenarios (auto-detected from project context)

Scenario A: Inert biomaterial scaffold
  -> Medical device pathway (Class I/II/III)
  -> Standard ISO 10993 battery
  -> FDA: 510(k) or PMA depending on class

Scenario B: Scaffold + drug payload (combination product)
  -> Drug-device combination
  -> PMA + CDER/CBER dual review
  -> Timeline: 7-12 years
  -> Flag early — shapes everything

Scenario C: Scaffold + engineered living cells (GMO cells in device)
  -> Advanced Therapy Medicinal Product (ATMP)
  -> Gene therapy / cell therapy regulatory pathway
  -> FDA: CBER (Center for Biologics), not CDER
  -> EU: EMA ATMP classification + certification scheme
  -> Significantly more complex than Class III device
  -> But: ATMP designation brings dedicated regulatory support +
          significant grant funding eligibility (EMA ATMP SME programme)
  -> Recommend: establish Scenario A safety first, add engineered
                cells in Phase 2

Scenario D: Engineered microorganism producing material component
  -> GMO regulations apply to manufacturing process only
  -> End product (purified material) may be GMO-free
  -> Much simpler than Scenario C
  -> Standard device pathway for the final product
  -> Manufacturing regulatory compliance separate concern

### Device Classification (Scenario A/B)
Class I: Low risk, surface contact, brief. General controls. 3-12 months.
Class II: Moderate, prolonged surface OR short-term implant. 510(k). 1-3 years.
Class III: High risk, permanent implant, life-sustaining. PMA + trials. 5-10 years.
Combination: PMA + CDER/CBER drug review. 7-12 years.

### ATMP Classification (Scenario C)
Gene therapy medicinal product: contains recombinant nucleic acid
Somatic cell therapy: cells substantially manipulated or non-homologous use
Tissue engineered product: cells/tissues to regenerate/repair/replace tissue
Combined ATMP: ATMP combined with medical device component
  -> This is your living scaffold scenario

### Breakthrough Device Designation (FDA)
- Available for: serious/life-threatening conditions +
                 substantial improvement over existing treatments
- Benefits: more frequent FDA interaction, prioritised review
- AMD regenerative approach: likely eligible
- App flags eligibility and explains application process

### ISO 10993 Biocompatibility Framework

Contact categories:
- Surface: intact skin / mucosal membrane / breached surface
- External communicating: blood path indirect / tissue/bone / circulating blood
- Implant: tissue/bone / blood

Duration: Limited (<24h) / Prolonged (24h-30d) / Permanent (>30d)

Required tests by contact type (stored as matrix in app):
Cytotoxicity, Sensitisation, Irritation, Systemic toxicity, Genotoxicity,
Implantation study, Haemocompatibility, Chronic toxicity,
Carcinogenicity, Reproductive toxicity

### Biocompatibility Scoring (Options B + C)
Confidence tier (always shown, per contact type + duration):
- 5 stars: User's own uploaded experimental data
- 4 stars: Published in vivo studies
- 3 stars: Published in vitro (primary cells)
- 2 stars: Published in vitro (cell lines only)
- 1 star:  AI structural analogy prediction (clearly flagged)
- 0:       No data, cannot assess

AI structural analogy reasoning (1 star):
- Assesses component materials separately
- Reasons about composite/combined behaviour
- Flags unexpected emergent properties
- States confidence level LOW/MEDIUM/HIGH
- Identifies "most informative single experiment to resolve uncertainty"

---

## Synthetic Biology Engine — Detail

### Four Integration Points with Biomaterials Platform

1. Engineered producers of biomaterial components
   E. coli / yeast producing: recombinant collagen, spider silk proteins,
   growth factors (BMP-2, VEGF, TGF-β), biodegradable polymers (PHA, PHB)
   Advantage: defined composition, batch consistency, no animal source

2. Living materials — cells with genetic circuits embedded in scaffolds
   Examples: inflammation-sensing + anti-inflammatory release circuits,
   mechanical load-sensing + ECM upregulation circuits,
   scaffold degradation reporter circuits (fluorescent readout in vivo),
   on-demand vascularisation circuits
   Regulatory: Scenario C (ATMP) — flagged automatically

3. Enhanced organoid/cell models
   Reporter cell lines, inducible differentiation circuits,
   isogenic disease variants via CRISPR (cleaner than patient-derived)

4. DBTL cycle framework
   Design-Build-Test-Learn explicitly tracked per project.
   App supports iteration history — shows how design improved across cycles.

### Queryable Sources
- iGEM Registry of Standard Biological Parts (parts.igem.org)
  20,000+ BioBrick parts, REST API, searchable by function/organism
  Relevant queries: "collagen", "ECM", "growth factor", "scaffold", "biosensor"

- iGEM Project Wikis
  Every iGEM team project publicly documented
  Contains: design, parts used, experimental results, protocols
  Source for working genetic circuits that have been tested

- SynBioHub (synbiohub.org)
  Genetic design repository, SPARQL endpoint
  Designs in SBOL format, linked to experimental results

- Addgene (addgene.org)
  200,000+ validated plasmid constructs, API
  Bridge from "found a design" to "can order and use in lab"

- JBEI ICE
  Metabolic engineering parts
  Relevant for engineered producers of biomaterial precursors

### DBTL Wizard Flow
Goal input: desired function (e.g., "cells that sense inflammation + release IL-10")
  -> Step 1: Choose sensing component (promoter) — search iGEM by function
  -> Step 2: Choose output component (coding sequence) — search by target molecule
  -> Step 3: Choose chassis organism — filtered to project resources
  -> Step 4: Regulatory flag — GMO cells in device? Scenario C triggered
  -> Step 5: Generate build protocol (protocols.io links)
  -> Step 6: Generate test plan (assays to validate circuit function)
  -> Step 7: Link to experimental roadmap (where in the DBTL cycle are we)

---

## Genetic Engineering Intelligence — Detail

Sub-module within Synthetic Biology Engine (genetic_editor.py + delivery_advisor.py).
Covers editing strategy selection — complementary to DBTL wizard (circuit design).

### Editing Technology Selector

Input: target gene + cell type + goal (KO / KI / activate / repress / base edit)
Reads project context (target tissue -> infers cell type + delivery constraints)

CRISPR-Cas9: standard knockout/knock-in, broad cell type support, most literature
  precedent. Creates double-strand break. Best for straightforward KO, stable integration.

Cas12a (Cpf1): preferred for A/T-rich regions, cleaner staggered cuts, lower
  off-target in some contexts.

Base editors (CBE/ABE): single base change (C->T or A->G) without DSB. Lower
  off-target profile, no donor template. Best for correcting known point mutations.

Prime editing (PE3/PE3b): precise insertion/substitution up to ~50bp via pegRNA.
  No DSB, no donor template. Best for small precise insertions, disease variant
  correction. More complex to design but increasing adoption.

CRISPRi/CRISPRa (dCas9-KRAB / dCas9-VPR): transcriptional repression or
  activation without permanent edit. Best for testing pathway importance before
  committing to permanent modification.

Cre/lox and Flp/FRT: conditional knockouts if floxed alleles are available.
  App checks if floxed mouse line exists in literature before suggesting CRISPR.

S. cerevisiae homologous recombination: ~100x more efficient than mammalian HR.
  Seamless gene replacement with 50bp homology arms — no Cas9 required.
  App defaults to HR for yeast, not CRISPR, when simple replacement suffices.

### Delivery System Recommender

  Primary neurons          -> AAV (serotype: AAV9, AAVrh10 for CNS)
  T cells                  -> Electroporation + RNP (no viral, minimal integration risk)
  Organoid / iPSC          -> LNP or lentiviral
  RPE cells (ocular)       -> AAV2, AAV5, or subretinal LNP
  CHO / HEK293             -> Lipofection or electroporation
  Primary hepatocytes      -> LNP (clinical precedent from mRNA therapeutics)
  Muscle cells             -> AAV6, electroporation
  Yeast                    -> Lithium acetate transformation
  E. coli                  -> Heat shock or electroporation

RNP delivery (ribonucleoprotein — pre-formed Cas9+gRNA protein complex):
  Now best practice for primary cells. Protein degrades after editing.
  Minimal integration risk. Preferred non-viral clinical-grade option.

LNP (lipid nanoparticle): current gold standard for mRNA and CRISPR delivery.
  Moderna/BioNTech validation provides regulatory credibility. Preferred for
  non-viral systemic or local delivery.

### Guide RNA Design Awareness
App does NOT run CRISPR design algorithms internally. Instead:
  - Accepts gene name or NCBI/Ensembl ID
  - Looks up exon coordinates via Ensembl REST API (guide placement context)
  - Links out to CRISPOR (web, trusted, no API key) for guide design
  - Links out to Cas-OFFinder for off-target screening
  - Searches Addgene for validated plasmids for that gene
  - PubMed search: "[gene] CRISPR off-target" to surface known problem loci

Regulatory flag: stable genomic integration -> Scenario C check triggered.
Transient/RNP delivery -> stays Scenario A or B.
Editing strategy output directly updates regulatory pathway detector.

### Additional Databases for Genetic Engineering
- Ensembl REST API: exon coordinates, transcript variants (guide placement)
- ClinVar: disease variants — know which variant you are targeting therapeutically
- BioGPS / GTEx: tissue-specific expression — confirm gene is expressed in
  target tissue before committing to editing strategy (prevents embarrassing recs)
- UniProt: protein function, known domains to avoid disrupting

### Regulatory Auto-Detection
App detects Scenario C when:
  - Experimental engine selects engineered/modified cells
  - Circuit designer produces a genetic circuit intended for in vivo use
  - Living materials layer connects a circuit to a scaffold design
  Triggers: ATMP pathway display in regulatory engine
            Warning: "Engineered living cells in implantable device
                      triggers ATMP classification. Significant
                      additional regulatory complexity."

---

## Bioproduction Planning — Detail

Sub-module within Synthetic Biology Engine (bioproduction_planner.py).
Covers production system selection, bioreactor type, scale, process mode,
upscaling constraints, and cost for any synthetic biology production proposal.

### Production System Recommender

First branch: is the protein glycosylated?

Non-glycosylated (insulin, GH, ELPs, spider silk, collagen fragments):
  -> E. coli or S. cerevisiae. Cheaper media, faster runs.
  -> E. coli inclusion bodies common at high expression — refolding step
     can destroy 50-80% of yield. Factor into cost estimate.

Glycosylated — glycosylation decorative (yield/solubility not function):
  -> Yeast acceptable. GlycoFi/Merck engineered P. pastoris for humanised glycans.

Glycosylated — glycosylation is functional (EPO half-life, antibody effector,
hormone receptor binding):
  -> CHO mandatory. HEK293 for transient smaller-scale production.

Biomaterials-specific production:
  Recombinant collagen   -> E. coli + co-expressed prolyl hydroxylase
                            (required for hydroxylation and thermal stability)
  Spider silk proteins   -> E. coli (Bolt Threads, Spiber, AMSilk precedent)
  Elastin-like peptides  -> E. coli (simple, thermoresponsive)
  BMP-2 / BMP-7         -> CHO mandatory (Medtronic InFuse = CHO-derived BMP-2
                            in collagen sponge — FDA-approved, direct precedent)
  VEGF                   -> CHO preferred for full activity
  FGF2, EGF             -> E. coli acceptable (minimal glycosylation)
  Hyaluronic acid        -> Bacterial fermentation (Streptococcus or engineered
                            B. subtilis/E. coli — most pharma-grade HA now uses this)

### Scale Ladder

  Screening    10-250 mL    Any university lab          Shake flask, Ambr micro-bioreactor
  Process dev  1-10 L       University / small biotech  Bench-top STR
  Pilot        50-500 L     Specialist CRO              Pilot STR or wave bioreactor
  Clinical     500-2,000 L  CMO                         Single-use bioreactor (SUB)
  Commercial   2,000-25k L  CMO or large pharma         Stainless steel STR

For hackathon context: team is at screening/bench-top level.
App flags when proposed organism requires infrastructure beyond this and
routes to CMO options with cost range estimates.

### Bioreactor Type by Organism

Microbial (E. coli, yeast): stirred tank fermenter, sparger aeration.
  High oxygen demand — kLa is the limiting factor at scale.
  Cheap media ($1-10/L E. coli). Fast doubling (~20 min). Runs: days.

Mammalian (CHO, HEK293): shear sensitive — impeller tip speed critical,
  bubble bursting damages cells. CO2/O2 balance required.
  Expensive media ($100-500/L serum-free). Slow (~24h doubling). Runs: 10-21 days.
  Single-use bags dominant at clinical scale.

Insect cells (Sf9, Hi5 — baculovirus): intermediate shear tolerance.
  Different glycosylation (no sialic acid). VLP vaccine production.

### Single-Use vs Stainless Steel

Single-use (SUBs): disposable pre-sterilised bags. No CIP/SIP. Faster turnaround,
  lower contamination risk. Dominant up to ~2,000 L. Higher per-batch cost.

Stainless steel: required above ~2,000 L. High CapEx, lower per-batch cost at scale.
  CIP/SIP required between batches. Standard for commodity biologics.

### Process Modes

Batch: simple, lower titre.
Fed-batch: feeds over time to push titre. Most common (mAbs, structural proteins).
  Starting point for E. coli production of recombinant proteins.
Perfusion: continuous product removal and media addition. Complex.
  Reduces batch-to-batch variability (regulatory advantage). Emerging standard.

### Key Upscaling Challenges
- kLa (oxygen transfer rate): largest constraint. Larger vessel = worse O2 supply.
  Microbial systems hit this hardest.
- Mixing time: non-linear with volume. Nutrient gradients appear at scale
  that are invisible at 2L. E. coli near feed port sees high glucose (acetate
  production); cells away see starvation.
- Heat removal: metabolic heat cannot dissipate through jacket alone above ~500L.
- Shear gradients: impeller tip speed vs bulk — CHO damage not seen at bench scale.

### Cost Structure (rough order of magnitude)
  Media cost/L:       E. coli $1-10     CHO $100-500
  Run duration:       E. coli 1-3 days  CHO 10-21 days
  DSP % of total:     E. coli 30-50%    CHO 50-70%
  CMO cost/gram:      E. coli $50-500   CHO $500-5,000+

### GMP Flag
Clinical trial or patient-use material requires GMP certification at production site
(ICH Q7/Q10, 21 CFR 210/211). Research lab CANNOT supply clinical material
without this. Step-change in cost and complexity. App surfaces this flag prominently —
investors routinely underestimate this transition.

### Tissue Engineering Bioreactors (separate from protein production)

Perfusion bioreactors for scaffolds: media flows through porous scaffold.
  Required for thick constructs (diffusion limits O2 to ~200 um without perfusion).
  Used for: bone/cartilage, cardiac patches, liver tissue engineering.

Rotating wall vessels (RWV): NASA-developed, low shear, simulated microgravity.
  Good for organoids and spheroids. Synthecon systems.

Hollow fibre bioreactors: media through fibres = synthetic vasculature geometry.
  High cell density. Used for CAR-T and exosome/EV production.

EV/exosome bioreactors: stem cell-derived EVs loaded into scaffolds for
  paracrine therapeutic effects. Hollow fibre + TFF. Emerging 2025 topic.

---

## Imaging & Microscopy Intelligence — Detail

Sub-module within Experimental Engine (microscopy_advisor.py).
Covers technique selection, sample preparation, what each technique yields,
and links to public image databases. Biomaterials-focused throughout.

### Electron Microscopy

SEM (Scanning Electron Microscopy):
  Surface morphology, scaffold architecture, pore geometry, cell attachment.
  Standard SEM requires dry, conductive samples — cells must be fixed/dehydrated,
  which introduces artefacts. App flags this for cell-on-scaffold samples.

  ESEM (Environmental SEM): humid chamber, no coating required. Hydrated samples
  including hydrogels and live cells possible. Lower resolution than standard SEM.

  FE-SEM (Field Emission SEM): higher resolution, better low-kV performance.
  Better for nanostructures and polymer nanofibers (electrospun, MEW).

  Cryo-SEM: sample vitrified, imaged at cryogenic temperature. Preserves hydrated
  state. Gold standard for hydrogel microstructure — not accessible in all labs.

  EDS/EDX (Energy Dispersive X-ray): elemental composition overlay on SEM image.
  Confirms presence of calcium/phosphate in HA coatings, titanium in alloys.

TEM (Transmission Electron Microscopy):
  Internal structure, ultrastructure, cross-sections, nanomaterial characterisation.

  Standard TEM: fibril spacing in collagen scaffolds, cell organelle response.
  Sample must be ultrathin (80-100 nm resin sections). Fixation artefacts apply.

  Cryo-TEM: vitrified, no staining. Gold standard for nanoparticles, LNPs,
  vesicles, protein assemblies. Can image liposome internal structure.
  Biomaterials angle: LNP drug delivery vehicles, protein corona morphology.

  STEM + HAADF: mass-contrast imaging of nanoparticles in tissue sections.

  EELS (Electron Energy Loss Spectroscopy): chemical bonding information.
  Can distinguish oxidation states of metals in degrading implants.

### AFM (Atomic Force Microscopy)

Surface topography at nanoscale. Can be done in liquid (physiological conditions).

Force spectroscopy: indent cell or hydrogel surface, measure force-displacement.
  Extract local Young's modulus. Biomaterials: spatial stiffness maps of composite
  scaffolds, compare gelatin vs crosslinked GelMA. Relevant to YAP/TAZ mechanosensing
  studies — match matrix stiffness to what transcriptomics shows.

Peak Force QNM mode: simultaneous topography + modulus + adhesion maps.
  Can reveal protein adsorption layers (early protein corona characterisation).

### Optical Microscopy

Confocal CLSM (Confocal Laser Scanning Microscopy):
  Optical sectioning via pinhole — rejects out-of-focus light.
  Z-stack -> 3D reconstruction. Standard for cell-scaffold imaging, live/dead,
  cytoskeletal organisation (phalloidin), nuclear morphology, marker co-localisation.
  Live imaging compatible (appropriate objectives + CO2/temp chamber).

  Spinning disk confocal variant: faster frame rate (less photobleaching).
  Preferred for live time-lapse — cell migration on scaffold over hours.

Two-photon / Multiphoton Microscopy:
  Near-IR excitation — deeper tissue penetration (~1 mm). Less phototoxicity.
  Endogenous signal modes (no labels required):
    SHG (Second Harmonic Generation): collagen fibril imaging. Label-free.
      Collagen I shows strong SHG; collagen IV does not. Discriminates fibril
      vs non-fibril collagen. CRITICAL for biomaterial ECM remodelling studies.
    THG (Third Harmonic Generation): lipid droplets, cell membranes.
  App flags SHG as the recommended first-choice for collagen-containing scaffolds.

FLIM (Fluorescence Lifetime Imaging Microscopy):
  Measures fluorescence lifetime, not intensity. Intensity is artifactually
  affected by concentration, scattering, photobleaching. Lifetime is intrinsic.
  NAD(P)H lifetime imaging: metabolic state mapping without extraction.
    Free NAD(P)H (short lifetime, ~0.4 ns) = glycolytic state.
    Protein-bound NAD(P)H (long lifetime, ~2.5 ns) = OXPHOS state.
  Warburg effect (glycolytic shift under material hypoxia) detectable in situ.
  App flags FLIM as complementary to metabolomics when spatial metabolic info needed.

Light Sheet Microscopy (LSFM / SPIM):
  Sheet of light illuminates one plane at a time. Very low photobleaching.
  Enables whole-organoid imaging in 3D at single-cell resolution.
  Requires tissue clearing for opaque samples.

  Tissue Clearing Protocols (app surfaces which to recommend by sample type):
    CLARITY: polyacrylamide embedding + detergent, preserves proteins and lipids.
    iDISCO: solvent-based, faster, preserves proteins, loses some lipids.
    CUBIC: aqueous, milder, good for organoids and soft tissues.
  App note: histology MUST precede spatial transcriptomics decisions —
  clearing and 3D imaging provides morphological context required to interpret
  spatial transcriptomic data.

Super-Resolution Microscopy (breaks ~200 nm diffraction limit):
  STED (Stimulated Emission Depletion): ~50 nm XY resolution.
    Good for integrin nanoclusters, focal adhesion organisation.
    High laser power — phototoxic for live samples.
  STORM/PALM: stochastic single-molecule localisation. ~20 nm resolution.
    Best for mapping nanoscale distribution of surface receptors.
    Fixed samples only (standard STORM/PALM).
  SIM (Structured Illumination Microscopy): ~100 nm, live-cell compatible.
    Lower resolution than STED/STORM but gentler — live cell dynamics.
  App recommends STORM/PALM for nanoscale receptor distribution on material surfaces.

Intravital Microscopy:
  Imaging through surgical window or thinned bone preparation in live animal.
  Can observe scaffold vascularisation in real time.
  Malda lab uses this for cartilage implant studies — directly relevant.

### Histology (prerequisite for spatial transcriptomics)
Standard H&E: morphology, cellularity, necrosis assessment.
Masson's Trichrome: collagen (blue), muscle (red), cytoplasm (pink).
Alcian Blue: proteoglycans — critical for cartilage biomaterial assessment.
Immunohistochemistry (IHC): protein localisation in tissue section.
App notes: histology should ALWAYS be performed on same sample batch as spatial
transcriptomics. Morphology + gene expression co-registration is the value.

### Public Image Databases
- BioImage Archive (EMBL-EBI): primary repository for bioimaging datasets,
  microscopy raw data, associated metadata. Free access.
- Image Data Resource (IDR): curated high-content screening, confocal, EM datasets.
  Linked to publications. Queryable.
- OMERO (Open Microscopy Environment): institutional image management platform.
  Many university core facilities run OMERO for image sharing.
- Allen Brain Atlas: brain region imaging (relevant for neural biomaterials).

### Technique Selection Decision Logic (Assay Recommender integration)

  "What does my scaffold look like at the nanoscale?"
  -> SEM (dry) — first choice for architecture
  -> Cryo-SEM if hydrogel microstructure matters
  -> AFM force mapping if mechanical gradients are the question

  "Are cells attaching and spreading?"
  -> Confocal CLSM (phalloidin/DAPI/vinculin)
  -> SEM for detailed surface contact morphology

  "Is collagen remodelled by cells in my scaffold?"
  -> Two-photon SHG (label-free, in scaffold, 3D)

  "What is the metabolic state of scaffold-seeded cells?"
  -> FLIM (NAD(P)H lifetime, spatial map)

  "Whole organoid at single-cell resolution?"
  -> Light sheet + tissue clearing (CUBIC or iDISCO)

  "Nanoscale receptor distribution on material surface?"
  -> STORM or PALM super-resolution

  "Where in the tissue are the scaffold-responding genes?"
  -> Spatial transcriptomics (Visium/Xenium) — always preceded by H&E

---

## Proteomics Intelligence — Detail

Sub-module within Experimental Engine (proteomics_client.py).
Covers proteomics workflow design, database queries, and protein-protein
interaction networks at the cell surface.

### Proteomics Workflow
Standard bottom-up proteomics:
  Protein extraction -> trypsin digestion (peptides) ->
  nanoLC separation -> mass spectrometry -> database search -> quantification

Instruments: Thermo Orbitrap (Q Exactive, Exploris, Astral — most sensitive),
  Bruker timsTOF Pro (PASEF mode, very high sensitivity, good for clinical samples).

### Data Acquisition: DDA vs DIA

DDA (Data-Dependent Acquisition):
  Instrument selects most abundant peptides to fragment — shotgun approach.
  Problem: missing values across samples (different peptides selected per run).
  Not ideal for quantitative comparison across many conditions.

DIA (Data-Independent Acquisition):
  All peptide precursors fragmented in defined mass windows — nothing missed.
  Missing value problem largely eliminated. Gold standard for quantitative work.
  App recommends DIA as default for biomaterial comparative proteomics studies.
  Tools: DIA-NN (free, GPU-accelerated), Spectronaut (commercial, widely used).

### Quantification Strategies
LFQ (Label-Free Quantification): compare protein intensity across runs.
  No chemical labelling cost. Suitable for any sample type. Slightly higher
  technical variance than labelled approaches.

TMT (Tandem Mass Tag): chemical labelling before LC-MS. 18-plex max.
  Multiple samples run together — eliminates run-to-run variation (same LC-MS run).
  Best for large-N experiments (e.g., 10+ conditions). Higher cost per sample.

SILAC (Stable Isotope Labelling by Amino Acids in Cell Culture):
  Metabolic labelling with heavy lysine/arginine. Cells grown in heavy media.
  Most accurate for cell culture comparisons. Cannot be used for tissue samples.
  Useful for: protein turnover studies (pulse-chase), secretome labelling.

### Proteomics Types (Biomaterials-Relevant)

Global discovery proteomics:
  Full cellular proteome after material contact. Identifies all protein changes.
  Complement to RNA-seq — post-translational regulation only visible at protein level.

Phosphoproteomics:
  Enrichment step: TiO2 or Fe-IMAC beads capture phosphopeptides.
  Maps active signalling: pFAK (integrin activation), pYAP/TAZ (mechanosensing),
  pSmad2/3 (TGF-beta), pERK (proliferation). Reveals how cells transduce material cues.

Secretome proteomics:
  Conditioned media analysis — what proteins are secreted by scaffold-seeded cells?
  Cytokines, growth factors, ECM components shed into media.
  Relevant for: paracrine signalling, inflammatory mediators, EV cargo analysis.
  Note: serum-containing media must be depleted before secretome analysis.

ECM proteomics (matrisome):
  Detergent-enrichment protocol to isolate ECM fraction. Identifies deposited ECM.
  The Matrisome Project (Naba lab) defines all ~300 ECM proteins and glycoproteins.
  Quantifies collagen I/III/IV ratio, fibronectin, laminin, proteoglycans.
  Direct readout of scaffold remodelling competence.

Surface proteomics (cell surface capture):
  Biotinylation of cell surface proteins -> streptavidin pulldown -> MS.
  Identifies which receptors and adhesion molecules are presented by cells
  growing on the material surface. Most relevant to integrin-ECM interaction studies.

Protein corona proteomics:
  Incubate material in serum/plasma, recover adsorbed proteins -> MS.
  The protein corona is the actual biological interface — what cells interact with,
  not the bare material surface.
  Hard corona: tightly bound, stable. Soft corona: dynamic, exchangeable.
  Key proteins to watch:
    Vitronectin, fibronectin: promote cell attachment via integrin binding
    Albumin: often anti-adhesive (passivates surface)
    Complement C3/C4/C5: activation triggers phagocytosis (opsonisation)
    Apolipoproteins: competitive binders, displace functional proteins
    IgG (immunoglobulins): opsonisation markers
    Fibrinogen: acute phase, promotes macrophage attachment
  App flags complement-activating corona compositions for immune response risk.

### Protein-Protein Interactions — Cell Surface Focus

This is critical for understanding how material-surface receptor expression
translates into intracellular signalling networks.

Integrin interaction networks:
  Integrins do not signal alone. Key complexes:
  - Integrin + CD47: "don't eat me" signal — prevents macrophage phagocytosis.
    Relevant for implant immune tolerance.
  - Integrin + tetraspanins (CD9, CD63, CD151): tetraspanin-enriched microdomains
    (TEMs) regulate integrin clustering, internalisation, and signalling strength.
  - Integrin + growth factor receptors (EGFR, VEGFR2, PDGFR): integrin-GFR
    crosstalk amplifies proliferation and survival signals.
  - Integrin + Piezo1: mechanosensitive ion channel, co-regulated with integrin β1
    in stiffness-sensing. Relevant for hydrogel stiffness studies.

Focal adhesion scaffold:
  Integrin (outside-in signal) ->
  Talin (direct integrin binder, mechanosensitive) ->
  Vinculin (force transducer) ->
  Paxillin -> FAK (tyrosine kinase, central hub) ->
  Src kinase -> downstream MAPK/ERK, PI3K/AKT, Rho GTPases
  App surfaces this cascade when focal adhesion proteins are detected as
  differentially expressed in transcriptomics.

YAP/TAZ (mechanosensing output):
  Stiff matrix -> LATS1/2 inhibited -> YAP/TAZ nuclear (transcriptional active).
  Soft matrix -> LATS1/2 active -> YAP/TAZ cytoplasmic/degraded.
  Nuclear YAP detectable by: FLIM (confocal nuclear vs cytoplasmic intensity),
  flow cytometry (phospho-YAP), immunostaining, proteomics (nuclear fractionation).

MMP interactions:
  MT1-MMP (MMP14) on cell surface complexes with TIMP2 and recruits MMP2.
  Primary mechanism for cell-mediated scaffold degradation in 3D.
  Surface proteomics can detect MT1-MMP expression level.

Complement receptor complexes (immunological interface):
  CR3 (CD11b/CD18) on macrophages binds complement-opsonised material.
  Combined with toll-like receptor signalling -> inflammatory cascade.
  Foreign body response mechanism — material corona complement activation
  -> CR3 recognition -> macrophage fusion -> giant cell formation.

How the app integrates PPIs:
  - STRING database query: input surface protein list (from proteomics or flow),
    output interaction network filtered to surface-annotated proteins (UniProt:
    cellular compartment = plasma membrane)
  - Network visualised in app (networkx -> Plotly network graph)
  - Hub proteins highlighted (high degree nodes = signalling integration points)
  - When DEGs include surface proteins: auto-cross-reference STRING for their
    known partners — are those partners also differentially expressed?
  - Integrin alpha/beta subunit combination matrix surfaced: which ECM ligand
    does the expressed integrin heterodimer bind? (links to Materials Engine
    ligand functionalisation recommendations)

### Proteomics Databases
- UniProt/Swiss-Prot: protein function, domains, PTMs, interactions (manually curated)
- Human Protein Atlas (HPA): tissue and cell-type expression (API available)
  Protein localisation images — confirm surface vs intracellular before
  designing pulldown experiment
- STRING (string-db.org): protein-protein interaction networks.
  API: get_interaction_partners(), get_network().
  Network score threshold: app defaults to high confidence (>0.7).
  Filters to plasma membrane proteins for surface interaction queries.
- PhosphoSitePlus: known phosphorylation sites, validated kinase-substrate pairs.
  App cross-references detected phosphopeptides against database.
- PRIDE Archive (EBI): public proteomics datasets (raw + processed).
  Searchable by tissue/organism — find existing scaffold proteomics datasets.
- Matrisome Project database: curated ECM protein annotations, used for ECM
  proteomics data interpretation.

### Analysis Tools
- MaxQuant: DDA quantification, LFQ, SILAC (free, widely used)
- Perseus: downstream statistical analysis of MaxQuant output (free)
- DIA-NN: DIA quantification, GPU-accelerated (free)
- MSFragger / FragPipe: fast DDA + DIA search, ptm discovery (free academic)
- STRING API: PPI network generation

### New Visualisations (Proteomics)
- Protein abundance volcano plots (same logic as DEG volcano, different data)
- Protein corona heatmap: material vs serum protein adsorption profile
- PPI network graph (networkx -> Plotly, hub proteins highlighted)
- Phosphosite occupancy bar charts
- Matrisome category breakdown (fibrous proteins, glycoproteins, regulators)
- Integrin heterodimer expression + ECM ligand matrix

---

## Flow Cytometry Intelligence — Detail

Sub-module within Experimental Engine (flow_cytometry_advisor.py) and
Bio Analysis tab (flow_data_processor.py).
Covers technique selection, panel design, biomaterials-specific applications.

### Technique Variants

Conventional flow cytometry (4-18 colours, suspension cells):
  High throughput, population statistics, not spatial data.
  Industry standard for immunophenotyping and cell viability.
  Accessible at virtually every university core facility.

Mass cytometry (CyTOF — Cytometry by Time-Of-Flight):
  Metal isotope-conjugated antibodies (40+ markers simultaneously).
  No spectral overlap — genuine 40+ parameter immunophenotyping.
  Gold standard for deep immune profiling of scaffold-explanted cells.
  Limitation: cells destroyed, cannot sort for downstream use.
  Higher cost, specialist instrument, not universally accessible.

Spectral flow cytometry (Aurora, Symphony A5):
  Full emission spectrum captured, computationally unmixed.
  30-40 channels, cells can be sorted. Bridges conventional and CyTOF.

FACS (Fluorescence-Activated Cell Sorting — physical cell separation):
  Sort live or fixed cells based on marker expression.
  Critical for:
    Downstream culture of purified subpopulations after material selection
    Sorted cell -> scRNA-seq library (cell-type-specific transcriptomics)
    Functional assays on pure populations (e.g., sorted macrophage phenotypes)

Imaging flow cytometry (ImageStream, Amnis):
  Flow throughput combined with brightfield + fluorescence images per cell.
  Detects morphological features and protein localisation:
    YAP/TAZ nuclear vs cytoplasmic translocation (mechanosensing readout)
    Cell-cell conjugates (T cell + target, macrophage + scaffold fragment)
    Nuclear morphology (apoptosis scoring without microscopy)
  App recommends ImageStream when spatial protein localisation is needed
  at population scale (not just a few fields in confocal).

### Biomaterials-Specific Applications

Viability panels (any lab, day 1):
  Live/dead gating: PI, DAPI, Zombie dyes (amine-reactive),
  Annexin V (early apoptosis), caspase-3/7 activation.
  First-pass cytotoxicity screen before committing to transcriptomics.

Surface receptor immunophenotyping:
  Integrin expression profile (αVβ3, α5β1, α2β1 — direct ECM receptor status).
  Upregulation/downregulation in response to material stiffness or ligand density.
  Flow confirms surface receptor presence before designing co-IP experiment
  for protein-protein interaction partners (integrates with proteomics module).

Phospho-flow (intracellular signalling):
  Fix + permeabilise + phospho-specific antibody staining.
  pFAK (integrin downstream), pYAP (mechanosensing state),
  pSmad2/3 (TGF-beta pathway activation), pERK (proliferation signal).
  Population-level signalling state — faster than Western blot for multiple conditions.
  Note: cells must be fixed (Cytofix/Cytoperm or methanol) — no downstream sorting.

Reactive oxygen species (ROS):
  DCFH-DA (general ROS), CellROX (mitochondrial), MitoSOX (mitochondrial superoxide).
  Material oxidative stress response — relevant for metal degradation products,
  reactive scaffold crosslinkers, photoinitiator residuals.

Cell cycle analysis:
  PI or DAPI (DNA content) for G0/G1/S/G2/M distribution.
  BrdU or EdU incorporation (S-phase cells actively synthesising DNA).
  Proliferation response to material vs Matrigel baseline.

Stem cell and differentiation markers:
  MSC identity: CD90+/CD105+/CD73+/CD45-/CD34-
  Endothelial commitment: CD31, CD34, VE-cadherin
  Chondrogenic: Col2A1, Sox9 (intracellular — permeabilisation required)
  Osteogenic: osteocalcin, Runx2 (intracellular)
  iPSC pluripotency: Oct4, Sox2, SSEA-4, TRA-1-81

ECM remodelling readout (flow-based):
  Surface MMP activity assays (FRET-peptide substrates)
  Collagen receptor expression (DDR1, DDR2 — discoidin domain receptors)
  Links to ECM proteomics module — confirms receptor expression complements
  secreted ECM protein composition data.

### Panel Design Logic (assay_recommender integration)
App recommends panel based on research question + cell type + available instruments.
  Priority order: fluorochrome-receptor pairing optimised for:
  - Antigen density (dim markers -> brightest fluorochrome, e.g. PE)
  - Spectral overlap constraints (tandem dyes last, avoid similar emission neighbours)
  - Viability dye always included in multicolour panel

### Data & Analysis
FCS file format (standard, all instruments).
Analysis tools:
  FlowJo — industry standard, manual hierarchical gating
  Cytobank — cloud platform, CyTOF/mass cytometry optimised
  FlowSOM — unsupervised clustering for high-dimensional panels (R package)
  UMAP/tSNE — dimensionality reduction (same tools as scRNA-seq but on protein data)
  OMIQ — cloud-based FlowJo alternative, good for publication-quality figures

Public repositories:
  FlowRepository (flowrepository.org): public FCS datasets, linked to publications
  ImmPort: NIH-funded immunology data, well-curated, flow-heavy

### Integration with Other Modules
- Flow surface receptor data -> STRING PPI query in proteomics module:
  "These receptors are expressed — what are their known interaction partners?"
- Phospho-flow signalling data -> complements RNA-seq pathway enrichment:
  "Pathway X enriched in RNA-seq; pFAK elevated in flow = convergent evidence"
- FACS sorted subpopulations -> scRNA-seq input:
  "Sort CD44hi/CD24lo population -> 10x scRNA-seq -> material-induced stem state"
- CyTOF deep immune phenotyping -> foreign body response characterisation:
  "Which macrophage subtypes (M1/M2/MHCII-hi) dominate at scaffold interface?"
- ImageStream YAP/TAZ localisation -> stiffness response confirmation:
  "Material stiffness prediction from YAP nuclear fraction across population"

---

## Toxicology Engine — Detail

Built as standalone tox_engine/ module. Four MCP servers + shared manager singleton.

### Server Architecture
ToxServerManager — singleton accessed via get_tox_manager() in tox_tab.py.
Each server is a local HTTP subprocess launched via Python -m <package> --port <n>.

  admet   port 8082  ADMETlab MCP   predict_admet(smiles), render_structure(smiles)
                                     No API key required. Absorption/Distribution/
                                     Metabolism/Excretion/Toxicity. 30+ endpoints.
                                     Toxicity flags: ames_mutagenicity, herg_inhibition,
                                     hepatotoxicity, skin_sensitization, eye_irritation, LD50.

  comptox port 8083  CompTox MCP    lookup_by_name(name), screen_material_components(list)
                                     EPA_COMPTOX_API_KEY required. Runs in demo mode without.
                                     Returns: ChemicalHazardProfile with risk_tier property,
                                     GHS codes, carcinogenicity, acute toxicity, NOAEL/LOAEL,
                                     OPERA predictions (log P, BCF, Henry's law, etc).

  aop     port 8084  AOP MCP        map_chemical_to_aops(chemical), search_aops(query)
                                     No API key required. AOP-Wiki Adverse Outcome Pathways.
                                     Returns: AOPMappingResult, AOPSummary, KeyEvent list.
                                     Full MIE → Key Events → Adverse Outcome chain.

  pbpk    port 8085  PBPK MCP       load_model(path), set_parameter(name, value),
                                     run_simulation(), run_population_simulation(n=100)
                                     sensitivity_analysis(), list_parameters()
                                     No API key required. OSP Suite PK-Sim .pkml models.
                                     Returns: SimulationResult with time_points, concentrations,
                                     pk_metrics (Cmax, Tmax, AUC, t_half, CL, Vd).

### Integration with Regulatory Engine
ISO10993Assessor(comptox=None, aop=None, admet=None):
  - Without clients: rule-based test matrix only
  - With clients: enriches with live chemical hazard flags + AOP concerns + ADMET alerts
  - regulatory_tab.ISO10993Worker passes live_clients from ToxTab.get_live_clients()

BiocCompatScorer(comptox=None, admet=None, aop=None):
  - Composite 0-100 score: 40% CompTox hazard + 30% ADMET + 30% AOP pathway burden
  - Without clients: defaults to mid-range score, clearly flagged
  - regulatory_tab.BiocompatWorker passes live_clients from ToxTab.get_live_clients()

### Pre-built QThread Workers (workers.py)
All workers take their client in __init__ and emit result_ready / error_occurred.
ADMETWorker(admet_client, smiles)
CompToxWorker(comptox_client, components: list)  — emits list of ChemicalHazardProfile
AOPWorker(aop_client, components: list)          — emits dict[str, AOPMappingResult]
ISO10993Worker(assessor, material, contact_type, contact_duration, components)
BiocCompatScorerWorker(scorer, material, components, drug_smiles=[])
ServerHealthWorker(manager)                       — emits dict[server_name, bool]

### Graceful Degradation
All clients are optional. Regulatory engine works without them.
ToxTab shows offline indicator (grey dot) when servers not running.
Enrichment activates automatically when servers come online — no manual intervention needed.

---

## Business Intelligence Engine — Detail

### Scope (confirmed)
- On-demand queries only (no active monitoring — Phase 2)
- Own IP strategy: Phase 2 (groundwork laid, not built yet)
- Pre-populated from project context (no manual query entry needed)

### Market Intelligence
Sources: PubMed (health economics papers), WHO/CDC (epidemiology),
         ClinicalTrials.gov (where market is heading),
         FDA 510(k)/PMA databases (what's approved = market validation),
         Public SEC filings (real revenue from public companies),
         Press releases (funding rounds, partnerships)
Output: market size + CAGR (sourced), segmentation relevant to application,
        addressable patient population, reimbursement landscape,
        adoption drivers and barriers

### Competitive Landscape
Sources: ClinicalTrials.gov API (primary — underused intelligence source),
         Crunchbase free tier (startup funding),
         Patent databases (overlaps with patent analysis)
Output: direct competitors / indirect competitors / adjacent players /
        academic groups (future competitors or acquisition targets)
        Structured table: company, approach, stage, funding, last update

### Patent Landscape
Sources: USPTO Patent Full-Text Database (free REST API),
         EPO Open Patent Services (free, registration required),
         Lens.org (aggregates both + scholarly literature, free API)
Output: patent clusters by assignee, timeline view (filed/granted/expiring),
        claim analysis, white space identification
AI layer: Claude identifies potential freedom-to-operate concerns +
          unpatented angles + suggested filing priorities
Own IP strategy: Phase 2 only

### ClinicalTrials.gov Integration
search_by_condition(), search_by_intervention(), get_trial_details(),
monitor_updates() (Phase 2)
Trial status changes = competitive intelligence signal

### Funding Intelligence
Sources: Crunchbase API (free tier, may lag 3-6 months),
         NIH Reporter (free API — all NIH grants),
         ERC database (EU grants — Levato grant example),
         CORDIS (all EU-funded research)
Output: VC activity, typical deal sizes by stage, active investors,
        M&A activity, grant landscape, strategic acquirer identification

### Stakeholder Mapping
Full stakeholder set (auto-generated, customisable per project):

Clinical: patients, surgeons/interventional specialists, referring clinicians,
          nurses/clinical staff, hospital procurement/device committees

Regulatory: FDA/EMA/MHRA, Notified Bodies (CE),
            Ethics committees/IRBs, HTA bodies (NICE, HAS, G-BA)
            NOTE: HTA bodies decide reimbursement separately from approval —
            critical and commonly overlooked

Payers: private insurers, national health systems (NHS, Medicare),
        hospital budget holders

Manufacturing: CMOs, raw material suppliers, sterilisation providers,
               packaging/cold chain logistics

Commercial: medical device distributors, hospital GPOs (US — control
            hospital system access), strategic partners/licensees

R&D: academic collaborators, CROs, core facilities, TTO (tech transfer office)

Investment: VCs/angels, grant bodies, strategic corporate investors, acquirers

Advocacy: disease charities, patient advocacy groups, clinical societies

Per stakeholder profile:
- Vested interest (primary + secondary + financial)
- What they care about (positive + negative + neutral assessment of your product)
- Key message for this stakeholder
- Engagement strategy

Stakeholder matrix output:
  Axes: Benefit / Risk-Concern / Influence / Urgency
  Immediately shows: who to engage first, who can block you, natural allies

Stakeholder-filtered SWOT lens:
  Same SWOT data, filtered through one stakeholder's perspective
  Generated per stakeholder on demand

### SWOT Generator
Principles:
- Every point specific, evidence-backed, quantified where possible
- Weaknesses section is honest — investors distrust sanitised SWOTs
- Each point linked to its source (paper, dataset, patent, competitor data)

Quadrant sources:
  Strengths   <- Materials Engine + Bio Engine + Regulatory Engine
  Weaknesses  <- Regulatory Engine + Biocompat Scorer + Experimental Engine
  Opportunities <- Business Intelligence (market, white space, funding, expiring patents)
  Threats     <- Business Intelligence + Regulatory Engine (competitors, IP, HTA)

Key Strategic Insight (AI-generated):
  Claude synthesises across all four quadrants:
  - Single most important strength to lead with
  - Single most important weakness to address first
  - Most credible opportunity
  - Most likely threat to materialise
  Output: one paragraph, not a list

SWOT versioning:
  Every generation saved + dated
  Compare SWOT v1 (pre-data) vs SWOT v2 (post-rat study) —
  shows how position strengthened over time

Stakeholder-filtered lens:
  Same SWOT filtered through individual stakeholder's vested interests
  Generated on demand per stakeholder

### Data Quality Transparency
All BI outputs show:
  Data quality: LOW / MEDIUM / HIGH
  Sources with known lag times
  Last updated date
  What's missing (private company data, undisclosed deals)

---

## AI Engine — Detail

### Briefing Document
Two modes (same underlying data, different prompt templates):

Technical mode (teammates):
- Dense, assumes domain knowledge
- Properties with numbers and ranges
- Fabrication details, limitations stated plainly
- Papers cited directly

Executive mode (investors/stakeholders):
- Opens with "why this matters now" (one sentence)
- Market/clinical context front-loaded
- No unexplained jargon
- Ends with opportunity framing
- Papers mentioned but not dwelt on

### Cross-Module Briefing (flagship feature)
Synthesises across all modules simultaneously.
Example "volumetric bioprinting for cartilage repair" pulls from:
  Literature + Materials KB + Researcher feed + Drug delivery +
  Experimental roadmap + Regulatory pathway + Business context +
  SWOT + Stakeholder map + Synthetic biology (if applicable)

Briefing sections (selectable):
  1. Executive summary
  2. Scientific rationale + evidence
  3. Material assessment + comparison
  4. Biological evidence (transcriptomics, organoid data)
  5. Drug delivery (if applicable)
  6. Experimental roadmap
  7. Regulatory pathway + timeline
  8. Competitive landscape
  9. Stakeholder analysis
  10. SWOT
  11. Market opportunity
  12. "What we still need to prove" (most valuable for investors)
  13. Sources

### Prompt Template Structure
Context: material/topic + class + recent papers + project context +
         depth (monitoring/standard/deep) + audience (technical/executive)
Constraint: grounded in provided papers only (prevents hallucination)
Requirement: sources listed in output, speculative content flagged

---

## Data Architecture

### SQLite Tables (planned)
- projects
  id, name, target_tissue, clinical_indication, resources_json,
  regulatory_class, markets, created

- papers
  pmid, doi, title, authors_json, journal, year, abstract,
  keywords_json, pdf_path, full_text_extracted, cached_date

- paper_annotations
  id, paper_id, project_id, annotation_type, content_json,
  linked_material_id, linked_researcher_id, confidence_tier,
  human_verified, created_date

- researchers
  id, name, orcid, pubmed_query, institution, group_id,
  google_scholar_id, tags_json, added_date, last_synced, paper_count

- researcher_groups
  id, name, description, project_id

- co_authorship
  researcher_id_a, researcher_id_b, paper_count, last_paper_year

- materials
  id, name, class, properties_json, biocompat_scores_json,
  fabrication_compat_json, last_reviewed, ai_generated, human_verified

- geo_datasets
  gse_id, title, organism, tissue, experiment_type,
  file_path, cached_date, analysis_complete

- geo_analyses
  id, project_id, gse_id, material, baseline, deg_count,
  results_path, top_pathways_json, created_date

- metabolomics_datasets
  id, source, accession, title, organism, tissue, platform,
  file_path, cached_date, culture_condition

- metabolomics_analyses
  id, project_id, dataset_id, material, differential_metabolites_json,
  pathway_enrichment_json, created_date

- assay_recommendations
  id, project_id, research_question, recommended_platforms_json,
  rationale, cost_flag, equipment_flag, created_date

- genetic_edit_designs
  id, project_id, target_gene, cell_type, editing_tool, delivery_method,
  guide_rna_notes, off_target_risk, regulatory_flag, created_date

- bioproduction_plans
  id, project_id, molecule, organism, bioreactor_type, scale,
  process_mode, cost_estimate_json, gmp_required, created_date

- proteomics_datasets
  id, source, accession, title, organism, tissue, acquisition_mode,
  quantification_method, file_path, cached_date

- proteomics_analyses
  id, project_id, dataset_id, material, differentially_expressed_proteins_json,
  protein_corona_json, phosphosite_hits_json, ppi_network_json, created_date

- flow_panels
  id, name, cell_type, markers_json, fluorochromes_json, instrument,
  acquisition_mode, project_id, created_date

- flow_analyses
  id, project_id, panel_id, gating_strategy_json, population_stats_json,
  phospho_data_json, linked_experiment_id, created_date

- drug_cache
  compound_id, source, name, data_json, cached_date

- drug_analyses
  id, project_id, compound, material, pk_level,
  pk_params_json, release_curve_data, combination_product_flag

- regulatory_assessments
  id, project_id, material, scenario, device_class, contact_type,
  duration, required_tests_json, biocompat_score,
  missing_evidence_json, combination_product, atmp_flag

- experimental_roadmaps
  id, project_id, material, target_tissue, steps_json,
  dbtl_cycle, version, created_date

- synbio_designs
  id, project_id, goal, parts_json, chassis, circuit_design_json,
  dbtl_phase, regulatory_flag, created_date

- stakeholder_analyses
  id, project_id, stakeholders_json, matrix_json, created_date

- swot_analyses
  id, project_id, version, strengths_json, weaknesses_json,
  opportunities_json, threats_json, strategic_insight,
  created_date

- briefings
  id, project_id, mode, content, modules_included_json,
  prompt_used, created_date

### Local File Storage
- data/geo_cache/            HDF5 expression matrices (bulk + single-cell)
- data/metabolomics_cache/   Cached metabolomics datasets from MetaboLights/Workbench
- data/proteomics_cache/     Cached proteomics datasets from PRIDE Archive
- data/flow_data/            FCS files and gating results
- data/papers/inbox/         Watched folder — PDF drop zone
- data/papers/processed/     PDFs after extraction, archived
- data/exports/              Generated briefings (PDF/MD), figures (PNG/SVG)
- data/user_projects/        Saved project files

---

## What Is NOT Yet Built

### Priority for next session
1. Synthetic Biology tab — iGEM/SynBioHub parts browser, DBTL wizard, living materials,
   genetic editor (editing strategy + delivery advisor), bioproduction planner
2. Assay Recommender — Claude-driven analytical technology suggestion by research question
3. Microscopy Advisor — technique selector, sample prep, public image repos
4. Proteomics Advisor — DDA/DIA workflow, protein corona, STRING PPI queries
5. Flow Cytometry Advisor — panel design, phospho-flow, FCS file import

### Post-hackathon / Phase 2
- Sequencing advisor (10x / ONT / PacBio / Spatial technology selection)
- Metabolomics viewer + MetaboLights client
- Multi-omics integration (MOFA/MixOmics)
- ArrayExpress, Single Cell Portal, Human Cell Atlas clients
- Network discovery (BFS co-author expansion)
- Bioproduction planner (bioreactor + scale + cost)
- ATMP pathway full detail (EMA ATMP SME programme, combined ATMP rules)
- Level 3-4 PK models (compartmental + tissue distribution)
- Full pathway analysis (KEGG/Reactome enrichment)
- Settings + Configuration tab (API key management, themes)
- Pre-cache script (GEO datasets + materials KB for hackathon)
- Own IP strategy (patent drafting suggestions)
- ClinicalTrials.gov monitoring feed
- Data Management UI (cache view, project export)

---

## Build Order — Completed vs Remaining

### COMPLETED (Steps 1-11 + Tox)
1.  [DONE] Fix __init__.py files — all submodules importable
2.  [DONE] PubMed search wired to Literature tab
3.  [DONE] Claude API client (llm_client.py) — Claude primary, GPT-4o fallback
4.  [DONE] Researcher Network tab — manual add, feed, network graph
5.  [DONE] Materials engine + AI knowledge cards
6.  [DONE] Bio engine — GEO client + bulk transcriptomics viz (volcano, heatmap)
            + CELLxGENE + Scanpy single-cell pipeline
7.  [DONE] Drug engine — PubChem/ChEMBL/DrugBank + Level 1-3 PK models
8.  [DONE] Regulatory engine — device classifier, ISO 10993, biocompat scorer,
            pathway mapper, AI narrative
9.  [DONE] Experimental design engine — cell/organism KB, DBTL tracker, roadmap generator,
            AI advisor (5-tab UI)
10. [DONE] Business Intelligence — market KB, stakeholder KB, SWOT engine,
            strategic summary (6-tab UI with Claude synthesis)
11. [DONE] Briefing generator — BriefingContext, ContextAssembler, BriefingGenerator,
            10 Technical + 10 Executive sections, editable prompts, export
12. [DONE] Toxicology tab — ToxServerManager, ADMET/CompTox/AOP/PBPK clients,
            Server Control + CompTox + ADMET + AOP + PBPK sub-tabs,
            live client injection into Regulatory workers

### NEXT SESSION — Synthetic Biology tab
- synthetic_biology_engine/ — iGEM, SynBioHub, Addgene clients
- Parts browser + circuit designer (DBTL wizard)
- Living materials integration layer
- Genetic editor (editing strategy + delivery advisor)
- Bioproduction planner
- synbio_tab.py — wire all sub-tabs into main_window
- Business Intelligence monitoring (active alerts)
- Own IP strategy module
- Own experimental data upload pipeline
- PowerPoint export


---

## Tox Engine -- ToxMCP Integration

### Overview

The tox_engine/ module wraps the ToxMCP suite of MCP (Model Context Protocol)
servers for computational toxicology. All servers run locally as HTTP JSON-RPC
services. The app communicates with them via the MCPClient base class.

ToxMCP paper: https://doi.org/10.64898/2026.02.06.703989
GitHub: https://github.com/ToxMCP/

### Servers

| Server       | Package         | Port | Key Required        | Primary Use                             |
|--------------|-----------------|------|---------------------|-----------------------------------------|
| ADMETlab MCP | admetlab-mcp    | 8082 | No                  | ADMET prediction from SMILES            |
| CompTox MCP  | comptox-mcp     | 8083 | Yes (EPA, free)     | Chemical hazard, ToxValDB, OPERA models |
| AOP MCP      | aop-mcp         | 8084 | No                  | Adverse Outcome Pathway mapping         |
| PBPK MCP     | pbpk-mcp        | 8085 | No                  | Drug PK simulation (OSP Suite)          |
| O-QT MCP     | oqt-mcp         | 8086 | Windows + licensed  | QSAR read-across (post-hackathon only)  |

### Module Map

    src/tox_engine/
    ├── __init__.py            exports ToxServerManager, MCPClient, MCPToolResult
    ├── mcp_client.py          HTTP JSON-RPC 2.0 base client + MCPToolResult dataclass
    ├── server_manager.py      subprocess lifecycle + health checks + port config
    ├── admet_client.py        ADMETClient -- predict_admet, wash_molecule, render_structure
    ├── comptox_client.py      CompToxClient -- lookup_by_name, get_hazard_profile, screen_material_components
    ├── aop_client.py          AOPClient -- map_chemical_to_aops, search_aops, get_key_events_for_aop
    ├── pbpk_client.py         PBPKClient -- load_model, run_simulation, sensitivity_analysis
    ├── iso10993_assessor.py   ISO10993Assessor -- assess() builds full ISO 10993 evaluation
    ├── biocompat_scorer.py    BiocCompatScorer -- score_material() returns 0-100 composite score
    └── workers.py             QThread workers for all off-thread tox calls

### Integration Points

The tox_engine feeds into three existing modules:

1. Regulatory tab -- ISO 10993 Assessor
   ISO10993Assessor.assess(material, contact_type, duration, components)
   Returns ISO10993Assessment: required tests, chemical flags, AOP concerns, narrative
   Narrative auto-included in Briefing Builder regulatory section

2. Materials Lab tab -- Biocompat Scorer
   BiocCompatScorer.score_material(name, components, drug_smiles)
   Returns BiocCompatScore: 0-100 score, confidence tier A/B/C, traffic light
   Score shown on Knowledge Card alongside material properties

3. Drug Delivery tab -- ADMET + PBPK
   ADMETClient.predict_admet(smiles) for loaded drug molecules
   PBPKClient.run_simulation(model_id) for release kinetics modelling

### Startup Sequence

On app launch (main.py):
  1. ToxServerManager instantiated with port config from Config.tox_server_port
  2. manager.start_all_available() called in background thread
     - ADMETlab starts automatically (no key needed)
     - AOP starts automatically (no key needed)
     - CompTox starts only if EPA_COMPTOX_API_KEY is set
     - PBPK starts only if user enables in settings
  3. ServerHealthWorker polls every 30s and updates status bar
  4. If a server is offline its tab features are greyed out with
     an Install & Start prompt linking to setup instructions

### Day-One Priority

For hackathon MVP implement in this order:
  1. ADMETlab (no key, works immediately) -- wire to Drug Delivery tab
  2. AOP (no key) -- wire to Regulatory tab AOP Explorer subtab
  3. BiocCompatScorer with ADMETlab + AOP data -- wire to Materials Lab Knowledge Card
  4. ISO10993Assessor with AOP data only -- wire to Regulatory required tests
  5. CompTox (after EPA key obtained) -- enriches all of the above

### Environment Variables Added

  EPA_COMPTOX_API_KEY   -- free at https://comptox.epa.gov/dashboard
  ANTHROPIC_API_KEY     -- Claude API primary AI engine

Both loaded by Config._load_env_vars() and accessible as
config.epa_comptox_api_key and config.anthropic_api_key.

---

## Research Flow (Canonical)

One active project per session. The team receives an industry question and works through
the following steps in order. Each step feeds the next. Every analysis has an
"Add to Briefing" button so findings accumulate as the team works.

### Step 0 -- Project Creation
Team pastes the raw industry question into New Project.
Claude parses it into structured fields: target_tissue, application_type,
patient_population, regulatory_target, drug_payload, material_class,
research_phase, key_challenges, search_keywords.
Low-confidence fields are highlighted for team review and editing.
One confirmed project drives all subsequent module behaviour.

### Step 1 -- Literature  (what do we know?)
PubMed auto-searches using Claude-generated keywords from project context.
Team scans abstracts, marks key papers, drops PDFs into the inbox.
Claude extracts structured facts per paper: material, cell model, viability,
key finding, limitations.
Confirmed facts propagate to: Materials KB, Biocompat Scorer, Briefing.

### Step 2 -- Researcher Network  (who are the key players?)
Authors from found papers seed the network automatically.
Team tracks researchers to monitor new output.
Feeds into Briefing as "leading research groups" section.

### Step 3 -- Materials Lab  (what material fits?)
Topic tree pre-navigated to project material_class.
Claude generates AI knowledge cards for candidate materials.
Comparison view (radar charts) supports material selection.
Fabrication tab shows manufacturing method compatibility.
Biocompat score feeds into Regulatory tab.

### Step 4 -- Bio Analysis  (what does the target tissue look like?)
GEO and CELLxGENE auto-queried for target_tissue expression data.
Transcriptomics, cell type composition, key pathways characterised.
Sequencing advisor selects appropriate technology.
Tissue interaction model informs experimental design.

### Step 5 -- Drug Delivery  (if drug_payload is set)
PubChem / ChEMBL auto-lookup from drug_payload field.
ADMET toxicity screening via ToxMCP.
PK release model curves (Level 1-3).
Material-drug compatibility check.

### Step 6 -- Experimental Design  (how do we prove it works?)
Cell model and assay recommenders pre-filtered by target_tissue.
Microscopy advisor for imaging strategy.
DBTL tracker for synthetic biology design iterations.
Outputs: experimental roadmap, recommended protocol list.
Becomes the Methods section of the briefing.

### Step 7 -- Synthetic Biology  (optional: living materials / gene therapy angle)
iGEM Registry and SynBioHub searched by biological function.
Circuit designer for genetic strategy planning.
Living materials layer connects synbio design to scaffold.
Relevant when team wants a biology-embedded differentiation angle.

### Step 8 -- Regulatory  (what is the approval path?)
Device auto-classified from application_type and regulatory_target.
ISO 10993 required test matrix generated.
Biocompat score from Materials Lab + ToxMCP feeds in.
Pathway map (FDA / CE mark / ATMP) with milestone timeline.

### Step 9 -- Business Intelligence  (is there a market?)
Market size seeded by target_tissue + patient_population.
Competitive landscape, patent white space, funding intelligence.
Evidence-grounded SWOT generated from all collected data.
Strategic one-page summary for pitch preparation.

### Step 10 -- Briefing Builder  (synthesise everything)
Team selects which modules to include.
Mode toggle: Technical report vs Executive summary.
Prompt editor shows the exact Claude prompt being used.
One-click export: PDF or Markdown.

### Summary
frame -> literature -> biology -> material -> experiment -> regulatory -> business -> brief
Each tab receives the ProjectContext object at construction and auto-loads its
first search on showEvent (lazy loading -- no simultaneous API flood at project open).


---

## Module Relevance System

Every module tab is always visible. Claude's question parsing outputs relevance flags
that suggest which modules apply to the current project. The team can override any flag.

### Relevance Flags (part of ProjectContext)

relevant_modules: dict[str, bool]
  literature     -- always True
  researcher     -- always True
  materials      -- always True
  bio_analysis   -- True unless clearly irrelevant
  drug_delivery  -- True only if drug_payload is present
  experimental   -- almost always True
  synbio         -- True only if living materials / gene therapy angle detected
  regulatory     -- almost always True
  business       -- almost always True
  briefing       -- always True

### Behaviour per module

If relevant_modules[module] is False:
  - Tab is still visible (no hidden tabs)
  - Tab shows a dismissable banner: "[Module] not flagged as relevant for this
    project. You can still use it."
  - "Add to Briefing" button is disabled by default
  - Briefing builder excludes the module unless user manually includes it

If relevant_modules[module] is True:
  - Tab loads normally on first visit (lazy)
  - "Add to Briefing" button enabled
  - Module included in briefing content selector by default

### User override
The team can flip any relevance flag from the project settings panel.
Claude suggests -- humans decide. The raw question and Claude confidence
scores are always visible so the team can see why a module was flagged.


---

## Simulation Module

A top-level tab. Elevates the app from a research aggregator to a predictive
modelling environment. Strong hackathon differentiator -- live parameter sweeps
with instant visual feedback require no wet lab and demonstrate quantitative thinking.

All models are ODE systems solved with scipy.integrate.odeint.
Plots update in real time on every slider change (debounced, ~200ms).
Every model output has an "Add to Briefing" button.

### UI Structure

Simulation tab
  Model Library        -- browse and select pre-built simulation models
  Parameter Panel      -- grouped sliders + numeric spinboxes per model
  Live Plot            -- Matplotlib/Plotly canvas, updates on parameter change
  Chain Builder        -- connect models in sequence (post-MVP)
  Export               -- curve data as CSV, plot image to briefing

### MVP Model Library

1. Cell Proliferation on Scaffold
   ODE: logistic growth coupled to scaffold degradation
   Parameters: seeding density, growth rate, scaffold degradation constant,
               carrying capacity, scaffold porosity
   Output: cell number vs time + scaffold mass vs time (dual axis)
   Context link: auto-seeds carrying capacity from Materials Lab scaffold properties

2. Drug Release Kinetics
   Models: zero-order, first-order, Korsmeyer-Peppas (n=0.5 diffusion, n=1 erosion)
   Parameters: initial drug loading, release rate constant, diffusion exponent,
               burst fraction
   Output: cumulative release (%) vs time
   Context link: auto-seeds drug from drug_payload field

3. Gene Circuit Dynamics
   ODE: Hill function activator/repressor kinetics
   Represents consequence of CRISPR edit -- altered transcription factor
   or protein level over time
   Parameters: production rate, degradation rate, Hill coefficient,
               activation threshold, initial condition
   Output: protein/mRNA concentration vs time
   Context link: synbio module genetic edit feeds initial condition

4. Scaffold Diffusion (Fick's Law)
   1D steady-state and transient diffusion-reaction
   Parameters: diffusion coefficient, oxygen/glucose consumption rate,
               scaffold thickness, surface concentration
   Output: concentration profile across scaffold depth
   Critical insight: identifies hypoxic core thickness for thick constructs
   Context link: auto-seeds scaffold thickness from Materials Lab

5. Tissue Inflammatory Response
   Semi-empirical ODE: acute inflammation -> resolution -> integration
   Parameters: material biocompatibility score, degradation rate,
               vascularisation rate, foreign body response intensity
   Output: inflammation index + integration index vs weeks post-implant
   Context link: auto-seeds biocompat score from Regulatory/ToxMCP

6. Metabolic Flux (simplified)
   Altered gene expression -> changed enzyme levels -> pathway flux shift
   Parameters: baseline flux, fold-change in enzyme from gene edit,
               pathway connectivity (series vs parallel)
   Output: relative flux through key metabolic nodes vs time
   Connects to transcriptome/metabolome readout layer

### Chained Simulation (post-MVP)

The full example workflow:
  Gene circuit ODE (CRISPR edit -> protein level change)
    -> Metabolic flux model (protein affects enzyme -> flux shift)
    -> Cell proliferation model (metabolic state affects growth rate)
    -> Diffusion model (growing cell density increases oxygen demand)
    -> Tissue response model (scaffold degradation + cell integration)

Each model output feeds the next model's initial conditions.
Chain Builder UI: drag-and-drop model sequence, wire output -> input parameter.

### Integration with ProjectContext

On project load, simulation tab reads:
  drug_payload       -> pre-seeds Drug Release model
  material_class     -> pre-seeds degradation constants where known
  target_tissue      -> pre-seeds tissue response parameters from literature values
  relevant_modules   -> "simulation" flag (default True unless question is purely
                        computational/informatics with no physical system)

### Technical Implementation Notes

  scipy.integrate.odeint  -- ODE solver
  numpy                   -- parameter arrays, curve data
  matplotlib (embedded)   -- live plot canvas in PyQt6 via FigureCanvasQTAgg
  QSlider + QDoubleSpinBox -- parameter controls, linked bidirectionally
  QTimer debounce         -- 200ms delay before recompute on slider drag
  All model classes inherit SimulationModel base class with:
    parameters: dict[str, Parameter]  (name, min, max, default, unit, description)
    run(t_span, params) -> SimulationResult
    plot(result, ax)    -> annotated matplotlib axes


---

## Tab Structure Update (11 tabs)

The Simulation tab is added as tab 8, before Regulatory.
Full tab order:

1.  Literature Analysis
2.  Researcher Network
3.  Materials Lab
4.  Bio Analysis
5.  Drug Delivery
6.  Experimental Design
7.  Synthetic Biology
8.  Simulation
9.  Regulatory
10. Business Intelligence
11. Briefing Builder

Simulation sits between Synthetic Biology and Regulatory because:
- It can consume synbio outputs (gene circuit -> protein level)
- Its outputs (biocompat score, tissue response) feed Regulatory
- It represents the "what will happen" answer before committing to a regulatory path

Module map addition:
src/simulation_engine/
  base_model.py          NEW -- SimulationModel base class, Parameter dataclass,
                                SimulationResult dataclass
  cell_proliferation.py  NEW -- logistic growth + scaffold degradation ODE
  drug_release.py        NEW -- zero-order / first-order / Korsmeyer-Peppas
  gene_circuit.py        NEW -- Hill function activator/repressor ODE
  diffusion.py           NEW -- 1D Fick diffusion-reaction
  tissue_response.py     NEW -- inflammatory response + integration ODE
  metabolic_flux.py      NEW -- simplified pathway flux model
  chain_runner.py        NEW -- post-MVP: sequential model chaining


---

## Pathway Intervention Planner + Small Molecule by Target

Both are subtabs within Bio Analysis, extending it from pure analysis into actionable
intervention strategy. They are independently usable but connect to each other.

### Bio Analysis tab -- updated subtab list

  Transcriptomics          (GEO query, volcano, heatmap -- bulk)
  Single Cell              (CELLxGENE, UMAP, clustering, diff abundance)
  Sequencing Advisor       (technology selection)
  Metabolomics             (pathway overlay, PCA/UMAP)
  Multi-Omics              (MOFA, joint pathway enrichment)
  Proteomics               (DDA/DIA, protein corona, STRING PPI)
  Flow Cytometry           (panel design, population stats)
  Tissue Interaction       (response timeline)
  Intervention Planner     NEW -- pathway hit -> ranked intervention strategies
  Target Lookup            NEW -- gene/protein -> small molecule modulators

---

### Intervention Planner (subtab)

Input: a dysregulated pathway + direction (activated/suppressed) + key gene list.
Receives this automatically from Pathway Analysis results, or user can enter manually.

Evaluates three intervention categories per pathway node:

GENETIC
  - Essentiality check (do not suggest KO of essential genes)
  - Editing strategy selection: KO / knockin / base edit / CRISPRi / CRISPRa
    (CRISPRi/a preferred for tuning rather than elimination)
  - Guide RNA feasibility score for key targets
  - Delivery system options filtered by target_tissue from ProjectContext
  - Links to Synthetic Biology tab for circuit design

PHARMACOLOGICAL
  - Calls Target Lookup for each druggable node in the pathway
  - Filters by clinical precedent: approved > clinical trial > preclinical > predicted
  - Druggability assessment per node (binding pocket evidence)
  - Links to Drug Delivery tab for ADMET + PK modelling

COMBINATORIAL
  - Genetic edit + small molecule together (sensitisation strategies)
  - Dual-target strategies from STRING PPI upstream regulator analysis
  - Flags combinations with existing clinical evidence

Ranking criteria per intervention:
  1. Evidence level (clinical > preclinical > computational)
  2. Target selectivity (off-target risk)
  3. Delivery feasibility to target_tissue
  4. Safety / toxicity flags (ToxMCP feed)
  5. Patent novelty (white space signal from Business Intelligence)

Output: ranked intervention table with columns:
  Strategy | Target | Mechanism | Evidence Level | Delivery | Safety Flag | Links

"Add to Briefing" exports ranked table + rationale narrative (Claude-generated).

Backend modules:
  bio_engine/pathway_intervention.py   NEW -- orchestration logic
  bio_engine/target_druggability.py    NEW -- OpenTargets + UniProt druggability queries
  bio_engine/crispr_advisor.py         NEW -- essentiality check, editing strategy logic
                                              (guide RNA scoring via CRISPOR API or local)

---

### Target Lookup (subtab)

Target-first small molecule search. Distinct from Drug Delivery > Drug Lookup which
is compound-first (you know the drug). Here you know the gene/protein target and
want to find what modulates it.

Input: gene symbol or UniProt ID (e.g. VEGFR2, P35968, TGFB1)

Queries (in parallel):
  ChEMBL by target   -- all compounds with bioactivity data, IC50/Ki values,
                        assay type, organism, confidence score
  OpenTargets        -- approved drugs + clinical candidates for this target,
                        disease indication, clinical phase
  PubChem            -- compound structures, known activity annotations
  DrugBank           -- approved drugs with PK parameters where available

Output table columns:
  Compound | Mode (activator/inhibitor) | Potency (IC50/Ki) | Clinical Stage |
  Organism tested | Toxicity flag | Structure thumbnail

Filters:
  Mode: activator / inhibitor / all
  Clinical stage: approved only / clinical / all
  Organism: human / in vitro / all
  Potency threshold: slider (nM range)

"Add to Briefing" exports compound table for the named target.
Clicking a compound opens its Drug Delivery > Drug Lookup entry (ADMET + PK).

Backend modules:
  bio_engine/target_lookup.py          NEW -- ChEMBL + OpenTargets + PubChem queries
                                              by target identifier

---

### Data Sources Summary

  OpenTargets Platform API   GraphQL, free, no key -- target-disease-drug associations
  ChEMBL REST API            free, no key -- bioactivity by target
  STRING API                 free, no key -- PPI, upstream regulator identification
  UniProt REST API           free, no key -- druggability, protein function
  PubChem PUG REST           free, no key -- compound lookup
  CRISPOR                    web API or local -- guide RNA off-target scoring

