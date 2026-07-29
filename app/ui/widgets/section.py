from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from app.ui.theme.colors import Colors
from app.ui.theme.fonts import Fonts


class Section(QFrame):

    def __init__(self, title=""):

        super().__init__()

        self.setObjectName("Section")

        self.setStyleSheet(f"""
        QFrame#Section {{
            background:white;
            border:1px solid {Colors.BORDER};
            border-radius:12px;
        }}
        """)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(15)

        if title:
            self.header = QLabel(title)
            self.header.setFont(Fonts.heading())
            self.header.setStyleSheet(f"""
                color:{Colors.TEXT};
                border:none;
            """)
            self.layout.addWidget(self.header)

    def addWidget(self, widget):
        self.layout.addWidget(widget)

    def addLayout(self, layout):
        self.layout.addLayout(layout)

    def addStretch(self):
        self.layout.addStretch()