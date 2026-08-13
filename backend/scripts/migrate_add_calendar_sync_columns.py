#!/usr/bin/env python3
"""
One-off column migration for calendar sync — superseded by app.db.sync_schema(),
which now runs automatically on every app startup and covers this (and any
future) model column additively. Kept as a thin manual entry point for anyone
who wants to apply pending schema changes without restarting the server.

    python scripts/migrate_add_calendar_sync_columns.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.db import sync_schema


def main() -> None:
    sync_schema()
    print(f"Schema synced against {settings.DATABASE_URL}")


if __name__ == "__main__":
    main()
