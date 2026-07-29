from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QWidget,
)

from app.ui.shell.sidebar import Sidebar

from app.ui.pages.home.dashboard_page import DashboardPage
from app.ui.pages.projects.projects_page import ProjectsPage

from app.modules.laboratory.page import LaboratoryPage
from app.modules.reports.page import ReportsPage
from app.modules.user_management.page import UserManagementPage

from app.modules.auth.permissions import Permissions


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.current_user = None

        self.setWindowTitle("FlowLab Pro")
        self.resize(1500, 900)

        self.statusBar().showMessage("Ready")

        central = QWidget()
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = Sidebar()
        layout.addWidget(self.sidebar)

        self.pages = QStackedWidget()
        layout.addWidget(self.pages, 1)

        self.dashboard_page = DashboardPage()
        self.projects_page = ProjectsPage()
        self.laboratory_page = LaboratoryPage()
        self.reports_page = ReportsPage()

        self.user_management_page = None

        self.page_map = [
            self.dashboard_page,
            self.projects_page,
            self.laboratory_page,
            self.reports_page,
        ]

        for page in self.page_map:
            self.pages.addWidget(page)

        self.sidebar.page_selected.connect(self.pages.setCurrentIndex)

    def initialize(self, user):

        self.current_user = user

        self.setWindowTitle(
            f"FlowLab Pro — {user.full_name} ({user.role_name})"
        )

        self.statusBar().showMessage(
            f"Logged in as {user.full_name}"
        )

        self.sidebar.set_user(
            user.full_name,
            user.role_name,
        )

        if (
            Permissions.can(user.role_name, "user_management")
            and self.user_management_page is None
        ):
            self.user_management_page = UserManagementPage()
            self.pages.addWidget(self.user_management_page)

            if hasattr(self.sidebar, "add_page"):
                self.sidebar.add_page("👥 User Management")

    def can(self, permission):
        return Permissions.can(
            self.current_user.role_name,
            permission,
        )

    def require(self, permission):

        if self.can(permission):
            return True

        QMessageBox.warning(
            self,
            "Access Denied",
            "You do not have permission to access this feature.",
        )

        return False