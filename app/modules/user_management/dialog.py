from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QPushButton,
)

from app.modules.user_management.service import UserService


class UserDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.service = UserService()
        self.roles = self.service.get_roles()

        self.user = None

        self.setWindowTitle("User")

        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.username = QLineEdit()
        self.password = QLineEdit()
        self.fullname = QLineEdit()
        self.email = QLineEdit()

        self.role = QComboBox()

        for role_id, role_name in self.roles:
            self.role.addItem(role_name, role_id)

        self.active = QCheckBox()
        self.active.setChecked(True)

        form.addRow("Username", self.username)
        form.addRow("Password", self.password)
        form.addRow("Full Name", self.fullname)
        form.addRow("Email", self.email)
        form.addRow("Role", self.role)
        form.addRow("Active", self.active)

        layout.addLayout(form)

        save = QPushButton("Save")
        layout.addWidget(save)

        save.clicked.connect(self.accept)

    def load_user(self, user):

        self.user = user

        self.username.setText(user.username)
        self.username.setEnabled(False)

        self.password.hide()

        self.fullname.setText(user.full_name)
        self.email.setText(user.email)

        index = self.role.findData(user.role_id)
        self.role.setCurrentIndex(index)

        self.active.setChecked(user.is_active)