from app.database.database import get_connection
from app.modules.auth.models import User


class UserRepository:

    def get_all(self):

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
                COALESCE(u.last_login, '')
            FROM users u
            JOIN roles r
                ON r.id = u.role_id
            ORDER BY u.username
        """)

        users = []

        for row in cursor.fetchall():

            user = User(
                id=row[0],
                username=row[1],
                password_hash=row[2],
                full_name=row[3],
                email=row[4],
                role_id=row[5],
                is_active=bool(row[7]),
                last_login=row[8],
            )

            user.role_name = row[6]

            users.append(user)

        conn.close()

        return users

    def roles(self):

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, name
            FROM roles
            ORDER BY name
        """)

        rows = cursor.fetchall()

        conn.close()

        return rows

    def add(self, user: User):

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
            VALUES (?,?,?,?,?,?)
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

    def update(self, user: User):

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE users
            SET
                full_name=?,
                email=?,
                role_id=?,
                is_active=?
            WHERE id=?
        """, (
            user.full_name,
            user.email,
            user.role_id,
            int(user.is_active),
            user.id,
        ))

        conn.commit()
        conn.close()

    def delete(self, user_id):

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM users WHERE id=?",
            (user_id,),
        )

        conn.commit()
        conn.close()

    def reset_password(self, user_id, password_hash):

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE users
            SET password_hash=?
            WHERE id=?
        """, (
            password_hash,
            user_id,
        ))

        conn.commit()
        conn.close()