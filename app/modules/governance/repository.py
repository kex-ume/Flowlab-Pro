"""Persistence operations for SDS governance modules."""

from __future__ import annotations

from app.core.audit import record_audit
from app.database.database import managed_connection


class GovernanceRepository:
    def controlled_documents(self):
        with managed_connection() as conn:
            return conn.execute(
                """
                SELECT id, document_type, COALESCE(document_number, ''), title,
                       COALESCE(revision, ''), original_filename, status,
                       COALESCE(effective_date, ''), file_path
                FROM controlled_documents
                ORDER BY document_type, title, revision DESC
                """
            ).fetchall()

    def add_controlled_document(
        self, document_type: str, document_number: str, title: str, revision: str,
        original_filename: str, file_path: str, status: str, effective_date: str,
        actor: str | None = None,
    ) -> int:
        with managed_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO controlled_documents (
                    document_type, document_number, title, revision,
                    original_filename, file_path, status, effective_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (document_type, document_number or None, title, revision or None,
                 original_filename, file_path, status, effective_date or None),
            )
            document_id = cursor.lastrowid
            record_audit(conn.cursor(), "controlled_document", document_id, "uploaded", actor,
                         after_state={"document_type": document_type, "title": title, "file_path": file_path})
            return document_id

    def methods(self):
        with managed_connection() as conn:
            return conn.execute(
                """
                SELECT id, meter_type, method_name, revision, procedure_reference,
                       status, effective_date, is_active
                FROM calibration_methods
                ORDER BY meter_type, method_name, revision DESC
                """
            ).fetchall()

    def add_method(
        self,
        meter_type: str,
        method_name: str,
        revision: str,
        procedure_reference: str,
        description: str,
        actor: str | None = None,
    ) -> int:
        with managed_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO calibration_methods (
                    meter_type, method_name, revision, procedure_reference,
                    description
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (meter_type, method_name, revision, procedure_reference, description),
            )
            method_id = cursor.lastrowid
            record_audit(
                conn.cursor(),
                "calibration_method",
                method_id,
                "created",
                actor,
                after_state={"method_name": method_name, "revision": revision},
            )
            return method_id

    def list_rules(self):
        with managed_connection() as conn:
            return conn.execute(
                """
                SELECT id, rule_name, entity_type, equipment_type, lead_days,
                       escalation_role, is_active
                FROM reminder_rules
                ORDER BY lead_days DESC, rule_name
                """
            ).fetchall()

    def add_rule(
        self,
        rule_name: str,
        entity_type: str,
        lead_days: int,
        equipment_type: str = "",
        actor: str | None = None,
    ) -> int:
        with managed_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO reminder_rules (
                    rule_name, entity_type, equipment_type, lead_days
                ) VALUES (?, ?, ?, ?)
                """,
                (rule_name, entity_type, equipment_type or None, lead_days),
            )
            rule_id = cursor.lastrowid
            record_audit(
                conn.cursor(),
                "reminder_rule",
                rule_id,
                "created",
                actor,
                after_state={"lead_days": lead_days, "entity_type": entity_type},
            )
            return rule_id

    def equipment_due_dates(self):
        with managed_connection() as conn:
            return conn.execute(
                """
                SELECT id, asset_number, equipment_name, equipment_type,
                       next_calibration_date
                FROM laboratory_equipment
                WHERE is_active = 1 AND next_calibration_date IS NOT NULL
                """
            ).fetchall()

    def add_reminder(
        self,
        rule_id: int,
        equipment_id: int,
        title: str,
        detail: str,
        due_date: str,
        trigger_date: str,
        status: str,
    ) -> bool:
        with managed_connection() as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO reminders (
                    reminder_rule_id, entity_type, entity_id, title, detail,
                    due_date, trigger_date, status, escalated_at
                ) VALUES (?, 'equipment', ?, ?, ?, ?, ?, ?,
                         CASE WHEN ? = 'Overdue' THEN CURRENT_TIMESTAMP ELSE NULL END)
                """,
                (
                    rule_id,
                    equipment_id,
                    title,
                    detail,
                    due_date,
                    trigger_date,
                    status,
                    status,
                ),
            )
            return bool(cursor.rowcount)

    def reminders(self, show_resolved: bool = False):
        filter_sql = "" if show_resolved else "WHERE r.status <> 'Resolved'"
        with managed_connection() as conn:
            return conn.execute(
                f"""
                SELECT r.id, r.title, r.detail, r.due_date, r.trigger_date,
                       r.status, rr.lead_days, r.escalated_at
                FROM reminders r
                LEFT JOIN reminder_rules rr ON rr.id = r.reminder_rule_id
                {filter_sql}
                ORDER BY CASE r.status WHEN 'Overdue' THEN 0 ELSE 1 END,
                         r.due_date, rr.lead_days DESC
                """
            ).fetchall()

    def resolve_reminder(self, reminder_id: int, actor: str | None = None) -> None:
        with managed_connection() as conn:
            conn.execute(
                """
                UPDATE reminders
                SET status = 'Resolved', resolved_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (reminder_id,),
            )
            record_audit(
                conn.cursor(),
                "reminder",
                reminder_id,
                "resolved",
                actor,
                after_state={"status": "Resolved"},
            )

    def quality_records(self, search: str = ""):
        value = f"%{search.strip()}%"
        with managed_connection() as conn:
            return conn.execute(
                """
                SELECT id, record_type, COALESCE(reference_number, ''), title,
                       COALESCE(owner, ''), COALESCE(due_date, ''), status
                FROM quality_records
                WHERE record_type LIKE ? OR title LIKE ? OR reference_number LIKE ?
                ORDER BY CASE status WHEN 'Open' THEN 0 ELSE 1 END, due_date, id DESC
                """,
                (value, value, value),
            ).fetchall()

    def add_quality_record(
        self,
        record_type: str,
        reference_number: str,
        title: str,
        description: str,
        owner: str,
        due_date: str,
        actor: str | None = None,
    ) -> int:
        with managed_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO quality_records (
                    record_type, reference_number, title, description, owner, due_date
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record_type,
                    reference_number or None,
                    title,
                    description,
                    owner,
                    due_date or None,
                ),
            )
            record_id = cursor.lastrowid
            record_audit(
                conn.cursor(),
                "quality_record",
                record_id,
                "created",
                actor,
                after_state={"record_type": record_type, "title": title},
            )
            return record_id

    def close_quality_record(self, record_id: int, actor: str | None = None) -> None:
        with managed_connection() as conn:
            conn.execute(
                """
                UPDATE quality_records
                SET status = 'Closed', closed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (record_id,),
            )
            record_audit(
                conn.cursor(),
                "quality_record",
                record_id,
                "closed",
                actor,
                after_state={"status": "Closed"},
            )

    def knowledge_entries(self, category: str = "", search: str = ""):
        category_sql = "" if not category else "AND category = ?"
        params = [f"%{search.strip()}%", f"%{search.strip()}%"]
        if category:
            params.append(category)
        with managed_connection() as conn:
            return conn.execute(
                f"""
                SELECT id, category, entry_key, title, version, status,
                       COALESCE(approved_by, '')
                FROM knowledge_base_entries
                WHERE (title LIKE ? OR entry_key LIKE ?) {category_sql}
                ORDER BY category, title, version DESC
                """,
                params,
            ).fetchall()

    def add_knowledge_entry(
        self,
        category: str,
        entry_key: str,
        title: str,
        content: str,
        version: str,
        actor: str | None = None,
    ) -> int:
        with managed_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO knowledge_base_entries (
                    category, entry_key, title, content, version
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (category, entry_key, title, content, version),
            )
            entry_id = cursor.lastrowid
            record_audit(
                conn.cursor(),
                "knowledge_entry",
                entry_id,
                "created",
                actor,
                after_state={"category": category, "entry_key": entry_key},
            )
            return entry_id
