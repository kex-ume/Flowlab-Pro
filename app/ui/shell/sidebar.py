from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import ThemeManager


class Sidebar(QFrame):
    page_selected = Signal(str)

    def __init__(self):
        super().__init__()

        self.setObjectName("Sidebar")
        self.setFixedWidth(250)

        self.buttons = {}
        self.current_key = None

        self._build_ui()

        ThemeManager.register(self._apply_theme)
        self._apply_theme(ThemeManager.current())

    # ==========================================================
    # UI
    # ==========================================================

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 18, 16, 18)
        layout.setSpacing(10)

        self.logo = QLabel("FlowLab Pro")
        self.logo.setObjectName("SidebarLogo")
        self.logo.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.logo)
        layout.addSpacing(8)

        self.menu_layout = QVBoxLayout()
        self.menu_layout.setSpacing(6)

        menu = QWidget()
        menu.setLayout(self.menu_layout)

        layout.addWidget(menu)
        layout.addStretch()

        self.user = QLabel("Not signed in")
        self.user.setObjectName("SidebarUser")
        self.user.setAlignment(Qt.AlignCenter)

        self.version = QLabel("v1.0")
        self.version.setObjectName("SidebarVersion")
        self.version.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.user)
        layout.addWidget(self.version)

        self.add_page("dashboard", "Dashboard")
        self.add_page("projects", "Projects")
        self.add_page("laboratory", "Laboratory")
        self.add_page("reports", "Reports")
        self.add_page("settings", "Settings")

        self.select("dashboard")

    # ==========================================================
    # Theme
    # ==========================================================

    def _apply_theme(self, theme):
        c = theme.color

        self.setStyleSheet(
            f"""
            QFrame#Sidebar {{
                background:{c.sidebar};
                border-right:1px solid {c.border};
            }}

            QLabel#SidebarLogo {{
                background:transparent;
                color:{c.text};
                font-size:22px;
                font-weight:700;
                padding:14px;
            }}

            QLabel#SidebarUser {{
                background:transparent;
                color:{c.text_secondary};
                font-size:12px;
                padding:10px;
            }}

            QLabel#SidebarVersion {{
                background:transparent;
                color:{c.text_muted};
                font-size:11px;
                padding:6px;
            }}

            QPushButton {{
                background:transparent;
                border:none;
                border-radius:10px;
                color:{c.text};
                text-align:left;
                padding:12px 16px;
                font-size:14px;
                font-weight:500;
            }}

            QPushButton:hover {{
                background:{c.surface};
            }}

            QPushButton:checked {{
                background:{c.primary};
                color:white;
                font-weight:700;
            }}
            """
        )

    # ==========================================================
    # Navigation
    # ==========================================================

    def add_page(self, key: str, title: str):
        button = QPushButton(title)
        button.setCheckable(True)
        button.setCursor(Qt.PointingHandCursor)
        button.setMinimumHeight(44)
        button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        button.clicked.connect(lambda _, k=key: self.select(k))

        self.menu_layout.addWidget(button)
        self.buttons[key] = button

    def select(self, key: str):
        self.current_key = key

        for page_key, button in self.buttons.items():
            button.setChecked(page_key == key)

        self.page_selected.emit(key)

    # ==========================================================
    # User
    # ==========================================================

    def set_user(self, name: str, role: str):
        self.user.setText(f"{name}\n{role}")

    # ==========================================================
    # Cleanup
    # ==========================================================

    def closeEvent(self, event):
        ThemeManager.unregister(self._apply_theme)
        super().closeEvent(event)