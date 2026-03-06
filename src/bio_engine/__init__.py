"""Bio Engine -- GEO, transcriptomics, single-cell, tissue interaction."""

from .geo_client import GEOClient
from .transcriptomics import (
    run_deg_analysis,
    load_series_matrix,
    make_demo_matrix,
    DEGResult,
    VolcanoPoint,
)

__all__ = [
    "GEOClient",
    "run_deg_analysis",
    "load_series_matrix",
    "make_demo_matrix",
    "DEGResult",
    "VolcanoPoint",
]
