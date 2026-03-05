# tox_engine -- ToxMCP Integration Layer

## What this module is

This module connects the app to the ToxMCP suite of computational toxicology
servers. ToxMCP wraps major toxicology databases and tools as local HTTP
services the app can query programmatically.

**Why it exists:** Every biomaterial going through regulatory approval (ISO 10993)
needs a toxicological risk assessment of its chemical components. ToxMCP automates
the hardest part of this: screening material components against EPA hazard databases,
predicting ADMET properties of drug payloads, and mapping Adverse Outcome Pathways
(the mechanistic reason *why* a material might be toxic to tissue).

**Why it matters for the hackathon:** No competitor will have automated toxicology
integrated into their materials analysis pipeline. Showing a judge a system that
takes a material formulation -> chemical hazard screening -> ADMET prediction ->
AOP mapping -> ISO 10993 test matrix -> briefing section, automatically, in under
2 minutes, is a strong differentiator.

ToxMCP paper: https://doi.org/10.64898/2026.02.06.703989
ToxMCP GitHub: https://github.com/ToxMCP/
Full design rationale: see ARCHITECTURE_DECISIONS.md (Tox Engine section, bottom)

---

## The five servers

### 1. ADMETlab MCP (port 8082) -- START FIRST, NO KEY NEEDED
Predicts ADMET properties for any molecule from its SMILES string.
ADMET = Absorption, Distribution, Metabolism, Excretion, Toxicity.

Use it when:
- You have a drug loaded into a scaffold (drug-eluting scaffold)
- You want to screen degradation products of a biodegradable polymer
- You need a quick toxicity flag for a novel crosslinker or photoinitiator

Install:  pip install admetlab-mcp
Start:    python -m admetlab_mcp --port 8082
No API key required.

### 2. EPA CompTox MCP (port 8083) -- requires free EPA key
Connects to the EPA Computational Toxicology Dashboard. Contains ToxValDB
(toxicity reference values), cancer classifications, genotoxicity data,
and OPERA/TEST predictive models for millions of chemicals.

Use it when:
- You need NOAEL/LOAEL values for a material component
- You need to know if a chemical is a known carcinogen or genotoxin
- You need regulatory-grade hazard data for ISO 10993 risk assessment

Install:  pip install comptox-mcp
Start:    EPA_COMPTOX_API_KEY=<key> python -m comptox_mcp --port 8083
Key:      Free registration at https://comptox.epa.gov/dashboard

### 3. AOP MCP (port 8084) -- NO KEY NEEDED
Queries AOP-Wiki for Adverse Outcome Pathways -- structured causal chains
from molecular perturbation to observable biological harm.

Example AOP: titanium ion release -> ROS generation -> mitochondrial
dysfunction -> apoptosis -> tissue necrosis.

Use it when:
- You need to explain *mechanistically* why a material raises biological concerns
- You want to identify which in vitro assays can detect the key events
  in a toxicity pathway (directly informs experimental design)
- You are writing the biological rationale section of a regulatory submission

Install:  pip install aop-mcp
Start:    python -m aop_mcp --port 8084
No API key required.

### 4. PBPK MCP (port 8085) -- NO KEY NEEDED
Wraps the Open Systems Pharmacology Suite for physiologically-based
pharmacokinetic modelling. Models how a drug distributes from a local
delivery device through tissue into systemic circulation.

Use it when:
- Your device delivers a drug (drug-device combination product)
- You need to predict systemic exposure from local release (for regulators)
- You want to run sensitivity analysis on material release parameters

Install:  pip install pbpk-mcp
Start:    python -m pbpk_mcp --port 8085
No API key required.

### 5. O-QT MCP -- POST-HACKATHON ONLY
Wraps the OECD QSAR Toolbox. Requires Windows + licensed OECD software.
Skip for hackathon day one.

---

## How the pieces connect to the rest of the app

Material component list
  -> comptox_client.screen_material_components()   ChemicalHazardProfile per component
  -> aop_client.map_material_components()           AOPMappingResult per component
  -> biocompat_scorer.score_material()              0-100 score, A/B/C confidence, traffic light
  -> iso10993_assessor.assess()                     required test list + narrative
  -> Briefing Builder injects all of above into Regulatory section

Drug SMILES
  -> admet_client.predict_admet()     ADMETResult with toxicity flags
  -> pbpk_client.run_simulation()     time-concentration curve + PK metrics
  -> Drug Delivery tab shows ADMET panel + release kinetics

Where it appears in the UI:
  Materials Lab > Knowledge Card       BiocCompatScore traffic light + score
  Regulatory > ISO 10993              ISO10993Assessment required test list
  Regulatory > Toxicology Assessment  NEW subtab: Chemical Lookup, ADMET, AOP Explorer
  Drug Delivery > Drug Lookup         ADMETResult panel
  Drug Delivery > Release Kinetics    PBPK simulation curves

---

## File reference

mcp_client.py
  Base HTTP JSON-RPC 2.0 client used by all wrappers.
  MCPToolResult dataclass -- all calls return this, never raise.
  Check .success and .error before using .content.

server_manager.py
  ToxServerManager -- spawn/stop/health-check server processes.
  start_all_available() starts keyless servers automatically at app launch.
  get_client("admet") returns an MCPClient for a named server.
  get_status() returns dict of server_name -> bool for status bar.

admet_client.py
  ADMETClient wrapping admetlab-mcp.
  predict_admet(smiles) -> ADMETResult
  ADMETResult.toxicity_summary  -- one-line flag string for the UI
  ADMETResult.has_toxicity_flags -- bool for colour-coding

comptox_client.py
  CompToxClient wrapping comptox-mcp.
  lookup_by_name(name) -> ChemicalHazardProfile
  screen_material_components([names]) -> list[ChemicalHazardProfile]
  ChemicalHazardProfile.risk_tier -> "low" / "moderate" / "high"

aop_client.py
  AOPClient wrapping aop-mcp.
  map_chemical_to_aops(dtxsid_or_name) -> AOPMappingResult
  AOPMappingResult.biological_concern_summary -- one-liner for the UI
  get_key_events_for_aop(aop_id) -> list[KeyEvent]

pbpk_client.py
  PBPKClient wrapping pbpk-mcp.
  load_model(path) -> model_id string
  run_simulation(model_id) -> SimulationResult
  SimulationResult.pk_metrics -> PKMetrics (Cmax, AUC, T1/2)

iso10993_assessor.py
  ISO10993Assessor -- pure business logic layer, uses CompTox + AOP clients.
  assess(material, contact_type, duration, components) -> ISO10993Assessment
  ISO10993Assessment.narrative -- briefing-ready markdown text
  Works even if CompTox/AOP servers are offline (graceful degradation).
  ISO 10993-1 required-test matrix is hard-coded and complete for all contact types.

biocompat_scorer.py
  BiocCompatScorer -- weighted composite scoring.
  score_material(name, components, drug_smiles) -> BiocCompatScore
  BiocCompatScore.traffic_light -> "green" / "amber" / "red"
  BiocCompatScore.overall_score -> 0-100
  BiocCompatScore.confidence_tier -> "A" (data-rich) / "B" (partial) / "C" (prediction-only)

workers.py
  QThread workers -- all blocking network calls run off the UI thread.
  ADMETWorker, CompToxWorker, AOPWorker, ISO10993Worker,
  BiocCompatScorerWorker, ServerHealthWorker
  All emit result_ready(result) on success and error_occurred(str) on failure.

---

## Day-one build order

1. pip install admetlab-mcp aop-mcp
2. Wire ADMETWorker into Drug Delivery tab > Drug Lookup subtab
3. Wire AOPWorker + ISO10993Worker into Regulatory tab
4. Wire BiocCompatScorerWorker into Materials Lab > Knowledge Card
5. Get free EPA key, pip install comptox-mcp, enrich all of the above with CompTox data

---

## Environment variables required

  ANTHROPIC_API_KEY       Claude API (primary AI engine for briefings)
  EPA_COMPTOX_API_KEY     Free at https://comptox.epa.gov/dashboard
  NCBI_API_KEY            Free at https://www.ncbi.nlm.nih.gov/account/
  NCBI_EMAIL              Required for PubMed API

All loaded automatically by src/utils/config.py from environment or .env file.
Accessible as:
  config.anthropic_api_key
  config.epa_comptox_api_key
  config.tox_server_port    -> dict of server_name -> port number
  config.tox_auto_start     -> dict of server_name -> bool (auto-start on launch)
