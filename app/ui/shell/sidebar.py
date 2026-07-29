from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class Sidebar(QFrame):

    page_selected = Signal(int)

    def __init__(self):
        super().__init__()

        self.setObjectName("Sidebar")
        self.setFixedWidth(260)

        self.buttons = []
        self.current_index = 0

        self.setStyleSheet("""
        QFrame#Sidebar{
            background:#1F2937;
            border:none;
        }

        QLabel#Logo{
            color:white;
            font-size:22px;
            font-weight:700;
            padding:18px;
        }

        QLabel#User{
            color:#D1D5DB;
            padding:15px;
            font-size:12px;
        }

        QLabel#Version{
            color:#9CA3AF;
            padding:10px;
            font-size:11px;
        }

        QPushButton{
            background:transparent;
            border:none;
            border-radius:8px;
            color:white;
            text-align:left;
            padding:12px 16px;
            font-size:14px;
        }

        QPushButton:hover{
            background:#374151;
        }

        QPushButton:checked{
            background:#2563EB;
            font-weight:bold;
        }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(8)

        logo = QLabel("FlowLab Pro")
        logo.setObjectName("Logo")
        logo.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo)

        layout.addSpacing(10)

        self.menu = QVBoxLayout()
        self.menu.setSpacing(6)

        menu_widget = QWidget()
        menu_widget.setLayout(self.menu)

        layout.addWidget(menu_widget)
        layout.addStretch()

        self.user = QLabel("Not signed in")
        self.user.setObjectName("User")
        self.user.setAlignment(Qt.AlignCenter)

        self.version = QLabel("v1.0")
        self.version.setObjectName("Version")
        self.version.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.user)
        layout.addWidget(self.version)

        for item in [
            "🏠 Dashboard",
            "📁 Projects",
            "🧪 Laboratory",
            "📊 Reports",
            "⚙ Settings",
        ]:
            self.add_page(item)

    def add_page(self, title):

        index = len(self.buttons)

        btn = QPushButton(title)
        btn.setCheckable(True)
        btn.setMinimumHeight(42)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed,
        )

        btn.clicked.connect(
            lambda _, i=index: self.select(i)
        )

        self.menu.addWidget(btn)
        self.buttons.append(btn)

        if len(self.buttons) == 1:
            btn.setChecked(True)

    def select(self, index):

        self.current_index = index

        for i, b in enumerate(self.buttons):
            b.setChecked(i == index)

        self.page_selected.emit(index)

    def set_user(self, name, role):
        self.user.setText(f"{name}\n{role}")