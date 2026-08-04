"""SDS-governed service rules for configuration, reminders and quality."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import shutil
from uuid import uuid4

from app.modules.governance.repository import GovernanceRepository


class GovernanceService:
    DEFAULT_REMINDER_DAYS = (30, 15, 7, 3, 1)

    def __init__(self, repository: GovernanceRepository | None = None):
        self.repository = repository or GovernanceRepository()

    def add_controlled_document(
        self, document_type: str, document_number: str, title: str, revision: str,
        source_path: str, status: str = "Draft", effective_date: str = "",
        actor: str | None = None,
    ) -> int:
        if document_type not in {"Standard", "Procedure"}:
            raise ValueError("Document type must be Standard or Procedure.")
        if not title.strip():
            raise ValueError("A document title is required.")
        source = Path(source_path)
        if not source.is_file():
            raise ValueError("Choose a document file to upload.")
        destination = Path("data/documents/controlled")
        destination.mkdir(parents=True, exist_ok=True)
        target = destination / f"{uuid4().hex}_{source.name}"
        shutil.copy2(source, target)
        try:
            return self.repository.add_controlled_document(
                document_type, document_number.strip(), title.strip(), revision.strip(),
                source.name, str(target), status, effective_date.strip(), actor,
            )
        except Exception:
            target.unlink(missing_ok=True)
            raise

    def add_method(
        self,
        meter_type: str,
        method_name: str,
        revision: str,
        procedure_reference: str = "",
        description: str = "",
        actor: str | None = None,
    ) -> int:
        if not meter_type.strip() or not method_name.strip() or not revision.strip():
            raise ValueError("Meter type, method name and revision are required.")
        return self.repository.add_method(
            meter_type.strip(),
            method_name.strip(),
            revision.strip(),
            procedure_reference.strip(),
            description.strip(),
            actor,
        )

    def ensure_default_reminder_rules(self) -> None:
        existing_days = {
            row[4]
            for row in self.repository.list_rules()
            if row[2] == "equipment" and row[6]
        }
        for days in self.DEFAULT_REMINDER_DAYS:
            if days not in existing_days:
                self.repository.add_rule(
                    f"Equipment calibration - {days} days",
                    "equipment",
                    days,
                )

    def generate_reminders(self, as_of: date | None = None) -> int:
        """Generate each due-date reminder without inferring technical data."""
        today = as_of or date.today()
        self.ensure_default_reminder_rules()
        rules = [row for row in self.repository.list_rules() if row[2] == "equipment" and row[6]]
        created = 0
        for equipment_id, asset, name, equipment_type, due_text in self.repository.equipment_due_dates():
            try:
                due_date = date.fromisoformat(due_text)
            except (TypeError, ValueError):
                continue
            for rule_id, _, _, rule_equipment_type, lead_days, *_ in rules:
                if rule_equipment_type and rule_equipment_type != equipment_type:
                    continue
                trigger_date = due_date - timedelta(days=lead_days)
                if today < trigger_date:
                    continue
                status = "Overdue" if due_date < today else "Open"
                created += int(
                    self.repository.add_reminder(
                        rule_id,
                        equipment_id,
                        f"Calibration due: {name}",
                        f"Asset {asset} is due for calibration on {due_date.isoformat()}.",
                        due_date.isoformat(),
                        trigger_date.isoformat(),
                        status,
                    )
                )
        return created

    def add_quality_record(
        self,
        record_type: str,
        reference_number: str,
        title: str,
        description: str = "",
        owner: str = "",
        due_date: str = "",
        actor: str | None = None,
    ) -> int:
        if not record_type.strip() or not title.strip():
            raise ValueError("Record type and title are required.")
        return self.repository.add_quality_record(
            record_type.strip(),
            reference_number.strip(),
            title.strip(),
            description.strip(),
            owner.strip(),
            due_date.strip(),
            actor,
        )

    def add_knowledge_entry(
        self,
        category: str,
        entry_key: str,
        title: str,
        content: str = "",
        version: str = "1.0",
        actor: str | None = None,
    ) -> int:
        if not category.strip() or not entry_key.strip() or not title.strip():
            raise ValueError("Category, key and title are required.")
        return self.repository.add_knowledge_entry(
            category.strip(),
            entry_key.strip(),
            title.strip(),
            content.strip(),
            version.strip() or "1.0",
            actor,
        )
