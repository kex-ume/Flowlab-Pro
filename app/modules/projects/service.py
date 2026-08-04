"""Project workflow validation from SDS Section 9."""

from __future__ import annotations

from app.modules.projects.models import Customer, Deliverable, Project
from app.modules.projects.repository import ProjectsRepository


class ProjectsService:
    PROJECT_STATUS_FLOW = {
        "Draft": ("Open",),
        "Open": ("In Progress",),
        "In Progress": ("Pending Review",),
        "Pending Review": ("Completed",),
        "Completed": ("Closed",),
        "Closed": (),
    }

    def __init__(self, repository: ProjectsRepository | None = None):
        self.repository = repository or ProjectsRepository()

    def create_customer(self, customer: Customer, actor: str | None = None) -> int:
        if not customer.customer_name.strip():
            raise ValueError("Customer name is required.")
        return self.repository.add_customer(customer, actor)

    def create_project(self, project: Project, actor: str | None = None) -> int:
        if not project.project_name.strip():
            raise ValueError("Project name is required.")
        if project.customer_id < 1:
            raise ValueError("A customer must be selected.")
        project.project_number = project.project_number or self.repository.next_project_number()
        return self.repository.add_project(project, actor)

    def advance_project(self, project_id: int, actor: str | None = None) -> str:
        project = self.repository.project(project_id)
        if project is None:
            raise ValueError("Project not found.")
        current_status = project[5]
        next_statuses = self.PROJECT_STATUS_FLOW.get(current_status, ())
        if not next_statuses:
            raise ValueError("Closed projects are read-only.")
        next_status = next_statuses[0]
        self.repository.update_status(project_id, next_status, actor)
        return next_status

    def create_deliverable(
        self, deliverable: Deliverable, actor: str | None = None
    ) -> int:
        if not deliverable.deliverable_name.strip():
            raise ValueError("Deliverable name is required.")
        return self.repository.add_deliverable(deliverable, actor)
