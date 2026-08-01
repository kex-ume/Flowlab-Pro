from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import ThemeManager


class TopBar(QFrame):

    def __init__(self):
        super().__init__()

        self.setObjectName("TopBar")
        self.setFixedHeight(86)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 12, 24, 12)
        layout.setSpacing(20)

        # --------------------------------------------------
        # Left
        # --------------------------------------------------

        left = QVBoxLayout()
        left.setSpacing(2)

        self.title = QLabel("Dashboard")
        self.title.setObjectName("TopTitle")

        self.subtitle = QLabel(
            "Welcome back. Here's what's happening in your laboratory."
        )
        self.subtitle.setObjectName("TopSubtitle")

        left.addWidget(self.title)
        left.addWidget(self.subtitle)

        layout.addLayout(left)

        layout.addStretch()

        # --------------------------------------------------
        # Search
        # --------------------------------------------------

        self.search = QLineEdit()
        self.search.setObjectName("SearchBox")
        self.search.setPlaceholderText(
            "🔍 Search jobs, equipment, certificates..."
        )
        self.search.setFixedWidth(420)

        layout.addWidget(self.search)

        layout.addStretch()

        # --------------------------------------------------
        # Notifications
        # --------------------------------------------------

        self.notifications = QPushButton("🔔")
        self.notifications.setObjectName("NotificationButton")
        self.notifications.setFixedSize(42, 42)

        layout.addWidget(self.notifications)

        # --------------------------------------------------
        # Avatar
        # --------------------------------------------------

        self.avatar = QLabel("SA")
        self.avatar.setObjectName("Avatar")
        self.avatar.setAlignment(Qt.AlignCenter)
        self.avatar.setFixedSize(40, 40)

        layout.addWidget(self.avatar)

        # --------------------------------------------------
        # User
        # --------------------------------------------------

        user_layout = QVBoxLayout()
        user_layout.setSpacing(0)

        self.user = QLabel("System Administrator")
        self.user.setObjectName("UserName")

        self.role = QLabel("Administrator")
        self.role.setObjectName("UserRole")

        user_layout.addWidget(self.user)
        user_layout.addWidget(self.role)

        layout.addLayout(user_layout)

        ThemeManager.register(self._apply_theme)
        self._apply_theme(ThemeManager.current())

    # --------------------------------------------------

    def _apply_theme(self, theme):

        c = theme.color

        self.setStyleSheet(
            f"""
QFrame#TopBar {{
    background:{c.surface};
    border-bottom:1px solid {c.border};
}}

QLabel#TopTitle {{
    font-size:26px;
    font-weight:700;
    color:{c.text};
}}

QLabel#TopSubtitle {{
    font-size:13px;
    color:{c.text_secondary};
}}

QLineEdit#SearchBox {{
    background:{c.input_bg};
    border:1px solid {c.border};
    border-radius:12px;
    padding:10px 14px;
    font-size:13px;
}}

QLineEdit#SearchBox:focus {{
    border:1px solid {c.primary};
}}

QPushButton#NotificationButton {{
    background:{c.surface};
    border:1px solid {c.border};
    border-radius:10px;
    font-size:16px;
}}

QPushButton#NotificationButton:hover {{
    background:{c.table_hover};
}}

QLabel#Avatar {{
    background:{c.primary};
    color:white;
    border-radius:20px;
    font-weight:700;
    font-size:14px;
}}

QLabel#UserName {{
    font-weight:700;
    font-size:13px;
    color:{c.text};
}}

QLabel#UserRole {{
    font-size:11px;
    color:{c.text_secondary};
}}
"""
        )

    # --------------------------------------------------

    def set_user(self, name):
        self.user.setText(name)

        initials = "".join(
            word[0].upper()
            for word in name.split()
            if word
        )[:2]

        self.avatar.setText(initials)

    def set_database_status(self, connected):
        # Reserved for future status indicator
        pass

    # --------------------------------------------------

    def closeEvent(self, event):
        ThemeManager.unregister(self._apply_theme)
        super().closeEvent(event)