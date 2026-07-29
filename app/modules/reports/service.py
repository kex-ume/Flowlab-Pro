from app.modules.reports.repository import ReportsRepository


class ReportsService:

    def __init__(self):
        self.repo = ReportsRepository()

    def equipment(self):
        return self.repo.equipment()

    def calibrations(self):
        return self.repo.calibrations()

    def maintenance(self):
        return self.repo.maintenance()

    def users(self):
        return self.repo.users()