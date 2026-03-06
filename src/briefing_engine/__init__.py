"""
Briefing Engine
===============
Context assembly and AI-powered Technical / Executive briefing generation.
"""

from .context_assembler import ContextAssembler, BriefingContext
from .briefing_generator import BriefingGenerator, BriefingSection, TECHNICAL_SECTIONS, EXECUTIVE_SECTIONS

__all__ = [
    "ContextAssembler", "BriefingContext",
    "BriefingGenerator", "BriefingSection",
    "TECHNICAL_SECTIONS", "EXECUTIVE_SECTIONS",
]
