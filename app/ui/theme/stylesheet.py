from __future__ import annotations

from app.ui.theme.base import Theme


class StyleSheet:
    @staticmethod
    def build(theme: Theme) -> str:
        c = theme.color
        r = theme.radius

        return f"""
/* ----------------------------------------------------------
   Global
---------------------------------------------------------- */

QMainWindow {{
    background: {c.window};
}}

QWidget {{
    background: {c.window};
    color: {c.text};
    font-family: "{theme.font.family}";
    font-size: {theme.font.body}pt;
}}

/* ----------------------------------------------------------
   Containers
---------------------------------------------------------- */

QFrame {{
    background: {c.card};
    border: 1px solid {c.border};
    border-radius: {r.md}px;
}}

QGroupBox {{
    background: {c.card};
    border: 1px solid {c.border};
    border-radius: {r.md}px;
    margin-top: 14px;
    font-weight: 600;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 16px;
    padding: 0 6px;
    color: {c.text};
}}

/* ----------------------------------------------------------
   Buttons
---------------------------------------------------------- */

QPushButton {{
    background: {c.primary};
    color: white;
    border: none;
    border-radius: {r.sm}px;
    padding: 10px 18px;
    min-height: 18px;
}}

QPushButton:hover {{
    background: {c.primary_hover};
}}

QPushButton:pressed {{
    background: {c.primary_pressed};
}}

QPushButton:disabled {{
    background: {c.border};
    color: {c.text_secondary};
}}

/* ----------------------------------------------------------
   Inputs
---------------------------------------------------------- */

QLineEdit,
QComboBox,
QDateEdit,
QTextEdit,
QPlainTextEdit,
QSpinBox,
QDoubleSpinBox {{
    background: {c.input};
    color: {c.text};
    border: 1px solid {c.input_border};
    border-radius: {r.sm}px;
    padding: 8px;
}}

QLineEdit:focus,
QComboBox:focus,
QDateEdit:focus,
QTextEdit:focus,
QPlainTextEdit:focus,
QSpinBox:focus,
QDoubleSpinBox:focus {{
    border: 2px solid {c.input_focus};
}}

/* ----------------------------------------------------------
   Tables / Lists
---------------------------------------------------------- */

QTableWidget,
QTableView,
QTreeView,
QListView {{
    background: {c.surface};
    color: {c.text};
    border: 1px solid {c.border};
    gridline-color: {c.table_grid};
    alternate-background-color: {c.card};
    selection-background-color: {c.primary};
    selection-color: white;
}}

QHeaderView::section {{
    background: {c.table_header};
    color: {c.text};
    border: none;
    border-bottom: 1px solid {c.border};
    padding: 10px;
    font-weight: 600;
}}

QTableWidget::item:hover,
QTableView::item:hover {{
    background: {c.divider};
}}

/* ----------------------------------------------------------
   Scroll Bars
---------------------------------------------------------- */

QScrollArea {{
    background: transparent;
    border: none;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
}}

QScrollBar::handle:vertical {{
    background: {c.border};
    border-radius: 5px;
    min-height: 30px;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
}}

QScrollBar::handle:horizontal {{
    background: {c.border};
    border-radius: 5px;
    min-width: 30px;
}}

/* ----------------------------------------------------------
   Tabs
---------------------------------------------------------- */

QTabWidget::pane {{
    border: 1px solid {c.border};
}}

QTabBar::tab {{
    background: {c.surface};
    color: {c.text};
    border: 1px solid {c.border};
    padding: 8px 16px;
}}

QTabBar::tab:selected {{
    background: {c.primary};
    color: white;
}}

/* ----------------------------------------------------------
   Menus
---------------------------------------------------------- */

QMenu {{
    background: {c.surface};
    color: {c.text};
    border: 1px solid {c.border};
}}

QMenu::item:selected {{
    background: {c.primary};
    color: white;
}}

QToolTip {{
    background: {c.sidebar};
    color: {c.text_light};
    border: 1px solid {c.border};
}}

/* ----------------------------------------------------------
   Status Bar
---------------------------------------------------------- */

QStatusBar {{
    background: {c.surface};
    border-top: 1px solid {c.border};
}}
"""