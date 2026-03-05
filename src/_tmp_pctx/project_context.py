"""
ProjectContext — the active project's scope, shared across all tabs.

Every tab reads from the active context to scope its queries:
  - target_tissue  -> filter GEO datasets, organoid KB, regulatory matrix
  - regulatory_aim -> ISO 10993 test matrix, device classification
  - budget_tier    -> assay recommender cost flags
  - focus_keywords -> PubMed search boosting, materials taxonomy default branch
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class ProjectContext:
    """Immutable snapshot of the active project's scope parameters."""

    project_id: int
    name: str
    target_tissue: str = ""
    regulatory_aim: str = ""       # e.g. "CE Class IIb", "FDA 510(k)", "ATMP"
    budget_tier: str = ""          # "academic", "startup", "industry"
    timeline_months: int = 0
    focus_keywords: List[str] = field(default_factory=list)
    description: str = ""

    @classmethod
    def from_db_row(cls, row) -> "ProjectContext":
        """Build from a sqlite3.Row or dict returned by DatabaseManager."""
        keywords_raw = row["focus_keywords"] or "" if isinstance(row, dict) else (row[7] or "")
        if isinstance(row, dict):
            keywords_raw = row.get("focus_keywords", "") or ""
            return cls(
                project_id=row["id"],
                name=row["name"],
                target_tissue=row.get("target_tissue", "") or "",
                regulatory_aim=row.get("regulatory_aim", "") or "",
                budget_tier=row.get("budget_tier", "") or "",
                timeline_months=row.get("timeline_months", 0) or 0,
                focus_keywords=[k.strip() for k in keywords_raw.split(",") if k.strip()],
                description=row.get("description", "") or "",
            )
        # sqlite3.Row
        return cls(
            project_id=row["id"],
            name=row["name"],
            target_tissue=row["target_tissue"] or "",
            regulatory_aim=row["regulatory_aim"] or "",
            budget_tier=row["budget_tier"] or "",
            timeline_months=row["timeline_months"] or 0,
            focus_keywords=[k.strip() for k in (row["focus_keywords"] or "").split(",") if k.strip()],
            description=row["description"] or "",
        )

    def to_dict(self) -> dict:
        return {
            "id": self.project_id,
            "name": self.name,
            "target_tissue": self.target_tissue,
            "regulatory_aim": self.regulatory_aim,
            "budget_tier": self.budget_tier,
            "timeline_months": self.timeline_months,
            "focus_keywords": ", ".join(self.focus_keywords),
            "description": self.description,
        }

    @property
    def has_tissue(self) -> bool:
        return bool(self.target_tissue.strip())

    @property
    def is_regulated(self) -> bool:
        return bool(self.regulatory_aim.strip())

    @property
    def is_atmp(self) -> bool:
        return "ATMP" in self.regulatory_aim.upper()

    @property
    def pubmed_tissue_term(self) -> Optional[str]:
        return self.target_tissue.strip() or None

    def keyword_string(self) -> str:
        return ", ".join(self.focus_keywords) if self.focus_keywords else ""

    def __str__(self) -> str:
        parts = [self.name]
        if self.target_tissue:
            parts.append(f"tissue: {self.target_tissue}")
        if self.regulatory_aim:
            parts.append(f"reg: {self.regulatory_aim}")
        return " | ".join(parts)
