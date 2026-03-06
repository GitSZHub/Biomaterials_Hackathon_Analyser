"""
FindingsWidget — reusable collapsible panel for saving module findings.

Drop one into any tab with:
    self._findings = FindingsWidget("drug")
    layout.addWidget(self._findings)

Then call:
    self._findings.set_project_id(project_id)

The widget auto-loads existing findings on set_project_id() and auto-saves
on every keystroke with a 2-second debounce (plus an explicit Save button).
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QFrame,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
import qtawesome as qta


class FindingsWidget(QFrame):
    """
    Collapsible 'Findings' panel that persists free-text notes per module.

    Parameters
    ----------
    module : str
        Identifier stored in module_findings.module (e.g. "drug", "literature").
    placeholder : str
        Grey placeholder text shown in the empty text box.
    """

    def __init__(self, module: str,
                 placeholder: str = "Record key findings, strategies, and decisions here...",
                 parent=None):
        super().__init__(parent)
        self._module = module
        self._project_id: int = 1
        self._expanded = False

        self.setStyleSheet("""
            FindingsWidget {
                border: 1px solid #dee2e6;
                border-radius: 6px;
                background-color: #fffbf0;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 4, 6, 4)
        root.setSpacing(4)

        # ── Header row ────────────────────────────────────────────────
        header = QHBoxLayout()

        self._toggle_btn = QPushButton()
        self._toggle_btn.setFlat(True)
        self._toggle_btn.setFixedWidth(24)
        self._toggle_btn.clicked.connect(self._toggle)

        title = QLabel("Findings & Strategy Notes")
        title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        title.setStyleSheet("color: #856404;")

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("color: #6c757d; font-size: 9px;")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        self._save_btn = QPushButton(qta.icon('fa5s.save', color='#856404'), "")
        self._save_btn.setFlat(True)
        self._save_btn.setFixedWidth(24)
        self._save_btn.setToolTip("Save findings now")
        self._save_btn.clicked.connect(self._save)

        header.addWidget(self._toggle_btn)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self._status_lbl)
        header.addWidget(self._save_btn)
        root.addLayout(header)

        # ── Content (hidden by default) ───────────────────────────────
        self._content = QWidget()
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)

        self._text = QTextEdit()
        self._text.setPlaceholderText(placeholder)
        self._text.setMinimumHeight(100)
        self._text.setMaximumHeight(200)
        self._text.setFont(QFont("Consolas", 9))
        self._text.textChanged.connect(self._on_text_changed)
        content_layout.addWidget(self._text)

        root.addWidget(self._content)
        self._content.setVisible(False)

        # Debounce timer — saves 2 s after last keystroke
        self._debounce = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(2000)
        self._debounce.timeout.connect(self._save)

        self._update_toggle_icon()

    # ── Public API ────────────────────────────────────────────────────

    def set_project_id(self, project_id: int) -> None:
        self._project_id = project_id
        self._load()

    def get_text(self) -> str:
        return self._text.toPlainText().strip()

    # ── Private ───────────────────────────────────────────────────────

    def _toggle(self):
        self._expanded = not self._expanded
        self._content.setVisible(self._expanded)
        self._update_toggle_icon()

    def _update_toggle_icon(self):
        icon_name = 'fa5s.chevron-down' if self._expanded else 'fa5s.chevron-right'
        self._toggle_btn.setIcon(qta.icon(icon_name, color='#856404'))

    def _on_text_changed(self):
        self._status_lbl.setText("unsaved")
        self._debounce.start()

    def _load(self):
        try:
            from data_manager import crud
            rows = crud.get_findings(module=self._module, project_id=self._project_id)
            if rows:
                text = rows[0].get("findings", "")
                self._text.blockSignals(True)
                self._text.setPlainText(text)
                self._text.blockSignals(False)
                saved_at = (rows[0].get("saved_at") or "")[:16]
                self._status_lbl.setText(f"saved {saved_at}")
                if text:
                    self._expanded = True
                    self._content.setVisible(True)
                    self._update_toggle_icon()
        except Exception:
            pass

    def _save(self):
        self._debounce.stop()
        text = self._text.toPlainText().strip()
        try:
            from data_manager import crud
            crud.save_findings(self._module, text, project_id=self._project_id)
            self._status_lbl.setText("saved")
        except Exception as e:
            self._status_lbl.setText(f"save failed: {e}")
