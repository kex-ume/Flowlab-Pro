from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from app.ui.base_page import BasePage


class EquipmentPage(BasePage):
    def __init__(self):
        super().__init__(
            "Equipment",
            "Manage laboratory equipment"
        )

        placeholder = QLabel(
            "Equipment module is under development."
        )
        placeholder.setAlignment(Qt.AlignCenter)

        self.content_layout.addWidget(placeholder)
        self.content_layout.addStretch()