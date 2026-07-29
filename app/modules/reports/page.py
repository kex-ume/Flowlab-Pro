from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QFileDialog,
    QMessageBox,
)

from app.modules.reports.service import ReportsService
from app.modules.reports.pdf_export import PDFExporter
from app.modules.reports.excel_export import ExcelExporter


class ReportsPage(QWidget):

    def __init__(self):
        super().__init__()

        self.service = ReportsService()

        self.setWindowTitle("Reports")

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()

        toolbar.addWidget(QLabel("Report"))

        self.report_type = QComboBox()
        self.report_type.addItems([
            "Equipment",
            "Calibration",
            "Maintenance",
            "Users",
        ])

        toolbar.addWidget(self.report_type)

        toolbar.addWidget(QLabel("Search"))

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search...")
        toolbar.addWidget(self.search)

        self.refresh_btn = QPushButton("Refresh")
        self.pdf_btn = QPushButton("Export PDF")
        self.excel_btn = QPushButton("Export Excel")
        self.print_btn = QPushButton("Print")

        toolbar.addWidget(self.refresh_btn)
        toolbar.addWidget(self.pdf_btn)
        toolbar.addWidget(self.excel_btn)
        toolbar.addWidget(self.print_btn)
        toolbar.addStretch()

        layout.addLayout(toolbar)

        self.table = QTableWidget()
        layout.addWidget(self.table)

        self.report_type.currentIndexChanged.connect(self.load_data)
        self.refresh_btn.clicked.connect(self.load_data)
        self.search.textChanged.connect(self.filter_table)
        self.pdf_btn.clicked.connect(self.export_pdf)
        self.excel_btn.clicked.connect(self.export_excel)
        self.print_btn.clicked.connect(self.print_report)

        self.current_data = []

        self.load_data()

    def load_data(self):

        report = self.report_type.currentText()

        if report == "Equipment":
            headers = [
                "Asset",
                "Equipment",
                "Manufacturer",
                "Model",
                "Status",
                "Next Calibration",
            ]
            rows = self.service.equipment()

        elif report == "Calibration":
            headers = [
                "Equipment",
                "Calibration Date",
                "Next Due",
                "Calibrated By",
            ]
            rows = self.service.calibrations()

        elif report == "Maintenance":
            headers = [
                "Equipment",
                "Date",
                "Type",
                "Performed By",
                "Cost",
            ]
            rows = self.service.maintenance()

        else:
            headers = [
                "Username",
                "Full Name",
                "Email",
                "Active",
            ]
            rows = self.service.users()

        self.current_data = rows

        self.table.clear()
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(rows))

        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                self.table.setItem(
                    r,
                    c,
                    QTableWidgetItem(str(value))
                )

        self.table.resizeColumnsToContents()

    def filter_table(self):

        text = self.search.text().lower()

        for row in range(self.table.rowCount()):

            visible = False

            for col in range(self.table.columnCount()):

                item = self.table.item(row, col)

                if item and text in item.text().lower():
                    visible = True
                    break

            self.table.setRowHidden(row, not visible)

    def export_pdf(self):

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export PDF",
            "",
            "PDF Files (*.pdf)"
        )

        if not filename:
            return

        PDFExporter().export(
            filename,
            self.table,
            self.report_type.currentText()
        )

        QMessageBox.information(
            self,
            "Reports",
            "PDF exported successfully."
        )

    def export_excel(self):

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Excel",
            "",
            "Excel Files (*.xlsx)"
        )

        if not filename:
            return

        ExcelExporter().export(
            filename,
            self.table,
            self.report_type.currentText()
        )

        QMessageBox.information(
            self,
            "Reports",
            "Excel exported successfully."
        )

    def print_report(self):

        QMessageBox.information(
            self,
            "Reports",
            "Print support coming next."
        )