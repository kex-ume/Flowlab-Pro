"""SQLite persistence for customers, projects, jobs and deliverables."""

from __future__ import annotations

from datetime import date

from app.core.audit import record_audit
from app.database.database import managed_connection
from app.modules.projects.models import Customer, Deliverable, Project


class ProjectsRepository:
    """Keeps project lifecycle records separate from individual calibration jobs."""

    def customers(self):
        with managed_connection() as conn:
            return conn.execute(
                """
                SELECT id, customer_name, account_reference, primary_contact,
                       email, phone, site_address, status
                FROM customers
                ORDER BY customer_name COLLATE NOCASE
                """
            ).fetchall()

    def add_customer(self, customer: Customer, actor: str | None = None) -> int:
        with managed_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO customers (
                    customer_name, account_reference, primary_contact, email,
                    phone, site_address, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    customer.customer_name,
                    customer.account_reference,
                    customer.primary_contact,
                    customer.email,
                    customer.phone,
                    customer.site_address,
                    customer.status,
                ),
            )
            customer_id = cursor.lastrowid
            record_audit(
                conn.cursor(),
                "customer",
                customer_id,
                "created",
                actor,
                after_state={"customer_name": customer.customer_name},
            )
            return customer_id

    def next_project_number(self) -> str:
        prefix = f"PRJ-{date.today():%Y}-"
        with managed_connection() as conn:
            row = conn.execute(
                """
                SELECT project_number
                FROM projects
                WHERE project_number LIKE ?
                ORDER BY project_number DESC
                LIMIT 1
                """,
                (f"{prefix}%",),
            ).fetchone()
        next_number = int(row[0].rsplit("-", 1)[-1]) + 1 if row else 1
        return f"{prefix}{next_number:04d}"

    def add_project(self, project: Project, actor: str | None = None) -> int:
        with managed_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO projects (
                    project_number, customer_id, project_name, description,
                    status, target_start_date, target_completion_date,
                    deliverable_summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project.project_number,
                    project.customer_id,
                    project.project_name,
                    project.description,
                    project.status,
                    project.target_start_date or None,
                    project.target_completion_date or None,
                    project.deliverable_summary,
                ),
            )
            project_id = cursor.lastrowid
            record_audit(
                conn.cursor(),
                "project",
                project_id,
                "created",
                actor,
                after_state={
                    "project_number": project.project_number,
                    "status": project.status,
                },
            )
            return project_id

    def projects(self, search: str = ""):
        value = f"%{search.strip()}%"
        with managed_connection() as conn:
            return conn.execute(
                """
                SELECT p.id, p.project_number, p.project_name, c.customer_name,
                       p.status, p.target_completion_date,
                       COUNT(DISTINCT pj.job_id) AS job_count,
                       COUNT(DISTINCT d.id) AS deliverable_count
                FROM projects p
                JOIN customers c ON c.id = p.customer_id
                LEFT JOIN project_jobs pj ON pj.project_id = p.id
                LEFT JOIN deliverables d ON d.project_id = p.id
                WHERE p.project_number LIKE ?
                   OR p.project_name LIKE ?
                   OR c.customer_name LIKE ?
                GROUP BY p.id
                ORDER BY CASE p.status WHEN 'Closed' THEN 1 ELSE 0 END,
                         p.target_completion_date, p.project_number
                """,
                (value, value, value),
            ).fetchall()

    def project(self, project_id: int):
        with managed_connection() as conn:
            return conn.execute(
                """
                SELECT p.id, p.project_number, p.customer_id, p.project_name,
                       p.description, p.status, p.target_start_date,
                       p.target_completion_date, p.deliverable_summary,
                       c.customer_name
                FROM projects p
                JOIN customers c ON c.id = p.customer_id
                WHERE p.id = ?
                """,
                (project_id,),
            ).fetchone()

    def update_status(
        self, project_id: int, status: str, actor: str | None = None
    ) -> None:
        with managed_connection() as conn:
            before = conn.execute(
                "SELECT status FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            conn.execute(
                """
                UPDATE projects
                SET status = ?,
                    closed_at = CASE WHEN ? = 'Closed' THEN CURRENT_TIMESTAMP ELSE NULL END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, status, project_id),
            )
            record_audit(
                conn.cursor(),
                "project",
                project_id,
                "status_changed",
                actor,
                before_state={"status": before[0]} if before else None,
                after_state={"status": status},
            )

    def add_deliverable(
        self, deliverable: Deliverable, actor: str | None = None
    ) -> int:
        with managed_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO deliverables (
                    project_id, deliverable_name, description, due_date, status
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    deliverable.project_id,
                    deliverable.deliverable_name,
                    deliverable.description,
                    deliverable.due_date or None,
                    deliverable.status,
                ),
            )
            deliverable_id = cursor.lastrowid
            record_audit(
                conn.cursor(),
                "deliverable",
                deliverable_id,
                "created",
                actor,
                after_state={"project_id": deliverable.project_id},
            )
            return deliverable_id

    def deliverables(self, project_id: int):
        with managed_connection() as conn:
            return conn.execute(
                """
                SELECT id, deliverable_name, description, due_date, status
                FROM deliverables
                WHERE project_id = ?
                ORDER BY CASE status WHEN 'Completed' THEN 1 ELSE 0 END, due_date
                """,
                (project_id,),
            ).fetchall()

    def set_deliverable_status(
        self, deliverable_id: int, status: str, actor: str | None = None
    ) -> None:
        with managed_connection() as conn:
            conn.execute(
                """
                UPDATE deliverables
                SET status = ?,
                    completed_at = CASE WHEN ? = 'Completed' THEN CURRENT_TIMESTAMP ELSE NULL END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, status, deliverable_id),
            )
            record_audit(
                conn.cursor(),
                "deliverable",
                deliverable_id,
                "status_changed",
                actor,
                after_state={"status": status},
            )
