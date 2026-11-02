"""PawPet - one-time database setup.      Run on the SERVER laptop with MySQL started:

    py setup_database.py              set up (or upgrade) the database, nothing is deleted
    py setup_database.py --reset      DELETE every table and start again with fresh sample data (asks first)

What it does, in order:
  1. creates the database if it is missing (MySQL),
  2. empty database            -> runs database/schema.sql, then adds the sample data and the first-run accounts,
  3. database from an OLD PawPet (tables but no schema_version) -> adds only what is missing, keeps all data,
  4. already on the current version -> says so and does nothing,
  5. older numbered version    -> applies the entries of db.UPGRADES in order.
The server (app.py) never creates or changes tables; it only checks that this step was done.
"""
import os
import sys
from datetime import date, timedelta

import db as dbmod
from db import Conn, SCHEMA_VERSION, UPGRADES
from app import TEST_FIXED_PASSWORDS, hash_pw, now, temp_password


def say(msg=""):
    print(msg, flush=True)


# sample data (fresh databases only)
def seed(c):
    t = now()
    ins = c.execute
    accounts = [("admin", "Clinic Admin", "admin@pawpet.ph", "09170000001", "admin", 1),
                ("staff", "Nurse Joy Reyes", "joy@pawpet.ph", "09170000002", "staff", 1),
                ("megan", "Megan Cruz", "megan@mail.com", "09171234567", "customer", 0),
                ("lester", "Lester John Jatico", "lester@mail.com", "09181234567", "customer", 0)]
    fixed = {"admin": "admin123", "staff": "staff123", "megan": "pass123", "lester": "pass123"}
    lines = []
    for username, full, email, phone, role, must in accounts:
        pw = fixed[username] if TEST_FIXED_PASSWORDS else temp_password()
        ins("INSERT INTO users(username,password,full_name,email,phone,role,must_change,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (username, hash_pw(pw), full, email, phone, role, 0 if TEST_FIXED_PASSWORDS else must, t))
        lines.append(f"{role:9} {username:8} {pw}")
    if not TEST_FIXED_PASSWORDS:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "FIRST_RUN_PASSWORDS.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("PawPet first-run passwords (random). admin and staff must change theirs at first sign-in.\n"
                    "Keep this file private and delete it after you have noted the passwords.\n\n"
                    + "\n".join(lines) + "\n")
        print("\n  First run: sample accounts were created with RANDOM passwords.\n  They are saved in " + path + "\n\n  "
              + "\n  ".join(lines) + "\n")
    for p in [(3, "Buddy", "Dog", "Golden Retriever", 5, 28, "Allergic to chicken"),
              (3, "Mochi", "Cat", "Puspin", 2, 4, ""),
              (4, "Brock", "Dog", "Aspin", 3, 15, "")]:
        ins("INSERT INTO pets(owner_id,name,species,breed,age,weight,notes) VALUES(?,?,?,?,?,?,?)", p)

    def days(n):
        return (date.today() + timedelta(days=n)).strftime("%Y-%m-%d")
    # name, category, price, stock, reorder level, emoji, [(batch no, qty, expiry)]
    for name, cat, price, stock, rl, emoji, batches in [
            ("Premium Dog Food 5kg", "Food", 1250, 24, 8, "🦴", [("PF-2610", 24, days(300))]),
            ("Cat Dry Food 3kg", "Food", 890, 18, 8, "🐟", [("CF-2609", 18, days(260))]),
            ("Dewormer Syrup", "Medicine", 180, 40, 10, "💊", [("DW-001", 25, days(240)), ("DW-002", 15, days(25))]),
            ("Anti-Tick Shampoo", "Grooming", 320, 12, 5, "🧴", [("AT-001", 12, days(500))]),
            ("Vitamin Drops", "Medicine", 260, 4, 6, "💧", [("VD-001", 4, days(-10))]),
            ("Chew Toy Bone", "Toys", 150, 30, 8, "🦴", [("TY-001", 30, None)]),
            ("Cat Litter 10L", "Hygiene", 410, 15, 5, "🧺", [("CL-001", 15, None)]),
            ("Pet Carrier Small", "Accessories", 1450, 6, 3, "🧳", [("PC-001", 6, None)]),
            ("Flea Collar", "Accessories", 220, 0, 5, "📿", []),
            ("Rabies Vaccine Dose", "Medicine", 450, 20, 6, "💉", [("RV-001", 20, days(90))])]:
        pid = ins("INSERT INTO products(name,category,price,stock,reorder_level,emoji) VALUES(?,?,?,?,?,?)",
                  (name, cat, price, stock, rl, emoji))
        for bno, bq, bexp in batches:
            ins("INSERT INTO batches(product_id,batch_no,qty,expiry_date,received_at) VALUES(?,?,?,?,?)",
                (pid, bno, bq, bexp, t))
    for s in [("Wellness Checkup", "Full physical exam and weight check", 350, 30, "🩺"),
              ("Vaccination", "Core vaccines with record card", 500, 30, "💉"),
              ("Deworming", "Safe deworming and advice", 250, 30, "💊"),
              ("Grooming", "Bath, trim and nail clipping", 600, 60, "🛁"),
              ("Dental Cleaning", "Scaling and polish", 1200, 60, "🦷"),
              ("Minor Surgery", "Consultation required first", 3500, 90, "🏥")]:
        ins("INSERT INTO services(name,description,price,duration,emoji) VALUES(?,?,?,?,?)", s)
    # work_days: 0 = Monday ... 6 = Sunday
    for v in [("Dr. Dave Singer", "General Practice", "0,1,2,3,4", "09:00", "17:00"),
              ("Dr. Anna Thomas", "Surgery", "1,2,3,4,5", "10:00", "18:00"),
              ("Dr. Paolo Lim", "Dermatology", "0,2,4,5", "09:00", "15:00")]:
        ins("INSERT INTO vets(name,specialty,work_days,start_time,end_time) VALUES(?,?,?,?,?)", v)
    today = date.today()

    def day(n):
        return (today + timedelta(days=n)).strftime("%Y-%m-%d")

    def at(n, hhmm):
        return day(n) + " " + hhmm + ":00"
    vets = {v["id"]: v["work_days"].split(",") for v in c.query("SELECT id, work_days FROM vets")}

    def slot(n, vet, step=1):
        """Day n from today for this vet; moves (forward, or back with step=-1) to a day the vet works (0 = Monday)."""
        while str((today + timedelta(days=n)).weekday()) not in vets[vet]:
            n += step
        return day(n)
    # (customer, pet, service, vet, date, time, status, notes, created)
    appts = [(3, 1, 2, 1, slot(-1, 1, -1), "10:00", "completed", "Annual vaccine", at(-3, "09:15")),
             (3, 1, 1, 1, slot(0, 1), "10:00", "confirmed", "", at(-1, "14:30")),
             (4, 3, 2, 2, slot(0, 2), "11:00", "pending", "", at(0, "08:05")),
             (3, 2, 3, 1, slot(1, 1), "09:30", "pending", "", at(0, "08:40")),
             (4, 3, 1, 3, slot(2, 3), "13:00", "confirmed", "", at(0, "09:10"))]
    ids = []
    for a in appts:
        ids.append(ins("""INSERT INTO appointments(customer_id,pet_id,service_id,vet_id,appt_date,appt_time,status,notes,created_at)
                          VALUES(?,?,?,?,?,?,?,?,?)""", (a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7], a[8])))
    # (customer, appointment, kind, item, qty, amount, when)
    for s in [(3, ids[0], "service", "Vaccination", 1, 500, at(-1, "10:40")),
              (3, None, "product", "Premium Dog Food 5kg", 1, 1250, at(-1, "10:45")),
              (4, None, "product", "Dewormer Syrup", 2, 360, at(-2, "15:20")),
              (None, None, "product", "Chew Toy Bone", 3, 450, at(-3, "11:05")),
              (3, None, "service", "Wellness Checkup", 1, 350, at(-5, "09:50"))]:
        ins("INSERT INTO sales(customer_id,appointment_id,kind,item_name,qty,amount,created_at) VALUES(?,?,?,?,?,?,?)", s)
    ins("INSERT INTO notifications(user_id,title,body,created_at) VALUES(3,'Welcome to PawPet','Book your first visit anytime.',?)", (t,))


def migrate_batches(c):
    """Older databases have stock but no batches yet: give every stocked product one starting batch.
    The sample medicines get demo expiry dates so the expiry alerts can be seen right away."""
    demo = {"Dewormer Syrup": 240, "Vitamin Drops": 20, "Rabies Vaccine Dose": 90}
    t = now()
    for p in c.query("SELECT id,name,category,stock FROM products WHERE stock>0"):
        if c.query("SELECT 1 AS x FROM batches WHERE product_id=? LIMIT 1", (p["id"],)):
            continue
        exp = None
        if p["name"] in demo:
            exp = (date.today() + timedelta(days=demo[p["name"]])).strftime("%Y-%m-%d")
        c.execute("INSERT INTO batches(product_id,batch_no,qty,expiry_date,received_at) VALUES(?,?,?,?,?)",
                  (p["id"], "INITIAL", p["stock"], exp, t))


# the steps
def create_database_if_missing():
    """MySQL only: connects without a database and creates it when it is not there yet."""
    if dbmod.ENGINE == "sqlite":
        return
    root = Conn(database=False)
    cur = root.raw.cursor()
    cur.execute("SHOW DATABASES LIKE %s", (dbmod.MYSQL_NAME,))
    if cur.fetchone():
        say("Database '%s' already exists." % dbmod.MYSQL_NAME)
    else:
        cur.execute("CREATE DATABASE `%s` CHARACTER SET utf8mb4" % dbmod.MYSQL_NAME)
        root.raw.commit()
        say("Created database '%s'." % dbmod.MYSQL_NAME)
    cur.close()
    root.close()


def run_statements(c, statements):
    for stmt in statements:
        c.execute(stmt)


def fresh_install(c):
    say("Creating the tables from database/schema.sql ...")
    run_statements(c, dbmod.schema_statements())
    say("Adding sample data and the first-run accounts ...")
    seed(c)
    migrate_batches(c)          # gives the sample products their starting batches
    say("Done: fresh database at schema version %d." % SCHEMA_VERSION)


def upgrade_old_database(c):
    """A database made by an earlier PawPet (before schema_version existed): add what is missing, keep the data."""
    say("This database has tables from an older PawPet. Adding only what is missing (no data is deleted) ...")
    have = dbmod.existing_tables(c)
    stmts = dbmod.schema_statements()
    for stmt in stmts:                                           # 1) tables that do not exist yet
        t = dbmod.table_of(stmt)
        if t and t not in have:
            c.execute(stmt)
            say("  + table %s" % t)
    cols = {r["n"].lower() for r in (c.query("SELECT name AS n FROM pragma_table_info('users')") if dbmod.ENGINE == "sqlite"
            else c.query("SELECT column_name AS n FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='users'"))}
    if "must_change" not in cols:                                # 2) columns added by later versions
        c.execute("ALTER TABLE users ADD COLUMN must_change %s NOT NULL DEFAULT 0" % ("INTEGER" if dbmod.ENGINE == "sqlite" else "TINYINT"))
        say("  + column users.must_change")
    if dbmod.ENGINE != "sqlite":
        c.execute("ALTER TABLE users MODIFY password VARCHAR(200) NOT NULL")   # room for the new password hashes
    for stmt in stmts:                                           # 3) indexes that are missing
        if stmt.upper().startswith("CREATE INDEX"):
            try:
                c.execute(stmt)
                say("  + index %s" % stmt.split()[2])
            except Exception as e:
                if "exists" not in str(e).lower() and "duplicate key name" not in str(e).lower():
                    raise
                try:
                    c.raw.rollback()
                except Exception:
                    pass
    migrate_batches(c)                                           # 4) old stock gets a starting batch
    if not c.query("SELECT 1 AS x FROM schema_version"):
        c.execute("INSERT INTO schema_version(version, description) VALUES (?, ?)", (SCHEMA_VERSION, "Upgraded from an older PawPet"))
    say("Done: database is now at schema version %d." % SCHEMA_VERSION)


def apply_upgrades(c, version):
    for v in sorted(UPGRADES):
        if v > version:
            say("Applying upgrade to version %d ..." % v)
            for stmt in UPGRADES[v]:
                c.execute(stmt)
            c.execute("INSERT INTO schema_version(version, description) VALUES (?, ?)", (v, "Upgrade"))
    say("Done: database is now at schema version %d." % max(UPGRADES or {SCHEMA_VERSION: 0}))


def drop_everything(c):
    say("Deleting every PawPet table ...")
    if dbmod.ENGINE == "sqlite":
        for t in dbmod.existing_tables(c):
            c.raw.execute("DROP TABLE %s" % t)
        c.raw.commit()
    else:
        cur = c.raw.cursor()
        cur.execute("SET FOREIGN_KEY_CHECKS=0")
        for t in dbmod.existing_tables(c):
            cur.execute("DROP TABLE `%s`" % t)
        cur.execute("SET FOREIGN_KEY_CHECKS=1")
        c.raw.commit()
        cur.close()


def run(reset=False, assume_yes=False):
    create_database_if_missing()
    c = Conn()
    try:
        if reset and dbmod.existing_tables(c):
            if not assume_yes and input("This DELETES ALL PawPet data (users, pets, appointments, sales...). Type YES to continue: ").strip() != "YES":
                say("Cancelled. Nothing was changed.")
                return 1
            drop_everything(c)
        tables = dbmod.existing_tables(c)
        version = dbmod.current_version(c)
        if not tables:
            fresh_install(c)
        elif version is None:
            upgrade_old_database(c)
        elif version == SCHEMA_VERSION:
            say("The database is already set up (schema version %d). Nothing to do." % version)
        elif version < SCHEMA_VERSION:
            apply_upgrades(c, version)
        else:
            say("The database is on version %d, newer than this server (%d). Use the newer PawPet files." % (version, SCHEMA_VERSION))
            return 1
    finally:
        c.close()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(run(reset="--reset" in sys.argv, assume_yes="--yes" in sys.argv))
    except Exception as e:                      # a short, readable reason instead of a long traceback
        say("\nSetup could not finish: %s" % e)
        say("Is MySQL started in XAMPP? Is the password right (PAWPET_DB_PASSWORD)?")
        sys.exit(1)
