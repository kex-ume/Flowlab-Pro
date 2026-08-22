class Permissions:
    """Central role policy for controlled laboratory records."""

    _CHIEF = {
        "equipment_add": True, "equipment_edit": True, "equipment_delete": True,
        "edit_approved": True, "record_approve": True, "record_review": True, "calibration": True,
        "maintenance": True, "reports": True, "dashboard": True,
        "user_management": True, "settings": True, "uncertainty_calculate": True,
        "uncertainty_save": True, "uncertainty_approve": True,
        "project_create": True, "client_create": True, "job_reopen": True,
        "job_assign": True,
    }
    _SUPERVISOR = {**_CHIEF, "user_management": False, "settings": False}
    _ENGINEER = {
        "equipment_add": True, "equipment_edit": True, "equipment_delete": False,
        "edit_approved": False, "record_approve": False, "record_review": True, "calibration": True,
        "maintenance": True, "reports": True, "dashboard": True,
        "user_management": False, "settings": False, "uncertainty_calculate": True,
        "uncertainty_save": True, "uncertainty_approve": False,
        "project_create": True, "client_create": True, "job_reopen": False,
        "job_assign": False,
    }
    _TECHNICIAN = {**_ENGINEER, "reports": True, "record_review": False}
    _OPERATOR = {
        **_TECHNICIAN, "equipment_add": False, "equipment_edit": False,
        "project_create": False, "client_create": False,
        "uncertainty_calculate": False, "uncertainty_save": False,
    }
    _GUEST = dict.fromkeys(_CHIEF, False) | {"reports": True, "dashboard": True}

    PERMISSIONS = {
        "Chief Meteorologist": _CHIEF,
        "Supervisor": _SUPERVISOR,
        "Engineer": _ENGINEER,
        "Technician": _TECHNICIAN,
        "Operator": _OPERATOR,
        "Guest": _GUEST,
        "Administrator": _CHIEF,
        "Manager": _ENGINEER,
        "HOD": _CHIEF,
        "Viewer": _GUEST,
    }

    @classmethod
    def can(cls, role, permission):
        return cls.PERMISSIONS.get(role, {}).get(permission, False)
