from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QStackedWidget,
)

from app.ui.shell.topbar import TopBar
from app.ui.shell.sidebar import Sidebar

from app.ui.pages.home.dashboard_page import DashboardPage
from app.ui.pages.projects.projects_page import ProjectsPage
from app.ui.pages.laboratory.equipment_page import EquipmentPage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("FlowLab Pro")
        self.resize(1400, 850)

        self.statusBar().showMessage("Ready")

        # ======================================================
        # Central Widget
        # ======================================================
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # ======================================================
        # Main Vertical Layout
        # ======================================================
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ======================================================
        # Top Bar
        # ======================================================
        self.topbar = TopBar()
        main_layout.addWidget(self.topbar)

        # ======================================================
        # Main Content Layout
        # ======================================================
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        main_layout.addLayout(content_layout)

        # ======================================================
        # Sidebar
        # ======================================================
        self.navigation = Sidebar()
        content_layout.addWidget(self.navigation)

        # ======================================================
        # Page Stack
        # ======================================================
        self.pages = QStackedWidget()
        content_layout.addWidget(self.pages)

        # ======================================================
        # Pages
        # ======================================================
        self.pages.addWidget(DashboardPage())      # Index 0
        self.pages.addWidget(ProjectsPage())       # Index 1
        self.pages.addWidget(EquipmentPage())      # Index 2

        # ======================================================
        # Navigation
        # ======================================================
        self.navigation.page_selected.connect(
            self.pages.setCurrentIndex
        )