#!/usr/bin/env python3
"""
Generates the secrets .env needs. Run once per environment (dev, staging,
prod each get their own — never share a SECRET_KEY or ENCRYPTION_KEY
across environments, and never commit the output).

    python scripts/gen_secrets.py
    python scripts/gen_secrets.py --password "correct horse battery staple"
"""
from __future__ import annotations

import argparse
import getpass
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cryptography.fernet import Fernet
from passlib.context import CryptContext

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--password", help="Admin password to hash (prompts securely if omitted)")
    parser.add_argument("--username", default="admin", help="Bootstrap admin username")
    args = parser.parse_args()

    password = args.password or getpass.getpass("Admin password to hash: ")
    if len(password) < 12:
        print("WARNING: password is shorter than 12 characters — consider something longer.", file=sys.stderr)

    print("# Paste these into your .env — generated fresh, never reuse across environments.\n")
    print(f"SECRET_KEY={secrets.token_urlsafe(48)}")
    print(f"ENCRYPTION_KEY={Fernet.generate_key().decode()}")
    print(f"BOOTSTRAP_ADMIN_USERNAME={args.username}")
    print(f"BOOTSTRAP_ADMIN_PASSWORD_HASH={_pwd_ctx.hash(password)}")


if __name__ == "__main__":
    main()
