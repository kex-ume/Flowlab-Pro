from .colors import Colors


class StyleSheet:

    @staticmethod
    def build():

        c = Colors

        return f"""

QMainWindow {{
    background:{c.WINDOW};
}}

QWidget {{
    background:{c.WINDOW};
    color:{c.TEXT};
    font-family:"Segoe UI";
    font-size:10pt;
}}

QFrame {{
    background:{c.CARD};
    border:1px solid {c.BORDER};
    border-radius:12px;
}}

QGroupBox {{
    background:{c.CARD};
    border:1px solid {c.BORDER};
    border-radius:12px;
    margin-top:14px;
    font-weight:600;
}}

QGroupBox::title {{
    left:16px;
    padding:0 6px;
}}

QPushButton {{
    background:{c.PRIMARY};
    color:white;
    border:none;
    border-radius:8px;
    padding:10px 18px;
    min-height:18px;
}}

QPushButton:hover {{
    background:{c.PRIMARY_HOVER};
}}

QPushButton:pressed {{
    background:{c.PRIMARY_PRESSED};
}}

QLineEdit,
QComboBox,
QDateEdit,
QTextEdit,
QSpinBox,
QDoubleSpinBox {{
    background:white;
    border:1px solid {c.INPUT_BORDER};
    border-radius:8px;
    padding:8px;
}}

QLineEdit:focus,
QComboBox:focus,
QDateEdit:focus,
QTextEdit:focus {{
    border:2px solid {c.INPUT_FOCUS};
}}

QTableWidget {{
    background:white;
    border:1px solid {c.BORDER};
    gridline-color:{c.TABLE_GRID};
    alternate-background-color:#F9FAFB;
    selection-background-color:{c.PRIMARY};
}}

QHeaderView::section {{
    background:{c.TABLE_HEADER};
    border:none;
    border-bottom:1px solid {c.BORDER};
    padding:10px;
    font-weight:600;
}}

QScrollArea {{
    border:none;
    background:transparent;
}}

QStatusBar {{
    background:white;
}}

QMenu {{
    background:white;
}}

QToolTip {{
    background:#111827;
    color:white;
    border:none;
}}
"""