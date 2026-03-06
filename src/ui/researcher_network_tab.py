"""
Researcher Network Tab
======================
Tracks key researchers, syncs their latest papers,
and shows a live feed of new publications.

Day-one features (per architecture doc):
  - Manual add (name → auto PubMed query → save)
  - Researcher list with last-sync status
  - Paper feed (newest papers from tracked researchers)
  - Sync individual or all researchers

Post day-one (placeholders present):
  - Co-authorship graph visualisation
  - BFS network discovery wizard
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QLabel, QLineEdit, QPushButton, QTableWidget,
                             QTableWidgetItem, QFrame, QTabWidget, QSplitter,
                             QHeaderView, QMessageBox, QProgressBar,
                             QTextEdit, QComboBox, QDialog, QDialogButtonBox,
                             QFormLayout, QListWidget, QListWidgetItem)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor
import qtawesome as qta


# ── Background workers ────────────────────────────────────────────────────────

class SyncWorker(QThread):
    """Syncs one or all researchers in background."""
    progress      = pyqtSignal(str, int, int)   # name, current, total
    paper_count   = pyqtSignal(str, int)         # name, count
    finished      = pyqtSignal()
    error         = pyqtSignal(str)

    def __init__(self, researcher_id=None):
        super().__init__()
        self.researcher_id = researcher_id   # None = sync all

    def run(self):
        try:
            from literature_engine.researcher_tracker import ResearcherTracker
            tracker = ResearcherTracker()

            if self.researcher_id:
                name = f"researcher id={self.researcher_id}"
                try:
                    from data_manager import crud
                    r = crud.get_researcher(self.researcher_id)
                    name = r.get("name", name)
                except Exception:
                    pass
                self.progress.emit(name, 1, 1)
                papers = tracker.sync_researcher(self.researcher_id)
                self.paper_count.emit(name, len(papers))
            else:
                def _cb(name, current, total):
                    self.progress.emit(name, current, total)

                results = tracker.sync_all(progress_callback=_cb)
                for name, count in results.items():
                    self.paper_count.emit(name, count)

            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class AddResearcherDialog(QDialog):
    """Modal dialog for adding a new researcher manually."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Researcher")
        self.setMinimumWidth(420)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(
            "Enter the researcher's name. A PubMed query will be\n"
            "auto-generated but you can customise it.")
        info.setStyleSheet("color: #6c757d; font-size: 11px;")
        layout.addWidget(info)

        form = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Jos Malda")
        self.name_input.textChanged.connect(self._auto_query)
        form.addRow("Full name *", self.name_input)

        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("e.g. Malda J[au]")
        form.addRow("PubMed query", self.query_input)

        self.orcid_input = QLineEdit()
        self.orcid_input.setPlaceholderText("0000-0000-0000-0000")
        form.addRow("ORCID (optional)", self.orcid_input)

        self.institution_input = QLineEdit()
        self.institution_input.setPlaceholderText("e.g. UMC Utrecht")
        form.addRow("Institution", self.institution_input)

        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("comma separated: biofabrication, cartilage")
        form.addRow("Tags", self.tags_input)

        self.group_input = QLineEdit()
        self.group_input.setPlaceholderText("e.g. Dutch Biofab Network")
        form.addRow("Group / cluster", self.group_input)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _auto_query(self, name: str):
        """Auto-generate PubMed query from name."""
        parts = name.strip().split()
        if len(parts) >= 2:
            self.query_input.setText(f"{parts[-1]} {parts[0][0]}[au]")

    def get_values(self) -> dict:
        tags = [t.strip() for t in self.tags_input.text().split(",") if t.strip()]
        return {
            "name":        self.name_input.text().strip(),
            "pubmed_query":self.query_input.text().strip(),
            "orcid":       self.orcid_input.text().strip(),
            "institution": self.institution_input.text().strip(),
            "tags":        tags,
            "group_name":  self.group_input.text().strip(),
        }


# ── Main tab ──────────────────────────────────────────────────────────────────

class ResearcherNetworkTab(QWidget):
    """Researcher Network — track researchers, sync papers, view feed."""

    def __init__(self):
        super().__init__()
        self._researchers = []
        self._feed_papers = []
        self.init_ui()
        self._load_researchers()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Header
        header = QLabel("Researcher Network")
        header.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(header)

        # Progress bar (shared by sync operations)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 0)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        layout.addWidget(self.status_label)

        # Tabs
        tabs = QTabWidget()

        # ── My Network tab ────────────────────────────────────────────
        network_tab = QWidget()
        network_layout = QVBoxLayout(network_tab)

        # Toolbar
        toolbar = QHBoxLayout()

        add_btn = QPushButton("  Add Researcher")
        add_btn.setIcon(qta.icon('fa5s.user-plus'))
        add_btn.setStyleSheet(
            "QPushButton { background-color: #2E86AB; color: white; "
            "border-radius: 5px; padding: 6px 14px; font-weight: bold; }"
            "QPushButton:hover { background-color: #1a6a8a; }")
        add_btn.clicked.connect(self.add_researcher_dialog)

        sync_all_btn = QPushButton("  Sync All")
        sync_all_btn.setIcon(qta.icon('fa5s.sync'))
        sync_all_btn.clicked.connect(self.sync_all)

        sync_one_btn = QPushButton("  Sync Selected")
        sync_one_btn.setIcon(qta.icon('fa5s.sync'))
        sync_one_btn.clicked.connect(self.sync_selected)

        remove_btn = QPushButton("  Remove")
        remove_btn.setIcon(qta.icon('fa5s.trash'))
        remove_btn.clicked.connect(self.remove_researcher)

        self.researcher_count_label = QLabel("0 researchers")
        self.researcher_count_label.setStyleSheet("color: #6c757d;")

        toolbar.addWidget(add_btn)
        toolbar.addWidget(sync_all_btn)
        toolbar.addWidget(sync_one_btn)
        toolbar.addWidget(remove_btn)
        toolbar.addStretch()
        toolbar.addWidget(self.researcher_count_label)
        network_layout.addLayout(toolbar)

        # Researcher table
        self.researcher_table = QTableWidget()
        self.researcher_table.setColumnCount(6)
        self.researcher_table.setHorizontalHeaderLabels([
            "Name", "Institution", "Group", "Tags", "Papers", "Last Synced"
        ])
        self.researcher_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self.researcher_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        _rh = self.researcher_table.horizontalHeader()
        if _rh:
            _rh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            _rh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            _rh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.researcher_table.setAlternatingRowColors(True)
        self.researcher_table.itemSelectionChanged.connect(
            self._on_researcher_selected)
        network_layout.addWidget(self.researcher_table)

        # Researcher detail panel
        detail_frame = QFrame()
        detail_frame.setStyleSheet(
            "QFrame { background: #f8f9fa; border: 1px solid #dee2e6; "
            "border-radius: 6px; padding: 8px; }")
        detail_frame.setMaximumHeight(120)
        detail_layout = QGridLayout(detail_frame)

        self.detail_name  = QLabel("Select a researcher")
        self.detail_name.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.detail_orcid = QLabel("")
        self.detail_orcid.setStyleSheet("color: #6c757d; font-size: 11px;")
        self.detail_query = QLabel("")
        self.detail_query.setStyleSheet(
            "color: #495057; font-size: 11px; font-family: monospace;")

        detail_layout.addWidget(self.detail_name,  0, 0, 1, 2)
        detail_layout.addWidget(QLabel("ORCID:"),  1, 0)
        detail_layout.addWidget(self.detail_orcid, 1, 1)
        detail_layout.addWidget(QLabel("PubMed query:"), 2, 0)
        detail_layout.addWidget(self.detail_query, 2, 1)

        network_layout.addWidget(detail_frame)
        tabs.addTab(network_tab, qta.icon('fa5s.users'), "My Network")

        # ── Feed tab ──────────────────────────────────────────────────
        feed_tab = QWidget()
        feed_layout = QVBoxLayout(feed_tab)

        feed_toolbar = QHBoxLayout()
        refresh_feed_btn = QPushButton("  Refresh Feed")
        refresh_feed_btn.setIcon(qta.icon('fa5s.sync'))
        refresh_feed_btn.clicked.connect(self._load_feed)

        self.feed_filter = QComboBox()
        self.feed_filter.addItem("All researchers")
        self.feed_filter.currentIndexChanged.connect(self._load_feed)

        self.feed_flag_btn = QPushButton("  Flag for Briefing")
        self.feed_flag_btn.setIcon(qta.icon('fa5s.bookmark'))
        self.feed_flag_btn.setEnabled(False)
        self.feed_flag_btn.clicked.connect(self.toggle_feed_flag)

        self.feed_flagged_label = QLabel("")
        self.feed_flagged_label.setStyleSheet("color: #6c757d; font-size: 11px;")

        feed_toolbar.addWidget(refresh_feed_btn)
        feed_toolbar.addWidget(QLabel("Filter:"))
        feed_toolbar.addWidget(self.feed_filter)
        feed_toolbar.addWidget(self.feed_flag_btn)
        feed_toolbar.addWidget(self.feed_flagged_label)
        feed_toolbar.addStretch()
        feed_layout.addLayout(feed_toolbar)

        self.feed_table = QTableWidget()
        self.feed_table.setColumnCount(5)
        self.feed_table.setHorizontalHeaderLabels([
            "Title", "Authors", "Journal", "Year", "PMID"
        ])
        self.feed_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self.feed_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        _fh = self.feed_table.horizontalHeader()
        if _fh:
            _fh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.feed_table.setAlternatingRowColors(True)
        self.feed_table.itemSelectionChanged.connect(self._on_feed_paper_selected)
        feed_layout.addWidget(self.feed_table)

        # Abstract preview
        self.feed_abstract = QTextEdit()
        self.feed_abstract.setReadOnly(True)
        self.feed_abstract.setMaximumHeight(140)
        self.feed_abstract.setPlaceholderText("Select a paper to preview abstract...")
        feed_layout.addWidget(self.feed_abstract)

        tabs.addTab(feed_tab, qta.icon('fa5s.rss'), "Paper Feed")

        # ── Discover tab (post day-one placeholder) ───────────────────
        discover_tab = QWidget()
        discover_layout = QVBoxLayout(discover_tab)
        discover_layout.addWidget(QLabel(
            "Network Discovery (BFS co-author expansion)\n\n"
            "Coming post day-one:\n"
            "• Set hop depth (1-2) and time window\n"
            "• App finds co-authors of your tracked researchers\n"
            "• Review table — you approve before anything is added\n"
            "• Co-authorship graph visualisation"))
        discover_layout.addStretch()
        tabs.addTab(discover_tab, qta.icon('fa5s.share-alt'), "Discover")

        layout.addWidget(tabs)

    # ── Data loading ──────────────────────────────────────────────────────────

    def _load_researchers(self):
        """Load researchers from DB, seeding defaults if empty."""
        try:
            from literature_engine.researcher_tracker import ResearcherTracker
            tracker = ResearcherTracker()
            added   = tracker.seed_if_empty()
            if added:
                self.status_label.setText(
                    f"Seeded {added} key researchers. Click 'Sync All' to fetch their papers.")
        except Exception as e:
            self.status_label.setText(f"Could not seed researchers: {e}")

        self._refresh_table()
        self._populate_feed_filter()
        self._load_feed()

    def _refresh_table(self):
        """Reload researcher list from DB into table."""
        from data_manager import crud
        self._researchers = crud.list_researchers()
        self.researcher_table.setRowCount(len(self._researchers))

        for row, r in enumerate(self._researchers):
            tags = r.get("tags_json") or []
            if isinstance(tags, list):
                tag_str = ", ".join(tags)
            else:
                tag_str = str(tags)

            last_synced = r.get("last_synced") or "Never"
            if last_synced and last_synced != "Never":
                last_synced = str(last_synced)[:16]

            self.researcher_table.setItem(row, 0, QTableWidgetItem(r.get("name", "")))
            self.researcher_table.setItem(row, 1, QTableWidgetItem(r.get("institution", "")))
            self.researcher_table.setItem(row, 2, QTableWidgetItem(r.get("group_name") or ""))
            self.researcher_table.setItem(row, 3, QTableWidgetItem(tag_str))
            self.researcher_table.setItem(row, 4, QTableWidgetItem(str(r.get("paper_count", 0))))
            self.researcher_table.setItem(row, 5, QTableWidgetItem(last_synced))

            # Colour rows that have never been synced
            if last_synced == "Never":
                for col in range(6):
                    item = self.researcher_table.item(row, col)
                    if item:
                        item.setForeground(QColor("#adb5bd"))

        self.researcher_count_label.setText(f"{len(self._researchers)} researchers")

    def _populate_feed_filter(self):
        self.feed_filter.blockSignals(True)
        self.feed_filter.clear()
        self.feed_filter.addItem("All researchers")
        for r in self._researchers:
            self.feed_filter.addItem(r["name"], r["id"])
        self.feed_filter.blockSignals(False)

    def _load_feed(self):
        """Load paper feed from DB."""
        try:
            from literature_engine.researcher_tracker import ResearcherTracker
            tracker = ResearcherTracker()

            rid = None
            if self.feed_filter.currentIndex() > 0:
                rid = self.feed_filter.currentData()

            self._feed_papers = tracker.get_feed(limit=100, researcher_id=rid)
            self._populate_feed_table()
            self._refresh_feed_flagged_count()
        except Exception as e:
            self.status_label.setText(f"Feed error: {e}")

    def _populate_feed_table(self):
        import json
        self.feed_table.setRowCount(len(self._feed_papers))
        for row, paper in enumerate(self._feed_papers):
            authors = paper.get("authors") or []
            if isinstance(authors, str):
                try:
                    authors = json.loads(authors)
                except Exception:
                    authors = [authors]
            author_str = ", ".join(authors[:2])
            if len(authors) > 2:
                author_str += " et al."

            self.feed_table.setItem(row, 0, QTableWidgetItem(paper.get("title", "")))
            self.feed_table.setItem(row, 1, QTableWidgetItem(author_str))
            self.feed_table.setItem(row, 2, QTableWidgetItem(paper.get("journal", "")))
            self.feed_table.setItem(row, 3, QTableWidgetItem(str(paper.get("year", ""))))
            self.feed_table.setItem(row, 4, QTableWidgetItem(str(paper.get("pmid", ""))))

    # ── Researcher actions ────────────────────────────────────────────────────

    def add_researcher_dialog(self):
        dlg = AddResearcherDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        values = dlg.get_values()
        if not values["name"]:
            QMessageBox.warning(self, "Missing name", "Please enter a researcher name.")
            return

        try:
            from literature_engine.researcher_tracker import ResearcherTracker
            tracker = ResearcherTracker()
            rid = tracker.add_researcher(**values)
            self.status_label.setText(
                f"Added {values['name']} (id={rid}). Click 'Sync Selected' to fetch their papers.")
            self._refresh_table()
            self._populate_feed_filter()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add researcher:\n{e}")

    def remove_researcher(self):
        row = self.researcher_table.currentRow()
        if row < 0 or row >= len(self._researchers):
            QMessageBox.information(self, "No selection", "Select a researcher to remove.")
            return

        r = self._researchers[row]
        reply = QMessageBox.question(
            self, "Confirm removal",
            f"Remove {r['name']} from tracking?\n"
            "(Their papers will remain in the database.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            try:
                from data_manager import get_db
                with get_db().connection() as conn:
                    conn.execute("DELETE FROM researchers WHERE id=?", (r["id"],))
                self._refresh_table()
                self._populate_feed_filter()
                self.status_label.setText(f"Removed {r['name']}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to remove:\n{e}")

    def sync_selected(self):
        row = self.researcher_table.currentRow()
        if row < 0 or row >= len(self._researchers):
            QMessageBox.information(self, "No selection",
                                    "Select a researcher to sync.")
            return
        rid = self._researchers[row]["id"]
        self._run_sync(researcher_id=rid)

    def sync_all(self):
        self._run_sync(researcher_id=None)

    def _run_sync(self, researcher_id=None):
        self.progress_bar.setVisible(True)
        self.status_label.setText("Syncing...")

        self._sync_worker = SyncWorker(researcher_id=researcher_id)
        self._sync_worker.progress.connect(self._on_sync_progress)
        self._sync_worker.paper_count.connect(self._on_paper_count)
        self._sync_worker.finished.connect(self._on_sync_finished)
        self._sync_worker.error.connect(self._on_sync_error)
        self._sync_worker.start()

    def _on_sync_progress(self, name: str, current: int, total: int):
        self.status_label.setText(f"Syncing {name} ({current}/{total})...")

    def _on_paper_count(self, name: str, count: int):
        self.status_label.setText(f"✓ {name}: {count} papers fetched")

    def _on_sync_finished(self):
        self.progress_bar.setVisible(False)
        self.status_label.setText("Sync complete")
        self._refresh_table()
        self._load_feed()

    def _on_sync_error(self, error: str):
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"Sync error: {error}")
        QMessageBox.critical(self, "Sync Failed", error)

    # ── Selection handlers ────────────────────────────────────────────────────

    def _on_researcher_selected(self):
        row = self.researcher_table.currentRow()
        if row < 0 or row >= len(self._researchers):
            return
        r = self._researchers[row]
        self.detail_name.setText(r.get("name", ""))
        self.detail_orcid.setText(r.get("orcid") or "Not set")
        self.detail_query.setText(r.get("pubmed_query") or "")

    def _on_feed_paper_selected(self):
        row = self.feed_table.currentRow()
        if row < 0 or row >= len(self._feed_papers):
            return
        paper = self._feed_papers[row]
        abstract = paper.get("abstract") or "Abstract not available."
        self.feed_abstract.setPlainText(abstract)
        self._update_feed_flag_btn(paper.get("pmid"))

    def _update_feed_flag_btn(self, pmid):
        if not pmid:
            self.feed_flag_btn.setEnabled(False)
            return
        self.feed_flag_btn.setEnabled(True)
        try:
            from data_manager.crud import get_flagged_pmids
            flagged = get_flagged_pmids()
            is_flagged = str(pmid) in flagged
            if is_flagged:
                self.feed_flag_btn.setText("  Flagged for Briefing")
                self.feed_flag_btn.setStyleSheet(
                    "QPushButton { background-color: #6f42c1; color: white; "
                    "border-radius: 5px; padding: 6px 14px; font-weight: bold; }"
                    "QPushButton:hover { background-color: #563d7c; }")
            else:
                self.feed_flag_btn.setText("  Flag for Briefing")
                self.feed_flag_btn.setStyleSheet("")
        except Exception:
            pass

    def toggle_feed_flag(self):
        row = self.feed_table.currentRow()
        if row < 0 or row >= len(self._feed_papers):
            return
        paper = self._feed_papers[row]
        pmid = paper.get("pmid")
        if not pmid:
            return
        try:
            from data_manager.crud import get_flagged_pmids, flag_paper_for_briefing, unflag_paper_for_briefing
            flagged = get_flagged_pmids()
            if str(pmid) in flagged:
                unflag_paper_for_briefing(str(pmid))
            else:
                flag_paper_for_briefing(str(pmid))
            self._update_feed_flag_btn(pmid)
            self._refresh_feed_flagged_count()
        except Exception as e:
            self.status_label.setText(f"Flag error: {e}")

    def _refresh_feed_flagged_count(self):
        try:
            from data_manager.crud import get_flagged_pmids
            n = len(get_flagged_pmids())
            self.feed_flagged_label.setText(f"{n} flagged" if n else "")
        except Exception:
            pass