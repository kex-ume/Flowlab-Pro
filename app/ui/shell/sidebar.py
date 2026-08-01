from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import ThemeManager
from app.ui.widgets.navigation_item import NavigationItem

import app.ui.resources.resources_rc

class Sidebar(QFrame):

    page_selected = Signal(str)

    SIDEBAR_WIDTH = 260

    def __init__(self):
        super().__init__()

        self.setObjectName("Sidebar")
        self.setFixedWidth(self.SIDEBAR_WIDTH)

        self.items = {}
        self.current_key = None

        self._build_ui()

        ThemeManager.register(self._apply_theme)
        self._apply_theme(ThemeManager.current())

    # =====================================================
       #SELECT
    # =====================================================
    def select(self, key: str):

        if key not in self.items:
            return

        self.current_key = key

        for page_key, item in self.items.items():
            item.set_active(page_key == key)

        self.page_selected.emit(key)

    def set_user(
            self,
            name: str,
            role: str,
        ):

            self.user.setText(
                f"{name}\n{role}"
    )

    def closeEvent(self, event):

        ThemeManager.unregister(self._apply_theme)

        super().closeEvent(event)
   # =====================================================
        #ADD PAGE
    # =====================================================
    def add_page(
        self,
        key: str,
        title: str,
        icon: str,
        enabled: bool = True,
    ):

        item = NavigationItem(
            key,
            title,
            icon,
        )

        item.setEnabled(enabled)

        if enabled:
            item.clicked.connect(self.select)

        self.menu_layout.addWidget(item)

        self.items[key] = item


    # =====================================================
    def _build_ui(self):

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 20, 18, 20)
        layout.setSpacing(8)

    

    # ======================================================
    # Brand
    # ======================================================

        self.logo_icon = QLabel()
        self.logo_icon.setPixmap(
            QIcon(":/icons/flowlab_logo.svg").pixmap(34, 34)
    )
        self.logo_icon.setAlignment(Qt.AlignCenter)

        self.logo = QLabel("FlowLab Pro")
        self.logo.setObjectName("SidebarLogo")
        self.logo.setAlignment(Qt.AlignCenter)

        self.subtitle = QLabel("ISO/IEC 17025 Calibration")
        self.subtitle.setObjectName("SidebarSubtitle")
        self.subtitle.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.logo_icon)
        layout.addWidget(self.logo)
        layout.addWidget(self.subtitle)

        layout.addSpacing(18)

    # ======================================================
    # Menu
    # ======================================================

        self.menu_layout = QVBoxLayout()
        self.menu_layout.setSpacing(5)

        menu = QWidget()
        menu.setLayout(self.menu_layout)

        layout.addWidget(menu)

    # ------------------------------------------------------

        self.main_section = QLabel("MAIN")
        self.main_section.setObjectName("SidebarSection")
        self.menu_layout.addWidget(self.main_section)

        self.add_page(
            "dashboard",
            "Dashboard",
            ":/icons/dashboard.svg",
        )

        self.add_page(
            "analytics",
            "Analytics",
            ":/icons/analytics.svg",
            enabled=False,
        )

        self.add_page(
            "iso17025",
            "ISO 17025",
            ":/icons/shield.svg",
            enabled=False,
        )

        self.add_page(
            "projects",
            "Projects",
            ":/icons/projects.svg",
        )

        self.menu_layout.addSpacing(12)

        # ------------------------------------------------------

        self.operations_section = QLabel("OPERATIONS")
        self.operations_section.setObjectName("SidebarSection")
        self.menu_layout.addWidget(self.operations_section)

        self.add_page(
            "laboratory",
            "Laboratory",
            ":/icons/laboratory.svg",
        )

        self.add_page(
            "tools",
            "Tools & Calculators",
            ":/icons/calculator.svg",
            enabled=False,
        )

        self.add_page(
            "standards",
            "Standards & Procedures",
            ":/icons/documents.svg",
            enabled=False,
        )

        self.add_page(
            "database",
            "Database & Records",
            ":/icons/database.svg",
            enabled=False,
        )

        self.menu_layout.addSpacing(12)

        # ------------------------------------------------------

        self.system_section = QLabel("SYSTEM")
        self.system_section.setObjectName("SidebarSection")
        self.menu_layout.addWidget(self.system_section)

        self.add_page(
            "settings",
            "Settings",
            ":/icons/settings.svg",
            enabled=False,
        )

        layout.addStretch()

        # ======================================================
        # Accreditation Card
        # ======================================================

        self.iso_card = QLabel(
            "ISO/IEC 17025:2017\n"
            "Accredited • Flow Calibration"
        )
        self.iso_card.setObjectName("IsoCard")
        self.iso_card.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.iso_card)

        # ======================================================
        # User
        # ======================================================

        self.user = QLabel("Not signed in")
        self.user.setObjectName("SidebarUser")

        layout.addWidget(self.user)

        # ======================================================
        # Organisation
        # ======================================================

        self.org = QLabel("EATL")
        self.org.setObjectName("SidebarVersion")

        layout.addWidget(self.org)

        self.select("dashboard")
        # =====================================================

    def _apply_theme(self, theme):

        c = theme.color

        self.setStyleSheet(f"""

QFrame#Sidebar {{
    background:qlineargradient(
        x1:0,y1:0,
        x2:0,y2:1,
        stop:0 #173A59,
        stop:1 #0F2847
    );
    border:none;
}}

QLabel#SidebarLogo {{
    background:transparent;
    color:white;
    font-size:24px;
    font-weight:700;
}}

QLabel#SidebarSubtitle {{
    background:transparent;
    color:#B7C7D7;
    font-size:11px;
}}

QLabel#SidebarSection {{
    background:transparent;
    color:#7E93AA;
    font-size:10px;
    font-weight:700;
    letter-spacing:1px;
    padding-top:12px;
    padding-bottom:6px;
}}

QLabel#IsoCard {{
    background:rgba(255,255,255,0.05);
    border:1px solid rgba(255,255,255,0.08);
    border-radius:12px;
    color:white;
    padding:14px;
    font-size:11px;
    font-weight:600;
}}

QLabel#SidebarUser {{
    background:transparent;
    color:white;
    font-size:13px;
    font-weight:700;
    padding-top:12px;
}}

QLabel#SidebarVersion {{
    background:transparent;
    color:#8EA7C0;
    font-size:11px;
}}

NavigationItem {{
    background:transparent;
}}

NavigationItem:hover {{
    background:rgba(255,255,255,0.08);
    border-radius:10px;
}}

""")
    # =====================================================

    def closeEvent(self, event):

        ThemeManager.unregister(self._apply_theme)

        super().closeEvent(event)