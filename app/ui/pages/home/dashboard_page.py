from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
)

from app.database.database import get_connection
from app.ui.base_page import BasePage
from app.ui.widgets.card import Card


class DashboardPage(BasePage):

    def __init__(self):

        super().__init__(
            "Dashboard",
            "Laboratory overview"
        )

        grid = QGridLayout()
        grid.setSpacing(15)

        self.total_equipment = Card("Equipment")
        self.active_equipment = Card("Active")
        self.overdue = Card("Overdue")
        self.due = Card("Due Soon")
        self.maintenance = Card("Maintenance")
        self.users = Card("Users")

        cards = [
            self.total_equipment,
            self.active_equipment,
            self.overdue,
            self.due,
            self.maintenance,
            self.users,
        ]

        for i, card in enumerate(cards):
            grid.addWidget(card, i // 3, i % 3)

        self.content_layout.addLayout(grid)

        quick = QGroupBox("Quick Actions")

        quick_layout = QHBoxLayout(quick)

        for text in (
            "Add Equipment",
            "Calibration",
            "Maintenance",
            "Reports",
        ):
            quick_layout.addWidget(QPushButton(text))

        quick_layout.addStretch()

        self.content_layout.addWidget(quick)

        activity_box = QGroupBox("Recent Activity")

        activity_layout = QHBoxLayout(activity_box)

        self.activity = QTextEdit()
        self.activity.setReadOnly(True)

        activity_layout.addWidget(self.activity)

        self.content_layout.addWidget(activity_box)

        self.refresh()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(60000)

    def refresh(self):

        conn = get_connection()
        cur = conn.cursor()

        def count(sql):
            cur.execute(sql)
            return str(cur.fetchone()[0])

        self.total_equipment.setValue(
            count("SELECT COUNT(*) FROM laboratory_equipment")
        )

        self.active_equipment.setValue(
            count("SELECT COUNT(*) FROM laboratory_equipment WHERE status='Active'")
        )

        self.overdue.setValue(
            count("SELECT COUNT(*) FROM laboratory_equipment WHERE status='Overdue'")
        )

        self.due.setValue(
            count("SELECT COUNT(*) FROM laboratory_equipment WHERE status='Due Soon'")
        )

        self.maintenance.setValue(
            count("SELECT COUNT(*) FROM maintenance_history")
        )

        self.users.setValue(
            count("SELECT COUNT(*) FROM users WHERE is_active=1")
        )

        cur.execute("""
            SELECT equipment_name,status
            FROM laboratory_equipment
            ORDER BY updated_at DESC
            LIMIT 10
        """)

        rows = cur.fetchall()

        if rows:
            self.activity.setPlainText(
                "\n".join(
                    f"• {name}   [{status}]"
                    for name, status in rows
                )
            )
        else:
            self.activity.setPlainText("No recent activity.")

        conn.close()