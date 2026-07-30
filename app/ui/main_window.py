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

from app.ui.theme import (
    ThemeManager,
    StyleSheet,
)


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
        # Main Layout
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
        # Content
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
        # Pages
        # ======================================================

        self.pages = QStackedWidget()
        content_layout.addWidget(self.pages)

        self.pages.addWidget(DashboardPage())     # dashboard
        self.pages.addWidget(ProjectsPage())      # projects
        self.pages.addWidget(EquipmentPage())     # laboratory

        self.page_map = {
            "dashboard": 0,
            "projects": 1,
            "laboratory": 2,
        }

        # ======================================================
        # Navigation
        # ======================================================

        self.navigation.page_selected.connect(self.change_page)

        # ======================================================
        # Theme
        # ======================================================

        ThemeManager.register(self.apply_theme)
        self.apply_theme(ThemeManager.current())

    def apply_theme(self, theme):
        self.setStyleSheet(
            StyleSheet.build(theme)
        )

    def change_page(self, key: str):
        index = self.page_map.get(key)

        if index is not None:
            self.pages.setCurrentIndex(index)

    def closeEvent(self, event):
        ThemeManager.unregister(self.apply_theme)
        super().closeEvent(event)