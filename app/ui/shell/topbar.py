from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
)

from app.ui.theme import ThemeManager


class TopBar(QFrame):
    def __init__(self):
        super().__init__()

        self.setObjectName("TopBar")
        self.setFixedHeight(60)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(15)

        # --------------------------------------------------
        # Application Title
        # --------------------------------------------------

        self.title = QLabel("FlowLab Pro")
        self.title.setObjectName("ApplicationTitle")

        # --------------------------------------------------
        # Global Search
        # --------------------------------------------------

        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "Search projects, equipment, reports..."
        )
        self.search.setMinimumWidth(350)

        # --------------------------------------------------
        # Right Side
        # --------------------------------------------------

        self.database = QLabel("🟢 Database")

        self.notifications = QPushButton("🔔")
        self.notifications.setFixedWidth(40)

        self.user = QLabel("Administrator")

        layout.addWidget(self.title)
        layout.addSpacing(20)
        layout.addWidget(self.search)
        layout.addStretch()
        layout.addWidget(self.database)
        layout.addWidget(self.notifications)
        layout.addWidget(self.user)

        ThemeManager.register(self._apply_theme)
        self._apply_theme(ThemeManager.current())

    # =====================================================
    # Theme
    # =====================================================

    def _apply_theme(self, theme):
        c = theme.color

        self.setStyleSheet(
            f"""
            QFrame#TopBar {{
                background:{c.surface};
                border-bottom:1px solid {c.border};
            }}

            QLabel#ApplicationTitle {{
                background:transparent;
                color:{c.text};
                font-size:20px;
                font-weight:700;
            }}

            QLabel {{
                background:transparent;
                color:{c.text_secondary};
                font-size:13px;
            }}

            QLineEdit {{
                background:{c.input_bg};
                color:{c.text};
                border:1px solid {c.input_border};
                border-radius:8px;
                padding:8px;
            }}

            QLineEdit:focus {{
                border:1px solid {c.primary};
            }}

            QPushButton {{
                background:{c.primary};
                color:white;
                border:none;
                border-radius:8px;
                padding:6px;
            }}

            QPushButton:hover {{
                background:{c.primary_hover};
            }}
            """
        )

    # =====================================================
    # Public API
    # =====================================================

    def set_user(self, name: str):
        self.user.setText(name)

    def set_database_status(self, connected: bool):
        self.database.setText(
            "🟢 Database" if connected else "🔴 Database"
        )

    # =====================================================
    # Cleanup
    # =====================================================

    def closeEvent(self, event):
        ThemeManager.unregister(self._apply_theme)
        super().closeEvent(event)