"""Top workspace bar matching the approved FlowLab console reference."""

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from app.ui.theme import ThemeManager

import app.ui.resources.resources_rc


class TopBar(QFrame):
    """Current workspace, global search, notifications and profile controls."""

    search_requested = Signal(str)
    notifications_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("TopBar")
        self.setFixedHeight(66)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(28, 0, 28, 0)
        layout.setSpacing(18)

        context = QVBoxLayout()
        context.setSpacing(1)
        self.title = QLabel("Dashboard")
        self.title.setObjectName("TopTitle")
        self.breadcrumb = QLabel("Welcome back — here's today's calibration and compliance picture")
        self.breadcrumb.setObjectName("PageSubtitle")
        context.addWidget(self.title)
        context.addWidget(self.breadcrumb)
        layout.addLayout(context)
        layout.addStretch(1)

        self.search = QLineEdit()
        self.search.setObjectName("SearchBox")
        self.search.setPlaceholderText("Search jobs, equipment, certificates…")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(300)
        self.search.addAction(QIcon(":/icons/search.svg"), QLineEdit.LeadingPosition)
        self.search.returnPressed.connect(self._request_search)
        layout.addWidget(self.search)
        layout.addStretch(1)

        self.notifications = QPushButton()
        self.notifications.setObjectName("NotificationButton")
        self.notifications.setIcon(QIcon(":/icons/notification.svg"))
        self.notifications.setIconSize(QSize(18, 18))
        self.notifications.setToolTip("Open notifications")
        self.notifications.setFixedSize(34, 34)
        self.notifications.clicked.connect(self.notifications_requested)
        self.notification_badge = QLabel("3", self.notifications)
        self.notification_badge.setObjectName("NotificationBadge")
        self.notification_badge.setAlignment(Qt.AlignCenter)
        self.notification_badge.setFixedSize(15, 15)
        self.notification_badge.move(20, 1)
        layout.addWidget(self.notifications)

        self.profile = QFrame()
        self.profile.setObjectName("Profile")
        profile_layout = QHBoxLayout(self.profile)
        profile_layout.setContentsMargins(14, 0, 0, 0)
        profile_layout.setSpacing(9)
        self.avatar = QLabel("SA")
        self.avatar.setObjectName("Avatar")
        self.avatar.setAlignment(Qt.AlignCenter)
        self.avatar.setFixedSize(34, 34)
        profile_layout.addWidget(self.avatar)
        details = QVBoxLayout()
        details.setSpacing(0)
        self.user = QLabel("System Administrator")
        self.user.setObjectName("UserName")
        self.role = QLabel("Administrator")
        self.role.setObjectName("UserRole")
        details.addWidget(self.user)
        details.addWidget(self.role)
        profile_layout.addLayout(details)
        layout.addWidget(self.profile)

        self._profile_widgets = (self.profile, self.avatar, self.user, self.role)
        for widget in self._profile_widgets:
            widget.setCursor(Qt.PointingHandCursor)
            widget.installEventFilter(self)

        ThemeManager.register(self._apply_theme)
        self._apply_theme(ThemeManager.current())

    def _request_search(self):
        query = self.search.text().strip()
        if query:
            self.search_requested.emit(query)

    def resizeEvent(self, event):
        compact = event.size().width() < 820
        self.breadcrumb.setVisible(not compact)
        self.user.setVisible(not compact)
        self.role.setVisible(not compact)
        self.search.setFixedWidth(190 if compact else 300)
        super().resizeEvent(event)

    def minimumSizeHint(self):
        return QSize(520, self.height())

    def eventFilter(self, watched, event):
        if (
            watched in self._profile_widgets
            and event.type() == QEvent.MouseButtonRelease
            and event.button() == Qt.LeftButton
        ):
            self._show_theme_menu(watched.mapToGlobal(event.pos()))
            return True
        return super().eventFilter(watched, event)

    def _show_theme_menu(self, position):
        menu = QMenu(self)
        light_action = menu.addAction("Light theme")
        light_action.setCheckable(True)
        light_action.setChecked(not ThemeManager.is_dark())
        light_action.triggered.connect(ThemeManager.set_light)
        dark_action = menu.addAction("Dark theme")
        dark_action.setCheckable(True)
        dark_action.setChecked(ThemeManager.is_dark())
        dark_action.triggered.connect(ThemeManager.set_dark)
        menu.exec(position)

    def _apply_theme(self, theme):
        c = theme.color
        self.setStyleSheet(f"""
QFrame#TopBar {{ background: {c.surface}; border-bottom: 1px solid {c.border}; }}
QFrame#TopBar QLabel {{ background: transparent; border: none; }}
QLabel#TopTitle {{ color: {c.text}; font-size: 19px; font-weight: 700; }}
QLabel#PageSubtitle {{ color: {c.text_secondary}; font-size: 12px; }}
QLineEdit#SearchBox {{ background: {c.window}; border: 1px solid {c.border}; border-radius: 8px; padding: 8px 10px; color: {c.text}; font-size: 13px; }}
QLineEdit#SearchBox:focus {{ border-color: {c.primary}; }}
QPushButton#NotificationButton {{ background: transparent; color: {c.text_secondary}; border: 1px solid transparent; border-radius: 8px; }}
QPushButton#NotificationButton:hover {{ background: {c.window}; border-color: {c.border}; }}
QLabel#NotificationBadge {{ background: {c.error}; color: white; border: 2px solid {c.surface}; border-radius: 7px; font-size: 8px; font-weight: 700; }}
QFrame#Profile {{ background: transparent; border: none; border-left: 1px solid {c.border}; }}
QLabel#Avatar {{ background: {c.primary}; color: white; border-radius: 8px; font-size: 12px; font-weight: 700; }}
QLabel#UserName {{ color: {c.text}; font-size: 13px; font-weight: 600; }}
QLabel#UserRole {{ color: {c.text_secondary}; font-size: 11px; }}
""")

    def set_user(self, name, role=None):
        self.user.setText(name)
        if role:
            self.role.setText(role)
        initials = "".join(word[0].upper() for word in name.split() if word)[:2]
        self.avatar.setText(initials or "U")

    def closeEvent(self, event):
        ThemeManager.unregister(self._apply_theme)
        super().closeEvent(event)
