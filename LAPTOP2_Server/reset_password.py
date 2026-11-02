"""PawPet - change the password (and optionally the username) of ANY account.
Use it when you lost the admin password or want a different admin username.
Run on the SERVER laptop with MySQL started:   py reset_password.py
It does not delete any data."""
import getpass
import sys

import app as server


def main():
    user = input("Account to change (current username, example: admin): ").strip()
    c = server.dbmod.Conn()
    rows = c.query("SELECT id, role FROM users WHERE username=?", (user,))
    if not rows:
        print("No such user. Existing users:", ", ".join(r["username"] for r in c.query("SELECT username FROM users")))
        return 1
    uid = rows[0]["id"]
    new_name = user
    while True:
        wanted = input("New username (just press Enter to keep '%s'): " % user).strip()
        if not wanted or wanted == user:
            break
        if not server.USER_RE.match(wanted):
            print("  -> Username must be 3-50 letters, numbers, dot, dash or underscore.")
            continue
        if c.query("SELECT 1 AS x FROM users WHERE username=? AND id<>?", (wanted, uid)):
            print("  -> That username is already taken.")
            continue
        new_name = wanted
        break
    while True:
        pw = getpass.getpass("New password (8+ characters, letters AND numbers; typing is hidden): ")
        try:
            server.password_rules(pw, new_name)
        except server.ApiError as e:
            print("  ->", e)
            if "letter and one number" in str(e) and len(pw) >= 8:       # only this one rule can be overridden, by you, here
                if input("  This password is weaker than the recommended rule (no number). Use it anyway? Type YES: ").strip() != "YES":
                    continue
            else:
                continue
        if pw != getpass.getpass("Repeat the new password: "):
            print("  -> The two passwords do not match.")
            continue
        break
    c.execute("UPDATE users SET username=?, password=?, must_change=0, active=1 WHERE id=?", (new_name, server.hash_pw(pw), uid))
    c.execute("DELETE FROM tokens WHERE user_id=?", (uid,))              # sign that account out everywhere
    print("Done. Sign in with username '%s' and the new password." % new_name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
