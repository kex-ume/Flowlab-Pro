from dataclasses import dataclass


@dataclass(slots=True)
class Role:
    id: int | None = None
    name: str = ""
    description: str = ""


@dataclass(slots=True)
class User:
    id: int | None = None
    username: str = ""
    password_hash: str = ""
    full_name: str = ""
    email: str = ""
    role_id: int | None = None
    role_name: str = ""
    is_active: bool = True
    last_login: str = ""
    created_at: str = ""