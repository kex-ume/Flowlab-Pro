from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHeaderView, QPushButton, QTableWidget, QTableWidgetItem

from app.modules.laboratory.repository import LaboratoryRepository
from app.ui.base_page import BasePage


class CalibrationProgrammePage(BasePage):
    """Operational schedule sourced only from opted-in equipment records."""

    def __init__(self):
        super().__init__("Calibration Programme", "Equipment included in the programme is managed in the Equipment Register; certificates remain linked to the master asset record.")
        self.repository = LaboratoryRepository()
        self.refresh_button = QPushButton("Refresh Programme")
        self.refresh_button.setObjectName("ControlledAction")
        self.add_toolbar_widget(self.refresh_button); self.add_toolbar_stretch()
        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(["ASSET", "EQUIPMENT", "TYPE", "CLASS", "INTERVAL", "LAST CAL", "NEXT DUE", "STATUS", "CERTIFICATE", "VIEW"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers); self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents); self.table.horizontalHeader().setStretchLastSection(True)
        self.content_layout.addWidget(self.table, 1); self.refresh_button.clicked.connect(self.refresh); self.refresh()

    def refresh(self):
        rows = self.repository.calibration_programme(); self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            _, asset, equipment, equipment_type, interval, last_cal, next_due, status, certificate_path, primary = row
            values = (asset, equipment, equipment_type or "-", "Primary" if primary else "Supporting", f"{interval} months", last_cal or "-", next_due or "-", status, Path(certificate_path).name if certificate_path else "No file")
            for column, value in enumerate(values):
                item = QTableWidgetItem(value); item.setTextAlignment(Qt.AlignVCenter | (Qt.AlignCenter if column in (3, 4, 5, 6, 7) else Qt.AlignLeft)); self.table.setItem(index, column, item)
            view = QPushButton("View certificate"); view.setObjectName("TableAction"); view.setEnabled(bool(certificate_path))
            if certificate_path: view.clicked.connect(lambda _, path=certificate_path: QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).resolve()))))
            self.table.setCellWidget(index, 9, view); self.table.setRowHeight(index, 42)
