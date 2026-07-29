from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from app.ui.theme.colors import Colors
from app.ui.theme.fonts import Fonts


class StatusChip(QLabel):

    COLORS = {
        "Active": Colors.SUCCESS,
        "Due Soon": Colors.WARNING,
        "Overdue": Colors.ERROR,
        "Inactive": "#6B7280",
        "Draft": Colors.INFO,
        "Completed": Colors.SUCCESS,
        "Pending": Colors.WARNING,
        "Cancelled": Colors.ERROR,
    }

    def __init__(self, text):

        super().__init__(text)

        self.setAlignment(Qt.AlignCenter)
        self.setFont(Fonts.small())
        self.setFixedHeight(26)

        self.set_status(text)

    def set_status(self, status):

        self.setText(status)

        color = self.COLORS.get(status, Colors.INFO)

        self.setStyleSheet(f"""
        QLabel {{
            background:{color};
            color:white;
            border:none;
            border-radius:13px;
            padding:2px 12px;
            font-weight:600;
        }}
        """)