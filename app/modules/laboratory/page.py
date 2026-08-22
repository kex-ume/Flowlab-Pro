from datetime import date
import os

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QMessageBox,
)

from app.modules.laboratory.dialogs.equipment_dialog import EquipmentDialog
from app.modules.laboratory.models import LaboratoryAsset
from app.modules.laboratory.repository import LaboratoryRepository
from app.modules.laboratory.service import LaboratoryService
from app.modules.laboratory.widgets.equipment_table import EquipmentTable

from app.modules.laboratory.calibration.page import CalibrationPage
from app.modules.laboratory.maintenance.page import MaintenancePage


class LaboratoryPage(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.repository = LaboratoryRepository()

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()

        self.add_button = QPushButton("Add Equipment")
        self.edit_button = QPushButton("Edit")
        self.delete_button = QPushButton("Delete")
        self.primary_button = QPushButton("Toggle Primary")
        self.calibration_button = QPushButton("Calibration")
        self.maintenance_button = QPushButton("Maintenance")

        toolbar.addWidget(self.add_button)
        toolbar.addWidget(self.edit_button)
        toolbar.addWidget(self.delete_button)
        toolbar.addWidget(self.primary_button)
        toolbar.addStretch()
        toolbar.addWidget(self.calibration_button)
        toolbar.addWidget(self.maintenance_button)

        layout.addLayout(toolbar)

        self.table = EquipmentTable()
        layout.addWidget(self.table)

        self.add_button.clicked.connect(self.add_equipment)
        self.edit_button.clicked.connect(self.edit_equipment)
        self.delete_button.clicked.connect(self.delete_equipment)
        self.primary_button.clicked.connect(self.toggle_primary_equipment)
        self.calibration_button.clicked.connect(self.open_calibration)
        self.maintenance_button.clicked.connect(self.open_maintenance)

        self.calibration_window = None
        self.maintenance_window = None

        self.load_data()

    def load_data(self):
        rows = self.repository.get_all_equipment()
        self.table.load_data(rows, self.open_certificate)

    def open_certificate(self, path):
        if path and os.path.exists(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        else:
            QMessageBox.warning(self, "Certificate", "File not found.")

    def add_equipment(self):

        dialog = EquipmentDialog(self)

        if dialog.exec():

            next_due = date(
                dialog.next_due_date.date().year(),
                dialog.next_due_date.date().month(),
                dialog.next_due_date.date().day(),
            )

            asset = LaboratoryAsset(
                asset_number=dialog.asset_number.text(),
                equipment_name=dialog.equipment_name.text(),
                equipment_type=dialog.equipment_type.text(),
                manufacturer=dialog.manufacturer.text(),
                model=dialog.model.text(),
                serial_number=dialog.serial_number.text(),
                laboratory_location=dialog.location.text(),
                next_calibration_date=next_due,
                status=LaboratoryService.determine_status(next_due),
                certificate_path=dialog.certificate_path,
                is_reference_standard=dialog.primary_equipment.isChecked(),
                include_in_calibration_programme=dialog.include_in_calibration_programme.isChecked(),
                notes=dialog.notes.toPlainText(),
            )

            self.repository.add_equipment(asset)
            self.load_data()

    def edit_equipment(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Edit Equipment", "Select equipment first.")
            return
        equipment_id = self.table.item(row, 0).data(Qt.UserRole)
        current = self.repository.get_equipment_by_id(equipment_id)
        dialog = EquipmentDialog(self)
        dialog.load_equipment(current)
        if not dialog.exec():
            return
        next_due = date(dialog.next_due_date.date().year(), dialog.next_due_date.date().month(), dialog.next_due_date.date().day())
        asset = LaboratoryAsset(
            asset_number=dialog.asset_number.text().strip(), equipment_name=dialog.equipment_name.text().strip(),
            equipment_type=dialog.equipment_type.text().strip(), manufacturer=dialog.manufacturer.text().strip(),
            model=dialog.model.text().strip(), serial_number=dialog.serial_number.text().strip(),
            laboratory_location=dialog.location.text().strip(), next_calibration_date=next_due,
            status=LaboratoryService.determine_status(next_due), certificate_path=dialog.certificate_path,
            is_reference_standard=dialog.primary_equipment.isChecked(),
            include_in_calibration_programme=dialog.include_in_calibration_programme.isChecked(),
            notes=dialog.notes.toPlainText().strip())
        self.repository.update_equipment(equipment_id, asset)
        self.load_data()

    def delete_equipment(self):

        row = self.table.currentRow()

        if row < 0:
            QMessageBox.information(
                self,
                "Delete Equipment",
                "Select equipment first."
            )
            return

        equipment_id = self.table.item(row, 0).data(Qt.UserRole)

        if QMessageBox.question(
            self,
            "Delete Equipment",
            "Delete selected equipment?",
            QMessageBox.Yes | QMessageBox.No,
        ) == QMessageBox.Yes:

            self.repository.delete_equipment(equipment_id)
            self.load_data()

    def toggle_primary_equipment(self):
        """Promote or demote the selected inventory item as primary equipment."""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(
                self,
                "Primary equipment",
                "Select an equipment item first.",
            )
            return

        equipment_id = self.table.item(row, 0).data(Qt.UserRole)
        control_level = self.table.item(row, 8).text()
        is_primary = control_level != "Primary"
        action = "Mark" if is_primary else "Remove"

        if QMessageBox.question(
            self,
            "Primary equipment",
            f"{action} this item as primary equipment?",
            QMessageBox.Yes | QMessageBox.No,
        ) != QMessageBox.Yes:
            return

        self.repository.set_primary_equipment(equipment_id, is_primary)
        self.load_data()

    def open_calibration(self):

        row = self.table.currentRow()

        if row < 0:
            QMessageBox.information(
                self,
                "Calibration",
                "Select equipment first."
            )
            return

        equipment_id = self.table.item(row, 0).data(Qt.UserRole)

        self.calibration_window = CalibrationPage(equipment_id)
        self.calibration_window.setWindowTitle("Calibration History")
        self.calibration_window.resize(750, 500)
        self.calibration_window.show()

    def open_maintenance(self):

        row = self.table.currentRow()

        if row < 0:
            QMessageBox.information(
                self,
                "Maintenance",
                "Select equipment first."
            )
            return

        equipment_id = self.table.item(row, 0).data(Qt.UserRole)

        self.maintenance_window = MaintenancePage(equipment_id)
        self.maintenance_window.setWindowTitle("Maintenance History")
        self.maintenance_window.resize(800, 500)
        self.maintenance_window.show()
