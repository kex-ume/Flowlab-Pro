from turtle import title

from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget,
)

from app.ui.widgets.page_header import PageHeader
from app.ui.widgets.toolbar import ToolBar

from app.ui.theme import ThemeManager


class BasePage(QWidget):
    def __init__(self, title: str, subtitle: str = ""):
        super().__init__()

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(24, 24, 24, 24)
        self.main_layout.setSpacing(20)

        self.header = PageHeader(title, subtitle)

        if title.strip() or subtitle.strip():
            self.main_layout.addWidget(self.header)
        else:
            self.header.hide()

        self.toolbar = ToolBar()
        self.main_layout.addWidget(self.toolbar)

        self.body = QWidget()

        self.content_layout = QVBoxLayout(self.body)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(20)

        self.main_layout.addWidget(self.body, 1)

        ThemeManager.register(self._apply_theme)
        self._apply_theme(ThemeManager.current())

    # ---------------------------------------------------------
    # Theme
    # ---------------------------------------------------------

    def _apply_theme(self, theme):
        c = theme.color

        self.setStyleSheet(
            f"""
            BasePage {{
                background:{c.window};
            }}

            QWidget {{
                background:{c.window};
                color:{c.text};
            }}
            """
        )

    # ---------------------------------------------------------
    # Toolbar helpers
    # ---------------------------------------------------------

    def add_toolbar_widget(self, widget):
        self.toolbar.add(widget)

    def add_toolbar_stretch(self):
        self.toolbar.stretch()

    # ---------------------------------------------------------
    # Cleanup
    # ---------------------------------------------------------

    def closeEvent(self, event):
        ThemeManager.unregister(self._apply_theme)
        super().closeEvent(event)
        