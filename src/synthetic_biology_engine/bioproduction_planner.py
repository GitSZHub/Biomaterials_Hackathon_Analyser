"""Bioproduction Planner.

Recommends production system, bioreactor type, scale, process mode,
and cost tier for synthetic biology production proposals.
"""
from dataclasses import dataclass, field

# ── Production system knowledge base ─────────────────────────────────────────
PRODUCTION_SYSTEMS: dict[str, dict] = {
    "E. coli fed-batch": {
        "organism":    "E. coli BL21(DE3)",
        "scale":       "1 L – 10,000 L",
        "yield":       "0.5 – 5 g/L recombinant protein (intracellular or periplasmic)",
        "cost_tier":   "Low",
        "process_mode":"Fed-batch (glucose feed to maintain low acetate)",
        "timeline":    "Weeks to first material; months to process development",
        "best_for":    ["intracellular proteins", "PHB", "biosynthetic enzymes",
                        "proteins tolerant of refolding from inclusion bodies"],
        "limitations": "No mammalian glycosylation; endotoxin removal required; "
                       "IBs require refolding for many proteins",
        "bioreactor":  "Stirred-tank bioreactor (STR)",
        "gmp_path":    "Established GMP E. coli manufacturing; biosafety level 1 (K12) or 2",
    },
    "S. cerevisiae fed-batch": {
        "organism":    "S. cerevisiae BY4741 or industrial strains",
        "scale":       "1 L – 100,000 L",
        "yield":       "0.1 – 2 g/L secreted protein",
        "cost_tier":   "Low-Medium",
        "process_mode":"Fed-batch (ethanol glucose switch or continuous feed)",
        "timeline":    "Months for strain development; fermentation weeks",
        "best_for":    ["glycoproteins", "secreted proteins", "spider silk", "collagen-like"],
        "limitations": "Yeast glycosylation differs from human; hypermannosylation risk",
        "bioreactor":  "Stirred-tank bioreactor (STR)",
        "gmp_path":    "GRAS organism; established regulatory precedent",
    },
    "Pichia pastoris fed-batch": {
        "organism":    "Komagataella phaffii (Pichia pastoris) GS115 / X-33",
        "scale":       "1 L – 100,000 L",
        "yield":       "1 – 10 g/L secreted protein (high secretion specialist)",
        "cost_tier":   "Low-Medium",
        "process_mode":"Fed-batch methanol induction (AOX1 promoter)",
        "timeline":    "Months for strain; fermentation days",
        "best_for":    ["high-yield secreted proteins", "collagen-like peptides", "enzymes"],
        "limitations": "Methanol handling; non-human glycosylation",
        "bioreactor":  "Stirred-tank bioreactor (STR)",
        "gmp_path":    "GRAS; used for approved products (insulin, vaccines)",
    },
    "CHO perfusion": {
        "organism":    "CHO-K1 or DG44",
        "scale":       "50 L – 25,000 L",
        "yield":       "1 – 10 g/L (perfusion); 3–5 g/L (fed-batch)",
        "cost_tier":   "High",
        "process_mode":"Perfusion (continuous media exchange) or fed-batch",
        "timeline":    "1-2 years to GMP clinical batch",
        "best_for":    ["therapeutic glycoproteins", "growth factors (clinical grade)",
                        "mAbs", "complex multi-domain proteins"],
        "limitations": "Expensive; long timelines; complex media; GMP requirements stringent",
        "bioreactor":  "Stirred-tank + perfusion ATF/TFF system",
        "gmp_path":    "Gold standard for biologics manufacturing; ICH Q5A/Q5D compliance",
    },
    "Cell-free expression": {
        "organism":    "E. coli or wheat germ extract (cell-free)",
        "scale":       "mL – L (small scale only currently)",
        "yield":       "0.1 – 1 mg/mL",
        "cost_tier":   "Medium-High per mg",
        "process_mode":"Batch or continuous exchange (CECF)",
        "timeline":    "Hours to days — rapid prototyping",
        "best_for":    ["toxic proteins", "membrane proteins", "rapid prototyping",
                        "non-standard amino acid incorporation"],
        "limitations": "Small scale; expensive extract; not for industrial volumes",
        "bioreactor":  "Bench-top CECF reactor or microfluidic device",
        "gmp_path":    "Regulatory path emerging; mostly research use",
    },
    "Insect cell (baculovirus)": {
        "organism":    "Sf9 or Hi5 insect cells + baculovirus",
        "scale":       "1 L – 1,000 L",
        "yield":       "1 – 500 mg/L",
        "cost_tier":   "Medium",
        "process_mode":"Batch infection at high MOI",
        "timeline":    "Weeks for vector construction; rapid production after",
        "best_for":    ["virus-like particles", "complex eukaryotic proteins",
                        "protein complexes", "vaccines"],
        "limitations": "Insect glycosylation (paucimannose); cytolytic process — single use",
        "bioreactor":  "Wave bag or stirred-tank",
        "gmp_path":    "Approved products (Cervarix, Flublok); established regulatory path",
    },
}

BIOREACTOR_TYPES: dict[str, dict] = {
    "Stirred-Tank Reactor (STR)": {
        "description": "Standard impeller-driven vessel; excellent mixing and O2 transfer",
        "scale": "1 mL – 100,000 L",
        "shear": "Moderate (impeller tip speed)",
        "best_for": ["E. coli", "yeast", "CHO fed-batch"],
        "notes": "Industry standard; most validated at GMP scale",
    },
    "Wave Bag (Rocker)": {
        "description": "Single-use rocking bag; low shear; disposable",
        "scale": "0.5 L – 500 L",
        "shear": "Low",
        "best_for": ["insect cells", "sensitive mammalian cells", "viral vector production"],
        "notes": "Single-use reduces cleaning validation; good for clinical batches",
    },
    "Hollow Fibre Bioreactor": {
        "description": "Media perfuses through fibres; high cell density; simulates vasculature",
        "scale": "Laboratory – clinical scale",
        "shear": "Very low",
        "best_for": ["CAR-T expansion", "exosome/EV production", "high-density CHO"],
        "notes": "Synthecon / Fibercell systems; complex sampling",
    },
    "Rotating Wall Vessel (RWV)": {
        "description": "NASA-developed; microgravity simulation; 3D aggregate formation",
        "scale": "50 mL – 10 L",
        "shear": "Very low (simulated microgravity)",
        "best_for": ["organoids", "spheroids", "3D tissue models"],
        "notes": "Synthecon RCCS; good for scaffold-seeded constructs in suspension",
    },
    "Perfusion STR": {
        "description": "STR + ATF/TFF cell retention device; continuous media exchange",
        "scale": "2 L – 25,000 L",
        "shear": "Moderate",
        "best_for": ["CHO perfusion", "high-density mammalian", "continuous manufacturing"],
        "notes": "Higher yield than fed-batch; higher equipment cost",
    },
}


@dataclass
class BioproductionPlan:
    target_molecule:    str = ""
    intended_organism:  str = ""
    scale_target:       str = ""  # e.g. "10 g/month", "clinical Phase I"
    production_system:  str = ""
    bioreactor_type:    str = ""
    process_mode:       str = ""
    estimated_yield:    str = ""
    cost_tier:          str = ""
    gmp_path:           str = ""
    key_challenges:     list[str] = field(default_factory=list)
    next_steps:         list[str] = field(default_factory=list)


class BioproductionPlanner:
    """Recommend bioproduction approach for a target molecule."""

    def recommend(self, target_molecule: str, chassis: str = "",
                  scale: str = "research") -> list[dict]:
        """Return ranked production system recommendations."""
        mol = target_molecule.lower()
        ch = chassis.lower()
        sc = scale.lower()

        scores: list[tuple[int, str, dict]] = []
        for name, info in PRODUCTION_SYSTEMS.items():
            score = 0
            best = " ".join(info["best_for"]).lower()

            # Molecule match
            for keyword in ["collagen", "silk", "phb", "growth factor", "vegf",
                            "bmp", "il-", "antibody", "vaccine", "enzyme"]:
                if keyword in mol and keyword in best:
                    score += 3

            # Chassis match
            if ch and ch in name.lower():
                score += 5

            # Scale preference
            if sc in ("clinical", "gmp", "manufacturing") and "gmp" in info["gmp_path"].lower():
                score += 2
            if sc in ("research", "prototype") and info["cost_tier"] in ("Low", "Low-Medium"):
                score += 1

            scores.append((score, name, info))

        scores.sort(key=lambda x: -x[0])
        return [
            {"system": name, **info, "relevance_score": score}
            for score, name, info in scores
        ]

    def get_bioreactor_options(self, organism: str) -> list[dict]:
        org = organism.lower()
        results = []
        for name, info in BIOREACTOR_TYPES.items():
            best = " ".join(info["best_for"]).lower()
            if any(kw in best for kw in [org, "mammalian", "yeast"] if kw in org or kw in best):
                results.append({"type": name, **info})
        return results or [{"type": k, **v} for k, v in BIOREACTOR_TYPES.items()]

    def generate_plan(self, target_molecule: str, chassis: str,
                      scale: str, notes: str = "") -> str:
        recs = self.recommend(target_molecule, chassis, scale)
        top = recs[0] if recs else {}

        bioreactor_opts = self.get_bioreactor_options(chassis)
        bioreactor_str = "\n".join(
            f"  - {b['type']}: {b['description']}" for b in bioreactor_opts[:3]
        )

        alt_systems = "\n".join(
            f"  {i+2}. {r['system']} — {r['cost_tier']} cost, yield: {r['yield']}"
            for i, r in enumerate(recs[1:3])
        ) if len(recs) > 1 else "  (no alternatives generated)"

        return f"""BIOPRODUCTION PLAN
{'='*70}

TARGET MOLECULE:  {target_molecule}
CHASSIS INPUT:    {chassis or '(not specified)'}
SCALE TARGET:     {scale or '(not specified)'}

RECOMMENDED PRODUCTION SYSTEM
  System:          {top.get('system', 'N/A')}
  Organism:        {top.get('organism', 'N/A')}
  Process mode:    {top.get('process_mode', 'N/A')}
  Expected yield:  {top.get('yield', 'N/A')}
  Cost tier:       {top.get('cost_tier', 'N/A')}
  Scale range:     {top.get('scale', 'N/A')}
  GMP path:        {top.get('gmp_path', 'N/A')}
  Best for:        {', '.join(top.get('best_for', []))}
  Limitations:     {top.get('limitations', 'N/A')}

BIOREACTOR OPTIONS
{bioreactor_str}

ALTERNATIVE SYSTEMS
{alt_systems}

PROCESS DEVELOPMENT ROADMAP
  1. Strain/cell line construction and genetic validation
  2. Shake flask screening — confirm expression and activity
  3. Bench-top bioreactor (1-5 L) — process parameter optimization
     (pH, dO2, temperature, feed strategy)
  4. Scale-up: 50 L pilot — confirm volumetric productivity
  5. Downstream processing development (clarification, chromatography, UF/DF)
  6. Analytical method development (potency, purity, identity)
  7. {'GMP batch manufacturing + regulatory filing' if 'clinical' in scale.lower() else 'Research-grade production at target scale'}

NOTES
  {notes or '(none)'}
"""

    def get_all_systems(self) -> list[str]:
        return list(PRODUCTION_SYSTEMS.keys())
