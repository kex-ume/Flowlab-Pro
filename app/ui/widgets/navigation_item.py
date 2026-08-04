from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsColorizeEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
)

from app.ui.theme import ThemeManager


class NavigationItem(QFrame):
    """A single selectable entry in the application sidebar."""

    clicked = Signal(str)

    def __init__(self, key: str, title: str, icon: str):
        super().__init__()

        self.key = key
        self.active = False
        self._icon_path = icon

        self.setObjectName("NavigationItem")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(35)
        self.setMaximumHeight(35)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(9, 0, 9, 0)
        layout.setSpacing(9)

        self.icon = QLabel()
        self.icon.setObjectName("NavigationIcon")
        self.icon.setFixedSize(15, 15)
        self.icon.setAlignment(Qt.AlignCenter)
        self.icon.setPixmap(QIcon(icon).pixmap(15, 15))
        self._icon_effect = QGraphicsColorizeEffect(self.icon)
        self.icon.setGraphicsEffect(self._icon_effect)

        self.text = QLabel(title)
        self.text.setObjectName("NavigationText")
        self.text.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        layout.addWidget(self.icon)
        layout.addWidget(self.text, 1)

        ThemeManager.register(self._apply_theme)
        self._apply_theme(ThemeManager.current())

    def set_active(self, active: bool):
        self.active = active
        self._apply_theme(ThemeManager.current())

    def _apply_theme(self, theme):
        c = theme.color
        active_background = c.sidebar_active
        hover_background = c.sidebar_hover
        active_text = c.text_light
        normal_text = c.sidebar_text

        self._icon_effect.setColor(active_text if self.active else normal_text)
        self.setStyleSheet(f"""
QFrame#NavigationItem {{
    background: {active_background if self.active else 'transparent'};
    border: none;
    border-radius: 8px;
}}
QFrame#NavigationItem:hover {{ background: {active_background if self.active else hover_background}; }}
QLabel#NavigationText {{
    background: transparent;
    color: {active_text if self.active else normal_text};
    font-size: 12px;
    font-weight: {600 if self.active else 500};
}}
QLabel#NavigationIcon {{ background: transparent; border: none; }}
""")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.isEnabled():
            self.clicked.emit(self.key)
        super().mousePressEvent(event)

    def closeEvent(self, event):
        ThemeManager.unregister(self._apply_theme)
        super().closeEvent(event)
