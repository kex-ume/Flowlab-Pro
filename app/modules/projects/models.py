"""Data contracts for the SDS project lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class Customer:
    customer_name: str
    account_reference: str = ""
    primary_contact: str = ""
    email: str = ""
    phone: str = ""
    site_address: str = ""
    status: str = "Active"
    id: Optional[int] = None


@dataclass(slots=True)
class Project:
    customer_id: int
    project_name: str
    description: str = ""
    target_start_date: str = ""
    target_completion_date: str = ""
    deliverable_summary: str = ""
    status: str = "Draft"
    project_number: str = ""
    id: Optional[int] = None


@dataclass(slots=True)
class Deliverable:
    project_id: int
    deliverable_name: str
    description: str = ""
    due_date: str = ""
    status: str = "Open"
    id: Optional[int] = None
