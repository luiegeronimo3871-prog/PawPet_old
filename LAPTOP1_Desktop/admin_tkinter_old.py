"""PawPet - Desktop Admin / Staff app (Python + Tkinter).

Run:  pip install -r requirements.txt   ->   python admin.py
Login: use the staff/admin account from LAPTOP2_Server/FIRST_RUN_PASSWORDS.txt (server must be running)
"""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime, timedelta

from api_client import Api, ApiError

# ---------------------------------------------------------------- theme
BG, PANEL, PANEL2, LINE = "#0f1a15", "#16241d", "#1b2d24", "#27402f"
TEXT, MUTED = "#e8f3ec", "#8fa89a"
GREEN, GREEN_D, AMBER, RED, BLUE = "#2fb36d", "#1f8a52", "#f0a94b", "#e5645a", "#4aa8d8"
FONT = ("Segoe UI", 10)
REFRESH_MS = 8000          # auto-refresh interval
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def peso(n):
    return "PHP {:,.2f}".format(float(n or 0))


def t12(t):
    h, m = [int(x) for x in t.split(":")]
    return "%d:%02d %s" % ((h + 11) % 12 + 1, m, "PM" if h >= 12 else "AM")


def today():
    return date.today().strftime("%Y-%m-%d")


def valid_date(s):
    try:
        y, m, d = [int(x) for x in s.split("-")]
        date(y, m, d)
        return True
    except Exception:
        return False


def days_until(s):
    """Days from today until an ISO date (negative = already past). None if blank."""
    if not s:
        return None
    try:
        y, m, d = [int(x) for x in s.split("-")]
        return (date(y, m, d) - date.today()).days
    except Exception:
        return None


def restore(tree, sel):
    """Keep the selected row after a refresh."""
    keep = [i for i in sel if tree.exists(i)]
    if keep:
        tree.selection_set(keep)


def setup_style(root):
    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure(".", background=BG, foreground=TEXT, font=FONT, fieldbackground=PANEL2)
    s.configure("TFrame", background=BG)
    s.configure("Panel.TFrame", background=PANEL)
    s.configure("TLabel", background=BG, foreground=TEXT)
    s.configure("Panel.TLabel", background=PANEL)
    s.configure("Muted.TLabel", background=BG, foreground=MUTED)
    s.configure("PMuted.TLabel", background=PANEL, foreground=MUTED)
    s.configure("H1.TLabel", font=("Segoe UI", 20, "bold"))
    s.configure("Big.TLabel", background=PANEL, font=("Segoe UI", 22, "bold"))
    s.configure("H2.TLabel", background=PANEL, font=("Segoe UI", 12, "bold"))
    s.configure("TButton", background=PANEL2, foreground=TEXT, bordercolor=LINE, padding=(12, 7), borderwidth=1)
    s.map("TButton", background=[("active", LINE)])
    s.configure("Accent.TButton", background=GREEN, foreground="#06210f", font=("Segoe UI", 10, "bold"), borderwidth=0)
    s.map("Accent.TButton", background=[("active", "#3cc57d")])
    s.configure("Danger.TButton", background=RED, foreground="#2b0907", borderwidth=0)
    s.configure("Nav.TButton", background="#0b140f", foreground=MUTED, anchor="w", padding=(16, 11), borderwidth=0)
    s.map("Nav.TButton", background=[("active", PANEL)], foreground=[("active", TEXT)])
    s.configure("NavOn.TButton", background=GREEN_D, foreground="#ffffff", anchor="w", padding=(16, 11), borderwidth=0)
    s.configure("TEntry", fieldbackground=PANEL2, foreground=TEXT, bordercolor=LINE, insertcolor=TEXT, padding=6)
    s.configure("TCombobox", fieldbackground=PANEL2, foreground=TEXT, bordercolor=LINE, arrowcolor=TEXT, padding=5)
    s.map("TCombobox", fieldbackground=[("readonly", PANEL2)], foreground=[("readonly", TEXT)])
    root.option_add("*TCombobox*Listbox.background", PANEL2)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    s.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT, rowheight=30,
                bordercolor=LINE, borderwidth=0)
    s.configure("Treeview.Heading", background=PANEL2, foreground=MUTED, font=("Segoe UI", 9, "bold"), padding=6)
    s.map("Treeview", background=[("selected", GREEN_D)], foreground=[("selected", "#ffffff")])
    s.configure("TCheckbutton", background=PANEL, foreground=TEXT)


def make_tree(parent, cols, widths, height=12):
    """cols: list of (id, heading)."""
    wrap = ttk.Frame(parent, style="Panel.TFrame")
    tree = ttk.Treeview(wrap, columns=[c[0] for c in cols], show="headings", height=height, selectmode="browse")
    for (cid, head), w in zip(cols, widths):
        tree.heading(cid, text=head)
        tree.column(cid, width=w, anchor="w")
    sb = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    tree.tag_configure("pending", foreground=AMBER)
    tree.tag_configure("confirmed", foreground=BLUE)
    tree.tag_configure("completed", foreground=GREEN)
    tree.tag_configure("cancelled", foreground=RED)
    tree.tag_configure("no_show", foreground=RED)
    tree.tag_configure("low", foreground=AMBER)
    tree.tag_configure("out", foreground=RED)
    return wrap, tree


def selected_id(tree):
    sel = tree.selection()
    return int(sel[0]) if sel else None


class FormDialog(tk.Toplevel):
    """Generic modal form. fields: list of (key, label, kind, default, options)
    kind: 'entry' | 'combo' | 'check' | 'text' | 'password'"""

    def __init__(self, parent, title, fields, on_save, save_text="Save"):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=PANEL, padx=22, pady=18)
        self.resizable(False, False)
        self.transient(parent)
        self.vars = {}
        self.on_save = on_save
        ttk.Label(self, text=title, style="H2.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        r = 1
        for key, label, kind, default, opts in fields:
            ttk.Label(self, text=label, style="PMuted.TLabel").grid(row=r, column=0, sticky="w", pady=5, padx=(0, 14))
            if kind == "combo":
                v = tk.StringVar(value=default)
                w = ttk.Combobox(self, textvariable=v, values=opts, state="readonly", width=34)
            elif kind == "check":
                v = tk.IntVar(value=int(default))
                w = ttk.Checkbutton(self, variable=v)
            elif kind == "password":
                v = tk.StringVar(value="")
                w = ttk.Entry(self, textvariable=v, width=37, show="*")
            elif kind == "text":
                v = tk.StringVar(value=default)
                w = ttk.Entry(self, textvariable=v, width=37)
            else:
                v = tk.StringVar(value="" if default is None else str(default))
                w = ttk.Entry(self, textvariable=v, width=37)
            w.grid(row=r, column=1, sticky="w", pady=5)
            self.vars[key] = v
            r += 1
        self.err = ttk.Label(self, text="", background=PANEL, foreground=RED)
        self.err.grid(row=r, column=0, columnspan=2, sticky="w", pady=(6, 0))
        bar = ttk.Frame(self, style="Panel.TFrame")
        bar.grid(row=r + 1, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(bar, text="Cancel", command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(bar, text=save_text, style="Accent.TButton", command=self._save).pack(side="right")
        self.bind("<Return>", lambda e: self._save())
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()
        self.focus_set()

    def values(self):
        return {k: v.get() for k, v in self.vars.items()}

    def _save(self):
        try:
            if self.on_save(self.values()) is not False:
                self.destroy()
        except ApiError as e:
            self.err.config(text=str(e))
        except ValueError as e:
            self.err.config(text=str(e))


# ---------------------------------------------------------------- pages
class Page(ttk.Frame):
    title = ""
    auto = False          # True = refreshed automatically every few seconds

    def __init__(self, app):
        super().__init__(app.body)
        self.app = app
        self.api = app.api

    def refresh(self, quiet=False):
        pass

    def fail(self, e, quiet=False):
        if quiet:                      # background refresh: no pop-up, just say so in the header
            self.app.offline = True
            return
        messagebox.showerror("PawPet", str(e), parent=self.app)


class Dashboard(Page):
    title = "Dashboard"
    auto = True

    def __init__(self, app):
        super().__init__(app)
        self.cards = ttk.Frame(self)
        self.cards.pack(fill="x")
        self.stat = {}
        for i, (key, label) in enumerate([("a", "APPOINTMENTS TODAY"), ("p", "PENDING REQUESTS"), ("s", "SALES TODAY"),
                                          ("m", "SALES (30 DAYS)"), ("e", "EXPIRED / EXPIRING")]):
            f = ttk.Frame(self.cards, style="Panel.TFrame", padding=14)
            f.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 10, 0))
            self.cards.columnconfigure(i, weight=1)
            ttk.Label(f, text=label, style="PMuted.TLabel", font=("Segoe UI", 8, "bold")).pack(anchor="w")
            lab = ttk.Label(f, text="-", style="Big.TLabel", font=("Segoe UI", 19, "bold"))
            lab.pack(anchor="w", pady=(4, 0))
            sub = ttk.Label(f, text="", style="PMuted.TLabel")
            sub.pack(anchor="w")
            self.stat[key] = (lab, sub)
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, pady=(12, 0))
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)
        left = ttk.Frame(body)
        left.grid(row=0, column=0, sticky="nsew")
        left.rowconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        pend = ttk.Frame(left, style="Panel.TFrame", padding=12)
        pend.grid(row=0, column=0, sticky="nsew")
        head = ttk.Frame(pend, style="Panel.TFrame")
        head.pack(fill="x", pady=(0, 6))
        ttk.Label(head, text="Booking requests waiting for confirmation (all dates)", style="H2.TLabel").pack(side="left")
        ttk.Button(head, text="Decline", style="Danger.TButton", command=lambda: self.decide("cancelled")).pack(side="right")
        ttk.Button(head, text="Confirm", style="Accent.TButton", command=lambda: self.decide("confirmed")).pack(side="right", padx=8)
        w, self.pend = make_tree(pend, [("date", "Date"), ("time", "Time"), ("pet", "Pet"), ("owner", "Owner"),
                                        ("svc", "Service"), ("vet", "Vet")], [90, 75, 100, 130, 130, 120], height=4)
        w.pack(fill="both", expand=True)

        tod = ttk.Frame(left, style="Panel.TFrame", padding=12)
        tod.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        ttk.Label(tod, text="Today's appointments", style="H2.TLabel").pack(anchor="w", pady=(0, 6))
        w, self.appts = make_tree(tod, [("time", "Time"), ("pet", "Pet"), ("owner", "Owner"), ("svc", "Service"),
                                        ("vet", "Vet"), ("st", "Status")], [80, 110, 130, 130, 130, 90], height=4)
        w.pack(fill="both", expand=True)

        right = ttk.Frame(body)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        right.columnconfigure(0, weight=1)
        ex = ttk.Frame(right, style="Panel.TFrame", padding=12)
        ex.pack(fill="x")
        ttk.Label(ex, text="Medicine expiry alerts", style="H2.TLabel").pack(anchor="w", pady=(0, 6))
        w, self.exp = make_tree(ex, [("n", "Product"), ("b", "Batch"), ("q", "Qty"), ("d", "Expiry"), ("s", "Status")],
                                [130, 70, 40, 85, 95], height=3)
        w.pack(fill="x")
        lo = ttk.Frame(right, style="Panel.TFrame", padding=12)
        lo.pack(fill="x", pady=(10, 0))
        ttk.Label(lo, text="Low stock", style="H2.TLabel").pack(anchor="w", pady=(0, 6))
        w, self.low = make_tree(lo, [("n", "Product"), ("s", "Usable stock")], [220, 100], height=3)
        w.pack(fill="x")
        tp = ttk.Frame(right, style="Panel.TFrame", padding=12)
        tp.pack(fill="x", pady=(10, 0))
        ttk.Label(tp, text="Top sellers", style="H2.TLabel").pack(anchor="w", pady=(0, 6))
        w, self.top = make_tree(tp, [("n", "Item"), ("q", "Qty"), ("a", "Amount")], [160, 50, 100], height=3)
        w.pack(fill="x")
        self.pend_rows = {}

    def decide(self, status):
        aid = selected_id(self.pend)
        if aid is None:
            return messagebox.showinfo("PawPet", "Select a booking request first.", parent=self.app)
        a = self.pend_rows.get(aid, {})
        if status == "cancelled" and not messagebox.askyesno(
                "PawPet", "Decline the booking of %s (%s)?" % (a.get("pet_name", "?"), a.get("service_name", "?")),
                parent=self.app):
            return
        try:
            self.api.post("/appointments/%d/status" % aid, {"status": status})
        except ApiError as e:
            return self.fail(e)
        self.refresh()

    def refresh(self, quiet=False):
        try:
            d = self.api.get("/dashboard")
            ap = self.api.get("/appointments", date=today())
        except ApiError as e:
            return self.fail(e, quiet)
        pend = d.get("pending_list", [])
        self.app.note_pending(pend)
        self.stat["a"][0].config(text=str(d["appointments_today"]))
        self.stat["a"][1].config(text="booked for today")
        self.stat["p"][0].config(text=str(d["pending"]))
        self.stat["p"][1].config(text="need your confirmation")
        self.stat["s"][0].config(text=peso(d["sales_today"]))
        self.stat["s"][1].config(text="products and services")
        self.stat["m"][0].config(text=peso(d["sales_30"]))
        self.stat["m"][1].config(text="all recorded sales")
        exp = d.get("expiring", [])
        n_exp = d.get("expired_count", 0)
        self.stat["e"][0].config(text="%d / %d" % (n_exp, len(exp) - n_exp))
        self.stat["e"][1].config(text="%d expired, %d expiring soon" % (n_exp, len(exp) - n_exp))
        sels = [(t, t.selection()) for t in (self.pend, self.appts, self.exp, self.low, self.top)]
        for t in (self.pend, self.appts, self.exp, self.low, self.top):
            t.delete(*t.get_children())
        self.pend_rows = {a["id"]: a for a in pend}
        for a in pend:
            self.pend.insert("", "end", iid=str(a["id"]), tags=("pending",),
                             values=(a["appt_date"], t12(a["appt_time"]), a["pet_name"], a["customer_name"],
                                     a["service_name"], a["vet_name"]))
        for a in ap:
            self.appts.insert("", "end", iid=str(a["id"]), tags=(a["status"],),
                              values=(t12(a["appt_time"]), a["pet_name"], a["customer_name"], a["service_name"],
                                      a["vet_name"], a["status"].replace("_", " ")))
        for b in exp:
            expired = b["status"] == "expired"
            self.exp.insert("", "end", iid="b%d" % b["id"], tags=("out" if expired else "low",),
                            values=(b["product_name"], b["batch_no"] or "-", b["qty"], b["expiry_date"],
                                    "EXPIRED" if expired else "in %d d" % b["days_left"]))
        for p in d["low_stock"]:
            self.low.insert("", "end", iid=str(p["id"]), tags=("out" if p["stock"] == 0 else "low",),
                            values=(p["name"], "OUT" if p["stock"] == 0 else p["stock"]))
        for i, t in enumerate(d["top_items"]):
            self.top.insert("", "end", iid="t%d" % i, values=(t["item_name"], t["qty"], peso(t["amount"])))
        for t, sel in sels:
            restore(t, sel)


class Appointments(Page):
    title = "Appointments"
    auto = True

    def __init__(self, app):
        super().__init__(app)
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 10))
        ttk.Button(bar, text="‹", width=3, command=lambda: self.shift(-1)).pack(side="left")
        self.date = tk.StringVar(value="")          # empty = all dates, so new bookings are never hidden
        e = ttk.Entry(bar, textvariable=self.date, width=12)
        e.pack(side="left", padx=4)
        e.bind("<Return>", lambda ev: self.refresh())
        ttk.Button(bar, text="›", width=3, command=lambda: self.shift(1)).pack(side="left")
        ttk.Button(bar, text="Today", command=self.go_today).pack(side="left", padx=(8, 0))
        ttk.Button(bar, text="All dates", command=self.all_dates).pack(side="left", padx=4)
        self.status = tk.StringVar(value="All statuses")
        c = ttk.Combobox(bar, textvariable=self.status, state="readonly", width=14,
                         values=["All statuses", "pending", "confirmed", "completed", "cancelled", "no_show"])
        c.pack(side="left", padx=(12, 0))
        c.bind("<<ComboboxSelected>>", lambda ev: self.refresh())
        ttk.Button(bar, text="+ New appointment", style="Accent.TButton", command=self.new).pack(side="right")
        w, self.tree = make_tree(self, [("date", "Date"), ("time", "Time"), ("pet", "Pet"), ("owner", "Owner"),
                                        ("svc", "Service"), ("vet", "Vet"), ("st", "Status")],
                                 [95, 80, 140, 160, 160, 150, 100], height=16)
        w.pack(fill="both", expand=True)
        acts = ttk.Frame(self)
        acts.pack(fill="x", pady=(10, 0))
        for text, fn, st in [("Confirm", self.confirm, "Accent.TButton"), ("Complete visit", self.complete, "Accent.TButton"),
                             ("Schedule follow-up", self.followup, "TButton"), ("No-show", self.no_show, "TButton"),
                             ("Cancel", self.cancel, "Danger.TButton"), ("Details", self.details, "TButton")]:
            ttk.Button(acts, text=text, style=st, command=fn).pack(side="left", padx=(0, 8))
        self.rows = {}

    def shift(self, n):
        try:
            y, m, d = [int(x) for x in self.date.get().split("-")]
            self.date.set((date(y, m, d) + timedelta(days=n)).strftime("%Y-%m-%d"))
        except Exception:
            self.date.set(today())
        self.refresh()

    def go_today(self):
        self.date.set(today())
        self.refresh()

    def all_dates(self):
        self.date.set("")
        self.refresh()

    def refresh(self, quiet=False):
        d = self.date.get().strip()
        if d and not valid_date(d):
            if quiet:
                return
            return messagebox.showwarning("PawPet", "Date must look like 2026-10-25.", parent=self.app)
        st = self.status.get()
        try:
            rows = self.api.get("/appointments", date=d, status="" if st == "All statuses" else st)
        except ApiError as e:
            return self.fail(e, quiet)
        self.rows = {a["id"]: a for a in rows}
        sel = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        for a in rows:
            self.tree.insert("", "end", iid=str(a["id"]), tags=(a["status"],),
                             values=(a["appt_date"], t12(a["appt_time"]), a["pet_name"], a["customer_name"],
                                     a["service_name"] + (" (follow-up)" if a["followup_of"] else ""),
                                     a["vet_name"], a["status"].replace("_", " ")))
        restore(self.tree, sel)

    def pick(self, allowed=None, need=""):
        aid = selected_id(self.tree)
        if aid is None:
            messagebox.showinfo("PawPet", "Select an appointment first.", parent=self.app)
            return None
        a = self.rows[aid]
        if allowed and a["status"] not in allowed:
            messagebox.showinfo("PawPet", need or "That action is not available for this status.", parent=self.app)
            return None
        return a

    def _set(self, a, st):
        try:
            self.api.post("/appointments/%d/status" % a["id"], {"status": st})
        except ApiError as e:
            return self.fail(e)
        self.refresh()

    def confirm(self):
        a = self.pick(("pending",), "Only pending appointments can be confirmed.")
        if a:
            self._set(a, "confirmed")

    def no_show(self):
        a = self.pick(("confirmed",), "Only confirmed appointments can be marked no-show.")
        if a:
            self._set(a, "no_show")

    def cancel(self):
        a = self.pick(("pending", "confirmed"), "Only pending or confirmed appointments can be cancelled.")
        if a and messagebox.askyesno("PawPet", "Cancel %s's appointment?" % a["pet_name"], parent=self.app):
            self._set(a, "cancelled")

    def details(self):
        a = self.pick()
        if not a:
            return
        messagebox.showinfo("Appointment #%d" % a["id"],
                            "Pet: %s (%s %s)\nOwner: %s  %s\nService: %s - %s\nVet: %s\nWhen: %s %s\nStatus: %s\n\n"
                            "Pet notes: %s\nVisit notes: %s" % (
                                a["pet_name"], a["species"], a["breed"] or "", a["customer_name"],
                                a["customer_phone"] or "", a["service_name"], peso(a["service_price"]), a["vet_name"],
                                a["appt_date"], t12(a["appt_time"]), a["status"], a["pet_notes"] or "-", a["notes"] or "-"),
                            parent=self.app)

    def complete(self):
        a = self.pick(("confirmed",), "Confirm the appointment before completing it.")
        if not a:
            return
        try:
            products = [p for p in self.api.get("/products") if p["stock"] > 0]
        except ApiError as e:
            return self.fail(e)
        names = ["(none)"] + ["%d - %s (%d left)" % (p["id"], p["name"], p["stock"]) for p in products]

        def save(v):
            items = []
            for k in ("p1", "p2"):
                if v[k] != "(none)":
                    qty = int(v[k + "q"] or 1)
                    if qty < 1:
                        raise ValueError("Quantity must be at least 1.")
                    items.append({"product_id": int(v[k].split(" - ")[0]), "qty": qty})
            r = self.api.post("/appointments/%d/complete" % a["id"], {"notes": v["notes"] or None, "products": items})
            messagebox.showinfo("PawPet", "Visit completed. Total: %s" % peso(r["total"]), parent=self.app)
            self.refresh()
        FormDialog(self.app, "Complete visit - %s" % a["pet_name"], [
            ("notes", "Visit notes", "text", "", None),
            ("p1", "Product 1", "combo", "(none)", names), ("p1q", "Qty", "entry", "1", None),
            ("p2", "Product 2", "combo", "(none)", names), ("p2q", "Qty", "entry", "1", None)],
            save, "Complete & record sale")

    def followup(self):
        a = self.pick(("completed",), "Follow-ups are scheduled after a visit is completed.")
        if not a:
            return
        SlotDialog(self.app, "Schedule follow-up - %s" % a["pet_name"], self.api, a["vet_id"], a["service_id"],
                   lambda d, t, n: self.api.post("/appointments/%d/followup" % a["id"],
                                                 {"appt_date": d, "appt_time": t, "notes": n or "Follow-up visit"}),
                   self.refresh)

    def new(self):
        try:
            customers = [c for c in self.api.get("/customers") if c["active"]]
            pets = self.api.get("/pets", all=1)
            services = self.api.get("/services")
            vets = self.api.get("/vets")
        except ApiError as e:
            return self.fail(e)
        NewAppointment(self.app, self.api, customers, pets, services, vets, self.refresh)


class SlotPicker:
    """Mixin-style helper: date entry + time combobox filled from /availability."""

    @staticmethod
    def load(api, vet_id, service_id, d):
        if not valid_date(d):
            raise ValueError("Date must look like 2026-10-25.")
        return api.get("/availability", vet_id=vet_id, service_id=service_id, date=d)


class SlotDialog(tk.Toplevel):
    def __init__(self, parent, title, api, vet_id, service_id, on_book, after):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=PANEL, padx=22, pady=18)
        self.transient(parent)
        self.api, self.vet_id, self.service_id, self.on_book, self.after_cb = api, vet_id, service_id, on_book, after
        ttk.Label(self, text=title, style="H2.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))
        ttk.Label(self, text="Date (YYYY-MM-DD)", style="PMuted.TLabel").grid(row=1, column=0, sticky="w", pady=5)
        self.d = tk.StringVar(value=(date.today() + timedelta(days=1)).strftime("%Y-%m-%d"))
        ttk.Entry(self, textvariable=self.d, width=14).grid(row=1, column=1, padx=8)
        ttk.Button(self, text="Show times", command=self.load).grid(row=1, column=2)
        ttk.Label(self, text="Time", style="PMuted.TLabel").grid(row=2, column=0, sticky="w", pady=5)
        self.t = tk.StringVar()
        self.cb = ttk.Combobox(self, textvariable=self.t, state="readonly", width=16)
        self.cb.grid(row=2, column=1, columnspan=2, sticky="w", padx=8)
        ttk.Label(self, text="Notes", style="PMuted.TLabel").grid(row=3, column=0, sticky="w", pady=5)
        self.n = tk.StringVar()
        ttk.Entry(self, textvariable=self.n, width=30).grid(row=3, column=1, columnspan=2, sticky="w", padx=8)
        self.err = ttk.Label(self, text="", background=PANEL, foreground=RED)
        self.err.grid(row=4, column=0, columnspan=3, sticky="w")
        bar = ttk.Frame(self, style="Panel.TFrame")
        bar.grid(row=5, column=0, columnspan=3, sticky="e", pady=(10, 0))
        ttk.Button(bar, text="Cancel", command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(bar, text="Book", style="Accent.TButton", command=self.book).pack(side="right")
        self.map = {}
        self.grab_set()
        self.load()

    def load(self):
        try:
            slots = SlotPicker.load(self.api, self.vet_id, self.service_id, self.d.get().strip())
        except (ApiError, ValueError) as e:
            self.err.config(text=str(e))
            return
        free = [t12(s["time"]) for s in slots if s["available"]]
        self.map = {t12(s["time"]): s["time"] for s in slots}
        self.cb["values"] = free
        self.t.set(free[0] if free else "")
        self.err.config(text="" if free else "No free times on this date.")

    def book(self):
        if not self.t.get():
            self.err.config(text="Pick a time.")
            return
        try:
            self.on_book(self.d.get().strip(), self.map[self.t.get()], self.n.get())
        except ApiError as e:
            self.err.config(text=str(e))
            return
        self.after_cb()
        self.destroy()


class NewAppointment(SlotDialog):
    def __init__(self, parent, api, customers, pets, services, vets, after):
        self.customers, self.pets, self.services, self.vets = customers, pets, services, vets
        tk.Toplevel.__init__(self, parent)
        self.title("New appointment")
        self.configure(bg=PANEL, padx=22, pady=18)
        self.transient(parent)
        self.api, self.after_cb = api, after
        ttk.Label(self, text="New appointment (auto-confirmed)", style="H2.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        def row(r, label, widget):
            ttk.Label(self, text=label, style="PMuted.TLabel").grid(row=r, column=0, sticky="w", pady=5, padx=(0, 12))
            widget.grid(row=r, column=1, columnspan=2, sticky="w")
        self.c = tk.StringVar()
        cc = ttk.Combobox(self, textvariable=self.c, state="readonly", width=34, values=[x["full_name"] for x in customers])
        row(1, "Customer", cc)
        cc.bind("<<ComboboxSelected>>", self.on_customer)
        self.p = tk.StringVar()
        self.pc = ttk.Combobox(self, textvariable=self.p, state="readonly", width=34)
        row(2, "Pet", self.pc)
        self.s = tk.StringVar(value="%s - %s" % (services[0]["name"], peso(services[0]["price"])))
        sc = ttk.Combobox(self, textvariable=self.s, state="readonly", width=34,
                          values=["%s - %s" % (x["name"], peso(x["price"])) for x in services])
        row(3, "Service", sc)
        self.v = tk.StringVar(value=vets[0]["name"])
        vc = ttk.Combobox(self, textvariable=self.v, state="readonly", width=34, values=[x["name"] for x in vets])
        row(4, "Veterinarian", vc)
        self.d = tk.StringVar(value=(date.today() + timedelta(days=1)).strftime("%Y-%m-%d"))
        row(5, "Date (YYYY-MM-DD)", ttk.Entry(self, textvariable=self.d, width=14))
        ttk.Button(self, text="Show times", command=self.load).grid(row=5, column=2, sticky="w")
        self.t = tk.StringVar()
        self.cb = ttk.Combobox(self, textvariable=self.t, state="readonly", width=16)
        row(6, "Time", self.cb)
        self.n = tk.StringVar()
        row(7, "Notes", ttk.Entry(self, textvariable=self.n, width=37))
        self.err = ttk.Label(self, text="", background=PANEL, foreground=RED)
        self.err.grid(row=8, column=0, columnspan=3, sticky="w")
        bar = ttk.Frame(self, style="Panel.TFrame")
        bar.grid(row=9, column=0, columnspan=3, sticky="e", pady=(10, 0))
        ttk.Button(bar, text="Cancel", command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(bar, text="Book", style="Accent.TButton", command=self.book).pack(side="right")
        self.map = {}
        self.grab_set()

    def on_customer(self, _=None):
        cust = next(x for x in self.customers if x["full_name"] == self.c.get())
        mine = [p for p in self.pets if p["owner_id"] == cust["id"]]
        self.pc["values"] = ["%d - %s (%s)" % (p["id"], p["name"], p["species"]) for p in mine]
        self.p.set(self.pc["values"][0] if mine else "")
        if not mine:
            self.err.config(text="This customer has no pets yet.")
        else:
            self.err.config(text="")

    def _ids(self):
        svc = next(x for x in self.services if "%s - %s" % (x["name"], peso(x["price"])) == self.s.get())
        vet = next(x for x in self.vets if x["name"] == self.v.get())
        return svc["id"], vet["id"]

    def load(self):
        try:
            sid, vid = self._ids()
            slots = SlotPicker.load(self.api, vid, sid, self.d.get().strip())
        except (ApiError, ValueError, StopIteration) as e:
            self.err.config(text=str(e) or "Choose service and vet.")
            return
        free = [t12(s["time"]) for s in slots if s["available"]]
        self.map = {t12(s["time"]): s["time"] for s in slots}
        self.cb["values"] = free
        self.t.set(free[0] if free else "")
        self.err.config(text="" if free else "No free times for this vet on that date.")

    def book(self):
        if not self.c.get() or not self.p.get():
            self.err.config(text="Choose a customer who has a pet.")
            return
        if not self.t.get():
            self.err.config(text="Press 'Show times' and pick a time.")
            return
        cust = next(x for x in self.customers if x["full_name"] == self.c.get())
        sid, vid = self._ids()
        try:
            self.api.post("/appointments", {"customer_id": cust["id"], "pet_id": int(self.p.get().split(" - ")[0]),
                                            "service_id": sid, "vet_id": vid, "appt_date": self.d.get().strip(),
                                            "appt_time": self.map[self.t.get()], "notes": self.n.get()})
        except ApiError as e:
            self.err.config(text=str(e))
            return
        self.after_cb()
        self.destroy()


class Customers(Page):
    title = "Customers"

    def __init__(self, app):
        super().__init__(app)
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 10))
        self.q = tk.StringVar()
        e = ttk.Entry(bar, textvariable=self.q, width=34)
        e.pack(side="left")
        e.bind("<Return>", lambda ev: self.refresh())
        ttk.Button(bar, text="Search", command=self.refresh).pack(side="left", padx=6)
        ttk.Button(bar, text="+ Add customer", style="Accent.TButton", command=self.add).pack(side="right")
        w, self.tree = make_tree(self, [("n", "Name"), ("u", "Username"), ("p", "Phone"), ("pets", "Pets"),
                                        ("v", "Visits"), ("s", "Status")], [200, 130, 130, 60, 60, 90], height=16)
        w.pack(fill="both", expand=True)
        acts = ttk.Frame(self)
        acts.pack(fill="x", pady=(10, 0))
        ttk.Button(acts, text="View pets & history", command=self.view).pack(side="left")
        self.toggle_btn = ttk.Button(acts, text="Enable / disable account", command=self.toggle)
        self.toggle_btn.pack(side="left", padx=8)
        ttk.Button(acts, text="Reset password", command=self.reset_pw).pack(side="left")

    def refresh(self):
        try:
            rows = self.api.get("/customers", q=self.q.get().strip())
        except ApiError as e:
            return self.fail(e)
        self.tree.delete(*self.tree.get_children())
        for c in rows:
            self.tree.insert("", "end", iid=str(c["id"]), tags=("" if c["active"] else "cancelled",),
                             values=(c["full_name"], c["username"], c["phone"] or "-", c["pet_count"], c["appt_count"],
                                     "Active" if c["active"] else "Disabled"))

    def add(self):
        def save(v):
            if not v["full_name"].strip() or not v["username"].strip():
                raise ValueError("Name and username are required.")
            r = self.api.post("/customers", v)
            self.refresh()
            if r.get("temp_password"):
                messagebox.showinfo("PawPet", "Customer created.\n\nUsername: %s\nTemporary password: %s\n\nGive this to the customer. "
                                    "They must choose a new password at first sign-in." % (v["username"].strip(), r["temp_password"]),
                                    parent=self.app)
        FormDialog(self.app, "Add customer", [
            ("full_name", "Full name", "entry", "", None), ("username", "Username", "entry", "", None),
            ("phone", "Phone", "entry", "", None), ("email", "Email", "entry", "", None),
            ("password", "Password (blank = make a temporary one)", "entry", "", None)], save)

    def reset_pw(self):
        cid = selected_id(self.tree)
        if cid is None:
            return messagebox.showinfo("PawPet", "Select a customer first.", parent=self.app)
        name = self.tree.item(str(cid), "values")[0]
        if not messagebox.askyesno("PawPet", "Reset the password of %s?\nThey will be signed out everywhere." % name, parent=self.app):
            return
        try:
            r = self.api.post("/users/%d/reset-password" % cid)
        except ApiError as e:
            return self.fail(e)
        messagebox.showinfo("PawPet", "Username: %s\nTemporary password: %s\n\nGive this to the customer. "
                            "They must choose a new password at first sign-in." % (r["username"], r["temp_password"]), parent=self.app)

    def view(self):
        cid = selected_id(self.tree)
        if cid is None:
            return messagebox.showinfo("PawPet", "Select a customer first.", parent=self.app)
        try:
            r = self.api.get("/customers/%d" % cid)
        except ApiError as e:
            return self.fail(e)
        pets = "\n".join("- %s: %s %s, %s%s" % (p["name"], p["species"], p["breed"] or "",
                                              ("%s yr" % p["age"]) if p["age"] else "age ?",
                                              (" [%s]" % p["notes"]) if p["notes"] else "") for p in r["pets"]) or "No pets"
        hist = "\n".join("- %s %s  %s / %s  [%s]" % (a["appt_date"], t12(a["appt_time"]), a["pet_name"],
                                                    a["service_name"], a["status"]) for a in r["appointments"][:10]) or "None"
        c = r["customer"]
        messagebox.showinfo(c["full_name"], "%s  %s\n\nPETS\n%s\n\nRECENT APPOINTMENTS\n%s" % (
            c["email"] or "", c["phone"] or "", pets, hist), parent=self.app)

    def toggle(self):
        cid = selected_id(self.tree)
        if cid is None:
            return messagebox.showinfo("PawPet", "Select a customer first.", parent=self.app)
        try:
            self.api.post("/customers/%d/toggle" % cid)
        except ApiError as e:
            return self.fail(e)
        self.refresh()


class Inventory(Page):
    title = "Inventory"
    auto = True

    def __init__(self, app):
        super().__init__(app)
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 10))
        self.q = tk.StringVar()
        e = ttk.Entry(bar, textvariable=self.q, width=30)
        e.pack(side="left")
        e.bind("<Return>", lambda ev: self.refresh())
        ttk.Button(bar, text="Search", command=self.refresh).pack(side="left", padx=6)
        ttk.Button(bar, text="+ Add product", style="Accent.TButton", command=lambda: self.form(None)).pack(side="right")
        w, self.tree = make_tree(self, [("n", "Product"), ("c", "Category"), ("p", "Price"), ("s", "Usable stock"),
                                        ("x", "Expired"), ("e", "Next expiry"), ("r", "Reorder at"), ("st", "Status")],
                                 [220, 100, 100, 90, 70, 100, 80, 140], height=16)
        w.pack(fill="both", expand=True)
        acts = ttk.Frame(self)
        acts.pack(fill="x", pady=(10, 0))
        for text, fn in [("Receive new batch", self.restock), ("Walk-in sale", self.sell), ("Edit", self.edit)]:
            ttk.Button(acts, text=text, command=fn).pack(side="left", padx=(0, 8))
        self.del_btn = ttk.Button(acts, text="Delete (admin)", style="Danger.TButton", command=self.delete)
        self.del_btn.pack(side="left")
        ttk.Label(acts, text="Expired stock is not counted and cannot be sold. See the Batches & Expiry page.",
                  style="Muted.TLabel").pack(side="right")
        self.rows = {}

    def refresh(self, quiet=False):
        try:
            rows = self.api.get("/products", q=self.q.get().strip())
        except ApiError as e:
            return self.fail(e, quiet)
        self.rows = {p["id"]: p for p in rows}
        sel = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        for p in rows:
            left = days_until(p.get("next_expiry"))
            if p.get("expired_qty", 0) > 0:
                tag, label = "out", "Has expired stock"
            elif p["stock"] == 0:
                tag, label = "out", "Out of stock"
            elif left is not None and left <= 30:
                tag, label = "low", "Expiring soon"
            elif p["stock"] <= p["reorder_level"]:
                tag, label = "low", "Low stock"
            else:
                tag, label = "", "In stock"
            self.tree.insert("", "end", iid=str(p["id"]), tags=(tag,),
                             values=(p["name"], p["category"], peso(p["price"]), p["stock"],
                                     p.get("expired_qty", 0) or "-", p.get("next_expiry") or "-",
                                     p["reorder_level"], label))
        restore(self.tree, sel)

    def pick(self):
        pid = selected_id(self.tree)
        if pid is None:
            messagebox.showinfo("PawPet", "Select a product first.", parent=self.app)
            return None
        return self.rows[pid]

    def _ask_qty(self, title, label, default):
        res = {}

        def save(v):
            n = int(v["n"])
            res["n"] = n
        dlg = FormDialog(self.app, title, [("n", label, "entry", default, None)], save, "OK")
        self.app.wait_window(dlg)
        return res.get("n")

    def restock(self):
        p = self.pick()
        if not p:
            return

        def save(v):
            try:
                qty = int(v["qty"])
            except ValueError:
                raise ValueError("Units must be a whole number.")
            if qty < 1:
                raise ValueError("Units must be at least 1.")
            exp = v["expiry_date"].strip()
            if exp and not valid_date(exp):
                raise ValueError("Expiry date must look like 2027-01-31.")
            self.api.post("/products/%d/restock" % p["id"], {"qty": qty, "batch_no": v["batch_no"].strip(),
                                                             "expiry_date": exp})
            self.refresh()
        FormDialog(self.app, "Receive new batch: %s" % p["name"], [
            ("qty", "Units received", "entry", "10", None),
            ("batch_no", "Batch / lot no.", "entry", "", None),
            ("expiry_date", "Expiry date (YYYY-MM-DD)", "entry", "", None)], save, "Add batch")

    def sell(self):
        p = self.pick()
        if not p:
            return
        n = self._ask_qty("Sell %s" % p["name"], "Quantity", "1")
        if n is None:
            return
        try:
            r = self.api.post("/products/%d/sell" % p["id"], {"qty": n})
        except ApiError as e:
            return self.fail(e)
        messagebox.showinfo("PawPet", "Sold. Amount: %s" % peso(r["amount"]), parent=self.app)
        self.refresh()

    def edit(self):
        p = self.pick()
        if p:
            self.form(p)

    def delete(self):
        p = self.pick()
        if p and messagebox.askyesno("PawPet", "Delete %s?" % p["name"], parent=self.app):
            try:
                self.api.delete("/products/%d" % p["id"])
            except ApiError as e:
                return self.fail(e)
            self.refresh()

    def form(self, p):
        def save(v):
            body = {"name": v["name"], "category": v["category"] or "Other", "price": float(v["price"]),
                    "stock": int(v["stock"]), "reorder_level": int(v["reorder_level"] or 5)}
            if p:
                self.api.put("/products/%d" % p["id"], body)
            else:
                exp = v["expiry_date"].strip()
                if exp and not valid_date(exp):
                    raise ValueError("Expiry date must look like 2027-01-31.")
                body["batch_no"] = v["batch_no"].strip()
                body["expiry_date"] = exp
                self.api.post("/products", body)
            self.refresh()
        fields = [
            ("name", "Name", "entry", (p or {}).get("name", ""), None),
            ("category", "Category", "entry", (p or {}).get("category", "Food"), None),
            ("price", "Price", "entry", (p or {}).get("price", ""), None),
            ("stock", "Stock", "entry", (p or {}).get("stock", 0), None),
            ("reorder_level", "Reorder level", "entry", (p or {}).get("reorder_level", 5), None)]
        if not p:
            fields += [("batch_no", "Batch / lot no. (optional)", "entry", "", None),
                       ("expiry_date", "Expiry date (YYYY-MM-DD, optional)", "entry", "", None)]
        FormDialog(self.app, "Edit product" if p else "Add product", fields, save)


class Batches(Page):
    """Every batch of every product with its expiry date, so nothing expires unnoticed."""
    title = "Batches & Expiry"
    auto = True

    def __init__(self, app):
        super().__init__(app)
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 10))
        self.flt = tk.StringVar(value="All batches")
        c = ttk.Combobox(bar, textvariable=self.flt, state="readonly", width=24,
                         values=["All batches", "Expired", "Expiring soon (30 days)", "OK"])
        c.pack(side="left")
        c.bind("<<ComboboxSelected>>", lambda ev: self.refresh())
        self.sum = ttk.Label(bar, text="", style="Muted.TLabel")
        self.sum.pack(side="left", padx=14)
        w, self.tree = make_tree(self, [("p", "Product"), ("b", "Batch / lot"), ("q", "Qty left"), ("e", "Expiry date"),
                                        ("d", "When"), ("s", "Status")], [240, 130, 80, 110, 140, 110], height=16)
        w.pack(fill="both", expand=True)
        acts = ttk.Frame(self)
        acts.pack(fill="x", pady=(10, 0))
        ttk.Button(acts, text="Discard selected batch", style="Danger.TButton", command=self.discard).pack(side="left")
        ttk.Label(acts, text="Discard removes what is left of the batch from stock (for example expired medicine thrown away). "
                             "New batches are added from the Inventory page.", style="Muted.TLabel").pack(side="left", padx=12)
        self.rows = {}

    def refresh(self, quiet=False):
        try:
            rows = self.api.get("/batches")
        except ApiError as e:
            return self.fail(e, quiet)
        want = {"Expired": ("expired",), "Expiring soon (30 days)": ("expiring",), "OK": ("ok", "no_expiry")}.get(self.flt.get())
        n_exp = sum(1 for b in rows if b["status"] == "expired")
        n_soon = sum(1 for b in rows if b["status"] == "expiring")
        self.sum.config(text="%d expired · %d expiring within 30 days · %d batches" % (n_exp, n_soon, len(rows)))
        self.rows = {b["id"]: b for b in rows}
        sel = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        for b in rows:
            if want and b["status"] not in want:
                continue
            if b["status"] == "expired":
                when, label, tag = "%d day(s) ago" % abs(b["days_left"]), "EXPIRED", "out"
            elif b["status"] == "expiring":
                when, label, tag = "in %d day(s)" % b["days_left"], "Expiring soon", "low"
            elif b["status"] == "ok":
                when, label, tag = "in %d day(s)" % b["days_left"], "OK", ""
            else:
                when, label, tag = "-", "No expiry", ""
            self.tree.insert("", "end", iid=str(b["id"]), tags=(tag,),
                             values=(b["product_name"], b["batch_no"] or "-", b["qty"], b["expiry_date"] or "-", when, label))
        restore(self.tree, sel)

    def discard(self):
        bid = selected_id(self.tree)
        if bid is None:
            return messagebox.showinfo("PawPet", "Select a batch first.", parent=self.app)
        b = self.rows[bid]
        if not messagebox.askyesno("PawPet", "Discard %d unit(s) of %s (batch %s)?\nThey will be removed from stock."
                                   % (b["qty"], b["product_name"], b["batch_no"] or "-"), parent=self.app):
            return
        try:
            self.api.post("/batches/%d/discard" % bid)
        except ApiError as e:
            return self.fail(e)
        self.refresh()


class Vets(Page):
    title = "Veterinarians"

    def __init__(self, app):
        super().__init__(app)
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 10))
        ttk.Label(bar, text="Availability on (YYYY-MM-DD)", style="Muted.TLabel").pack(side="left")
        self.d = tk.StringVar(value=today())
        e = ttk.Entry(bar, textvariable=self.d, width=12)
        e.pack(side="left", padx=8)
        e.bind("<Return>", lambda ev: self.refresh())
        ttk.Button(bar, text="Check", command=self.refresh).pack(side="left")
        self.add_btn = ttk.Button(bar, text="+ Add veterinarian", style="Accent.TButton", command=lambda: self.form(None))
        self.add_btn.pack(side="right")
        w, self.tree = make_tree(self, [("n", "Veterinarian"), ("sp", "Specialty"), ("days", "Working days"),
                                        ("h", "Hours"), ("free", "Free slots"), ("a", "Active")],
                                 [170, 140, 200, 150, 90, 70], height=10)
        w.pack(fill="both", expand=True)
        self.detail = ttk.Label(self, text="Select a vet to see free times.", style="Muted.TLabel", wraplength=900, justify="left")
        self.detail.pack(fill="x", pady=8)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.show())
        self.edit_btn = ttk.Button(self, text="Edit selected (admin)", command=self.edit)
        self.edit_btn.pack(anchor="w")
        self.vets, self.slots = {}, {}

    def refresh(self):
        d = self.d.get().strip()
        if not valid_date(d):
            return messagebox.showwarning("PawPet", "Date must look like 2026-10-25.", parent=self.app)
        try:
            vets = self.api.get("/vets")
            slots = {v["id"]: self.api.get("/availability", vet_id=v["id"], date=d) for v in vets}
        except ApiError as e:
            return self.fail(e)
        self.vets, self.slots = {v["id"]: v for v in vets}, slots
        self.tree.delete(*self.tree.get_children())
        for v in vets:
            free = len([s for s in slots[v["id"]] if s["available"]])
            self.tree.insert("", "end", iid=str(v["id"]), values=(
                v["name"], v["specialty"] or "", ", ".join(DAYS[int(x)] for x in v["work_days"].split(",")),
                "%s - %s" % (t12(v["start_time"]), t12(v["end_time"])),
                free if slots[v["id"]] else "off", "Yes" if v["active"] else "No"))
        self.detail.config(text="Select a vet to see free times.")

    def show(self):
        vid = selected_id(self.tree)
        if vid is None:
            return
        s = self.slots.get(vid, [])
        free = [t12(x["time"]) for x in s if x["available"]]
        busy = [t12(x["time"]) for x in s if not x["available"]]
        if not s:
            self.detail.config(text="%s is not working on this date." % self.vets[vid]["name"])
        else:
            self.detail.config(text="FREE: %s\nTAKEN: %s" % (", ".join(free) or "none", ", ".join(busy) or "none"))

    def edit(self):
        vid = selected_id(self.tree)
        if vid is None:
            return messagebox.showinfo("PawPet", "Select a veterinarian first.", parent=self.app)
        self.form(self.vets[vid])

    def form(self, v):
        def save(x):
            days = [str(i) for i, name in enumerate(DAYS) if name in [s.strip().capitalize() for s in x["days"].split(",")]]
            if not days:
                raise ValueError("Enter working days like: Mon,Tue,Wed")
            if x["end"] <= x["start"]:
                raise ValueError("End time must be after start time.")
            body = {"name": x["name"], "specialty": x["specialty"], "work_days": ",".join(days),
                    "start_time": x["start"], "end_time": x["end"]}
            if v:
                body["active"] = int(x["active"])
                self.api.put("/vets/%d" % v["id"], body)
            else:
                self.api.post("/vets", body)
            self.refresh()
        fields = [("name", "Name", "entry", v["name"] if v else "", None),
                  ("specialty", "Specialty", "entry", (v["specialty"] or "") if v else "", None),
                  ("days", "Working days (Mon,Tue,..)", "entry",
                   ",".join(DAYS[int(i)] for i in v["work_days"].split(",")) if v else "Mon,Tue,Wed,Thu,Fri", None),
                  ("start", "Start (HH:MM)", "entry", v["start_time"] if v else "09:00", None),
                  ("end", "End (HH:MM)", "entry", v["end_time"] if v else "17:00", None)]
        if v:
            fields.append(("active", "Active", "check", v["active"], None))
        FormDialog(self.app, "Edit veterinarian" if v else "Add veterinarian", fields, save)


class Services(Page):
    title = "Services"

    def __init__(self, app):
        super().__init__(app)
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 10))
        ttk.Button(bar, text="+ Add service", style="Accent.TButton", command=lambda: self.form(None)).pack(side="right")
        ttk.Button(bar, text="Edit selected", command=self.edit).pack(side="left")
        w, self.tree = make_tree(self, [("n", "Service"), ("d", "Description"), ("p", "Price"), ("t", "Duration")],
                                 [190, 380, 110, 90], height=14)
        w.pack(fill="both", expand=True)
        self.rows = {}

    def refresh(self):
        try:
            rows = self.api.get("/services")
        except ApiError as e:
            return self.fail(e)
        self.rows = {s["id"]: s for s in rows}
        self.tree.delete(*self.tree.get_children())
        for s in rows:
            self.tree.insert("", "end", iid=str(s["id"]), values=(s["name"], s["description"] or "", peso(s["price"]),
                                                                   "%d min" % s["duration"]))

    def edit(self):
        sid = selected_id(self.tree)
        if sid is None:
            return messagebox.showinfo("PawPet", "Select a service first.", parent=self.app)
        self.form(self.rows[sid])

    def form(self, s):
        def save(v):
            body = {"name": v["name"], "description": v["description"], "price": float(v["price"]),
                    "duration": int(v["duration"])}
            if s:
                self.api.put("/services/%d" % s["id"], body)
            else:
                self.api.post("/services", body)
            self.refresh()
        s = s or {}
        FormDialog(self.app, "Edit service" if s else "Add service", [
            ("name", "Name", "entry", s.get("name", ""), None), ("description", "Description", "entry", s.get("description", ""), None),
            ("price", "Price", "entry", s.get("price", ""), None), ("duration", "Duration (min)", "entry", s.get("duration", 30), None)], save)


class Sales(Page):
    title = "Sales"

    def __init__(self, app):
        super().__init__(app)
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 10))
        ttk.Label(bar, text="Period", style="Muted.TLabel").pack(side="left")
        self.days = tk.StringVar(value="30")
        c = ttk.Combobox(bar, textvariable=self.days, state="readonly", width=6, values=["7", "30", "90"])
        c.pack(side="left", padx=8)
        c.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        ttk.Label(bar, text="days", style="Muted.TLabel").pack(side="left")
        self.total = ttk.Label(bar, text="", font=("Segoe UI", 11, "bold"))
        self.total.pack(side="right")
        w, self.tree = make_tree(self, [("d", "Date"), ("i", "Item"), ("k", "Type"), ("c", "Customer"),
                                        ("q", "Qty"), ("a", "Amount")], [150, 230, 80, 170, 50, 120], height=18)
        w.pack(fill="both", expand=True)

    def refresh(self):
        try:
            rows = self.api.get("/sales", days=self.days.get())
        except ApiError as e:
            return self.fail(e)
        self.tree.delete(*self.tree.get_children())
        for i, s in enumerate(rows):
            self.tree.insert("", "end", iid=str(i), values=(s["created_at"][:16], s["item_name"], s["kind"],
                                                             s["customer_name"] or "Walk-in", s["qty"], peso(s["amount"])))
        prod = sum(s["amount"] for s in rows if s["kind"] == "product")
        tot = sum(s["amount"] for s in rows)
        self.total.config(text="Total %s   (products %s, services %s)" % (peso(tot), peso(prod), peso(tot - prod)))


# ---------------------------------------------------------------- application shell
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PawPet Admin")
        self.geometry("1280x740")
        self.minsize(1100, 640)
        self.configure(bg=BG)
        setup_style(self)
        self.api = Api()
        self.login_view()

    # ---- login
    def login_view(self):
        for w in self.winfo_children():
            w.destroy()
        root = ttk.Frame(self)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)
        hero = tk.Frame(root, bg="#0f5132")
        hero.grid(row=0, column=0, sticky="nsew")
        inner = tk.Frame(hero, bg="#0f5132")
        inner.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(inner, text="🐾  PawPet", bg="#0f5132", fg="white", font=("Segoe UI", 28, "bold")).pack(anchor="w")
        tk.Label(inner, text="Run the clinic.\nNot the paperwork.", bg="#0f5132", fg="white", justify="left",
                 font=("Segoe UI", 30, "bold")).pack(anchor="w", pady=(22, 10))
        tk.Label(inner, text="Inventory • vet schedules • appointments • sales", bg="#0f5132", fg="#bfe3cd",
                 font=("Segoe UI", 12)).pack(anchor="w")
        form = ttk.Frame(root)
        form.grid(row=0, column=1, sticky="nsew")
        box = ttk.Frame(form, style="Panel.TFrame", padding=30)
        box.place(relx=0.5, rely=0.5, anchor="center")
        ttk.Label(box, text="Staff sign in", style="H2.TLabel", font=("Segoe UI", 18, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(box, text="PawPet Admin Dashboard", style="PMuted.TLabel").grid(row=1, column=0, sticky="w", pady=(0, 14))
        self.f_url, self.f_user, self.f_pass = (tk.StringVar(value="http://localhost:5000"), tk.StringVar(value=""),
                                                tk.StringVar(value=""))
        for r, (label, var, show) in enumerate([("Server address", self.f_url, ""), ("Username", self.f_user, ""),
                                                ("Password", self.f_pass, "*")]):
            ttk.Label(box, text=label, style="PMuted.TLabel").grid(row=2 + r * 2, column=0, sticky="w", pady=(8, 3))
            ttk.Entry(box, textvariable=var, show=show, width=36).grid(row=3 + r * 2, column=0, sticky="we")
        self.login_err = ttk.Label(box, text="", background=PANEL, foreground=RED)
        self.login_err.grid(row=8, column=0, sticky="w", pady=(8, 0))
        ttk.Button(box, text="Sign in →", style="Accent.TButton", command=self.do_login).grid(row=9, column=0, sticky="we", pady=(8, 0))
        self.bind("<Return>", lambda e: self.do_login())

    def do_login(self):
        self.api = Api(self.f_url.get().strip() or "http://localhost:5000")
        try:
            self.api.login(self.f_user.get().strip(), self.f_pass.get())
        except ApiError as e:
            self.login_err.config(text=str(e))
            return
        self.unbind("<Return>")
        if self.api.user.get("must_change"):
            self.login_err.config(text="")
            if not self.change_pw(forced=True):          # must choose a new password before anything else
                self.api.logout()
                self.login_err.config(text="You must change your temporary password to continue.")
                self.bind("<Return>", lambda e: self.do_login())
                return
        self.main_view()

    def change_pw(self, forced=False):
        def save(v):
            if v["new"] != v["again"]:
                raise ValueError("The two new passwords do not match.")
            self.api.change_password(v["old"], v["new"])
            self.api.user["must_change"] = False
            messagebox.showinfo("PawPet", "Password changed.", parent=self)
        dlg = FormDialog(self, "Change password" if not forced else "Choose a new password", [
            ("old", "Current password", "password", "", None),
            ("new", "New password (8+ chars, letters + numbers)", "password", "", None),
            ("again", "Repeat new password", "password", "", None)], save, "Change password")
        self.wait_window(dlg)
        return not self.api.user.get("must_change")

    # ---- main
    def main_view(self):
        for w in self.winfo_children():
            w.destroy()
        side = tk.Frame(self, bg="#0b140f", width=220)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Label(side, text="🐾  PawPet", bg="#0b140f", fg="white", font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=18, pady=(20, 22))
        self.content = ttk.Frame(self)
        self.content.pack(side="left", fill="both", expand=True, padx=24, pady=18)
        head = ttk.Frame(self.content)
        head.pack(fill="x", pady=(0, 14))
        self.title_lbl = ttk.Label(head, text="", style="H1.TLabel")
        self.title_lbl.pack(side="left")
        u = self.api.user
        ttk.Label(head, text="%s  (%s)" % (u["full_name"], u["role"]), style="Muted.TLabel").pack(side="right")
        ttk.Button(head, text="🔔 Send reminders", command=self.reminders).pack(side="right", padx=12)
        ttk.Button(head, text="🔑 Password", command=self.change_pw).pack(side="right")
        self.status_lbl = ttk.Label(head, text="", style="Muted.TLabel")
        self.status_lbl.pack(side="right", padx=(0, 6))
        self.alert_lbl = tk.Label(self.content, text="", bg=BG, fg="#06210f", font=("Segoe UI", 10, "bold"), anchor="w")
        self.body = ttk.Frame(self.content)
        self.body.pack(fill="both", expand=True)
        pages = [Dashboard, Appointments, Customers, Inventory, Batches, Vets, Sales]
        if u["role"] == "admin":
            pages.insert(len(pages) - 1, Services)
        self.nav = {}
        self.pages = {}
        self.page_classes = pages
        for cls in pages:
            btn = ttk.Button(side, text=cls.title, style="Nav.TButton", command=lambda c=cls: self.show(c))
            btn.pack(fill="x", padx=10, pady=1)
            self.nav[cls] = btn
        ttk.Button(side, text="Log out", command=self.logout).pack(side="bottom", fill="x", padx=14, pady=16)
        self.seen_pending = None
        self.offline = False
        self.current = None
        self.show(Dashboard)
        self._stop_timer()
        self._timer = self.after(REFRESH_MS, self._tick)

    def show(self, cls):
        for c, b in self.nav.items():
            b.configure(style="NavOn.TButton" if c is cls else "Nav.TButton")
        for p in self.pages.values():
            p.pack_forget()
        if cls not in self.pages:
            self.pages[cls] = cls(self)
        page = self.pages[cls]
        self.current = page
        self.title_lbl.config(text=cls.title)
        page.pack(fill="both", expand=True)
        page.refresh()

    # ---- live updates
    def _stop_timer(self):
        t = getattr(self, "_timer", None)
        if t:
            try:
                self.after_cancel(t)
            except Exception:
                pass
        self._timer = None

    def _tick(self):
        """Every few seconds: refresh the visible page and look for new booking requests.
        A 1.5 s health check comes first, so a missing/slow server never freezes the window for long."""
        self._timer = None
        delay = REFRESH_MS
        try:
            page = self.current
            if page is not None and not self.grab_current():        # do not disturb an open dialog
                if not self.api.health():
                    self.offline = True
                    delay = REFRESH_MS * 2
                else:
                    self.offline = False
                    if page.auto:
                        page.refresh(quiet=True)
                    if not self.offline and not isinstance(page, Dashboard):   # the dashboard looks for new bookings itself
                        try:
                            self.note_pending(self.api.get("/dashboard")["pending_list"])
                        except ApiError:
                            self.offline = True
                self.set_status("Server not reachable, retrying…" if self.offline
                                else "Auto-refresh on · updated " + datetime.now().strftime("%H:%M:%S"))
        except Exception:
            pass
        self._timer = self.after(delay, self._tick)

    def set_status(self, text):
        self.status_lbl.config(text=text)

    def note_pending(self, pending):
        """Badge on the Appointments button and a banner when a customer books something new."""
        ids = {a["id"] for a in pending}
        new = [a for a in pending if self.seen_pending is not None and a["id"] not in self.seen_pending]
        self.seen_pending = ids
        btn = self.nav.get(Appointments)
        if btn is not None:
            btn.config(text="Appointments (%d pending)" % len(ids) if ids else "Appointments")
        if new:
            a = new[-1]
            self.alert_lbl.config(text="  🔔 New booking request: %s (%s) · %s on %s %s  [click to dismiss]" % (
                a["pet_name"], a["customer_name"], a["service_name"], a["appt_date"], t12(a["appt_time"])), bg=AMBER)
            self.alert_lbl.pack(fill="x", before=self.body, pady=(0, 8))
            self.alert_lbl.bind("<Button-1>", lambda e: self.alert_lbl.pack_forget())
            try:
                self.bell()
            except Exception:
                pass

    def reminders(self):
        try:
            r = self.api.post("/reminders/send")
        except ApiError as e:
            return messagebox.showerror("PawPet", str(e), parent=self)
        messagebox.showinfo("PawPet", "Reminders sent: %d" % r["sent"], parent=self)

    def logout(self):
        self._stop_timer()
        self.current = None
        self.api.logout()
        self.login_view()


if __name__ == "__main__":
    App().mainloop()
