from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
)


class TopBar(QFrame):
    """Professional application top bar."""

    def __init__(self):
        super().__init__()

        self.setObjectName("TopBar")
        self.setFixedHeight(60)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(15)

        # --------------------------------------------------
        # Application Title
        # --------------------------------------------------
        title = QLabel("FlowLab Pro")
        title.setObjectName("ApplicationTitle")

        # --------------------------------------------------
        # Global Search
        # --------------------------------------------------
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search projects, equipment, reports...")
        self.search.setMinimumWidth(350)

        # --------------------------------------------------
        # Right-side Controls
        # --------------------------------------------------
        notifications = QPushButton("🔔")
        notifications.setFixedWidth(40)

        database = QLabel("🟢 Database")

        user = QLabel("Administrator")

        layout.addWidget(title)
        layout.addSpacing(20)

        layout.addWidget(self.search)

        layout.addStretch()

        layout.addWidget(database)
        layout.addWidget(notifications)
        layout.addWidget(user)