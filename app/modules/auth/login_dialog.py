from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QLabel,
)

from app.modules.auth.service import AuthService
from app.ui.theme import ThemeManager


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.user = None

        self.setWindowTitle("FlowLab Pro Login")
        self.setFixedSize(420, 240)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        self.title = QLabel("FlowLab Pro")
        self.title.setObjectName("LoginTitle")
        self.title.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.title)

        form = QFormLayout()
        form.setSpacing(12)

        self.username = QLineEdit()

        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)

        form.addRow("Username", self.username)
        form.addRow("Password", self.password)

        layout.addLayout(form)

        self.login_button = QPushButton("Sign In")
        self.login_button.setMinimumHeight(42)

        layout.addWidget(self.login_button)

        self.login_button.clicked.connect(self.login)
        self.password.returnPressed.connect(self.login)

        ThemeManager.register(self._apply_theme)
        self._apply_theme(ThemeManager.current())

    # ---------------------------------------------------------
    # Theme
    # ---------------------------------------------------------

    def _apply_theme(self, theme):
        c = theme.color

        self.setStyleSheet(
            f"""
            QDialog {{
                background:{c.window};
            }}

            QLabel#LoginTitle {{
                background:transparent;
                color:{c.text};
                font-size:24px;
                font-weight:700;
            }}

            QLabel {{
                background:transparent;
                color:{c.text};
            }}

            QLineEdit {{
                background:{c.input_bg};
                color:{c.text};
                border:1px solid {c.input_border};
                border-radius:8px;
                padding:8px;
            }}

            QLineEdit:focus {{
                border:1px solid {c.primary};
            }}

            QPushButton {{
                background:{c.primary};
                color:white;
                border:none;
                border-radius:8px;
                padding:10px;
                font-weight:600;
            }}

            QPushButton:hover {{
                background:{c.primary_hover};
            }}
            """
        )

    # ---------------------------------------------------------
    # Login
    # ---------------------------------------------------------

    def login(self):
        service = AuthService()

        user = service.authenticate(
            self.username.text().strip(),
            self.password.text(),
        )

        if user is None:
            QMessageBox.warning(
                self,
                "Login",
                "Invalid username or password.",
            )
            return

        self.user = user
        self.accept()

    # ---------------------------------------------------------
    # Cleanup
    # ---------------------------------------------------------

    def closeEvent(self, event):
        ThemeManager.unregister(self._apply_theme)
        super().closeEvent(event)
