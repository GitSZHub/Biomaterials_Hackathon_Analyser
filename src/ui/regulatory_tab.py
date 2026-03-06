"""
Regulatory Tab -- device classification, ISO 10993 test matrix,
biocompatibility score, regulatory pathway timeline, and AI narrative.

Sub-tabs:
  1. Device Classifier  -- scenario A/B/C/D, FDA class, ATMP flag
  2. ISO 10993          -- required test matrix (from tox_engine)
  3. Biocompat Score    -- traffic-light composite score
  4. Pathway Timeline   -- milestone list with duration + cost estimates
  5. AI Narrative       -- Claude synthesises the full regulatory picture

Architecture:
  - All heavy work (ISO 10993 assessment) runs in QThread workers.
  - tox_engine clients (CompTox, ADMET, AOP) are optional --
    ISO10993Assessor degrades gracefully if MCP servers not running.
  - DeviceClassifier + PathwayMapper are pure-Python, run in the UI thread.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QPushButton, QScrollArea, QSizePolicy, QSplitter,
    QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit,
    QVBoxLayout, QWidget,
)
import qtawesome as qta

logger = logging.getLogger(__name__)

# Traffic light colours
_GREEN = "#27ae60"
_AMBER = "#f39c12"
_RED   = "#e74c3c"


# ── Workers ────────────────────────────────────────────────────────────────────

class ISO10993Worker(QThread):
    """Run ISO 10993 assessment in background (uses tox_engine)."""
    finished = pyqtSignal(object)   # ISO10993Assessment
    error    = pyqtSignal(str)

    def __init__(self, material: str, contact_type: str,
                 duration: str, components: List[str],
                 live_clients: Optional[Dict] = None):
        super().__init__()
        self.material     = material
        self.contact_type = contact_type
        self.duration     = duration
        self.components   = components
        self.live_clients = live_clients or {}

    def run(self):
        try:
            from tox_engine.iso10993_assessor import ISO10993Assessor
            assessor = ISO10993Assessor(
                comptox=self.live_clients.get("comptox"),
                aop=self.live_clients.get("aop"),
                admet=self.live_clients.get("admet"),
            )
            result = assessor.assess(
                self.material, self.contact_type,
                self.duration, self.components,
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class BiocompatWorker(QThread):
    """Run biocompatibility scoring in background."""
    finished = pyqtSignal(object)   # BiocCompatScore
    error    = pyqtSignal(str)

    def __init__(self, material: str, components: List[str],
                 live_clients: Optional[Dict] = None):
        super().__init__()
        self.material     = material
        self.components   = components
        self.live_clients = live_clients or {}

    def run(self):
        try:
            from tox_engine.biocompat_scorer import BiocCompatScorer
            scorer = BiocCompatScorer(
                comptox=self.live_clients.get("comptox"),
                admet=self.live_clients.get("admet"),
                aop=self.live_clients.get("aop"),
            )
            score = scorer.score_material(self.material, self.components)
            self.finished.emit(score)
        except Exception as e:
            self.error.emit(str(e))


class AIRegulatoryWorker(QThread):
    """Ask Claude to write a regulatory narrative."""
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, classification, pathway, iso_assessment=None,
                 biocompat_score=None):
        super().__init__()
        self.classification   = classification
        self.pathway          = pathway
        self.iso_assessment   = iso_assessment
        self.biocompat_score  = biocompat_score

    def run(self):
        try:
            from ai_engine.llm_client import get_client
            dc = self.classification
            pw = self.pathway

            iso_summary = ""
            if self.iso_assessment and self.iso_assessment.success:
                ia = self.iso_assessment
                iso_summary = (
                    f"\nISO 10993 required tests ({len(ia.required_tests)}): "
                    + ", ".join(t.test_id for t in ia.required_tests[:6])
                    + (f"... overall risk: {ia.overall_risk_tier}" if ia.overall_risk_tier else "")
                )

            bc_summary = ""
            if self.biocompat_score and self.biocompat_score.success:
                bc = self.biocompat_score
                bc_summary = (
                    f"\nBiocompatibility score: {bc.overall_score}/100 "
                    f"(tier {bc.confidence_tier}, risk: {bc.risk_tier})"
                )

            milestone_text = ""
            if pw.milestones:
                milestone_text = "\nKey milestones:\n" + "\n".join(
                    f"  - {m.phase}: {m.duration_months} months, ~{m.cost_estimate}"
                    for m in pw.milestones[:5]
                )

            prompt = (
                f"You are a regulatory affairs expert specialising in biomaterials and medical devices.\n\n"
                f"Device/material regulatory summary:\n"
                f"  Scenario: {dc.scenario} — {dc.scenario_label}\n"
                f"  FDA class: {dc.fda_class}\n"
                f"  EU class: {dc.eu_class}\n"
                f"  ATMP: {'Yes' if dc.atmp_flag else 'No'}\n"
                f"  Combination product: {'Yes' if dc.combination_product else 'No'}\n"
                f"  Pathway: {pw.pathway_name}\n"
                f"  Lead agencies: {pw.lead_fda_center} (FDA) / {pw.lead_eu_body} (EU)\n"
                f"  Total timeline estimate: {pw.total_duration_estimate}\n"
                f"  Cost estimate: {pw.total_cost_estimate}\n"
                f"{iso_summary}{bc_summary}{milestone_text}\n\n"
                f"Write a concise (4-5 paragraph) regulatory strategy narrative for a "
                f"hackathon briefing document covering:\n"
                f"1. The regulatory pathway and why this classification applies.\n"
                f"2. Key milestones and realistic timeline for market entry.\n"
                f"3. Major technical and regulatory risks and how to mitigate them.\n"
                f"4. Recommended immediate next steps (pre-submission, testing priorities).\n"
                f"5. One sentence investor-ready summary of the regulatory position."
            )
            client = get_client()
            text   = client.complete(prompt=prompt, max_tokens=800)
            self.finished.emit(text)
        except Exception as e:
            self.error.emit(str(e))


# ── Main Tab ───────────────────────────────────────────────────────────────────

class RegulatoryTab(QWidget):
    """Regulatory Engine: device classification, ISO 10993, pathway timeline, AI narrative."""

    def __init__(self):
        super().__init__()
        self._classification   = None
        self._pathway          = None
        self._iso_assessment   = None
        self._biocompat_score  = None
        self._iso_worker: Optional[ISO10993Worker]        = None
        self._biocompat_worker: Optional[BiocompatWorker] = None
        self._ai_worker: Optional[AIRegulatoryWorker]     = None
        self._tox_tab = None   # set by main_window after construction
        self._exp_tab = None   # set by main_window after construction
        self._init_ui()

    def set_tox_tab(self, tox_tab) -> None:
        """Wire in the ToxTab so workers can use live MCP clients."""
        self._tox_tab = tox_tab

    def set_experimental_tab(self, exp_tab) -> None:
        """Wire in ExperimentalTab so classification auto-prefills the wizard."""
        self._exp_tab = exp_tab

    def _get_live_clients(self) -> Dict:
        if self._tox_tab is not None:
            try:
                return self._tox_tab.get_live_clients()
            except Exception:
                pass
        return {}

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        header = QLabel("Regulatory Engine")
        header.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        layout.addWidget(header)
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_classifier_tab(), qta.icon("fa5s.sitemap"),    "Device Classifier")
        self._tabs.addTab(self._build_iso_tab(),        qta.icon("fa5s.list-ol"),    "ISO 10993")
        self._tabs.addTab(self._build_score_tab(),      qta.icon("fa5s.tachometer-alt"), "Biocompat Score")
        self._tabs.addTab(self._build_pathway_tab(),    qta.icon("fa5s.road"),       "Pathway Timeline")
        self._tabs.addTab(self._build_ai_tab(),         qta.icon("fa5s.magic"),      "AI Narrative")
        layout.addWidget(self._tabs)

    # ── Classifier tab ─────────────────────────────────────────────────────────

    def _build_classifier_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        # Inputs
        input_frame = QFrame()
        input_frame.setFrameShape(QFrame.Shape.StyledPanel)
        grid = QGridLayout(input_frame)

        grid.addWidget(QLabel("<b>Material / device name:</b>"), 0, 0)
        self._material_input = QLineEdit()
        self._material_input.setPlaceholderText("e.g. GelMA hydrogel scaffold, PLGA microspheres")
        grid.addWidget(self._material_input, 0, 1, 1, 3)

        grid.addWidget(QLabel("<b>Contact type:</b>"), 1, 0)
        self._contact_combo = QComboBox()
        self._contact_combo.addItems(["implant", "external_communicating", "surface"])
        grid.addWidget(self._contact_combo, 1, 1)

        grid.addWidget(QLabel("<b>Contact duration:</b>"), 1, 2)
        self._duration_combo = QComboBox()
        self._duration_combo.addItems(["permanent", "prolonged", "limited"])
        grid.addWidget(self._duration_combo, 1, 3)

        grid.addWidget(QLabel("<b>Drug-loaded?</b>"), 2, 0)
        self._has_drug = QCheckBox()
        grid.addWidget(self._has_drug, 2, 1)

        grid.addWidget(QLabel("<b>Contains living cells?</b>"), 2, 2)
        self._has_cells = QCheckBox()
        grid.addWidget(self._has_cells, 2, 3)

        grid.addWidget(QLabel("<b>Cells genetically modified?</b>"), 3, 0)
        self._cells_engineered = QCheckBox()
        grid.addWidget(self._cells_engineered, 3, 1)

        grid.addWidget(QLabel("<b>GMO produces material?</b>"), 3, 2)
        self._is_gmo = QCheckBox()
        grid.addWidget(self._is_gmo, 3, 3)

        grid.addWidget(QLabel("<b>Target tissue:</b>"), 4, 0)
        self._tissue_combo = QComboBox()
        self._tissue_combo.addItems(
            ["bone", "cartilage", "skin", "cardiovascular", "neural",
             "liver", "kidney", "lung", "intestine", "eye", "other"]
        )
        grid.addWidget(self._tissue_combo, 4, 1)

        classify_btn = QPushButton("Classify Device")
        classify_btn.setIcon(qta.icon("fa5s.sitemap"))
        classify_btn.setStyleSheet("QPushButton { font-weight: bold; }")
        classify_btn.clicked.connect(self._run_classify)
        grid.addWidget(classify_btn, 5, 0, 1, 4)
        layout.addWidget(input_frame)

        # Result panel
        result_frame = QFrame()
        result_frame.setFrameShape(QFrame.Shape.StyledPanel)
        result_layout = QVBoxLayout(result_frame)

        self._scenario_label = QLabel("--")
        self._scenario_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self._scenario_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        result_layout.addWidget(self._scenario_label)

        classes_row = QHBoxLayout()
        self._fda_label = self._class_badge("FDA", "--")
        self._eu_label  = self._class_badge("EU MDR", "--")
        self._atmp_label = self._class_badge("ATMP", "No")
        classes_row.addWidget(self._fda_label)
        classes_row.addWidget(self._eu_label)
        classes_row.addWidget(self._atmp_label)
        result_layout.addLayout(classes_row)

        self._reasoning_text = QTextEdit()
        self._reasoning_text.setReadOnly(True)
        self._reasoning_text.setMaximumHeight(130)
        self._reasoning_text.setPlaceholderText("Classification reasoning will appear here.")
        result_layout.addWidget(self._reasoning_text)

        next_btn_row = QHBoxLayout()
        run_all_btn = QPushButton("Run ISO 10993 + Pathway")
        run_all_btn.setIcon(qta.icon("fa5s.play"))
        run_all_btn.clicked.connect(self._run_all)
        next_btn_row.addWidget(run_all_btn)
        next_btn_row.addStretch()
        result_layout.addLayout(next_btn_row)
        layout.addWidget(result_frame)

        return w

    def _class_badge(self, label: str, value: str) -> QLabel:
        lbl = QLabel(f"<b>{label}</b><br>{value}")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            "QLabel { background: #2c3e50; color: white; border-radius: 6px; "
            "padding: 8px 16px; font-size: 13px; }"
        )
        lbl.setMinimumWidth(130)
        return lbl

    # ── ISO 10993 tab ──────────────────────────────────────────────────────────

    def _build_iso_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        comp_row = QHBoxLayout()
        comp_row.addWidget(QLabel("Components (comma-separated):"))
        self._components_input = QLineEdit()
        self._components_input.setPlaceholderText(
            "e.g. gelatin methacryloyl, lithium phenyl phosphinate, PBS"
        )
        comp_row.addWidget(self._components_input)
        run_iso_btn = QPushButton("Run Assessment")
        run_iso_btn.setIcon(qta.icon("fa5s.list-ol"))
        run_iso_btn.clicked.connect(self._run_iso)
        comp_row.addWidget(run_iso_btn)
        layout.addLayout(comp_row)

        self._iso_status = QLabel("Classify device first, then run ISO 10993 assessment.")
        layout.addWidget(self._iso_status)

        self._iso_table = QTableWidget(0, 4)
        self._iso_table.setHorizontalHeaderLabels(["Test", "Standard", "Risk Level", "Waivable?"])
        self._iso_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._iso_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._iso_table.setAlternatingRowColors(True)
        layout.addWidget(self._iso_table)

        self._iso_flags_text = QTextEdit()
        self._iso_flags_text.setReadOnly(True)
        self._iso_flags_text.setMaximumHeight(100)
        self._iso_flags_text.setPlaceholderText("Chemical hazard flags and AOP concerns will appear here.")
        layout.addWidget(self._iso_flags_text)

        return w

    # ── Biocompat Score tab ────────────────────────────────────────────────────

    def _build_score_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        run_btn_row = QHBoxLayout()
        self._score_btn = QPushButton("Calculate Biocompatibility Score")
        self._score_btn.setIcon(qta.icon("fa5s.tachometer-alt"))
        self._score_btn.clicked.connect(self._run_biocompat)
        run_btn_row.addWidget(self._score_btn)
        run_btn_row.addStretch()
        layout.addLayout(run_btn_row)

        self._score_status = QLabel(
            "Uses ISO 10993 component list. Run ISO 10993 assessment first."
        )
        layout.addWidget(self._score_status)

        # Traffic light + score display
        traffic_frame = QFrame()
        traffic_frame.setFrameShape(QFrame.Shape.StyledPanel)
        traffic_layout = QHBoxLayout(traffic_frame)

        self._traffic_light = QLabel("--")
        self._traffic_light.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._traffic_light.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        self._traffic_light.setMinimumWidth(120)
        self._traffic_light.setMinimumHeight(80)
        self._traffic_light.setStyleSheet(
            "QLabel { background: #95a5a6; color: white; border-radius: 8px; }"
        )
        traffic_layout.addWidget(self._traffic_light)

        score_details = QVBoxLayout()
        self._score_overall_label  = QLabel("Overall: --/100")
        self._score_overall_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self._score_chem_label     = QLabel("Chemical Hazard: --")
        self._score_admet_label    = QLabel("ADMET: --")
        self._score_aop_label      = QLabel("AOP Pathways: --")
        self._score_tier_label     = QLabel("Confidence Tier: --")
        for lbl in (self._score_overall_label, self._score_chem_label,
                    self._score_admet_label, self._score_aop_label,
                    self._score_tier_label):
            score_details.addWidget(lbl)
        traffic_layout.addLayout(score_details)
        layout.addWidget(traffic_frame)

        self._score_flags_text = QTextEdit()
        self._score_flags_text.setReadOnly(True)
        self._score_flags_text.setPlaceholderText("Risk flags and strengths will appear here.")
        layout.addWidget(self._score_flags_text)

        return w

    # ── Pathway Timeline tab ───────────────────────────────────────────────────

    def _build_pathway_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        self._pathway_header = QLabel(
            "Classify device first. The regulatory pathway timeline will appear here."
        )
        self._pathway_header.setWordWrap(True)
        self._pathway_header.setFont(QFont("Arial", 11))
        layout.addWidget(self._pathway_header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._milestone_widget = QWidget()
        self._milestone_layout = QVBoxLayout(self._milestone_widget)
        self._milestone_layout.setSpacing(4)
        self._milestone_layout.addStretch()
        scroll.setWidget(self._milestone_widget)
        layout.addWidget(scroll)

        risks_label = QLabel("<b>Key risks:</b>")
        layout.addWidget(risks_label)
        self._risks_text = QTextEdit()
        self._risks_text.setReadOnly(True)
        self._risks_text.setMaximumHeight(90)
        layout.addWidget(self._risks_text)

        return w

    # ── AI Narrative tab ───────────────────────────────────────────────────────

    def _build_ai_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        btn_row = QHBoxLayout()
        self._ai_btn = QPushButton("Generate Regulatory Narrative")
        self._ai_btn.setIcon(qta.icon("fa5s.magic"))
        self._ai_btn.clicked.connect(self._run_ai)
        btn_row.addWidget(self._ai_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._ai_output = QTextEdit()
        self._ai_output.setReadOnly(True)
        self._ai_output.setPlaceholderText(
            "AI regulatory narrative will appear here.\n\n"
            "Requires: device classification + ANTHROPIC_API_KEY in config/.env\n\n"
            "Covers:\n"
            "  - Applicable regulatory pathway and rationale\n"
            "  - Realistic timeline and cost estimates\n"
            "  - Key risks and mitigation strategies\n"
            "  - Immediate next steps\n"
            "  - Investor-ready one-liner on regulatory position"
        )
        layout.addWidget(self._ai_output)
        return w

    # ── Slots: Classifier ──────────────────────────────────────────────────────

    def _run_classify(self):
        contact_type = self._contact_combo.currentText()
        duration     = self._duration_combo.currentText()
        try:
            from regulatory_engine.device_classifier import DeviceClassifier
            clf = DeviceClassifier()
            self._classification = clf.classify(
                contact_type=contact_type,
                contact_duration=duration,
                has_drug=self._has_drug.isChecked(),
                has_living_cells=self._has_cells.isChecked(),
                cells_engineered=self._cells_engineered.isChecked(),
                is_engineered_organism=self._is_gmo.isChecked(),
                target_tissue=self._tissue_combo.currentText(),
            )
            dc = self._classification
            self._scenario_label.setText(f"Scenario {dc.scenario} — {dc.scenario_label}")
            self._fda_label.setText(f"<b>FDA</b><br>{dc.fda_class}")
            self._eu_label.setText(f"<b>EU MDR</b><br>{dc.eu_class}")
            atmp_text = "YES" if dc.atmp_flag else "No"
            self._atmp_label.setText(f"<b>ATMP</b><br>{atmp_text}")
            atmp_bg = "#8e44ad" if dc.atmp_flag else "#2c3e50"
            self._atmp_label.setStyleSheet(
                f"QLabel {{ background: {atmp_bg}; color: white; border-radius: 6px; "
                "padding: 8px 16px; font-size: 13px; }"
            )
            color = _RED if dc.is_high_risk else (_AMBER if dc.fda_class == "Class II" else _GREEN)
            self._scenario_label.setStyleSheet(f"color: {color};")
            self._reasoning_text.setPlainText(
                dc.reasoning + "\n\n" + dc.risk_class_rationale + "\n\n"
                + "Regulation refs: " + "; ".join(dc.regulation_refs)
            )

            # Auto-build pathway
            from regulatory_engine.pathway_mapper import PathwayMapper
            self._pathway = PathwayMapper().map(dc)
            self._populate_pathway(self._pathway)

            # Prefill experimental design wizard
            if self._exp_tab is not None:
                self._exp_tab.prefill(
                    tissue=self._tissue_combo.currentText(),
                    scenario=dc.scenario,
                )
        except Exception as e:
            QMessageBox.warning(self, "Classification error", str(e))

    def _run_all(self):
        if self._classification is None:
            QMessageBox.information(self, "Not classified",
                                    "Run device classification first.")
            return
        self._run_iso()
        self._tabs.setCurrentIndex(1)

    # ── Slots: ISO 10993 ───────────────────────────────────────────────────────

    def _run_iso(self):
        material = self._material_input.text().strip()
        if not material:
            material = "Unnamed material"
        components_str = self._components_input.text().strip()
        components = [c.strip() for c in components_str.split(",") if c.strip()] if components_str else []
        contact = self._contact_combo.currentText()
        duration = self._duration_combo.currentText()

        self._iso_status.setText("Running ISO 10993 assessment ...")
        self._iso_worker = ISO10993Worker(
            material, contact, duration, components,
            live_clients=self._get_live_clients(),
        )
        self._iso_worker.finished.connect(self._on_iso_finished)
        self._iso_worker.error.connect(lambda e: self._iso_status.setText(f"Error: {e}"))
        self._iso_worker.start()

    def _on_iso_finished(self, assessment):
        self._iso_assessment = assessment
        if not assessment.success:
            self._iso_status.setText(f"Assessment failed: {assessment.error}")
            return

        n = len(assessment.required_tests)
        self._iso_status.setText(
            f"{n} required test(s) for {assessment.contact_type} / "
            f"{assessment.contact_duration}  |  Overall risk: {assessment.overall_risk_tier}"
        )
        self._iso_table.setRowCount(0)
        for item in assessment.required_tests:
            row = self._iso_table.rowCount()
            self._iso_table.insertRow(row)
            self._iso_table.setItem(row, 0, QTableWidgetItem(item.test_id.replace("_", " ").title()))
            self._iso_table.setItem(row, 1, QTableWidgetItem(item.description))
            risk_item = QTableWidgetItem(item.risk_level)
            if item.risk_level == "high":
                risk_item.setForeground(QColor(_RED))
                risk_item.setFont(QFont("Arial", -1, QFont.Weight.Bold))
            self._iso_table.setItem(row, 2, risk_item)
            self._iso_table.setItem(row, 3, QTableWidgetItem("Yes" if item.waiver_possible else ""))

        flags_text = ""
        if assessment.chemical_risk_flags:
            flags_text += "Chemical hazard flags:\n" + "\n".join(f"  - {f}" for f in assessment.chemical_risk_flags) + "\n\n"
        if assessment.aop_concerns:
            flags_text += "AOP concerns:\n" + "\n".join(f"  - {c}" for c in assessment.aop_concerns)
        self._iso_flags_text.setPlainText(flags_text or "No specific chemical/AOP flags (MCP servers not active).")

    # ── Slots: Biocompat Score ─────────────────────────────────────────────────

    def _run_biocompat(self):
        material     = self._material_input.text().strip() or "Unnamed material"
        components_str = self._components_input.text().strip()
        components   = [c.strip() for c in components_str.split(",") if c.strip()] if components_str else []
        if not components:
            components = [material]

        self._score_status.setText("Calculating biocompatibility score ...")
        self._biocompat_worker = BiocompatWorker(
            material, components,
            live_clients=self._get_live_clients(),
        )
        self._biocompat_worker.finished.connect(self._on_biocompat_finished)
        self._biocompat_worker.error.connect(
            lambda e: self._score_status.setText(f"Error: {e}")
        )
        self._biocompat_worker.start()
        self._tabs.setCurrentIndex(2)

    def _on_biocompat_finished(self, score):
        self._biocompat_score = score
        if not score.success:
            self._score_status.setText(f"Score failed: {score.error}")
            return

        self._score_status.setText(score.score_rationale)
        self._score_overall_label.setText(f"Overall: {score.overall_score}/100")
        self._score_chem_label.setText(f"Chemical Hazard: {score.chemical_hazard_score}/100")
        self._score_admet_label.setText(f"ADMET: {score.admet_score}/100")
        self._score_aop_label.setText(f"AOP Pathways: {score.aop_score}/100")
        self._score_tier_label.setText(f"Confidence Tier: {score.confidence_tier}")

        tl = score.traffic_light
        color = {"green": _GREEN, "amber": _AMBER, "red": _RED}.get(tl, "#95a5a6")
        self._traffic_light.setText(tl.upper())
        self._traffic_light.setStyleSheet(
            f"QLabel {{ background: {color}; color: white; border-radius: 8px; }}"
        )

        flags_lines = ["FLAGS:"] + [f"  - {f}" for f in score.flags] if score.flags else []
        strength_lines = ["STRENGTHS:"] + [f"  + {s}" for s in score.strengths] if score.strengths else []
        self._score_flags_text.setPlainText(
            "\n".join(flags_lines + ([""] if flags_lines and strength_lines else []) + strength_lines)
            or "No flags detected (MCP servers not active — score based on defaults)."
        )

    # ── Pathway population ─────────────────────────────────────────────────────

    def _populate_pathway(self, pathway):
        self._pathway_header.setText(
            f"<b>{pathway.pathway_name}</b>  |  "
            f"Total: {pathway.total_duration_estimate}  |  "
            f"Est. cost: {pathway.total_cost_estimate}"
        )
        # Clear old milestone widgets
        while self._milestone_layout.count() > 1:
            item = self._milestone_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        for i, m in enumerate(pathway.milestones):
            card = self._make_milestone_card(i + 1, m)
            self._milestone_layout.insertWidget(self._milestone_layout.count() - 1, card)

        self._risks_text.setPlainText("\n".join(f"- {r}" for r in pathway.key_risks))
        if pathway.notes:
            self._risks_text.append(f"\nNote: {pathway.notes}")

    def _make_milestone_card(self, n: int, m) -> QFrame:
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setStyleSheet("QFrame { background: #f8f9fa; border-radius: 4px; }")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(8, 6, 8, 6)

        num = QLabel(f"<b>{n}</b>")
        num.setFixedWidth(22)
        num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(num)

        text = QVBoxLayout()
        phase_lbl = QLabel(f"<b>{m.phase}</b>")
        desc_lbl  = QLabel(m.description)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #555; font-size: 11px;")
        text.addWidget(phase_lbl)
        text.addWidget(desc_lbl)
        layout.addLayout(text)

        meta = QVBoxLayout()
        dur_lbl  = QLabel(f"{m.duration_months} mo")
        dur_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        cost_lbl = QLabel(m.cost_estimate)
        cost_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        cost_lbl.setStyleSheet("color: #2980b9; font-size: 11px;")
        meta.addWidget(dur_lbl)
        meta.addWidget(cost_lbl)
        layout.addLayout(meta)

        return card

    # ── Slots: AI Narrative ────────────────────────────────────────────────────

    def _run_ai(self):
        if self._classification is None:
            QMessageBox.information(self, "Not classified",
                                    "Run device classification first.")
            return
        if self._pathway is None:
            QMessageBox.information(self, "No pathway",
                                    "Run device classification to generate a pathway.")
            return
        self._ai_output.setText("Generating regulatory narrative ...")
        self._ai_btn.setEnabled(False)
        self._ai_worker = AIRegulatoryWorker(
            self._classification, self._pathway,
            self._iso_assessment, self._biocompat_score,
        )
        self._ai_worker.finished.connect(self._on_ai_finished)
        self._ai_worker.error.connect(self._on_ai_error)
        self._ai_worker.start()

    def _on_ai_finished(self, text: str):
        self._ai_output.setText(text)
        self._ai_btn.setEnabled(True)

    def _on_ai_error(self, msg: str):
        self._ai_output.setText(
            f"AI unavailable: {msg}\n\nCheck ANTHROPIC_API_KEY in config/.env"
        )
        self._ai_btn.setEnabled(True)
