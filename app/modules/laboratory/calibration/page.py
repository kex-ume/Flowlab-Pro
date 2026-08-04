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

from app.modules.laboratory.calibration.dialog import CalibrationDialog
from app.modules.laboratory.calibration.models import CalibrationRecord
from app.modules.laboratory.calibration.repository import CalibrationRepository


class CalibrationPage(QWidget):

    def __init__(self, equipment_id, parent=None):
        super().__init__(parent)

        self.equipment_id = equipment_id
        self.repository = CalibrationRepository()

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
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            "Calibration Date",
            "Next Due",
            "Calibrated By",
            "Certificate",
        ])

        self.table.cellDoubleClicked.connect(self.cell_double_clicked)

        layout.addWidget(self.table)

        self.add_button.clicked.connect(self.add_record)
        self.edit_button.clicked.connect(self.edit_record)
        self.delete_button.clicked.connect(self.delete_record)

        self.load_data()

    def load_data(self):

        rows = self.repository.get_records(self.equipment_id)

        self.table.setRowCount(len(rows))

        for r, row in enumerate(rows):

            self.table.setItem(r, 0, QTableWidgetItem(str(row[2])))
            self.table.setItem(r, 1, QTableWidgetItem(str(row[3])))
            self.table.setItem(r, 2, QTableWidgetItem(str(row[4])))

            cert = QTableWidgetItem("Open" if row[5] else "No File")
            cert.setData(Qt.UserRole, row[5])
            self.table.setItem(r, 3, cert)

            self.table.item(r, 0).setData(Qt.UserRole, row[0])

    def cell_double_clicked(self, row, column):

        if column == 3:

            path = self.table.item(row, 3).data(Qt.UserRole)

            if path and os.path.exists(path):
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            else:
                QMessageBox.warning(
                    self,
                    "Certificate",
                    "Certificate file not found."
                )

            return

        self.edit_record()

    def add_record(self):

        dialog = CalibrationDialog(self)

        if dialog.exec():

            record = CalibrationRecord(
                equipment_id=self.equipment_id,
                calibration_date=dialog.calibration_date.date().toString("yyyy-MM-dd"),
                next_due_date=dialog.next_due_date.date().toString("yyyy-MM-dd"),
                calibrated_by=dialog.calibrated_by.text(),
                certificate_path=dialog.certificate_path,
                remarks=dialog.remarks.toPlainText(),
            )

            try:
                self.repository.add_record(record)
            except ValueError as error:
                QMessageBox.warning(self, "Calibration certificate", str(error))
                return
            self.load_data()

    def edit_record(self):

        row = self.table.currentRow()

        if row < 0:
            QMessageBox.information(
                self,
                "Edit",
                "Select a calibration record."
            )
            return

        record_id = self.table.item(row, 0).data(Qt.UserRole)

        record = self.repository.get_record(record_id)

        dialog = CalibrationDialog(self)
        dialog.load_record(record)

        if dialog.exec():

            updated = CalibrationRecord(
                id=record_id,
                equipment_id=self.equipment_id,
                calibration_date=dialog.calibration_date.date().toString("yyyy-MM-dd"),
                next_due_date=dialog.next_due_date.date().toString("yyyy-MM-dd"),
                calibrated_by=dialog.calibrated_by.text(),
                certificate_path=dialog.certificate_path,
                remarks=dialog.remarks.toPlainText(),
            )

            try:
                self.repository.update_record(updated)
            except ValueError as error:
                QMessageBox.warning(self, "Calibration certificate", str(error))
                return
            self.load_data()

    def delete_record(self):

        row = self.table.currentRow()

        if row < 0:
            return

        record_id = self.table.item(row, 0).data(Qt.UserRole)

        if QMessageBox.question(
            self,
            "Delete",
            "Delete calibration record?",
        ) == QMessageBox.Yes:

            self.repository.delete_record(record_id)
            self.load_data()
