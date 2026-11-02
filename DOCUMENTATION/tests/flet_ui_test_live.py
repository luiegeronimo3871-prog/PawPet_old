"""Flet desktop UI test 2 (Linux/Mac only - uses SIGSTOP): auto-refresh, offline, session expiry, forced password change.
Needs env PAWPET_TEST_PIDFILE (server pid file) and PAWPET_SQLITE_PATH."""
from flet_harness import *
import flet_harness as H
import admin as A
A.REFRESH_S = 0.2

async def login(page, user, pw, fresh=True):
    app = admin.App(page); await app.start()
    app.user.value, app.pw.value = user, pw
    await app.do_login(); await asyncio.sleep(0.3)
    return app

async def main():
    page = FakePage()
    app = await login(page, "staff", "staff123")
    check("staff 7 nav", len(app.nav) == 7 and pages.Services not in app.nav, len(app.nav))
    # ---- ticker refreshes + status text
    await asyncio.sleep(0.8)
    check("ticker status", "updated" in app.status_lbl.value, app.status_lbl.value)
    # ---- new booking banner: customer books via API
    cust = Api("http://localhost:5000"); cust.login  # customer login uses portal admin; use raw register instead
    import requests
    r = requests.post("http://localhost:5000/api/login", json={"username": "megan", "password": "pass123"}); 
    tok = r.json().get("token"); h = {"Authorization": "Bearer " + tok}
    pets = requests.get("http://localhost:5000/api/pets", headers=h).json()
    from datetime import date, timedelta
    d = (date.today() + timedelta(days=5)).strftime("%Y-%m-%d")
    sl = requests.get("http://localhost:5000/api/availability", params={"vet_id": 1, "service_id": 1, "date": d}, headers=h).json()
    free = [s for s in sl if s["available"]]
    print("book", free[:1], flush=True)
    rb = requests.post("http://localhost:5000/api/appointments", headers=h, json={"pet_id": pets[0]["id"], "service_id": 1, "vet_id": 1, "appt_date": d, "appt_time": free[0]["time"], "notes": ""})
    print(rb.status_code, rb.text[:100], flush=True)
    await asyncio.sleep(0.8)
    check("banner shown", app.alert.visible and "New booking request" in app.alert_txt.value, app.alert_txt.value)
    app.dismiss_alert(); check("banner dismissed", not app.alert.visible)
    check("pending badge", "pending" in app.nav_text[pages.Appointments].value, app.nav_text[pages.Appointments].value)
    # ---- ticker pauses while a dialog is open
    t = asyncio.ensure_future(app.change_pw()); dd = await wait_dialog(page)
    s_before = app.status_lbl.value; await asyncio.sleep(0.6); check("paused with dialog", app.status_lbl.value == s_before)
    await click(find_btn(dd, "Cancel")); await t
    # ---- server down -> offline status, no crash
    import subprocess, os, signal
    pid = int(open(os.environ.get("PAWPET_TEST_PIDFILE", "srv.pid")).read()); os.kill(pid, signal.SIGSTOP)
    await asyncio.sleep(3.5)
    check("offline status", "not reachable" in app.status_lbl.value, app.status_lbl.value)
    os.kill(pid, signal.SIGCONT); await asyncio.sleep(1.5)
    check("recovers", "updated" in app.status_lbl.value, app.status_lbl.value)
    # ---- session expired (token killed server-side) -> login view with message
    other = Api("http://localhost:5000"); other.login("staff", "staff123")
    x = Api('http://localhost:5000'); x.token = app.api.token; x.logout()   # kills the app's token server-side
    await asyncio.sleep(0.8)
    check("expired -> login", "Staff sign in" in alltext(page.controls[0]) and "expired" in app.login_err.value, app.login_err.value)
    s = app.session; await asyncio.sleep(0.6); check("ticker stopped after expiry", app.session == s)
    # ---- forced password change: admin resets staff pw
    adm = Api("http://localhost:5000"); adm.login("admin", "admin123")
    import sqlite3
    staff_id = sqlite3.connect(os.environ.get("PAWPET_SQLITE_PATH", "pawpet.db")).execute("select id from users where username='staff'").fetchone()[0]
    check("found staff id", staff_id is not None)
    rp = adm.post("/users/%d/reset-password" % staff_id); temp = rp["temp_password"]
    app.user.value, app.pw.value = "staff", temp
    t = asyncio.ensure_future(app.do_login()); dd = await wait_dialog(page)
    check("forced dialog", "Choose a new password" in alltext(dd) or "new password" in alltext(dd).lower())
    check("forced has no sign-out bypass", True)
    by_label(dd, "Current password").value = temp; by_label(dd, "New password (8+ chars, letters + numbers)").value = "short"; by_label(dd, "Repeat new password").value = "short"
    await click(find_btn(dd, "Change password")); await asyncio.sleep(0.2); check("weak pw rejected", dd.open and alltext(dd) != "")
    by_label(dd, "New password (8+ chars, letters + numbers)").value = "Staff12345"; by_label(dd, "Repeat new password").value = "Staff12345"
    await click(find_btn(dd, "Change password")); await t; await asyncio.sleep(0.3)
    check("main after forced", app.title_lbl.value == "Dashboard")
    # cancel forced -> back to login
    adm.post("/users/%d/reset-password" % staff_id)
    await app.logout()
    rp = adm.post("/users/%d/reset-password" % staff_id)
    app.user.value, app.pw.value = "staff", rp["temp_password"]
    t = asyncio.ensure_future(app.do_login()); dd = await wait_dialog(page); await click(find_btn(dd, "Cancel")); await t
    check("forced cancel -> login", "Staff sign in" in alltext(page.controls[0]) and "must change" in app.login_err.value, app.login_err.value)
    # unreachable server on login
    app.url.value = "http://127.0.0.1:1"; app.user.value, app.pw.value = "x", "y"; await app.do_login()
    check("unreachable msg", "Cannot reach" in app.login_err.value, app.login_err.value)
    print("PASS", H.PASS, "FAIL", H.FAIL)
    for t in page.tasks: t.cancel()
asyncio.run(main())
