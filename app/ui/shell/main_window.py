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
from app.ui.pages.feature_page import Feature, FeaturePage
from app.ui.pages.governance_pages import (
    KnowledgeBasePage,
    MethodConfigurationPage,
    QualityPage,
    ReminderPage,
)
from app.ui.pages.projects.projects_page import ProjectsPage

from app.modules.laboratory.page import LaboratoryPage
from app.modules.laboratory.calibration_programme_page import CalibrationProgrammePage
from app.modules.reports.page import ReportsPage
from app.modules.user_management.page import UserManagementPage
from app.modules.uncertainty.page import UncertaintyPage

from app.modules.auth.permissions import Permissions


class MainWindow(QMainWindow):

    PAGE_TITLES = {
        "dashboard": "Dashboard",
        "analytics": "Analytics",
        "iso17025": "ISO 17025",
        "projects": "Projects",
        "laboratory": "Laboratory",
        "programme": "Calibration Programme",
        "tools": "Tools & Calculators",
        "standards": "Standards & Procedures",
        "database": "Database & Records",
        "flowpro": "FlowPro_Wiz",
        "settings": "Settings",
        "reminders": "Reminder Console",
        "knowledge": "Knowledge Base",
        "reports": "Reports",
        "users": "User Management",
    }

    PAGE_SUBTITLES = {
        "dashboard": "Welcome back — here's today's calibration and compliance picture",
        "analytics": "Calibration throughput, job status and measurement uncertainty",
        "iso17025": "Traceability, uncertainty, compliance and CAPA management",
        "projects": "All calibration jobs across clients",
        "laboratory": "Laboratory readiness by discipline",
        "programme": "Scheduled equipment calibration and certificate validity",
        "tools": "Metrology calculators and certificate tools",
        "standards": "Controlled documents and procedures",
        "database": "Laboratory records and archives",
        "flowpro": "Flow computer integration",
        "settings": "System configuration",
        "reminders": "Calibration, certificate and quality actions requiring attention",
        "knowledge": "Controlled laboratory reference content",
        "reports": "Equipment, calibration and maintenance reports",
        "users": "Manage user access and functional roles",
    }

    def __init__(self):
        super().__init__()

        self.current_user = None

        self.setWindowTitle("FlowLab Pro")
        self.resize(1500, 900)

        self.statusBar().showMessage("Ready")
        # The approved console shell has no permanent status-bar strip.
        self.statusBar().hide()

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
        self.calibration_programme_page = CalibrationProgrammePage()
        self.reports_page = ReportsPage()
        self.analytics_page = FeaturePage(
            "Calibration Throughput & Job Status",
            "Operational analytics defined by the FlowLab Pro SDS.",
            (
                Feature("Operational workload", "Review completed, pending and overdue calibration jobs.", "projects"),
                Feature("Equipment performance", "Review calibration frequency, upcoming due dates and overdue assets.", "laboratory"),
                Feature("Management reporting", "Open export-ready laboratory reports.", "reports"),
            ),
        )
        self.iso_page = QualityPage()
        self.tools_page = UncertaintyPage()
        self.standards_page = MethodConfigurationPage()
        self.database_page = FeaturePage(
            "Laboratory Records & Archives",
            "Queryable calibration history, maintenance records and issued documents.",
            (
                Feature("Equipment register", "Open the complete laboratory equipment register.", "laboratory"),
                Feature("Calibration history", "Open calibration reports and exported records.", "reports"),
                Feature("Customer projects", "Open active and historical calibration jobs.", "projects"),
            ),
        )
        self.flowpro_page = FeaturePage(
            "FlowPro_Wiz Integration",
            "Flow-computer integration is reserved for laboratory-approved data exchange.",
            (
                Feature("Integration readiness", "Review the approved equipment chain before an import.", "laboratory"),
                Feature("Job workspace", "Open calibration jobs that may receive imported data.", "projects"),
                Feature("Data evidence", "Open records available for controlled export.", "reports"),
            ),
        )
        self.settings_page = FeaturePage(
            "System Configuration",
            "Manage theme preferences, access control and laboratory system defaults.",
            (
                Feature("User management", "Open user accounts and role assignments.", "users"),
                Feature("Appearance", "Use the profile menu to choose the light or dark theme.", "dashboard"),
                Feature("System reports", "Open report export and record controls.", "reports"),
            ),
        )
        self.reminders_page = ReminderPage()
        self.knowledge_page = KnowledgeBasePage()

        self.user_management_page = None

        self.page_lookup = {}

        self._add_page("dashboard", self.dashboard_page)
        self._add_page("analytics", self.analytics_page)
        self._add_page("iso17025", self.iso_page)
        self._add_page("projects", self.projects_page)
        self._add_page("laboratory", self.laboratory_page)
        self._add_page("programme", self.calibration_programme_page)
        self._add_page("tools", self.tools_page)
        self._add_page("standards", self.standards_page)
        self._add_page("database", self.database_page)
        self._add_page("flowpro", self.flowpro_page)
        self._add_page("settings", self.settings_page)
        self._add_page("reminders", self.reminders_page)
        self._add_page("knowledge", self.knowledge_page)
        self._add_page("reports", self.reports_page)

        self.sidebar.page_selected.connect(self.show_page)
        self.dashboard_page.action_requested.connect(self._handle_dashboard_action)
        self.topbar.search_requested.connect(self._search)
        self.topbar.notifications_requested.connect(
            lambda: self._handle_dashboard_action("reminders")
        )
        for page in (
            self.analytics_page,
            self.database_page,
            self.flowpro_page,
            self.settings_page,
        ):
            page.action_requested.connect(self._handle_dashboard_action)

    # ======================================================

    def _add_page(self, key, page):
        self.page_lookup[key] = page
        self.pages.addWidget(page)

    def show_page(self, key):

        page = self.page_lookup.get(key)

        if page is not None:
            self.pages.setCurrentWidget(page)
            title = self.PAGE_TITLES.get(key, key.replace("_", " ").title())
            self.topbar.title.setText(title)
            self.topbar.breadcrumb.setText(
                self.PAGE_SUBTITLES.get(key, "FlowLab Pro workspace")
            )

    def _handle_dashboard_action(self, action):
        """Route an approved HTML dashboard click into a native module."""
        if action in self.page_lookup:
            self.show_page(action)
            if action in self.sidebar.items:
                self.sidebar.select(action)

    def _search(self, query):
        """Use the laboratory module as the live record-search destination."""
        self.show_page("laboratory")
        self.laboratory_page.table.setFocus()
        self.statusBar().showMessage(
            f"Search requested for ‘{query}’. Review matching laboratory records.",
            5000,
        )

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
        self.topbar.set_user(user.full_name, user.role_name)
        self.tools_page.set_role(user.role_name)

        if (
            Permissions.can(user.role_name, "user_management")
            and self.user_management_page is None
        ):

            self.user_management_page = UserManagementPage()

            self._add_page(
                "users",
                self.user_management_page,
            )

            # User administration remains available through Settings.  It is
            # deliberately not added to the permanent reference sidebar.

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
