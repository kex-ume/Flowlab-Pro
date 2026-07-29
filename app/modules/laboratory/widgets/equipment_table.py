from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
)


class EquipmentTable(QTableWidget):

    HEADERS = [
        "Asset No",
        "Equipment",
        "Manufacturer",
        "Model",
        "Serial No",
        "Location",
        "Next Due",
        "Status",
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

        for r, row in enumerate(rows):

            values = [
                row[1],
                row[2],
                row[4],
                row[5],
                row[6],
                row[7],
                row[11],
                row[12],
            ]

            for c, value in enumerate(values):

                item = QTableWidgetItem("" if value is None else str(value))
                item.setTextAlignment(Qt.AlignCenter)

                if c == 0:
                    item.setData(Qt.UserRole, row[0])

                if c == 7:

                    if value == "Active":
                        item.setText("Active 🟢")
                        item.setForeground(QColor("#2ECC71"))

                    elif value == "Due Soon":
                        item.setText("Due Soon 🟠")
                        item.setForeground(QColor("#F39C12"))

                    elif value == "Overdue":
                        item.setText("Overdue 🔴")
                        item.setForeground(QColor("#E74C3C"))

                self.setItem(r, c, item)

            button = QPushButton(
                "Open" if row[13] else "No File"
            )

            if row[13]:
                button.clicked.connect(
                    lambda _, p=row[13]: open_callback(p)
                )
            else:
                button.setEnabled(False)

            self.setCellWidget(r, 8, button)