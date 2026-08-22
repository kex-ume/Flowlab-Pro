from app.ui.base_page import BasePage
from app.modules.laboratory.page import LaboratoryPage


class EquipmentPage(BasePage):
    def __init__(self):
        super().__init__(
            "Equipment",
            "Manage laboratory equipment"
        )

        self.content_layout.addWidget(LaboratoryPage(self), 1)
