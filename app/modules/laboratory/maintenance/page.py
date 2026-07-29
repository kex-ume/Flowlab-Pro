import os

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
)

from app.modules.laboratory.maintenance.dialog import MaintenanceDialog
from app.modules.laboratory.maintenance.models import MaintenanceRecord
from app.modules.laboratory.maintenance.repository import MaintenanceRepository


class MaintenancePage(QWidget):

    def __init__(self, equipment_id, parent=None):
        super().__init__(parent)

        self.equipment_id = equipment_id
        self.repository = MaintenanceRepository()

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()

        self.add_button = QPushButton("Add")
        self.edit_button = QPushButton("Edit")
        self.delete_button = QPushButton("Delete")

        toolbar.addWidget(self.add_button)
        toolbar.addWidget(self.edit_button)
        toolbar.addWidget(self.delete_button)
        toolbar.addStretch()

        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Date",
            "Type",
            "Performed By",
            "Cost",
            "Document",
        ])

        layout.addWidget(self.table)

        self.add_button.clicked.connect(self.add_record)
        self.edit_button.clicked.connect(self.edit_record)
        self.delete_button.clicked.connect(self.delete_record)
        self.table.cellDoubleClicked.connect(self.cell_double_clicked)

        self.load_data()

    def load_data(self):

        rows = self.repository.get_records(self.equipment_id)

        self.table.setRowCount(len(rows))

        for r, row in enumerate(rows):

            self.table.setItem(r, 0, QTableWidgetItem(str(row[2])))
            self.table.setItem(r, 1, QTableWidgetItem(str(row[3])))
            self.table.setItem(r, 2, QTableWidgetItem(str(row[4])))
            self.table.setItem(r, 3, QTableWidgetItem(f"${float(row[5]):,.2f}"))

            doc = QTableWidgetItem("Open" if row[6] else "No File")
            doc.setData(Qt.UserRole, row[6])
            self.table.setItem(r, 4, doc)

            self.table.item(r, 0).setData(Qt.UserRole, row[0])

    def cell_double_clicked(self, row, column):

        if column == 4:

            path = self.table.item(row, 4).data(Qt.UserRole)

            if path and os.path.exists(path):
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            else:
                QMessageBox.warning(self, "Document", "File not found.")

            return

        self.edit_record()

    def add_record(self):

        dialog = MaintenanceDialog(self)

        if dialog.exec():

            record = MaintenanceRecord(
                equipment_id=self.equipment_id,
                maintenance_date=dialog.maintenance_date.date().toString("yyyy-MM-dd"),
                maintenance_type=dialog.maintenance_type.currentText(),
                performed_by=dialog.performed_by.text(),
                cost=dialog.cost.value(),
                document_path=dialog.document_path,
                remarks=dialog.remarks.toPlainText(),
            )

            self.repository.add_record(record)
            self.load_data()

    def edit_record(self):

        row = self.table.currentRow()

        if row < 0:
            return

        record_id = self.table.item(row, 0).data(Qt.UserRole)

        data = self.repository.get_record(record_id)

        dialog = MaintenanceDialog(self)
        dialog.load_record(data)

        if dialog.exec():

            record = MaintenanceRecord(
                id=record_id,
                equipment_id=self.equipment_id,
                maintenance_date=dialog.maintenance_date.date().toString("yyyy-MM-dd"),
                maintenance_type=dialog.maintenance_type.currentText(),
                performed_by=dialog.performed_by.text(),
                cost=dialog.cost.value(),
                document_path=dialog.document_path,
                remarks=dialog.remarks.toPlainText(),
            )

            self.repository.update_record(record)
            self.load_data()

    def delete_record(self):

        row = self.table.currentRow()

        if row < 0:
            return

        record_id = self.table.item(row, 0).data(Qt.UserRole)

        if QMessageBox.question(
            self,
            "Delete",
            "Delete maintenance record?",
        ) == QMessageBox.Yes:

            self.repository.delete_record(record_id)
            self.load_data()