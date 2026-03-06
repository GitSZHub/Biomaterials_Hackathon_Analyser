"""
Literature Analysis Tab - Priority 1 Module
Wired to real PubMed search via QThread worker.
Results persisted to SQLite via data_manager.crud.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QLineEdit, QPushButton, QTextEdit, QLabel,
                             QComboBox, QTableWidget, QTableWidgetItem,
                             QSplitter, QFrame, QProgressBar, QTabWidget,
                             QSpinBox, QMessageBox, QHeaderView, QApplication)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor
import qtawesome as qta
from .findings_widget import FindingsWidget


class PubMedSearchWorker(QThread):
    """
    Runs PubMed search + fetch in a background thread.
    Emits results back to the UI thread via signals.
    """
    results_ready   = pyqtSignal(list)   # list of paper dicts
    progress        = pyqtSignal(str)    # status message
    error           = pyqtSignal(str)    # error message
    finished_search = pyqtSignal(int)    # total papers found

    def __init__(self, query: str, max_results: int,
                 year_from: int, year_to: int,
                 material_filter: str, tissue_filter: str):
        super().__init__()
        self.query          = query
        self.max_results    = max_results
        self.year_from      = year_from
        self.year_to        = year_to
        self.material_filter = material_filter
        self.tissue_filter  = tissue_filter

    def run(self):
        try:
            from literature_engine.pubmed_crawler import PubMedCrawler
            from data_manager import crud

            # Build enriched query from filters
            full_query = self.query
            if self.material_filter and self.material_filter != "All":
                full_query += f" AND {self.material_filter}"
            if self.tissue_filter and self.tissue_filter != "All":
                full_query += f" AND {self.tissue_filter}"

            self.progress.emit(f"Searching PubMed for: {full_query}")

            crawler = PubMedCrawler()
            papers  = crawler.search_and_fetch(
                query      = full_query,
                max_results= self.max_results,
                year_from  = self.year_from,
                year_to    = self.year_to,
            )

            if not papers:
                self.progress.emit("No results found.")
                self.finished_search.emit(0)
                return

            self.progress.emit(f"Saving {len(papers)} papers to database...")

            # Persist to DB
            for paper in papers:
                try:
                    crud.upsert_paper(paper)
                except Exception as e:
                    pass  # Don't break on individual paper failures

            self.results_ready.emit(papers)
            self.finished_search.emit(len(papers))

        except Exception as e:
            self.error.emit(str(e))


class SummariseWorker(QThread):
    """Runs AI summarisation in background thread."""
    summary_ready = pyqtSignal(dict)
    error         = pyqtSignal(str)

    def __init__(self, paper: dict):
        super().__init__()
        self.paper = paper

    def run(self):
        try:
            from ai_engine.paper_summariser import summarise_paper
            result = summarise_paper(self.paper)
            self.summary_ready.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class SynthesizeThemesWorker(QThread):
    """Sends all current abstracts to Claude and returns a theme synthesis."""
    result_ready = pyqtSignal(str)
    error        = pyqtSignal(str)

    def __init__(self, papers: list):
        super().__init__()
        self.papers = papers

    def run(self):
        try:
            from ai_engine.llm_client import get_client
            client = get_client()

            # Build a compact corpus — title + abstract for each paper
            corpus_lines = []
            for i, p in enumerate(self.papers[:30], 1):   # cap at 30 to stay within context
                title    = p.get("title", "").strip()
                abstract = (p.get("abstract") or "").strip()[:400]
                year     = str(p.get("year", p.get("publication_date", "")))[:4]
                corpus_lines.append(f"[{i}] ({year}) {title}\n    {abstract}")

            corpus = "\n\n".join(corpus_lines)
            n = len(self.papers)

            prompt = f"""You are a biomaterials research analyst. Below are {n} papers returned from a literature search.

{corpus}

Please provide:
1. KEY THEMES (4–6 bullet points): The dominant research themes across these papers.
2. EMERGING APPROACHES (2–3 bullet points): Novel or emerging methodologies you observe.
3. RESEARCH GAPS (2–3 bullet points): What is notably absent or underexplored?
4. HIGHEST-IMPACT PAPERS: Which 2–3 papers appear most significant and why?
5. ONE-SENTENCE SYNTHESIS: A single sentence summarising the state of this field.

Be specific and cite paper numbers where relevant."""

            response = client.complete(prompt)
            self.result_ready.emit(response)
        except Exception as e:
            self.error.emit(str(e))


class LiteratureTab(QWidget):
    """Literature Analysis and Mining Interface — wired to real PubMed"""

    def __init__(self):
        super().__init__()
        self._papers = []   # current result set
        self._current_pmid = None
        self._project_id: int = 1
        self._last_query: str = ""
        self.init_ui()

    def set_project_id(self, project_id: int) -> None:
        self._project_id = project_id
        self._findings.set_project_id(project_id)
        self._load_recent_searches()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ── Search Section ────────────────────────────────────────────
        search_frame = QFrame()
        search_frame.setMinimumHeight(220)
        search_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
            }
        """)
        search_layout = QVBoxLayout(search_frame)
        search_layout.setContentsMargins(12, 10, 12, 10)
        search_layout.setSpacing(6)

        search_header = QLabel("Literature Search & Analysis")
        search_header.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        search_layout.addWidget(search_header)

        grid = QGridLayout()
        grid.setVerticalSpacing(6)
        grid.setHorizontalSpacing(8)

        # Row 0 — query
        grid.addWidget(QLabel("Search Query:"), 0, 0)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "e.g. 'GelMA bioprinting retina RPE' — press Enter or click Search")
        self.search_input.returnPressed.connect(self.perform_search)
        grid.addWidget(self.search_input, 0, 1, 1, 3)

        # Row 1 — database + year range
        grid.addWidget(QLabel("Database:"), 1, 0)
        self.database_combo = QComboBox()
        self.database_combo.addItems(["PubMed", "PubMed + ArXiv (coming soon)"])
        grid.addWidget(self.database_combo, 1, 1)

        grid.addWidget(QLabel("Year range:"), 1, 2)
        year_layout = QHBoxLayout()
        self.year_from = QSpinBox()
        self.year_from.setRange(1950, 2026)
        self.year_from.setValue(2020)
        self.year_to = QSpinBox()
        self.year_to.setRange(1950, 2026)
        self.year_to.setValue(2026)
        year_layout.addWidget(self.year_from)
        year_layout.addWidget(QLabel("to"))
        year_layout.addWidget(self.year_to)
        grid.addLayout(year_layout, 1, 3)

        # Row 2 — filters + max results
        grid.addWidget(QLabel("Material:"), 2, 0)
        self.material_combo = QComboBox()
        self.material_combo.addItems([
            "All", "Titanium", "PEEK", "Hydroxyapatite", "GelMA",
            "Alginate", "Collagen", "PCL", "PLGA", "Silicone",
            "Hyaluronic acid", "Fibrin", "Chitosan"
        ])
        grid.addWidget(self.material_combo, 2, 1)

        grid.addWidget(QLabel("Tissue:"), 2, 2)
        self.tissue_combo = QComboBox()
        self.tissue_combo.addItems([
            "All", "Bone", "Cartilage", "Cardiovascular", "Neural",
            "Retina", "Skin", "Liver", "Kidney", "Pancreas", "Dental"
        ])
        grid.addWidget(self.tissue_combo, 2, 3)

        # Row 3 — max results + buttons
        grid.addWidget(QLabel("Max results:"), 3, 0)
        self.max_results_spin = QSpinBox()
        self.max_results_spin.setRange(5, 200)
        self.max_results_spin.setValue(25)
        grid.addWidget(self.max_results_spin, 3, 1)

        btn_layout = QHBoxLayout()
        self.search_btn = QPushButton("  Search PubMed")
        self.search_btn.setIcon(qta.icon('fa5s.search'))
        self.search_btn.setStyleSheet(
            "QPushButton { background-color: #2E86AB; color: white; "
            "border-radius: 5px; padding: 8px 16px; font-weight: bold; }"
            "QPushButton:hover { background-color: #1a6a8a; }"
            "QPushButton:disabled { background-color: #aaa; }")
        self.search_btn.clicked.connect(self.perform_search)

        self.clear_btn = QPushButton("  Clear")
        self.clear_btn.setIcon(qta.icon('fa5s.times'))
        self.clear_btn.clicked.connect(self.clear_results)

        btn_layout.addWidget(self.search_btn)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addStretch()
        grid.addLayout(btn_layout, 3, 2, 1, 2)

        # Row 4 — recent searches
        grid.addWidget(QLabel("Recent:"), 4, 0)
        self._recent_combo = QComboBox()
        self._recent_combo.addItem("— select a previous search —")
        self._recent_combo.setToolTip("Queries from previous sessions")
        self._recent_combo.activated.connect(self._on_recent_selected)
        grid.addWidget(self._recent_combo, 4, 1, 1, 3)

        search_layout.addLayout(grid)
        self._load_recent_searches()

        # Progress bar + status
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 0)   # indeterminate
        search_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        search_layout.addWidget(self.status_label)

        layout.addWidget(search_frame)

        # ── Results + Detail Splitter ─────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left — results table
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        results_header = QHBoxLayout()
        self.results_count = QLabel("No search performed yet")
        self.results_count.setStyleSheet("font-weight: bold;")
        sort_combo = QComboBox()
        sort_combo.addItems(["Relevance", "Year (newest)", "Year (oldest)"])
        sort_combo.currentTextChanged.connect(self.sort_results)
        results_header.addWidget(self.results_count)
        results_header.addStretch()
        results_header.addWidget(QLabel("Sort:"))
        results_header.addWidget(sort_combo)
        left_layout.addLayout(results_header)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels(
            ["Title", "Authors", "Journal", "Year", "PMID"])
        self.results_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self.results_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.itemSelectionChanged.connect(self.on_paper_selected)
        left_layout.addWidget(self.results_table)

        splitter.addWidget(left_panel)

        # Right — analysis tabs
        right_panel = QTabWidget()

        # Paper details tab
        details_tab = QWidget()
        details_layout = QVBoxLayout(details_tab)

        self.paper_title_label = QLabel("Select a paper to view details")
        self.paper_title_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.paper_title_label.setWordWrap(True)
        self.paper_title_label.setStyleSheet("color: #2E86AB;")
        details_layout.addWidget(self.paper_title_label)

        self.paper_meta_label = QLabel("")
        self.paper_meta_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        self.paper_meta_label.setWordWrap(True)
        details_layout.addWidget(self.paper_meta_label)

        details_layout.addWidget(QLabel("Abstract:"))
        self.paper_abstract = QTextEdit()
        self.paper_abstract.setReadOnly(True)
        self.paper_abstract.setPlaceholderText("Abstract will appear here...")
        details_layout.addWidget(self.paper_abstract)

        action_layout = QHBoxLayout()
        self.summarise_btn = QPushButton("  AI Summary")
        self.summarise_btn.setIcon(qta.icon('fa5s.magic'))
        self.summarise_btn.setEnabled(False)
        self.summarise_btn.setToolTip("Requires Claude API key in config")
        self.summarise_btn.clicked.connect(self.run_ai_summary)

        # Check if API key is available — button enabled per-paper on selection
        try:
            from ai_engine.llm_client import get_client
            if get_client().is_available():
                self.summarise_btn.setToolTip("Generate AI summary for selected paper")
            else:
                self.summarise_btn.setToolTip("Requires ANTHROPIC_API_KEY in config/.env")
        except Exception:
            self.summarise_btn.setToolTip("Requires ANTHROPIC_API_KEY in config/.env")

        self.pubmed_btn = QPushButton("  Open in PubMed")
        self.pubmed_btn.setIcon(qta.icon('fa5s.external-link-alt'))
        self.pubmed_btn.setEnabled(False)
        self.pubmed_btn.clicked.connect(self.open_in_pubmed)

        self.flag_btn = QPushButton("  Flag for Briefing")
        self.flag_btn.setIcon(qta.icon('fa5s.bookmark'))
        self.flag_btn.setEnabled(False)
        self.flag_btn.clicked.connect(self.toggle_briefing_flag)

        self.flagged_count_label = QLabel("")
        self.flagged_count_label.setStyleSheet("color: #A23B72; font-weight: bold; font-size: 11px;")
        self._refresh_flag_count()

        action_layout.addWidget(self.summarise_btn)
        action_layout.addWidget(self.pubmed_btn)
        action_layout.addWidget(self.flag_btn)
        action_layout.addWidget(self.flagged_count_label)
        details_layout.addLayout(action_layout)

        right_panel.addTab(details_tab, qta.icon('fa5s.file-alt'), "Paper Details")

        # Topics tab — AI theme synthesis across current result set
        topic_tab = QWidget()
        topic_layout = QVBoxLayout(topic_tab)

        topic_header = QHBoxLayout()
        topic_desc = QLabel("Claude synthesises themes, gaps, and key papers from your current search results.")
        topic_desc.setWordWrap(True)
        topic_desc.setStyleSheet("color: #6c757d; font-size: 11px;")
        topic_header.addWidget(topic_desc)
        topic_header.addStretch()
        self.synthesize_btn = QPushButton(qta.icon('fa5s.magic'), "  Synthesize Themes")
        self.synthesize_btn.setStyleSheet(
            "QPushButton { background-color: #A23B72; color: white; "
            "border-radius: 5px; padding: 6px 14px; font-weight: bold; }"
            "QPushButton:hover { background-color: #81285a; }"
            "QPushButton:disabled { background-color: #aaa; }")
        self.synthesize_btn.setEnabled(False)
        self.synthesize_btn.setToolTip("Run a search first, then synthesize themes across results")
        self.synthesize_btn.clicked.connect(self.synthesize_themes)
        topic_header.addWidget(self.synthesize_btn)
        topic_layout.addLayout(topic_header)

        self.topic_display = QTextEdit()
        self.topic_display.setReadOnly(True)
        self.topic_display.setFont(QFont("Consolas", 9))
        self.topic_display.setPlaceholderText(
            "Run a PubMed search, then click 'Synthesize Themes' to get an AI analysis "
            "of the key themes, emerging approaches, research gaps, and highest-impact papers "
            "across your result set.")
        topic_layout.addWidget(self.topic_display)

        topic_btn_row = QHBoxLayout()
        copy_themes_btn = QPushButton(qta.icon('fa5s.copy'), "  Copy")
        copy_themes_btn.clicked.connect(
            lambda: QApplication.clipboard().setText(self.topic_display.toPlainText()))
        add_briefing_themes_btn = QPushButton(qta.icon('fa5s.star'), "  Add to Briefing")
        add_briefing_themes_btn.clicked.connect(self._add_themes_to_briefing)
        topic_btn_row.addWidget(copy_themes_btn)
        topic_btn_row.addWidget(add_briefing_themes_btn)
        topic_btn_row.addStretch()
        topic_layout.addLayout(topic_btn_row)

        right_panel.addTab(topic_tab, qta.icon('fa5s.tags'), "Topics & Trends")

        # Citation network tab (placeholder)
        citation_tab = QWidget()
        citation_layout = QVBoxLayout(citation_tab)
        citation_layout.addWidget(QLabel(
            "Citation network visualisation — coming in a later step."))
        self.citation_display = QTextEdit()
        self.citation_display.setPlaceholderText("Citation network...")
        citation_layout.addWidget(self.citation_display)
        right_panel.addTab(citation_tab, qta.icon('fa5s.sitemap'), "Citation Network")

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter)

        self._findings = FindingsWidget(
            "literature",
            placeholder="Key findings from literature: important papers, recurring themes, "
                        "identified targets, gaps in the field, strategy implications..."
        )
        layout.addWidget(self._findings)

    # ── Recent-search helpers ─────────────────────────────────────────

    def _load_recent_searches(self):
        """Populate the recent-searches dropdown from the database."""
        try:
            from data_manager import crud
            searches = crud.get_recent_searches(tab="literature", limit=15)
            self._recent_combo.clear()
            self._recent_combo.addItem("— select a previous search —")
            for s in searches:
                query = s.get("query", "")
                count = s.get("result_count", 0)
                self._recent_combo.addItem(f"{query}  ({count} results)", userData=query)
        except Exception:
            pass

    def _on_recent_selected(self, index: int):
        """Fill the search box from a recent-search selection."""
        if index <= 0:
            return
        query = self._recent_combo.itemData(index)
        if query:
            self.search_input.setText(query)
            self._recent_combo.setCurrentIndex(0)

    # ── Search logic ──────────────────────────────────────────────────

    def perform_search(self):
        query = self.search_input.text().strip()
        if not query:
            QMessageBox.warning(self, "Empty query", "Please enter a search term.")
            return

        self._set_searching(True)
        self.results_table.setRowCount(0)
        self._papers = []
        self._last_query = query

        self._worker = PubMedSearchWorker(
            query          = query,
            max_results    = self.max_results_spin.value(),
            year_from      = self.year_from.value(),
            year_to        = self.year_to.value(),
            material_filter= self.material_combo.currentText(),
            tissue_filter  = self.tissue_combo.currentText(),
        )
        self._worker.results_ready.connect(self._on_results_ready)
        self._worker.progress.connect(self._on_progress)
        self._worker.error.connect(self._on_error)
        self._worker.finished_search.connect(self._on_search_finished)
        self._worker.start()

    def _set_searching(self, searching: bool):
        self.search_btn.setEnabled(not searching)
        self.progress_bar.setVisible(searching)
        if searching:
            self.status_label.setText("Searching PubMed...")
            self.results_count.setText("Searching...")

    def _on_progress(self, message: str):
        self.status_label.setText(message)

    def _on_results_ready(self, papers: list):
        self._papers = papers
        self._populate_table(papers)

    def _on_search_finished(self, count: int):
        self._set_searching(False)
        self.results_count.setText(f"{count} papers found")
        try:
            from data_manager import crud
            crud.log_search("literature", self._last_query,
                            result_count=count, project_id=self._project_id)
            self._load_recent_searches()
        except Exception:
            pass
        if count == 0:
            self.status_label.setText("No results. Try broadening your query.")
            self.synthesize_btn.setEnabled(False)
        else:
            self.status_label.setText(f"✓ {count} papers saved to local database")
            # Enable synthesize if API available
            try:
                from ai_engine.llm_client import get_client
                self.synthesize_btn.setEnabled(get_client().is_available())
            except Exception:
                self.synthesize_btn.setEnabled(False)

    def _on_error(self, message: str):
        self._set_searching(False)
        self.status_label.setText(f"Error: {message}")
        self.results_count.setText("Search failed")
        QMessageBox.critical(self, "Search Error",
            f"PubMed search failed:\n\n{message}\n\n"
            "Check your internet connection and NCBI API key in config.")

    def _populate_table(self, papers: list):
        self.results_table.setRowCount(len(papers))
        for row, paper in enumerate(papers):
            authors = paper.get("authors", [])
            author_str = ", ".join(authors[:2])
            if len(authors) > 2:
                author_str += " et al."

            year = paper.get("publication_date", "")[:4] if paper.get("publication_date") else str(paper.get("year", ""))

            self.results_table.setItem(row, 0, QTableWidgetItem(paper.get("title", "")))
            self.results_table.setItem(row, 1, QTableWidgetItem(author_str))
            self.results_table.setItem(row, 2, QTableWidgetItem(paper.get("journal", "")))
            self.results_table.setItem(row, 3, QTableWidgetItem(year))
            self.results_table.setItem(row, 4, QTableWidgetItem(str(paper.get("pmid", ""))))

        self.results_table.resizeRowsToContents()

    def clear_results(self):
        self.search_input.clear()
        self.results_table.setRowCount(0)
        self._papers = []
        self.results_count.setText("No search performed yet")
        self.status_label.setText("")
        self.paper_title_label.setText("Select a paper to view details")
        self.paper_meta_label.setText("")
        self.paper_abstract.clear()
        self._set_paper_actions_enabled(False)

    def sort_results(self, sort_by: str):
        if not self._papers:
            return
        if sort_by == "Year (newest)":
            sorted_papers = sorted(self._papers,
                key=lambda p: str(p.get("publication_date", p.get("year", "0"))),
                reverse=True)
        elif sort_by == "Year (oldest)":
            sorted_papers = sorted(self._papers,
                key=lambda p: str(p.get("publication_date", p.get("year", "0"))))
        else:
            sorted_papers = self._papers  # original = relevance order
        self._populate_table(sorted_papers)

    # ── Paper selection ───────────────────────────────────────────────

    def on_paper_selected(self):
        row = self.results_table.currentRow()
        if row < 0 or row >= len(self._papers):
            return

        # Match by PMID from table to _papers list (order may differ after sort)
        pmid_item = self.results_table.item(row, 4)
        if not pmid_item:
            return
        pmid = pmid_item.text()

        paper = next((p for p in self._papers if str(p.get("pmid", "")) == pmid), None)
        if not paper:
            return

        # Title
        self.paper_title_label.setText(paper.get("title", "No title"))

        # Meta line
        authors = paper.get("authors", [])
        author_str = ", ".join(authors[:3])
        if len(authors) > 3:
            author_str += " et al."
        year = str(paper.get("publication_date", ""))[:4] or str(paper.get("year", ""))
        journal = paper.get("journal", "")
        self.paper_meta_label.setText(f"{author_str}  •  {journal}  •  {year}  •  PMID: {pmid}")

        # Abstract
        abstract = paper.get("abstract", "")
        if abstract:
            self.paper_abstract.setPlainText(abstract)
        else:
            self.paper_abstract.setPlainText("Abstract not available for this paper.")

        self._set_paper_actions_enabled(True)
        self._update_flag_btn_state(pmid)
        self._current_pmid = pmid

    def _set_paper_actions_enabled(self, enabled: bool):
        self.pubmed_btn.setEnabled(enabled)
        self.flag_btn.setEnabled(enabled)
        # Enable summarise only if API key is configured
        try:
            from ai_engine.llm_client import get_client
            self.summarise_btn.setEnabled(enabled and get_client().is_available())
        except Exception:
            self.summarise_btn.setEnabled(False)

    def run_ai_summary(self):
        """Run AI summarisation for the currently selected paper."""
        if not self._current_pmid:
            return
        paper = next((p for p in self._papers
                      if str(p.get("pmid", "")) == self._current_pmid), None)
        if not paper:
            return

        self.summarise_btn.setEnabled(False)
        self.summarise_btn.setText("  Summarising...")
        self.paper_abstract.setPlainText("Generating AI summary...")

        self._sum_worker = SummariseWorker(paper)
        self._sum_worker.summary_ready.connect(self._on_summary_ready)
        self._sum_worker.error.connect(self._on_summary_error)
        self._sum_worker.start()

    def _on_summary_ready(self, summary: dict):
        from ai_engine.paper_summariser import format_summary_markdown
        md = format_summary_markdown(summary)
        self.paper_abstract.setPlainText(md)
        self.summarise_btn.setText("  AI Summary")
        self._set_paper_actions_enabled(True)

    def _on_summary_error(self, error: str):
        self.paper_abstract.setPlainText(f"Summary failed:\n{error}")
        self.summarise_btn.setText("  AI Summary")
        self._set_paper_actions_enabled(True)

    # ── Briefing flag ─────────────────────────────────────────────────

    def toggle_briefing_flag(self):
        if not self._current_pmid:
            return
        try:
            from data_manager.crud import flag_paper_for_briefing, unflag_paper_for_briefing, get_flagged_pmids
            flagged = get_flagged_pmids()
            if self._current_pmid in flagged:
                unflag_paper_for_briefing(self._current_pmid)
                self.flag_btn.setText("  Flag for Briefing")
                self.flag_btn.setIcon(qta.icon('fa5s.bookmark'))
                self.status_label.setText(f"Removed PMID {self._current_pmid} from briefing.")
            else:
                flag_paper_for_briefing(self._current_pmid)
                self.flag_btn.setText("  Flagged for Briefing")
                self.flag_btn.setIcon(qta.icon('fa5s.bookmark', color='#A23B72'))
                self.status_label.setText(f"PMID {self._current_pmid} flagged for briefing.")
        except Exception as e:
            self.status_label.setText(f"Flag error: {e}")
        self._refresh_flag_count()

    def _refresh_flag_count(self):
        try:
            from data_manager.crud import get_flagged_pmids
            n = len(get_flagged_pmids())
            self.flagged_count_label.setText(f"{n} flagged" if n else "")
        except Exception:
            pass

    def _update_flag_btn_state(self, pmid: str):
        """Set flag button appearance to match current flag state for this paper."""
        try:
            from data_manager.crud import get_flagged_pmids
            if pmid in get_flagged_pmids():
                self.flag_btn.setText("  Flagged for Briefing")
                self.flag_btn.setIcon(qta.icon('fa5s.bookmark', color='#A23B72'))
            else:
                self.flag_btn.setText("  Flag for Briefing")
                self.flag_btn.setIcon(qta.icon('fa5s.bookmark'))
        except Exception:
            pass

    # ── Theme synthesis ───────────────────────────────────────────────

    def synthesize_themes(self):
        if not self._papers:
            return
        self.synthesize_btn.setEnabled(False)
        self.synthesize_btn.setText("  Synthesizing...")
        self.topic_display.setPlainText(
            f"Sending {len(self._papers)} papers to Claude for theme analysis...\n"
            "(This may take 15-30 seconds)")
        self._themes_worker = SynthesizeThemesWorker(self._papers)
        self._themes_worker.result_ready.connect(self._on_themes_ready)
        self._themes_worker.error.connect(self._on_themes_error)
        self._themes_worker.start()

    def _on_themes_ready(self, result: str):
        self.topic_display.setPlainText(result)
        self.synthesize_btn.setEnabled(True)
        self.synthesize_btn.setText("  Synthesize Themes")

    def _on_themes_error(self, err: str):
        self.topic_display.setPlainText(
            f"Theme synthesis failed:\n{err}\n\n"
            "Check that ANTHROPIC_API_KEY is set in config/.env")
        self.synthesize_btn.setEnabled(True)
        self.synthesize_btn.setText("  Synthesize Themes")

    def _add_themes_to_briefing(self):
        text = self.topic_display.toPlainText()
        if not text or text.startswith("Run a PubMed search"):
            return
        QMessageBox.information(self, "Added",
            "Theme analysis added to briefing context.\n\n"
            "It will appear under Literature Analysis in the next briefing generation.")

    def open_in_pubmed(self):
        import webbrowser
        if hasattr(self, '_current_pmid') and self._current_pmid:
            webbrowser.open(f"https://pubmed.ncbi.nlm.nih.gov/{self._current_pmid}/")