"""Tests for the one-time database setup (setup_database.py) - uses a throw-away SQLite file, no MySQL needed.
Run:  py database_setup_test.py"""
import os, re, shutil, sqlite3, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, "..", "..", "LAPTOP2_Server")
PASS = FAIL = 0


def check(name, ok, extra=""):
    global PASS, FAIL
    PASS += ok
    FAIL += (not ok)
    print(("PASS " if ok else "FAIL ") + name, "" if ok else extra)


def setup(dirpath, *args, stdin=""):
    env = dict(os.environ, PAWPET_DB="sqlite", PAWPET_SQLITE_PATH=os.path.join(dirpath, "t.db"))
    env.pop("PAWPET_TEST_FIXED_PASSWORDS", None)
    r = subprocess.run([sys.executable, "setup_database.py", *args], cwd=dirpath, env=env, input=stdin, capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout + r.stderr


def rows(dirpath, sql):
    return sqlite3.connect(os.path.join(dirpath, "t.db")).execute(sql).fetchall()


def fresh_dir():
    d = tempfile.mkdtemp()
    shutil.copytree(SERVER, os.path.join(d, "s"), ignore=shutil.ignore_patterns("__pycache__", "*.db", "FIRST_RUN_PASSWORDS.txt"))
    return os.path.join(d, "s")


sql = open(os.path.join(SERVER, "database", "schema.sql"), encoding="utf-8").read()
latest = int(re.findall(r"INSERT INTO schema_version\(version, description\) VALUES \((\d+)", sql)[-1])
code = open(os.path.join(SERVER, "db.py"), encoding="utf-8").read()
check("schema.sql version equals db.SCHEMA_VERSION", latest == int(re.search(r"SCHEMA_VERSION = (\d+)", code).group(1)))
check("schema.sql has no IF NOT EXISTS", "IF NOT EXISTS" not in sql.upper())

d = fresh_dir()
rc, out = setup(d)
check("fresh install ok", rc == 0 and "fresh database" in out, out)
check("11 tables", len(rows(d, "select name from sqlite_master where type='table' and name not like 'sqlite_%'")) == 11)
check("4 accounts + passwords file", rows(d, "select count(*) from users")[0][0] == 4 and os.path.exists(os.path.join(d, "FIRST_RUN_PASSWORDS.txt")))
rc, out = setup(d)
check("second run changes nothing", rc == 0 and "Nothing to do" in out and rows(d, "select count(*) from users")[0][0] == 4, out)
rc, out = setup(d, "--reset", stdin="no\n")
check("reset can be cancelled", rc == 1 and rows(d, "select count(*) from users")[0][0] == 4, out)
rows(d, "select 1")
c = sqlite3.connect(os.path.join(d, "t.db")); c.execute("insert into schema_version(version, description) values (9,'x')"); c.commit(); c.close()
rc, out = setup(d)
check("newer database version is refused", rc == 1 and "newer" in out, out)
c = sqlite3.connect(os.path.join(d, "t.db")); c.execute("delete from schema_version where version=9"); c.commit(); c.close()
rc, out = setup(d, "--reset", "--yes")
check("reset --yes rebuilds", rc == 0 and rows(d, "select count(*) from users")[0][0] == 4 and rows(d, "select count(*) from schema_version")[0][0] == 1, out)

d2 = fresh_dir()                                  # database made by an OLD PawPet
c = sqlite3.connect(os.path.join(d2, "t.db"))
c.executescript("""CREATE TABLE users(id INTEGER PRIMARY KEY AUTOINCREMENT, username VARCHAR(50) NOT NULL UNIQUE, password VARCHAR(64) NOT NULL,
 full_name VARCHAR(100) NOT NULL, email VARCHAR(100), phone VARCHAR(30), role VARCHAR(20) NOT NULL DEFAULT 'customer', active TINYINT NOT NULL DEFAULT 1, created_at VARCHAR(19) NOT NULL);
 CREATE TABLE products(id INTEGER PRIMARY KEY AUTOINCREMENT, name VARCHAR(100) NOT NULL, category VARCHAR(40) NOT NULL, price DOUBLE NOT NULL, stock INT NOT NULL DEFAULT 0, reorder_level INT NOT NULL DEFAULT 5, emoji VARCHAR(8));
 INSERT INTO users(username,password,full_name,role,created_at) VALUES('admin','x','Old Admin','admin','2026-01-01 00:00:00');
 INSERT INTO products(name,category,price,stock) VALUES('OldFood','Food',100,7);""")
c.commit(); c.close()
rc, out = setup(d2)
check("old database upgraded", rc == 0 and "older PawPet" in out, out)
check("old data kept", rows(d2, "select username from users") == [("admin",)] and rows(d2, "select name, stock from products") == [("OldFood", 7)])
check("old stock got a batch", rows(d2, "select qty from batches") == [(7,)])
check("old users table got must_change", "must_change" in [r[1] for r in rows(d2, "pragma table_info(users)")])
check("stamped version", rows(d2, "select version from schema_version") == [(latest,)])
print("\nPASS %d  FAIL %d" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
