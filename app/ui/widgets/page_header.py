from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import ThemeManager


class PageHeader(QWidget):
    def __init__(self, title: str, subtitle: str = ""):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.title = QLabel(title)
        self.title.setObjectName("PageTitle")
        self.title.setAlignment(Qt.AlignLeft)

        self.subtitle = QLabel(subtitle)
        self.subtitle.setObjectName("PageSubtitle")
        self.subtitle.setAlignment(Qt.AlignLeft)

        layout.addWidget(self.title)

        if subtitle:
            layout.addWidget(self.subtitle)

        layout.addSpacing(10)

        ThemeManager.register(self._apply_theme)
        self._apply_theme(ThemeManager.current())

    # ---------------------------------------------------------
    # Theme
    # ---------------------------------------------------------

    def _apply_theme(self, theme):
        c = theme.color

        self.setStyleSheet(
            f"""
            QLabel#PageTitle {{
                background: transparent;
                color: {c.text};
                font-size: 28px;
                font-weight: 700;
            }}

            QLabel#PageSubtitle {{
                background: transparent;
                color: {c.text_secondary};
                font-size: 13px;
            }}
            """
        )

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------

    def set_title(self, text: str):
        self.title.setText(text)

    def set_subtitle(self, text: str):
        self.subtitle.setText(text)
        self.subtitle.setVisible(bool(text))

    # ---------------------------------------------------------
    # Cleanup
    # ---------------------------------------------------------

    def closeEvent(self, event):
        ThemeManager.unregister(self._apply_theme)
        super().closeEvent(event)