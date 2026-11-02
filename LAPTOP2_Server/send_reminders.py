"""Sends today's/tomorrow's appointment reminders through the PawPet server.
Meant to be run by Windows Task Scheduler (see send_reminders.bat). Uses only the standard library."""
import json, os, sys, urllib.request, datetime

BASE = os.environ.get("PAWPET_URL", "http://localhost:5000")
HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "reminders.log")


def credentials():
    """Staff login used for the reminders. Either set PAWPET_STAFF_USER / PAWPET_STAFF_PASS, or put the
    username on line 1 and the password on line 2 of reminders_login.txt (next to this file; keep it private)."""
    u, p = os.environ.get("PAWPET_STAFF_USER"), os.environ.get("PAWPET_STAFF_PASS")
    if u and p:
        return u, p
    path = os.path.join(HERE, "reminders_login.txt")
    if os.path.exists(path):
        lines = [x.strip() for x in open(path, encoding="utf-8").read().splitlines() if x.strip()]
        if len(lines) >= 2:
            return lines[0], lines[1]
    raise RuntimeError("No staff login for reminders. Create reminders_login.txt (line 1 = staff username, line 2 = password).")


def call(path, body=None, token=None):
    req = urllib.request.Request(BASE + path, data=json.dumps(body or {}).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def main():
    try:
        user, password = credentials()
        token = call("/api/login", {"username": user, "password": password, "portal": "admin"})["token"]
        sent = call("/api/reminders/send", token=token)["sent"]
        msg = f"OK - {sent} reminder(s) sent"
        code = 0
    except Exception as e:
        msg, code = f"FAILED - {e}", 1
    line = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(line)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    sys.exit(code)


main()
