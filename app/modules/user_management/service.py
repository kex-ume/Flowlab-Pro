from app.modules.user_management.repository import UserRepository
from app.modules.auth.service import AuthService
from app.modules.auth.models import User


class UserService:

    def __init__(self):
        self.repo = UserRepository()
        self.auth = AuthService()

    def get_users(self):
        return self.repo.get_all()

    def get_roles(self):
        return self.repo.roles()

    def add_user(self, username, password, fullname, email, role_id):

        user = User(
            username=username,
            password_hash=self.auth.hash_password(password),
            full_name=fullname,
            email=email,
            role_id=role_id,
            is_active=True,
        )

        self.repo.add(user)

    def update_user(self, user):
        self.repo.update(user)

    def delete_user(self, user_id):
        self.repo.delete(user_id)

    def reset_password(self, user_id, new_password):
        self.repo.reset_password(
            user_id,
            self.auth.hash_password(new_password),
        )