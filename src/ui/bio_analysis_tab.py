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
    QComboBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QProgressBar, QPushButton, QSplitter, QTabWidget,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)
import qtawesome as qta

logger = logging.getLogger(__name__)

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


# ── Main Tab ───────────────────────────────────────────────────────────────────

class BioAnalysisTab(QWidget):
    """Biological Analysis: GEO search, DEG, volcano plot, AI interpretation."""

    def __init__(self):
        super().__init__()
        self._current_matrix   = None
        self._current_result   = None
        self._loaded_file_path: Optional[str] = None
        self._geo_results: list = []          # cache of last search results
        self._search_worker: Optional[GeoSearchWorker]   = None
        self._download_worker: Optional[DownloadWorker]  = None
        self._deg_worker: Optional[DEGWorker]            = None
        self._ai_worker: Optional[AIInterpretWorker]     = None
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
        self._tabs.addTab(self._build_ai_tab(),         qta.icon("fa5s.magic"),         "AI Insight")
        layout.addWidget(self._tabs)

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
