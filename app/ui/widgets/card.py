from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from app.ui.theme.colors import Colors
from app.ui.theme.fonts import Fonts


class Card(QFrame):

    def __init__(self, title: str, value="0", accent=Colors.PRIMARY):
        super().__init__()

        self.accent = accent

        self.setMinimumHeight(140)
        self.setObjectName("DashboardCard")

        self.setStyleSheet(f"""
        QFrame#DashboardCard {{
            background: white;
            border:1px solid {Colors.BORDER};
            border-left:5px solid {accent};
            border-radius:12px;
        }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(8)

        self.title = QLabel(title)
        self.title.setFont(Fonts.card_title())
        self.title.setStyleSheet(f"color:{Colors.TEXT_SECONDARY};")

        self.value = QLabel(str(value))
        self.value.setFont(Fonts.card_value())
        self.value.setAlignment(Qt.AlignCenter)
        self.value.setStyleSheet(f"color:{Colors.TEXT};")

        layout.addWidget(self.title)
        layout.addStretch()
        layout.addWidget(self.value)

    def setValue(self, value):
        self.value.setText(str(value))

    def setAccent(self, color):
        self.setStyleSheet(f"""
        QFrame#DashboardCard {{
            background:white;
            border:1px solid {Colors.BORDER};
            border-left:5px solid {color};
            border-radius:12px;
        }}
        """)