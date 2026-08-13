#!/usr/bin/env python3
"""
Adds the columns introduced for full Google Calendar control (true
event updates + two-way drift detection) to a database that was
created before this change:

    appointment.calendar_drift
    calendar_credential.sync_token
    calendar_credential.last_synced_at

There's no Alembic in this project (see scripts/init_db.py — schema is
managed via Base.metadata.create_all, which only creates *missing
tables*, never new columns on a table that already exists). This
script fills that one gap for anyone upgrading an existing install; a
brand new install doesn't need it, since create_all() already includes
these columns for a table it's creating from scratch.

Safe to re-run: every ALTER is skipped if the column is already there.
Works against SQLite, Postgres, or MySQL — whatever DATABASE_URL points
at — via SQLAlchemy's inspector rather than dialect-specific SQL.

    python scripts/migrate_add_calendar_sync_columns.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect, text

from app.config import settings
from app.db import engine

# (table, column, DDL type) — DDL type kept dialect-generic (works
# unmodified on SQLite/Postgres/MySQL, same reasoning as db.py's
# comment on why this app never hand-writes dialect-specific SQL).
_COLUMNS = [
    ("appointment", "calendar_drift", "VARCHAR(500)"),
    ("calendar_credential", "sync_token", "TEXT"),
    ("calendar_credential", "last_synced_at", "DATETIME"),
]


def main() -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table, column, ddl_type in _COLUMNS:
            if table not in existing_tables:
                print(f"Skipping {table}.{column} — table doesn't exist yet "
                      f"(will be created with this column by init_db.py).")
                continue
            existing_columns = {c["name"] for c in inspector.get_columns(table)}
            if column in existing_columns:
                print(f"{table}.{column} already present — skipping.")
                continue
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))
            print(f"Added {table}.{column} ({ddl_type}).")

    print(f"Done against {settings.DATABASE_URL}")


if __name__ == "__main__":
    main()
