from PySide6.QtWidgets import (
    QLabel,
)
from PySide6.QtCore import Qt

from app.ui.base_page import BasePage


class ProjectsPage(BasePage):
    def __init__(self):
        super().__init__(
            "Projects",
            "Manage laboratory projects"
        )

        placeholder = QLabel(
            "Projects module is under development."
        )
        placeholder.setAlignment(Qt.AlignCenter)

        self.content_layout.addWidget(placeholder)
        self.content_layout.addStretch()