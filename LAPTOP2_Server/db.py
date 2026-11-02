"""Database layer for PawPet.

Default engine is MySQL (PyMySQL). Set PAWPET_DB=sqlite to use a local file instead
(handy for quick tests without MySQL installed).

MySQL settings (environment variables, defaults in brackets):
    PAWPET_DB_HOST [localhost]   PAWPET_DB_PORT [3306]
    PAWPET_DB_USER [root]        PAWPET_DB_PASSWORD []
    PAWPET_DB_NAME [pawpet]
"""
import os
import re
import sqlite3

ENGINE = os.environ.get("PAWPET_DB", "mysql").lower()
SQLITE_PATH = os.environ.get("PAWPET_SQLITE_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "pawpet.db"))

MYSQL_CFG = dict(
    host=os.environ.get("PAWPET_DB_HOST", "localhost"),
    port=int(os.environ.get("PAWPET_DB_PORT", "3306")),
    user=os.environ.get("PAWPET_DB_USER", "root"),
    password=os.environ.get("PAWPET_DB_PASSWORD", ""),
)
MYSQL_NAME = os.environ.get("PAWPET_DB_NAME", "pawpet")

class Conn:
    """Tiny wrapper so app.py is identical for MySQL and SQLite. SQL is written with ? placeholders."""

    def __init__(self, database=True):
        if ENGINE == "sqlite":
            self.raw = sqlite3.connect(SQLITE_PATH)
            self.raw.row_factory = sqlite3.Row
        else:
            import pymysql
            import pymysql.cursors
            cfg = dict(MYSQL_CFG, charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor, autocommit=False,
                       connect_timeout=5, read_timeout=15, write_timeout=15,
                       init_command="SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")
            if database:
                cfg["database"] = MYSQL_NAME
            self.raw = pymysql.connect(**cfg)

    def _sql(self, sql):
        return sql if ENGINE == "sqlite" else sql.replace("?", "%s")

    def query(self, sql, args=()):
        cur = self.raw.cursor()
        cur.execute(self._sql(sql), tuple(args))
        rs = cur.fetchall()
        cur.close()
        return [dict(r) for r in rs]

    def execute(self, sql, args=()):
        cur = self.raw.cursor()
        cur.execute(self._sql(sql), tuple(args))
        last = cur.lastrowid
        cur.close()
        self.raw.commit()
        return last

    def close(self):
        try:
            self.raw.close()
        except Exception:
            pass


# schema (the tables live in database/schema.sql)
SCHEMA_VERSION = 1        # must match the last INSERT INTO schema_version in database/schema.sql
SCHEMA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database", "schema.sql")
# Future changes: bump SCHEMA_VERSION, add the change to schema.sql AND list it here, e.g.
#   UPGRADES = {2: ["ALTER TABLE pets ADD COLUMN birthday VARCHAR(10)"]}
# setup_database.py applies every entry above the database's current version, in order.
UPGRADES = {}


class SetupNeeded(Exception):
    """The database is missing, empty or on another schema version: setup_database.py must be run."""


def schema_statements():
    """The statements of database/schema.sql for the current engine (without CREATE DATABASE / USE / SET:
    setup_database.py creates and selects the database itself)."""
    with open(SCHEMA_FILE, encoding="utf-8") as f:
        text = "\n".join(re.sub(r"\s*--.*$", "", line) for line in f.read().splitlines())      # drop comments
    out = []
    for stmt in (s.strip() for s in text.split(";")):
        head = stmt[:20].upper()
        if not stmt or head.startswith(("CREATE DATABASE", "USE ", "SET ")):
            continue
        if ENGINE == "sqlite":
            stmt = (stmt.replace("INT AUTO_INCREMENT PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
                        .replace(") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4", ")")
                        .replace(") ENGINE=InnoDB", ")"))
        out.append(stmt)
    return out


def table_of(stmt):
    """'CREATE TABLE users(...' -> 'users'  (None for other statements)."""
    words = stmt.replace("(", " ( ").split()
    return words[2].lower() if len(words) > 2 and words[0].upper() == "CREATE" and words[1].upper() == "TABLE" else None


def existing_tables(c):
    if ENGINE == "sqlite":
        rs = c.query("SELECT name AS n FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    else:
        rs = c.query("SELECT table_name AS n FROM information_schema.tables WHERE table_schema=DATABASE()")
    return {r["n"].lower() for r in rs}


def current_version(c):
    """Schema version stored in the database, or None when there is no schema_version table (empty / old DB)."""
    if "schema_version" not in existing_tables(c):
        return None
    rs = c.query("SELECT MAX(version) AS v FROM schema_version")
    return rs[0]["v"] if rs and rs[0]["v"] is not None else None


def connect_checked():
    """Open the database for the server. Never creates or changes anything: raises SetupNeeded with a plain
    message when the database is not ready."""
    try:
        c = Conn()
    except Exception as e:
        if ENGINE == "sqlite":
            raise
        text = str(e)
        if "Unknown database" in text or "1049" in text:
            raise SetupNeeded("The database '%s' does not exist yet." % MYSQL_NAME)
        raise
    v = current_version(c)
    if v is None:
        c.close()
        raise SetupNeeded("The database '%s' has not been set up (no schema_version table)." % MYSQL_NAME)
    if v != SCHEMA_VERSION:
        c.close()
        raise SetupNeeded("The database is on schema version %s but this server needs version %s." % (v, SCHEMA_VERSION))
    return c
