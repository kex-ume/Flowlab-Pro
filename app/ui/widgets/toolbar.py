from PySide6.QtWidgets import (
    QHBoxLayout,
    QWidget,
)

from app.ui.theme import ThemeManager


class ToolBar(QWidget):
    def __init__(self):
        super().__init__()

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(10)

        ThemeManager.register(self._apply_theme)
        self._apply_theme(ThemeManager.current())

    # ---------------------------------------------------------
    # Theme
    # ---------------------------------------------------------

    def _apply_theme(self, theme):
        c = theme.color

        self.setStyleSheet(
            f"""
            ToolBar {{
                background: transparent;
            }}

            QPushButton {{
                min-height: 36px;
            }}

            QLineEdit,
            QComboBox {{
                min-height: 36px;
            }}
            """
        )

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------

    def add(self, widget):
        self.layout.addWidget(widget)

    def stretch(self):
        self.layout.addStretch()

    def clear(self):
        while self.layout.count():
            item = self.layout.takeAt(0)

            if item.widget():
                item.widget().deleteLater()

    # ---------------------------------------------------------
    # Cleanup
    # ---------------------------------------------------------

    def closeEvent(self, event):
        ThemeManager.unregister(self._apply_theme)
        super().closeEvent(event)