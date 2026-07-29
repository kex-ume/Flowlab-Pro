from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QMessageBox,
)

from app.modules.auth.service import AuthService


class LoginDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.user = None

        self.setWindowTitle("FlowLab Pro Login")
        self.resize(350, 180)

        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.username = QLineEdit()

        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)

        form.addRow("Username", self.username)
        form.addRow("Password", self.password)

        layout.addLayout(form)

        self.login_button = QPushButton("Login")
        layout.addWidget(self.login_button)

        self.login_button.clicked.connect(self.login)

        self.password.returnPressed.connect(self.login)

    def login(self):

        service = AuthService()

        user = service.authenticate(
            self.username.text().strip(),
            self.password.text()
        )

        if user is None:
            QMessageBox.warning(
                self,
                "Login",
                "Invalid username or password."
            )
            return

        self.user = user
        self.accept()