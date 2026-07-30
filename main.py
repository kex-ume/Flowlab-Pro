import sys

from PySide6.QtWidgets import QApplication

from app.database.init_db import initialize_database
from app.modules.auth.login_dialog import LoginDialog
from app.modules.auth.service import AuthService
from app.ui.shell.main_window import MainWindow
from app.ui.theme import (
    DarkTheme,
    StyleSheet,
    ThemeManager,
)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("FlowLab Pro")
    app.setOrganizationName("FlowLab")

    # --------------------------------------------------
    # Database
    # --------------------------------------------------

    initialize_database()

    # Ensure default admin exists
    AuthService()

    # --------------------------------------------------
    # Theme
    # --------------------------------------------------

    ThemeManager.set_theme(DarkTheme)
    app.setStyleSheet(
        StyleSheet.build(ThemeManager.current())
    )

    # Keep the application stylesheet synchronized with
    # runtime theme changes.

    def _update_stylesheet(theme):
        app.setStyleSheet(
            StyleSheet.build(theme)
        )

    ThemeManager.register(_update_stylesheet)

    # --------------------------------------------------
    # Login
    # --------------------------------------------------

    login = LoginDialog()

    if login.exec() != LoginDialog.Accepted:
        ThemeManager.unregister(_update_stylesheet)
        sys.exit(0)

    # --------------------------------------------------
    # Main Window
    # --------------------------------------------------

    window = MainWindow()

    if hasattr(window, "initialize"):
        window.initialize(login.user)

    window.show()

    exit_code = app.exec()

    ThemeManager.unregister(_update_stylesheet)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()