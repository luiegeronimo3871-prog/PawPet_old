"""PawPet desktop - the pages (Dashboard, Appointments, Customers, Inventory, Batches, Vets, Services, Sales).

Every page has:  build() -> a Flet control,  async refresh(quiet=False)  and a few async button handlers.
Network calls always go through `self.call(...)`, which runs the blocking HTTP request in a worker thread so the
window never freezes."""
from datetime import date, timedelta

import flet as ft

from api_client import ApiError
from ui import (AMBER, BLUE, DAYS, GREEN, LINE, MUTED, PANEL, RED, STATUS_COLOR, TEXT, Table, card, danger, days_until,
                dropdown, field, label, peso, plain, primary, stat_card, t12, today, valid_date)

STATUSES = ["All statuses", "pending", "confirmed", "completed", "cancelled", "no_show"]


def nice(status):
    return status.replace("_", " ")


class Page:
    title = ""
    icon = ft.Icons.CIRCLE
    auto = False            # True = refreshed automatically every few seconds
    admin_only = False

    def __init__(self, app):
        self.app = app
        self.api = app.api
        self.root = self.build()

    # -- to override
    def build(self):
        return ft.Column([])

    async def refresh(self, quiet=False):
        pass

    # -- helpers
    @property
    def page(self):
        return self.app.page

    async def call(self, fn, *a, **k):
        return await self.app.call(fn, *a, **k)

    def act(self, fn):
        """Wrap an async button handler: API/validation problems become a message instead of a crash."""
        async def handler(e=None):
            try:
                await fn()
            except ApiError as ex:
                await self.app.fail(ex)
            except ValueError as ex:
                await self.app.info("PawPet", str(ex))
        return handler

    def table(self, headings, weights=None):
        return Table(headings, weights).attach(self.page)

    def toolbar(self, *left, right=()):
        return ft.Row([*left, ft.Container(expand=True), *right], spacing=8,
                      vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def buttons(self, *items):
        return ft.Row(list(items), spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)


# Dashboard
class Dashboard(Page):
    title = "Dashboard"
    icon = ft.Icons.DASHBOARD
    auto = True

    def build(self):
        self.cards = {}
        row = []
        for key, title in [("a", "APPOINTMENTS TODAY"), ("p", "PENDING REQUESTS"), ("s", "SALES TODAY"),
                           ("m", "SALES (30 DAYS)"), ("e", "EXPIRED / EXPIRING")]:
            box, val, sub = stat_card(title)
            self.cards[key] = (val, sub)
            row.append(box)
        self.pend = self.table(["Date", "Time", "Pet", "Owner", "Service", "Vet"], [2, 2, 2, 3, 3, 3])
        self.appts = self.table(["Time", "Pet", "Owner", "Service", "Vet", "Status"], [2, 2, 3, 3, 3, 2])
        self.exp = self.table(["Product", "Batch", "Qty", "Expiry", "Status"], [4, 2, 1, 3, 2])
        self.low = self.table(["Product", "Usable stock"], [3, 2])
        self.top = self.table(["Item", "Qty", "Amount"], [4, 1, 3])
        self.pend_rows = {}
        pend_head = self.toolbar(label("Booking requests waiting for confirmation (all dates)", 14, TEXT, True),
                                 right=[primary("Confirm", self.act(lambda: self.decide("confirmed"))),
                                        danger("Decline", self.act(lambda: self.decide("cancelled")))])
        left = ft.Column([
            card(ft.Column([pend_head, ft.Container(self.pend.root, height=190)], spacing=8)),
            card(ft.Column([label("Today's appointments", 14, TEXT, True), ft.Container(self.appts.root, height=190)],
                           spacing=8)),
        ], expand=3, spacing=12)
        right = ft.Column([
            card(ft.Column([label("Medicine expiry alerts", 14, TEXT, True), ft.Container(self.exp.root, height=150)],
                           spacing=8)),
            card(ft.Column([label("Low stock", 14, TEXT, True), ft.Container(self.low.root, height=130)], spacing=8)),
            card(ft.Column([label("Top sellers", 14, TEXT, True), ft.Container(self.top.root, height=130)], spacing=8)),
        ], expand=2, spacing=12)
        return ft.Column([ft.Row(row, spacing=12),
                          ft.Row([left, right], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START)],
                         spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)

    async def decide(self, status):
        aid = self.pend.selected
        if aid is None:
            return await self.app.info("PawPet", "Select a booking request first.")
        a = self.pend_rows.get(aid, {})
        if status == "cancelled" and not await self.app.confirm(
                "Decline the booking of %s (%s)?" % (a.get("pet_name", "?"), a.get("service_name", "?"))):
            return
        await self.call(self.api.post, "/appointments/%d/status" % aid, {"status": status})
        await self.refresh()

    async def refresh(self, quiet=False):
        try:
            d = await self.call(self.api.get, "/dashboard")
            ap = await self.call(self.api.get, "/appointments", date=today())
        except ApiError as e:
            return await self.app.fail(e, quiet)
        pend = d.get("pending_list", [])
        self.app.note_pending(pend)
        val = self.cards
        val["a"][0].value, val["a"][1].value = str(d["appointments_today"]), "booked for today"
        val["p"][0].value, val["p"][1].value = str(d["pending"]), "need your confirmation"
        val["s"][0].value, val["s"][1].value = peso(d["sales_today"]), "products and services"
        val["m"][0].value, val["m"][1].value = peso(d["sales_30"]), "all recorded sales"
        exp = d.get("expiring", [])
        n_exp = d.get("expired_count", 0)
        val["e"][0].value = "%d / %d" % (n_exp, len(exp) - n_exp)
        val["e"][1].value = "%d expired, %d expiring soon" % (n_exp, len(exp) - n_exp)
        self.pend_rows = {a["id"]: a for a in pend}
        self.pend.set([(a["id"], [a["appt_date"], t12(a["appt_time"]), a["pet_name"], a["customer_name"],
                                  a["service_name"], a["vet_name"]], AMBER) for a in pend])
        self.appts.set([(a["id"], [t12(a["appt_time"]), a["pet_name"], a["customer_name"], a["service_name"],
                                   a["vet_name"], nice(a["status"])], STATUS_COLOR.get(a["status"])) for a in ap])
        self.exp.set([(b["id"], [b["product_name"], b["batch_no"] or "-", str(b["qty"]), b["expiry_date"],
                                 "EXPIRED" if b["status"] == "expired" else "in %d d" % b["days_left"]],
                       RED if b["status"] == "expired" else AMBER) for b in exp])
        self.low.set([(p["id"], [p["name"], "OUT" if p["stock"] == 0 else str(p["stock"])],
                       RED if p["stock"] == 0 else AMBER) for p in d["low_stock"]])
        self.top.set([(i, [t["item_name"], str(t["qty"]), peso(t["amount"])], None)
                      for i, t in enumerate(d["top_items"])])
        self.page.update()


# Appointments
class Appointments(Page):
    title = "Appointments"
    icon = ft.Icons.EVENT
    auto = True

    def build(self):
        self.date = field("Date (blank = all)", "", width=170, on_submit=self.act(self.refresh))
        self.status = dropdown("Status", STATUSES, "All statuses", width=170, on_select=self.act(self.refresh))
        self.tree = self.table(["Date", "Time", "Pet", "Owner", "Service", "Vet", "Status"], [2, 2, 2, 3, 3, 3, 2])
        self.rows = {}
        bar = self.toolbar(
            ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, on_click=self.act(lambda: self.shift(-1)), tooltip="Previous day"),
            self.date,
            ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, on_click=self.act(lambda: self.shift(1)), tooltip="Next day"),
            plain("Today", self.act(self.go_today)), plain("All dates", self.act(self.all_dates)), self.status,
            right=[primary("New appointment", self.act(self.new), ft.Icons.ADD)])
        acts = self.buttons(primary("Confirm", self.act(self.confirm)), primary("Complete visit", self.act(self.complete)),
                            plain("Schedule follow-up", self.act(self.followup)), plain("No-show", self.act(self.no_show)),
                            danger("Cancel", self.act(self.cancel)), plain("Details", self.act(self.details)))
        return ft.Column([bar, ft.Container(self.tree.root, expand=True), acts], expand=True, spacing=10)

    async def shift(self, n):
        try:
            y, m, d = [int(x) for x in self.date.value.split("-")]
            self.date.value = (date(y, m, d) + timedelta(days=n)).strftime("%Y-%m-%d")
        except Exception:
            self.date.value = today()
        await self.refresh()

    async def go_today(self):
        self.date.value = today()
        await self.refresh()

    async def all_dates(self):
        self.date.value = ""
        await self.refresh()

    async def refresh(self, quiet=False):
        d = (self.date.value or "").strip()
        if d and not valid_date(d):
            if quiet:
                return
            return await self.app.info("PawPet", "Date must look like 2026-10-25.")
        st = self.status.value or "All statuses"
        try:
            rows = await self.call(self.api.get, "/appointments", date=d, status="" if st == "All statuses" else st)
        except ApiError as e:
            return await self.app.fail(e, quiet)
        self.rows = {a["id"]: a for a in rows}
        self.tree.set([(a["id"], [a["appt_date"], t12(a["appt_time"]), a["pet_name"], a["customer_name"],
                                  a["service_name"] + (" (follow-up)" if a["followup_of"] else ""), a["vet_name"],
                                  nice(a["status"])], STATUS_COLOR.get(a["status"])) for a in rows])

    async def pick(self, allowed=None, need=""):
        aid = self.tree.selected
        if aid is None or aid not in self.rows:
            await self.app.info("PawPet", "Select an appointment first.")
            return None
        a = self.rows[aid]
        if allowed and a["status"] not in allowed:
            await self.app.info("PawPet", need or "That action is not available for this status.")
            return None
        return a

    async def _set(self, a, st):
        await self.call(self.api.post, "/appointments/%d/status" % a["id"], {"status": st})
        await self.refresh()

    async def confirm(self):
        a = await self.pick(("pending",), "Only pending appointments can be confirmed.")
        if a:
            await self._set(a, "confirmed")

    async def no_show(self):
        a = await self.pick(("confirmed",), "Only confirmed appointments can be marked no-show.")
        if a:
            await self._set(a, "no_show")

    async def cancel(self):
        a = await self.pick(("pending", "confirmed"), "Only pending or confirmed appointments can be cancelled.")
        if a and await self.app.confirm("Cancel %s's appointment?" % a["pet_name"]):
            await self._set(a, "cancelled")

    async def details(self):
        a = await self.pick()
        if not a:
            return
        await self.app.info("Appointment #%d" % a["id"],
                            "Pet: %s (%s %s)\nOwner: %s  %s\nService: %s - %s\nVet: %s\nWhen: %s %s\nStatus: %s\n\n"
                            "Pet notes: %s\nVisit notes: %s" % (
                                a["pet_name"], a["species"], a["breed"] or "", a["customer_name"],
                                a["customer_phone"] or "", a["service_name"], peso(a["service_price"]), a["vet_name"],
                                a["appt_date"], t12(a["appt_time"]), nice(a["status"]), a["pet_notes"] or "-",
                                a["notes"] or "-"))

    async def complete(self):
        a = await self.pick(("confirmed",), "Confirm the appointment before completing it.")
        if not a:
            return
        products = [p for p in await self.call(self.api.get, "/products") if p["stock"] > 0]
        names = [("", "(none)")] + [(p["id"], "%s (%d left)" % (p["name"], p["stock"])) for p in products]

        async def save(v):
            items = []
            for k in ("p1", "p2"):
                if v[k]:
                    try:
                        qty = int(v[k + "q"] or 1)
                    except ValueError:
                        raise ValueError("Quantity must be a whole number.")
                    if qty < 1:
                        raise ValueError("Quantity must be at least 1.")
                    items.append({"product_id": int(v[k]), "qty": qty})
            r = await self.call(self.api.post, "/appointments/%d/complete" % a["id"],
                                {"notes": v["notes"] or None, "products": items})
            await self.refresh()
            self.app.toast("Visit completed. Total: %s" % peso(r["total"]))
        await self.app.form("Complete visit - %s" % a["pet_name"], [
            ("notes", "Visit notes", "text", "", None),
            ("p1", "Product 1", "combo", "", names), ("p1q", "Qty", "entry", "1", None),
            ("p2", "Product 2", "combo", "", names), ("p2q", "Qty", "entry", "1", None)],
            save, "Complete & record sale")

    async def followup(self):
        a = await self.pick(("completed",), "Follow-ups are scheduled after a visit is completed.")
        if not a:
            return

        async def book(d, t, n):
            await self.call(self.api.post, "/appointments/%d/followup" % a["id"],
                            {"appt_date": d, "appt_time": t, "notes": n or "Follow-up visit"})
            await self.refresh()
        await self.slot_dialog("Schedule follow-up - %s" % a["pet_name"], a["vet_id"], a["service_id"], book)

    # ---- dialog with a date box + free-time dropdown (used by follow-up)
    async def slot_dialog(self, title, vet_id, service_id, on_book):
        d = field("Date (YYYY-MM-DD)", (date.today() + timedelta(days=1)).strftime("%Y-%m-%d"), width=200)
        t = dropdown("Time", [], None, width=200)
        n = field("Notes", "", width=420)
        err = label("", 12, RED)

        async def show(e=None):
            try:
                if not valid_date(d.value.strip()):
                    raise ValueError("Date must look like 2026-10-25.")
                slots = await self.call(self.api.get, "/availability", vet_id=vet_id, service_id=service_id,
                                        date=d.value.strip())
            except (ApiError, ValueError) as ex:
                err.value = str(ex)
                self.page.update()
                return
            free = [s["time"] for s in slots if s["available"]]
            t.options = [ft.DropdownOption(key=x, text=t12(x)) for x in free]
            t.value = free[0] if free else None
            err.value = "" if free else "No free times for this vet on that date."
            self.page.update()

        async def save():
            if not t.value:
                raise ValueError("Press 'Show times' and pick a time.")
            await on_book(d.value.strip(), t.value, n.value)
        await self.app.custom_form(title, [ft.Row([d, plain("Show times", show)], spacing=8), t, n, err], save, "Book")

    async def new(self):
        customers = [c for c in await self.call(self.api.get, "/customers") if c["active"]]
        pets = await self.call(self.api.get, "/pets", all=1)
        services = await self.call(self.api.get, "/services")
        vets = [v for v in await self.call(self.api.get, "/vets") if v["active"]]
        if not customers or not services or not vets:
            return await self.app.info("PawPet", "You need at least one customer, one service and one active vet first.")
        cust = dropdown("Customer", [(c["id"], c["full_name"]) for c in customers], None, width=420)
        pet = dropdown("Pet", [], None, width=420)
        svc = dropdown("Service", [(s["id"], "%s - %s" % (s["name"], peso(s["price"]))) for s in services],
                       services[0]["id"], width=420)
        vet = dropdown("Veterinarian", [(v["id"], v["name"]) for v in vets], vets[0]["id"], width=420)
        d = field("Date (YYYY-MM-DD)", (date.today() + timedelta(days=1)).strftime("%Y-%m-%d"), width=200)
        t = dropdown("Time", [], None, width=200)
        n = field("Notes", "", width=420)
        err = label("", 12, RED)

        def on_customer(e=None):
            mine = [p for p in pets if str(p["owner_id"]) == str(cust.value)]
            pet.options = [ft.DropdownOption(key=str(p["id"]), text="%s (%s)" % (p["name"], p["species"])) for p in mine]
            pet.value = str(mine[0]["id"]) if mine else None
            err.value = "" if mine else "This customer has no pets yet."
            self.page.update()
        cust.on_select = on_customer

        async def show(e=None):
            try:
                if not valid_date(d.value.strip()):
                    raise ValueError("Date must look like 2026-10-25.")
                slots = await self.call(self.api.get, "/availability", vet_id=vet.value, service_id=svc.value,
                                        date=d.value.strip())
            except (ApiError, ValueError) as ex:
                err.value = str(ex)
                self.page.update()
                return
            free = [s["time"] for s in slots if s["available"]]
            t.options = [ft.DropdownOption(key=x, text=t12(x)) for x in free]
            t.value = free[0] if free else None
            err.value = "" if free else "No free times for this vet on that date."
            self.page.update()

        async def save():
            if not cust.value or not pet.value:
                raise ValueError("Choose a customer who has a pet.")
            if not t.value:
                raise ValueError("Press 'Show times' and pick a time.")
            await self.call(self.api.post, "/appointments", {
                "customer_id": int(cust.value), "pet_id": int(pet.value), "service_id": int(svc.value),
                "vet_id": int(vet.value), "appt_date": d.value.strip(), "appt_time": t.value, "notes": n.value})
            await self.refresh()
        await self.app.custom_form("New appointment (auto-confirmed)", [
            cust, pet, svc, vet, ft.Row([d, plain("Show times", show)], spacing=8), t, n, err], save, "Book")


# Customers
class Customers(Page):
    title = "Customers"
    icon = ft.Icons.PEOPLE

    def build(self):
        self.q = field("Search name, username or phone", "", width=340, on_submit=self.act(self.refresh))
        self.tree = self.table(["Name", "Username", "Phone", "Pets", "Visits", "Status"], [4, 3, 3, 1, 1, 2])
        bar = self.toolbar(self.q, plain("Search", self.act(self.refresh), ft.Icons.SEARCH),
                           right=[primary("Add customer", self.act(self.add), ft.Icons.PERSON_ADD)])
        acts = self.buttons(plain("View pets & history", self.act(self.view)),
                            plain("Enable / disable account", self.act(self.toggle)),
                            plain("Reset password", self.act(self.reset_pw)))
        return ft.Column([bar, ft.Container(self.tree.root, expand=True), acts], expand=True, spacing=10)

    async def refresh(self, quiet=False):
        try:
            rows = await self.call(self.api.get, "/customers", q=(self.q.value or "").strip())
        except ApiError as e:
            return await self.app.fail(e, quiet)
        self.names = {c["id"]: c["full_name"] for c in rows}
        self.tree.set([(c["id"], [c["full_name"], c["username"], c["phone"] or "-", str(c["pet_count"]),
                                  str(c["appt_count"]), "Active" if c["active"] else "Disabled"],
                        None if c["active"] else RED) for c in rows])

    async def add(self):
        made = {}

        async def save(v):
            if not v["full_name"].strip() or not v["username"].strip():
                raise ValueError("Name and username are required.")
            made["r"] = await self.call(self.api.post, "/customers", v)
            made["u"] = v["username"].strip()
            await self.refresh()
        await self.app.form("Add customer", [
            ("full_name", "Full name", "entry", "", None), ("username", "Username", "entry", "", None),
            ("phone", "Phone", "entry", "", None), ("email", "Email", "entry", "", None),
            ("password", "Password (blank = make a temporary one)", "entry", "", None)], save)
        if made.get("r", {}).get("temp_password"):          # shown after the form has closed
            await self.app.info("PawPet", "Customer created.\n\nUsername: %s\nTemporary password: %s\n\n"
                                "Give this to the customer. They must choose a new password at first sign-in."
                                % (made["u"], made["r"]["temp_password"]))

    def _need(self):
        cid = self.tree.selected
        return cid

    async def reset_pw(self):
        cid = self._need()
        if cid is None:
            return await self.app.info("PawPet", "Select a customer first.")
        name = self.names.get(cid, "this customer")
        if not await self.app.confirm("Reset the password of %s?\nThey will be signed out everywhere." % name):
            return
        r = await self.call(self.api.post, "/users/%d/reset-password" % cid)
        await self.app.info("PawPet", "Username: %s\nTemporary password: %s\n\nGive this to the customer. "
                            "They must choose a new password at first sign-in." % (r["username"], r["temp_password"]))

    async def view(self):
        cid = self._need()
        if cid is None:
            return await self.app.info("PawPet", "Select a customer first.")
        r = await self.call(self.api.get, "/customers/%d" % cid)
        pets = "\n".join("- %s: %s %s, %s%s" % (p["name"], p["species"], p["breed"] or "",
                                              ("%s yr" % p["age"]) if p["age"] else "age ?",
                                              (" [%s]" % p["notes"]) if p["notes"] else "") for p in r["pets"]) or "No pets"
        hist = "\n".join("- %s %s  %s / %s  [%s]" % (a["appt_date"], t12(a["appt_time"]), a["pet_name"],
                                                    a["service_name"], nice(a["status"]))
                         for a in r["appointments"][:10]) or "None"
        c = r["customer"]
        await self.app.info(c["full_name"], "%s  %s\n\nPETS\n%s\n\nRECENT APPOINTMENTS\n%s" % (
            c["email"] or "", c["phone"] or "", pets, hist))

    async def toggle(self):
        cid = self._need()
        if cid is None:
            return await self.app.info("PawPet", "Select a customer first.")
        await self.call(self.api.post, "/customers/%d/toggle" % cid)
        await self.refresh()


# Inventory
class Inventory(Page):
    title = "Inventory"
    icon = ft.Icons.INVENTORY_2
    auto = True

    def build(self):
        self.q = field("Search products", "", width=300, on_submit=self.act(self.refresh))
        self.tree = self.table(["Product", "Category", "Price", "Usable stock", "Expired", "Next expiry",
                                "Reorder at", "Status"], [4, 2, 2, 2, 1, 2, 2, 3])
        self.rows = {}
        bar = self.toolbar(self.q, plain("Search", self.act(self.refresh), ft.Icons.SEARCH),
                           right=[primary("Add product", self.act(lambda: self.form(None)), ft.Icons.ADD)])
        acts = self.buttons(plain("Receive new batch", self.act(self.restock)), plain("Walk-in sale", self.act(self.sell)),
                            plain("Edit", self.act(self.edit)), danger("Delete (admin)", self.act(self.delete)),
                            label("Expired stock is not counted and cannot be sold.", 11, MUTED))
        return ft.Column([bar, ft.Container(self.tree.root, expand=True), acts], expand=True, spacing=10)

    async def refresh(self, quiet=False):
        try:
            rows = await self.call(self.api.get, "/products", q=(self.q.value or "").strip())
        except ApiError as e:
            return await self.app.fail(e, quiet)
        self.rows = {p["id"]: p for p in rows}
        out = []
        for p in rows:
            left = days_until(p.get("next_expiry"))
            if p.get("expired_qty", 0) > 0:
                color, text = RED, "Has expired stock"
            elif p["stock"] == 0:
                color, text = RED, "Out of stock"
            elif left is not None and left <= 30:
                color, text = AMBER, "Expiring soon"
            elif p["stock"] <= p["reorder_level"]:
                color, text = AMBER, "Low stock"
            else:
                color, text = None, "In stock"
            out.append((p["id"], [p["name"], p["category"], peso(p["price"]), str(p["stock"]),
                                  str(p.get("expired_qty", 0) or "-"), p.get("next_expiry") or "-",
                                  str(p["reorder_level"]), text], color))
        self.tree.set(out)

    async def pick(self):
        pid = self.tree.selected
        if pid is None or pid not in self.rows:
            await self.app.info("PawPet", "Select a product first.")
            return None
        return self.rows[pid]

    async def restock(self):
        p = await self.pick()
        if not p:
            return

        async def save(v):
            try:
                qty = int(v["qty"])
            except ValueError:
                raise ValueError("Units must be a whole number.")
            if qty < 1:
                raise ValueError("Units must be at least 1.")
            exp = v["expiry_date"].strip()
            if exp and not valid_date(exp):
                raise ValueError("Expiry date must look like 2027-01-31.")
            await self.call(self.api.post, "/products/%d/restock" % p["id"],
                            {"qty": qty, "batch_no": v["batch_no"].strip(), "expiry_date": exp})
            await self.refresh()
        await self.app.form("Receive new batch: %s" % p["name"], [
            ("qty", "Units received", "entry", "10", None), ("batch_no", "Batch / lot no.", "entry", "", None),
            ("expiry_date", "Expiry date (YYYY-MM-DD)", "entry", "", None)], save, "Add batch")

    async def sell(self):
        p = await self.pick()
        if not p:
            return

        async def save(v):
            try:
                n = int(v["n"])
            except ValueError:
                raise ValueError("Quantity must be a whole number.")
            r = await self.call(self.api.post, "/products/%d/sell" % p["id"], {"qty": n})
            await self.refresh()
            self.app.toast("Sold. Amount: %s" % peso(r["amount"]))
        await self.app.form("Sell %s" % p["name"], [("n", "Quantity", "entry", "1", None)], save, "Sell")

    async def edit(self):
        p = await self.pick()
        if p:
            await self.form(p)

    async def delete(self):
        p = await self.pick()
        if p and await self.app.confirm("Delete %s?" % p["name"]):
            await self.call(self.api.delete, "/products/%d" % p["id"])
            await self.refresh()

    async def form(self, p):
        async def save(v):
            try:
                body = {"name": v["name"], "category": v["category"] or "Other", "price": float(v["price"]),
                        "stock": int(v["stock"]), "reorder_level": int(v["reorder_level"] or 5)}
            except ValueError:
                raise ValueError("Price must be a number; stock and reorder level must be whole numbers.")
            if p:
                await self.call(self.api.put, "/products/%d" % p["id"], body)
            else:
                exp = v["expiry_date"].strip()
                if exp and not valid_date(exp):
                    raise ValueError("Expiry date must look like 2027-01-31.")
                body["batch_no"] = v["batch_no"].strip()
                body["expiry_date"] = exp
                await self.call(self.api.post, "/products", body)
            await self.refresh()
        q = p or {}
        fields = [("name", "Name", "entry", q.get("name", ""), None),
                  ("category", "Category", "entry", q.get("category", "Food"), None),
                  ("price", "Price", "entry", q.get("price", ""), None),
                  ("stock", "Stock", "entry", q.get("stock", 0), None),
                  ("reorder_level", "Reorder level", "entry", q.get("reorder_level", 5), None)]
        if not p:
            fields += [("batch_no", "Batch / lot no. (optional)", "entry", "", None),
                       ("expiry_date", "Expiry date (YYYY-MM-DD, optional)", "entry", "", None)]
        await self.app.form("Edit product" if p else "Add product", fields, save)


# Batches & Expiry
class Batches(Page):
    title = "Batches & Expiry"
    icon = ft.Icons.WARNING_AMBER
    auto = True

    FILTERS = ["All batches", "Expired", "Expiring soon (30 days)", "OK"]

    def build(self):
        self.flt = dropdown("Show", self.FILTERS, "All batches", width=240, on_select=self.act(self.refresh))
        self.sum = label("", 12, MUTED)
        self.tree = self.table(["Product", "Batch / lot", "Qty left", "Expiry date", "When", "Status"], [4, 2, 1, 2, 2, 2])
        self.rows = {}
        bar = self.toolbar(self.flt, self.sum)
        acts = ft.Row([danger("Discard selected batch", self.act(self.discard)),
                       label("Discard removes what is left of the batch from stock (for example expired medicine thrown "
                             "away). New batches are added from the Inventory page.", 11, MUTED)],
                      spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        return ft.Column([bar, ft.Container(self.tree.root, expand=True), acts], expand=True, spacing=10)

    async def refresh(self, quiet=False):
        try:
            rows = await self.call(self.api.get, "/batches")
        except ApiError as e:
            return await self.app.fail(e, quiet)
        want = {"Expired": ("expired",), "Expiring soon (30 days)": ("expiring",),
                "OK": ("ok", "no_expiry")}.get(self.flt.value)
        n_exp = sum(1 for b in rows if b["status"] == "expired")
        n_soon = sum(1 for b in rows if b["status"] == "expiring")
        self.sum.value = "%d expired · %d expiring within 30 days · %d batches" % (n_exp, n_soon, len(rows))
        self.rows = {b["id"]: b for b in rows}
        out = []
        for b in rows:
            if want and b["status"] not in want:
                continue
            if b["status"] == "expired":
                when, text, color = "%d day(s) ago" % abs(b["days_left"]), "EXPIRED", RED
            elif b["status"] == "expiring":
                when, text, color = "in %d day(s)" % b["days_left"], "Expiring soon", AMBER
            elif b["status"] == "ok":
                when, text, color = "in %d day(s)" % b["days_left"], "OK", None
            else:
                when, text, color = "-", "No expiry", None
            out.append((b["id"], [b["product_name"], b["batch_no"] or "-", str(b["qty"]), b["expiry_date"] or "-",
                                  when, text], color))
        self.tree.set(out)

    async def discard(self):
        bid = self.tree.selected
        if bid is None or bid not in self.rows:
            return await self.app.info("PawPet", "Select a batch first.")
        b = self.rows[bid]
        if not await self.app.confirm("Discard %d unit(s) of %s (batch %s)?\nThey will be removed from stock."
                                      % (b["qty"], b["product_name"], b["batch_no"] or "-")):
            return
        await self.call(self.api.post, "/batches/%d/discard" % bid)
        await self.refresh()


# Veterinarians
class Vets(Page):
    title = "Veterinarians"
    icon = ft.Icons.MEDICAL_SERVICES

    def build(self):
        self.d = field("Availability on (YYYY-MM-DD)", today(), width=240, on_submit=self.act(self.refresh))
        self.tree = self.table(["Veterinarian", "Specialty", "Working days", "Hours", "Free slots", "Active"], [3, 3, 4, 3, 1, 1])
        self.tree.on_change = self.show
        self.detail = label("Select a vet to see free times.", 12, MUTED)
        self.vets, self.slots = {}, {}
        bar = self.toolbar(self.d, plain("Check", self.act(self.refresh)),
                           right=[primary("Add veterinarian", self.act(lambda: self.form(None)), ft.Icons.ADD)])
        acts = ft.Row([plain("Edit selected (admin)", self.act(self.edit))])
        return ft.Column([bar, ft.Container(self.tree.root, expand=True), card(self.detail), acts],
                         expand=True, spacing=10)

    async def refresh(self, quiet=False):
        d = (self.d.value or "").strip()
        if not valid_date(d):
            return await self.app.info("PawPet", "Date must look like 2026-10-25.")
        try:
            vets = await self.call(self.api.get, "/vets")
            slots = {}
            for v in vets:
                slots[v["id"]] = await self.call(self.api.get, "/availability", vet_id=v["id"], date=d)
        except ApiError as e:
            return await self.app.fail(e, quiet)
        self.vets, self.slots = {v["id"]: v for v in vets}, slots
        rows = []
        for v in vets:
            free = len([s for s in slots[v["id"]] if s["available"]])
            rows.append((v["id"], [v["name"], v["specialty"] or "", ", ".join(DAYS[int(x)] for x in v["work_days"].split(",")),
                                   "%s - %s" % (t12(v["start_time"]), t12(v["end_time"])),
                                   str(free) if slots[v["id"]] else "off", "Yes" if v["active"] else "No"], None))
        self.tree.set(rows)
        self.detail.value = "Select a vet to see free times."
        self.page.update()

    def show(self, vid):
        s = self.slots.get(vid, [])
        free = [t12(x["time"]) for x in s if x["available"]]
        busy = [t12(x["time"]) for x in s if not x["available"]]
        if not s:
            self.detail.value = "%s is not working on this date." % self.vets[vid]["name"]
        else:
            self.detail.value = "FREE: %s\nTAKEN: %s" % (", ".join(free) or "none", ", ".join(busy) or "none")

    async def edit(self):
        vid = self.tree.selected
        if vid is None or vid not in self.vets:
            return await self.app.info("PawPet", "Select a veterinarian first.")
        await self.form(self.vets[vid])

    async def form(self, v):
        async def save(x):
            picked = [s.strip().capitalize() for s in x["days"].split(",")]
            days = [str(i) for i, name in enumerate(DAYS) if name in picked]
            if not days:
                raise ValueError("Enter working days like: Mon,Tue,Wed")
            if x["end"] <= x["start"]:
                raise ValueError("End time must be after start time.")
            body = {"name": x["name"], "specialty": x["specialty"], "work_days": ",".join(days),
                    "start_time": x["start"], "end_time": x["end"]}
            if v:
                body["active"] = int(x["active"])
                await self.call(self.api.put, "/vets/%d" % v["id"], body)
            else:
                await self.call(self.api.post, "/vets", body)
            await self.refresh()
        fields = [("name", "Name", "entry", v["name"] if v else "", None),
                  ("specialty", "Specialty", "entry", (v["specialty"] or "") if v else "", None),
                  ("days", "Working days (Mon,Tue,..)", "entry",
                   ",".join(DAYS[int(i)] for i in v["work_days"].split(",")) if v else "Mon,Tue,Wed,Thu,Fri", None),
                  ("start", "Start (HH:MM)", "entry", v["start_time"] if v else "09:00", None),
                  ("end", "End (HH:MM)", "entry", v["end_time"] if v else "17:00", None)]
        if v:
            fields.append(("active", "Active", "check", v["active"], None))
        await self.app.form("Edit veterinarian" if v else "Add veterinarian", fields, save)


# Services (admin only)
class Services(Page):
    title = "Services"
    icon = ft.Icons.MISCELLANEOUS_SERVICES
    admin_only = True

    def build(self):
        self.tree = self.table(["Service", "Description", "Price", "Duration"], [3, 5, 2, 2])
        self.rows = {}
        bar = self.toolbar(plain("Edit selected", self.act(self.edit)),
                           right=[primary("Add service", self.act(lambda: self.form(None)), ft.Icons.ADD)])
        return ft.Column([bar, ft.Container(self.tree.root, expand=True)], expand=True, spacing=10)

    async def refresh(self, quiet=False):
        try:
            rows = await self.call(self.api.get, "/services")
        except ApiError as e:
            return await self.app.fail(e, quiet)
        self.rows = {s["id"]: s for s in rows}
        self.tree.set([(s["id"], [s["name"], s["description"] or "", peso(s["price"]), "%d min" % s["duration"]], None)
                       for s in rows])

    async def edit(self):
        sid = self.tree.selected
        if sid is None or sid not in self.rows:
            return await self.app.info("PawPet", "Select a service first.")
        await self.form(self.rows[sid])

    async def form(self, s):
        async def save(v):
            try:
                body = {"name": v["name"], "description": v["description"], "price": float(v["price"]),
                        "duration": int(v["duration"])}
            except ValueError:
                raise ValueError("Price must be a number and duration a whole number of minutes.")
            if s:
                await self.call(self.api.put, "/services/%d" % s["id"], body)
            else:
                await self.call(self.api.post, "/services", body)
            await self.refresh()
        q = s or {}
        await self.app.form("Edit service" if s else "Add service", [
            ("name", "Name", "entry", q.get("name", ""), None),
            ("description", "Description", "entry", q.get("description", ""), None),
            ("price", "Price", "entry", q.get("price", ""), None),
            ("duration", "Duration (min)", "entry", q.get("duration", 30), None)], save)


# Sales
class Sales(Page):
    title = "Sales"
    icon = ft.Icons.RECEIPT_LONG

    def build(self):
        self.days = dropdown("Period (days)", ["7", "30", "90"], "30", width=170, on_select=self.act(self.refresh))
        self.total = label("", 14, TEXT, True)
        self.tree = self.table(["Date", "Item", "Type", "Customer", "Qty", "Amount"], [3, 4, 2, 3, 1, 2])
        bar = self.toolbar(self.days, right=[self.total])
        return ft.Column([bar, ft.Container(self.tree.root, expand=True)], expand=True, spacing=10)

    async def refresh(self, quiet=False):
        try:
            rows = await self.call(self.api.get, "/sales", days=self.days.value or "30")
        except ApiError as e:
            return await self.app.fail(e, quiet)
        self.tree.set([(i, [s["created_at"][:16], s["item_name"], s["kind"], s["customer_name"] or "Walk-in",
                            str(s["qty"]), peso(s["amount"])], None) for i, s in enumerate(rows)])
        prod = sum(s["amount"] for s in rows if s["kind"] == "product")
        tot = sum(s["amount"] for s in rows)
        self.total.value = "Total %s   (products %s, services %s)" % (peso(tot), peso(prod), peso(tot - prod))
        self.page.update()


ALL_PAGES = [Dashboard, Appointments, Customers, Inventory, Batches, Vets, Services, Sales]
