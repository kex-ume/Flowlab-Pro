from dataclasses import dataclass


@dataclass(slots=True)
class ReportItem:
    title: str = ""
    category: str = ""
    created_by: str = ""
    created_at: str = ""
    reference: str = ""
    status: str = ""