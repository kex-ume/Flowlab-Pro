from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QTextEdit,
)

from app.database.database import get_connection
from app.ui.base_page import BasePage
from app.ui.widgets.card import Card


class DashboardPage(BasePage):
    def __init__(self):
        super().__init__(
             "",
             ""
        )

        # --------------------------------------------------
        # KPI Cards
        # --------------------------------------------------

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

        # --------------------------------------------------
        # Quick Actions
        # --------------------------------------------------

        quick_box = QGroupBox("Quick Actions")

        quick_layout = QHBoxLayout(quick_box)

        self.add_equipment_btn = QPushButton("Add Equipment")
        self.calibration_btn = QPushButton("Calibration")
        self.maintenance_btn = QPushButton("Maintenance")
        self.reports_btn = QPushButton("Reports")

        quick_layout.addWidget(self.add_equipment_btn)
        quick_layout.addWidget(self.calibration_btn)
        quick_layout.addWidget(self.maintenance_btn)
        quick_layout.addWidget(self.reports_btn)
        quick_layout.addStretch()

        self.content_layout.addWidget(quick_box)

        # --------------------------------------------------
        # Recent Activity
        # --------------------------------------------------

        activity_box = QGroupBox("Recent Activity")

        activity_layout = QHBoxLayout(activity_box)

        self.activity = QTextEdit()
        self.activity.setReadOnly(True)

        activity_layout.addWidget(self.activity)

        self.content_layout.addWidget(activity_box)

        # --------------------------------------------------
        # Auto Refresh
        # --------------------------------------------------

        self.refresh()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(60000)

    # ======================================================
    # Refresh
    # ======================================================

    def refresh(self):
        conn = get_connection()
        cur = conn.cursor()

        def count(sql):
            cur.execute(sql)
            row = cur.fetchone()
            return str(row[0] if row else 0)

        self.total_equipment.setValue(
            count(
                "SELECT COUNT(*) FROM laboratory_equipment"
            )
        )

        self.active_equipment.setValue(
            count(
                """
                SELECT COUNT(*)
                FROM laboratory_equipment
                WHERE status='Active'
                """
            )
        )

        self.overdue.setValue(
            count(
                """
                SELECT COUNT(*)
                FROM laboratory_equipment
                WHERE status='Overdue'
                """
            )
        )

        self.due.setValue(
            count(
                """
                SELECT COUNT(*)
                FROM laboratory_equipment
                WHERE status='Due Soon'
                """
            )
        )

        self.maintenance.setValue(
            count(
                "SELECT COUNT(*) FROM maintenance_history"
            )
        )

        self.users.setValue(
            count(
                """
                SELECT COUNT(*)
                FROM users
                WHERE is_active=1
                """
            )
        )

        cur.execute(
            """
            SELECT
                equipment_name,
                status
            FROM laboratory_equipment
            ORDER BY updated_at DESC
            LIMIT 10
            """
        )

        rows = cur.fetchall()

        if rows:
            self.activity.setPlainText(
                "\n".join(
                    f"• {name} [{status}]"
                    for name, status in rows
                )
            )
        else:
            self.activity.setPlainText(
                "No recent activity."
            )

        conn.close()