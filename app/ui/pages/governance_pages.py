"""Operational pages for SDS reminder, quality, knowledge and method records."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from app.modules.governance.service import GovernanceService
from app.ui.base_page import BasePage
from app.ui.theme import ThemeManager


class _ControlledRecordDialog(QDialog):
    def __init__(self, title: str, fields: tuple[tuple[str, str, str], ...], parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self._widgets = {}
        form = QFormLayout(self)
        for key, label, kind in fields:
            widget = QComboBox() if kind == "choice" else QTextEdit() if kind == "text" else QLineEdit()
            if kind == "choice":
                widget.addItems(
                    [
                        "CAPA",
                        "Internal Audit",
                        "Risk Register",
                        "Management Review",
                        "Competency",
                        "Training",
                        "Document Control",
                    ]
                )
            if kind == "text":
                widget.setFixedHeight(80)
            self._widgets[key] = widget
            form.addRow(label, widget)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def value(self, key: str) -> str:
        widget = self._widgets[key]
        if isinstance(widget, QComboBox):
            return widget.currentText().strip()
        if isinstance(widget, QTextEdit):
            return widget.toPlainText().strip()
        return widget.text().strip()


class _ControlledDocumentDialog(QDialog):
    """Collect document-control metadata alongside the uploaded source file."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Upload Controlled Document")
        self.resize(520, 270)
        self.source_path = ""
        form = QFormLayout(self)
        self.document_type = QComboBox()
        self.document_type.addItems(["Standard", "Procedure"])
        self.document_number = QLineEdit()
        self.title = QLineEdit()
        self.revision = QLineEdit()
        self.status = QComboBox()
        self.status.addItems(["Draft", "Approved", "Obsolete"])
        self.file_button = QPushButton("Choose File")
        self.file_label = QLineEdit("No file selected")
        self.file_label.setReadOnly(True)
        self.file_button.clicked.connect(self._choose_file)
        form.addRow("Document type *", self.document_type)
        form.addRow("Document number", self.document_number)
        form.addRow("Title *", self.title)
        form.addRow("Revision", self.revision)
        form.addRow("Status", self.status)
        form.addRow("File *", self.file_button)
        form.addRow("Selected file", self.file_label)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _choose_file(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Select Standard or Procedure", "",
            "Documents (*.pdf *.doc *.docx *.xls *.xlsx);;All Files (*.*)",
        )
        if filename:
            self.source_path = filename
            self.file_label.setText(Path(filename).name)


class _TablePage(BasePage):
    """Shared restrained table treatment for controlled-record screens."""

    def _make_table(self, headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setObjectName("ControlledTable")
        table.setHorizontalHeaderLabels(headers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setShowGrid(False)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        return table

    def _apply_controlled_theme(self, theme):
        c = theme.color
        self.setStyleSheet(f"""
QPushButton#ControlledAction {{ background: {c.primary}; color: white; border: none; border-radius: 7px; padding: 0 12px; font-weight: 600; }}
QPushButton#ControlledAction:hover {{ background: {c.primary_hover}; }}
QTableWidget#ControlledTable {{ background: {c.card}; border: 1px solid {c.border}; border-radius: 10px; color: {c.text}; }}
QTableWidget#ControlledTable::item {{ border-bottom: 1px solid {c.divider}; padding: 6px 8px; }}
QTableWidget#ControlledTable::item:selected {{ background: {c.primary}; color: white; }}
QHeaderView::section {{ background: {c.window}; color: {c.text_secondary}; border: none; border-bottom: 1px solid {c.border}; padding: 9px 8px; font-size: 10px; font-weight: 700; }}
QFrame#RecordDetail {{ background: {c.card}; border: 1px solid {c.border}; border-radius: 10px; }}
QLabel#RecordDetailText {{ color: {c.text_secondary}; font-size: 11px; }}
""")


class ReminderPage(_TablePage):
    def __init__(self):
        super().__init__(
            "Reminder Console",
            "SDS-controlled calibration due-date notices and escalations.",
        )
        self.service = GovernanceService()
        self.generate_button = QPushButton("Generate Reminders")
        self.resolve_button = QPushButton("Resolve Selected")
        self.refresh_button = QPushButton("Refresh")
        for button in (self.generate_button, self.resolve_button):
            button.setObjectName("ControlledAction")
        self.add_toolbar_widget(self.generate_button)
        self.add_toolbar_widget(self.resolve_button)
        self.add_toolbar_stretch()
        self.add_toolbar_widget(self.refresh_button)
        self.table = self._make_table(
            ["NOTICE", "DETAIL", "DUE", "TRIGGER", "STATUS", "LEAD DAYS", "ESCALATED"]
        )
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.content_layout.addWidget(self.table, 1)
        self.generate_button.clicked.connect(self._generate)
        self.resolve_button.clicked.connect(self._resolve)
        self.refresh_button.clicked.connect(self.refresh)
        ThemeManager.register(self._apply_controlled_theme)
        self._apply_controlled_theme(ThemeManager.current())
        self.refresh()

    def refresh(self):
        rows = self.service.repository.reminders()
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            reminder_id, title, detail, due, trigger, status, lead_days, escalated = row
            for column, value in enumerate(
                (title, detail or "—", due, trigger, status, str(lead_days or "—"), "Yes" if escalated else "No")
            ):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, reminder_id)
                item.setTextAlignment(Qt.AlignVCenter | (Qt.AlignCenter if column >= 2 else Qt.AlignLeft))
                self.table.setItem(row_index, column, item)
            self.table.setRowHeight(row_index, 38)

    def _generate(self):
        count = self.service.generate_reminders()
        self.refresh()
        QMessageBox.information(self, "Reminders", f"Generated {count} new reminder(s).")

    def _resolve(self):
        items = self.table.selectedItems()
        if not items:
            QMessageBox.information(self, "Reminders", "Select a reminder first.")
            return
        self.service.repository.resolve_reminder(int(items[0].data(Qt.UserRole)))
        self.refresh()

    def closeEvent(self, event):
        ThemeManager.unregister(self._apply_controlled_theme)
        super().closeEvent(event)


class QualityPage(_TablePage):
    def __init__(self):
        super().__init__(
            "ISO/IEC 17025 Quality Management",
            "Controlled CAPA, audit, risk, competency and document-control records.",
        )
        self.service = GovernanceService()
        self.new_button = QPushButton("New Quality Record")
        self.close_button = QPushButton("Close Selected")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search quality records")
        self.refresh_button = QPushButton("Refresh")
        for button in (self.new_button, self.close_button):
            button.setObjectName("ControlledAction")
        self.add_toolbar_widget(self.new_button)
        self.add_toolbar_widget(self.close_button)
        self.add_toolbar_stretch()
        self.add_toolbar_widget(self.search)
        self.add_toolbar_widget(self.refresh_button)
        self.table = self._make_table(
            ["TYPE", "REFERENCE", "TITLE", "OWNER", "DUE", "STATUS"]
        )
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.content_layout.addWidget(self.table, 1)
        self.new_button.clicked.connect(self._new_record)
        self.close_button.clicked.connect(self._close_record)
        self.search.textChanged.connect(self.refresh)
        self.refresh_button.clicked.connect(self.refresh)
        ThemeManager.register(self._apply_controlled_theme)
        self._apply_controlled_theme(ThemeManager.current())
        self.refresh()

    def refresh(self):
        rows = self.service.repository.quality_records(self.search.text())
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            record_id, record_type, reference, title, owner, due, status = row
            for column, value in enumerate((record_type, reference or "—", title, owner or "—", due or "—", status)):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, record_id)
                item.setTextAlignment(Qt.AlignVCenter | (Qt.AlignCenter if column in (0, 4, 5) else Qt.AlignLeft))
                self.table.setItem(row_index, column, item)
            self.table.setRowHeight(row_index, 38)

    def _new_record(self):
        dialog = _ControlledRecordDialog(
            "New Quality Record",
            (
                ("type", "Record type *", "choice"),
                ("reference", "Reference number", "line"),
                ("title", "Title *", "line"),
                ("owner", "Owner", "line"),
                ("due", "Due date (YYYY-MM-DD)", "line"),
                ("description", "Description", "text"),
            ),
            self,
        )
        if not dialog.exec():
            return
        try:
            self.service.add_quality_record(
                dialog.value("type"),
                dialog.value("reference"),
                dialog.value("title"),
                dialog.value("description"),
                dialog.value("owner"),
                dialog.value("due"),
            )
            self.refresh()
        except (ValueError, Exception) as error:
            QMessageBox.warning(self, "Quality Record", str(error))

    def _close_record(self):
        items = self.table.selectedItems()
        if not items:
            QMessageBox.information(self, "Quality Record", "Select a record first.")
            return
        self.service.repository.close_quality_record(int(items[0].data(Qt.UserRole)))
        self.refresh()

    def closeEvent(self, event):
        ThemeManager.unregister(self._apply_controlled_theme)
        super().closeEvent(event)


class KnowledgeBasePage(_TablePage):
    CATEGORIES = (
        "All categories",
        "Meter Types",
        "Calibration Methods",
        "Primary Standards",
        "Procedures",
        "Standards Bodies",
        "Environmental Models",
        "Density Models",
        "Buoyancy Models",
        "Flow Units",
        "Laboratory Terminology",
    )

    def __init__(self):
        super().__init__(
            "Laboratory Knowledge Base",
            "Laboratory-authored, versioned reference data. The system never infers entries.",
        )
        self.service = GovernanceService()
        self.new_button = QPushButton("New Controlled Entry")
        self.new_button.setObjectName("ControlledAction")
        self.category = QComboBox()
        self.category.addItems(self.CATEGORIES)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search controlled entries")
        self.refresh_button = QPushButton("Refresh")
        self.add_toolbar_widget(self.new_button)
        self.add_toolbar_stretch()
        self.add_toolbar_widget(self.category)
        self.add_toolbar_widget(self.search)
        self.add_toolbar_widget(self.refresh_button)
        self.table = self._make_table(
            ["CATEGORY", "KEY", "TITLE", "VERSION", "STATUS", "APPROVER"]
        )
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.content_layout.addWidget(self.table, 1)
        self.new_button.clicked.connect(self._new_entry)
        self.category.currentIndexChanged.connect(self.refresh)
        self.search.textChanged.connect(self.refresh)
        self.refresh_button.clicked.connect(self.refresh)
        ThemeManager.register(self._apply_controlled_theme)
        self._apply_controlled_theme(ThemeManager.current())
        self.refresh()

    def refresh(self):
        category = self.category.currentText()
        rows = self.service.repository.knowledge_entries(
            "" if category == "All categories" else category,
            self.search.text(),
        )
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            entry_id, entry_category, entry_key, title, version, status, approver = row
            for column, value in enumerate((entry_category, entry_key, title, version, status, approver or "—")):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, entry_id)
                item.setTextAlignment(Qt.AlignVCenter | (Qt.AlignCenter if column in (3, 4) else Qt.AlignLeft))
                self.table.setItem(row_index, column, item)
            self.table.setRowHeight(row_index, 38)

    def _new_entry(self):
        dialog = _ControlledRecordDialog(
            "New Knowledge Base Entry",
            (
                ("category", "Category *", "line"),
                ("key", "Controlled key *", "line"),
                ("title", "Title *", "line"),
                ("version", "Version", "line"),
                ("content", "Controlled content", "text"),
            ),
            self,
        )
        if not dialog.exec():
            return
        try:
            self.service.add_knowledge_entry(
                dialog.value("category"),
                dialog.value("key"),
                dialog.value("title"),
                dialog.value("content"),
                dialog.value("version") or "1.0",
            )
            self.refresh()
        except (ValueError, Exception) as error:
            QMessageBox.warning(self, "Knowledge Base", str(error))

    def closeEvent(self, event):
        ThemeManager.unregister(self._apply_controlled_theme)
        super().closeEvent(event)


class MethodConfigurationPage(_TablePage):
    """Library of uploaded controlled standards and procedures."""

    def __init__(self):
        super().__init__(
            "Standards & Procedures",
            "Controlled standards and procedures stored as uploaded source documents.",
        )
        self.service = GovernanceService()
        self.new_button = QPushButton("Upload Document")
        self.new_button.setObjectName("ControlledAction")
        self.open_button = QPushButton("Open Selected")
        self.refresh_button = QPushButton("Refresh")
        self.add_toolbar_widget(self.new_button)
        self.add_toolbar_widget(self.open_button)
        self.add_toolbar_stretch()
        self.add_toolbar_widget(self.refresh_button)
        self.table = self._make_table(
            ["TYPE", "NUMBER", "TITLE", "REVISION", "FILE", "STATUS", "EFFECTIVE"]
        )
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.content_layout.addWidget(self.table, 1)
        self.new_button.clicked.connect(self._upload_document)
        self.open_button.clicked.connect(self._open_selected)
        self.refresh_button.clicked.connect(self.refresh)
        ThemeManager.register(self._apply_controlled_theme)
        self._apply_controlled_theme(ThemeManager.current())
        self.refresh()

    def _legacy_method_refresh(self):
        rows = self.service.repository.methods()
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            method_id, meter, method, revision, procedure, status, effective, active = row
            for column, value in enumerate(
                (meter, method, revision, procedure or "—", status, effective or "—", "Yes" if active else "No")
            ):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, method_id)
                item.setTextAlignment(Qt.AlignVCenter | (Qt.AlignCenter if column >= 2 else Qt.AlignLeft))
                self.table.setItem(row_index, column, item)
            self.table.setRowHeight(row_index, 38)

    def _legacy_new_method(self):
        dialog = _ControlledRecordDialog(
            "New Calibration Method",
            (
                ("meter", "Meter type *", "line"),
                ("method", "Method name *", "line"),
                ("revision", "Revision *", "line"),
                ("procedure", "Procedure reference", "line"),
                ("description", "Description", "text"),
            ),
            self,
        )
        if not dialog.exec():
            return
        try:
            self.service.add_method(
                dialog.value("meter"),
                dialog.value("method"),
                dialog.value("revision"),
                dialog.value("procedure"),
                dialog.value("description"),
            )
            self.refresh()
        except (ValueError, Exception) as error:
            QMessageBox.warning(self, "Calibration Method", str(error))

    def refresh(self):
        rows = self.service.repository.controlled_documents()
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            document_id, document_type, number, title, revision, filename, status, effective, file_path = row
            values = (document_type, number or "-", title, revision or "-", filename, status, effective or "-")
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, document_id)
                item.setData(Qt.UserRole + 1, file_path)
                item.setTextAlignment(Qt.AlignVCenter | (Qt.AlignCenter if column >= 3 else Qt.AlignLeft))
                self.table.setItem(row_index, column, item)
            self.table.setRowHeight(row_index, 38)

    def _upload_document(self):
        dialog = _ControlledDocumentDialog(self)
        if not dialog.exec():
            return
        try:
            self.service.add_controlled_document(
                dialog.document_type.currentText(), dialog.document_number.text(),
                dialog.title.text(), dialog.revision.text(), dialog.source_path,
                dialog.status.currentText(),
            )
            self.refresh()
        except (ValueError, Exception) as error:
            QMessageBox.warning(self, "Controlled Document", str(error))

    def _open_selected(self):
        items = self.table.selectedItems()
        if not items:
            QMessageBox.information(self, "Controlled Document", "Select a document first.")
            return
        path = Path(str(items[0].data(Qt.UserRole + 1)))
        if not path.is_file():
            QMessageBox.warning(self, "Controlled Document", "The uploaded file is no longer available.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    def closeEvent(self, event):
        ThemeManager.unregister(self._apply_controlled_theme)
        super().closeEvent(event)
