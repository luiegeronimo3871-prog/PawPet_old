"""Regression tests for every problem found in the pre-launch audit.

Run:  py audit_regression_test.py
It copies the server to a temp folder, starts it on port 5071 with a throw-away SQLite database
(real first-run mode: random passwords), runs the checks, then stops it. MySQL is NOT needed.
"""
import datetime as dt
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "LAPTOP2_Server")
PORT = 5071
B = f"http://127.0.0.1:{PORT}/api"
tmp = tempfile.mkdtemp(prefix="pawpet_audit_")
srv_dir = os.path.join(tmp, "server")
shutil.copytree(SRC, srv_dir, ignore=shutil.ignore_patterns("__pycache__", "*.db", "FIRST_RUN_PASSWORDS.txt"))
DB = os.path.join(tmp, "t.db")
env = dict(os.environ, PAWPET_DB="sqlite", PAWPET_SQLITE_PATH=DB, PAWPET_PORT=str(PORT))
env.pop("PAWPET_TEST_FIXED_PASSWORDS", None)
proc = subprocess.Popen([sys.executable, "app.py"], cwd=srv_dir, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
for _ in range(60):
    try:
        requests.get(B + "/health", timeout=1)
        break
    except Exception:
        time.sleep(0.25)

fails = 0
total = 0


def check(name, cond, extra=""):
    global fails, total
    total += 1
    if not cond:
        fails += 1
    print(("PASS " if cond else "FAIL ") + name + ((" -> " + str(extra)[:150]) if (extra and not cond) else ""))


def call(method, path, body=None, tok=None, raw=None):
    h = {"Authorization": "Bearer " + tok} if tok else {}
    if raw is not None:
        h["Content-Type"] = "application/json"
        r = requests.request(method, B + path, data=raw, headers=h, timeout=30)
    else:
        r = requests.request(method, B + path, json=body, headers=h, timeout=30)
    try:
        j = r.json()
    except Exception:
        j = None
    return r.status_code, j


def is_json_error(code, j, want):
    return code == want and isinstance(j, dict) and "error" in j


try:
    pw = {}
    for line in open(os.path.join(srv_dir, "FIRST_RUN_PASSWORDS.txt"), encoding="utf-8"):
        m = re.match(r"^(admin|staff|customer)\s+(\w+)\s+(\S+)$", line.strip())
        if m:
            pw[m.group(2)] = m.group(3)
    check("first run wrote random passwords for 4 sample accounts", len(pw) == 4 and "admin123" not in pw.values())

    print("== default passwords")
    for u, p in (("admin", "admin123"), ("staff", "staff123"), ("megan", "pass123")):
        c, j = call("POST", "/login", {"username": u, "password": p})
        check(f"{u}/{p} no longer works", c == 401, (c, j))

    print("== forced password change")
    c, j = call("POST", "/login", {"username": "admin", "password": pw["admin"], "portal": "admin"})
    check("admin logs in with the random password", c == 200 and j["user"]["must_change"] is True, (c, j))
    A0 = j["token"]
    c, j = call("GET", "/customers", tok=A0)
    check("admin blocked from everything until password is changed", c == 403 and j.get("must_change") is True, (c, j))
    c, j = call("POST", "/change-password", {"old_password": pw["admin"], "new_password": "short"}, A0)
    check("weak new password rejected", c == 400, (c, j))
    c, j = call("POST", "/change-password", {"old_password": pw["admin"], "new_password": "admin123"}, A0)
    check("default password rejected as new password", c == 400, (c, j))
    c, j = call("POST", "/change-password", {"old_password": "wrongwrong1", "new_password": "Clinic2026Pass"}, A0)
    check("wrong old password rejected", c == 403, (c, j))
    c, j = call("POST", "/change-password", {"old_password": pw["admin"], "new_password": "Clinic2026Pass"}, A0)
    check("password changed", c == 200, (c, j))
    c, j = call("POST", "/login", {"username": "admin", "password": pw["admin"]})
    check("old password stops working", c == 401)
    c, j = call("POST", "/login", {"username": "admin", "password": "Clinic2026Pass", "portal": "admin"})
    check("new password works, no longer forced", c == 200 and j["user"]["must_change"] is False, (c, j))
    A = j["token"]
    c, j = call("POST", "/login", {"username": "staff", "password": pw["staff"], "portal": "admin"})
    S0 = j["token"]
    call("POST", "/change-password", {"old_password": pw["staff"], "new_password": "StaffDesk2026"}, S0)
    c, j = call("POST", "/login", {"username": "staff", "password": "StaffDesk2026", "portal": "admin"})
    S = j["token"]
    c, j = call("POST", "/login", {"username": "megan", "password": pw["megan"]})
    check("customer sample account logs in with random password", c == 200 and j["user"]["must_change"] is False, (c, j))
    M = j["token"]
    c, j = call("POST", "/login", {"username": "lester", "password": pw["lester"]})
    L = j["token"]

    print("== password storage / legacy accounts")
    con = sqlite3.connect(DB)
    h = con.execute("select password from users where username='admin'").fetchone()[0]
    check("password stored as salted PBKDF2", h.startswith("pbkdf2$200000$") and len(h.split("$")[2]) == 32, h[:30])
    hs = [r[0] for r in con.execute("select password from users")]
    check("every user has a different salt", len({x.split("$")[2] for x in hs}) == len(hs))
    import hashlib
    legacy = hashlib.sha256(b"pawpet$pass123").hexdigest()
    con.execute("insert into users(username,password,full_name,role,created_at) values('olduser',?,'Old User','customer','2026-01-01 00:00:00')", (legacy,))
    con.commit()
    c, j = call("POST", "/login", {"username": "olduser", "password": "pass123"})
    check("old SHA-256 account can still sign in once", c == 200 and j["user"]["must_change"] is True, (c, j))
    check("...and its hash was upgraded to PBKDF2", con.execute("select password from users where username='olduser'").fetchone()[0].startswith("pbkdf2$"))
    c, j = call("GET", "/pets", tok=j["token"])
    check("...but it must change the default password first", c == 403 and j.get("must_change"), (c, j))

    print("== brute force / token expiry")
    codes = [call("POST", "/login", {"username": "lester", "password": "bad%d" % i})[0] for i in range(7)]
    check("lockout after 5 wrong passwords (429)", codes[:5] == [401] * 5 and codes[5] == 429 and codes[6] == 429, codes)
    c, j = call("POST", "/login", {"username": "lester", "password": pw["lester"]})
    check("even the right password is refused while locked", c == 429, (c, j))
    old = (dt.datetime.now() - dt.timedelta(days=45)).strftime("%Y-%m-%d %H:%M:%S")
    con.execute("update tokens set created_at=? where token=?", (old, L))
    con.commit()
    c, j = call("GET", "/pets", tok=L)
    check("a 45-day-old token is rejected (tokens expire after 30 days)", c == 401, (c, j))

    print("== malformed input returns JSON 400 (never a 500)")
    d3 = (dt.date.today() + dt.timedelta(days=3))
    while d3.weekday() > 3:
        d3 += dt.timedelta(days=1)
    D = d3.isoformat()
    p_id = call("GET", "/pets", tok=M)[1][0]["id"]
    good = {"pet_id": p_id, "service_id": 1, "vet_id": 1, "appt_date": D, "appt_time": "09:00"}
    cases = [
        ("login body is a list", lambda: call("POST", "/login", raw="[1,2]")),
        ("login invalid JSON", lambda: call("POST", "/login", raw="{bad")),
        ("register body is a list", lambda: call("POST", "/register", raw="[]")),
        ("register password is a number", lambda: call("POST", "/register", {"username": "abc1", "password": 12345678, "full_name": "x"})),
        ("register 500-char username", lambda: call("POST", "/register", {"username": "a" * 500, "password": "Secret123", "full_name": "x"})),
        ("register invalid email", lambda: call("POST", "/register", {"username": "abc2", "password": "Secret123", "full_name": "x", "email": "nope"})),
        ("register letters in phone", lambda: call("POST", "/register", {"username": "abc3", "password": "Secret123", "full_name": "x", "phone": "abc"})),
        ("register short password", lambda: call("POST", "/register", {"username": "abc4", "password": "abc123", "full_name": "x"})),
        ("booking bad date", lambda: call("POST", "/appointments", {**good, "appt_date": "abc"}, M)),
        ("booking bad time", lambda: call("POST", "/appointments", {**good, "appt_time": "xx"}, M)),
        ("booking pet_id is a list", lambda: call("POST", "/appointments", {**good, "pet_id": [1]}, M)),
        ("booking notes 100k chars (too big)", lambda: call("POST", "/appointments", {**good, "notes": "x" * 100000}, M)),
        ("booking notes 600 chars", lambda: call("POST", "/appointments", {**good, "notes": "x" * 600}, M)),
        ("booking in the past", lambda: call("POST", "/appointments", {**good, "appt_date": "2020-01-06"}, M)),
        ("booking in 2099", lambda: call("POST", "/appointments", {**good, "appt_date": "2099-01-05"}, M)),
        ("availability bad date", lambda: call("GET", "/availability?vet_id=1&date=abc")),
        ("availability vet_id=abc", lambda: call("GET", "/availability?vet_id=abc&date=" + D)),
        ("sell qty='abc'", lambda: call("POST", "/products/1/sell", {"qty": "abc"}, S)),
        ("sell qty=-5", lambda: call("POST", "/products/1/sell", {"qty": -5}, S)),
        ("sell qty=0.5", lambda: call("POST", "/products/1/sell", {"qty": 0.5}, S)),
        ("product price NaN", lambda: call("POST", "/products", {"name": "n", "price": "nan", "stock": 1}, S)),
        ("product price infinity", lambda: call("POST", "/products", {"name": "n", "price": "1e999", "stock": 1}, S)),
        ("product name 5000 chars", lambda: call("POST", "/products", {"name": "n" * 5000, "price": 1, "stock": 1}, S)),
        ("product reorder_level='x'", lambda: call("POST", "/products", {"name": "n", "price": 1, "stock": 1, "reorder_level": "x"}, S)),
        ("service duration 0", lambda: call("POST", "/services", {"name": "s", "price": 1, "duration": 0}, A)),
        ("service negative price", lambda: call("POST", "/services", {"name": "s", "price": -100, "duration": 30}, A)),
        ("vet start_time 'zz'", lambda: call("POST", "/vets", {"name": "v", "start_time": "zz", "end_time": "10:00"}, A)),
        ("vet end before start", lambda: call("POST", "/vets", {"name": "v", "start_time": "17:00", "end_time": "09:00"}, A)),
        ("vet work_days 'x'", lambda: call("POST", "/vets", {"name": "v2", "work_days": "x"}, A)),
        ("sales days=abc", lambda: call("GET", "/sales?days=abc", tok=S)),
        ("followup bad date", lambda: call("POST", "/appointments/1/followup", {"appt_date": "zz", "appt_time": "10:00"}, S)),
        ("complete with qty 'x'", lambda: call("POST", "/appointments/1/complete", {"products": [{"product_id": 1, "qty": "x"}]}, S)),
        ("complete with products not a list", lambda: call("POST", "/appointments/1/complete", {"products": "abc"}, S)),
        ("pet age -5", lambda: call("POST", "/pets", {"name": "x", "species": "Dog", "age": -5}, M)),
        ("appointment filter bad date", lambda: call("GET", "/appointments?date=zz", tok=S)),
        ("appointment filter bad status", lambda: call("GET", "/appointments?status=zz", tok=S)),
        ("body larger than 64 KB", lambda: call("POST", "/pets", {"name": "x", "species": "Dog", "notes": "x" * 70000}, M)),
    ]
    for name, fn in cases:
        c, j = fn()
        check("bad input handled: " + name, c in (400, 413, 404, 409) and isinstance(j, dict) and "error" in j, (c, j))
    c, j = call("POST", "/pets", {"name": "Okay", "species": "Dog", "age": "3", "weight": "10.5"}, M)
    check("valid input still accepted (pet with numeric strings)", c == 201, (c, j))

    print("== permissions (customer token)")
    for name, c in [("GET /customers", call("GET", "/customers", tok=M)[0]), ("GET /sales", call("GET", "/sales", tok=M)[0]),
                    ("GET /dashboard", call("GET", "/dashboard", tok=M)[0]), ("GET /batches", call("GET", "/batches", tok=M)[0]),
                    ("POST /reminders/send", call("POST", "/reminders/send", {}, M)[0]),
                    ("POST /products", call("POST", "/products", {"name": "x", "price": 1}, M)[0]),
                    ("POST /products/1/sell", call("POST", "/products/1/sell", {"qty": 1}, M)[0]),
                    ("POST /customers/3/toggle", call("POST", "/customers/3/toggle", {}, M)[0]),
                    ("DELETE /products/1", call("DELETE", "/products/1", tok=M)[0]),
                    ("PUT /vets/1", call("PUT", "/vets/1", {"active": 0}, M)[0]),
                    ("POST /users/4/reset-password", call("POST", "/users/4/reset-password", {}, M)[0])]:
        check("customer blocked: " + name, c == 403, c)
    check("staff cannot use admin-only (add service)", call("POST", "/services", {"name": "s", "price": 1}, S)[0] == 403)
    check("customer cannot cancel someone else's appointment", call("POST", "/appointments/3/cancel", {}, M)[0] == 404)
    check("customer cannot book with someone else's pet", call("POST", "/appointments", {**good, "pet_id": 3}, M)[0] == 404)
    pets_m = [p["name"] for p in call("GET", "/pets?all=1", tok=M)[1]]
    check("customer ?all=1 still sees only own pets", "Brock" not in pets_m, pets_m)
    pr = call("GET", "/products")[1][0]
    check("public product list hides internal stock fields", "physical_stock" not in pr and "expired_qty" not in pr, pr)
    pr = call("GET", "/products", tok=S)[1][0]
    check("staff product list still has expiry fields", "expired_qty" in pr and "physical_stock" in pr, pr)

    print("== staff can reset passwords")
    c, j = call("POST", "/users/4/reset-password", {}, S)
    check("staff resets a customer password -> temp password", c == 200 and len(j["temp_password"]) >= 8, (c, j))
    tmp_pw = j["temp_password"]
    check("temp password is not a default one", tmp_pw not in ("admin123", "staff123", "pass123"))
    c, j = call("POST", "/users/1/reset-password", {}, S)
    check("staff cannot reset an admin", c == 403, (c, j))
    c, j = call("POST", "/customers", {"username": "walkin1", "full_name": "Walk In"}, S)
    check("staff-created customer gets a random temp password (not pass123)", c == 201 and j.get("temp_password") and j["temp_password"] != "pass123", (c, j))
    c, j2 = call("POST", "/login", {"username": "walkin1", "password": j["temp_password"]})
    check("...and must change it at first login", c == 200 and j2["user"]["must_change"], (c, j2))

    print("== double booking race: 10 rounds x 20 customers on the same slot")
    toks, pets = [], []
    for i in range(20):
        u = f"racer{i}"
        c, j = call("POST", "/customers", {"username": u, "full_name": u, "password": "Racer2026x"}, S)
        c, j = call("POST", "/login", {"username": u, "password": "Racer2026x"})
        t = j["token"]
        call("POST", "/change-password", {"old_password": "Racer2026x", "new_password": "Racer2026y"}, t)
        t = call("POST", "/login", {"username": u, "password": "Racer2026y"})[1]["token"]
        toks.append(t)
        pets.append(call("POST", "/pets", {"name": "p" + u, "species": "Dog"}, t)[1]["id"])
    d = dt.date.today() + dt.timedelta(days=9)
    while d.weekday() != 2:
        d += dt.timedelta(days=1)
    doubles, never_booked = 0, 0
    for tm in ["09:00", "09:30", "10:00", "10:30", "11:00", "11:30", "12:00", "12:30", "13:00", "13:30"]:
        res, bar = [], threading.Barrier(20)

        def go(i, tm=tm):
            bar.wait()
            res.append(call("POST", "/appointments", {"pet_id": pets[i], "service_id": 1, "vet_id": 1, "appt_date": d.isoformat(), "appt_time": tm}, toks[i])[0])
        th = [threading.Thread(target=go, args=(i,)) for i in range(20)]
        [x.start() for x in th]
        [x.join() for x in th]
        doubles += res.count(201) > 1
        never_booked += res.count(201) == 0
    check("no slot was ever booked twice (0 of 10 rounds)", doubles == 0, f"{doubles} rounds double-booked")
    check("exactly one customer got each slot", never_booked == 0)
    rows_ = call("GET", f"/appointments?date={d.isoformat()}&vet_id=1", tok=S)[1]
    times = [a["appt_time"] for a in rows_ if a["status"] != "cancelled"]
    check("database holds one appointment per slot", len(times) == len(set(times)) == 10, times)
    c, j = call("POST", "/appointments", {"pet_id": pets[0], "service_id": 4, "vet_id": 1, "appt_date": d.isoformat(), "appt_time": "13:30"}, toks[0])
    check("a 60-minute service cannot overlap an existing booking", c == 409, (c, j))

    print("== stock race: 10 parallel sales of 3 with 15 in stock")
    cid = next(p["id"] for p in call("GET", "/products", tok=S)[1] if p["name"] == "Cat Litter 10L")
    res, bar = [], threading.Barrier(10)

    def sell():
        bar.wait()
        res.append(call("POST", f"/products/{cid}/sell", {"qty": 3}, S)[0])
    th = [threading.Thread(target=sell) for _ in range(10)]
    [x.start() for x in th]
    [x.join() for x in th]
    check("exactly 5 sales succeed (15 / 3)", res.count(200) == 5 and res.count(409) == 5, sorted(res))
    con2 = sqlite3.connect(DB)
    check("stock in database is 0, never negative", con2.execute("select stock from products where id=?", (cid,)).fetchone()[0] == 0)
    check("batch quantities add up to the stock", con2.execute("select coalesce(sum(qty),0) from batches where product_id=?", (cid,)).fetchone()[0] == 0)
    check("no negative stock anywhere", con2.execute("select count(*) from products where stock<0").fetchone()[0] == 0)
    c, j = call("POST", "/products/5/sell", {"qty": 1}, S)
    check("expired stock still cannot be sold", c == 409, (c, j))

    print("== appointment workflow")
    nxt = dt.date.today() + dt.timedelta(days=2)
    while nxt.weekday() > 3:
        nxt += dt.timedelta(days=1)
    aid = call("POST", "/appointments", {**good, "appt_date": nxt.isoformat(), "appt_time": "15:00"}, M)[1]["id"]
    c, j = call("POST", f"/appointments/{aid}/status", {"status": "completed"}, S)
    check("cannot mark completed through /status (sale would be skipped)", c == 400, (c, j))
    c, j = call("POST", f"/appointments/{aid}/complete", {"products": [{"product_id": 9, "qty": 5}]}, S)
    check("complete with too little stock -> 409 'Nothing was saved'", c == 409 and "Nothing was saved" in j["error"], (c, j))
    st = [a for a in call("GET", "/appointments", tok=S)[1] if a["id"] == aid][0]["status"]
    sales_rows = [s for s in call("GET", "/sales", tok=S)[1] if s.get("appointment_id") == aid]
    check("appointment is still pending and no sale was written (atomic)", st == "pending" and not sales_rows, (st, sales_rows))
    c, j = call("POST", f"/appointments/{aid}/complete", {"products": [{"product_id": 1, "qty": 1}, {"product_id": 1, "qty": 1}]}, S)
    check("complete with enough stock works (duplicate lines merged)", c == 200 and j["total"] == 350 + 1250 * 2, (c, j))
    c, j = call("POST", f"/appointments/{aid}/status", {"status": "pending"}, S)
    check("a completed visit cannot be reopened", c == 409, (c, j))
    c, j = call("POST", f"/appointments/{aid}/complete", {}, S)
    check("cannot complete twice", c == 409, (c, j))
    c, j = call("POST", f"/appointments/{aid}/followup", {"appt_date": "2020-01-01", "appt_time": "10:00"}, S)
    check("follow-up in the past rejected", c == 400, (c, j))
    a2 = call("POST", "/appointments", {**good, "appt_date": nxt.isoformat(), "appt_time": "16:00"}, M)[1]["id"]
    c, j = call("POST", f"/appointments/{a2}/followup", {"appt_date": nxt.isoformat(), "appt_time": "10:00"}, S)
    check("follow-up needs a completed visit", c == 409, (c, j))
    c, j = call("POST", f"/appointments/{a2}/status", {"status": "no_show"}, S)
    check("pending -> no_show allowed", c == 200, (c, j))
    c, j = call("POST", f"/appointments/{a2}/cancel", {}, M)
    check("no_show cannot be cancelled again", c == 409, (c, j))
    c, j = call("DELETE", f"/pets/{p_id}", tok=M)
    check("pet with visit history cannot be deleted (would break the database link)", c == 409, (c, j))

    print("== reminders")
    call("POST", "/appointments", {**good, "appt_date": dt.date.today().isoformat(), "appt_time": "23:30"}, M)
    a_ = call("POST", "/reminders/send", {}, S)[1]
    b_ = call("POST", "/reminders/send", {}, S)[1]
    check("second reminder run sends nothing new (no duplicates)", b_["sent"] == 0, (a_, b_))

    print("== customer cap and vets")
    c, j = call("POST", "/vets", {"name": "Dr Test", "work_days": "0,1", "start_time": "08:00", "end_time": "12:00"}, A)
    check("valid vet accepted", c == 201, (c, j))
    c, j = call("PUT", "/vets/4", {"start_time": "13:00"}, A)
    check("vet edit that makes end < start rejected", c == 400, (c, j))
    c, j = call("GET", "/vets")
    check("public vet list is clean", c == 200 and all(re.fullmatch(r"\d\d:\d\d", v["start_time"]) for v in j))

    print("== registration limits")
    codes = [call("POST", "/register", {"username": f"spam{i}", "password": "Spam2026x", "full_name": "s"})[0] for i in range(25)]
    check("sign-ups are rate limited per device (429 after 20)", 429 in codes and codes.count(201) <= 20, codes)

    print("== server tidy")
    log = proc.poll()
    check("server is still running after all of the above", log is None, log)
finally:
    proc.terminate()
    try:
        proc.wait(5)
    except Exception:
        proc.kill()
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{total - fails} passed, {fails} failed, {total} total")
sys.exit(1 if fails else 0)
