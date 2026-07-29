from PySide6.QtWidgets import QListWidget


class NavigationPanel(QListWidget):
    def __init__(self):
        super().__init__()

        self.setFixedWidth(200)

        self.addItems([
            "Dashboard",
            "Projects",
            "Equipment",
        ])

        self.setCurrentRow(0)