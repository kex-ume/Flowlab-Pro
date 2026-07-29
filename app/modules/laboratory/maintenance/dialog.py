from pathlib import Path
import shutil

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)


class MaintenanceDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Maintenance Record")
        self.resize(520, 400)

        self.document_path = ""

        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.maintenance_date = QDateEdit()
        self.maintenance_date.setCalendarPopup(True)
        self.maintenance_date.setDate(QDate.currentDate())

        self.maintenance_type = QComboBox()
        self.maintenance_type.addItems([
            "Preventive",
            "Corrective",
            "Repair",
            "Inspection",
            "Cleaning",
            "Other",
        ])

        self.performed_by = QLineEdit()

        self.cost = QDoubleSpinBox()
        self.cost.setMaximum(1000000)
        self.cost.setDecimals(2)
        self.cost.setPrefix("$ ")

        self.remarks = QTextEdit()

        self.upload_button = QPushButton("Upload Document")
        self.file_label = QLabel("No File")

        upload_layout = QHBoxLayout()
        upload_layout.addWidget(self.upload_button)
        upload_layout.addWidget(self.file_label)

        self.upload_button.clicked.connect(self.select_document)

        form.addRow("Maintenance Date:", self.maintenance_date)
        form.addRow("Type:", self.maintenance_type)
        form.addRow("Performed By:", self.performed_by)
        form.addRow("Cost:", self.cost)
        form.addRow("Document:", upload_layout)
        form.addRow("Remarks:", self.remarks)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)

    def select_document(self):

        destination = Path("data/documents/maintenance")
        destination.mkdir(parents=True, exist_ok=True)

        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select Document",
            "",
            "PDF Files (*.pdf);;All Files (*.*)"
        )

        if not filename:
            return

        source = Path(filename)
        target = destination / source.name

        shutil.copy2(source, target)

        self.document_path = str(target)
        self.file_label.setText(target.name)

    def load_record(self, row):

        self.maintenance_date.setDate(
            QDate.fromString(str(row[2]), "yyyy-MM-dd")
        )

        index = self.maintenance_type.findText(row[3])
        if index >= 0:
            self.maintenance_type.setCurrentIndex(index)

        self.performed_by.setText(row[4] or "")
        self.cost.setValue(float(row[5] or 0))

        self.document_path = row[6] or ""

        if self.document_path:
            self.file_label.setText(Path(self.document_path).name)
        else:
            self.file_label.setText("No File")

        self.remarks.setPlainText(row[7] or "")