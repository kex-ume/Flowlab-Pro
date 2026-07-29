from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget,
)

from app.ui.widgets.page_header import PageHeader
from app.ui.widgets.toolbar import ToolBar


class BasePage(QWidget):

    def __init__(self, title, subtitle=""):

        super().__init__()

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(24, 24, 24, 24)
        self.main_layout.setSpacing(20)

        self.header = PageHeader(title, subtitle)
        self.main_layout.addWidget(self.header)

        self.toolbar = ToolBar()
        self.main_layout.addWidget(self.toolbar)

        self.body = QWidget()

        self.content_layout = QVBoxLayout(self.body)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(20)

        self.main_layout.addWidget(self.body, 1)

    def add_toolbar_widget(self, widget):
        self.toolbar.add(widget)

    def add_toolbar_stretch(self):
        self.toolbar.stretch()