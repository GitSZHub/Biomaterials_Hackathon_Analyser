"""
Bio Analysis Tab -- GEO dataset search, series matrix download,
DEG analysis, volcano plot, and AI interpretation.

Sub-tabs:
  1. GEO Search      -- query NCBI GEO, browse results, download
  2. Expression Data -- load matrix, define sample groups
  3. Volcano Plot    -- DEG analysis + matplotlib embedded volcano
  4. AI Insight      -- Claude interprets the top DEGs in biomaterial context

Architecture notes:
  - All network ops run in QThread workers; UI never blocks.
  - Matrigel caveat banner is always visible at the top.
  - Volcano plot uses matplotlib (embedded via FigureCanvas).
  - "Open in Browser" exports a Plotly HTML for interactive exploration.
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QProgressBar, QPushButton, QSplitter, QTabWidget,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)
import qtawesome as qta
from .findings_widget import FindingsWidget

logger = logging.getLogger(__name__)


def _make_checkbox(text: str, checked: bool = False) -> QCheckBox:
    cb = QCheckBox(text)
    cb.setChecked(checked)
    return cb


# ── matplotlib Qt embedding ────────────────────────────────────────────────────
try:
    import matplotlib
    matplotlib.use("QtAgg")
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    _MPL_OK = True
except ImportError:
    _MPL_OK = False
    logger.warning("matplotlib not available; volcano plot disabled")


# ── Background workers ─────────────────────────────────────────────────────────

class GeoSearchWorker(QThread):
    """Search NCBI GEO in background."""
    results_ready = pyqtSignal(list)
    error         = pyqtSignal(str)

    def __init__(self, query: str, organism: str = "", max_results: int = 30):
        super().__init__()
        self.query       = query
        self.organism    = organism
        self.max_results = max_results

    def run(self):
        try:
            from bio_engine.geo_client import GEOClient
            client  = GEOClient()
            results = client.search(self.query, organism=self.organism,
                                    max_results=self.max_results)
            client.cache_metadata(results)
            self.results_ready.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class DownloadWorker(QThread):
    """Download a GEO series matrix in background."""
    progress  = pyqtSignal(int, int)   # bytes_done, bytes_total
    finished  = pyqtSignal(str)        # local file path
    error     = pyqtSignal(str)

    def __init__(self, gse_id: str):
        super().__init__()
        self.gse_id = gse_id

    def run(self):
        try:
            from bio_engine.geo_client import GEOClient
            client = GEOClient()
            path   = client.download_series(
                self.gse_id,
                progress_callback=lambda done, total: self.progress.emit(done, total),
            )
            if path:
                self.finished.emit(path)
            else:
                self.error.emit(f"Download failed for {self.gse_id}")
        except Exception as e:
            self.error.emit(str(e))


class DEGWorker(QThread):
    """Run DEG analysis in background."""
    finished = pyqtSignal(object)   # DEGResult
    error    = pyqtSignal(str)

    def __init__(self, matrix, group_a: List[str], group_b: List[str],
                 material: str = "", baseline: str = ""):
        super().__init__()
        self.matrix   = matrix
        self.group_a  = group_a
        self.group_b  = group_b
        self.material = material
        self.baseline = baseline

    def run(self):
        try:
            from bio_engine.transcriptomics import run_deg_analysis
            result = run_deg_analysis(
                self.matrix, self.group_a, self.group_b,
                material=self.material, baseline=self.baseline,
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class PathwayEnrichmentWorker(QThread):
    """Run pathway enrichment analysis in background."""
    finished = pyqtSignal(object)   # PathwayReport
    error    = pyqtSignal(str)

    def __init__(self, deg_result, mode: str = "split", organism: str = "hsapiens",
                 sources: Optional[List[str]] = None, run_gsea: bool = False):
        super().__init__()
        self.deg_result = deg_result
        self.mode       = mode       # "split" | "combined"
        self.organism   = organism
        self.sources    = sources or ["GO:BP", "KEGG", "REAC"]
        self.run_gsea   = run_gsea

    def run(self):
        try:
            from bio_engine.pathway_analysis import (
                run_enrichment, run_enrichment_split,
                run_preranked_gsea, genes_from_deg_result,
            )
            up, down, ranked = genes_from_deg_result(self.deg_result)

            if self.mode == "split" and (up or down):
                report = run_enrichment_split(
                    up, down, organism=self.organism, sources=self.sources,
                )
            else:
                all_genes = up + down
                report = run_enrichment(
                    all_genes, organism=self.organism, sources=self.sources,
                )

            if self.run_gsea and ranked:
                report.gsea_results = run_preranked_gsea(ranked)

            self.finished.emit(report)
        except Exception as e:
            self.error.emit(str(e))


class AIInterpretWorker(QThread):
    """Ask Claude to interpret DEG results in biomaterial context."""
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, deg_result, project_context: str = ""):
        super().__init__()
        self.deg_result      = deg_result
        self.project_context = project_context

    def run(self):
        try:
            from ai_engine.llm_client import get_client
            r     = self.deg_result
            top5  = r.top_degs[:5]
            genes = ", ".join(d["gene"] for d in top5)
            paths = ", ".join(r.flagged_pathways) or "none detected"
            caveat = (
                "\nNOTE: Matrigel was used as baseline. "
                f"Known Matrigel artefact genes detected: {', '.join(r.matrigel_genes) or 'none'}. "
                "Interpret hypoxia and ECM signals cautiously."
                if r.matrigel_caveat else ""
            )
            prompt = (
                f"You are a biomaterials scientist analysing transcriptomic data.\n"
                f"Project context: {self.project_context or 'biomaterial scaffold evaluation'}.\n"
                f"Material tested: {r.material or 'unknown'}. Baseline: {r.baseline or 'control'}.\n"
                f"DEG results: {r.up_count} upregulated genes, {r.down_count} downregulated genes.\n"
                f"Top significant genes: {genes}.\n"
                f"Flagged biomaterial-relevant pathways: {paths}.{caveat}\n\n"
                f"Provide a concise (3-4 paragraph) biomaterial interpretation:\n"
                f"1. What the pathway activity suggests about the material's biocompatibility.\n"
                f"2. Any red flags (inflammation, apoptosis, oxidative stress).\n"
                f"3. Recommended follow-up experiments.\n"
                f"4. Confidence in conclusions given the dataset."
            )
            client = get_client()
            text   = client.complete(prompt=prompt, max_tokens=600)
            self.finished.emit(text)
        except Exception as e:
            self.error.emit(str(e))


class DeconvolutionWorker(QThread):
    """Run cell type deconvolution in background."""
    finished = pyqtSignal(object)   # DeconvolutionResult
    error    = pyqtSignal(str)

    def __init__(self, matrix, tissue: str = "general", method: str = "markers"):
        super().__init__()
        self.matrix = matrix
        self.tissue = tissue
        self.method = method

    def run(self):
        try:
            from bio_engine.deconvolution import (
                deconvolve_markers, deconvolve_nnls, build_signature_from_markers,
            )
            if self.method == "nnls":
                sig = build_signature_from_markers(self.tissue)
                result = deconvolve_nnls(self.matrix, sig)
            else:
                result = deconvolve_markers(self.matrix, tissue=self.tissue)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class FlowGatingWorker(QThread):
    """Run flow cytometry gating + stats in background."""
    finished = pyqtSignal(object, object)   # GatingResult, PopulationStats
    error    = pyqtSignal(str)

    def __init__(self, flow_data, channel: str, threshold: float,
                 keep: str = "above", gate_name: str = ""):
        super().__init__()
        self.flow_data = flow_data
        self.channel   = channel
        self.threshold = threshold
        self.keep      = keep
        self.gate_name = gate_name

    def run(self):
        try:
            from bio_engine.flow_data_processor import gate_threshold, compute_population_stats
            gated = gate_threshold(
                self.flow_data, self.channel, self.threshold,
                keep=self.keep, gate_name=self.gate_name,
            )
            stats = compute_population_stats(gated.data)
            self.finished.emit(gated, stats)
        except Exception as e:
            self.error.emit(str(e))


class MetabSearchWorker(QThread):
    """Search MetaboLights/Workbench in background."""
    results_ready = pyqtSignal(list)
    error         = pyqtSignal(str)

    def __init__(self, query: str, source: str = "both", organism: str = ""):
        super().__init__()
        self.query    = query
        self.source   = source
        self.organism = organism

    def run(self):
        try:
            from bio_engine.metabolomics_client import MetabolomicsClient
            client  = MetabolomicsClient()
            results = client.search(self.query, source=self.source, organism=self.organism)
            client.cache_metadata(results)
            self.results_ready.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class MetabDiffWorker(QThread):
    """Run metabolomics differential analysis in background."""
    finished = pyqtSignal(object)   # DifferentialResult
    error    = pyqtSignal(str)

    def __init__(self, matrix, group_a: List[str], group_b: List[str],
                 material: str = "", baseline: str = ""):
        super().__init__()
        self.matrix   = matrix
        self.group_a  = group_a
        self.group_b  = group_b
        self.material = material
        self.baseline = baseline

    def run(self):
        try:
            from bio_engine.metabolomics import run_differential_analysis
            result = run_differential_analysis(
                self.matrix, self.group_a, self.group_b,
                material=self.material, baseline=self.baseline,
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


# ── Main Tab ───────────────────────────────────────────────────────────────────

class BioAnalysisTab(QWidget):
    """Biological Analysis: GEO search, DEG, volcano plot, metabolomics, AI interpretation."""

    def __init__(self):
        super().__init__()
        self._current_matrix   = None
        self._current_result   = None
        self._current_pathway_report = None
        self._loaded_file_path: Optional[str] = None
        self._geo_results: list = []          # cache of last search results
        self._search_worker: Optional[GeoSearchWorker]   = None
        self._download_worker: Optional[DownloadWorker]  = None
        self._deg_worker: Optional[DEGWorker]            = None
        self._pathway_worker: Optional[PathwayEnrichmentWorker] = None
        self._ai_worker: Optional[AIInterpretWorker]     = None
        # Metabolomics state
        self._metab_matrix    = None
        self._metab_result    = None
        self._metab_results: list = []
        self._metab_search_worker: Optional[MetabSearchWorker] = None
        self._metab_diff_worker: Optional[MetabDiffWorker]     = None
        # Deconvolution state
        self._deconv_result = None
        self._deconv_worker: Optional[DeconvolutionWorker] = None
        # Flow cytometry state
        self._flow_data = None          # current FlowData
        self._flow_gated = None         # last GatingResult
        self._flow_stats = None         # last PopulationStats
        self._flow_worker: Optional[FlowGatingWorker] = None
        # Sequencing advisor state
        self._seq_recs = None           # last TechAdvisorReport
        # Tissue interaction state
        self._tissue_timeline = None    # last TissueResponseTimeline
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        header = QLabel("Bio Analysis")
        header.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(header)

        # ── Matrigel caveat banner (always visible) ────────────────────────
        banner = QFrame()
        banner.setStyleSheet(
            "QFrame { background: #fff3cd; border: 1px solid #ffc107; border-radius: 4px; }"
        )
        banner_layout = QHBoxLayout(banner)
        banner_layout.setContentsMargins(8, 4, 8, 4)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(qta.icon("fa5s.exclamation-triangle", color="#856404").pixmap(16, 16))
        banner_layout.addWidget(icon_lbl)
        banner_layout.addWidget(QLabel(
            "<b>Matrigel caveat:</b> many GEO datasets use Matrigel as baseline. "
            "Hypoxia, HIF-1, and ECM signals may reflect culture artefacts, "
            "not material response. Flagged genes are highlighted automatically."
        ))
        banner_layout.addStretch()
        layout.addWidget(banner)

        # ── Sub-tabs ───────────────────────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_search_tab(),     qta.icon("fa5s.search"),       "GEO Search")
        self._tabs.addTab(self._build_expression_tab(), qta.icon("fa5s.table"),         "Expression Data")
        self._tabs.addTab(self._build_volcano_tab(),    qta.icon("fa5s.circle"),        "Volcano Plot")
        self._tabs.addTab(self._build_pathway_tab(),    qta.icon("fa5s.project-diagram"), "Pathway Enrichment")
        self._tabs.addTab(self._build_metabolomics_tab(), qta.icon("fa5s.vial"),         "Metabolomics")
        self._tabs.addTab(self._build_deconv_tab(),     qta.icon("fa5s.chart-pie"),    "Deconvolution")
        self._tabs.addTab(self._build_flow_tab(),      qta.icon("fa5s.water"),        "Flow Cytometry")
        self._tabs.addTab(self._build_seq_advisor_tab(), qta.icon("fa5s.dna"),          "Sequencing Advisor")
        self._tabs.addTab(self._build_multiomics_tab(), qta.icon("fa5s.layer-group"),   "Multi-Omics")
        self._tabs.addTab(self._build_tissue_tab(),     qta.icon("fa5s.heartbeat"),     "Tissue Interaction")
        self._tabs.addTab(self._build_intervention_tab(), qta.icon("fa5s.bullseye"),    "Intervention Planner")
        self._tabs.addTab(self._build_target_tab(),     qta.icon("fa5s.pills"),         "Target Lookup")
        self._tabs.addTab(self._build_ai_tab(),         qta.icon("fa5s.magic"),         "AI Insight")
        layout.addWidget(self._tabs)

        self._findings = FindingsWidget(
            "bio_analysis",
            placeholder="Key biological findings: top DEGs, enriched pathways, "
                        "GEO datasets used, gene targets of interest, pathway strategy "
                        "(e.g. HIF-1 knockdown, Wnt activation), single-cell insights..."
        )
        layout.addWidget(self._findings)

    def set_project_id(self, project_id: int) -> None:
        self._findings.set_project_id(project_id)

    # ── GEO Search tab ─────────────────────────────────────────────────────────

    def _build_search_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        # Search controls
        ctrl_frame = QFrame()
        ctrl_frame.setFrameShape(QFrame.Shape.StyledPanel)
        ctrl_layout = QHBoxLayout(ctrl_frame)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(
            "e.g. GelMA scaffold bone regeneration  |  collagen hydrogel cartilage  |  HA osteoblast"
        )
        self._search_input.returnPressed.connect(self._run_search)
        ctrl_layout.addWidget(self._search_input, 3)

        self._organism_combo = QComboBox()
        self._organism_combo.addItems(["Any organism", "Homo sapiens", "Mus musculus",
                                       "Rattus norvegicus", "Ovis aries"])
        ctrl_layout.addWidget(self._organism_combo, 1)

        search_btn = QPushButton("Search GEO")
        search_btn.setIcon(qta.icon("fa5s.search"))
        search_btn.clicked.connect(self._run_search)
        ctrl_layout.addWidget(search_btn)
        layout.addWidget(ctrl_frame)

        # Status / progress
        self._search_status = QLabel("Enter a query to search NCBI GEO.")
        layout.addWidget(self._search_status)

        # Results table
        self._results_table = QTableWidget(0, 5)
        self._results_table.setHorizontalHeaderLabels(
            ["GSE ID", "Title", "Organism", "Samples", "Type"]
        )
        self._results_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._results_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._results_table.setAlternatingRowColors(True)
        self._results_table.itemSelectionChanged.connect(self._on_dataset_selected)
        layout.addWidget(self._results_table)

        # Dataset detail panel
        detail_frame = QFrame()
        detail_frame.setStyleSheet(
            "QFrame { background: #f8f9fa; border: 1px solid #dee2e6; "
            "border-radius: 6px; padding: 4px; }"
        )
        detail_layout = QVBoxLayout(detail_frame)
        detail_layout.setContentsMargins(8, 6, 8, 6)
        detail_layout.setSpacing(4)

        detail_top = QHBoxLayout()
        self._detail_meta = QLabel("Select a dataset to preview details.")
        self._detail_meta.setStyleSheet("color: #495057; font-size: 11px;")
        self._detail_meta.setWordWrap(True)
        detail_top.addWidget(self._detail_meta, 1)

        self._open_geo_btn = QPushButton("Open in GEO")
        self._open_geo_btn.setIcon(qta.icon("fa5s.external-link-alt"))
        self._open_geo_btn.setEnabled(False)
        self._open_geo_btn.clicked.connect(self._open_selected_in_geo)
        detail_top.addWidget(self._open_geo_btn)

        detail_layout.addLayout(detail_top)

        self._detail_summary = QTextEdit()
        self._detail_summary.setReadOnly(True)
        self._detail_summary.setMaximumHeight(80)
        self._detail_summary.setPlaceholderText("Dataset summary will appear here...")
        self._detail_summary.setStyleSheet("font-size: 11px; background: transparent; border: none;")
        detail_layout.addWidget(self._detail_summary)
        layout.addWidget(detail_frame)

        # Download controls
        dl_layout = QHBoxLayout()
        self._dl_btn = QPushButton("Download Selected Dataset")
        self._dl_btn.setIcon(qta.icon("fa5s.download"))
        self._dl_btn.clicked.connect(self._download_selected)
        dl_layout.addWidget(self._dl_btn)

        self._local_btn = QPushButton("Load Local File")
        self._local_btn.setIcon(qta.icon("fa5s.folder-open"))
        self._local_btn.clicked.connect(self._load_local_file)
        dl_layout.addWidget(self._local_btn)

        dl_layout.addStretch()
        layout.addLayout(dl_layout)

        self._dl_progress = QProgressBar()
        self._dl_progress.setVisible(False)
        layout.addWidget(self._dl_progress)

        return w

    # ── Expression Data tab ────────────────────────────────────────────────────

    def _build_expression_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        info_label = QLabel("Matrix not loaded. Search GEO and download a dataset first.")
        info_label.setWordWrap(True)
        self._matrix_info = info_label
        layout.addWidget(info_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Sample list A
        a_frame = QFrame()
        a_frame.setFrameShape(QFrame.Shape.StyledPanel)
        a_layout = QVBoxLayout(a_frame)
        a_layout.addWidget(QLabel("Control (Group A):"))
        self._group_a_list = QListWidget()
        self._group_a_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        a_layout.addWidget(self._group_a_list)
        splitter.addWidget(a_frame)

        # Sample list B
        b_frame = QFrame()
        b_frame.setFrameShape(QFrame.Shape.StyledPanel)
        b_layout = QVBoxLayout(b_frame)
        b_layout.addWidget(QLabel("Treatment (Group B):"))
        self._group_b_list = QListWidget()
        self._group_b_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        b_layout.addWidget(self._group_b_list)
        splitter.addWidget(b_frame)

        layout.addWidget(splitter)

        # Auto-split button + run DEG
        btn_layout = QHBoxLayout()
        auto_btn = QPushButton("Auto-split 50/50")
        auto_btn.setIcon(qta.icon("fa5s.random"))
        auto_btn.clicked.connect(self._auto_split_groups)
        btn_layout.addWidget(auto_btn)

        demo_btn = QPushButton("Load Demo Matrix")
        demo_btn.setIcon(qta.icon("fa5s.flask"))
        demo_btn.clicked.connect(self._load_demo_matrix)
        btn_layout.addWidget(demo_btn)

        btn_layout.addStretch()

        self._material_input = QLineEdit()
        self._material_input.setPlaceholderText("Material name (optional)")
        self._material_input.setMaximumWidth(200)
        btn_layout.addWidget(QLabel("Material:"))
        btn_layout.addWidget(self._material_input)

        self._baseline_input = QLineEdit()
        self._baseline_input.setPlaceholderText("Baseline (e.g. Matrigel)")
        self._baseline_input.setMaximumWidth(180)
        btn_layout.addWidget(QLabel("Baseline:"))
        btn_layout.addWidget(self._baseline_input)

        run_deg_btn = QPushButton("Run DEG Analysis")
        run_deg_btn.setIcon(qta.icon("fa5s.play"))
        run_deg_btn.setStyleSheet("QPushButton { font-weight: bold; }")
        run_deg_btn.clicked.connect(self._run_deg)
        btn_layout.addWidget(run_deg_btn)

        layout.addLayout(btn_layout)

        self._deg_status = QLabel("")
        layout.addWidget(self._deg_status)

        return w

    # ── Volcano Plot tab ───────────────────────────────────────────────────────

    def _build_volcano_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        # Summary bar
        self._volcano_summary = QLabel("No DEG results yet. Run analysis in Expression Data tab.")
        self._volcano_summary.setWordWrap(True)
        layout.addWidget(self._volcano_summary)

        if _MPL_OK:
            self._fig    = Figure(figsize=(8, 5), tight_layout=True)
            self._canvas = FigureCanvas(self._fig)
            layout.addWidget(self._canvas)
        else:
            layout.addWidget(QLabel("matplotlib not installed. Run: pip install matplotlib"))

        # Top DEGs table
        self._deg_table = QTableWidget(0, 4)
        self._deg_table.setHorizontalHeaderLabels(["Gene", "log2FC", "padj", "Direction"])
        self._deg_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._deg_table.setMaximumHeight(180)
        self._deg_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._deg_table.setAlternatingRowColors(True)
        layout.addWidget(self._deg_table)

        btn_layout = QHBoxLayout()
        export_btn = QPushButton("Export Figure")
        export_btn.setIcon(qta.icon("fa5s.save"))
        export_btn.clicked.connect(self._export_volcano)
        btn_layout.addWidget(export_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        return w

    # ── Pathway Enrichment tab ────────────────────────────────────────────────

    def _build_pathway_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        # Controls row
        ctrl = QHBoxLayout()

        ctrl.addWidget(QLabel("Sources:"))
        self._pw_go_bp = _make_checkbox("GO:BP", True)
        self._pw_kegg  = _make_checkbox("KEGG", True)
        self._pw_reac  = _make_checkbox("Reactome", True)
        self._pw_go_mf = _make_checkbox("GO:MF", False)
        self._pw_go_cc = _make_checkbox("GO:CC", False)
        ctrl.addWidget(self._pw_go_bp)
        ctrl.addWidget(self._pw_kegg)
        ctrl.addWidget(self._pw_reac)
        ctrl.addWidget(self._pw_go_mf)
        ctrl.addWidget(self._pw_go_cc)

        ctrl.addWidget(QLabel("  Mode:"))
        self._pw_mode_combo = QComboBox()
        self._pw_mode_combo.addItems(["Split (up/down separate)", "Combined"])
        ctrl.addWidget(self._pw_mode_combo)

        self._pw_gsea_check = _make_checkbox("Run GSEA", False)
        ctrl.addWidget(self._pw_gsea_check)

        ctrl.addStretch()

        self._pw_run_btn = QPushButton("Run Enrichment")
        self._pw_run_btn.setIcon(qta.icon("fa5s.play"))
        self._pw_run_btn.setStyleSheet("QPushButton { font-weight: bold; }")
        self._pw_run_btn.clicked.connect(self._run_pathway_enrichment)
        ctrl.addWidget(self._pw_run_btn)

        layout.addLayout(ctrl)

        # Status
        self._pw_status = QLabel("Run DEG analysis first, then run pathway enrichment.")
        self._pw_status.setWordWrap(True)
        layout.addWidget(self._pw_status)

        # Biomaterial flags banner (hidden until results)
        self._pw_flags_frame = QFrame()
        self._pw_flags_frame.setStyleSheet(
            "QFrame { background: #d4edda; border: 1px solid #28a745; "
            "border-radius: 4px; padding: 4px; }"
        )
        fl = QHBoxLayout(self._pw_flags_frame)
        fl.setContentsMargins(8, 4, 8, 4)
        fl.addWidget(QLabel())  # placeholder for icon
        self._pw_flags_label = QLabel("")
        self._pw_flags_label.setWordWrap(True)
        fl.addWidget(self._pw_flags_label, 1)
        self._pw_flags_frame.setVisible(False)
        layout.addWidget(self._pw_flags_frame)

        # ORA results table
        layout.addWidget(QLabel("Over-Representation Analysis (ORA):"))
        self._pw_ora_table = QTableWidget(0, 7)
        self._pw_ora_table.setHorizontalHeaderLabels([
            "Source", "Term", "padj", "Overlap", "Term Size", "Direction", "Genes"
        ])
        self._pw_ora_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._pw_ora_table.horizontalHeader().setSectionResizeMode(
            6, QHeaderView.ResizeMode.Stretch
        )
        self._pw_ora_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._pw_ora_table.setAlternatingRowColors(True)
        self._pw_ora_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self._pw_ora_table)

        # GSEA results table (hidden until GSEA is run)
        self._pw_gsea_label = QLabel("Gene Set Enrichment Analysis (GSEA — biomaterial pathways):")
        self._pw_gsea_label.setVisible(False)
        layout.addWidget(self._pw_gsea_label)

        self._pw_gsea_table = QTableWidget(0, 6)
        self._pw_gsea_table.setHorizontalHeaderLabels([
            "Gene Set", "NES", "p-value", "FDR", "Size", "Leading Edge"
        ])
        self._pw_gsea_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._pw_gsea_table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.Stretch
        )
        self._pw_gsea_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._pw_gsea_table.setAlternatingRowColors(True)
        self._pw_gsea_table.setVisible(False)
        layout.addWidget(self._pw_gsea_table)

        # Bar chart (matplotlib)
        if _MPL_OK:
            self._pw_fig    = Figure(figsize=(8, 4), tight_layout=True)
            self._pw_canvas = FigureCanvas(self._pw_fig)
            self._pw_canvas.setMaximumHeight(320)
            layout.addWidget(self._pw_canvas)

        # Export
        btn_row = QHBoxLayout()
        export_btn = QPushButton("Export Enrichment Table")
        export_btn.setIcon(qta.icon("fa5s.file-csv"))
        export_btn.clicked.connect(self._export_pathway_table)
        btn_row.addWidget(export_btn)
        if _MPL_OK:
            export_fig_btn = QPushButton("Export Figure")
            export_fig_btn.setIcon(qta.icon("fa5s.save"))
            export_fig_btn.clicked.connect(self._export_pathway_figure)
            btn_row.addWidget(export_fig_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        return w

    # ── Slots: Pathway Enrichment ──────────────────────────────────────────────

    def _run_pathway_enrichment(self):
        if self._current_result is None or not self._current_result.volcano_points:
            QMessageBox.information(self, "No DEG data",
                                    "Run DEG analysis first (Expression Data tab).")
            return

        # Gather selected sources
        sources = []
        if self._pw_go_bp.isChecked():
            sources.append("GO:BP")
        if self._pw_kegg.isChecked():
            sources.append("KEGG")
        if self._pw_reac.isChecked():
            sources.append("REAC")
        if self._pw_go_mf.isChecked():
            sources.append("GO:MF")
        if self._pw_go_cc.isChecked():
            sources.append("GO:CC")
        if not sources:
            sources = ["GO:BP", "KEGG", "REAC"]

        mode = "split" if self._pw_mode_combo.currentIndex() == 0 else "combined"
        run_gsea = self._pw_gsea_check.isChecked()

        self._pw_status.setText("Running pathway enrichment ...")
        self._pw_run_btn.setEnabled(False)
        self._pw_ora_table.setRowCount(0)

        self._pathway_worker = PathwayEnrichmentWorker(
            self._current_result, mode=mode, sources=sources, run_gsea=run_gsea,
        )
        self._pathway_worker.finished.connect(self._on_pathway_finished)
        self._pathway_worker.error.connect(self._on_pathway_error)
        self._pathway_worker.start()

    def _on_pathway_finished(self, report):
        self._pw_run_btn.setEnabled(True)
        self._current_pathway_report = report

        if report.error:
            self._pw_status.setText(f"Enrichment error: {report.error}")
            return

        n_ora = len(report.enrichment_results)
        n_gsea = len(report.gsea_results)
        method = report.method or "unknown"
        self._pw_status.setText(
            f"Done ({method}): {n_ora} significant terms"
            + (f", {n_gsea} GSEA results" if n_gsea else "")
            + f"  |  {report.n_input_genes} input genes"
        )

        # Biomaterial flags
        if report.biomaterial_flags:
            self._pw_flags_label.setText(
                "<b>Biomaterial-relevant pathways detected:</b>  "
                + "  |  ".join(report.biomaterial_flags)
            )
            self._pw_flags_frame.setVisible(True)
        else:
            self._pw_flags_frame.setVisible(False)

        # Populate ORA table
        self._pw_ora_table.setRowCount(0)
        for r in report.enrichment_results[:100]:  # cap at 100 rows
            row = self._pw_ora_table.rowCount()
            self._pw_ora_table.insertRow(row)
            self._pw_ora_table.setItem(row, 0, QTableWidgetItem(r.source))
            self._pw_ora_table.setItem(row, 1, QTableWidgetItem(r.term_name))
            padj_item = QTableWidgetItem(f"{r.padj:.2e}")
            self._pw_ora_table.setItem(row, 2, padj_item)
            self._pw_ora_table.setItem(row, 3, QTableWidgetItem(str(r.intersection)))
            self._pw_ora_table.setItem(row, 4, QTableWidgetItem(str(r.term_size)))
            dir_item = QTableWidgetItem(r.direction or "mixed")
            if r.direction == "up":
                dir_item.setForeground(QColor("#c0392b"))
            elif r.direction == "down":
                dir_item.setForeground(QColor("#2980b9"))
            self._pw_ora_table.setItem(row, 5, dir_item)
            genes_str = ", ".join(r.genes[:10])
            if len(r.genes) > 10:
                genes_str += f" ... (+{len(r.genes) - 10})"
            self._pw_ora_table.setItem(row, 6, QTableWidgetItem(genes_str))

        # GSEA table
        if report.gsea_results:
            self._pw_gsea_label.setVisible(True)
            self._pw_gsea_table.setVisible(True)
            self._pw_gsea_table.setRowCount(0)
            for g in report.gsea_results:
                row = self._pw_gsea_table.rowCount()
                self._pw_gsea_table.insertRow(row)
                self._pw_gsea_table.setItem(row, 0, QTableWidgetItem(g.term_name))
                nes_item = QTableWidgetItem(f"{g.nes:+.3f}")
                if g.nes > 0:
                    nes_item.setForeground(QColor("#c0392b"))
                else:
                    nes_item.setForeground(QColor("#2980b9"))
                self._pw_gsea_table.setItem(row, 1, nes_item)
                self._pw_gsea_table.setItem(row, 2, QTableWidgetItem(f"{g.p_value:.4f}"))
                self._pw_gsea_table.setItem(row, 3, QTableWidgetItem(f"{g.fdr:.4f}"))
                self._pw_gsea_table.setItem(row, 4, QTableWidgetItem(str(g.size)))
                le_str = ", ".join(g.leading_edge[:8])
                if len(g.leading_edge) > 8:
                    le_str += f" ... (+{len(g.leading_edge) - 8})"
                self._pw_gsea_table.setItem(row, 5, QTableWidgetItem(le_str))
        else:
            self._pw_gsea_label.setVisible(False)
            self._pw_gsea_table.setVisible(False)

        # Draw bar chart
        if _MPL_OK:
            self._draw_pathway_chart(report)

    def _on_pathway_error(self, msg: str):
        self._pw_run_btn.setEnabled(True)
        self._pw_status.setText(f"Enrichment failed: {msg}")

    def _draw_pathway_chart(self, report):
        """Draw top enriched terms as horizontal bar chart."""
        self._pw_fig.clear()
        ax = self._pw_fig.add_subplot(111)

        top = report.enrichment_results[:20]
        if not top:
            ax.text(0.5, 0.5, "No significant terms", ha="center", va="center",
                    transform=ax.transAxes, fontsize=12, color="#888")
            self._pw_canvas.draw()
            return

        # Reverse so top result is at top of plot
        top = list(reversed(top))
        names = []
        for r in top:
            label = r.term_name
            if len(label) > 50:
                label = label[:47] + "..."
            names.append(label)
        neg_log10 = [-math.log10(r.padj + 1e-300) for r in top]
        colours = []
        for r in top:
            if r.direction == "up":
                colours.append("#e74c3c")
            elif r.direction == "down":
                colours.append("#3498db")
            else:
                colours.append("#7f8c8d")

        y_pos = range(len(names))
        ax.barh(y_pos, neg_log10, color=colours, edgecolor="none", height=0.7)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(names, fontsize=7)
        ax.set_xlabel("-log10(padj)", fontsize=9)
        ax.set_title("Top Enriched Pathways / Terms", fontsize=10)

        # Threshold line
        ax.axvline(-math.log10(0.05), color="grey", linestyle="--",
                   linewidth=0.8, alpha=0.6)

        self._pw_canvas.draw()

    def _export_pathway_table(self):
        if not self._current_pathway_report or not self._current_pathway_report.enrichment_results:
            QMessageBox.information(self, "No data", "Run pathway enrichment first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Enrichment Table", "pathway_enrichment.csv",
            "CSV Files (*.csv);;TSV Files (*.tsv)"
        )
        if not path:
            return
        try:
            import csv
            sep = "\t" if path.endswith(".tsv") else ","
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, delimiter=sep)
                writer.writerow(["Source", "Term_ID", "Term_Name", "padj", "p_value",
                                 "Overlap", "Term_Size", "Direction", "Precision",
                                 "Recall", "Genes"])
                for r in self._current_pathway_report.enrichment_results:
                    writer.writerow([
                        r.source, r.term_id, r.term_name, r.padj, r.p_value,
                        r.intersection, r.term_size, r.direction,
                        f"{r.precision:.4f}", f"{r.recall:.4f}",
                        ";".join(r.genes),
                    ])
            self._pw_status.setText(f"Exported to {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.warning(self, "Export Error", str(e))

    def _export_pathway_figure(self):
        if not _MPL_OK or not self._current_pathway_report:
            QMessageBox.information(self, "Nothing to export", "Run enrichment first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Pathway Figure", "pathway_enrichment.png",
            "PNG Image (*.png);;PDF (*.pdf);;SVG (*.svg)"
        )
        if path:
            self._pw_fig.savefig(path, dpi=150, bbox_inches="tight")

    # ── Metabolomics tab ──────────────────────────────────────────────────────

    def _build_metabolomics_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        # --- Search section ---
        search_frame = QFrame()
        search_frame.setFrameShape(QFrame.Shape.StyledPanel)
        sf = QHBoxLayout(search_frame)

        self._metab_search_input = QLineEdit()
        self._metab_search_input.setPlaceholderText(
            "e.g. biomaterial scaffold, hydrogel osteoblast, cartilage metabolome"
        )
        self._metab_search_input.returnPressed.connect(self._run_metab_search)
        sf.addWidget(self._metab_search_input, 3)

        self._metab_source_combo = QComboBox()
        self._metab_source_combo.addItems(["Both", "MetaboLights", "Metabolomics Workbench"])
        sf.addWidget(self._metab_source_combo)

        search_btn = QPushButton("Search")
        search_btn.setIcon(qta.icon("fa5s.search"))
        search_btn.clicked.connect(self._run_metab_search)
        sf.addWidget(search_btn)

        layout.addWidget(search_frame)

        self._metab_search_status = QLabel(
            "Search MetaboLights / Metabolomics Workbench, or load a local file."
        )
        layout.addWidget(self._metab_search_status)

        # Results table
        self._metab_results_table = QTableWidget(0, 5)
        self._metab_results_table.setHorizontalHeaderLabels(
            ["Accession", "Title", "Organism", "Platform", "Source"]
        )
        self._metab_results_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._metab_results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._metab_results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._metab_results_table.setAlternatingRowColors(True)
        self._metab_results_table.setMaximumHeight(150)
        layout.addWidget(self._metab_results_table)

        # Load buttons
        load_row = QHBoxLayout()
        local_btn = QPushButton("Load Local File (CSV/TSV)")
        local_btn.setIcon(qta.icon("fa5s.folder-open"))
        local_btn.clicked.connect(self._load_metab_local)
        load_row.addWidget(local_btn)

        demo_btn = QPushButton("Load Demo Data")
        demo_btn.setIcon(qta.icon("fa5s.flask"))
        demo_btn.clicked.connect(self._load_metab_demo)
        load_row.addWidget(demo_btn)

        load_row.addStretch()
        layout.addLayout(load_row)

        # --- Analysis section ---
        self._metab_matrix_info = QLabel("No metabolomics data loaded.")
        layout.addWidget(self._metab_matrix_info)

        # Group selection + run
        grp_frame = QFrame()
        grp_frame.setFrameShape(QFrame.Shape.StyledPanel)
        gf = QHBoxLayout(grp_frame)

        # Group A
        a_box = QVBoxLayout()
        a_box.addWidget(QLabel("Control (Group A):"))
        self._metab_group_a = QListWidget()
        self._metab_group_a.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self._metab_group_a.setMaximumHeight(100)
        a_box.addWidget(self._metab_group_a)
        gf.addLayout(a_box)

        # Group B
        b_box = QVBoxLayout()
        b_box.addWidget(QLabel("Treatment (Group B):"))
        self._metab_group_b = QListWidget()
        self._metab_group_b.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self._metab_group_b.setMaximumHeight(100)
        b_box.addWidget(self._metab_group_b)
        gf.addLayout(b_box)

        # Controls
        ctrl_box = QVBoxLayout()
        auto_btn = QPushButton("Auto-split")
        auto_btn.setIcon(qta.icon("fa5s.random"))
        auto_btn.clicked.connect(self._metab_auto_split)
        ctrl_box.addWidget(auto_btn)

        ctrl_box.addWidget(QLabel("Material:"))
        self._metab_material = QLineEdit()
        self._metab_material.setPlaceholderText("e.g. GelMA")
        ctrl_box.addWidget(self._metab_material)

        ctrl_box.addWidget(QLabel("Baseline:"))
        self._metab_baseline = QLineEdit()
        self._metab_baseline.setPlaceholderText("e.g. TCP")
        ctrl_box.addWidget(self._metab_baseline)

        run_btn = QPushButton("Run Analysis")
        run_btn.setIcon(qta.icon("fa5s.play"))
        run_btn.setStyleSheet("QPushButton { font-weight: bold; }")
        run_btn.clicked.connect(self._run_metab_diff)
        ctrl_box.addWidget(run_btn)
        gf.addLayout(ctrl_box)

        layout.addWidget(grp_frame)

        # --- Results section ---
        self._metab_diff_status = QLabel("")
        layout.addWidget(self._metab_diff_status)

        # Results table + PCA plot side by side
        results_split = QSplitter(Qt.Orientation.Horizontal)

        # Differential table
        self._metab_diff_table = QTableWidget(0, 5)
        self._metab_diff_table.setHorizontalHeaderLabels(
            ["Metabolite", "log2FC", "padj", "Direction", "Pathway"]
        )
        self._metab_diff_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._metab_diff_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._metab_diff_table.setAlternatingRowColors(True)
        results_split.addWidget(self._metab_diff_table)

        # PCA plot
        if _MPL_OK:
            self._metab_fig    = Figure(figsize=(5, 4), tight_layout=True)
            self._metab_canvas = FigureCanvas(self._metab_fig)
            results_split.addWidget(self._metab_canvas)

        layout.addWidget(results_split)

        return w

    # ── Slots: Metabolomics ───────────────────────────────────────────────────

    def _run_metab_search(self):
        query = self._metab_search_input.text().strip()
        if not query:
            return
        source_map = {"Both": "both", "MetaboLights": "metabolights",
                      "Metabolomics Workbench": "workbench"}
        source = source_map.get(self._metab_source_combo.currentText(), "both")
        self._metab_search_status.setText(f"Searching: {query} ...")
        self._metab_results_table.setRowCount(0)

        self._metab_search_worker = MetabSearchWorker(query, source=source)
        self._metab_search_worker.results_ready.connect(self._on_metab_search_done)
        self._metab_search_worker.error.connect(
            lambda msg: self._metab_search_status.setText(f"Search failed: {msg}")
        )
        self._metab_search_worker.start()

    def _on_metab_search_done(self, results: list):
        self._metab_results = results
        self._metab_search_status.setText(f"Found {len(results)} dataset(s).")
        self._metab_results_table.setRowCount(0)
        for ds in results:
            row = self._metab_results_table.rowCount()
            self._metab_results_table.insertRow(row)
            self._metab_results_table.setItem(row, 0, QTableWidgetItem(ds.get("accession", "")))
            self._metab_results_table.setItem(row, 1, QTableWidgetItem(ds.get("title", "")))
            self._metab_results_table.setItem(row, 2, QTableWidgetItem(ds.get("organism", "")))
            self._metab_results_table.setItem(row, 3, QTableWidgetItem(ds.get("platform", "")))
            self._metab_results_table.setItem(row, 4, QTableWidgetItem(ds.get("source", "")))

    def _load_metab_local(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Metabolomics Data", "",
            "Data Files (*.csv *.tsv *.txt *.json *.xlsx);;All Files (*)"
        )
        if not path:
            return
        try:
            from bio_engine.metabolomics import load_metabolomics_table
            df = load_metabolomics_table(path)
            if df is None or df.empty:
                self._metab_matrix_info.setText("Failed to parse metabolomics data.")
                return
            self._metab_matrix = df
            self._metab_matrix_info.setText(
                f"Loaded: {os.path.basename(path)}  |  "
                f"{df.shape[0]} metabolites x {df.shape[1]} samples"
            )
            self._populate_metab_samples(list(df.columns))
        except Exception as e:
            self._metab_matrix_info.setText(f"Error: {e}")

    def _load_metab_demo(self):
        try:
            from bio_engine.metabolomics import make_demo_metabolomics
            df, cols_a, cols_b = make_demo_metabolomics()
            self._metab_matrix = df
            self._metab_matrix_info.setText(
                f"Demo: {df.shape[0]} metabolites x {df.shape[1]} samples"
            )
            self._populate_metab_samples(list(df.columns))
            # Pre-select groups
            for i in range(self._metab_group_a.count()):
                self._metab_group_a.item(i).setSelected(
                    self._metab_group_a.item(i).text() in cols_a
                )
            for i in range(self._metab_group_b.count()):
                self._metab_group_b.item(i).setSelected(
                    self._metab_group_b.item(i).text() in cols_b
                )
            self._metab_material.setText("Demo material")
            self._metab_baseline.setText("Demo control")
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _populate_metab_samples(self, columns: List[str]):
        self._metab_group_a.clear()
        self._metab_group_b.clear()
        for col in columns:
            self._metab_group_a.addItem(QListWidgetItem(col))
            self._metab_group_b.addItem(QListWidgetItem(col))

    def _metab_auto_split(self):
        if self._metab_matrix is None:
            return
        cols = list(self._metab_matrix.columns)
        mid = len(cols) // 2
        self._metab_group_a.clearSelection()
        self._metab_group_b.clearSelection()
        for i in range(mid):
            self._metab_group_a.item(i).setSelected(True)
        for i in range(mid, len(cols)):
            self._metab_group_b.item(i).setSelected(True)

    def _run_metab_diff(self):
        if self._metab_matrix is None:
            QMessageBox.information(self, "No data", "Load metabolomics data first.")
            return
        group_a = [self._metab_group_a.item(i).text()
                    for i in range(self._metab_group_a.count())
                    if self._metab_group_a.item(i).isSelected()]
        group_b = [self._metab_group_b.item(i).text()
                    for i in range(self._metab_group_b.count())
                    if self._metab_group_b.item(i).isSelected()]
        if len(group_a) < 2 or len(group_b) < 2:
            QMessageBox.warning(self, "Groups too small",
                                "Select at least 2 samples per group.")
            return

        self._metab_diff_status.setText("Running differential analysis ...")
        self._metab_diff_worker = MetabDiffWorker(
            self._metab_matrix, group_a, group_b,
            material=self._metab_material.text().strip(),
            baseline=self._metab_baseline.text().strip(),
        )
        self._metab_diff_worker.finished.connect(self._on_metab_diff_done)
        self._metab_diff_worker.error.connect(
            lambda msg: self._metab_diff_status.setText(f"Analysis failed: {msg}")
        )
        self._metab_diff_worker.start()

    def _on_metab_diff_done(self, result):
        self._metab_result = result
        if result.error:
            self._metab_diff_status.setText(f"Error: {result.error}")
            return

        self._metab_diff_status.setText(
            f"Done: {result.up_count} up, {result.down_count} down. "
            f"Pathways: {', '.join(result.flagged_pathways) or 'none'}."
        )

        # Populate table
        self._metab_diff_table.setRowCount(0)
        for h in result.top_hits[:50]:
            row = self._metab_diff_table.rowCount()
            self._metab_diff_table.insertRow(row)
            self._metab_diff_table.setItem(row, 0, QTableWidgetItem(h["name"]))
            self._metab_diff_table.setItem(row, 1, QTableWidgetItem(f"{h['log2fc']:+.3f}"))
            self._metab_diff_table.setItem(row, 2, QTableWidgetItem(f"{h['padj']:.2e}"))
            dir_item = QTableWidgetItem(h["direction"])
            if h["direction"] == "up":
                dir_item.setForeground(QColor("#c0392b"))
            elif h["direction"] == "down":
                dir_item.setForeground(QColor("#2980b9"))
            self._metab_diff_table.setItem(row, 3, dir_item)
            self._metab_diff_table.setItem(row, 4, QTableWidgetItem(h.get("pathway", "")))

        # Draw PCA
        if _MPL_OK and self._metab_matrix is not None:
            self._draw_metab_pca()

    def _draw_metab_pca(self):
        """Draw PCA scatter of samples, coloured by group selection."""
        from bio_engine.metabolomics import run_pca
        pca = run_pca(self._metab_matrix, n_components=2)
        if pca.error or pca.scores.size == 0:
            return

        self._metab_fig.clear()
        ax = self._metab_fig.add_subplot(111)

        group_a_set = {
            self._metab_group_a.item(i).text()
            for i in range(self._metab_group_a.count())
            if self._metab_group_a.item(i).isSelected()
        }

        colours = ["#3498db" if s in group_a_set else "#e74c3c"
                   for s in pca.sample_names]

        ax.scatter(pca.scores[:, 0], pca.scores[:, 1], c=colours, s=40, alpha=0.8)
        for i, name in enumerate(pca.sample_names):
            ax.annotate(name, (pca.scores[i, 0], pca.scores[i, 1]),
                        fontsize=6, xytext=(3, 3), textcoords="offset points")

        ax.set_xlabel(f"PC1 ({pca.explained_var[0]:.1f}%)", fontsize=9)
        ax.set_ylabel(f"PC2 ({pca.explained_var[1]:.1f}%)", fontsize=9)
        ax.set_title("PCA — Metabolomics Samples", fontsize=10)
        self._metab_canvas.draw()

    # ── Deconvolution tab ─────────────────────────────────────────────────────

    def _build_deconv_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        info = QLabel(
            "Estimate cell type composition from bulk RNA-seq data. "
            "Uses curated marker gene sets per tissue context."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # Controls
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Tissue context:"))
        self._deconv_tissue = QComboBox()
        self._deconv_tissue.addItems([
            "general", "bone", "cartilage", "skin", "neural", "liver"
        ])
        ctrl.addWidget(self._deconv_tissue)

        ctrl.addWidget(QLabel("Method:"))
        self._deconv_method = QComboBox()
        self._deconv_method.addItems(["Marker scoring", "NNLS (reference-based)"])
        ctrl.addWidget(self._deconv_method)

        ctrl.addStretch()

        run_btn = QPushButton("Run Deconvolution")
        run_btn.setIcon(qta.icon("fa5s.play"))
        run_btn.setStyleSheet("QPushButton { font-weight: bold; }")
        run_btn.clicked.connect(self._run_deconv)
        ctrl.addWidget(run_btn)

        demo_btn = QPushButton("Load Demo")
        demo_btn.setIcon(qta.icon("fa5s.flask"))
        demo_btn.clicked.connect(self._load_deconv_demo)
        ctrl.addWidget(demo_btn)

        layout.addLayout(ctrl)

        self._deconv_status = QLabel(
            "Load expression data (GEO Search or Expression Data tab), then run deconvolution."
        )
        self._deconv_status.setWordWrap(True)
        layout.addWidget(self._deconv_status)

        # Results: table + stacked bar chart
        results_split = QSplitter(Qt.Orientation.Horizontal)

        # Proportions table
        self._deconv_table = QTableWidget(0, 1)
        self._deconv_table.setHorizontalHeaderLabels(["Cell Type"])
        self._deconv_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._deconv_table.setAlternatingRowColors(True)
        results_split.addWidget(self._deconv_table)

        # Stacked bar chart
        if _MPL_OK:
            self._deconv_fig    = Figure(figsize=(6, 4), tight_layout=True)
            self._deconv_canvas = FigureCanvas(self._deconv_fig)
            results_split.addWidget(self._deconv_canvas)

        layout.addWidget(results_split)

        return w

    # ── Slots: Deconvolution ──────────────────────────────────────────────────

    def _run_deconv(self):
        matrix = self._current_matrix
        if matrix is None:
            QMessageBox.information(
                self, "No data",
                "Load expression data first (GEO Search or Expression Data tab), "
                "or click Load Demo."
            )
            return

        tissue = self._deconv_tissue.currentText()
        method = "nnls" if self._deconv_method.currentIndex() == 1 else "markers"
        self._deconv_status.setText(f"Running {method} deconvolution ({tissue}) ...")

        self._deconv_worker = DeconvolutionWorker(matrix, tissue=tissue, method=method)
        self._deconv_worker.finished.connect(self._on_deconv_done)
        self._deconv_worker.error.connect(
            lambda msg: self._deconv_status.setText(f"Deconvolution failed: {msg}")
        )
        self._deconv_worker.start()

    def _load_deconv_demo(self):
        try:
            from bio_engine.deconvolution import make_demo_bulk_with_composition
            tissue = self._deconv_tissue.currentText()
            bulk, true_props = make_demo_bulk_with_composition(tissue=tissue)
            self._current_matrix = bulk
            self._deconv_status.setText(
                f"Demo loaded: {bulk.shape[0]} genes x {bulk.shape[1]} samples ({tissue}). "
                "Click Run Deconvolution."
            )
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _on_deconv_done(self, result):
        self._deconv_result = result
        if result.error:
            self._deconv_status.setText(f"Error: {result.error}")
            return

        n_types = len(result.cell_types)
        n_samples = len(result.sample_names)
        corr_str = f", fit r={result.correlation}" if result.correlation else ""
        warn_str = f"  |  {len(result.warnings)} warnings" if result.warnings else ""
        self._deconv_status.setText(
            f"Done ({result.method}): {n_types} cell types x {n_samples} samples"
            f"{corr_str}{warn_str}"
        )

        # Populate table
        props = result.proportions
        cols = ["Cell Type"] + list(props.index)
        self._deconv_table.setColumnCount(len(cols))
        self._deconv_table.setHorizontalHeaderLabels(cols)
        self._deconv_table.setRowCount(0)

        for ct in props.columns:
            row = self._deconv_table.rowCount()
            self._deconv_table.insertRow(row)
            self._deconv_table.setItem(row, 0, QTableWidgetItem(ct))
            for j, sample in enumerate(props.index):
                val = props.loc[sample, ct]
                item = QTableWidgetItem(f"{val:.3f}")
                self._deconv_table.setItem(row, j + 1, item)

        self._deconv_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )

        # Draw stacked bar chart
        if _MPL_OK:
            self._draw_deconv_chart(result)

    def _draw_deconv_chart(self, result):
        """Draw stacked bar chart of cell type proportions per sample."""
        self._deconv_fig.clear()
        ax = self._deconv_fig.add_subplot(111)

        props = result.proportions
        samples = list(props.index)
        cell_types = list(props.columns)

        # Colour palette
        import matplotlib.cm as cm
        n = len(cell_types)
        colors = [cm.tab20(i / max(n - 1, 1)) for i in range(n)]

        x = np.arange(len(samples))
        bottom = np.zeros(len(samples))

        for i, ct in enumerate(cell_types):
            vals = props[ct].values
            ax.bar(x, vals, bottom=bottom, label=ct, color=colors[i],
                   edgecolor="white", linewidth=0.3, width=0.7)
            bottom += vals

        ax.set_xticks(x)
        ax.set_xticklabels(samples, rotation=45, ha="right", fontsize=7)
        ax.set_ylabel("Proportion", fontsize=9)
        ax.set_title("Cell Type Composition", fontsize=10)
        ax.set_ylim(0, 1.05)
        ax.legend(fontsize=6, bbox_to_anchor=(1.01, 1), loc="upper left",
                  borderaxespad=0)
        self._deconv_fig.subplots_adjust(right=0.72)

        self._deconv_canvas.draw()

    # ── Flow Cytometry tab ──────────────────────────────────────────────────────

    def _build_flow_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        # ── Controls row ──────────────────────────────────────────────────
        ctrl = QHBoxLayout()

        load_btn = QPushButton("Load FCS File")
        load_btn.setIcon(qta.icon("fa5s.file-upload"))
        load_btn.clicked.connect(self._load_fcs_file)
        ctrl.addWidget(load_btn)

        demo_btn = QPushButton("Load Demo Data")
        demo_btn.setIcon(qta.icon("fa5s.flask"))
        demo_btn.clicked.connect(self._load_flow_demo)
        ctrl.addWidget(demo_btn)

        ctrl.addWidget(QLabel("Panel template:"))
        self._flow_panel_combo = QComboBox()
        self._flow_panel_combo.addItems(["(none)"] + list(self._get_panel_names()))
        self._flow_panel_combo.currentTextChanged.connect(self._on_panel_selected)
        ctrl.addWidget(self._flow_panel_combo)

        ctrl.addStretch()
        layout.addLayout(ctrl)

        # ── Panel info label ──────────────────────────────────────────────
        self._flow_panel_info = QLabel("")
        self._flow_panel_info.setStyleSheet("color: #6c757d; font-style: italic;")
        self._flow_panel_info.setWordWrap(True)
        layout.addWidget(self._flow_panel_info)

        # ── Gating controls ──────────────────────────────────────────────
        gate_box = QHBoxLayout()
        gate_box.addWidget(QLabel("Channel:"))
        self._flow_channel_combo = QComboBox()
        gate_box.addWidget(self._flow_channel_combo)

        gate_box.addWidget(QLabel("Threshold:"))
        self._flow_threshold_input = QLineEdit("50000")
        self._flow_threshold_input.setMaximumWidth(100)
        gate_box.addWidget(self._flow_threshold_input)

        self._flow_keep_combo = QComboBox()
        self._flow_keep_combo.addItems(["above", "below"])
        gate_box.addWidget(self._flow_keep_combo)

        gate_btn = QPushButton("Apply Gate")
        gate_btn.setIcon(qta.icon("fa5s.filter"))
        gate_btn.clicked.connect(self._run_flow_gating)
        gate_box.addWidget(gate_btn)

        gate_box.addStretch()
        layout.addLayout(gate_box)

        # ── Status ────────────────────────────────────────────────────────
        self._flow_status = QLabel(
            "Load an FCS file or demo data to begin flow cytometry analysis."
        )
        self._flow_status.setWordWrap(True)
        layout.addWidget(self._flow_status)

        # ── Results: stats table + scatter plot ──────────────────────────
        results_split = QSplitter(Qt.Orientation.Horizontal)

        self._flow_stats_table = QTableWidget(0, 7)
        self._flow_stats_table.setHorizontalHeaderLabels(
            ["Channel", "Mean", "Median", "Std", "CV%", "Min", "Max"]
        )
        self._flow_stats_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._flow_stats_table.setAlternatingRowColors(True)
        results_split.addWidget(self._flow_stats_table)

        if _MPL_OK:
            self._flow_fig    = Figure(figsize=(5, 4), tight_layout=True)
            self._flow_canvas = FigureCanvas(self._flow_fig)
            results_split.addWidget(self._flow_canvas)

        results_split.setStretchFactor(0, 1)
        results_split.setStretchFactor(1, 1)
        layout.addWidget(results_split)

        return w

    @staticmethod
    def _get_panel_names():
        try:
            from bio_engine.flow_data_processor import PANEL_TEMPLATES
            return PANEL_TEMPLATES.keys()
        except Exception:
            return []

    def _on_panel_selected(self, name: str):
        if name == "(none)":
            self._flow_panel_info.setText("")
            return
        try:
            from bio_engine.flow_data_processor import PANEL_TEMPLATES
            panel = PANEL_TEMPLATES.get(name, {})
            markers = ", ".join(panel.get("markers", []))
            desc = panel.get("description", "")
            self._flow_panel_info.setText(f"{desc}\nMarkers: {markers}")
        except Exception:
            self._flow_panel_info.setText("")

    def _load_fcs_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open FCS File", "",
            "FCS files (*.fcs);;All files (*)",
        )
        if not path:
            return
        self._flow_status.setText(f"Loading {path} ...")
        try:
            from bio_engine.flow_data_processor import load_fcs
            data = load_fcs(path)
            if data.error:
                self._flow_status.setText(f"Error: {data.error}")
                return
            self._set_flow_data(data)
        except Exception as e:
            self._flow_status.setText(f"Load failed: {e}")

    def _load_flow_demo(self):
        try:
            from bio_engine.flow_data_processor import make_demo_flow_data
            data = make_demo_flow_data(n_events=5000)
            self._set_flow_data(data)
        except Exception as e:
            self._flow_status.setText(f"Demo load failed: {e}")

    def _set_flow_data(self, data):
        self._flow_data = data
        self._flow_gated = None
        self._flow_stats = None

        # Populate channel combo
        self._flow_channel_combo.clear()
        self._flow_channel_combo.addItems(data.channels)

        # Show marker mapping
        marker_info = ", ".join(
            f"{ch}={mk}" for ch, mk in data.markers.items()
        ) if data.markers else "no marker annotations"

        self._flow_status.setText(
            f"Loaded {data.filename}: {data.n_events:,} events, "
            f"{len(data.channels)} channels. Markers: {marker_info}"
        )

        # Compute initial stats on full data
        try:
            from bio_engine.flow_data_processor import compute_population_stats
            stats = compute_population_stats(data)
            self._flow_stats = stats
            self._populate_flow_stats_table(stats)
        except Exception as e:
            logger.warning(f"Failed to compute initial flow stats: {e}")

        # Draw initial scatter (FSC vs SSC if available)
        if _MPL_OK:
            self._draw_flow_scatter(data)

    def _run_flow_gating(self):
        if self._flow_data is None:
            self._flow_status.setText("No flow data loaded.")
            return

        channel = self._flow_channel_combo.currentText()
        if not channel:
            return

        try:
            threshold = float(self._flow_threshold_input.text().strip())
        except ValueError:
            self._flow_status.setText("Invalid threshold value.")
            return

        keep = self._flow_keep_combo.currentText()
        self._flow_status.setText(
            f"Gating {channel} {keep} {threshold:.0f} ..."
        )

        self._flow_worker = FlowGatingWorker(
            self._flow_data, channel, threshold, keep=keep,
        )
        self._flow_worker.finished.connect(self._on_flow_gating_done)
        self._flow_worker.error.connect(
            lambda msg: self._flow_status.setText(f"Gating failed: {msg}")
        )
        self._flow_worker.start()

    def _on_flow_gating_done(self, gated, stats):
        self._flow_gated = gated
        self._flow_stats = stats

        self._flow_status.setText(
            f"Gate: {gated.gate_name} — "
            f"{gated.gated_events:,}/{gated.parent_events:,} events "
            f"({gated.pct:.1f}%)"
        )
        self._populate_flow_stats_table(stats)

        if _MPL_OK:
            self._draw_flow_scatter(gated.data, gate_label=gated.gate_name)

    def _populate_flow_stats_table(self, stats):
        self._flow_stats_table.setRowCount(0)
        for ch, s in stats.channel_stats.items():
            row = self._flow_stats_table.rowCount()
            self._flow_stats_table.insertRow(row)
            # Channel name (with marker if known)
            label = ch
            if self._flow_data and ch in self._flow_data.markers:
                label = f"{ch} ({self._flow_data.markers[ch]})"
            self._flow_stats_table.setItem(row, 0, QTableWidgetItem(label))
            for j, key in enumerate(["mean", "median", "std", "cv", "min", "max"]):
                item = QTableWidgetItem(f"{s.get(key, 0):.1f}")
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self._flow_stats_table.setItem(row, j + 1, item)

        self._flow_stats_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )

    def _draw_flow_scatter(self, data, gate_label: str = ""):
        self._flow_fig.clear()
        ax = self._flow_fig.add_subplot(111)

        if data.events.empty or len(data.channels) < 2:
            ax.text(0.5, 0.5, "No data to plot", ha="center", va="center",
                    transform=ax.transAxes, fontsize=12)
            self._flow_canvas.draw()
            return

        # Pick x/y: prefer FSC-A vs SSC-A, else first two channels
        chs = data.channels
        x_ch = "FSC-A" if "FSC-A" in chs else chs[0]
        y_ch = "SSC-A" if "SSC-A" in chs else (chs[1] if len(chs) > 1 else chs[0])

        x = data.events[x_ch].values
        y = data.events[y_ch].values

        # Subsample for performance
        max_pts = 5000
        if len(x) > max_pts:
            import numpy as np
            idx = np.random.default_rng(0).choice(len(x), max_pts, replace=False)
            x, y = x[idx], y[idx]

        ax.scatter(x, y, s=1, alpha=0.3, c="#1f77b4", rasterized=True)
        ax.set_xlabel(x_ch, fontsize=9)
        ax.set_ylabel(y_ch, fontsize=9)
        title = "Flow Scatter"
        if gate_label:
            title += f" — {gate_label}"
        ax.set_title(title, fontsize=10)
        ax.tick_params(labelsize=7)

        self._flow_canvas.draw()

    # ── Sequencing Advisor tab ────────────────────────────────────────────────

    def _build_seq_advisor_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        # Question input
        q_row = QHBoxLayout()
        q_row.addWidget(QLabel("Research question:"))
        self._seq_question = QLineEdit()
        self._seq_question.setPlaceholderText(
            "e.g. Which genes are changing in MSCs on my scaffold?"
        )
        q_row.addWidget(self._seq_question)
        layout.addLayout(q_row)

        # Options row
        opt_row = QHBoxLayout()
        opt_row.addWidget(QLabel("Budget:"))
        self._seq_budget = QComboBox()
        self._seq_budget.addItems(["standard", "low", "high"])
        opt_row.addWidget(self._seq_budget)

        self._seq_tissue_section = QCheckBox("Cryosectioned tissue available")
        opt_row.addWidget(self._seq_tissue_section)

        seq_btn = QPushButton("Recommend Technologies")
        seq_btn.setIcon(qta.icon("fa5s.search"))
        seq_btn.clicked.connect(self._run_seq_recommend)
        opt_row.addWidget(seq_btn)
        opt_row.addStretch()
        layout.addLayout(opt_row)

        # Decision tree quick reference
        tree_btn = QPushButton("Show Decision Tree")
        tree_btn.setIcon(qta.icon("fa5s.sitemap"))
        tree_btn.clicked.connect(self._show_decision_tree)
        layout.addWidget(tree_btn)

        # Results splitter: table + detail
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Technology table
        self._seq_table = QTableWidget(0, 6)
        self._seq_table.setHorizontalHeaderLabels([
            "#", "Technology", "Platform", "Tier", "Cost/Sample", "Turnaround",
        ])
        self._seq_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._seq_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._seq_table.currentCellChanged.connect(self._on_seq_select)
        splitter.addWidget(self._seq_table)

        # Detail view
        self._seq_detail = QTextEdit()
        self._seq_detail.setReadOnly(True)
        self._seq_detail.setPlaceholderText("Select a technology for details.")
        splitter.addWidget(self._seq_detail)

        splitter.setSizes([300, 200])
        layout.addWidget(splitter)

        # Summary label
        self._seq_summary = QLabel("")
        self._seq_summary.setWordWrap(True)
        self._seq_summary.setStyleSheet("color: #155724; font-weight: bold;")
        layout.addWidget(self._seq_summary)

        return w

    def _run_seq_recommend(self):
        question = self._seq_question.text().strip()
        if not question:
            return
        try:
            from src.bio_engine.sequencing_advisor import recommend_technology
            report = recommend_technology(
                question,
                budget=self._seq_budget.currentText(),
                has_tissue_section=self._seq_tissue_section.isChecked(),
            )
            self._seq_recs = report

            self._seq_table.setRowCount(0)
            for i, rec in enumerate(report.recommendations):
                row = self._seq_table.rowCount()
                self._seq_table.insertRow(row)
                t = rec.technology
                self._seq_table.setItem(row, 0, QTableWidgetItem(str(i + 1)))
                self._seq_table.setItem(row, 1, QTableWidgetItem(t.name))
                self._seq_table.setItem(row, 2, QTableWidgetItem(t.platform))
                tier_item = QTableWidgetItem(f"Tier {rec.tier}")
                if rec.tier == 1:
                    tier_item.setForeground(QColor("#155724"))
                elif rec.tier == 3:
                    tier_item.setForeground(QColor("#856404"))
                self._seq_table.setItem(row, 3, tier_item)
                self._seq_table.setItem(row, 4, QTableWidgetItem(t.cost_per_sample))
                self._seq_table.setItem(row, 5, QTableWidgetItem(t.turnaround))

            self._seq_summary.setText(report.decision_summary)
        except Exception as e:
            logger.error("Sequencing advisor error: %s", e)
            self._seq_summary.setText(f"Error: {e}")

    def _on_seq_select(self, row, *_args):
        if self._seq_recs is None or row < 0:
            return
        if row >= len(self._seq_recs.recommendations):
            return
        rec = self._seq_recs.recommendations[row]
        t = rec.technology
        html = (
            f"<h3>{t.name}</h3>"
            f"<p><b>Platform:</b> {t.platform}<br>"
            f"<b>Cost:</b> {t.cost_per_sample} | <b>Turnaround:</b> {t.turnaround}<br>"
            f"<b>Accessibility:</b> {t.accessibility}<br>"
            f"<b>Data format:</b> {t.data_format}</p>"
            f"<p><b>Rationale:</b> {rec.rationale}</p>"
            f"<h4>Best For</h4><ul>"
        )
        for item in t.best_for:
            html += f"<li>{item}</li>"
        html += "</ul><h4>Limitations</h4><ul>"
        for item in t.limitations:
            html += f"<li>{item}</li>"
        html += f"</ul><h4>Biomaterials Angle</h4><p>{t.biomaterials_angle}</p>"
        html += "<h4>Public Data Repositories</h4><ul>"
        for repo in t.public_repos:
            html += f"<li>{repo}</li>"
        html += "</ul>"
        self._seq_detail.setHtml(html)

    def _show_decision_tree(self):
        from src.bio_engine.sequencing_advisor import get_decision_tree
        tree = get_decision_tree()
        html = "<h3>Sequencing Technology Decision Tree</h3><table border='1' cellpadding='6'>"
        html += "<tr><th>Question</th><th>Recommended Technology</th></tr>"
        for q, tech in tree.items():
            html += f"<tr><td>{q}</td><td><b>{tech}</b></td></tr>"
        html += "</table>"
        self._seq_detail.setHtml(html)

    # ── Multi-Omics tab ───────────────────────────────────────────────────────

    def _build_multiomics_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        layout.addWidget(QLabel(
            "<b>Multi-Omics Integration:</b> Joint pathway enrichment, "
            "cross-omics correlation, and MOFA-lite factor analysis."
        ))

        # Demo data button
        btn_row = QHBoxLayout()
        demo_btn = QPushButton("Load Demo Multi-Omics Data")
        demo_btn.setIcon(qta.icon("fa5s.play"))
        demo_btn.clicked.connect(self._run_multiomics_demo)
        btn_row.addWidget(demo_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Results output
        self._multiomics_output = QTextEdit()
        self._multiomics_output.setReadOnly(True)
        self._multiomics_output.setPlaceholderText(
            "Load demo data or provide gene + metabolite matrices.\n\n"
            "Analysis includes:\n"
            "  1. Joint Pathway Enrichment -- gene + metabolite overlap on pathways\n"
            "  2. Cross-Omics Correlation -- Pearson/Spearman with FDR correction\n"
            "  3. MOFA-lite -- SVD-based multi-omics factor analysis"
        )
        layout.addWidget(self._multiomics_output)

        return w

    def _run_multiomics_demo(self):
        try:
            from src.bio_engine.multiomics_integrator import (
                make_demo_multiomics,
                run_joint_pathway_enrichment,
                run_cross_omics_correlation,
                run_mofa_lite,
            )
            gene_mat, met_mat, deg_genes, diff_mets = make_demo_multiomics()

            # 1. Joint pathway enrichment
            jp_report = run_joint_pathway_enrichment(deg_genes, diff_mets)

            # 2. Cross-omics correlation
            corrs = run_cross_omics_correlation(gene_mat, met_mat, top_n=10)

            # 3. MOFA-lite
            mofa = run_mofa_lite(gene_mat, met_mat, n_factors=3)

            # Format results
            html = "<h3>Multi-Omics Integration Results (Demo Data)</h3>"

            # Joint pathway
            html += "<h4>1. Joint Pathway Enrichment</h4>"
            html += f"<p>Query: {len(deg_genes)} DEGs + {len(diff_mets)} differential metabolites</p>"
            if jp_report.hits:
                html += "<table border='1' cellpadding='4'>"
                html += "<tr><th>Pathway</th><th>Gene Hits</th><th>Met Hits</th><th>Joint Score</th><th>Direction</th></tr>"
                for hit in jp_report.hits[:8]:
                    html += (
                        f"<tr><td>{hit.pathway_name}</td>"
                        f"<td>{hit.gene_hits}/{hit.gene_total}</td>"
                        f"<td>{hit.met_hits}/{hit.met_total}</td>"
                        f"<td>{hit.joint_score:.2f}</td>"
                        f"<td>{hit.direction}</td></tr>"
                    )
                html += "</table>"
            else:
                html += "<p>No significant joint pathway hits.</p>"

            # Cross-omics correlations
            html += "<h4>2. Top Cross-Omics Correlations</h4>"
            if corrs:
                html += "<table border='1' cellpadding='4'>"
                html += "<tr><th>Gene</th><th>Metabolite</th><th>r</th><th>p-value</th><th>FDR</th></tr>"
                for c in corrs[:8]:
                    color = "#155724" if c.correlation > 0 else "#721c24"
                    html += (
                        f"<tr><td>{c.gene}</td><td>{c.metabolite}</td>"
                        f"<td style='color:{color}'>{c.correlation:.3f}</td>"
                        f"<td>{c.p_value:.2e}</td>"
                        f"<td>{c.fdr:.2e}</td></tr>"
                    )
                html += "</table>"

            # MOFA-lite
            html += "<h4>3. MOFA-lite Factor Analysis</h4>"
            html += f"<p>Factors extracted: {mofa.n_factors}<br>"
            var_strs = [f"F{i+1}: {v:.1%}" for i, v in enumerate(mofa.variance_explained)]
            html += f"Variance explained: {', '.join(var_strs)}</p>"
            if mofa.top_gene_loadings:
                html += "<p><b>Top gene loadings (Factor 1):</b> "
                top_genes = list(mofa.top_gene_loadings.items())[:5]
                html += ", ".join(f"{g} ({v:.3f})" for g, v in top_genes)
                html += "</p>"
            if mofa.top_met_loadings:
                html += "<p><b>Top metabolite loadings (Factor 1):</b> "
                top_mets = list(mofa.top_met_loadings.items())[:5]
                html += ", ".join(f"{m} ({v:.3f})" for m, v in top_mets)
                html += "</p>"

            self._multiomics_output.setHtml(html)
        except Exception as e:
            logger.error("Multi-omics demo error: %s", e)
            self._multiomics_output.setText(f"Error: {e}")

    # ── Tissue Interaction tab ────────────────────────────────────────────────

    def _build_tissue_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        # Input controls
        input_row = QHBoxLayout()
        input_row.addWidget(QLabel("Material:"))
        self._tissue_material = QComboBox()
        self._tissue_material.setEditable(True)
        self._tissue_material.addItems([
            "", "titanium", "PLGA", "silicone", "collagen",
            "hydrogel", "PEEK", "hydroxyapatite", "silk", "PCL", "chitosan",
        ])
        input_row.addWidget(self._tissue_material)

        input_row.addWidget(QLabel("Tissue:"))
        self._tissue_type = QComboBox()
        self._tissue_type.setEditable(True)
        self._tissue_type.addItems([
            "", "bone", "cartilage", "skin", "nerve",
            "cardiac", "vascular", "tendon", "liver",
        ])
        input_row.addWidget(self._tissue_type)

        self._tissue_degradable = QCheckBox("Degradable")
        self._tissue_degradable.setChecked(True)
        input_row.addWidget(self._tissue_degradable)

        tissue_btn = QPushButton("Model Response")
        tissue_btn.setIcon(qta.icon("fa5s.heartbeat"))
        tissue_btn.clicked.connect(self._run_tissue_model)
        input_row.addWidget(tissue_btn)
        input_row.addStretch()
        layout.addLayout(input_row)

        # Biomarker timepoint lookup
        tp_row = QHBoxLayout()
        tp_row.addWidget(QLabel("Biomarkers at week:"))
        self._tissue_week_combo = QComboBox()
        self._tissue_week_combo.addItems(["0.01", "0.1", "0.5", "1", "2", "4", "8", "12", "24"])
        tp_row.addWidget(self._tissue_week_combo)
        tp_btn = QPushButton("Get Biomarkers")
        tp_btn.clicked.connect(self._run_biomarker_lookup)
        tp_row.addWidget(tp_btn)
        tp_row.addStretch()
        layout.addLayout(tp_row)

        # Results
        splitter = QSplitter(Qt.Orientation.Vertical)

        self._tissue_output = QTextEdit()
        self._tissue_output.setReadOnly(True)
        self._tissue_output.setPlaceholderText(
            "Select a material and tissue, then click 'Model Response' "
            "to see the expected tissue interaction timeline."
        )
        splitter.addWidget(self._tissue_output)

        # Interface zones (static reference)
        self._tissue_zones = QTextEdit()
        self._tissue_zones.setReadOnly(True)
        self._tissue_zones.setPlaceholderText("Interface zone model will appear here.")
        splitter.addWidget(self._tissue_zones)

        splitter.setSizes([400, 200])
        layout.addWidget(splitter)

        return w

    def _run_tissue_model(self):
        try:
            from src.bio_engine.tissue_interaction import (
                model_tissue_response, get_interface_zones,
            )
            material = self._tissue_material.currentText().strip()
            tissue = self._tissue_type.currentText().strip()
            degradable = self._tissue_degradable.isChecked()

            timeline = model_tissue_response(
                material_type=material,
                tissue_type=tissue,
                is_degradable=degradable,
            )
            self._tissue_timeline = timeline

            # Format timeline
            html = (
                f"<h3>Tissue Response Timeline: {timeline.material_type} "
                f"in {timeline.tissue_type}</h3>"
                f"<p><b>Expected outcome:</b> {timeline.overall_outcome}<br>"
                f"<b>Timeline:</b> {timeline.total_duration_weeks}</p>"
            )

            # Warnings
            if timeline.warnings:
                html += "<div style='background:#fff3cd; padding:8px; border:1px solid #ffc107; margin:8px 0;'>"
                for w_msg in timeline.warnings:
                    html += f"<p>{w_msg}</p>"
                html += "</div>"

            # Outcome factors
            html += "<h4>Key Factors</h4><ul>"
            for f in timeline.outcome_factors:
                html += f"<li>{f}</li>"
            html += "</ul>"

            # Phases
            html += "<h4>Response Phases</h4>"
            phase_colors = ["#e3f2fd", "#fff3e0", "#fce4ec", "#e8f5e9", "#f3e5f5"]
            for i, phase in enumerate(timeline.phases):
                bg = phase_colors[i % len(phase_colors)]
                html += (
                    f"<div style='background:{bg}; padding:8px; margin:4px 0; border-radius:4px;'>"
                    f"<h4>{phase.name}</h4>"
                    f"<p><b>Onset:</b> {phase.onset} | <b>Duration:</b> {phase.duration}</p>"
                    f"<p>{phase.description}</p>"
                )
                if phase.key_cells:
                    html += "<p><b>Key cells:</b> " + ", ".join(phase.key_cells) + "</p>"
                if phase.key_molecules:
                    html += "<p><b>Key molecules:</b> " + ", ".join(phase.key_molecules[:6])
                    if len(phase.key_molecules) > 6:
                        html += f" (+{len(phase.key_molecules)-6} more)"
                    html += "</p>"
                if phase.biomarkers:
                    html += "<p><b>Measurable biomarkers:</b></p><ul>"
                    for bm in phase.biomarkers:
                        html += f"<li>{bm}</li>"
                    html += "</ul>"
                html += "</div>"

            self._tissue_output.setHtml(html)

            # Interface zones
            zones = get_interface_zones()
            z_html = "<h3>Spatial Interface Zones</h3>"
            for zone in zones:
                z_html += (
                    f"<h4>{zone.zone_name} ({zone.distance_from_surface})</h4>"
                    f"<p><b>Expected cells:</b> {', '.join(zone.expected_cells)}</p>"
                    f"<p><b>ECM:</b> {', '.join(zone.expected_ecm)}</p>"
                    f"<p><b>Gene signatures:</b> {', '.join(zone.gene_signatures)}</p>"
                )
            self._tissue_zones.setHtml(z_html)

        except Exception as e:
            logger.error("Tissue interaction error: %s", e)
            self._tissue_output.setText(f"Error: {e}")

    def _run_biomarker_lookup(self):
        try:
            from src.bio_engine.tissue_interaction import get_biomarkers_for_timepoint
            weeks = float(self._tissue_week_combo.currentText())
            markers = get_biomarkers_for_timepoint(weeks)
            html = f"<h4>Recommended Biomarkers at Week {weeks}</h4><ul>"
            for m in markers:
                html += f"<li>{m}</li>"
            html += "</ul>"
            self._tissue_zones.setHtml(html)
        except Exception as e:
            self._tissue_zones.setText(f"Error: {e}")

    # ── Intervention Planner tab ──────────────────────────────────────────────

    def _build_intervention_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        layout.addWidget(QLabel(
            "<b>Pathway Intervention Planner:</b> Enter a dysregulated pathway "
            "and key genes to get genetic, pharmacological, and combinatorial strategies."
        ))

        # Pathway input
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Pathway:"))
        self._interv_pathway = QLineEdit()
        self._interv_pathway.setPlaceholderText("e.g. NF-kB signalling, TGF-beta/fibrosis, HIF-1 hypoxia")
        row1.addWidget(self._interv_pathway)

        row1.addWidget(QLabel("Direction:"))
        self._interv_direction = QComboBox()
        self._interv_direction.addItems(["activated", "suppressed"])
        row1.addWidget(self._interv_direction)
        layout.addLayout(row1)

        # Gene input
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Key genes (comma-separated):"))
        self._interv_genes = QLineEdit()
        self._interv_genes.setPlaceholderText("e.g. TNF, IL6, NFKB1")
        row2.addWidget(self._interv_genes)

        row2.addWidget(QLabel("Tissue:"))
        self._interv_tissue = QComboBox()
        self._interv_tissue.setEditable(True)
        self._interv_tissue.addItems([
            "", "bone", "cartilage", "skin", "nerve", "cardiac", "vascular", "liver",
        ])
        row2.addWidget(self._interv_tissue)

        interv_btn = QPushButton("Plan Interventions")
        interv_btn.setIcon(qta.icon("fa5s.bullseye"))
        interv_btn.clicked.connect(self._run_intervention)
        row2.addWidget(interv_btn)
        layout.addLayout(row2)

        # Results
        self._interv_output = QTextEdit()
        self._interv_output.setReadOnly(True)
        self._interv_output.setPlaceholderText(
            "Intervention strategies will appear here.\n\n"
            "Categories:\n"
            "  - GENETIC: CRISPRi/a, knockout, base/prime editing\n"
            "  - PHARMACOLOGICAL: approved drugs, clinical candidates\n"
            "  - COMBINATORIAL: dual-target strategies"
        )
        layout.addWidget(self._interv_output)

        return w

    def _run_intervention(self):
        pathway = self._interv_pathway.text().strip()
        genes_text = self._interv_genes.text().strip()
        if not pathway or not genes_text:
            return
        genes = [g.strip() for g in genes_text.split(",") if g.strip()]
        direction = self._interv_direction.currentText()
        tissue = self._interv_tissue.currentText().strip()

        try:
            from src.bio_engine.pathway_intervention import plan_intervention
            plan = plan_intervention(pathway, direction, genes, tissue_type=tissue)

            html = f"<h3>Intervention Plan: {plan.pathway_name} ({plan.direction})</h3>"
            html += f"<p>{plan.summary}</p>"

            if plan.warnings:
                html += "<div style='background:#fff3cd; padding:8px; border:1px solid #ffc107; margin:6px 0;'>"
                for w_msg in plan.warnings:
                    html += f"<p><b>Warning:</b> {w_msg}</p>"
                html += "</div>"

            # Group by type
            for stype, color, icon in [
                ("genetic", "#d4edda", "DNA"),
                ("pharmacological", "#d1ecf1", "Rx"),
                ("combinatorial", "#e2d9f3", "Combo"),
            ]:
                typed = [s for s in plan.strategies if s.strategy_type == stype]
                if not typed:
                    continue
                html += f"<h4>{icon} -- {stype.upper()} ({len(typed)})</h4>"
                for s in typed:
                    evidence_color = {
                        "approved": "#155724",
                        "clinical_trial": "#0c5460",
                        "preclinical": "#856404",
                        "computational": "#6c757d",
                    }.get(s.evidence_level, "#333")
                    html += (
                        f"<div style='background:{color}; padding:8px; margin:4px 0; border-radius:4px;'>"
                        f"<b>{s.target_gene}</b> -- {s.mechanism}<br>"
                        f"<b>Tool:</b> {s.tool}<br>"
                        f"<b>Evidence:</b> <span style='color:{evidence_color}'>"
                        f"{s.evidence_level}</span><br>"
                        f"<b>Rationale:</b> {s.rationale}<br>"
                    )
                    if s.delivery_note:
                        html += f"<b>Delivery:</b> {s.delivery_note}<br>"
                    if s.safety_flag:
                        html += f"<b>Safety:</b> {s.safety_flag}<br>"
                    if s.links:
                        html += f"<b>Links:</b> {', '.join(s.links)}"
                    html += "</div>"

            self._interv_output.setHtml(html)
        except Exception as e:
            logger.error("Intervention planner error: %s", e)
            self._interv_output.setText(f"Error: {e}")

    # ── Target Lookup tab ─────────────────────────────────────────────────────

    def _build_target_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        layout.addWidget(QLabel(
            "<b>Target Lookup:</b> Find small molecule modulators for a gene/protein target."
        ))

        # Input row
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Gene / UniProt ID:"))
        self._target_query = QLineEdit()
        self._target_query.setPlaceholderText("e.g. VEGFA, TNF, HIF1A, PTGS2")
        row1.addWidget(self._target_query)

        row1.addWidget(QLabel("Mode:"))
        self._target_mode = QComboBox()
        self._target_mode.addItems(["all", "inhibitor", "activator"])
        row1.addWidget(self._target_mode)

        row1.addWidget(QLabel("Stage:"))
        self._target_stage = QComboBox()
        self._target_stage.addItems(["all", "clinical", "approved"])
        row1.addWidget(self._target_stage)

        target_btn = QPushButton("Search")
        target_btn.setIcon(qta.icon("fa5s.search"))
        target_btn.clicked.connect(self._run_target_lookup)
        row1.addWidget(target_btn)
        layout.addLayout(row1)

        # Known targets hint
        hint_btn = QPushButton("Show Known Targets")
        hint_btn.clicked.connect(self._show_known_targets)
        layout.addWidget(hint_btn)

        # Results splitter
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Compound table
        self._target_table = QTableWidget(0, 7)
        self._target_table.setHorizontalHeaderLabels([
            "Compound", "ID", "Mode", "Potency", "Stage", "Organism", "Mechanism",
        ])
        self._target_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._target_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        splitter.addWidget(self._target_table)

        # Target info panel
        self._target_info = QTextEdit()
        self._target_info.setReadOnly(True)
        self._target_info.setPlaceholderText("Target information will appear here.")
        splitter.addWidget(self._target_info)

        splitter.setSizes([350, 150])
        layout.addWidget(splitter)

        return w

    def _run_target_lookup(self):
        query = self._target_query.text().strip()
        if not query:
            return
        try:
            from src.bio_engine.target_lookup import lookup_target
            result = lookup_target(
                query,
                mode_filter=self._target_mode.currentText(),
                clinical_filter=self._target_stage.currentText(),
            )

            # Target info
            ti = result.target_info
            if ti:
                html = (
                    f"<h3>{ti.gene_symbol} -- {ti.protein_name}</h3>"
                    f"<p><b>UniProt:</b> {ti.uniprot_id or 'N/A'}<br>"
                    f"<b>Druggability:</b> {ti.druggability}<br>"
                    f"<b>Protein class:</b> {ti.protein_class}<br>"
                    f"<b>Sources:</b> {', '.join(result.sources_queried)}</p>"
                )
                if result.errors:
                    html += "<p style='color:red'>" + "<br>".join(result.errors) + "</p>"
                self._target_info.setHtml(html)

            # Compound table
            self._target_table.setRowCount(0)
            for c in result.compounds:
                row = self._target_table.rowCount()
                self._target_table.insertRow(row)
                self._target_table.setItem(row, 0, QTableWidgetItem(c.compound_name))
                self._target_table.setItem(row, 1, QTableWidgetItem(c.compound_id))

                mode_item = QTableWidgetItem(c.mode)
                if c.mode == "inhibitor":
                    mode_item.setForeground(QColor("#dc3545"))
                elif c.mode == "activator":
                    mode_item.setForeground(QColor("#28a745"))
                self._target_table.setItem(row, 2, mode_item)

                self._target_table.setItem(row, 3, QTableWidgetItem(c.potency))

                stage_item = QTableWidgetItem(c.clinical_stage)
                if c.clinical_stage == "approved":
                    stage_item.setForeground(QColor("#155724"))
                elif "phase" in c.clinical_stage:
                    stage_item.setForeground(QColor("#0c5460"))
                self._target_table.setItem(row, 4, stage_item)

                self._target_table.setItem(row, 5, QTableWidgetItem(c.organism_tested))
                self._target_table.setItem(row, 6, QTableWidgetItem(c.mechanism))

        except Exception as e:
            logger.error("Target lookup error: %s", e)
            self._target_info.setText(f"Error: {e}")

    def _show_known_targets(self):
        from src.bio_engine.target_lookup import list_known_targets
        targets = list_known_targets()
        self._target_info.setHtml(
            "<h4>Known Targets in Local KB</h4>"
            "<p>" + ", ".join(f"<b>{t}</b>" for t in targets) + "</p>"
            "<p>These targets have curated compound data available offline. "
            "Other targets can be queried via the ChEMBL API (enable 'Use API' in settings).</p>"
        )

    # ── AI Insight tab ─────────────────────────────────────────────────────────

    def _build_ai_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        ctx_layout = QHBoxLayout()
        ctx_layout.addWidget(QLabel("Project context (optional):"))
        self._ai_context_input = QLineEdit()
        self._ai_context_input.setPlaceholderText(
            "e.g. bone tissue engineering, osteogenic scaffold, rat calvaria model"
        )
        ctx_layout.addWidget(self._ai_context_input)
        layout.addLayout(ctx_layout)

        btn_layout = QHBoxLayout()
        self._ai_btn = QPushButton("Interpret DEG Results with AI")
        self._ai_btn.setIcon(qta.icon("fa5s.magic"))
        self._ai_btn.clicked.connect(self._run_ai_interpret)
        btn_layout.addWidget(self._ai_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self._ai_output = QTextEdit()
        self._ai_output.setPlaceholderText(
            "AI interpretation will appear here after running DEG analysis.\n\n"
            "The assistant will:\n"
            "  - Interpret pathway activity in terms of biocompatibility\n"
            "  - Flag inflammation, apoptosis, or stress signals\n"
            "  - Recommend follow-up experiments\n"
            "  - Note Matrigel artefacts if applicable"
        )
        self._ai_output.setReadOnly(True)
        layout.addWidget(self._ai_output)

        return w

    # ── Slots: GEO Search ──────────────────────────────────────────────────────

    def _run_search(self):
        query = self._search_input.text().strip()
        if not query:
            return
        organism = self._organism_combo.currentText()
        if organism == "Any organism":
            organism = ""
        self._search_status.setText(f"Searching GEO for: {query} ...")
        self._results_table.setRowCount(0)

        self._search_worker = GeoSearchWorker(query, organism=organism)
        self._search_worker.results_ready.connect(self._on_search_results)
        self._search_worker.error.connect(self._on_search_error)
        self._search_worker.start()

    def _on_search_results(self, results: list):
        self._geo_results = results
        self._search_status.setText(f"Found {len(results)} dataset(s).")
        self._results_table.setRowCount(0)
        for ds in results:
            row = self._results_table.rowCount()
            self._results_table.insertRow(row)
            self._results_table.setItem(row, 0, QTableWidgetItem(ds.get("gse_id", "")))
            self._results_table.setItem(row, 1, QTableWidgetItem(ds.get("title", "")))
            self._results_table.setItem(row, 2, QTableWidgetItem(ds.get("organism", "")))
            self._results_table.setItem(row, 3, QTableWidgetItem(str(ds.get("sample_count", ""))))
            self._results_table.setItem(row, 4, QTableWidgetItem(ds.get("experiment_type", "")))

    def _on_search_error(self, msg: str):
        self._search_status.setText(f"Search failed: {msg}")

    def _on_dataset_selected(self):
        row = self._results_table.currentRow()
        if row < 0 or row >= len(self._geo_results):
            self._detail_meta.setText("Select a dataset to preview details.")
            self._detail_summary.clear()
            self._open_geo_btn.setEnabled(False)
            return
        ds = self._geo_results[row]
        gse  = ds.get("gse_id", "")
        tissue = ds.get("tissue", "") or "unknown tissue"
        n    = ds.get("sample_count", "?")
        pmids = ds.get("pubmed_ids", [])
        pmid_str = "  PubMed: " + ", ".join(pmids[:3]) if pmids else ""
        self._detail_meta.setText(
            f"{gse}  |  {tissue}  |  {n} samples{pmid_str}"
        )
        self._detail_summary.setPlainText(ds.get("summary", "") or "No summary available.")
        self._open_geo_btn.setEnabled(bool(gse))

    def _open_selected_in_geo(self):
        row = self._results_table.currentRow()
        if row < 0 or row >= len(self._geo_results):
            return
        gse = self._geo_results[row].get("gse_id", "")
        if gse:
            import webbrowser
            webbrowser.open(f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={gse}")

    def _download_selected(self):
        row = self._results_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "No selection", "Select a dataset row first.")
            return
        gse_item = self._results_table.item(row, 0)
        if not gse_item:
            return
        gse_id = gse_item.text().strip()
        if not gse_id:
            return

        self._dl_progress.setVisible(True)
        self._dl_progress.setValue(0)
        self._dl_progress.setRange(0, 0)   # indeterminate until we know size
        self._search_status.setText(f"Downloading {gse_id} ...")

        self._download_worker = DownloadWorker(gse_id)
        self._download_worker.progress.connect(self._on_dl_progress)
        self._download_worker.finished.connect(self._on_dl_finished)
        self._download_worker.error.connect(self._on_dl_error)
        self._download_worker.start()

    def _on_dl_progress(self, done: int, total: int):
        if total > 0:
            self._dl_progress.setRange(0, total)
            self._dl_progress.setValue(done)
            mb = done / 1_048_576
            self._search_status.setText(f"Downloading ... {mb:.1f} MB")

    def _on_dl_finished(self, path: str):
        self._dl_progress.setVisible(False)
        self._search_status.setText(f"Downloaded: {os.path.basename(path)}")
        self._loaded_file_path = path
        self._load_matrix_from_path(path)

    def _on_dl_error(self, msg: str):
        self._dl_progress.setVisible(False)
        self._search_status.setText(f"Download failed: {msg}")
        QMessageBox.warning(self, "Download Error", msg)

    def _load_local_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Series Matrix File", "",
            "GEO Matrix (*.txt *.txt.gz *.gz);;All Files (*)"
        )
        if path:
            self._loaded_file_path = path
            self._load_matrix_from_path(path)

    # ── Slots: Expression Data ─────────────────────────────────────────────────

    def _load_matrix_from_path(self, path: str):
        self._matrix_info.setText(f"Loading: {os.path.basename(path)} ...")
        try:
            from bio_engine.transcriptomics import load_series_matrix
            df = load_series_matrix(path)
            if df is None or df.empty:
                self._matrix_info.setText("Failed to parse expression matrix.")
                return
            self._current_matrix = df
            n_genes, n_samples = df.shape
            self._matrix_info.setText(
                f"Loaded: {os.path.basename(path)}  |  "
                f"{n_genes:,} probes/genes  x  {n_samples} samples"
            )
            self._populate_sample_lists(list(df.columns))
            # Switch to expression tab
            self._tabs.setCurrentIndex(1)
        except Exception as e:
            self._matrix_info.setText(f"Error loading matrix: {e}")

    def _populate_sample_lists(self, columns: List[str]):
        self._group_a_list.clear()
        self._group_b_list.clear()
        for col in columns:
            self._group_a_list.addItem(QListWidgetItem(col))
            self._group_b_list.addItem(QListWidgetItem(col))
        # Default: no selection (user must choose)

    def _auto_split_groups(self):
        if self._current_matrix is None:
            QMessageBox.information(self, "No data", "Load a matrix first.")
            return
        cols = list(self._current_matrix.columns)
        mid  = len(cols) // 2
        self._group_a_list.clearSelection()
        self._group_b_list.clearSelection()
        for i in range(mid):
            self._group_a_list.item(i).setSelected(True)
        for i in range(mid, len(cols)):
            self._group_b_list.item(i).setSelected(True)

    def _load_demo_matrix(self):
        try:
            from bio_engine.transcriptomics import make_demo_matrix
            df, cols_a, cols_b = make_demo_matrix()
            self._current_matrix = df
            n_genes, n_samples = df.shape
            self._matrix_info.setText(
                f"Demo matrix loaded: {n_genes} genes x {n_samples} samples"
            )
            self._populate_sample_lists(list(df.columns))
            # Pre-select groups A and B
            for i in range(self._group_a_list.count()):
                col = self._group_a_list.item(i).text()
                self._group_a_list.item(i).setSelected(col in cols_a)
            for i in range(self._group_b_list.count()):
                col = self._group_b_list.item(i).text()
                self._group_b_list.item(i).setSelected(col in cols_b)
            self._baseline_input.setText("Demo control")
            self._material_input.setText("Demo material")
            self._tabs.setCurrentIndex(1)
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _run_deg(self):
        if self._current_matrix is None:
            QMessageBox.information(self, "No data", "Load a matrix first.")
            return
        group_a = [self._group_a_list.item(i).text()
                   for i in range(self._group_a_list.count())
                   if self._group_a_list.item(i).isSelected()]
        group_b = [self._group_b_list.item(i).text()
                   for i in range(self._group_b_list.count())
                   if self._group_b_list.item(i).isSelected()]
        if len(group_a) < 2 or len(group_b) < 2:
            QMessageBox.warning(self, "Groups too small",
                                "Select at least 2 samples per group.")
            return

        self._deg_status.setText("Running DEG analysis ...")
        self._deg_worker = DEGWorker(
            self._current_matrix, group_a, group_b,
            material=self._material_input.text().strip(),
            baseline=self._baseline_input.text().strip(),
        )
        self._deg_worker.finished.connect(self._on_deg_finished)
        self._deg_worker.error.connect(self._on_deg_error)
        self._deg_worker.start()

    def _on_deg_finished(self, result):
        self._current_result = result
        if result.error:
            self._deg_status.setText(f"DEG error: {result.error}")
            return
        self._deg_status.setText(
            f"Done: {result.up_count} up, {result.down_count} down. "
            f"Pathways: {', '.join(result.flagged_pathways) or 'none'}."
        )
        self._draw_volcano(result)
        self._populate_deg_table(result)
        self._tabs.setCurrentIndex(2)

    def _on_deg_error(self, msg: str):
        self._deg_status.setText(f"DEG failed: {msg}")

    # ── Volcano Plot ───────────────────────────────────────────────────────────

    def _draw_volcano(self, result):
        if not _MPL_OK:
            return
        self._fig.clear()
        ax = self._fig.add_subplot(111)

        up_x, up_y     = [], []
        down_x, down_y = [], []
        ns_x, ns_y     = [], []
        mat_x, mat_y, mat_labels = [], [], []

        from bio_engine.transcriptomics import MATRIGEL_ARTEFACT_GENES
        artefact_set = {g.upper() for g in MATRIGEL_ARTEFACT_GENES}

        for pt in result.volcano_points:
            x, y = pt.log2fc, pt.neg_log10p
            if pt.significant and pt.gene.upper() in artefact_set:
                mat_x.append(x)
                mat_y.append(y)
                mat_labels.append(pt.gene)
            elif pt.direction == "up":
                up_x.append(x); up_y.append(y)
            elif pt.direction == "down":
                down_x.append(x); down_y.append(y)
            else:
                ns_x.append(x); ns_y.append(y)

        ax.scatter(ns_x, ns_y, s=8, color="#aaaaaa", alpha=0.5, label="NS")
        ax.scatter(up_x, up_y, s=12, color="#e74c3c", alpha=0.7, label="Up")
        ax.scatter(down_x, down_y, s=12, color="#3498db", alpha=0.7, label="Down")
        if mat_x:
            ax.scatter(mat_x, mat_y, s=18, color="#f39c12", alpha=0.9,
                       marker="^", label="Matrigel artefact")
            for xi, yi, gi in zip(mat_x, mat_y, mat_labels):
                ax.annotate(gi, (xi, yi), fontsize=6, color="#8b5e0a",
                            xytext=(2, 2), textcoords="offset points")

        # Label top 10 significant (non-artefact) genes
        sig = sorted(
            [p for p in result.volcano_points
             if p.significant and p.gene.upper() not in artefact_set],
            key=lambda p: p.padj
        )[:10]
        for pt in sig:
            ax.annotate(pt.gene, (pt.log2fc, pt.neg_log10p),
                        fontsize=6, xytext=(2, 2), textcoords="offset points")

        # Threshold lines
        ax.axhline(-__import__("math").log10(0.05), color="grey",
                   linestyle="--", linewidth=0.8, alpha=0.6)
        ax.axvline(1.0,  color="grey", linestyle="--", linewidth=0.8, alpha=0.6)
        ax.axvline(-1.0, color="grey", linestyle="--", linewidth=0.8, alpha=0.6)

        ax.set_xlabel("log2 Fold Change", fontsize=10)
        ax.set_ylabel("-log10(padj)", fontsize=10)
        title = f"Volcano: {result.material or 'treatment'} vs {result.baseline or 'control'}"
        ax.set_title(title, fontsize=11)
        ax.legend(fontsize=8, markerscale=1.2)

        # Matrigel caveat watermark
        if result.matrigel_caveat:
            ax.text(0.01, 0.99, "Matrigel baseline — interpret ECM/hypoxia with caution",
                    transform=ax.transAxes, fontsize=7, color="#856404",
                    va="top", style="italic")

        self._canvas.draw()

        # Update summary label
        caveat_note = ""
        if result.matrigel_caveat and result.matrigel_genes:
            caveat_note = f"  |  Matrigel artefacts: {', '.join(result.matrigel_genes[:5])}"
        self._volcano_summary.setText(
            f"{result.up_count} up  /  {result.down_count} down  "
            f"|  Pathways: {', '.join(result.flagged_pathways) or 'none'}{caveat_note}"
        )

    def _populate_deg_table(self, result):
        self._deg_table.setRowCount(0)
        for d in result.top_degs[:30]:
            row = self._deg_table.rowCount()
            self._deg_table.insertRow(row)
            self._deg_table.setItem(row, 0, QTableWidgetItem(d["gene"]))
            self._deg_table.setItem(row, 1, QTableWidgetItem(f"{d['log2fc']:+.3f}"))
            self._deg_table.setItem(row, 2, QTableWidgetItem(f"{d['padj']:.2e}"))
            dir_item = QTableWidgetItem(d["direction"])
            if d["direction"] == "up":
                dir_item.setForeground(QColor("#c0392b"))
            elif d["direction"] == "down":
                dir_item.setForeground(QColor("#2980b9"))
            self._deg_table.setItem(row, 3, dir_item)

    def _export_volcano(self):
        if not _MPL_OK or self._current_result is None:
            QMessageBox.information(self, "Nothing to export",
                                    "Run DEG analysis first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Volcano Plot", "volcano.png",
            "PNG Image (*.png);;PDF (*.pdf);;SVG (*.svg)"
        )
        if path:
            self._fig.savefig(path, dpi=150, bbox_inches="tight")

    # ── Slots: AI Insight ──────────────────────────────────────────────────────

    def _run_ai_interpret(self):
        if self._current_result is None:
            QMessageBox.information(self, "No data",
                                    "Run DEG analysis first.")
            return
        if not self._current_result.top_degs:
            QMessageBox.information(self, "No significant DEGs",
                                    "No significant genes found to interpret.")
            return

        self._ai_output.setText("Asking AI for interpretation ...")
        self._ai_btn.setEnabled(False)
        context = self._ai_context_input.text().strip()
        self._ai_worker = AIInterpretWorker(self._current_result, context)
        self._ai_worker.finished.connect(self._on_ai_finished)
        self._ai_worker.error.connect(self._on_ai_error)
        self._ai_worker.start()

    def _on_ai_finished(self, text: str):
        self._ai_output.setText(text)
        self._ai_btn.setEnabled(True)

    def _on_ai_error(self, msg: str):
        self._ai_output.setText(
            f"AI interpretation unavailable: {msg}\n\n"
            "Check that ANTHROPIC_API_KEY is set in config/.env"
        )
        self._ai_btn.setEnabled(True)
