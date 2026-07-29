from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QMessageBox,
)

from app.modules.auth.service import AuthService
from app.database.database import get_connection


class ChangePasswordDialog(QDialog):

    def __init__(self, user, parent=None):
        super().__init__(parent)

        self.user = user

        self.setWindowTitle("Change Password")

        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.password1 = QLineEdit()
        self.password1.setEchoMode(QLineEdit.Password)

        self.password2 = QLineEdit()
        self.password2.setEchoMode(QLineEdit.Password)

        form.addRow("New Password", self.password1)
        form.addRow("Confirm", self.password2)

        layout.addLayout(form)

        button = QPushButton("Save")
        layout.addWidget(button)

        button.clicked.connect(self.save)

    def save(self):

        if self.password1.text() != self.password2.text():
            QMessageBox.warning(
                self,
                "Password",
                "Passwords do not match."
            )
            return

        service = AuthService()

        password_hash = service.hash_password(
            self.password1.text()
        )

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE users
            SET password_hash=?
            WHERE id=?
        """, (
            password_hash,
            self.user.id,
        ))

        conn.commit()
        conn.close()

        QMessageBox.information(
            self,
            "Password",
            "Password updated."
        )

        self.accept()