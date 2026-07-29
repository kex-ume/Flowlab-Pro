from pathlib import Path
import shutil

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)


class CalibrationDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Calibration Record")
        self.resize(500, 350)

        self.certificate_path = ""

        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.calibration_date = QDateEdit()
        self.calibration_date.setCalendarPopup(True)
        self.calibration_date.setDate(QDate.currentDate())

        self.next_due_date = QDateEdit()
        self.next_due_date.setCalendarPopup(True)
        self.next_due_date.setDate(QDate.currentDate().addYears(1))

        self.calibrated_by = QLineEdit()
        self.remarks = QTextEdit()

        self.upload_button = QPushButton("Upload Certificate")
        self.file_label = QLabel("No File")

        upload_layout = QHBoxLayout()
        upload_layout.addWidget(self.upload_button)
        upload_layout.addWidget(self.file_label)

        self.upload_button.clicked.connect(self.select_certificate)

        form.addRow("Calibration Date:", self.calibration_date)
        form.addRow("Next Due:", self.next_due_date)
        form.addRow("Calibrated By:", self.calibrated_by)
        form.addRow("Certificate:", upload_layout)
        form.addRow("Remarks:", self.remarks)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)

    def select_certificate(self):

        destination = Path("data/documents/calibration")
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

    def load_record(self, row):

        self.calibration_date.setDate(
            QDate.fromString(str(row[2]), "yyyy-MM-dd")
        )

        self.next_due_date.setDate(
            QDate.fromString(str(row[3]), "yyyy-MM-dd")
        )

        self.calibrated_by.setText(row[4] or "")

        self.certificate_path = row[5] or ""

        if self.certificate_path:
            self.file_label.setText(Path(self.certificate_path).name)
        else:
            self.file_label.setText("No File")

        self.remarks.setPlainText(row[6] or "")