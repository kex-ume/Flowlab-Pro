from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from app.ui.theme import ThemeManager


class Card(QFrame):
    def __init__(self, title: str, value="0", accent=None):
        super().__init__()

        self.setObjectName("DashboardCard")
        self.setMinimumHeight(140)

        self._accent = accent

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(8)

        self.title = QLabel(title)
        self.title.setObjectName("CardTitle")

        self.value = QLabel(str(value))
        self.value.setObjectName("CardValue")
        self.value.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.title)
        layout.addStretch()
        layout.addWidget(self.value)

        ThemeManager.register(self._apply_theme)
        self._apply_theme(ThemeManager.current())

    # ---------------------------------------------------------
    # Theme
    # ---------------------------------------------------------

    def _apply_theme(self, theme):
        c = theme.color

        accent = self._accent or c.primary

        self.setStyleSheet(
            f"""
            QFrame#DashboardCard {{
                background:{c.card};
                border:1px solid {c.border};
                border-left:5px solid {accent};
                border-radius:12px;
            }}

            QLabel#CardTitle {{
                background:transparent;
                color:{c.text_secondary};
                font-size:13px;
                font-weight:600;
            }}

            QLabel#CardValue {{
                background:transparent;
                color:{c.text};
                font-size:34px;
                font-weight:700;
            }}
            """
        )

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------

    def setValue(self, value):
        self.value.setText(str(value))

    def setAccent(self, color):
        self._accent = color
        self._apply_theme(ThemeManager.current())

    # ---------------------------------------------------------
    # Cleanup
    # ---------------------------------------------------------

    def closeEvent(self, event):
        ThemeManager.unregister(self._apply_theme)
        super().closeEvent(event)