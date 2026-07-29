from app.database.database import get_connection
from app.modules.auth.models import User


class AuthRepository:

    def get_user(self, username):

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                u.id,
                u.username,
                u.password_hash,
                u.full_name,
                u.email,
                u.role_id,
                r.name,
                u.is_active,
                u.last_login,
                u.created_at
            FROM users u
            JOIN roles r
                ON u.role_id = r.id
            WHERE u.username = ?
        """, (username,))

        row = cursor.fetchone()

        conn.close()

        if not row:
            return None

        return User(
            id=row[0],
            username=row[1],
            password_hash=row[2],
            full_name=row[3],
            email=row[4],
            role_id=row[5],
            role_name=row[6],
            is_active=bool(row[7]),
            last_login=row[8] or "",
            created_at=row[9] or "",
        )

    def create_user(self, user: User):

        conn = get_connection()
        cursor = conn.cursor()

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
            user.username,
            user.password_hash,
            user.full_name,
            user.email,
            user.role_id,
            int(user.is_active),
        ))

        conn.commit()
        conn.close()

    def update_last_login(self, user_id):

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE users
            SET last_login=CURRENT_TIMESTAMP
            WHERE id=?
        """, (user_id,))

        conn.commit()
        conn.close()

    def get_roles(self):

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id,name
            FROM roles
            ORDER BY id
        """)

        rows = cursor.fetchall()

        conn.close()

        return rows

    def get_all_users(self):

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                u.id,
                u.username,
                u.full_name,
                r.name,
                u.is_active
            FROM users u
            JOIN roles r
                ON u.role_id=r.id
            ORDER BY u.username
        """)

        rows = cursor.fetchall()

        conn.close()

        return rows