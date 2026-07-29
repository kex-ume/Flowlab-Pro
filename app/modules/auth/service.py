import hashlib

from app.database.database import get_connection
from app.modules.auth.models import User
from app.modules.auth.repository import AuthRepository


class AuthService:

    def __init__(self):
        self.repository = AuthRepository()
        self.ensure_default_admin()

    # ------------------------------------------------------------------
    # Password Hashing
    # ------------------------------------------------------------------

    @staticmethod
    def hash_password(password: str) -> str:
        return hashlib.sha256(
            password.encode("utf-8")
        ).hexdigest()

    # ------------------------------------------------------------------
    # Default Administrator
    # ------------------------------------------------------------------

    def ensure_default_admin(self):

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id
            FROM users
            WHERE username='admin'
        """)

        exists = cursor.fetchone()

        if exists:
            conn.close()
            return

        cursor.execute("""
            SELECT id
            FROM roles
            WHERE name='Administrator'
        """)

        role = cursor.fetchone()

        if role is None:
            conn.close()
            return

        role_id = role[0]

        cursor.execute("""
            INSERT INTO users(
                username,
                password_hash,
                full_name,
                email,
                role_id,
                is_active
            )
            VALUES(?,?,?,?,?,?)
        """, (
            "admin",
            self.hash_password("admin123"),
            "System Administrator",
            "",
            role_id,
            1,
        ))

        conn.commit()
        conn.close()

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