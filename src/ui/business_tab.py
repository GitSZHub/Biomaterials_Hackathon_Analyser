"""
Business Intelligence Tab
=========================
Six sub-tabs:
  1. Market Analysis     -- curated segment data + market sizing
  2. Competitive Landscape -- competitor tracking table
  3. Stakeholder Map     -- curated + user-added stakeholders, influence matrix
  4. SWOT Analysis       -- structured SWOT with evidence links
  5. Patent Search       -- keyword-driven patent landscape (links to Google Patents / Espacenet)
  6. Strategic Insight   -- Claude synthesises all quadrants into actionable advice
"""

from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel, QPushButton,
    QComboBox, QTextEdit, QTableWidget, QTableWidgetItem, QFrame,
    QLineEdit, QSplitter, QHeaderView, QDialog, QDialogButtonBox,
    QFormLayout, QPlainTextEdit, QScrollArea, QCheckBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QFont, QColor, QDesktopServices
import qtawesome as qta

logger = logging.getLogger(__name__)

# ── Safe imports ───────────────────────────────────────────────────────────────

try:
    from business_intelligence import (
        ALL_SEGMENTS, get_segment, search_segments, get_all_segments,
        ALL_STAKEHOLDERS, get_stakeholders_by_type, get_commonly_missed,
        SWOTEngine, SWOTAnalysis, SWOTItem, CompetitorEntry,
        StrategicSummaryEngine, SynthesisContext,
        MarketSegment, Stakeholder,
    )
    _BI_OK = True
except ImportError as e:
    logger.warning("business_intelligence not available: %s", e)
    _BI_OK = False


# ── Worker threads ─────────────────────────────────────────────────────────────

class StrategicInsightWorker(QThread):
    finished = pyqtSignal(object)   # StrategyResult
    error    = pyqtSignal(str)

    def __init__(self, context):
        super().__init__()
        self._ctx = context

    def run(self):
        try:
            result = StrategicSummaryEngine().synthesise(self._ctx)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


# ── Main tab ───────────────────────────────────────────────────────────────────

class BusinessTab(QWidget):

    AUDIENCES = [
        ("Executive (balanced overview)", "executive"),
        ("Investor / BD",                 "investor"),
        ("Technical / R&D team",          "technical"),
        ("Clinical KOLs",                 "clinical"),
        ("Regulatory affairs",            "regulatory"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._swot: Optional[SWOTAnalysis] = None
        self._worker: Optional[QThread] = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()
        tabs.addTab(self._build_market_tab(),        qta.icon('fa.pie-chart'),    "Market Analysis")
        tabs.addTab(self._build_competitive_tab(),   qta.icon('fa.sitemap'),      "Competitive")
        tabs.addTab(self._build_stakeholder_tab(),   qta.icon('fa.users'),        "Stakeholders")
        tabs.addTab(self._build_swot_tab(),          qta.icon('fa.th-large'),     "SWOT")
        tabs.addTab(self._build_patent_tab(),        qta.icon('fa.legal'),        "Patents")
        tabs.addTab(self._build_strategy_tab(),      qta.icon('fa.lightbulb-o'), "Strategic Insight")
        layout.addWidget(tabs)

    # ── Sub-tab 1: Market Analysis ─────────────────────────────────────────────

    def _build_market_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Segment:"))
        self._market_combo = QComboBox()
        self._market_combo.addItem("-- Select segment --")
        if _BI_OK:
            for seg in get_all_segments():
                self._market_combo.addItem(seg.name, seg.key)
        self._market_combo.currentIndexChanged.connect(self._show_market_segment)
        bar.addWidget(self._market_combo)

        bar.addWidget(QLabel("or filter by tissue:"))
        self._market_tissue = QComboBox()
        self._market_tissue.addItem("All")
        self._market_tissue.addItems(["bone", "cartilage", "skin", "cardiovascular", "neural", "dental"])
        self._market_tissue.currentTextChanged.connect(self._filter_by_tissue)
        bar.addWidget(self._market_tissue)
        bar.addStretch()
        layout.addLayout(bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._market_content = QWidget()
        self._market_content_layout = QVBoxLayout(self._market_content)
        self._market_content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._market_content)
        layout.addWidget(scroll)

        placeholder = QLabel("Select a market segment above to view curated market intelligence.")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color:#adb5bd; font-size:12px; padding:40px;")
        self._market_content_layout.addWidget(placeholder)
        return w

    def _filter_by_tissue(self, tissue: str):
        if not _BI_OK or tissue == "All":
            return
        segs = search_segments(tissue)
        if segs:
            for i in range(self._market_combo.count()):
                if self._market_combo.itemData(i) == segs[0].key:
                    self._market_combo.setCurrentIndex(i)
                    break

    def _show_market_segment(self, idx: int):
        if not _BI_OK or idx == 0:
            return
        key = self._market_combo.itemData(idx)
        seg = get_segment(key)
        if seg is None:
            return

        for i in reversed(range(self._market_content_layout.count())):
            item = self._market_content_layout.itemAt(i)
            if item and item.widget():
                item.widget().deleteLater()

        # Header metrics
        hdr = QFrame()
        hdr.setStyleSheet("background:#2E86AB; border-radius:6px;")
        hdr_layout = QHBoxLayout(hdr)
        for label, value in [
            ("Market Size (2024)", f"${seg.market_size_2024}B"),
            ("CAGR 2024-2030",    f"{seg.cagr}%/yr"),
            ("Projected (2030)",  f"${seg.market_2030}B"),
        ]:
            col = QVBoxLayout()
            val_lbl = QLabel(value)
            val_lbl.setFont(QFont("Arial", 16, QFont.Weight.Bold))
            val_lbl.setStyleSheet("color:white;")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            key_lbl = QLabel(label)
            key_lbl.setStyleSheet("color:rgba(255,255,255,0.75); font-size:10px;")
            key_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(val_lbl); col.addWidget(key_lbl)
            hdr_layout.addLayout(col)
        self._market_content_layout.addWidget(hdr)

        geo_box = self._make_info_box("Geographic Split",
                                      "\n".join(f"  {r}: {s}" for r, s in seg.geography_split.items()))
        self._market_content_layout.addWidget(geo_box)

        split_w = QWidget()
        split = QHBoxLayout(split_w)
        split.addWidget(self._make_list_box("Growth Drivers", seg.growth_drivers, "#d4edda", "#155724"))
        split.addWidget(self._make_list_box("Restraints", seg.restraints, "#f8d7da", "#721c24"))
        self._market_content_layout.addWidget(split_w)

        self._market_content_layout.addWidget(
            self._make_list_box("Unmet Needs (Opportunity Space)", seg.unmet_needs, "#fff3cd", "#856404"))

        self._market_content_layout.addWidget(
            self._make_info_box("Key Players", "  |  ".join(seg.key_players)))

        if seg.reimbursement_notes:
            self._market_content_layout.addWidget(
                self._make_info_box("Reimbursement Notes", seg.reimbursement_notes))

        if seg.regulatory_hurdles:
            self._market_content_layout.addWidget(
                self._make_info_box("Regulatory Hurdles", seg.regulatory_hurdles))

    def _make_info_box(self, title: str, text: str) -> QFrame:
        box = QFrame()
        box.setStyleSheet("QFrame{background:#f8f9fa;border:1px solid #dee2e6;border-radius:4px;margin:2px 0;}")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 6, 10, 6)
        t = QLabel(title); t.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        t.setStyleSheet("color:#495057;")
        v = QLabel(text); v.setWordWrap(True); v.setStyleSheet("color:#212529; font-size:10px;")
        layout.addWidget(t); layout.addWidget(v)
        return box

    def _make_list_box(self, title: str, items: list, bg: str, fg: str) -> QFrame:
        box = QFrame()
        box.setStyleSheet(f"QFrame{{background:{bg};border:1px solid {fg};border-radius:4px;margin:2px;padding:4px;}}")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(8, 4, 8, 4)
        t = QLabel(title); t.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        t.setStyleSheet(f"color:{fg};"); layout.addWidget(t)
        for item in items:
            lbl = QLabel(f"• {item}"); lbl.setWordWrap(True)
            lbl.setStyleSheet(f"color:{fg}; font-size:10px;"); layout.addWidget(lbl)
        return box

    # ── Sub-tab 2: Competitive Landscape ──────────────────────────────────────

    def _build_competitive_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        bar = QHBoxLayout()
        add_btn = QPushButton(qta.icon('fa.plus'), " Add Competitor")
        add_btn.setStyleSheet(self._primary_btn_style())
        add_btn.clicked.connect(self._add_competitor)
        bar.addWidget(add_btn)
        bar.addStretch()
        layout.addLayout(bar)

        self._comp_table = QTableWidget()
        self._comp_table.setColumnCount(6)
        self._comp_table.setHorizontalHeaderLabels([
            "Company", "Product", "Stage", "Strengths", "Weaknesses", "Notes"
        ])
        self._comp_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._comp_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._comp_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self._comp_table)
        return w

    def _add_competitor(self):
        dlg = _CompetitorDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            r = self._comp_table.rowCount()
            self._comp_table.insertRow(r)
            self._comp_table.setItem(r, 0, QTableWidgetItem(data["company"]))
            self._comp_table.setItem(r, 1, QTableWidgetItem(data["product"]))
            stage_item = QTableWidgetItem(data["stage"])
            colors = {"market": "#d4edda", "clinical": "#fff3cd",
                      "preclinical": "#cce5ff", "research": "#f8f9fa"}
            stage_item.setBackground(QColor(colors.get(data["stage"], "#ffffff")))
            self._comp_table.setItem(r, 2, stage_item)
            self._comp_table.setItem(r, 3, QTableWidgetItem(data["strengths"]))
            self._comp_table.setItem(r, 4, QTableWidgetItem(data["weaknesses"]))
            self._comp_table.setItem(r, 5, QTableWidgetItem(data["notes"]))
            if self._swot is not None:
                self._swot.add_competitor(
                    name=data["company"], product=data["product"], stage=data["stage"],
                    strengths=[s.strip() for s in data["strengths"].split(";") if s.strip()],
                    weaknesses=[s.strip() for s in data["weaknesses"].split(";") if s.strip()],
                    notes=data["notes"],
                )

    # ── Sub-tab 3: Stakeholder Map ─────────────────────────────────────────────

    def _build_stakeholder_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Filter:"))
        self._sh_filter = QComboBox()
        self._sh_filter.addItems(["All", "clinical", "payer", "hta", "regulator", "industry", "patient", "investor"])
        self._sh_filter.currentTextChanged.connect(self._filter_stakeholders)
        bar.addWidget(self._sh_filter)

        self._sh_missed_chk = QCheckBox("Commonly missed only")
        self._sh_missed_chk.stateChanged.connect(self._filter_stakeholders)
        bar.addWidget(self._sh_missed_chk)
        bar.addStretch()
        layout.addLayout(bar)

        self._sh_table = QTableWidget()
        self._sh_table.setColumnCount(5)
        self._sh_table.setHorizontalHeaderLabels([
            "Stakeholder", "Category", "Influence", "Role", "Often Missed?"
        ])
        self._sh_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._sh_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._sh_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._sh_table.itemSelectionChanged.connect(self._show_stakeholder_detail)
        layout.addWidget(self._sh_table)

        self._sh_detail = QTextEdit()
        self._sh_detail.setMaximumHeight(130)
        self._sh_detail.setReadOnly(True)
        self._sh_detail.setPlaceholderText("Select a stakeholder to view engagement strategy...")
        layout.addWidget(self._sh_detail)

        self._populate_stakeholders(list(ALL_STAKEHOLDERS.values()) if _BI_OK else [])
        return w

    def _filter_stakeholders(self):
        if not _BI_OK:
            return
        category = self._sh_filter.currentText()
        missed_only = self._sh_missed_chk.isChecked()
        if missed_only:
            stakeholders = get_commonly_missed()
        elif category != "All":
            stakeholders = get_stakeholders_by_type(category)
        else:
            stakeholders = list(ALL_STAKEHOLDERS.values())
        self._populate_stakeholders(stakeholders)

    def _populate_stakeholders(self, stakeholders: list):
        self._sh_table.setRowCount(0)
        influence_colors = {"high": "#d4edda", "medium": "#fff3cd", "low": "#f8f9fa"}
        for s in stakeholders:
            r = self._sh_table.rowCount()
            self._sh_table.insertRow(r)
            self._sh_table.setItem(r, 0, QTableWidgetItem(s.name))
            self._sh_table.setItem(r, 1, QTableWidgetItem(s.category.title()))
            inf_item = QTableWidgetItem(s.influence.upper())
            inf_item.setBackground(QColor(influence_colors.get(s.influence, "#ffffff")))
            self._sh_table.setItem(r, 2, inf_item)
            self._sh_table.setItem(r, 3, QTableWidgetItem(s.role[:80] + ("..." if len(s.role) > 80 else "")))
            missed_item = QTableWidgetItem("YES" if s.typically_missed else "")
            if s.typically_missed:
                missed_item.setForeground(QColor("#dc3545"))
            self._sh_table.setItem(r, 4, missed_item)
            self._sh_table.item(r, 0).setData(Qt.ItemDataRole.UserRole, s)

    def _show_stakeholder_detail(self):
        sel = self._sh_table.selectedItems()
        if not sel:
            return
        s = self._sh_table.item(sel[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        if s is None:
            return
        lines = [
            f"<b>{s.name}</b> [{s.category.upper()} | Influence: {s.influence.upper()}]",
            f"<b>Role:</b> {s.role}",
            f"<b>Key interests:</b> {'; '.join(s.interests[:3])}",
            f"<b>Engagement strategy:</b> {s.engagement_strategy}",
            f"<b>Examples:</b> {', '.join(s.examples[:4])}",
        ]
        self._sh_detail.setHtml("<br>".join(lines))

    # ── Sub-tab 4: SWOT Analysis ───────────────────────────────────────────────

    def _build_swot_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        bar = QHBoxLayout()
        self._swot_project = QLineEdit()
        self._swot_project.setPlaceholderText("Project name...")
        self._swot_tissue = QComboBox()
        self._swot_tissue.addItems(["bone", "cartilage", "skin", "cardiovascular", "neural", "general"])
        self._swot_scenario = QComboBox()
        self._swot_scenario.addItems(["A", "B", "C", "D"])

        create_btn = QPushButton(qta.icon('fa.plus'), " Create / Seed SWOT")
        create_btn.setStyleSheet(self._primary_btn_style())
        create_btn.clicked.connect(self._create_swot)

        bar.addWidget(QLabel("Project:")); bar.addWidget(self._swot_project)
        bar.addWidget(QLabel("Tissue:")); bar.addWidget(self._swot_tissue)
        bar.addWidget(QLabel("Scenario:")); bar.addWidget(self._swot_scenario)
        bar.addWidget(create_btn)
        layout.addLayout(bar)

        lens_bar = QHBoxLayout()
        lens_bar.addWidget(QLabel("Lens:"))
        self._swot_lens = QComboBox()
        self._swot_lens.addItems(["general", "investor", "clinical", "regulatory", "payer"])
        self._swot_lens.currentTextChanged.connect(self._refresh_swot_view)
        lens_bar.addWidget(self._swot_lens)
        lens_bar.addStretch()
        add_item_btn = QPushButton(qta.icon('fa.edit'), " Add Item")
        add_item_btn.clicked.connect(self._add_swot_item)
        lens_bar.addWidget(add_item_btn)
        layout.addLayout(lens_bar)

        # 4-quadrant display
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_w = QWidget(); left_l = QVBoxLayout(left_w)
        right_w = QWidget(); right_l = QVBoxLayout(right_w)

        self._swot_s_lbl = self._make_swot_quad_frame("STRENGTHS", "#d4edda", "#155724")
        self._swot_w_lbl = self._make_swot_quad_frame("WEAKNESSES", "#f8d7da", "#721c24")
        self._swot_o_lbl = self._make_swot_quad_frame("OPPORTUNITIES", "#d1ecf1", "#0c5460")
        self._swot_t_lbl = self._make_swot_quad_frame("THREATS", "#fff3cd", "#856404")

        left_l.addWidget(self._swot_s_lbl[0]); left_l.addWidget(self._swot_w_lbl[0])
        right_l.addWidget(self._swot_o_lbl[0]); right_l.addWidget(self._swot_t_lbl[0])

        splitter.addWidget(left_w); splitter.addWidget(right_w)
        layout.addWidget(splitter)
        return w

    def _make_swot_quad_frame(self, label: str, bg: str, fg: str):
        box = QFrame()
        box.setStyleSheet(f"QFrame{{background:{bg};border:1px solid {fg};border-radius:6px;margin:2px;}}")
        v = QVBoxLayout(box)
        title = QLabel(label); title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{fg}; padding:4px;"); v.addWidget(title)
        content = QLabel("(create a SWOT above to populate)")
        content.setWordWrap(True)
        content.setStyleSheet(f"color:{fg}; font-size:10px; padding:4px;")
        content.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        v.addWidget(content)
        return box, content

    def _create_swot(self):
        if not _BI_OK:
            return
        name = self._swot_project.text().strip() or "Untitled Project"
        self._swot = SWOTEngine().create(
            name, self._swot_tissue.currentText(),
            self._swot_scenario.currentText(), pre_seed=True,
        )
        self._refresh_swot_view()

    def _refresh_swot_view(self):
        if self._swot is None:
            return
        lens = self._swot_lens.currentText()
        view = self._swot.filter_by_lens(lens)

        def _render(items) -> str:
            if not items:
                return "(none)"
            priority_tag = {"high": "[!]", "medium": "[-]", "low": "[.]"}
            return "\n".join(
                f"{priority_tag.get(i.priority, '')} {i.text}"
                + (f"  ({i.evidence})" if i.evidence else "")
                for i in items
            )

        self._swot_s_lbl[1].setText(_render(view.strengths))
        self._swot_w_lbl[1].setText(_render(view.weaknesses))
        self._swot_o_lbl[1].setText(_render(view.opportunities))
        self._swot_t_lbl[1].setText(_render(view.threats))

    def _add_swot_item(self):
        if self._swot is None:
            return
        dlg = _SWOTItemDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            methods = {
                "Strength":    self._swot.add_strength,
                "Weakness":    self._swot.add_weakness,
                "Opportunity": self._swot.add_opportunity,
                "Threat":      self._swot.add_threat,
            }
            fn = methods.get(data["quadrant"])
            if fn:
                fn(data["text"], data["evidence"], data["lens"], data["priority"])
            self._refresh_swot_view()

    # ── Sub-tab 5: Patent Search ───────────────────────────────────────────────

    def _build_patent_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        desc = QLabel(
            "Search buttons open Google Patents or Espacenet in your browser. "
            "Track relevant patents manually using the table below."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#495057; font-size:11px; padding:8px;")
        layout.addWidget(desc)

        bar = QHBoxLayout()
        self._patent_query = QLineEdit()
        self._patent_query.setPlaceholderText("e.g. hydroxyapatite scaffold bone regeneration")
        bar.addWidget(self._patent_query)

        gp_btn = QPushButton(qta.icon('fa.external-link'), " Google Patents")
        gp_btn.setStyleSheet(self._primary_btn_style())
        gp_btn.clicked.connect(self._open_google_patents)
        bar.addWidget(gp_btn)

        ep_btn = QPushButton(qta.icon('fa.external-link'), " Espacenet")
        ep_btn.clicked.connect(self._open_espacenet)
        bar.addWidget(ep_btn)
        layout.addLayout(bar)

        add_btn = QPushButton(qta.icon('fa.plus'), " Add Patent to Tracker")
        add_btn.clicked.connect(self._add_patent)
        layout.addWidget(add_btn)

        self._patent_table = QTableWidget()
        self._patent_table.setColumnCount(6)
        self._patent_table.setHorizontalHeaderLabels([
            "Patent / App No.", "Title", "Assignee", "Priority Date", "Status", "Relevance"
        ])
        self._patent_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._patent_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._patent_table)

        note = QLabel(
            "Note: FTO analysis requires specialist patent attorneys. This tracker is for high-level awareness only."
        )
        note.setStyleSheet("color:#6c757d; font-size:10px; padding:4px; font-style:italic;")
        layout.addWidget(note)
        return w

    def _open_google_patents(self):
        query = self._patent_query.text().strip().replace(" ", "+")
        QDesktopServices.openUrl(QUrl(f"https://patents.google.com/?q={query}&country=US,EP,WO"))

    def _open_espacenet(self):
        query = self._patent_query.text().strip().replace(" ", "+")
        QDesktopServices.openUrl(QUrl(f"https://worldwide.espacenet.com/patent/search?q={query}"))

    def _add_patent(self):
        dlg = _PatentDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            r = self._patent_table.rowCount()
            self._patent_table.insertRow(r)
            for col, key in enumerate(["number", "title", "assignee", "date", "status", "relevance"]):
                self._patent_table.setItem(r, col, QTableWidgetItem(data.get(key, "")))

    # ── Sub-tab 6: Strategic Insight ───────────────────────────────────────────

    def _build_strategy_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        desc = QLabel(
            "Claude synthesises market, stakeholder, competitive, and SWOT data into a concise strategic "
            "paragraph with next-action recommendations. Create a SWOT and add competitors first for best results."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#495057; font-size:11px; padding:8px;")
        layout.addWidget(desc)

        form_layout = QFormLayout()
        self._strat_project = QLineEdit()
        self._strat_project.setPlaceholderText("Project name...")
        form_layout.addRow("Project:", self._strat_project)

        self._strat_tissue = QComboBox()
        self._strat_tissue.addItems(["bone", "cartilage", "skin", "cardiovascular", "neural", "general"])
        form_layout.addRow("Tissue:", self._strat_tissue)

        self._strat_audience = QComboBox()
        for label, _ in self.AUDIENCES:
            self._strat_audience.addItem(label)
        form_layout.addRow("Audience:", self._strat_audience)

        self._strat_notes = QPlainTextEdit()
        self._strat_notes.setMaximumHeight(60)
        self._strat_notes.setPlaceholderText("Any additional context for Claude (optional)...")
        form_layout.addRow("Notes:", self._strat_notes)

        form_w = QWidget(); form_w.setLayout(form_layout)
        layout.addWidget(form_w)

        btn_bar = QHBoxLayout()
        self._strat_btn = QPushButton(qta.icon('fa.lightbulb-o'), "  Generate Strategic Insight")
        self._strat_btn.setStyleSheet(self._primary_btn_style())
        self._strat_btn.clicked.connect(self._run_strategy)
        btn_bar.addWidget(self._strat_btn)
        btn_bar.addStretch()
        layout.addLayout(btn_bar)

        self._strat_insight = QTextEdit()
        self._strat_insight.setReadOnly(True)
        self._strat_insight.setPlaceholderText(
            "Strategic insight will appear here.\n"
            "Tip: create a SWOT and add competitors first for richer analysis."
        )
        layout.addWidget(self._strat_insight)
        return w

    def _run_strategy(self):
        _, audience = self.AUDIENCES[self._strat_audience.currentIndex()]
        tissue = self._strat_tissue.currentText()

        market_name = market_size = market_cagr = ""
        if _BI_OK:
            segs = search_segments(tissue)
            if segs:
                market_name = segs[0].name
                market_size = segs[0].market_size_2024
                market_cagr = segs[0].cagr

        swot_text = self._swot.to_context_string() if self._swot else ""

        comp_lines = []
        for r in range(self._comp_table.rowCount()):
            comp_lines.append(
                f"  - {self._comp_table.item(r,0).text()}: "
                f"{self._comp_table.item(r,1).text()} ({self._comp_table.item(r,2).text()})"
            )

        sh_names = ", ".join(
            s.name for s in list(ALL_STAKEHOLDERS.values())
            if s.influence == "high"
        )[:200] if _BI_OK else ""

        ctx = SynthesisContext(
            project_name=self._strat_project.text().strip() or "Unnamed Project",
            tissue=tissue,
            scenario=self._swot.scenario if self._swot else "A",
            audience=audience,
            market_segment=market_name,
            market_size=market_size,
            market_cagr=market_cagr,
            swot_text=swot_text,
            competitive_context="\n".join(comp_lines),
            key_stakeholders=sh_names,
            user_notes=self._strat_notes.toPlainText(),
        )

        self._strat_btn.setEnabled(False)
        self._strat_btn.setText("  Analysing...")
        self._strat_insight.setPlainText("Waiting for Claude...")

        self._worker = StrategicInsightWorker(ctx)
        self._worker.finished.connect(self._on_strategy_done)
        self._worker.error.connect(self._on_strategy_error)
        self._worker.start()

    def _on_strategy_done(self, result):
        self._strat_btn.setEnabled(True)
        self._strat_btn.setText("  Generate Strategic Insight")
        html = [f"<b>Strategic Insight — {result.audience.title()} lens</b><br><br>",
                f"<p>{result.insight}</p>"]
        if result.key_actions:
            html.append("<b>Key Actions:</b><ol>")
            for a in result.key_actions:
                html.append(f"<li>{a}</li>")
            html.append("</ol>")
        if result.watch_list:
            html.append("<b>Watch List:</b><ul>")
            for r in result.watch_list:
                html.append(f"<li style='color:#856404'>{r}</li>")
            html.append("</ul>")
        self._strat_insight.setHtml("".join(html))

    def _on_strategy_error(self, msg: str):
        self._strat_btn.setEnabled(True)
        self._strat_btn.setText("  Generate Strategic Insight")
        self._strat_insight.setPlainText(f"Error: {msg}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _primary_btn_style() -> str:
        return """
            QPushButton {
                background-color: #2E86AB; color: white;
                border: none; border-radius: 4px; padding: 6px 14px; font-weight: bold;
            }
            QPushButton:hover { background-color: #1d6e8f; }
            QPushButton:disabled { background-color: #adb5bd; }
        """


# ── Helper dialogs ─────────────────────────────────────────────────────────────

class _CompetitorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Competitor"); self.setMinimumWidth(460)
        layout = QFormLayout(self)
        self._company    = QLineEdit(); layout.addRow("Company:", self._company)
        self._product    = QLineEdit(); layout.addRow("Product:", self._product)
        self._stage      = QComboBox()
        self._stage.addItems(["market", "clinical", "preclinical", "research"])
        layout.addRow("Stage:", self._stage)
        self._strengths  = QLineEdit(); self._strengths.setPlaceholderText("semicolon-separated")
        layout.addRow("Strengths:", self._strengths)
        self._weaknesses = QLineEdit(); self._weaknesses.setPlaceholderText("semicolon-separated")
        layout.addRow("Weaknesses:", self._weaknesses)
        self._notes      = QLineEdit(); layout.addRow("Notes:", self._notes)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def get_data(self) -> dict:
        return {"company": self._company.text(), "product": self._product.text(),
                "stage": self._stage.currentText(), "strengths": self._strengths.text(),
                "weaknesses": self._weaknesses.text(), "notes": self._notes.text()}


class _SWOTItemDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add SWOT Item"); self.setMinimumWidth(460)
        layout = QFormLayout(self)
        self._quad = QComboBox()
        self._quad.addItems(["Strength", "Weakness", "Opportunity", "Threat"])
        layout.addRow("Quadrant:", self._quad)
        self._text     = QLineEdit(); layout.addRow("Text:", self._text)
        self._evidence = QLineEdit()
        self._evidence.setPlaceholderText("Citation, data source, or expert judgement")
        layout.addRow("Evidence:", self._evidence)
        self._lens = QComboBox()
        self._lens.addItems(["general", "investor", "clinical", "regulatory", "payer"])
        layout.addRow("Stakeholder lens:", self._lens)
        self._priority = QComboBox(); self._priority.addItems(["high", "medium", "low"])
        layout.addRow("Priority:", self._priority)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def get_data(self) -> dict:
        return {"quadrant": self._quad.currentText(), "text": self._text.text(),
                "evidence": self._evidence.text(), "lens": self._lens.currentText(),
                "priority": self._priority.currentText()}


class _PatentDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Patent"); self.setMinimumWidth(460)
        layout = QFormLayout(self)
        self._number   = QLineEdit(); layout.addRow("Patent/App No.:", self._number)
        self._title    = QLineEdit(); layout.addRow("Title:", self._title)
        self._assignee = QLineEdit(); layout.addRow("Assignee:", self._assignee)
        self._date     = QLineEdit(); self._date.setPlaceholderText("YYYY-MM-DD")
        layout.addRow("Priority date:", self._date)
        self._status = QComboBox()
        self._status.addItems(["granted", "pending", "published", "expired", "abandoned"])
        layout.addRow("Status:", self._status)
        self._relevance = QComboBox()
        self._relevance.addItems(["high", "medium", "low", "blocking", "freedom-to-operate"])
        layout.addRow("Relevance:", self._relevance)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def get_data(self) -> dict:
        return {"number": self._number.text(), "title": self._title.text(),
                "assignee": self._assignee.text(), "date": self._date.text(),
                "status": self._status.currentText(), "relevance": self._relevance.currentText()}
