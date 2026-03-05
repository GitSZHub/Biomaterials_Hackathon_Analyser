"""
Material Topic Tree
===================
Defines the biomaterial taxonomy from the architecture doc.

Branch types:
  deep       — knowledge cards, fabrication compat, researcher tracking, full paper feed
  monitoring — live paper feed + brief state-of-field card only
  promotable — monitoring branch that can be promoted to deep by user

Used by:
  - materials_engine/materials_db.py  (seeding)
  - ui/materials_tab.py               (navigation tree)
  - ai_engine/knowledge_card_gen.py   (context assembly)
"""

from typing import List, Optional
from dataclasses import dataclass, field


@dataclass
class MaterialNode:
    key:         str                        # unique slug, e.g. "titanium_alloys"
    label:       str                        # display name
    parent:      Optional[str]             # parent key, None = root
    branch_type: str                        # "deep" | "monitoring" | "promotable"
    description: str       = ""
    pubmed_terms: List[str] = field(default_factory=list)   # search terms for PubMed
    children:    List['MaterialNode'] = field(default_factory=list)


# ── Tree definition ────────────────────────────────────────────────────────────
# Mirrors architecture doc exactly.

TOPIC_TREE: List[MaterialNode] = [

    # ── Metals ────────────────────────────────────────────────────────
    MaterialNode("metals", "Metals", None, "deep",
        "Metallic biomaterials for structural and functional implants.",
        ["metal biomaterial implant"]),

    MaterialNode("titanium_alloys", "Titanium & Alloys", "metals", "deep",
        "Ti-6Al-4V, cpTi, Ti-6Al-7Nb. Gold standard for orthopaedic and dental implants.",
        ["titanium implant", "Ti-6Al-4V biocompatibility", "titanium alloy osseointegration"]),

    MaterialNode("shape_memory", "Shape Memory (Nitinol)", "metals", "deep",
        "NiTi shape memory alloy. Used in stents, orthodontic wires, surgical tools.",
        ["nitinol biomaterial", "shape memory alloy biomedical", "NiTi stent"]),

    MaterialNode("biodegradable_metals", "Biodegradable Metals", "metals", "deep",
        "Mg, Zn, Fe alloys. Degrade in vivo — no second surgery needed.",
        ["magnesium implant biodegradable", "zinc alloy biomaterial", "iron scaffold degradable"]),

    # ── Polymers ──────────────────────────────────────────────────────
    MaterialNode("polymers", "Polymers", None, "deep",
        "Synthetic and natural polymer biomaterials.",
        ["polymer biomaterial"]),

    MaterialNode("synthetic_polymers", "Synthetic Polymers", "polymers", "deep",
        "PEEK, PCL, PLGA, PLA, silicone — workhorse materials for devices and scaffolds.",
        ["PEEK implant", "PCL scaffold", "PLGA drug delivery", "PLA biomedical"]),

    MaterialNode("hydrogels", "Hydrogels", "polymers", "deep",
        "PEG, GelMA, alginate, hyaluronic acid. Key substrates for soft tissue and bioprinting.",
        ["hydrogel scaffold", "GelMA bioprinting", "alginate encapsulation",
         "hyaluronic acid tissue engineering"]),

    MaterialNode("smart_polymers", "Smart / Stimuli-Responsive", "polymers", "monitoring",
        "Temperature-, pH-, light-responsive polymers for triggered drug release.",
        ["stimuli responsive polymer biomaterial", "smart hydrogel drug release"]),

    # ── Ceramics ──────────────────────────────────────────────────────
    MaterialNode("ceramics", "Ceramics", None, "deep",
        "Bioactive and bioinert ceramics for bone and dental applications.",
        ["ceramic biomaterial bone"]),

    MaterialNode("hydroxyapatite", "Hydroxyapatite (HA)", "ceramics", "deep",
        "Primary mineral of bone. Used as coating, filler, or scaffold material.",
        ["hydroxyapatite scaffold", "HA coating titanium", "hydroxyapatite bone regeneration"]),

    MaterialNode("bioactive_glass", "Bioactive Glass", "ceramics", "deep",
        "45S5 Bioglass and variants. Bonds to both bone and soft tissue.",
        ["bioactive glass scaffold", "bioglass bone", "silicate bioceramics"]),

    MaterialNode("zirconia", "Zirconia", "ceramics", "deep",
        "High-strength ceramic for dental crowns and orthopaedic bearings.",
        ["zirconia dental implant", "zirconia biocompatibility"]),

    MaterialNode("tcp", "TCP (Tricalcium Phosphate)", "ceramics", "deep",
        "Resorbable ceramic. Degrades and is replaced by new bone.",
        ["tricalcium phosphate scaffold", "TCP bone regeneration", "beta-TCP resorption"]),

    # ── Natural materials ──────────────────────────────────────────────
    MaterialNode("natural_materials", "Natural Materials", None, "deep",
        "Protein- and polysaccharide-based materials from biological sources.",
        ["natural biomaterial scaffold"]),

    MaterialNode("collagen", "Collagen", "natural_materials", "deep",
        "Most abundant ECM protein. Used in scaffolds, films, sponges, and bioinks.",
        ["collagen scaffold tissue engineering", "collagen bioink", "collagen crosslinking"]),

    MaterialNode("fibrin", "Fibrin", "natural_materials", "deep",
        "Blood clot protein. Self-assembling, cell-instructive, fully degradable.",
        ["fibrin scaffold", "fibrin gel tissue engineering"]),

    MaterialNode("silk", "Silk Fibroin", "natural_materials", "deep",
        "Strong, slow-degrading, tunable. Used in tendons, cartilage, and cornea.",
        ["silk fibroin scaffold", "silk biomaterial mechanical"]),

    MaterialNode("chitosan", "Chitosan", "natural_materials", "deep",
        "Deacetylated chitin. Antimicrobial, haemostatic, wound healing applications.",
        ["chitosan scaffold", "chitosan wound healing", "chitosan drug delivery"]),

    # ── Composites ────────────────────────────────────────────────────
    MaterialNode("composites", "Composites & Hybrid", None, "deep",
        "Multi-phase materials combining mechanical and biological properties.",
        ["composite biomaterial scaffold", "hybrid biomaterial"]),

    # ── Carbon-based ──────────────────────────────────────────────────
    MaterialNode("carbon_based", "Carbon-Based", None, "monitoring",
        "Graphene, CNTs, carbon nanofibers. Strong mechanical properties, conductivity.",
        ["graphene biomaterial", "carbon nanotube biomedical", "graphene oxide scaffold"]),

    # ── Soft robotics (monitoring only) ───────────────────────────────
    MaterialNode("soft_robotics", "Soft Robotics & Actuators", None, "monitoring",
        "Pneumatic, SMP, DEA, hydrogel actuators for medical robotics.",
        ["soft robot actuator biomedical", "shape memory polymer actuator",
         "dielectric elastomer biomedical"]),

    # ── Living / biofabricated ─────────────────────────────────────────
    MaterialNode("living_materials", "Living / Biofabricated Materials", None, "deep",
        "Materials containing living cells or derived from biological fabrication.",
        ["bioink tissue engineering", "organoid biomaterial", "decellularized ECM scaffold"]),

    MaterialNode("bioinks", "Bioinks", "living_materials", "deep",
        "Cell-laden printable materials for bioprinting. GelMA, alginate, fibrin-based.",
        ["bioink bioprinting", "cell-laden hydrogel printing", "bioink rheology"]),

    MaterialNode("organoids", "Organoids", "living_materials", "deep",
        "Self-organising 3D cell structures. Intestinal, retinal, cardiac, brain.",
        ["organoid biomaterial", "scaffold organoid", "organ-on-chip biomaterial"]),

    MaterialNode("decell_ecm", "Decellularised ECM", "living_materials", "deep",
        "Native ECM retaining growth factors and structural proteins after decellularisation.",
        ["decellularized ECM scaffold", "dECM bioink", "decellularized tissue biomaterial"]),

    # ── Synthetic biology materials (promotable) ───────────────────────
    MaterialNode("synbio_materials", "Synthetic Biology Materials", None, "promotable",
        "Engineered protein materials, biosynthesised polymers, living composites.",
        ["engineered protein biomaterial", "recombinant collagen", "spider silk recombinant",
         "PHA biopolymer", "living material genetic circuit"]),
]

# ── Helper functions ──────────────────────────────────────────────────────────

def get_node(key: str) -> Optional[MaterialNode]:
    return next((n for n in TOPIC_TREE if n.key == key), None)


def get_children(parent_key: Optional[str]) -> List[MaterialNode]:
    """Return direct children of a node (or root nodes if parent_key is None)."""
    return [n for n in TOPIC_TREE if n.parent == parent_key]


def get_roots() -> List[MaterialNode]:
    return get_children(None)


def get_all_pubmed_terms(key: str) -> List[str]:
    """Collect pubmed_terms from a node and all its children."""
    node = get_node(key)
    if not node:
        return []
    terms = list(node.pubmed_terms)
    for child in get_children(key):
        terms.extend(get_all_pubmed_terms(child.key))
    return terms


def node_path(key: str) -> List[str]:
    """Return breadcrumb path from root to node: ['metals', 'titanium_alloys']"""
    node = get_node(key)
    if not node:
        return []
    if node.parent is None:
        return [key]
    return node_path(node.parent) + [key]