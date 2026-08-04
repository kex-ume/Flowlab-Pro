"""Customer and project lifecycle workspace."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.modules.projects.models import Customer, Deliverable, Project
from app.modules.projects.service import ProjectsService
from app.ui.base_page import BasePage
from app.ui.theme import ThemeManager


class _CustomerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Customer")
        form = QFormLayout(self)
        self.name = QLineEdit()
        self.reference = QLineEdit()
        self.contact = QLineEdit()
        self.email = QLineEdit()
        self.phone = QLineEdit()
        self.address = QLineEdit()
        form.addRow("Customer name *", self.name)
        form.addRow("Account reference", self.reference)
        form.addRow("Primary contact", self.contact)
        form.addRow("Email", self.email)
        form.addRow("Phone", self.phone)
        form.addRow("Site address", self.address)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def customer(self) -> Customer:
        return Customer(
            customer_name=self.name.text().strip(),
            account_reference=self.reference.text().strip(),
            primary_contact=self.contact.text().strip(),
            email=self.email.text().strip(),
            phone=self.phone.text().strip(),
            site_address=self.address.text().strip(),
        )


class _ProjectDialog(QDialog):
    def __init__(self, customers, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Project")
        form = QFormLayout(self)
        self.customer = QComboBox()
        for customer_id, name, *_ in customers:
            self.customer.addItem(name, customer_id)
        self.name = QLineEdit()
        self.description = QLineEdit()
        self.target_date = QLineEdit()
        self.target_date.setPlaceholderText("YYYY-MM-DD")
        self.deliverables = QLineEdit()
        form.addRow("Customer *", self.customer)
        form.addRow("Project name *", self.name)
        form.addRow("Description", self.description)
        form.addRow("Target completion", self.target_date)
        form.addRow("Deliverable summary", self.deliverables)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def project(self) -> Project:
        return Project(
            customer_id=int(self.customer.currentData()),
            project_name=self.name.text().strip(),
            description=self.description.text().strip(),
            target_completion_date=self.target_date.text().strip(),
            deliverable_summary=self.deliverables.text().strip(),
        )


class ProjectsPage(BasePage):
    """Operational project register with controlled SDS status transitions."""

    def __init__(self):
        super().__init__(
            "Projects",
            "Customer engagements, grouped calibration jobs and deliverables.",
        )
        self.service = ProjectsService()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        self.new_customer_button = QPushButton("New Customer")
        self.new_project_button = QPushButton("New Project")
        self.advance_button = QPushButton("Advance Status")
        self.add_deliverable_button = QPushButton("Add Deliverable")
        self.refresh_button = QPushButton("Refresh")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search project number, project or customer")
        self.search.setClearButtonEnabled(True)

        for button in (
            self.new_customer_button,
            self.new_project_button,
            self.advance_button,
            self.add_deliverable_button,
        ):
            button.setObjectName("ProjectAction")

        self.add_toolbar_widget(self.new_customer_button)
        self.add_toolbar_widget(self.new_project_button)
        self.add_toolbar_widget(self.advance_button)
        self.add_toolbar_widget(self.add_deliverable_button)
        self.add_toolbar_stretch()
        self.add_toolbar_widget(self.search)
        self.add_toolbar_widget(self.refresh_button)

        self.projects_table = QTableWidget(0, 8)
        self.projects_table.setObjectName("ProjectsTable")
        self.projects_table.setHorizontalHeaderLabels(
            [
                "PROJECT",
                "NAME",
                "CUSTOMER",
                "STATUS",
                "TARGET",
                "JOBS",
                "DELIVERABLES",
                "DETAILS",
            ]
        )
        self.projects_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.projects_table.setSelectionMode(QTableWidget.SingleSelection)
        self.projects_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.projects_table.setAlternatingRowColors(False)
        self.projects_table.verticalHeader().setVisible(False)
        self.projects_table.setShowGrid(False)
        header = self.projects_table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        for column in (0, 2, 3, 4, 5, 6, 7):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        self.content_layout.addWidget(self.projects_table, 1)

        self.detail = QFrame()
        self.detail.setObjectName("ProjectDetail")
        detail_layout = QVBoxLayout(self.detail)
        detail_layout.setContentsMargins(16, 12, 16, 12)
        detail_layout.setSpacing(4)
        self.detail_title = QLabel("Select a project to view its lifecycle and deliverables.")
        self.detail_title.setObjectName("ProjectDetailTitle")
        self.detail_summary = QLabel("")
        self.detail_summary.setObjectName("ProjectDetailSummary")
        self.detail_summary.setWordWrap(True)
        detail_layout.addWidget(self.detail_title)
        detail_layout.addWidget(self.detail_summary)
        self.content_layout.addWidget(self.detail)

        self.new_customer_button.clicked.connect(self._new_customer)
        self.new_project_button.clicked.connect(self._new_project)
        self.advance_button.clicked.connect(self._advance_project)
        self.add_deliverable_button.clicked.connect(self._add_deliverable)
        self.refresh_button.clicked.connect(self.refresh)
        self.search.textChanged.connect(self.refresh)
        self.projects_table.itemSelectionChanged.connect(self._show_selection)
        self.projects_table.itemDoubleClicked.connect(lambda _: self._advance_project())

        ThemeManager.register(self._apply_theme)
        self._apply_theme(ThemeManager.current())

    def refresh(self):
        rows = self.service.repository.projects(self.search.text())
        self.projects_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            project_id, number, name, customer, status, target, jobs, deliverables = row
            values = (
                number,
                name,
                customer,
                status,
                target or "—",
                str(jobs),
                str(deliverables),
                "Select",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, project_id)
                item.setTextAlignment(
                    Qt.AlignVCenter | (Qt.AlignCenter if column in (3, 5, 6, 7) else Qt.AlignLeft)
                )
                self.projects_table.setItem(row_index, column, item)
            self.projects_table.setRowHeight(row_index, 38)
        self._show_selection()

    def _selected_project_id(self) -> int | None:
        selection = self.projects_table.selectedItems()
        return int(selection[0].data(Qt.UserRole)) if selection else None

    def _show_selection(self):
        project_id = self._selected_project_id()
        if not project_id:
            self.detail_title.setText("Select a project to view its lifecycle and deliverables.")
            self.detail_summary.setText("")
            return
        row = self.service.repository.project(project_id)
        deliverables = self.service.repository.deliverables(project_id)
        names = ", ".join(f"{item[1]} ({item[4]})" for item in deliverables) or "No deliverables defined"
        self.detail_title.setText(f"{row[1]} · {row[3]} · {row[5]}")
        self.detail_summary.setText(
            f"Customer: {row[9]}\n"
            f"Target completion: {row[7] or 'Not set'}\n"
            f"Deliverables: {names}\n"
            f"{row[8] or row[4] or 'No project narrative recorded.'}"
        )

    def _new_customer(self):
        dialog = _CustomerDialog(self)
        if not dialog.exec():
            return
        try:
            self.service.create_customer(dialog.customer())
            self.refresh()
        except ValueError as error:
            QMessageBox.warning(self, "Customer", str(error))
        except Exception as error:
            QMessageBox.warning(self, "Customer", f"Unable to save customer: {error}")

    def _new_project(self):
        customers = self.service.repository.customers()
        if not customers:
            QMessageBox.information(
                self,
                "New Project",
                "Create a customer before creating a project.",
            )
            return
        dialog = _ProjectDialog(customers, self)
        if not dialog.exec():
            return
        try:
            self.service.create_project(dialog.project())
            self.refresh()
        except ValueError as error:
            QMessageBox.warning(self, "Project", str(error))
        except Exception as error:
            QMessageBox.warning(self, "Project", f"Unable to save project: {error}")

    def _advance_project(self):
        project_id = self._selected_project_id()
        if not project_id:
            QMessageBox.information(self, "Project", "Select a project first.")
            return
        try:
            status = self.service.advance_project(project_id)
            self.refresh()
            QMessageBox.information(self, "Project", f"Project advanced to {status}.")
        except ValueError as error:
            QMessageBox.information(self, "Project", str(error))

    def _add_deliverable(self):
        project_id = self._selected_project_id()
        if not project_id:
            QMessageBox.information(self, "Deliverable", "Select a project first.")
            return
        name, accepted = QInputDialog.getText(self, "Add Deliverable", "Deliverable name")
        if not accepted or not name.strip():
            return
        try:
            self.service.create_deliverable(
                Deliverable(project_id=project_id, deliverable_name=name.strip())
            )
            self._show_selection()
        except ValueError as error:
            QMessageBox.warning(self, "Deliverable", str(error))

    def _apply_theme(self, theme):
        c = theme.color
        self.setStyleSheet(f"""
QPushButton#ProjectAction {{ background: {c.primary}; color: white; border: none; border-radius: 7px; padding: 0 12px; font-weight: 600; }}
QPushButton#ProjectAction:hover {{ background: {c.primary_hover}; }}
QTableWidget#ProjectsTable {{ background: {c.card}; border: 1px solid {c.border}; border-radius: 10px; color: {c.text}; }}
QTableWidget#ProjectsTable::item {{ border-bottom: 1px solid {c.divider}; padding: 6px 8px; }}
QTableWidget#ProjectsTable::item:selected {{ background: {c.primary}; color: white; }}
QHeaderView::section {{ background: {c.window}; color: {c.text_secondary}; border: none; border-bottom: 1px solid {c.border}; padding: 9px 8px; font-size: 10px; font-weight: 700; }}
QFrame#ProjectDetail {{ background: {c.card}; border: 1px solid {c.border}; border-radius: 10px; }}
QLabel#ProjectDetailTitle {{ color: {c.text}; font-size: 13px; font-weight: 700; }}
QLabel#ProjectDetailSummary {{ color: {c.text_secondary}; font-size: 11px; }}
""")

    def closeEvent(self, event):
        ThemeManager.unregister(self._apply_theme)
        super().closeEvent(event)
