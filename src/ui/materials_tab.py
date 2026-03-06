"""
Materials Lab Tab — Step 5
==========================
Topic tree navigation, AI knowledge cards, property comparison,
and fabrication compatibility matrix.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QLabel, QLineEdit, QPushButton, QComboBox,
                             QTableWidget, QTableWidgetItem, QFrame,
                             QTabWidget, QSplitter, QTreeWidget,
                             QTreeWidgetItem, QTextEdit, QHeaderView,
                             QProgressBar, QMessageBox, QListWidget,
                             QListWidgetItem)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor
import qtawesome as qta


# ── Background workers ────────────────────────────────────────────────────────

class KnowledgeCardWorker(QThread):
    """Fetches PubMed papers then generates AI knowledge card."""
    card_ready = pyqtSignal(dict)
    status     = pyqtSignal(str)
    error      = pyqtSignal(str)

    def __init__(self, material: dict, project_context: str = ""):
        super().__init__()
        self.material        = material
        self.project_context = project_context

    def run(self):
        try:
            from literature_engine.pubmed_crawler import PubMedCrawler
            from ai_engine.knowledge_card_gen import generate_knowledge_card
            from materials_engine.topic_tree import get_node

            name  = self.material.get("name", "")
            mclass= self.material.get("material_class", "")

            # Get PubMed terms for this topic
            topic_key = self.material.get("topic_key", "")
            node = get_node(topic_key) if topic_key else None
            terms = node.pubmed_terms if node else [name]

            # Fetch recent papers
            self.status.emit(f"Searching PubMed for {name} papers...")
            crawler = PubMedCrawler()
            papers  = []
            for term in terms[:2]:
                results = crawler.search_and_fetch(
                    query=term, max_results=5, year_from=2022)
                papers.extend(results)

            self.status.emit(f"Generating knowledge card for {name}...")
            props = self.material.get("properties") or {}
            card  = generate_knowledge_card(
                material_name    = name,
                material_class   = mclass,
                recent_papers    = papers,
                known_properties = props,
                project_context  = self.project_context,
            )
            self.card_ready.emit(card)

        except Exception as e:
            self.error.emit(str(e))


# ── Main tab ──────────────────────────────────────────────────────────────────

class MaterialsTab(QWidget):
    """Materials Lab — topic tree, knowledge cards, comparison."""

    def __init__(self):
        super().__init__()
        self._selected_material = None
        self._compare_ids       = []
        self.init_ui()
        self._load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        header = QLabel("🔬 Materials Lab")
        header.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(header)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color:#6c757d; font-size:11px;")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 0)
        layout.addWidget(self.progress_bar)

        # ── Main splitter: tree | content ─────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: topic tree + search
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 4, 0)

        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search materials...")
        self.search_input.returnPressed.connect(self._search)
        search_btn = QPushButton()
        search_btn.setIcon(qta.icon('fa5s.search'))
        search_btn.setFixedWidth(32)
        search_btn.clicked.connect(self._search)
        search_row.addWidget(self.search_input)
        search_row.addWidget(search_btn)
        left_layout.addLayout(search_row)

        self.topic_tree = QTreeWidget()
        self.topic_tree.setHeaderLabel("Material Topics")
        self.topic_tree.setMinimumWidth(200)
        self.topic_tree.itemClicked.connect(self._on_topic_selected)
        left_layout.addWidget(self.topic_tree)

        splitter.addWidget(left_panel)

        # Right: tabs for card / comparison / fabrication
        right_tabs = QTabWidget()

        # ── Knowledge Card tab ────────────────────────────────────────
        card_tab = QWidget()
        card_layout = QVBoxLayout(card_tab)

        card_toolbar = QHBoxLayout()

        self.material_label = QLabel("Select a material from the tree")
        self.material_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        card_toolbar.addWidget(self.material_label)
        card_toolbar.addStretch()

        self.gen_card_btn = QPushButton("  Generate AI Card")
        self.gen_card_btn.setIcon(qta.icon('fa5s.magic'))
        self.gen_card_btn.setEnabled(False)
        self.gen_card_btn.setStyleSheet(
            "QPushButton { background:#2E86AB; color:white; border-radius:5px;"
            " padding:5px 12px; font-weight:bold; }"
            "QPushButton:disabled { background:#adb5bd; }"
            "QPushButton:hover:!disabled { background:#1a6a8a; }")
        self.gen_card_btn.clicked.connect(self._generate_card)
        card_toolbar.addWidget(self.gen_card_btn)

        self.verify_btn = QPushButton("  Mark Verified")
        self.verify_btn.setIcon(qta.icon('fa5s.check'))
        self.verify_btn.setEnabled(False)
        self.verify_btn.clicked.connect(self._mark_verified)
        card_toolbar.addWidget(self.verify_btn)

        self.compare_btn = QPushButton("  Add to Compare")
        self.compare_btn.setIcon(qta.icon('fa5s.balance-scale'))
        self.compare_btn.setEnabled(False)
        self.compare_btn.clicked.connect(self._add_to_compare)
        card_toolbar.addWidget(self.compare_btn)

        card_layout.addLayout(card_toolbar)

        self.card_display = QTextEdit()
        self.card_display.setReadOnly(True)
        self.card_display.setPlaceholderText(
            "Select a material from the tree to view its knowledge card.\n\n"
            "Click 'Generate AI Card' to create one with Claude.")
        card_layout.addWidget(self.card_display)

        right_tabs.addTab(card_tab, qta.icon('fa5s.file-alt'), "Knowledge Card")

        # ── Comparison tab ────────────────────────────────────────────
        compare_tab = QWidget()
        compare_layout = QVBoxLayout(compare_tab)

        compare_controls = QHBoxLayout()
        self.compare_list = QListWidget()
        self.compare_list.setMaximumHeight(60)
        self.compare_list.setToolTip("Materials queued for comparison")

        clear_compare_btn = QPushButton("Clear")
        clear_compare_btn.setFixedWidth(60)
        clear_compare_btn.clicked.connect(self._clear_compare)

        run_compare_btn = QPushButton("  Compare")
        run_compare_btn.setIcon(qta.icon('fa5s.table'))
        run_compare_btn.clicked.connect(self._run_comparison)

        compare_controls.addWidget(QLabel("Comparing:"))
        compare_controls.addWidget(self.compare_list)
        compare_controls.addWidget(clear_compare_btn)
        compare_controls.addWidget(run_compare_btn)
        compare_layout.addLayout(compare_controls)

        self.compare_table = QTableWidget()
        self.compare_table.setAlternatingRowColors(True)
        compare_layout.addWidget(self.compare_table)

        right_tabs.addTab(compare_tab, qta.icon('fa5s.columns'), "Comparison")

        # ── Fabrication tab ───────────────────────────────────────────
        fab_tab = QWidget()
        fab_layout = QVBoxLayout(fab_tab)
        fab_layout.addWidget(QLabel(
            "Select a material and click 'Knowledge Card' to see fabrication compatibility.\n"
            "Full fabrication matrix across all materials coming in a later step."))
        self.fab_display = QTextEdit()
        self.fab_display.setReadOnly(True)
        self.fab_display.setPlaceholderText(
            "Fabrication compatibility will appear here after selecting a material.")
        fab_layout.addWidget(self.fab_display)

        right_tabs.addTab(fab_tab, qta.icon('fa5s.industry'), "Fabrication")

        splitter.addWidget(right_tabs)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        layout.addWidget(splitter)

    # ── Data loading ──────────────────────────────────────────────────

    def _load_data(self):
        try:
            from materials_engine.materials_db import MaterialsDB
            db = MaterialsDB()
            added = db.seed_if_empty()
            if added:
                self.status_label.setText(
                    f"Seeded {added} materials into knowledge base.")
        except Exception as e:
            self.status_label.setText(f"Materials DB error: {e}")

        self._populate_topic_tree()

    def _populate_topic_tree(self):
        from materials_engine.topic_tree import get_roots, get_children, TOPIC_TREE

        self.topic_tree.clear()
        self._tree_items = {}   # key -> QTreeWidgetItem

        def _type_icon(branch_type):
            if branch_type == "deep":       return qta.icon('fa5s.circle', color='#2E86AB')
            if branch_type == "monitoring": return qta.icon('fa5.circle', color='#6c757d')
            return qta.icon('fa5.circle', color='#f4a261')   # promotable

        def _add_node(parent_item, node):
            item = QTreeWidgetItem([node.label])
            item.setIcon(0, _type_icon(node.branch_type))
            item.setData(0, Qt.ItemDataRole.UserRole, node.key)
            if node.branch_type == "monitoring":
                item.setForeground(0, QColor("#6c757d"))
            elif node.branch_type == "promotable":
                item.setForeground(0, QColor("#f4a261"))
            if parent_item:
                parent_item.addChild(item)
            else:
                self.topic_tree.addTopLevelItem(item)
            self._tree_items[node.key] = item
            for child in get_children(node.key):
                _add_node(item, child)

        for root in get_roots():
            _add_node(None, root)

        self.topic_tree.expandAll()

    def _search(self):
        query = self.search_input.text().strip()
        if not query:
            return
        try:
            from materials_engine.materials_db import MaterialsDB
            results = MaterialsDB().search(query)
            if not results:
                self.status_label.setText(f"No materials found for '{query}'")
                return
            # Show results in card display
            lines = [f"**Search results for '{query}':**\n"]
            for m in results:
                lines.append(f"• **{m['name']}** ({m.get('material_class','')})")
            self.card_display.setPlainText("\n".join(lines))
            self.status_label.setText(f"{len(results)} materials found")
        except Exception as e:
            self.status_label.setText(f"Search error: {e}")

    # ── Topic tree selection ──────────────────────────────────────────

    def _on_topic_selected(self, item, column):
        topic_key = item.data(0, Qt.ItemDataRole.UserRole)
        if not topic_key:
            return

        from materials_engine.topic_tree import get_node
        from materials_engine.materials_db import MaterialsDB

        node = get_node(topic_key)
        db   = MaterialsDB()

        # Try to load a material matching this node
        materials = db.get_by_topic(topic_key)

        if materials:
            self._selected_material = materials[0]
            self._show_material(self._selected_material)
        else:
            # No material record yet — show node description
            self._selected_material = {
                "name":           node.label if node else topic_key,
                "material_class": topic_key,
                "topic_key":      topic_key,
                "properties":     {},
            }
            self.material_label.setText(node.label if node else topic_key)
            desc = node.description if node else ""
            self.card_display.setPlainText(
                f"{desc}\n\nNo knowledge card yet. "
                f"Click 'Generate AI Card' to create one.")
            self._update_fab_display({})

        self.gen_card_btn.setEnabled(True)
        self.compare_btn.setEnabled(bool(materials))
        self.verify_btn.setEnabled(False)

    def _show_material(self, material: dict):
        from ai_engine.knowledge_card_gen import format_card_markdown
        self.material_label.setText(material.get("name", ""))

        # If material has a stored card (properties + fabrication), show it
        props = material.get("properties") or {}
        fab   = material.get("fabrication_compat") or {}

        if props:
            # Build a simple card from stored data
            card = {
                "material_name":           material["name"],
                "material_class":          material.get("material_class", ""),
                "what_it_is":              "",
                "key_properties":          props,
                "fabrication_compatibility": fab,
                "frontier_developments":   [],
                "open_problems":           [],
                "limitations":             [],
                "key_paper_pmids":         [],
                "confidence":              "high" if material.get("human_verified") else "medium",
                "ai_generated":            material.get("ai_generated", False),
                "human_verified":          material.get("human_verified", False),
            }
            self.card_display.setPlainText(format_card_markdown(card))
            self._update_fab_display(fab)
        else:
            self.card_display.setPlainText(
                f"No knowledge card for {material['name']} yet.\n"
                "Click 'Generate AI Card' to create one.")

        self.verify_btn.setEnabled(
            material.get("ai_generated", False) and
            not material.get("human_verified", False))

    def _update_fab_display(self, fab: dict):
        if not fab:
            self.fab_display.setPlaceholderText(
                "No fabrication data yet. Generate an AI card first.")
            self.fab_display.clear()
            return
        lines = ["**Fabrication Compatibility:**\n"]
        for method, rating in fab.items():
            lines.append(f"• **{method}**: {rating}")
        self.fab_display.setPlainText("\n".join(lines))

    # ── AI card generation ────────────────────────────────────────────

    def _generate_card(self):
        if not self._selected_material:
            return
        try:
            from ai_engine.llm_client import get_client
            if not get_client().is_available():
                QMessageBox.information(
                    self, "No API Key",
                    "Add ANTHROPIC_API_KEY to your .env file to generate AI cards.")
                return
        except Exception:
            pass

        self.gen_card_btn.setEnabled(False)
        self.gen_card_btn.setText("  Generating...")
        self.progress_bar.setVisible(True)
        self.status_label.setText("Fetching papers and generating card...")

        self._card_worker = KnowledgeCardWorker(self._selected_material)
        self._card_worker.card_ready.connect(self._on_card_ready)
        self._card_worker.status.connect(self.status_label.setText)
        self._card_worker.error.connect(self._on_card_error)
        self._card_worker.start()

    def _on_card_ready(self, card: dict):
        from ai_engine.knowledge_card_gen import format_card_markdown
        from materials_engine.materials_db import MaterialsDB

        self.card_display.setPlainText(format_card_markdown(card))
        self._update_fab_display(card.get("fabrication_compatibility", {}))

        # Save back to DB
        try:
            if self._selected_material is not None:
                mid = self._selected_material.get("id")
                if mid:
                    MaterialsDB().save_knowledge_card(mid, card)
                    self._selected_material.update(card)
        except Exception as e:
            logger.warning(f"Could not save card: {e}")

        self.gen_card_btn.setText("  Generate AI Card")
        self.gen_card_btn.setEnabled(True)
        self.verify_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText("Knowledge card generated.")

    def _on_card_error(self, error: str):
        self.gen_card_btn.setText("  Generate AI Card")
        self.gen_card_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"Card error: {error}")
        QMessageBox.critical(self, "Card Generation Failed", error)

    def _mark_verified(self):
        mid = self._selected_material.get("id") if self._selected_material else None
        if not mid:
            return
        try:
            from materials_engine.materials_db import MaterialsDB
            MaterialsDB().mark_verified(mid)
            if self._selected_material is not None:
                self._selected_material["human_verified"] = True
            self.verify_btn.setEnabled(False)
            self.status_label.setText("Marked as verified.")
        except Exception as e:
            self.status_label.setText(f"Error: {e}")

    # ── Comparison ────────────────────────────────────────────────────

    def _add_to_compare(self):
        if not self._selected_material:
            return
        mid  = self._selected_material.get("id")
        name = self._selected_material.get("name", "")
        if mid and mid not in self._compare_ids:
            self._compare_ids.append(mid)
            self.compare_list.addItem(name)
            self.status_label.setText(f"Added {name} to comparison.")

    def _clear_compare(self):
        self._compare_ids.clear()
        self.compare_list.clear()
        self.compare_table.clear()
        self.compare_table.setRowCount(0)
        self.compare_table.setColumnCount(0)

    def _run_comparison(self):
        if len(self._compare_ids) < 2:
            QMessageBox.information(
                self, "Need more materials",
                "Add at least 2 materials to compare.")
            return

        try:
            from materials_engine.materials_db import MaterialsDB
            comparison = MaterialsDB().compare(self._compare_ids)

            if not comparison:
                self.status_label.setText("No comparable properties found.")
                return

            db2 = MaterialsDB()
            names = [m["name"] for mid in self._compare_ids
                     for m in [db2.get(mid)] if m is not None]

            self.compare_table.clear()
            self.compare_table.setColumnCount(len(names) + 1)
            self.compare_table.setHorizontalHeaderLabels(["Property"] + names)
            self.compare_table.setRowCount(len(comparison))

            for row, (prop, values) in enumerate(comparison.items()):
                self.compare_table.setItem(
                    row, 0, QTableWidgetItem(prop))
                for col, name in enumerate(names):
                    val = values.get(name, "—")
                    self.compare_table.setItem(
                        row, col + 1, QTableWidgetItem(str(val)))

            _ch = self.compare_table.horizontalHeader()
            if _ch:
                _ch.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
                _ch.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            self.status_label.setText(
                f"Comparing {len(names)} materials across {len(comparison)} properties.")

        except Exception as e:
            self.status_label.setText(f"Comparison error: {e}")


import logging
logger = logging.getLogger(__name__)