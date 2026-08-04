from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
)


class EquipmentTable(QTableWidget):
    """Inventory table; primary equipment remains part of the same pool."""

    HEADERS = [
        "Asset No",
        "Equipment",
        "Manufacturer",
        "Model",
        "Serial No",
        "Location",
        "Next Due",
        "Status",
        "Control Level",
        "Certificate",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(len(self.HEADERS))
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    def load_data(self, rows, open_callback):
        self.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row[1],
                row[2],
                row[4],
                row[5],
                row[6],
                row[7],
                row[11],
                row[12],
                "Primary" if row[14] else "Supporting",
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem("" if value is None else str(value))
                item.setTextAlignment(Qt.AlignCenter)
                if column == 0:
                    item.setData(Qt.UserRole, row[0])
                if column == 7:
                    self._apply_status_style(item, value)
                self.setItem(row_index, column, item)

            certificate_button = QPushButton("Open" if row[13] else "No File")
            if row[13]:
                certificate_button.clicked.connect(
                    lambda _, path=row[13]: open_callback(path)
                )
            else:
                certificate_button.setEnabled(False)
            self.setCellWidget(row_index, 9, certificate_button)

    @staticmethod
    def _apply_status_style(item, status):
        status_colors = {
            "Active": "#2ECC71",
            "Due Soon": "#F39C12",
            "Overdue": "#E74C3C",
        }
        color = status_colors.get(status)
        if color:
            item.setForeground(QColor(color))
