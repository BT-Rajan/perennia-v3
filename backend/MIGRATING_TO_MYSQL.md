# Migrating from SQLite to MySQL

The app was already built dialect-agnostic (see the note at the top of
`app/db.py`): every model and query goes through SQLAlchemy's ORM, so
the exact same code runs against SQLite, MySQL, or Postgres — only
`DATABASE_URL` changes. This doc covers the parts that aren't
automatic: installing a driver, creating the MySQL database, and
(if you have existing local data) copying it over.

## 1. Install a driver

Already pinned in `requirements.txt`: `pymysql==1.1.1`, a pure-Python
driver — no system `libmysqlclient` needed.

```bash
pip install -r requirements.txt
```

## 2. Create the MySQL database

Use `utf8mb4` (not `utf8`) so every Unicode character — including
emoji, used nowhere in this app today but cheap to get right up
front — fits:

```sql
CREATE DATABASE perennia CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'perennia'@'localhost' IDENTIFIED BY 'change-me';
GRANT ALL PRIVILEGES ON perennia.* TO 'perennia'@'localhost';
FLUSH PRIVILEGES;
```

MySQL 5.7.7+ / MariaDB 10.2.2+ is required — both default
`innodb_large_prefix` on, which every indexed column here (longest is
`lead.email`, `String(254)`) fits well within.

## 3. Point `DATABASE_URL` at it

In `backend/.env`:

```
DATABASE_URL=mysql+pymysql://perennia:change-me@localhost:3306/perennia
```

## 4. Create the schema

Same command as always — `Base.metadata.create_all()` builds the
schema fresh on whatever `DATABASE_URL` points at:

```bash
python scripts/init_db.py
```

This also bootstraps the first admin account if the target database
has no `admin_user` rows yet (see the script's docstring).

## 5. Copy existing data (only if you have a local SQLite DB with real data)

If `backend/data/perennia.db` is empty or doesn't exist, skip this —
step 4 already gave you a ready-to-use empty MySQL database.

Otherwise, with `DATABASE_URL` in `.env` already pointed at the
**target** MySQL database:

```bash
# Preview what would be copied — writes nothing:
python scripts/migrate_sqlite_to_mysql.py --sqlite-path ./data/perennia.db --dry-run

# Actually copy:
python scripts/migrate_sqlite_to_mysql.py --sqlite-path ./data/perennia.db
```

The script creates the MySQL schema itself (same `create_all()` call
as `init_db.py`), then copies every table's rows over in
foreign-key-safe order. It refuses to overwrite a target table that
already has rows unless you pass `--truncate` — so it's safe to run
`--dry-run` as many times as you like first.

## Notes / things that don't change

- **No app code changes needed.** Every `String` column already
  declares an explicit length (MySQL requires this for indexed
  columns; SQLite and Postgres don't, so this was already correct
  for portability, not added for this migration).
- **`JSON` columns** (`translations`, `transcript`, `events`, etc.)
  map to MySQL's native `JSON` type automatically.
- **`DateTime(timezone=True)` columns**: like SQLite, MySQL has no
  true tz-aware storage — both dialects silently store naive
  datetimes. This app already accounts for that (see
  `calendar_sync_service.py`), so migrated timestamps behave exactly
  as they did on SQLite.
- **Tests** (`tests/conftest.py`) intentionally keep using a temp
  SQLite file regardless of `DATABASE_URL` in `.env` — fast, isolated,
  no MySQL dependency for CI. Nothing to change there.
