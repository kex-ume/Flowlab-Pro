from pathlib import Path
import shutil

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QFileDialog,
    QPushButton,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QCheckBox,
    QLabel,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
)


class EquipmentDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Equipment")
        self.resize(550, 500)

        self.certificate_path = ""

        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.asset_number = QLineEdit()
        self.equipment_name = QLineEdit()
        self.equipment_type = QLineEdit()
        self.manufacturer = QLineEdit()
        self.model = QLineEdit()
        self.serial_number = QLineEdit()
        self.location = QLineEdit()
        self.primary_equipment = QCheckBox(
            "Primary equipment / reference standard"
        )
        self.include_in_calibration_programme = QCheckBox(
            "Include in Calibration Programme"
        )
        self.primary_equipment.setToolTip(
            "Primary equipment requires a controlled calibration certificate."
        )

        self.next_due_date = QDateEdit()
        self.next_due_date.setCalendarPopup(True)
        self.next_due_date.setDate(QDate.currentDate())

        self.notes = QTextEdit()

        self.upload_button = QPushButton("Upload Certificate")
        self.file_label = QLabel("No File")

        upload_layout = QHBoxLayout()
        upload_layout.addWidget(self.upload_button)
        upload_layout.addWidget(self.file_label)

        self.upload_button.clicked.connect(self.select_certificate)

        form.addRow("Asset No:", self.asset_number)
        form.addRow("Equipment:", self.equipment_name)
        form.addRow("Equipment type:", self.equipment_type)
        form.addRow("Manufacturer:", self.manufacturer)
        form.addRow("Model:", self.model)
        form.addRow("Serial No:", self.serial_number)
        form.addRow("Location:", self.location)
        form.addRow("Control level:", self.primary_equipment)
        form.addRow("Calibration programme:", self.include_in_calibration_programme)
        form.addRow("Next Due:", self.next_due_date)
        form.addRow("Certificate:", upload_layout)
        form.addRow("Notes:", self.notes)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)

    def select_certificate(self):

        destination = Path("data/documents/laboratory")
        destination.mkdir(parents=True, exist_ok=True)

        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select Certificate",
            "",
            "PDF Files (*.pdf);;All Files (*.*)"
        )

        if not filename:
            return

        source = Path(filename)
        target = destination / source.name

        shutil.copy2(source, target)

        self.certificate_path = str(target)
        self.file_label.setText(target.name)

    def load_equipment(self, row):

        self.asset_number.setText(row[1])
        self.equipment_name.setText(row[2])
        self.equipment_type.setText(row[3] or "")
        self.manufacturer.setText(row[4])
        self.model.setText(row[5])
        self.serial_number.setText(row[6])
        self.location.setText(row[7])
        self.primary_equipment.setChecked(bool(row[14]))
        self.include_in_calibration_programme.setChecked(bool(row[19]) if len(row) > 19 else False)

        if row[11]:
            self.next_due_date.setDate(
                QDate.fromString(str(row[11]), "yyyy-MM-dd")
            )

        self.certificate_path = row[13] or ""

        if self.certificate_path:
            self.file_label.setText(
                Path(self.certificate_path).name
            )
        else:
            self.file_label.setText("No File")

        self.notes.setPlainText(row[16] or "")
