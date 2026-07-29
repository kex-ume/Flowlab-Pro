import sys

from PySide6.QtWidgets import QApplication

from app.database.init_db import initialize_database
from app.modules.auth.login_dialog import LoginDialog
from app.modules.auth.service import AuthService
from app.ui.shell.main_window import MainWindow
from app.ui.theme.stylesheet import StyleSheet


def main():

    app = QApplication(sys.argv)
    app.setStyleSheet(StyleSheet.build())

    initialize_database()

    # Ensure default admin exists
    AuthService()

    login = LoginDialog()

    if login.exec() != LoginDialog.Accepted:
        sys.exit(0)

    window = MainWindow()
    window.initialize(login.user)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()