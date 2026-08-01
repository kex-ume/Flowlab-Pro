from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.ui.shell.sidebar import Sidebar
from app.ui.shell.topbar import TopBar

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

        # ======================================================
        # Central Widget
        # ======================================================

        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ======================================================
        # Sidebar
        # ======================================================

        self.sidebar = Sidebar()
        root_layout.addWidget(self.sidebar)

        # ======================================================
        # Right Panel
        # ======================================================

        right_panel = QWidget()

        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.topbar = TopBar()
        right_layout.addWidget(self.topbar)

        self.pages = QStackedWidget()
        right_layout.addWidget(self.pages, 1)

        root_layout.addWidget(right_panel, 1)

        # ======================================================
        # Pages
        # ======================================================

        self.dashboard_page = DashboardPage()
        self.projects_page = ProjectsPage()
        self.laboratory_page = LaboratoryPage()
        self.reports_page = ReportsPage()

        self.user_management_page = None

        self.page_lookup = {}

        self._add_page("dashboard", self.dashboard_page)
        self._add_page("projects", self.projects_page)
        self._add_page("laboratory", self.laboratory_page)
        self._add_page("reports", self.reports_page)

        self.sidebar.page_selected.connect(self.show_page)

    # ======================================================

    def _add_page(self, key, page):
        self.page_lookup[key] = page
        self.pages.addWidget(page)

    def show_page(self, key):

        page = self.page_lookup.get(key)

        if page is not None:
            self.pages.setCurrentWidget(page)

    # ======================================================

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

        self.topbar.title.setText("Dashboard")
        self.topbar.set_user(user.full_name)

        if (
            Permissions.can(user.role_name, "user_management")
            and self.user_management_page is None
        ):

            self.user_management_page = UserManagementPage()

            self._add_page(
                "users",
                self.user_management_page,
            )

            self.sidebar.add_page(
                "users",
                "User Management",
                ":/icons/user.svg",
                True,
            )

    # ======================================================

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