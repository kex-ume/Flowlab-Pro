from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
)

from app.modules.user_management.dialog import UserDialog
from app.modules.user_management.service import UserService


class UserManagementPage(QWidget):

    def __init__(self):

        super().__init__()

        self.service = UserService()

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()

        self.add_btn = QPushButton("Add")
        self.edit_btn = QPushButton("Edit")
        self.delete_btn = QPushButton("Delete")
        self.refresh_btn = QPushButton("Refresh")

        toolbar.addWidget(self.add_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.delete_btn)
        toolbar.addStretch()
        toolbar.addWidget(self.refresh_btn)

        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(6)

        self.table.setHorizontalHeaderLabels([
            "Username",
            "Full Name",
            "Email",
            "Role",
            "Active",
            "Last Login",
        ])

        layout.addWidget(self.table)

        self.add_btn.clicked.connect(self.add_user)
        self.edit_btn.clicked.connect(self.edit_user)
        self.delete_btn.clicked.connect(self.delete_user)
        self.refresh_btn.clicked.connect(self.load_users)

        self.table.doubleClicked.connect(self.edit_user)

        self.load_users()

    def load_users(self):

        users = self.service.get_users()

        self.users = users

        self.table.setRowCount(len(users))

        for row, user in enumerate(users):

            self.table.setItem(row, 0, QTableWidgetItem(user.username))
            self.table.setItem(row, 1, QTableWidgetItem(user.full_name))
            self.table.setItem(row, 2, QTableWidgetItem(user.email))
            self.table.setItem(row, 3, QTableWidgetItem(user.role_name))
            self.table.setItem(
                row,
                4,
                QTableWidgetItem("Yes" if user.is_active else "No"),
            )
            self.table.setItem(row, 5, QTableWidgetItem(user.last_login))

        self.table.resizeColumnsToContents()

    def selected_user(self):

        row = self.table.currentRow()

        if row < 0:
            return None

        return self.users[row]

    def add_user(self):

        dialog = UserDialog(self)

        if dialog.exec():

            self.service.add_user(
                dialog.username.text(),
                dialog.password.text(),
                dialog.fullname.text(),
                dialog.email.text(),
                dialog.role.currentData(),
            )

            self.load_users()

    def edit_user(self):

        user = self.selected_user()

        if user is None:
            return

        dialog = UserDialog(self)
        dialog.load_user(user)

        if dialog.exec():

            user.full_name = dialog.fullname.text()
            user.email = dialog.email.text()
            user.role_id = dialog.role.currentData()
            user.is_active = dialog.active.isChecked()

            self.service.update_user(user)

            self.load_users()

    def delete_user(self):

        user = self.selected_user()

        if user is None:
            return

        if QMessageBox.question(
            self,
            "Delete User",
            f"Delete '{user.username}'?",
        ) != QMessageBox.Yes:
            return

        self.service.delete_user(user.id)

        self.load_users()