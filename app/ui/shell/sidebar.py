"""Persistent navigation matching the approved FlowLab console shell."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import ThemeManager
from app.ui.widgets.navigation_item import NavigationItem

import app.ui.resources.resources_rc


class Sidebar(QFrame):
    """The stable, compact application navigation shell."""

    page_selected = Signal(str)
    SIDEBAR_WIDTH = 208

    def __init__(self):
        super().__init__()
        self.setObjectName("Sidebar")
        self.setFixedWidth(self.SIDEBAR_WIDTH)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        self.items = {}
        self.current_key = None
        self._build_ui()
        ThemeManager.register(self._apply_theme)
        self._apply_theme(ThemeManager.current())

    def sizeHint(self):
        return QSize(self.SIDEBAR_WIDTH, super().sizeHint().height())

    def select(self, key: str):
        if key not in self.items:
            return
        self.current_key = key
        for page_key, item in self.items.items():
            item.set_active(page_key == key)
        self.page_selected.emit(key)

    def set_user(self, name: str, role: str):
        """Retain the shell contract; identity is displayed in the top bar."""
        self.setToolTip(f"Signed in as {name} ({role})")

    def add_page(self, key: str, title: str, icon: str):
        item = NavigationItem(key, title, icon)
        item.clicked.connect(self.select)
        self.menu_layout.addWidget(item)
        self.items[key] = item

    def _section_label(self, text: str):
        label = QLabel(text)
        label.setObjectName("SidebarSection")
        self.menu_layout.addWidget(label)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 20, 0, 16)
        layout.setSpacing(0)

        brand = QHBoxLayout()
        brand.setContentsMargins(16, 0, 16, 18)
        brand.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(QIcon(":/icons/flowlab_logo.svg").pixmap(32, 32))
        logo.setFixedSize(32, 32)
        logo.setAlignment(Qt.AlignCenter)
        brand_text = QVBoxLayout()
        brand_text.setSpacing(1)
        brand_name = QLabel("FlowLab Pro")
        brand_name.setObjectName("SidebarLogo")
        brand_subtitle = QLabel("ISO/IEC 17025 Calibration")
        brand_subtitle.setObjectName("SidebarSubtitle")
        brand_text.addWidget(brand_name)
        brand_text.addWidget(brand_subtitle)
        brand.addWidget(logo)
        brand.addLayout(brand_text, 1)
        layout.addLayout(brand)

        divider = QFrame()
        divider.setObjectName("SidebarDivider")
        divider.setFixedHeight(1)
        layout.addWidget(divider)
        layout.addSpacing(16)

        menu = QWidget()
        menu.setObjectName("SidebarMenu")
        self.menu_layout = QVBoxLayout(menu)
        self.menu_layout.setContentsMargins(10, 0, 10, 0)
        self.menu_layout.setSpacing(2)
        layout.addWidget(menu)

        self._section_label("MAIN")
        self.add_page("dashboard", "Dashboard", ":/icons/dashboard.svg")
        self.add_page("analytics", "Analytics", ":/icons/analytics.svg")
        self.add_page("iso17025", "ISO 17025", ":/icons/shield.svg")
        self.add_page("projects", "Projects", ":/icons/projects.svg")
        self.menu_layout.addSpacing(16)

        self._section_label("OPERATIONS")
        self.add_page("laboratory", "Laboratory", ":/icons/laboratory.svg")
        self.add_page("programme", "Calibration Programme", ":/icons/notification.svg")
        self.add_page("reminders", "Reminders", ":/icons/notification.svg")
        self.add_page("tools", "Tools & Calculators", ":/icons/calculator.svg")
        self.add_page("standards", "Standards & Procedures", ":/icons/documents.svg")
        self.add_page("database", "Database & Records", ":/icons/database.svg")
        self.menu_layout.addSpacing(16)

        self._section_label("SYSTEM")
        self.add_page("knowledge", "Knowledge Base", ":/icons/documents.svg")
        self.add_page("flowpro", "FlowPro_Wiz", ":/icons/calculator.svg")
        self.add_page("settings", "Settings", ":/icons/settings.svg")
        layout.addStretch(1)

        footer = QFrame()
        footer.setObjectName("SidebarFoot")
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(16, 12, 16, 0)
        footer_layout.setSpacing(0)
        accreditation = QLabel("ISO/IEC 17025:2017\nAccredited · Flow Calibration")
        accreditation.setObjectName("AccreditationText")
        accreditation.setWordWrap(True)
        org = QLabel("EATL T&CL SBU")
        org.setObjectName("OrgName")
        location = QLabel("Eket, Akwa Ibom")
        location.setObjectName("OrgLocation")
        footer_layout.addWidget(accreditation)
        footer_layout.addSpacing(10)
        footer_layout.addWidget(org)
        footer_layout.addWidget(location)
        layout.addWidget(footer)

        self.select("dashboard")

    def _apply_theme(self, theme):
        c = theme.color
        self.setStyleSheet(f"""
QFrame#Sidebar {{ background: {c.sidebar}; border-right: 1px solid rgba(255,255,255,0.06); }}
QWidget#SidebarMenu, QFrame#Sidebar QLabel {{ background: transparent; border: none; }}
QFrame#SidebarDivider, QFrame#SidebarFoot {{ border-top: 1px solid rgba(255,255,255,0.08); }}
QLabel#SidebarLogo {{ color: {c.sidebar_text}; font-size: 14px; font-weight: 700; }}
QLabel#SidebarSubtitle {{ color: {c.sidebar_text_secondary}; font-size: 8px; font-weight: 500; }}
QLabel#SidebarSection {{ color: #5E7B93; font-size: 9px; font-weight: 700; letter-spacing: 0.8px; padding: 0 8px 7px; }}
QLabel#AccreditationText {{ color: #B9CBDA; font-size: 9px; line-height: 1.3; }}
QLabel#AccreditationText::first-line {{ color: {c.sidebar_text}; font-weight: 700; }}
QLabel#OrgName {{ color: {c.sidebar_text}; font-size: 11px; font-weight: 600; }}
QLabel#OrgLocation {{ color: #84A0B6; font-size: 10px; margin-top: 1px; }}
""")

    def closeEvent(self, event):
        ThemeManager.unregister(self._apply_theme)
        super().closeEvent(event)
