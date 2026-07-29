from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme.fonts import Fonts


class PageHeader(QWidget):

    def __init__(self, title, subtitle=""):

        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.title = QLabel(title)
        self.title.setFont(Fonts.title())

        self.subtitle = QLabel(subtitle)
        self.subtitle.setFont(Fonts.subtitle())
        self.subtitle.setStyleSheet("color:#6B7280;")

        self.title.setAlignment(Qt.AlignLeft)
        self.subtitle.setAlignment(Qt.AlignLeft)

        layout.addWidget(self.title)

        if subtitle:
            layout.addWidget(self.subtitle)

        layout.addSpacing(10)