"""
Materials Database
==================
Local SQLite knowledge base for material properties,
biocompatibility scores, and fabrication compatibility.

Seeded from topic_tree on first run.
Enriched by:
  - knowledge_card_gen.py  (AI-generated cards)
  - literature_engine      (extracted facts from papers)
  - user manual edits
"""

import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# ── Fabrication method list (from architecture doc) ───────────────────────────

FABRICATION_METHODS = [
    "GRACE (volumetric)",
    "Xolography (volumetric)",
    "Tomographic VBP",
    "FDM / extrusion",
    "Bioprinting (extrusion)",
    "Coaxial extrusion",
    "MEW (Melt Electrowriting)",
    "Electrospinning",
    "Inkjet / drop-on-demand",
    "SLA",
    "LIFT",
    "Self-assembly / organoid",
    "Fermentation / biosynthesis",
    "Casting",
    "Machining",
]

# ── Seed data: key properties per material node ───────────────────────────────
# These are literature-backed starting values — flagged AI_GENERATED=False
# because they come from well-established sources, not LLM inference.

SEED_MATERIALS = [
    {
        "name":           "Ti-6Al-4V",
        "material_class": "metals",
        "topic_key":      "titanium_alloys",
        "properties": {
            "Young's modulus (GPa)":   "110-114",
            "Tensile strength (MPa)":  "860-1000",
            "Density (g/cm³)":         "4.43",
            "Corrosion resistance":    "Excellent (passive TiO₂ layer)",
            "Biocompatibility":        "Excellent — ISO 10993 established",
            "Degradation":             "Non-degradable",
            "Typical applications":    "Orthopaedic implants, dental abutments, spinal cages",
        },
        "fabrication_compat": {
            "Machining":               "Excellent",
            "FDM / extrusion":         "Not applicable",
            "SLA":                     "Not applicable",
            "MEW (Melt Electrowriting)":"Not applicable",
            "GRACE (volumetric)":      "Not applicable",
        },
        "biocompat_score": 4,   # 4 stars — published in vivo studies
        "ai_generated":    False,
    },
    {
        "name":           "GelMA",
        "material_class": "polymers",
        "topic_key":      "hydrogels",
        "properties": {
            "Stiffness (kPa)":         "0.1-100 (tunable by crosslink density)",
            "Gelation":                "Photo-crosslinkable (UV/visible + photoinitiator)",
            "Cell adhesion":           "Excellent (RGD motifs from gelatin backbone)",
            "Degradation":             "Enzymatic (MMP-sensitive)",
            "Printability":            "Good — widely used bioink base",
            "Biocompatibility":        "Excellent",
            "Typical applications":    "Bioprinting, organoid culture, wound healing",
        },
        "fabrication_compat": {
            "Bioprinting (extrusion)": "Excellent",
            "GRACE (volumetric)":      "Good",
            "Xolography (volumetric)": "Good",
            "Inkjet / drop-on-demand": "Moderate (viscosity-dependent)",
            "SLA":                     "Good (with photoinitiator)",
            "Electrospinning":         "Poor",
        },
        "biocompat_score": 4,
        "ai_generated":    False,
    },
    {
        "name":           "Hydroxyapatite (HA)",
        "material_class": "ceramics",
        "topic_key":      "hydroxyapatite",
        "properties": {
            "Young's modulus (GPa)":   "70-120",
            "Compressive strength (MPa)": "100-900 (dense) / 2-20 (porous)",
            "Ca/P ratio":              "1.67",
            "Bioactivity":             "Excellent — bonds to bone directly",
            "Degradation":             "Very slow (years) — can be sintered to control",
            "Osteoconductive":         "Yes",
            "Typical applications":    "Bone substitute, Ti coating, composite filler",
        },
        "fabrication_compat": {
            "Casting":                 "Good (slip casting)",
            "SLA":                     "Good (with resin)",
            "FDM / extrusion":         "Good (HA/polymer composite)",
            "Bioprinting (extrusion)": "Good (HA/hydrogel composite)",
            "Machining":               "Difficult (brittle)",
            "GRACE (volumetric)":      "Emerging (HA/resin composites)",
        },
        "biocompat_score": 5,   # 5 stars — own data equivalent (FDA approved)
        "ai_generated":    False,
    },
    {
        "name":           "PCL (Polycaprolactone)",
        "material_class": "polymers",
        "topic_key":      "synthetic_polymers",
        "properties": {
            "Young's modulus (MPa)":   "400-600",
            "Tensile strength (MPa)":  "10-50",
            "Degradation":             "Hydrolytic — slow (2-4 years)",
            "Melting point (°C)":      "58-63",
            "Biocompatibility":        "Excellent — FDA approved",
            "Printability":            "Excellent for MEW and FDM",
            "Typical applications":    "Bone scaffold, MEW fibre, slow-release device",
        },
        "fabrication_compat": {
            "MEW (Melt Electrowriting)":"Excellent — benchmark material",
            "FDM / extrusion":         "Excellent",
            "Electrospinning":         "Good",
            "Bioprinting (extrusion)": "Poor (no cell adhesion without modification)",
            "GRACE (volumetric)":      "Not applicable (not photo-crosslinkable)",
        },
        "biocompat_score": 5,
        "ai_generated":    False,
    },
    {
        "name":           "Alginate",
        "material_class": "polymers",
        "topic_key":      "hydrogels",
        "properties": {
            "Stiffness (kPa)":         "1-100 (ionic crosslinking with Ca²⁺)",
            "Gelation":                "Ionic (CaCl₂) or covalent",
            "Cell adhesion":           "Poor without RGD functionalisation",
            "Degradation":             "Slow in vivo (no mammalian alginase)",
            "Biocompatibility":        "Good — FDA approved for wound care",
            "Typical applications":    "Cell encapsulation, bioprinting, wound dressing",
        },
        "fabrication_compat": {
            "Bioprinting (extrusion)": "Excellent — most common bioink",
            "Coaxial extrusion":       "Excellent (core-shell structures)",
            "Inkjet / drop-on-demand": "Good",
            "GRACE (volumetric)":      "Poor (ionic gelation incompatible with VBP)",
        },
        "biocompat_score": 4,
        "ai_generated":    False,
    },
]


class MaterialsDB:
    """
    Interface to the materials knowledge base.
    Handles seeding, retrieval, and updates.
    """

    def __init__(self):
        from data_manager import get_db
        get_db()

    # ── Seeding ───────────────────────────────────────────────────────

    def seed_if_empty(self) -> int:
        """Seed default materials if table is empty. Returns count added."""
        from data_manager import crud
        existing = crud.list_materials()
        if existing:
            return 0

        added = 0
        for m in SEED_MATERIALS:
            try:
                crud.upsert_material(
                    name             = m["name"],
                    material_class   = m["material_class"],
                    properties       = m["properties"],
                    fabrication_compat = m["fabrication_compat"],
                    biocompat_score  = m["biocompat_score"],
                    ai_generated     = m["ai_generated"],
                    human_verified   = True,
                    subclass         = m.get("topic_key", ""),
                )
                added += 1
            except Exception as e:
                logger.error(f"Failed to seed {m['name']}: {e}")

        logger.info(f"Seeded {added} materials")
        return added

    # ── Retrieval ─────────────────────────────────────────────────────

    def get_by_topic(self, topic_key: str) -> List[Dict]:
        """All materials under a topic tree node (matched via subclass)."""
        from data_manager import get_db
        with get_db().connection() as conn:
            rows = conn.execute(
                "SELECT * FROM materials WHERE subclass=? ORDER BY name",
                (topic_key,)
            ).fetchall()
        return [self._deserialise(dict(r)) for r in rows]

    def get_by_class(self, material_class: str) -> List[Dict]:
        from data_manager import crud
        mats = crud.list_materials(material_class=material_class)
        return [self._deserialise(m) for m in mats]

    def search(self, query: str) -> List[Dict]:
        """Simple text search on name and properties."""
        from data_manager import get_db
        q = f"%{query}%"
        with get_db().connection() as conn:
            rows = conn.execute(
                """SELECT * FROM materials
                   WHERE name LIKE ? OR properties_json LIKE ?
                   ORDER BY name LIMIT 50""",
                (q, q)
            ).fetchall()
        return [self._deserialise(dict(r)) for r in rows]

    def get(self, material_id: int) -> Optional[Dict]:
        from data_manager import crud
        m = crud.get_material(material_id)
        return self._deserialise(m) if m else None

    def get_by_name(self, name: str) -> Optional[Dict]:
        from data_manager import get_db
        with get_db().connection() as conn:
            row = conn.execute(
                "SELECT * FROM materials WHERE name=?", (name,)
            ).fetchone()
        return self._deserialise(dict(row)) if row else None

    def list_all(self) -> List[Dict]:
        from data_manager import crud
        return [self._deserialise(m) for m in crud.list_materials()]

    # ── Update ────────────────────────────────────────────────────────

    def save_knowledge_card(self, material_id: int, card: Dict) -> None:
        """Save AI-generated knowledge card content back to the material record."""
        from data_manager import get_db
        import json
        with get_db().connection() as conn:
            conn.execute(
                """UPDATE materials
                   SET properties_json=?, ai_generated=1, last_reviewed=datetime('now')
                   WHERE id=?""",
                (json.dumps(card.get("properties", {})), material_id)
            )
        logger.info(f"Saved knowledge card for material id={material_id}")

    def mark_verified(self, material_id: int) -> None:
        from data_manager import get_db
        with get_db().connection() as conn:
            conn.execute(
                "UPDATE materials SET human_verified=1 WHERE id=?",
                (material_id,)
            )

    # ── Comparison ────────────────────────────────────────────────────

    def compare(self, material_ids: List[int]) -> Dict:
        """
        Return a comparison dict for the given material IDs.
        Keys = property names, values = dict of {material_name: value}.
        """
        materials = [m for mid in material_ids for m in [self.get(mid)] if m is not None]
        if not materials:
            return {}

        # Collect all property keys across all materials
        all_keys = set()
        for m in materials:
            props = m.get("properties") or {}
            all_keys.update(props.keys())

        comparison: Dict[str, Dict[str, Any]] = {}
        for key in sorted(all_keys):
            comparison[key] = {}
            for m in materials:
                props = m.get("properties") or {}
                name = m.get("name") or "Unknown"
                comparison[key][name] = props.get(key, "—")

        return comparison

    # ── Helpers ───────────────────────────────────────────────────────

    def _deserialise(self, m: Dict) -> Dict:
        import json
        if not m:
            return m
        for field in ("properties_json", "biocompat_scores_json",
                      "fabrication_compat_json"):
            if field in m and isinstance(m[field], str):
                try:
                    key = field.replace("_json", "")
                    key = key.replace("biocompat_scores", "biocompat_scores")
                    m[key] = json.loads(m[field])
                except Exception:
                    pass
        # Friendlier aliases
        m["properties"]         = m.get("properties_json_parsed") or \
                                   self._try_parse(m.get("properties_json"))
        m["fabrication_compat"] = self._try_parse(m.get("fabrication_compat_json"))
        return m

    @staticmethod
    def _try_parse(s: Any) -> Any:
        if s is None:
            return {}
        if isinstance(s, dict):
            return s
        import json
        try:
            return json.loads(s)
        except Exception:
            return {}