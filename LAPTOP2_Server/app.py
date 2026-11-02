"""PawPet server - Flask REST API on top of MySQL.

Run:  py -m pip install -r requirements.txt  ->  py app.py   (API at http://<your-pc-ip>:5000/api)

Safety rules built in (see PAWPET_GUIDE.md):
  * every booking / stock change runs inside WRITE_LOCK, so two requests can never take the same slot or the same stock
  * all input is validated (types, lengths, ranges, dates) and bad input returns a JSON 400, never a crash
  * passwords use PBKDF2 with a per-user salt, logins are rate limited, tokens expire after 30 days
  * accounts that still use a known default password must change it before doing anything else
"""
import hashlib
import hmac
import math
import os
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, date
from functools import wraps

from flask import Flask, g, jsonify, request
from werkzeug.exceptions import HTTPException

import db as dbmod
from db import Conn


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024          # no request body above 64 KB

# One lock for every operation that checks something and then changes it (booking, stock, completing a visit).
# The server runs as ONE process, so this is enough to make those operations safe when many users act together.
WRITE_LOCK = threading.RLock()

TEST_FIXED_PASSWORDS = os.environ.get("PAWPET_TEST_FIXED_PASSWORDS") == "1"   # automated tests only
TOKEN_DAYS = 30
PW_ITERATIONS = 200_000
KNOWN_DEFAULTS = ("admin123", "staff123", "pass123")
MAX_FUTURE_DAYS = 180
MAX_ACTIVE_APPTS_PER_CUSTOMER = 10
MAX_PETS_PER_CUSTOMER = 20
STATUSES = ("pending", "confirmed", "completed", "cancelled", "no_show")
STAFF = ("staff", "admin")


# database

def db():
    if "db" not in g:
        g.db = Conn()
    return g.db


@app.teardown_appcontext
def close_db(_):
    d = g.pop("db", None)
    if d:
        d.close()


def q(sql, args=(), one=False):
    rs = db().query(sql, args)
    return (rs[0] if rs else None) if one else rs


def run(sql, args=()):
    return db().execute(sql, args)


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def rows(rs):
    return [dict(r) for r in rs]


def notify(user_id, title, body=""):
    run("INSERT INTO notifications(user_id,title,body,created_at) VALUES(?,?,?,?)",
        (user_id, title[:120], body[:500], now()))


def fresh_read():
    """End the current database transaction so the next SELECT sees everything other requests have already saved.
    (MySQL otherwise keeps showing the data as it was when this request first touched the database.)"""
    db().raw.commit()


def locked(fn):
    @wraps(fn)
    def wrap(*a, **kw):
        with WRITE_LOCK:
            fresh_read()
            return fn(*a, **kw)
    return wrap


# input validation

class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message, self.status = message, status


@app.errorhandler(ApiError)
def api_error(e):
    return jsonify(error=e.message), e.status


@app.errorhandler(Exception)
def any_error(e):
    if isinstance(e, HTTPException):
        msg = {413: "That request is too large.", 405: "Method not allowed.", 404: "Not found."}.get(e.code, e.description)
        return jsonify(error=msg), e.code
    app.logger.exception("Unhandled error on %s %s", request.method, request.path)
    return jsonify(error="Something went wrong on the server. Please try again."), 500


def body():
    d = request.get_json(silent=True)
    if not isinstance(d, dict):
        raise ApiError("Please send the form data as a JSON object.")
    return d


def text(d, key, label, maxlen, required=False, default=""):
    v = d.get(key)
    if v is None:
        v = ""
    if isinstance(v, bool) or not isinstance(v, (str, int, float)):
        raise ApiError(f"{label} is not valid.")
    v = str(v).strip()
    if not v:
        if required:
            raise ApiError(f"{label} is required.")
        return default
    if len(v) > maxlen:
        raise ApiError(f"{label} must be at most {maxlen} characters.")
    if any(ord(c) < 32 and c not in "\n\r\t" for c in v):
        raise ApiError(f"{label} has invalid characters.")
    return v


def num(d, key, label, lo=None, hi=None, integer=False, required=True, default=None):
    v = d.get(key)
    if v is None or (isinstance(v, str) and not v.strip()):
        if required:
            raise ApiError(f"{label} is required.")
        return default
    if isinstance(v, (bool, list, dict)):
        raise ApiError(f"{label} must be a number.")
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ApiError(f"{label} must be a number.")
    if math.isnan(x) or math.isinf(x):
        raise ApiError(f"{label} must be a number.")
    if integer:
        if x != int(x):
            raise ApiError(f"{label} must be a whole number.")
        x = int(x)
    if lo is not None and x < lo:
        raise ApiError(f"{label} must be at least {lo}.")
    if hi is not None and x > hi:
        raise ApiError(f"{label} must be at most {hi}.")
    return x


def valid_iso(s):
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except (TypeError, ValueError):
        return False


def valid_hhmm(s):
    return isinstance(s, str) and re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", s) is not None


def appt_date_ok(s):
    if not valid_iso(s):
        raise ApiError("Date must look like 2026-12-31.")
    d = datetime.strptime(s, "%Y-%m-%d").date()
    if d < date.today():
        raise ApiError("You cannot book a date that has already passed.")
    if d > date.today() + timedelta(days=MAX_FUTURE_DAYS):
        raise ApiError(f"Appointments can only be booked up to {MAX_FUTURE_DAYS} days ahead.")
    return s


def work_days_ok(v):
    parts = [p.strip() for p in str(v).split(",") if p.strip() != ""]
    if not parts or any(p not in "0123456" or len(p) != 1 for p in parts):
        raise ApiError("Working days must be numbers 0-6 (0 = Monday ... 6 = Sunday), separated by commas.")
    return ",".join(sorted(set(parts)))


EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,200}\.[^@\s]{2,}$")
PHONE_RE = re.compile(r"^[0-9+()\- ]{0,30}$")
USER_RE = re.compile(r"^[A-Za-z0-9_.\-]{3,50}$")


def contact_fields(d):
    email = text(d, "email", "Email", 100)
    phone = text(d, "phone", "Phone", 30)
    if email and not EMAIL_RE.match(email):
        raise ApiError("Email address is not valid.")
    if phone and not PHONE_RE.match(phone):
        raise ApiError("Phone may only contain digits, spaces and + - ( ).")
    return email, phone


# passwords, tokens, rate limits

def hash_pw(p, salt=None):
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", p.encode(), bytes.fromhex(salt), PW_ITERATIONS).hex()
    return f"pbkdf2${PW_ITERATIONS}${salt}${h}"


def legacy_hash(p):
    return hashlib.sha256(("pawpet$" + p).encode()).hexdigest()


def check_pw(p, stored):
    try:
        if stored.startswith("pbkdf2$"):
            _, it, salt, h = stored.split("$")
            calc = hashlib.pbkdf2_hmac("sha256", p.encode(), bytes.fromhex(salt), int(it)).hex()
            return hmac.compare_digest(calc, h)
        return hmac.compare_digest(legacy_hash(p), stored)
    except Exception:
        return False


DUMMY_HASH = hash_pw("not-a-real-password")


def password_rules(p, username=""):
    if not isinstance(p, str) or len(p) < 8:
        raise ApiError("Password must be at least 8 characters.")
    if len(p) > 128:
        raise ApiError("Password must be at most 128 characters.")
    if not (re.search(r"[A-Za-z]", p) and re.search(r"\d", p)):
        raise ApiError("Password needs at least one letter and one number.")
    if p in KNOWN_DEFAULTS or (username and p.lower() == username.lower()):
        raise ApiError("Choose a password that is not a common or default one.")


def temp_password():
    letters, digits = "abcdefghjkmnpqrstuvwxyz", "23456789"
    pw = [secrets.choice(letters.upper()), secrets.choice(letters), secrets.choice(digits)]
    pw += [secrets.choice(letters + digits) for _ in range(7)]
    secrets.SystemRandom().shuffle(pw)
    return "".join(pw)


_hits = defaultdict(deque)
_hits_lock = threading.Lock()


def rate_limited(key, limit, window, record=False):
    """True when `key` already used up `limit` hits in the last `window` seconds."""
    t = time.time()
    with _hits_lock:
        if len(_hits) > 5000:                                  # forget old keys so memory cannot grow without limit
            for k in [k for k, v in _hits.items() if not v or v[-1] < t - 3600]:
                del _hits[k]
        dq = _hits[key]
        while dq and dq[0] < t - window:
            dq.popleft()
        if len(dq) >= limit:
            return True
        if record:
            dq.append(t)
        return False


def clear_hits(key):
    with _hits_lock:
        _hits.pop(key, None)


def client_ip():
    return request.remote_addr or "?"


def token_cutoff():
    return (datetime.now() - timedelta(days=TOKEN_DAYS)).strftime("%Y-%m-%d %H:%M:%S")


def current_user():
    h = request.headers.get("Authorization", "")
    tok = h.replace("Bearer ", "").strip()
    if not tok or len(tok) > 64:
        return None
    return q("""SELECT u.* FROM tokens t JOIN users u ON u.id=t.user_id
                WHERE t.token=? AND u.active=1 AND t.created_at>=?""", (tok, token_cutoff()), one=True)


ALLOWED_WHEN_MUST_CHANGE = ("change_password", "logout", "me")


def auth(*roles):
    def deco(fn):
        @wraps(fn)
        def wrap(*a, **kw):
            u = current_user()
            if not u:
                return jsonify(error="Please sign in again."), 401
            if u["must_change"] and request.endpoint not in ALLOWED_WHEN_MUST_CHANGE:
                return jsonify(error="Please change your temporary password first.", must_change=True), 403
            if roles and u["role"] not in roles:
                return jsonify(error="Not allowed."), 403
            g.user = u
            return fn(*a, **kw)
        return wrap
    return deco


def is_staff_request():
    u = current_user()
    return bool(u and u["role"] in STAFF and not u["must_change"])


def user_json(u):
    d = {k: u[k] for k in ("id", "username", "full_name", "email", "phone", "role")}
    d["must_change"] = bool(u["must_change"])
    return d


# startup checks (tables are made by setup_database.py)

def flag_default_passwords(c):
    """Any account that still uses admin123 / staff123 / pass123 must change it at its next sign-in."""
    if TEST_FIXED_PASSWORDS:
        return
    for u in c.query("SELECT id,password FROM users WHERE must_change=0"):
        if any(check_pw(p, u["password"]) for p in KNOWN_DEFAULTS):
            c.execute("UPDATE users SET must_change=1 WHERE id=?", (u["id"],))


# batches / expiry helpers

EXPIRY_WARN_DAYS = 30


def today_str():
    return date.today().strftime("%Y-%m-%d")


def batch_info():
    """product_id -> {'expired': qty already expired, 'next': earliest upcoming expiry}"""
    t = today_str()
    info = {}
    for b in q("SELECT product_id, qty, expiry_date FROM batches WHERE qty>0"):
        i = info.setdefault(b["product_id"], {"expired": 0, "next": None})
        if b["expiry_date"]:
            if b["expiry_date"] < t:
                i["expired"] += b["qty"]
            elif i["next"] is None or b["expiry_date"] < i["next"]:
                i["next"] = b["expiry_date"]
    return info


def product_view(p, info, staff=True):
    """`stock` is what can really be sold (expired batches are not counted)."""
    p = dict(p)
    i = info.get(p["id"], {"expired": 0, "next": None})
    physical = p["stock"]
    p["stock"] = max(physical - i["expired"], 0)
    if staff:                                   # customers do not need the internal numbers
        p["physical_stock"] = physical
        p["expired_qty"] = i["expired"]
        p["next_expiry"] = i["next"]
    return p


def usable_stock(pid):
    p = q("SELECT stock FROM products WHERE id=?", (pid,), one=True)
    if not p:
        return 0
    return max(p["stock"] - batch_info().get(pid, {"expired": 0})["expired"], 0)


def add_batch(pid, qty, batch_no="", expiry=None):
    run("INSERT INTO batches(product_id,batch_no,qty,expiry_date,received_at) VALUES(?,?,?,?,?)",
        (pid, (batch_no or "")[:40], qty, expiry or None, now()))
    run("UPDATE products SET stock=stock+? WHERE id=?", (qty, pid))


def deduct_stock(pid, qty, include_expired=False):
    """Take stock from the batches that expire first (FEFO). Callers check the stock first, under WRITE_LOCK."""
    t = today_str()
    left = qty
    sql = "SELECT * FROM batches WHERE product_id=? AND qty>0"
    args = [pid]
    if not include_expired:
        sql += " AND (expiry_date IS NULL OR expiry_date >= ?)"
        args.append(t)
    sql += " ORDER BY CASE WHEN expiry_date IS NULL THEN 1 ELSE 0 END, expiry_date, id"
    for b in q(sql, args):
        if left <= 0:
            break
        take = min(b["qty"], left)
        run("UPDATE batches SET qty=qty-? WHERE id=?", (take, b["id"]))
        left -= take
    run("UPDATE products SET stock=stock-? WHERE id=?", (qty, pid))


def batch_status(expiry):
    if not expiry:
        return "no_expiry", None
    days = (datetime.strptime(expiry, "%Y-%m-%d").date() - date.today()).days
    if days < 0:
        return "expired", days
    if days <= EXPIRY_WARN_DAYS:
        return "expiring", days
    return "ok", days


def batch_rows(only_active=True, product_id=None):
    sql = """SELECT b.id, b.product_id, p.name AS product_name, p.category, b.batch_no, b.qty,
                    b.expiry_date, b.received_at
             FROM batches b JOIN products p ON p.id=b.product_id WHERE 1=1"""
    args = []
    if only_active:
        sql += " AND b.qty>0"
    if product_id:
        sql += " AND b.product_id=?"
        args.append(product_id)
    out = []
    for b in q(sql + " ORDER BY CASE WHEN b.expiry_date IS NULL THEN 1 ELSE 0 END, b.expiry_date, b.id", args):
        b = dict(b)
        b["status"], b["days_left"] = batch_status(b["expiry_date"])
        out.append(b)
    return out


# auth endpoints

@app.post("/api/register")
def register():
    ip = "reg:" + client_ip()
    if rate_limited(ip, 20, 3600, record=True):
        raise ApiError("Too many sign-ups from this device. Please try again later.", 429)
    d = body()
    username = text(d, "username", "Username", 50, required=True)
    if not USER_RE.match(username):
        raise ApiError("Username must be 3-50 letters, numbers, dot, dash or underscore.")
    full_name = text(d, "full_name", "Full name", 100, required=True)
    email, phone = contact_fields(d)
    pw = d.get("password")
    password_rules(pw, username)
    if q("SELECT 1 FROM users WHERE LOWER(username)=?", (username.lower(),), one=True):
        raise ApiError("Username is already taken.", 409)
    with WRITE_LOCK:
        fresh_read()
        if q("SELECT 1 FROM users WHERE LOWER(username)=?", (username.lower(),), one=True):
            raise ApiError("Username is already taken.", 409)
        uid = run("INSERT INTO users(username,password,full_name,email,phone,role,created_at) VALUES(?,?,?,?,?,'customer',?)",
                  (username, hash_pw(pw), full_name, email, phone, now()))
    notify(uid, "Welcome to PawPet", "Add your pet and book your first visit.")
    return jsonify(ok=True), 201


@app.post("/api/login")
def login():
    d = body()
    username = str(d.get("username", "")).strip()[:50]
    password = d.get("password", "")
    password = password if isinstance(password, str) else ""
    ukey, ikey = "login-u:" + username.lower(), "login-ip:" + client_ip()
    if rate_limited(ukey, 5, 600) or rate_limited(ikey, 60, 600):
        return jsonify(error="Too many failed attempts. Please wait 10 minutes and try again."), 429
    u = q("SELECT * FROM users WHERE LOWER(username)=? AND active=1", (username.lower(),), one=True)
    ok = check_pw(password[:128], u["password"] if u else DUMMY_HASH) and u is not None
    if not ok:
        rate_limited(ukey, 5, 600, record=True)
        rate_limited(ikey, 60, 600, record=True)
        return jsonify(error="Wrong username or password."), 401
    clear_hits(ukey)
    role_wanted = d.get("portal")  # 'admin' portal only for staff/admin
    if role_wanted == "admin" and u["role"] not in STAFF:
        return jsonify(error="This portal is for clinic staff only."), 403
    if not u["password"].startswith("pbkdf2$"):                    # upgrade an old SHA-256 hash
        run("UPDATE users SET password=? WHERE id=?", (hash_pw(password), u["id"]))
    if not TEST_FIXED_PASSWORDS and password in KNOWN_DEFAULTS and not u["must_change"]:
        run("UPDATE users SET must_change=1 WHERE id=?", (u["id"],))
    u = q("SELECT * FROM users WHERE id=?", (u["id"],), one=True)
    run("DELETE FROM tokens WHERE created_at<?", (token_cutoff(),))
    tok = secrets.token_hex(24)
    run("INSERT INTO tokens(token,user_id,created_at) VALUES(?,?,?)", (tok, u["id"], now()))
    return jsonify(token=tok, user=user_json(u))


@app.post("/api/logout")
@auth()
def logout():
    tok = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    run("DELETE FROM tokens WHERE token=?", (tok,))
    return jsonify(ok=True)


@app.get("/api/me")
@auth()
def me():
    return jsonify(user_json(g.user))


@app.post("/api/change-password")
@auth()
def change_password():
    d = body()
    old, new = d.get("old_password", ""), d.get("new_password", "")
    if not isinstance(old, str) or not check_pw(old[:128], g.user["password"]):
        if rate_limited("chg:" + str(g.user["id"]), 5, 600, record=True):
            raise ApiError("Too many attempts. Please wait 10 minutes.", 429)
        raise ApiError("Your current password is not correct.", 403)
    password_rules(new, g.user["username"])
    if new == old:
        raise ApiError("The new password must be different from the old one.")
    tok = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    run("UPDATE users SET password=?, must_change=0 WHERE id=?", (hash_pw(new), g.user["id"]))
    run("DELETE FROM tokens WHERE user_id=? AND token<>?", (g.user["id"], tok))     # sign out other devices
    return jsonify(ok=True)


@app.post("/api/users/<int:uid>/reset-password")
@auth(*STAFF)
def reset_password(uid):
    """Staff can reset a customer's password; an admin can reset anybody's. Returns a one-time temporary password."""
    u = q("SELECT * FROM users WHERE id=?", (uid,), one=True)
    if not u:
        raise ApiError("User not found.", 404)
    if u["role"] != "customer" and g.user["role"] != "admin":
        raise ApiError("Only an admin can reset staff accounts.", 403)
    if u["id"] == g.user["id"]:
        raise ApiError("Use Change password for your own account.")
    tmp = temp_password()
    run("UPDATE users SET password=?, must_change=1 WHERE id=?", (hash_pw(tmp), uid))
    run("DELETE FROM tokens WHERE user_id=?", (uid,))
    return jsonify(temp_password=tmp, username=u["username"])


# catalog (public-ish)

@app.get("/api/products")
def products():
    cat = text(request.args, "category", "Category", 40)
    s = text(request.args, "q", "Search", 100)
    sql, args = "SELECT * FROM products WHERE 1=1", []
    if cat and cat != "All":
        sql += " AND category=?"
        args.append(cat)
    if s:
        sql += " AND name LIKE ?"
        args.append(f"%{s}%")
    info = batch_info()
    staff = is_staff_request()
    return jsonify([product_view(p, info, staff) for p in q(sql + " ORDER BY name", args)])


@app.get("/api/services")
def services():
    return jsonify(rows(q("SELECT * FROM services ORDER BY name")))


@app.get("/api/vets")
def vets():
    return jsonify(rows(q("SELECT * FROM vets WHERE active=1 ORDER BY name")))


def slot_window(vet):
    """(start, end) datetimes of a vet's day, or None when the vet record is unusable."""
    try:
        start = datetime.strptime(vet["start_time"], "%H:%M")
        end = datetime.strptime(vet["end_time"], "%H:%M")
    except (ValueError, TypeError):
        return None
    return (start, end) if end > start else None


def busy_blocks(vet_id, the_date, exclude_id=None):
    out = []
    for b in q("""SELECT a.id, a.appt_time, s.duration FROM appointments a JOIN services s ON s.id=a.service_id
                  WHERE a.vet_id=? AND a.appt_date=? AND a.status IN ('pending','confirmed')""", (vet_id, the_date)):
        if exclude_id and b["id"] == exclude_id:
            continue
        try:
            bs = datetime.strptime(b["appt_time"], "%H:%M")
        except ValueError:
            continue
        out.append((b["id"], bs, bs + timedelta(minutes=max(b["duration"], 30))))
    return out


def slots_for(vet, service, the_date):
    """Return list of {time, available} for a vet on a date. Past dates and non-working days give no slots."""
    try:
        d = datetime.strptime(the_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return []
    win = slot_window(vet)
    if win is None or d < date.today():
        return []
    if str(d.weekday()) not in [x.strip() for x in str(vet["work_days"]).split(",")]:
        return []
    start, end = win
    step = 30
    dur = max(service["duration"], 30) if service else 30
    busy = [(bs, be) for _, bs, be in busy_blocks(vet["id"], the_date)]
    out = []
    cur = start
    while cur + timedelta(minutes=dur) <= end:
        ce = cur + timedelta(minutes=dur)
        free = all(ce <= bs or cur >= be for bs, be in busy)
        if d == date.today() and cur <= datetime.now().replace(year=1900, month=1, day=1):
            free = False
        out.append({"time": cur.strftime("%H:%M"), "available": free})
        cur += timedelta(minutes=step)
    return out


def overlapping(vet_id, the_date, the_time, duration, exclude_id=None, only_older_than=None):
    """ids of active appointments that overlap [the_time, the_time+duration) for this vet."""
    cs = datetime.strptime(the_time, "%H:%M")
    ce = cs + timedelta(minutes=max(duration, 30))
    hits = []
    for bid, bs, be in busy_blocks(vet_id, the_date, exclude_id):
        if only_older_than and bid >= only_older_than:
            continue
        if not (ce <= bs or cs >= be):
            hits.append(bid)
    return hits


@app.get("/api/availability")
def availability():
    vid = num(request.args, "vet_id", "Veterinarian", 1, integer=True)
    the_date = text(request.args, "date", "Date", 10, required=True)
    if not valid_iso(the_date):
        raise ApiError("Date must look like 2026-12-31.")
    vet = q("SELECT * FROM vets WHERE id=?", (vid,), one=True)
    if not vet:
        raise ApiError("Vet not found.", 404)
    sid = num(request.args, "service_id", "Service", 1, integer=True, required=False)
    svc = q("SELECT * FROM services WHERE id=?", (sid,), one=True) if sid else None
    return jsonify(slots_for(vet, svc, the_date))


# customer: pets & appointments

@app.get("/api/pets")
@auth()
def my_pets():
    if g.user["role"] in STAFF and request.args.get("all"):
        return jsonify(rows(q("""SELECT p.*, u.full_name AS owner_name FROM pets p
                                 JOIN users u ON u.id=p.owner_id ORDER BY p.name""")))
    return jsonify(rows(q("SELECT * FROM pets WHERE owner_id=? ORDER BY name", (g.user["id"],))))


@app.post("/api/pets")
@auth()
@locked
def add_pet():
    d = body()
    name = text(d, "name", "Pet name", 60, required=True)
    species = text(d, "species", "Species", 30, required=True)
    breed = text(d, "breed", "Breed", 60)
    age = num(d, "age", "Age", 0, 60, required=False)
    weight = num(d, "weight", "Weight", 0, 500, required=False)
    notes = text(d, "notes", "Notes", 255)
    owner = g.user["id"]
    if g.user["role"] in STAFF and d.get("owner_id"):
        owner = num(d, "owner_id", "Owner", 1, integer=True)
        if not q("SELECT 1 FROM users WHERE id=? AND role='customer'", (owner,), one=True):
            raise ApiError("Customer not found.", 404)
    if q("SELECT COUNT(*) AS n FROM pets WHERE owner_id=?", (owner,), one=True)["n"] >= MAX_PETS_PER_CUSTOMER:
        raise ApiError(f"A customer can have at most {MAX_PETS_PER_CUSTOMER} pets.", 409)
    pid = run("INSERT INTO pets(owner_id,name,species,breed,age,weight,notes) VALUES(?,?,?,?,?,?,?)",
              (owner, name, species, breed, age, weight, notes))
    return jsonify(id=pid), 201


@app.delete("/api/pets/<int:pid>")
@auth()
@locked
def del_pet(pid):
    p = q("SELECT * FROM pets WHERE id=?", (pid,), one=True)
    if not p or (p["owner_id"] != g.user["id"] and g.user["role"] not in STAFF):
        return jsonify(error="Pet not found."), 404
    if q("SELECT 1 FROM appointments WHERE pet_id=? AND status IN ('pending','confirmed')", (pid,), one=True):
        return jsonify(error="This pet has an active appointment."), 409
    if q("SELECT 1 FROM appointments WHERE pet_id=?", (pid,), one=True):
        return jsonify(error="This pet has visit history, so it cannot be removed."), 409
    run("DELETE FROM pets WHERE id=?", (pid,))
    return jsonify(ok=True)


APPT_SQL = """
SELECT a.*, u.full_name AS customer_name, u.phone AS customer_phone,
       p.name AS pet_name, p.species, p.breed, p.age AS pet_age, p.notes AS pet_notes,
       s.name AS service_name, s.price AS service_price, s.duration, s.emoji AS service_emoji,
       v.name AS vet_name
FROM appointments a
JOIN users u ON u.id=a.customer_id
JOIN pets p ON p.id=a.pet_id
JOIN services s ON s.id=a.service_id
JOIN vets v ON v.id=a.vet_id
"""


@app.get("/api/appointments")
@auth()
def list_appts():
    sql, args = APPT_SQL + " WHERE 1=1", []
    if g.user["role"] not in STAFF:
        sql += " AND a.customer_id=?"
        args.append(g.user["id"])
    the_date = text(request.args, "date", "Date", 10)
    if the_date:
        if not valid_iso(the_date):
            raise ApiError("Date must look like 2026-12-31.")
        sql += " AND a.appt_date=?"
        args.append(the_date)
    st = text(request.args, "status", "Status", 20)
    if st:
        if st not in STATUSES:
            raise ApiError("Unknown status.")
        sql += " AND a.status=?"
        args.append(st)
    vid = num(request.args, "vet_id", "Veterinarian", 1, integer=True, required=False)
    if vid:
        sql += " AND a.vet_id=?"
        args.append(vid)
    return jsonify(rows(q(sql + " ORDER BY a.appt_date, a.appt_time", args)))


def book_slot(cust, pet, vet, svc, the_date, the_time, notes, status, followup_of=None):
    """Check the slot and insert, under WRITE_LOCK. A second check after the insert protects even if two
    server processes were ever started by mistake (the newer booking gives way)."""
    with WRITE_LOCK:
        fresh_read()
        ok = [s for s in slots_for(vet, svc, the_date) if s["time"] == the_time and s["available"]]
        if not ok or overlapping(vet["id"], the_date, the_time, svc["duration"]):
            raise ApiError("That time is no longer available. Please pick another slot.", 409)
        aid = run("""INSERT INTO appointments(customer_id,pet_id,service_id,vet_id,appt_date,appt_time,status,notes,followup_of,created_at)
                     VALUES(?,?,?,?,?,?,?,?,?,?)""",
                  (cust, pet, svc["id"], vet["id"], the_date, the_time, status, notes, followup_of, now()))
        if overlapping(vet["id"], the_date, the_time, svc["duration"], exclude_id=aid, only_older_than=aid):
            run("DELETE FROM appointments WHERE id=?", (aid,))
            raise ApiError("That time was just taken by someone else. Please pick another slot.", 409)
        return aid


@app.post("/api/appointments")
@auth()
def book():
    d = body()
    pet_id = num(d, "pet_id", "Pet", 1, integer=True)
    service_id = num(d, "service_id", "Service", 1, integer=True)
    vet_id = num(d, "vet_id", "Veterinarian", 1, integer=True)
    the_date = appt_date_ok(text(d, "appt_date", "Date", 10, required=True))
    the_time = text(d, "appt_time", "Time", 5, required=True)
    if not valid_hhmm(the_time):
        raise ApiError("Time must look like 09:30.")
    notes = text(d, "notes", "Notes", 500)
    cust = g.user["id"]
    if g.user["role"] in STAFF and d.get("customer_id"):
        cust = num(d, "customer_id", "Customer", 1, integer=True)
        if not q("SELECT 1 FROM users WHERE id=? AND role='customer' AND active=1", (cust,), one=True):
            raise ApiError("Customer not found.", 404)
    pet = q("SELECT * FROM pets WHERE id=? AND owner_id=?", (pet_id, cust), one=True)
    if not pet:
        return jsonify(error="Pet not found for this customer."), 404
    vet = q("SELECT * FROM vets WHERE id=? AND active=1", (vet_id,), one=True)
    svc = q("SELECT * FROM services WHERE id=?", (service_id,), one=True)
    if not vet or not svc:
        return jsonify(error="Vet or service not found."), 404
    if g.user["role"] not in STAFF:
        n = q("""SELECT COUNT(*) AS n FROM appointments WHERE customer_id=? AND status IN ('pending','confirmed')
                 AND appt_date>=?""", (cust, today_str()), one=True)["n"]
        if n >= MAX_ACTIVE_APPTS_PER_CUSTOMER:
            raise ApiError(f"You already have {n} upcoming appointments. Please cancel one or wait for the visit.", 409)
    aid = book_slot(cust, pet["id"], vet, svc, the_date, the_time, notes,
                    "confirmed" if g.user["role"] in STAFF else "pending")
    notify(cust, "Appointment booked",
           f"{pet['name']} - {svc['name']} with {vet['name']} on {the_date} at {the_time}.")
    return jsonify(id=aid), 201


@app.post("/api/appointments/<int:aid>/cancel")
@auth()
@locked
def cancel(aid):
    a = q("SELECT * FROM appointments WHERE id=?", (aid,), one=True)
    if not a or (a["customer_id"] != g.user["id"] and g.user["role"] not in STAFF):
        return jsonify(error="Appointment not found."), 404
    if a["status"] not in ("pending", "confirmed"):
        return jsonify(error="This appointment can no longer be cancelled."), 409
    run("UPDATE appointments SET status='cancelled' WHERE id=?", (aid,))
    notify(a["customer_id"], "Appointment cancelled", f"Appointment #{aid} was cancelled.")
    return jsonify(ok=True)


# staff: appointment workflow

# what a staff member may change an appointment to (finished visits use /complete so the sale is recorded)
TRANSITIONS = {"pending": ("confirmed", "cancelled", "no_show"),
               "confirmed": ("cancelled", "no_show")}


@app.post("/api/appointments/<int:aid>/status")
@auth(*STAFF)
@locked
def set_status(aid):
    d = body()
    st = d.get("status")
    if st not in STATUSES:
        return jsonify(error="Invalid status."), 400
    notes = text(d, "notes", "Notes", 500) if d.get("notes") is not None else None
    a = q("SELECT * FROM appointments WHERE id=?", (aid,), one=True)
    if not a:
        return jsonify(error="Appointment not found."), 404
    if st == "completed":
        return jsonify(error="Use Complete visit so the sale is recorded."), 400
    if st not in TRANSITIONS.get(a["status"], ()):
        return jsonify(error=f"A {a['status'].replace('_', ' ')} appointment cannot be changed to {st.replace('_', ' ')}."), 409
    run("UPDATE appointments SET status=?, notes=COALESCE(?,notes) WHERE id=?", (st, notes, aid))
    msg = {"confirmed": "Your appointment is confirmed.",
           "cancelled": "Your appointment was cancelled by the clinic.",
           "no_show": "You missed your appointment. Please rebook."}.get(st)
    if msg:
        notify(a["customer_id"], f"Appointment {st.replace('_', ' ')}", msg)
    return jsonify(ok=True)


@app.post("/api/appointments/<int:aid>/complete")
@auth(*STAFF)
@locked
def complete(aid):
    """Record the completed service (+ optional products used) as sales. Everything is checked BEFORE anything is saved."""
    d = request.get_json(silent=True) or {}
    if not isinstance(d, dict):
        raise ApiError("Please send the form data as a JSON object.")
    a = q(APPT_SQL + " WHERE a.id=?", (aid,), one=True)
    if not a:
        return jsonify(error="Appointment not found."), 404
    if a["status"] == "completed":
        return jsonify(error="Already completed."), 409
    if a["status"] not in ("pending", "confirmed"):
        return jsonify(error=f"A {a['status'].replace('_', ' ')} appointment cannot be completed."), 409
    notes = text(d, "notes", "Notes", 500) if d.get("notes") is not None else None
    items = d.get("products") or []
    if not isinstance(items, list) or len(items) > 50:
        raise ApiError("Products must be a list of up to 50 items.")
    wanted = {}
    for it in items:
        if not isinstance(it, dict):
            raise ApiError("Each product needs a product_id and qty.")
        pid = num(it, "product_id", "Product", 1, integer=True)
        qty = num(it, "qty", "Quantity", 1, 10000, integer=True, required=False, default=1)
        wanted[pid] = wanted.get(pid, 0) + qty
    prods = {}
    for pid, qty in wanted.items():
        p = q("SELECT * FROM products WHERE id=?", (pid,), one=True)
        if not p:
            raise ApiError(f"Product #{pid} was not found.", 404)
        if usable_stock(pid) < qty:
            return jsonify(error=f"Not enough usable stock for {p['name']} (expired items are not counted). "
                                 "Nothing was saved."), 409
        prods[pid] = p
    # all checks passed: now save
    run("UPDATE appointments SET status='completed', notes=COALESCE(?,notes) WHERE id=?", (notes, aid))
    run("INSERT INTO sales(customer_id,appointment_id,kind,item_name,qty,amount,created_at) VALUES(?,?,?,?,?,?,?)",
        (a["customer_id"], aid, "service", a["service_name"], 1, a["service_price"], now()))
    total = a["service_price"]
    for pid, qty in wanted.items():
        p = prods[pid]
        deduct_stock(pid, qty)
        amount = round(p["price"] * qty, 2)
        run("INSERT INTO sales(customer_id,appointment_id,kind,item_name,qty,amount,created_at) VALUES(?,?,?,?,?,?,?)",
            (a["customer_id"], aid, "product", p["name"], qty, amount, now()))
        total += amount
    notify(a["customer_id"], "Visit completed", f"{a['pet_name']}'s visit is done. Total: PHP {total:,.2f}.")
    return jsonify(ok=True, total=round(total, 2))


@app.post("/api/appointments/<int:aid>/followup")
@auth(*STAFF)
def followup(aid):
    d = body()
    the_date = appt_date_ok(text(d, "appt_date", "Date", 10, required=True))
    the_time = text(d, "appt_time", "Time", 5, required=True)
    if not valid_hhmm(the_time):
        raise ApiError("Time must look like 09:30.")
    notes = text(d, "notes", "Notes", 500, default="Follow-up visit")
    a = q("SELECT * FROM appointments WHERE id=?", (aid,), one=True)
    if not a:
        return jsonify(error="Appointment not found."), 404
    if a["status"] != "completed":
        return jsonify(error="Follow-ups are scheduled after a visit is completed."), 409
    vet = q("SELECT * FROM vets WHERE id=?", (a["vet_id"],), one=True)
    svc = q("SELECT * FROM services WHERE id=?", (a["service_id"],), one=True)
    try:
        nid = book_slot(a["customer_id"], a["pet_id"], vet, svc, the_date, the_time, notes, "confirmed", followup_of=aid)
    except ApiError as e:
        if e.status == 409:
            raise ApiError("That follow-up slot is not available.", 409)
        raise
    notify(a["customer_id"], "Follow-up scheduled", f"Follow-up on {the_date} at {the_time}.")
    return jsonify(id=nid), 201


@app.post("/api/reminders/send")
@auth(*STAFF)
def send_reminders():
    tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    today = today_str()
    n = 0
    for a in q(APPT_SQL + " WHERE a.appt_date IN (?,?) AND a.status IN ('pending','confirmed')", (today, tomorrow)):
        when = "today" if a["appt_date"] == today else "tomorrow"
        msg = f"{a['pet_name']} has {a['service_name']} {when} at {a['appt_time']} with {a['vet_name']}."
        if q("""SELECT 1 FROM notifications WHERE user_id=? AND title='Appointment reminder' AND body=?
                AND substr(created_at,1,10)=?""", (a["customer_id"], msg, today), one=True):
            continue                       # already reminded today: no duplicates
        notify(a["customer_id"], "Appointment reminder", msg)
        n += 1
    return jsonify(sent=n)


# staff: customers, inventory, vets

@app.get("/api/customers")
@auth(*STAFF)
def customers():
    s = text(request.args, "q", "Search", 100)
    sql = """SELECT u.id,u.username,u.full_name,u.email,u.phone,u.active,u.created_at,
             (SELECT COUNT(*) FROM pets p WHERE p.owner_id=u.id) AS pet_count,
             (SELECT COUNT(*) FROM appointments a WHERE a.customer_id=u.id) AS appt_count
             FROM users u WHERE u.role='customer'"""
    args = []
    if s:
        sql += " AND (u.full_name LIKE ? OR u.username LIKE ? OR u.phone LIKE ?)"
        args = [f"%{s}%"] * 3
    return jsonify(rows(q(sql + " ORDER BY u.full_name", args)))


@app.get("/api/customers/<int:cid>")
@auth(*STAFF)
def customer_detail(cid):
    u = q("SELECT id,username,full_name,email,phone,active,created_at FROM users WHERE id=? AND role='customer'",
          (cid,), one=True)
    if not u:
        return jsonify(error="Customer not found."), 404
    return jsonify(customer=dict(u),
                   pets=rows(q("SELECT * FROM pets WHERE owner_id=?", (cid,))),
                   appointments=rows(q(APPT_SQL + " WHERE a.customer_id=? ORDER BY a.appt_date DESC", (cid,))))


@app.post("/api/customers")
@auth(*STAFF)
@locked
def add_customer():
    d = body()
    username = text(d, "username", "Username", 50, required=True)
    if not USER_RE.match(username):
        raise ApiError("Username must be 3-50 letters, numbers, dot, dash or underscore.")
    full_name = text(d, "full_name", "Full name", 100, required=True)
    email, phone = contact_fields(d)
    if q("SELECT 1 FROM users WHERE LOWER(username)=?", (username.lower(),), one=True):
        raise ApiError("Username is already taken.", 409)
    pw = d.get("password")
    given = isinstance(pw, str) and pw != ""
    if given:
        password_rules(pw, username)
    else:
        pw = temp_password()
    uid = run("""INSERT INTO users(username,password,full_name,email,phone,role,must_change,created_at)
                 VALUES(?,?,?,?,?,'customer',1,?)""", (username, hash_pw(pw), full_name, email, phone, now()))
    out = {"id": uid}
    if not given:
        out["temp_password"] = pw          # shown once to the staff member; the customer must change it
    return jsonify(out), 201


@app.post("/api/customers/<int:cid>/toggle")
@auth("admin")
def toggle_customer(cid):
    run("UPDATE users SET active=1-active WHERE id=? AND role='customer'", (cid,))
    run("DELETE FROM tokens WHERE user_id=?", (cid,))
    return jsonify(ok=True)


@app.post("/api/products")
@auth(*STAFF)
@locked
def add_product():
    d = body()
    name = text(d, "name", "Product name", 100, required=True)
    category = text(d, "category", "Category", 40, default="Other")
    price = round(num(d, "price", "Price", 0, 1_000_000), 2)
    stock = num(d, "stock", "Stock", 0, 100_000, integer=True, required=False, default=0)
    reorder = num(d, "reorder_level", "Reorder level", 0, 100_000, integer=True, required=False, default=5)
    emoji = text(d, "emoji", "Emoji", 8, default="🐾")
    batch_no = text(d, "batch_no", "Batch number", 40, default="INITIAL")
    expiry = text(d, "expiry_date", "Expiry date", 10) or None
    if expiry and not valid_iso(expiry):
        raise ApiError("Expiry date must look like YYYY-MM-DD.")
    pid = run("INSERT INTO products(name,category,price,stock,reorder_level,emoji) VALUES(?,?,?,?,?,?)",
              (name, category, price, 0, reorder, emoji))
    if stock > 0:
        add_batch(pid, stock, batch_no, expiry)
    return jsonify(id=pid), 201


@app.put("/api/products/<int:pid>")
@auth(*STAFF)
@locked
def edit_product(pid):
    d = body()
    p = q("SELECT * FROM products WHERE id=?", (pid,), one=True)
    if not p:
        return jsonify(error="Product not found."), 404
    name = text(d, "name", "Product name", 100, default=p["name"]) if "name" in d else p["name"]
    category = text(d, "category", "Category", 40, default=p["category"]) if "category" in d else p["category"]
    price = round(num(d, "price", "Price", 0, 1_000_000, required=False, default=p["price"]), 2)
    reorder = num(d, "reorder_level", "Reorder level", 0, 100_000, integer=True, required=False, default=p["reorder_level"])
    usable = usable_stock(pid)
    stock = num(d, "stock", "Stock", 0, 100_000, integer=True, required=False, default=usable)   # shown to staff = usable stock
    run("UPDATE products SET name=?,category=?,price=?,reorder_level=? WHERE id=?", (name, category, price, reorder, pid))
    diff = stock - usable              # stock edits keep the batch list in step
    if diff > 0:
        add_batch(pid, diff, "ADJUST", None)
    elif diff < 0:
        deduct_stock(pid, -diff)
    return jsonify(ok=True)


@app.post("/api/products/<int:pid>/adjust")
@auth(*STAFF)
@locked
def adjust_stock(pid):
    d = body()
    p = q("SELECT * FROM products WHERE id=?", (pid,), one=True)
    if not p:
        return jsonify(error="Product not found."), 404
    delta = num(d, "delta", "Change", -100_000, 100_000, integer=True, required=False, default=0)
    if delta < 0 and usable_stock(pid) + delta < 0:
        return jsonify(error="Stock cannot go below zero."), 409
    if delta > 0:
        add_batch(pid, delta, "ADJUST", None)
    elif delta < 0:
        deduct_stock(pid, -delta)
    return jsonify(stock=usable_stock(pid))


@app.post("/api/products/<int:pid>/restock")
@auth(*STAFF)
@locked
def restock(pid):
    """Receive a new batch (quantity, batch number, expiry date)."""
    d = body()
    if not q("SELECT 1 AS x FROM products WHERE id=?", (pid,), one=True):
        return jsonify(error="Product not found."), 404
    qty = num(d, "qty", "Quantity", 1, 100_000, integer=True)
    expiry = text(d, "expiry_date", "Expiry date", 10) or None
    if expiry and not valid_iso(expiry):
        raise ApiError("Expiry date must look like YYYY-MM-DD.")
    if expiry and expiry < today_str():
        raise ApiError("That expiry date is already in the past.")
    add_batch(pid, qty, text(d, "batch_no", "Batch number", 40) or "BATCH", expiry)
    return jsonify(stock=usable_stock(pid)), 201


@app.get("/api/batches")
@auth(*STAFF)
def batches():
    return jsonify(batch_rows(only_active=not request.args.get("all"),
                              product_id=request.args.get("product_id", type=int)))


@app.post("/api/batches/<int:bid>/discard")
@auth(*STAFF)
@locked
def discard_batch(bid):
    """Write off what is left of a batch (for example expired medicine thrown away)."""
    b = q("SELECT * FROM batches WHERE id=?", (bid,), one=True)
    if not b:
        return jsonify(error="Batch not found."), 404
    if b["qty"] <= 0:
        return jsonify(error="This batch is already empty."), 409
    run("UPDATE batches SET qty=0 WHERE id=?", (bid,))
    run("UPDATE products SET stock=stock-? WHERE id=?", (b["qty"], b["product_id"]))
    return jsonify(ok=True, discarded=b["qty"])


@app.delete("/api/products/<int:pid>")
@auth("admin")
@locked
def del_product(pid):
    run("DELETE FROM products WHERE id=?", (pid,))
    return jsonify(ok=True)


@app.post("/api/products/<int:pid>/sell")
@auth(*STAFF)
@locked
def sell_product(pid):
    d = body()
    p = q("SELECT * FROM products WHERE id=?", (pid,), one=True)
    if not p:
        return jsonify(error="Product not found."), 404
    qty = num(d, "qty", "Quantity", 1, 10_000, integer=True, required=False, default=1)
    cust = None
    if d.get("customer_id"):
        cust = num(d, "customer_id", "Customer", 1, integer=True)
        if not q("SELECT 1 FROM users WHERE id=? AND role='customer'", (cust,), one=True):
            raise ApiError("Customer not found.", 404)
    if usable_stock(pid) < qty:
        return jsonify(error="Not enough usable stock (expired items are not counted)."), 409
    deduct_stock(pid, qty)
    amount = round(p["price"] * qty, 2)
    run("INSERT INTO sales(customer_id,kind,item_name,qty,amount,created_at) VALUES(?,?,?,?,?,?)",
        (cust, "product", p["name"], qty, amount, now()))
    return jsonify(ok=True, amount=amount)


def service_fields(d, cur=None):
    name = text(d, "name", "Service name", 100, required=cur is None, default=cur["name"] if cur else "")
    desc = text(d, "description", "Description", 255, default=cur["description"] if cur else "") if (cur is None or "description" in d) else cur["description"]
    price = round(num(d, "price", "Price", 0, 1_000_000, required=cur is None, default=cur["price"] if cur else None), 2)
    dur = num(d, "duration", "Duration", 5, 480, integer=True, required=False, default=cur["duration"] if cur else 30)
    return name, desc, price, dur


@app.post("/api/services")
@auth("admin")
def add_service():
    d = body()
    name, desc, price, dur = service_fields(d)
    emoji = text(d, "emoji", "Emoji", 8, default="🩺")
    sid = run("INSERT INTO services(name,description,price,duration,emoji) VALUES(?,?,?,?,?)",
              (name, desc, price, dur, emoji))
    return jsonify(id=sid), 201


@app.put("/api/services/<int:sid>")
@auth("admin")
def edit_service(sid):
    d = body()
    s = q("SELECT * FROM services WHERE id=?", (sid,), one=True)
    if not s:
        return jsonify(error="Service not found."), 404
    name, desc, price, dur = service_fields(d, s)
    run("UPDATE services SET name=?,description=?,price=?,duration=? WHERE id=?", (name, desc, price, dur, sid))
    return jsonify(ok=True)


def vet_fields(d, cur=None):
    name = text(d, "name", "Vet name", 100, required=cur is None, default=cur["name"] if cur else "")
    spec = text(d, "specialty", "Specialty", 100, default=cur["specialty"] if cur else "") if (cur is None or "specialty" in d) else cur["specialty"]
    days = work_days_ok(d.get("work_days", cur["work_days"] if cur else "0,1,2,3,4"))
    st = text(d, "start_time", "Start time", 5, default=cur["start_time"] if cur else "09:00")
    en = text(d, "end_time", "End time", 5, default=cur["end_time"] if cur else "17:00")
    if not (valid_hhmm(st) and valid_hhmm(en)):
        raise ApiError("Times must look like 09:00.")
    if en <= st:
        raise ApiError("End time must be later than start time.")
    return name, spec, days, st, en


@app.post("/api/vets")
@auth("admin")
def add_vet():
    d = body()
    name, spec, days, st, en = vet_fields(d)
    vid = run("INSERT INTO vets(name,specialty,work_days,start_time,end_time) VALUES(?,?,?,?,?)", (name, spec, days, st, en))
    return jsonify(id=vid), 201


@app.put("/api/vets/<int:vid>")
@auth("admin")
def edit_vet(vid):
    d = body()
    v = q("SELECT * FROM vets WHERE id=?", (vid,), one=True)
    if not v:
        return jsonify(error="Vet not found."), 404
    name, spec, days, st, en = vet_fields(d, v)
    active = num(d, "active", "Active", 0, 1, integer=True, required=False, default=v["active"])
    run("UPDATE vets SET name=?,specialty=?,work_days=?,start_time=?,end_time=?,active=? WHERE id=?",
        (name, spec, days, st, en, active, vid))
    return jsonify(ok=True)


# sales + dashboard

@app.get("/api/sales")
@auth(*STAFF)
def sales():
    days = num(request.args, "days", "Days", 1, 3650, integer=True, required=False, default=30)
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rs = q("""SELECT s.*, u.full_name AS customer_name FROM sales s
              LEFT JOIN users u ON u.id=s.customer_id
              WHERE s.created_at >= ? ORDER BY s.created_at DESC""", (since,))
    return jsonify(rows(rs))


@app.get("/api/dashboard")
@auth(*STAFF)
def dashboard():
    today = date.today().strftime("%Y-%m-%d")
    since = (date.today() - timedelta(days=6)).strftime("%Y-%m-%d")
    appts_today = q("SELECT COUNT(*) c FROM appointments WHERE appt_date=? AND status!='cancelled'", (today,), one=True)["c"]
    pending = q("SELECT COUNT(*) c FROM appointments WHERE status='pending'", one=True)["c"]
    sales_today = q("SELECT COALESCE(SUM(amount),0) s FROM sales WHERE substr(created_at,1,10)=?", (today,), one=True)["s"]
    sales_30 = q("SELECT COALESCE(SUM(amount),0) s FROM sales WHERE created_at >= ?",
                 ((date.today() - timedelta(days=30)).strftime("%Y-%m-%d"),), one=True)["s"]
    customers_n = q("SELECT COUNT(*) c FROM users WHERE role='customer'", one=True)["c"]
    info = batch_info()
    views = [product_view(p, info) for p in q("SELECT * FROM products")]
    low = sorted([{"id": v["id"], "name": v["name"], "stock": v["stock"], "reorder_level": v["reorder_level"]}
                  for v in views if v["stock"] <= v["reorder_level"]], key=lambda x: x["stock"])
    expiring = [b for b in batch_rows() if b["status"] in ("expired", "expiring")]
    pending_list = rows(q(APPT_SQL + " WHERE a.status='pending' ORDER BY a.appt_date, a.appt_time LIMIT 30"))
    by_status = rows(q("SELECT status, COUNT(*) c FROM appointments GROUP BY status"))
    daily = {r["d"]: r["s"] for r in q(
        "SELECT substr(created_at,1,10) d, SUM(amount) s FROM sales WHERE substr(created_at,1,10)>=? GROUP BY d", (since,))}
    series = []
    for i in range(7):
        dd = (date.today() - timedelta(days=6 - i)).strftime("%Y-%m-%d")
        series.append({"date": dd, "amount": daily.get(dd, 0)})
    top = rows(q("""SELECT item_name, CAST(SUM(qty) AS SIGNED) qty, SUM(amount) amount FROM sales
                    GROUP BY item_name ORDER BY amount DESC LIMIT 5"""))
    return jsonify(appointments_today=appts_today, pending=pending, sales_today=sales_today, sales_30=sales_30,
                   customers=customers_n, low_stock=low, by_status=by_status, sales_series=series, top_items=top,
                   expiring=expiring, expired_count=sum(1 for b in expiring if b['status'] == 'expired'),
                   pending_list=pending_list)


# notifications

@app.get("/api/notifications")
@auth()
def notifs():
    return jsonify(rows(q("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 50", (g.user["id"],))))


@app.post("/api/notifications/read")
@auth()
def notifs_read():
    run("UPDATE notifications SET is_read=1 WHERE user_id=?", (g.user["id"],))
    return jsonify(ok=True)


# misc

@app.after_request
def cors(r):
    r.headers["Access-Control-Allow-Origin"] = "*"           # tokens travel in a header, not a cookie
    r.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
    r.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    r.headers["X-Content-Type-Options"] = "nosniff"
    if request.path.startswith("/api/"):
        r.headers["Cache-Control"] = "no-store"
    return r


@app.get("/api/health")
def health():
    return jsonify(ok=True, app="PawPet", time=now())


def check_database():
    """Run once when the server starts. READ-ONLY for the schema: it never creates or alters tables.
    If the database is not ready it says exactly what to do and stops."""
    try:
        c = dbmod.connect_checked()
    except dbmod.SetupNeeded as e:
        if dbmod.ENGINE == "sqlite":                       # test mode only: a throw-away SQLite file sets itself up
            import setup_database
            setup_database.run()
            c = dbmod.connect_checked()
        else:
            print("\n  %s\n  Run the one-time setup first:   py setup_database.py   (or double-click setup_database.bat)\n" % e)
            raise SystemExit(1)
    except Exception as e:
        print("\n  Cannot open the database: %s\n  Is MySQL started in XAMPP? Is PAWPET_DB_PASSWORD right?\n" % e)
        raise SystemExit(1)
    flag_default_passwords(c)
    c.close()
    if dbmod.ENGINE != "sqlite" and dbmod.MYSQL_CFG["user"] == "root" and not dbmod.MYSQL_CFG["password"]:
        print("\n  WARNING: the server connects to MySQL as 'root' with NO password.\n"
              "  Before real use, run database\\secure_mysql.sql and set PAWPET_DB_USER / PAWPET_DB_PASSWORD.\n")


def lan_addresses():
    """IPv4 addresses of this laptop (what the other devices must type). Best effort; never raises."""
    found = set()
    try:
        import socket
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.add(info[4][0])
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("10.255.255.255", 1))             # no packet is sent; just asks the OS which address it would use
            found.add(s.getsockname()[0])
        finally:
            s.close()
    except Exception:
        pass
    return sorted(a for a in found if not a.startswith("127."))


def print_banner(port, scheme="http"):
    print("=" * 66)
    print(" PawPet server is running.  On the OTHER devices use ONE of:")
    for a in lan_addresses() or ["(run ipconfig to find this laptop's IPv4 address)"]:
        print("     %s://%s:%d" % (scheme, a, port))
    print(" On THIS laptop:  %s://localhost:%d" % (scheme, port))
    print(" If another device cannot connect: run open_firewall.bat as Administrator.")
    print("=" * 66, flush=True)


if __name__ == "__main__":
    host, port = "0.0.0.0", int(os.environ.get("PAWPET_PORT", "5000"))
    check_database()
    cert, key = os.environ.get("PAWPET_SSL_CERT"), os.environ.get("PAWPET_SSL_KEY")
    print_banner(port, "https" if (cert and key) else "http")
    if cert and key:                                           # optional HTTPS (see PAWPET_GUIDE.md)
        app.run(host=host, port=port, debug=False, threaded=True, ssl_context=(cert, key))
    elif os.environ.get("PAWPET_WAITRESS") == "1":             # optional production server: py -m pip install waitress
        from waitress import serve
        print(f"PawPet server (waitress) on http://{host}:{port}")
        serve(app, host=host, port=port, threads=8)
    else:
        app.run(host=host, port=port, debug=False, threaded=True)
