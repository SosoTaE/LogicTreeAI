#!/usr/bin/env python3
"""
Bootstrap CLI for creating / updating the admin user.

Usage:
    python create_admin.py
    python create_admin.py --username alice
    python create_admin.py --username alice --password s3cret  (non-interactive)

If the user exists, the script offers to promote them to admin and reset
the password. Only this script can create the first account — once an
admin exists, further users are created through the admin UI / API.
"""
import argparse
import getpass
import logging
import sys

from logging_config import setup_logging
from models import init_db, get_session, create_user, User, ROLE_ADMIN

setup_logging()
logger = logging.getLogger('create_admin')


def prompt_username(default=None):
    while True:
        prompt = f"Admin username [{default}]: " if default else "Admin username: "
        value = input(prompt).strip() or (default or '')
        if value:
            return value
        print("Username cannot be empty.")


def prompt_password():
    while True:
        pw = getpass.getpass("Password (min 6 chars): ")
        if len(pw) < 6:
            print("Password must be at least 6 characters.")
            continue
        confirm = getpass.getpass("Confirm password: ")
        if pw != confirm:
            print("Passwords do not match. Try again.")
            continue
        return pw


def main():
    parser = argparse.ArgumentParser(description="Create or promote an admin user.")
    parser.add_argument('--username', help="Admin username")
    parser.add_argument('--password', help="Admin password (prompted if omitted)")
    parser.add_argument('--force', action='store_true',
                        help="If the user exists, promote to admin and reset password without prompting.")
    args = parser.parse_args()

    init_db()

    username = args.username or prompt_username()
    password = args.password or prompt_password()

    db = get_session()
    try:
        existing = db.query(User).filter_by(username=username).first()
        if existing:
            if not args.force:
                print(f"User '{username}' already exists (role: {existing.role}).")
                answer = input("Promote to admin and reset password? [y/N]: ").strip().lower()
                if answer not in ('y', 'yes'):
                    print("Aborted.")
                    return 1
            existing.role = ROLE_ADMIN
            existing.set_password(password)
            db.commit()
            logger.info("Admin promoted via CLI: user_id=%s username=%s", existing.id, existing.username)
            print(f"Updated '{username}' -> role=admin, password reset.")
            return 0

        user = create_user(db, username, password, role=ROLE_ADMIN)
        db.commit()
        logger.info("Admin created via CLI: user_id=%s username=%s", user.id, user.username)
        print(f"Created admin user '{user.username}' (id={user.id}).")
        return 0
    except ValueError as e:
        db.rollback()
        logger.warning("Admin CLI rejected: %s", e)
        print(f"Error: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        db.rollback()
        logger.exception("Admin CLI failed")
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 2
    finally:
        db.close()


if __name__ == '__main__':
    sys.exit(main())
