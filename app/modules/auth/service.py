import hashlib

from app.database.database import get_connection
from app.modules.auth.models import User
from app.modules.auth.repository import AuthRepository


class AuthService:

    def __init__(self):
        self.repository = AuthRepository()

    # ------------------------------------------------------------------
    # Password Hashing
    # ------------------------------------------------------------------

    @staticmethod
    def hash_password(password: str) -> str:
        return hashlib.sha256(
            password.encode("utf-8")
        ).hexdigest()

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    def authenticate(self, username, password):

        user = self.repository.get_user(username)

        if user is None:
            return None

        if not user.is_active:
            return None

        if user.password_hash != self.hash_password(password):
            return None

        self.repository.update_last_login(user.id)

        return user

    # ------------------------------------------------------------------
    # Create User
    # ------------------------------------------------------------------

    def create_user(
        self,
        username,
        password,
        full_name,
        email,
        role_id,
    ):

        user = User(
            username=username,
            password_hash=self.hash_password(password),
            full_name=full_name,
            email=email,
            role_id=role_id,
            is_active=True,
        )

        self.repository.create_user(user)
