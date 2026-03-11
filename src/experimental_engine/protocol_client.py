"""
Protocol Client
================
protocols.io integration for finding and referencing published
experimental protocols relevant to biomaterials research.

Uses the protocols.io public API v4 (free, no key for public protocols).
Also provides a local protocol template KB for offline use.
"""

from __future__ import annotations

import logging
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)


# ── Data classes ──────────────────────────────────────────────

@dataclass
class Protocol:
    """A published or template protocol."""
    title: str
    source: str                 # "protocols.io", "local_kb"
    protocol_id: str            # doi or protocols.io ID
    url: str
    description: str
    steps: List[str]
    categories: List[str]       # e.g. ["cell_culture", "viability"]
    duration: str               # estimated time
    difficulty: str             # "beginner", "intermediate", "advanced"
    materials_needed: List[str]
    author: str = ""
    citations: int = 0


@dataclass
class ProtocolSearchResult:
    """Result of a protocol search."""
    query: str
    protocols: List[Protocol]
    source: str
    total_found: int


# ── Local protocol template KB ───────────────────────────────

_LOCAL_PROTOCOLS: List[Protocol] = [
    Protocol(
        title="Live/Dead Viability Assay on Scaffolds",
        source="local_kb",
        protocol_id="local-001",
        url="",
        description=(
            "Standard calcein-AM / ethidium homodimer viability assay "
            "adapted for 3D scaffolds. Includes z-stack confocal imaging."
        ),
        steps=[
            "Seed cells on scaffold at desired density (e.g. 1e5 cells/scaffold)",
            "Culture for 1, 3, 7 days in standard conditions",
            "Prepare staining solution: 2 uM calcein-AM + 4 uM EthD-1 in PBS",
            "Remove media, wash 2x with warm PBS",
            "Add staining solution (enough to cover scaffold)",
            "Incubate 30 min at 37C in dark",
            "Image with confocal microscope (z-stack for 3D scaffolds)",
            "Quantify live/dead ratio using ImageJ/FIJI",
        ],
        categories=["viability", "cytotoxicity", "scaffold", "confocal"],
        duration="2-3 hours (excluding culture time)",
        difficulty="beginner",
        materials_needed=[
            "Calcein-AM", "Ethidium homodimer-1 (EthD-1)",
            "PBS", "Confocal microscope", "Well plates",
        ],
    ),
    Protocol(
        title="MTT / MTS Metabolic Activity Assay",
        source="local_kb",
        protocol_id="local-002",
        url="",
        description=(
            "Colorimetric assay for cell metabolic activity. "
            "MTS (CellTiter 96) preferred over MTT for scaffolds as no "
            "DMSO solubilisation step needed."
        ),
        steps=[
            "Seed cells on scaffolds in 96- or 24-well plates",
            "At timepoint, aspirate media",
            "Add MTS reagent diluted in fresh media (20 uL MTS per 100 uL media)",
            "Incubate 1-4 hours at 37C (check manufacturer's protocol)",
            "Transfer supernatant to new plate (avoids scaffold interference)",
            "Read absorbance at 490 nm",
            "Calculate relative metabolic activity vs control",
        ],
        categories=["viability", "metabolic", "cytotoxicity", "high_throughput"],
        duration="1-4 hours",
        difficulty="beginner",
        materials_needed=[
            "MTS or MTT reagent", "Plate reader (490 nm)",
            "Multi-well plates", "Fresh culture media",
        ],
    ),
    Protocol(
        title="Scaffold Mechanical Testing (Compression)",
        source="local_kb",
        protocol_id="local-003",
        url="",
        description=(
            "Uniaxial compression testing of hydrogel or porous scaffolds. "
            "Yields compressive modulus, yield strength, and stress-strain curves."
        ),
        steps=[
            "Prepare cylindrical samples (8mm diameter x 4mm height typical)",
            "Equilibrate samples in PBS at 37C for 1 hour",
            "Mount sample on mechanical tester (Instron, TA, Bose)",
            "Apply preload (0.01 N) to ensure contact",
            "Compress at 1 mm/min (or 10% strain/min) to 80% strain",
            "Record force and displacement",
            "Calculate engineering stress = F/A0, strain = dL/L0",
            "Compressive modulus = slope of linear region (10-20% strain)",
            "Report modulus, yield point, and ultimate compressive strength",
        ],
        categories=["mechanical", "compression", "scaffold", "hydrogel"],
        duration="30 min per sample (excluding prep)",
        difficulty="intermediate",
        materials_needed=[
            "Mechanical testing machine (Instron/TA/Bose)",
            "Cylindrical punch or mould",
            "Calipers", "PBS",
        ],
    ),
    Protocol(
        title="Alizarin Red S Mineralisation Assay",
        source="local_kb",
        protocol_id="local-004",
        url="",
        description=(
            "Calcium deposition staining for osteogenic differentiation. "
            "Quantifiable by cetylpyridinium chloride (CPC) extraction."
        ),
        steps=[
            "Culture cells in osteogenic media for 7-21 days",
            "Aspirate media, wash 2x PBS",
            "Fix with 4% paraformaldehyde for 15 min at RT",
            "Wash 3x with distilled water",
            "Add 2% Alizarin Red S solution (pH 4.1-4.3) for 20 min at RT",
            "Wash 5x with distilled water to remove unbound dye",
            "Image for qualitative assessment (red = mineralised)",
            "For quantification: extract with 10% CPC for 1 hr at 37C",
            "Read absorbance at 562 nm, compare to standard curve",
        ],
        categories=["osteogenic", "mineralisation", "bone", "differentiation"],
        duration="1 hour (excluding culture period)",
        difficulty="beginner",
        materials_needed=[
            "Alizarin Red S", "Paraformaldehyde (4%)",
            "Cetylpyridinium chloride (CPC)", "Plate reader (562 nm)",
        ],
    ),
    Protocol(
        title="Degradation Study (Mass Loss + pH)",
        source="local_kb",
        protocol_id="local-005",
        url="",
        description=(
            "In vitro degradation study tracking mass loss and pH change "
            "over time. Standard for characterising degradable scaffolds."
        ),
        steps=[
            "Prepare samples (n>=3 per timepoint), record dry weight (W0)",
            "Immerse in PBS (pH 7.4) at 37C, 5 mL per sample",
            "At each timepoint (1, 3, 7, 14, 28, 56 days):",
            "  - Measure pH of degradation medium",
            "  - Remove samples, blot dry, weigh (wet weight)",
            "  - Lyophilise and weigh (dry weight, Wt)",
            "  - Replace degradation medium with fresh PBS",
            "Calculate: mass loss (%) = (W0 - Wt) / W0 * 100",
            "Plot mass loss and pH vs time",
            "Characterise degradation products by GC-MS if needed",
        ],
        categories=["degradation", "scaffold", "characterisation"],
        duration="Weeks to months (longitudinal)",
        difficulty="beginner",
        materials_needed=[
            "Analytical balance (0.1 mg)",
            "PBS (pH 7.4)", "Incubator (37C)",
            "pH meter", "Lyophiliser",
        ],
    ),
    Protocol(
        title="SEM Sample Preparation (Biological on Scaffold)",
        source="local_kb",
        protocol_id="local-006",
        url="",
        description=(
            "Fixation, dehydration, and sputter coating for SEM imaging "
            "of cells on biomaterial scaffolds."
        ),
        steps=[
            "Fix samples in 2.5% glutaraldehyde in 0.1M cacodylate buffer, 2 hr at 4C",
            "Wash 3x10 min in cacodylate buffer",
            "Post-fix in 1% OsO4 for 1 hr (optional, improves contrast)",
            "Wash 3x10 min in distilled water",
            "Dehydrate in graded ethanol: 30%, 50%, 70%, 90%, 100% (2x), 10 min each",
            "Critical point dry (CPD) or HMDS dry (3 changes, air dry overnight)",
            "Mount on stubs with carbon tape",
            "Sputter coat with gold or platinum (5-10 nm)",
            "Image at 5-15 kV accelerating voltage",
        ],
        categories=["sem", "microscopy", "scaffold", "characterisation"],
        duration="1 day (including drying)",
        difficulty="intermediate",
        materials_needed=[
            "Glutaraldehyde (2.5%)", "Cacodylate buffer",
            "Ethanol series", "Critical point dryer or HMDS",
            "Sputter coater", "SEM",
        ],
    ),
    Protocol(
        title="Flow Cytometry: MSC Surface Marker Panel (ISCT)",
        source="local_kb",
        protocol_id="local-007",
        url="",
        description=(
            "ISCT minimal criteria panel for mesenchymal stromal cell identity: "
            "positive for CD73, CD90, CD105; negative for CD34, CD45, HLA-DR."
        ),
        steps=[
            "Harvest cells (trypsin-EDTA, gentle), count and assess viability",
            "Resuspend at 1e6 cells/mL in FACS buffer (PBS + 2% FBS + 1 mM EDTA)",
            "Aliquot 100 uL (1e5 cells) per tube",
            "Add antibodies: CD73-PE, CD90-FITC, CD105-APC, CD34-PerCP, CD45-APC-Cy7, HLA-DR-PE-Cy7",
            "Include: unstained control, single-colour controls, FMO controls",
            "Incubate 20 min at 4C in dark",
            "Wash 2x with FACS buffer, centrifuge 300g 5 min",
            "Resuspend in 300 uL FACS buffer + viability dye (7-AAD or DAPI)",
            "Acquire on flow cytometer (minimum 10,000 events in live gate)",
            "Gate: FSC/SSC -> singlets -> live cells -> marker expression",
            "ISCT pass: >=95% positive for CD73, CD90, CD105; <=2% for CD34, CD45, HLA-DR",
        ],
        categories=["flow_cytometry", "msc", "identity", "isct"],
        duration="2-3 hours",
        difficulty="intermediate",
        materials_needed=[
            "Antibodies (CD73-PE, CD90-FITC, CD105-APC, CD34, CD45, HLA-DR)",
            "FACS buffer", "Viability dye (7-AAD)",
            "Flow cytometer",
        ],
    ),
    Protocol(
        title="RNA Extraction from Scaffold-Seeded Cells",
        source="local_kb",
        protocol_id="local-008",
        url="",
        description=(
            "TRIzol-based RNA extraction adapted for cells growing on/in "
            "3D scaffolds. Critical for downstream RNA-seq or qPCR."
        ),
        steps=[
            "Aspirate media, wash scaffold with cold PBS",
            "Add 1 mL TRIzol directly to scaffold in tube",
            "Homogenise thoroughly (vortex + pipette + optional tissue grinder)",
            "Incubate 5 min at RT to complete lysis",
            "For PLGA/PCL scaffolds: centrifuge to remove polymer debris before chloroform step",
            "Add 200 uL chloroform per mL TRIzol, shake vigorously 15 sec",
            "Incubate 3 min RT, centrifuge 12,000g 15 min 4C",
            "Transfer aqueous phase (top) to new tube",
            "Precipitate with 500 uL isopropanol, -20C 30 min",
            "Centrifuge 12,000g 10 min 4C, discard supernatant",
            "Wash pellet with 75% ethanol, air dry",
            "Resuspend in RNase-free water",
            "Check concentration (NanoDrop) and integrity (Bioanalyzer, RIN > 7)",
        ],
        categories=["rna", "extraction", "scaffold", "transcriptomics"],
        duration="2-3 hours",
        difficulty="intermediate",
        materials_needed=[
            "TRIzol reagent", "Chloroform", "Isopropanol",
            "75% ethanol (RNase-free)", "RNase-free water",
            "NanoDrop or equivalent",
        ],
    ),
]


# ── Public API ───────────────────────────────────────────────

def search_protocols(
    query: str,
    source: str = "local",     # "local", "api", "both"
    max_results: int = 10,
) -> ProtocolSearchResult:
    """Search for protocols by keyword.

    Parameters
    ----------
    query : str
        Search keywords.
    source : str
        "local" for offline KB, "api" for protocols.io, "both" for both.
    max_results : int
        Maximum results to return.

    Returns
    -------
    ProtocolSearchResult
    """
    results: List[Protocol] = []

    if source in ("local", "both"):
        local = _search_local(query)
        results.extend(local)

    if source in ("api", "both"):
        try:
            api_results = _search_protocols_io(query, max_results)
            results.extend(api_results)
        except Exception as e:
            logger.warning("protocols.io API error: %s", e)

    results = results[:max_results]

    return ProtocolSearchResult(
        query=query,
        protocols=results,
        source=source,
        total_found=len(results),
    )


def get_protocol_by_id(protocol_id: str) -> Optional[Protocol]:
    """Look up a specific protocol by ID."""
    for p in _LOCAL_PROTOCOLS:
        if p.protocol_id == protocol_id:
            return p
    return None


def get_protocols_for_assay(assay_name: str) -> List[Protocol]:
    """Find protocols relevant to a specific assay type."""
    return _search_local(assay_name)


def list_local_protocols() -> List[Protocol]:
    """Return all local protocol templates."""
    return list(_LOCAL_PROTOCOLS)


# ── Private helpers ──────────────────────────────────────────

def _search_local(query: str) -> List[Protocol]:
    """Search local protocol KB by keyword matching."""
    q_lower = query.lower()
    terms = q_lower.split()
    scored: List[tuple] = []

    for protocol in _LOCAL_PROTOCOLS:
        score = 0
        searchable = (
            protocol.title.lower() + " " +
            protocol.description.lower() + " " +
            " ".join(protocol.categories)
        )
        for term in terms:
            if term in searchable:
                score += 1
        if score > 0:
            scored.append((score, protocol))

    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored]


def _search_protocols_io(query: str, max_results: int = 10) -> List[Protocol]:
    """Search protocols.io public API."""
    import urllib.request

    url = (
        f"https://www.protocols.io/api/v4/protocols"
        f"?filter=public&key={quote(query)}"
        f"&page_size={max_results}&fields=title,description,doi,uri,stats"
    )

    try:
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        logger.warning("protocols.io API request failed: %s", e)
        return []

    protocols = []
    for item in data.get("items", []):
        protocols.append(Protocol(
            title=item.get("title", "Untitled"),
            source="protocols.io",
            protocol_id=item.get("doi", item.get("uri", "")),
            url=f"https://www.protocols.io/{item.get('uri', '')}",
            description=item.get("description", "")[:500],
            steps=[],  # Full steps require separate API call
            categories=[],
            duration="",
            difficulty="",
            materials_needed=[],
            author=item.get("authors", [{}])[0].get("name", "") if item.get("authors") else "",
            citations=item.get("stats", {}).get("number_of_citations", 0),
        ))

    return protocols
