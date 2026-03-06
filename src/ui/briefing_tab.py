"""
Briefing Generator Tab — Flagship Feature
==========================================
Claude synthesises all module data into a full Technical or Executive briefing,
generated section by section with live progress feedback.

Layout:
  Left panel  — Mode selector, section checklist, project snapshot, Generate button
  Right panel — Tabbed: Live Output | Prompt Preview | Export

Key design principles:
  - Prompts are VISIBLE and EDITABLE before generation (Option C architecture)
  - Sections generate sequentially with per-section progress bar
  - Export to Markdown, HTML, plain text via file dialog
  - Works with partial data — graceful degradation per module
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel, QPushButton,
    QComboBox, QCheckBox, QTextEdit, QPlainTextEdit, QProgressBar,
    QScrollArea, QFrame, QTabWidget, QFileDialog, QGroupBox,
    QButtonGroup, QRadioButton, QSizePolicy,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QMutex, QMutexLocker
from PyQt6.QtGui import QFont, QColor, QTextCursor
import qtawesome as qta

logger = logging.getLogger(__name__)

# ── Safe imports ───────────────────────────────────────────────────────────────

try:
    from briefing_engine import (
        ContextAssembler, BriefingContext, BriefingGenerator,
        TECHNICAL_SECTIONS, EXECUTIVE_SECTIONS,
    )
    _ENGINE_OK = True
except ImportError as e:
    logger.warning("briefing_engine not available: %s", e)
    _ENGINE_OK = False


# ── Worker thread ──────────────────────────────────────────────────────────────

class BriefingWorker(QThread):
    """Generates one section at a time; emits section_done after each."""
    section_done   = pyqtSignal(str, str)   # (section_key, markdown_text)
    all_done       = pyqtSignal(str)         # full assembled markdown
    error          = pyqtSignal(str, str)    # (section_key, error_message)
    progress       = pyqtSignal(int, int)    # (current, total)

    def __init__(self, context: BriefingContext, mode: str, section_keys: List[str]):
        super().__init__()
        self._ctx          = context
        self._mode         = mode
        self._section_keys = section_keys
        self._cancelled    = False
        self._mutex        = QMutex()

    def cancel(self):
        with QMutexLocker(self._mutex):
            self._cancelled = True

    def run(self):
        if not _ENGINE_OK:
            self.error.emit("__init__", "briefing_engine not available"); return
        try:
            gen = BriefingGenerator()
            sections_meta = {s.key: s for s in gen.get_sections(self._mode)}
            parts = [
                f"# {self._ctx.project_name or 'Project'} — "
                f"{'Technical Briefing' if self._mode == 'technical' else 'Executive Briefing'}\n"
                f"*Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n"
            ]
            total = len(self._section_keys)
            for i, key in enumerate(self._section_keys):
                with QMutexLocker(self._mutex):
                    if self._cancelled:
                        break
                self.progress.emit(i, total)
                section = sections_meta.get(key)
                if section is None:
                    continue
                try:
                    text = gen.generate_section(key, self._ctx, self._mode)
                    formatted = f"## {section.title}\n\n{text}\n"
                    parts.append(formatted)
                    self.section_done.emit(key, formatted)
                except Exception as e:
                    err_text = f"## {section.title}\n\n*[Generation error: {e}]*\n"
                    parts.append(err_text)
                    self.error.emit(key, str(e))
            self.progress.emit(total, total)
            self.all_done.emit("\n".join(parts))
        except Exception as e:
            self.error.emit("__global__", str(e))


# ── Context preview worker ─────────────────────────────────────────────────────

class ContextWorker(QThread):
    done = pyqtSignal(object)   # BriefingContext

    def __init__(self, swot=None, roadmap=None, dbtl=None):
        super().__init__()
        self._swot = swot; self._roadmap = roadmap; self._dbtl = dbtl

    def run(self):
        try:
            ctx = ContextAssembler().assemble(
                swot=self._swot, roadmap=self._roadmap, dbtl_tracker=self._dbtl
            )
            self.done.emit(ctx)
        except Exception as e:
            from briefing_engine.context_assembler import BriefingContext
            ctx = BriefingContext(project_name="Error assembling context")
            ctx.user_context = str(e)
            self.done.emit(ctx)


# ── Main tab ───────────────────────────────────────────────────────────────────

class BriefingTab(QWidget):
    """Flagship briefing generator tab."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._context: Optional[BriefingContext] = None
        self._full_markdown: str = ""
        self._worker: Optional[BriefingWorker] = None
        self._section_checkboxes: dict = {}
        self._init_ui()

    # ── Public API (called by main window or other tabs) ───────────────────────

    def set_live_objects(self, swot=None, roadmap=None, dbtl=None):
        """Pass live in-memory objects from other tabs for richer context."""
        self._swot_obj    = swot
        self._roadmap_obj = roadmap
        self._dbtl_obj    = dbtl

    # ── UI construction ────────────────────────────────────────────────────────

    def _init_ui(self):
        self._swot_obj = self._roadmap_obj = self._dbtl_obj = None

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([320, 900])
        root.addWidget(splitter)

    # ── Left panel ─────────────────────────────────────────────────────────────

    def _build_left_panel(self) -> QWidget:
        panel = QFrame()
        panel.setMaximumWidth(340)
        panel.setStyleSheet("QFrame { background:#f8f9fa; border-right:1px solid #dee2e6; }")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Title
        title = QLabel("Briefing Generator")
        title.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        title.setStyleSheet("color:#2E86AB;")
        layout.addWidget(title)

        sub = QLabel("Claude synthesises all modules into a full project briefing.")
        sub.setWordWrap(True)
        sub.setStyleSheet("color:#6c757d; font-size:10px;")
        layout.addWidget(sub)

        # Mode selector
        mode_box = QGroupBox("Briefing Mode")
        mode_layout = QVBoxLayout(mode_box)
        self._mode_group = QButtonGroup()
        self._radio_tech = QRadioButton("Technical — for R&D teammates")
        self._radio_exec = QRadioButton("Executive — for investors / partners")
        self._radio_tech.setChecked(True)
        self._mode_group.addButton(self._radio_tech, 0)
        self._mode_group.addButton(self._radio_exec, 1)
        self._radio_tech.toggled.connect(self._on_mode_changed)
        mode_layout.addWidget(self._radio_tech)
        mode_layout.addWidget(self._radio_exec)
        layout.addWidget(mode_box)

        # Sections checklist
        sections_box = QGroupBox("Sections to Include")
        sections_scroll = QScrollArea()
        sections_scroll.setWidgetResizable(True)
        sections_scroll.setMaximumHeight(260)
        sections_inner = QWidget()
        self._sections_layout = QVBoxLayout(sections_inner)
        self._sections_layout.setSpacing(2)
        sections_scroll.setWidget(sections_inner)
        sections_box_layout = QVBoxLayout(sections_box)
        sections_box_layout.addWidget(sections_scroll)

        sel_bar = QHBoxLayout()
        all_btn  = QPushButton("All"); all_btn.setFixedWidth(50)
        none_btn = QPushButton("None"); none_btn.setFixedWidth(50)
        all_btn.clicked.connect(lambda: self._set_all_sections(True))
        none_btn.clicked.connect(lambda: self._set_all_sections(False))
        sel_bar.addWidget(all_btn); sel_bar.addWidget(none_btn); sel_bar.addStretch()
        sections_box_layout.addLayout(sel_bar)
        layout.addWidget(sections_box)
        self._rebuild_section_checkboxes()

        # Project snapshot
        snap_box = QGroupBox("Project Snapshot")
        snap_layout = QVBoxLayout(snap_box)
        self._snap_label = QLabel("Click 'Refresh Context' to load project data.")
        self._snap_label.setWordWrap(True)
        self._snap_label.setStyleSheet("font-size:10px; color:#495057;")
        snap_layout.addWidget(self._snap_label)

        refresh_btn = QPushButton(qta.icon('fa.refresh'), " Refresh Context")
        refresh_btn.clicked.connect(self._refresh_context)
        snap_layout.addWidget(refresh_btn)
        layout.addWidget(snap_box)

        layout.addStretch()

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress.setTextVisible(True)
        layout.addWidget(self._progress)

        # Status label
        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet("font-size:10px; color:#495057;")
        layout.addWidget(self._status_label)

        # Generate / Cancel buttons
        self._gen_btn = QPushButton(qta.icon('fa.magic'), "  Generate Briefing")
        self._gen_btn.setStyleSheet(self._primary_btn_style())
        self._gen_btn.setMinimumHeight(36)
        self._gen_btn.clicked.connect(self._start_generation)
        layout.addWidget(self._gen_btn)

        self._cancel_btn = QPushButton(qta.icon('fa.stop'), " Cancel")
        self._cancel_btn.setVisible(False)
        self._cancel_btn.clicked.connect(self._cancel_generation)
        layout.addWidget(self._cancel_btn)

        return panel

    # ── Right panel ────────────────────────────────────────────────────────────

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)

        tabs = QTabWidget()

        # Tab 1: Live output
        output_w = QWidget()
        output_layout = QVBoxLayout(output_w)
        self._output = QTextEdit()
        self._output.setReadOnly(True)
        self._output.setFont(QFont("Consolas", 10))
        self._output.setPlaceholderText(
            "Briefing output will appear here, section by section, as Claude generates it.\n\n"
            "1. Click 'Refresh Context' to load project data.\n"
            "2. Choose Technical or Executive mode.\n"
            "3. Select sections to include.\n"
            "4. Click 'Generate Briefing'."
        )
        output_layout.addWidget(self._output)
        tabs.addTab(output_w, qta.icon('fa.file-text-o'), "Live Output")

        # Tab 2: Prompt preview (visible/editable)
        prompt_w = QWidget()
        prompt_layout = QVBoxLayout(prompt_w)
        prompt_note = QLabel(
            "The context below will be sent to Claude. You can edit it before generating. "
            "Changes here only affect this generation run."
        )
        prompt_note.setWordWrap(True)
        prompt_note.setStyleSheet("color:#495057; font-size:10px; padding:4px;")
        prompt_layout.addWidget(prompt_note)
        self._prompt_edit = QPlainTextEdit()
        self._prompt_edit.setFont(QFont("Consolas", 9))
        self._prompt_edit.setPlaceholderText("Context will appear here after 'Refresh Context'.")
        prompt_layout.addWidget(self._prompt_edit)
        regen_from_prompt_btn = QPushButton(qta.icon('fa.magic'), " Generate with Edited Context")
        regen_from_prompt_btn.clicked.connect(self._generate_with_edited_context)
        prompt_layout.addWidget(regen_from_prompt_btn)
        tabs.addTab(prompt_w, qta.icon('fa.edit'), "Context / Prompt")

        # Tab 3: Export
        export_w = QWidget()
        export_layout = QVBoxLayout(export_w)
        export_layout.addWidget(QLabel("Export the generated briefing:"))
        export_layout.addSpacing(8)

        for label, icon, fn in [
            ("Export as Markdown (.md)",  'fa.file-text-o', self._export_markdown),
            ("Export as HTML (.html)",    'fa.file-code-o', self._export_html),
            ("Export as Plain Text (.txt)",'fa.file-o',     self._export_text),
        ]:
            btn = QPushButton(qta.icon(icon), f"  {label}")
            btn.setStyleSheet(self._secondary_btn_style())
            btn.clicked.connect(fn)
            export_layout.addWidget(btn)

        export_layout.addStretch()
        copy_btn = QPushButton(qta.icon('fa.copy'), "  Copy all to clipboard")
        copy_btn.clicked.connect(self._copy_to_clipboard)
        export_layout.addWidget(copy_btn)
        tabs.addTab(export_w, qta.icon('fa.download'), "Export")

        layout.addWidget(tabs)
        return panel

    # ── Section checklist management ───────────────────────────────────────────

    def _rebuild_section_checkboxes(self):
        # Clear existing
        for i in reversed(range(self._sections_layout.count())):
            item = self._sections_layout.itemAt(i)
            if item and item.widget():
                item.widget().deleteLater()
        self._section_checkboxes.clear()

        if not _ENGINE_OK:
            return

        mode = "technical" if self._radio_tech.isChecked() else "executive"
        sections = TECHNICAL_SECTIONS if mode == "technical" else EXECUTIVE_SECTIONS

        for section in sections:
            chk = QCheckBox(section.title)
            chk.setChecked(section.default_on)
            chk.setToolTip(section.description)
            chk.setStyleSheet("font-size:10px;")
            self._section_checkboxes[section.key] = chk
            self._sections_layout.addWidget(chk)

    def _on_mode_changed(self):
        self._rebuild_section_checkboxes()

    def _set_all_sections(self, checked: bool):
        for chk in self._section_checkboxes.values():
            chk.setChecked(checked)

    def _selected_section_keys(self) -> List[str]:
        return [key for key, chk in self._section_checkboxes.items() if chk.isChecked()]

    # ── Context management ─────────────────────────────────────────────────────

    def _refresh_context(self):
        if not _ENGINE_OK:
            self._snap_label.setText("briefing_engine not available.")
            return
        self._snap_label.setText("Loading...")
        worker = ContextWorker(
            swot=self._swot_obj,
            roadmap=self._roadmap_obj,
            dbtl=self._dbtl_obj,
        )
        worker.done.connect(self._on_context_ready)
        self._ctx_worker = worker
        worker.start()

    def _on_context_ready(self, ctx: BriefingContext):
        self._context = ctx
        lines = []
        if ctx.project_name:
            lines.append(f"Project: {ctx.project_name}")
        if ctx.project_tissue:
            lines.append(f"Tissue: {ctx.project_tissue}")
        if ctx.paper_count:
            lines.append(f"Papers: {ctx.paper_count}")
        if ctx.materials_named:
            lines.append(f"Materials: {', '.join(ctx.materials_named[:3])}")
        if ctx.reg_scenario:
            lines.append(f"Regulatory: Scenario {ctx.reg_scenario} | {ctx.reg_fda_class}")
        if ctx.market_name:
            lines.append(f"Market: {ctx.market_name} (${ctx.market_size_2024}B)")
        if ctx.dbtl_iterations:
            lines.append(f"DBTL iterations: {ctx.dbtl_iterations}")
        self._snap_label.setText("\n".join(lines) if lines else "No project data found. Check data_manager.")

        # Populate prompt preview
        self._prompt_edit.setPlainText(ctx.to_full_context())

    # ── Generation ─────────────────────────────────────────────────────────────

    def _start_generation(self):
        if not _ENGINE_OK:
            self._status_label.setText("briefing_engine not available.")
            return
        if self._context is None:
            self._refresh_context()
            self._status_label.setText("Context loading — click Generate again in a moment.")
            return

        keys = self._selected_section_keys()
        if not keys:
            self._status_label.setText("Select at least one section.")
            return

        mode = "technical" if self._radio_tech.isChecked() else "executive"

        # Apply any user edits to the context
        edited_text = self._prompt_edit.toPlainText()
        self._context.user_context = edited_text

        # Clear output
        self._output.clear()
        self._full_markdown = ""

        # UI state
        self._gen_btn.setEnabled(False)
        self._cancel_btn.setVisible(True)
        self._progress.setVisible(True)
        self._progress.setRange(0, len(keys))
        self._progress.setValue(0)
        self._status_label.setText(f"Generating {len(keys)} sections...")

        self._worker = BriefingWorker(self._context, mode, keys)
        self._worker.section_done.connect(self._on_section_done)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.error.connect(self._on_section_error)
        self._worker.progress.connect(self._on_progress)
        self._worker.start()

    def _generate_with_edited_context(self):
        """Generate using the text in the prompt edit pane as the full context override."""
        if self._context is None:
            self._context = BriefingContext(project_name="Manual context")
        self._context.user_context = self._prompt_edit.toPlainText()
        self._start_generation()

    def _cancel_generation(self):
        if self._worker:
            self._worker.cancel()
        self._status_label.setText("Cancelling...")

    def _on_section_done(self, key: str, text: str):
        # Render Markdown as HTML approximation in QTextEdit
        self._output.moveCursor(QTextCursor.MoveOperation.End)
        self._output.insertPlainText(text + "\n")
        self._output.moveCursor(QTextCursor.MoveOperation.End)
        self._full_markdown += text + "\n"

    def _on_all_done(self, full_md: str):
        self._full_markdown = full_md
        self._gen_btn.setEnabled(True)
        self._cancel_btn.setVisible(False)
        self._progress.setVisible(False)
        self._status_label.setText("Generation complete.")

    def _on_section_error(self, key: str, msg: str):
        self._output.moveCursor(QTextCursor.MoveOperation.End)
        self._output.insertPlainText(f"\n[ERROR in {key}]: {msg}\n\n")
        if key == "__global__":
            self._gen_btn.setEnabled(True)
            self._cancel_btn.setVisible(False)
            self._progress.setVisible(False)
            self._status_label.setText(f"Fatal error: {msg}")

    def _on_progress(self, current: int, total: int):
        self._progress.setValue(current)
        if current < total:
            self._status_label.setText(f"Generating section {current + 1} of {total}...")

    # ── Export ─────────────────────────────────────────────────────────────────

    def _export_markdown(self):
        self._save_file("Markdown Files (*.md)", ".md", self._full_markdown)

    def _export_html(self):
        html = self._markdown_to_html(self._full_markdown)
        self._save_file("HTML Files (*.html)", ".html", html)

    def _export_text(self):
        import re
        plain = re.sub(r"#+\s", "", self._full_markdown)
        plain = re.sub(r"\*\*(.+?)\*\*", r"\1", plain)
        plain = re.sub(r"\*(.+?)\*", r"\1", plain)
        self._save_file("Text Files (*.txt)", ".txt", plain)

    def _save_file(self, filter_str: str, ext: str, content: str):
        if not self._full_markdown:
            self._status_label.setText("Nothing to export — generate a briefing first.")
            return
        project = (self._context.project_name if self._context else "briefing").replace(" ", "_")
        default_name = f"{project}_briefing{ext}"
        path, _ = QFileDialog.getSaveFileName(self, "Save Briefing", default_name, filter_str)
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self._status_label.setText(f"Saved to {os.path.basename(path)}")

    def _copy_to_clipboard(self):
        from PyQt6.QtWidgets import QApplication
        if self._full_markdown:
            QApplication.clipboard().setText(self._full_markdown)
            self._status_label.setText("Copied to clipboard.")

    @staticmethod
    def _markdown_to_html(md: str) -> str:
        """Minimal Markdown -> HTML conversion (no external deps)."""
        import re
        lines = md.split("\n")
        html_lines = ["<html><body style='font-family:Arial,sans-serif;max-width:900px;margin:auto;padding:20px'>"]
        for line in lines:
            if line.startswith("# "):
                html_lines.append(f"<h1>{line[2:]}</h1>")
            elif line.startswith("## "):
                html_lines.append(f"<h2 style='color:#2E86AB;border-bottom:1px solid #dee2e6'>{line[3:]}</h2>")
            elif line.startswith("### "):
                html_lines.append(f"<h3>{line[4:]}</h3>")
            elif line.startswith("- ") or line.startswith("* "):
                html_lines.append(f"<li>{line[2:]}</li>")
            elif line.strip() == "":
                html_lines.append("<br>")
            else:
                # Bold and italic
                line = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line)
                line = re.sub(r"\*(.+?)\*", r"<i>\1</i>", line)
                html_lines.append(f"<p>{line}</p>")
        html_lines.append("</body></html>")
        return "\n".join(html_lines)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _primary_btn_style() -> str:
        return """
            QPushButton {
                background-color: #2E86AB; color: white;
                border: none; border-radius: 4px; padding: 8px 16px; font-weight: bold; font-size: 12px;
            }
            QPushButton:hover { background-color: #1d6e8f; }
            QPushButton:disabled { background-color: #adb5bd; }
        """

    @staticmethod
    def _secondary_btn_style() -> str:
        return """
            QPushButton {
                background-color: #f8f9fa; color: #212529;
                border: 1px solid #dee2e6; border-radius: 4px; padding: 6px 12px;
                text-align: left;
            }
            QPushButton:hover { background-color: #e9ecef; }
        """
