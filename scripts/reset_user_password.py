"""Reset one FlowLab Pro PostgreSQL user's password from the server console."""

import argparse
import getpass
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database.database import database_backend, managed_connection
from app.modules.auth.service import AuthService


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username", help="Existing FlowLab Pro username")
    args = parser.parse_args()

    if database_backend() != "postgresql":
        raise SystemExit(
            "PostgreSQL is not configured in this PowerShell window. Set FLOWLAB_DATABASE_URL first."
        )

    password = getpass.getpass("New temporary password: ")
    confirmation = getpass.getpass("Confirm temporary password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match; no change was made.")
    if len(password) < 10:
        raise SystemExit("Use at least 10 characters; no change was made.")

    with managed_connection() as connection:
        user = connection.execute(
            "SELECT id FROM users WHERE LOWER(username)=LOWER(?)", (args.username,)
        ).fetchone()
        if not user:
            raise SystemExit(f"User not found: {args.username}")
        connection.execute(
            """UPDATE users
               SET password_hash=?, is_active=1, must_change_password=1
               WHERE id=?""",
            (AuthService.hash_password(password), user[0]),
        )

    print(f"Password reset completed for {args.username}. A password change is required at sign-in.")


if __name__ == "__main__":
    main()
