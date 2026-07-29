class Permissions:

    PERMISSIONS = {

        "Administrator": {
            "equipment_add": True,
            "equipment_edit": True,
            "equipment_delete": True,
            "calibration": True,
            "maintenance": True,
            "reports": True,
            "dashboard": True,
            "user_management": True,
            "settings": True,
        },

        "Manager": {
            "equipment_add": True,
            "equipment_edit": True,
            "equipment_delete": True,
            "calibration": True,
            "maintenance": True,
            "reports": True,
            "dashboard": True,
            "user_management": False,
            "settings": False,
        },

        "Technician": {
            "equipment_add": True,
            "equipment_edit": True,
            "equipment_delete": False,
            "calibration": True,
            "maintenance": True,
            "reports": False,
            "dashboard": True,
            "user_management": False,
            "settings": False,
        },

        "Viewer": {
            "equipment_add": False,
            "equipment_edit": False,
            "equipment_delete": False,
            "calibration": False,
            "maintenance": False,
            "reports": True,
            "dashboard": True,
            "user_management": False,
            "settings": False,
        },
    }

    @classmethod
    def can(cls, role, permission):
        return cls.PERMISSIONS.get(role, {}).get(permission, False)