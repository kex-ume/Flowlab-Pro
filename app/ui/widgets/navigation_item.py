from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
)


class NavigationItem(QFrame):

    clicked = Signal(str)

    def __init__(self, key: str, title: str, icon: str):
        super().__init__()

        self.key = key
        self.active = False

        self.setObjectName("NavigationItem")
        self.setCursor(Qt.PointingHandCursor)

        self.setMinimumHeight(46)
        self.setMaximumHeight(46)

        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed,
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(12)

        self.icon = QLabel()
        self.icon.setFixedSize(20, 20)
        self.icon.setAlignment(Qt.AlignCenter)
        self.icon.setPixmap(QIcon(icon).pixmap(18, 18))

        self.text = QLabel(title)
        self.text.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        layout.addWidget(self.icon)
        layout.addWidget(self.text, 1)

        self.update_style()

    # -----------------------------------------------------

    def set_active(self, active: bool):
        self.active = active
        self.update_style()

    # -----------------------------------------------------

    def update_style(self):

        if self.active:

            self.setStyleSheet("""
QFrame#NavigationItem{
    background:#18A9B0;
    border:none;
    border-radius:10px;
}

QFrame#NavigationItem:hover{
    background:#18A9B0;
}

QLabel{
    background:transparent;
    border:none;
    color:white;
    font-size:14px;
    font-weight:600;
}
""")

        else:

            self.setStyleSheet("""
QFrame#NavigationItem{
    background:transparent;
    border:none;
    border-radius:10px;
}

QFrame#NavigationItem:hover{
    background:rgba(255,255,255,0.08);
}

QLabel{
    background:transparent;
    border:none;
    color:#D7E4F2;
    font-size:14px;
    font-weight:500;
}
""")

    # -----------------------------------------------------

    def mousePressEvent(self, event):
        self.clicked.emit(self.key)
        super().mousePressEvent(event)