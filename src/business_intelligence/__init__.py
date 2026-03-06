"""
Business Intelligence Engine
=============================
Market data, stakeholder map, SWOT, competitive landscape, and strategic synthesis.
"""

from .market_kb import MarketSegment, ALL_SEGMENTS, get_segment, search_segments, get_all_segments
from .stakeholder_kb import (
    Stakeholder, ALL_STAKEHOLDERS,
    get_stakeholders_by_type, get_commonly_missed, get_high_influence, get_stakeholder,
)
from .swot_engine import SWOTEngine, SWOTAnalysis, SWOTItem, CompetitorEntry
from .strategic_summary import StrategicSummaryEngine, SynthesisContext, StrategyResult

__all__ = [
    "MarketSegment", "ALL_SEGMENTS", "get_segment", "search_segments", "get_all_segments",
    "Stakeholder", "ALL_STAKEHOLDERS",
    "get_stakeholders_by_type", "get_commonly_missed", "get_high_influence", "get_stakeholder",
    "SWOTEngine", "SWOTAnalysis", "SWOTItem", "CompetitorEntry",
    "StrategicSummaryEngine", "SynthesisContext", "StrategyResult",
]
