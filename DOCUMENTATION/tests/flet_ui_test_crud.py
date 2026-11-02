"""Flet desktop UI test 1: every page and button, against a LIVE test server.
Start the server first:  set PAWPET_TEST_FIXED_PASSWORDS=1 & set PAWPET_DB=sqlite & py app.py   (then run this file)"""
from flet_harness import *
import flet_harness as H
from datetime import date, timedelta

async def login(page, user, pw):
    app = admin.App(page); await app.start()
    app.user.value, app.pw.value = user, pw
    await app.do_login(); await asyncio.sleep(0.3)
    return app

async def main():
    page = FakePage()
    app = await login(page, "admin", "admin123")
    P = lambda c: app.pages[c]
    api = app.api
    # ---- layout guard: a wrapping Row (Wrap) collapsed to nothing on real Flet 1.0.5 and showed grey boxes
    for cls, pg in app.pages.items():
        bad = [x for x in walk(pg.root) if isinstance(x, ft.Row) and x.wrap]
        check("no wrapping Row on " + cls.title, not bad)
    # ---- Appointments
    await app.goto(pages.Appointments); ap = P(pages.Appointments)
    pend = [a for a in ap.rows.values() if a["status"] == "pending"]
    check("have pending", len(pend) > 0)
    ap.tree.select(pend[0]["id"])
    await ap.act(ap.confirm)()
    await ap.refresh()
    check("confirmed", ap.rows[pend[0]["id"]]["status"] == "confirmed")
    # wrong status message
    ap.tree.select(pend[0]["id"])
    t = asyncio.ensure_future(ap.act(ap.confirm)()); d = await wait_dialog(page)
    check("only pending msg", "Only pending" in alltext(d)); await click(find_btn(d, "OK")); await t
    # complete visit
    prods = api.get("/products")
    p0 = [p for p in prods if p["stock"] > 2][0]
    ap.tree.select(pend[0]["id"])
    before = p0["stock"]
    await run_with_dialog(page, ap.act(ap.complete), fill={"Visit notes": "ok", "Product 1": str(p0["id"]), "Qty": "2"}, press="Complete & record sale")
    await ap.refresh()
    check("completed", ap.rows[pend[0]["id"]]["status"] == "completed")
    after = [p for p in api.get("/products") if p["id"] == p0["id"]][0]["stock"]
    check("stock reduced", after == before - 2, (before, after))
    # complete with bad qty -> error stays in dialog
    ap2 = [a for a in ap.rows.values() if a["status"] == "pending"]
    ap.tree.select(ap2[0]["id"]); await ap.act(ap.confirm)(); await ap.refresh()
    ap.tree.select(ap2[0]["id"])
    t = asyncio.ensure_future(ap.act(ap.complete)()); d = await wait_dialog(page)
    by_label(d, "Product 1").value = str(p0["id"]); by_label(d, "Qty").value = "0"
    await click(find_btn(d, "Complete & record sale")); await asyncio.sleep(0.1)
    check("qty error shown", "at least 1" in alltext(d), alltext(d))
    check("dialog still open", d.open)
    await click(find_btn(d, "Cancel")); await t
    # follow-up
    ap.tree.select(pend[0]["id"])
    tm = (date.today() + timedelta(days=3))
    async def pick_slot(d):
        by_label(d, "Date (YYYY-MM-DD)").value = tm.strftime("%Y-%m-%d")
        await click(find_btn(d, "Show times")); await asyncio.sleep(0.2)
        tdd = by_label(d, "Time"); check("slots offered", len(tdd.options) > 0, alltext(d))
        if tdd.options: tdd.value = tdd.options[0].key
    await run_with_dialog(page, ap.act(ap.followup), press="Book", then=pick_slot)
    await ap.refresh()
    check("follow-up row", any(a["followup_of"] for a in ap.rows.values()))
    # new appointment
    custs = api.get("/customers"); pets = api.get("/pets", all=1)
    c = [c for c in custs if any(p["owner_id"] == c["id"] for p in pets)][0]
    async def fill_new(d):
        by_label(d, "Customer").value = str(c["id"])
        by_label(d, "Customer").on_select(None)
        by_label(d, "Date (YYYY-MM-DD)").value = (date.today() + timedelta(days=4)).strftime("%Y-%m-%d")
        await click(find_btn(d, "Show times")); await asyncio.sleep(0.2)
        t = by_label(d, "Time"); check("new slots", len(t.options) > 0, alltext(d))
        if t.options: t.value = t.options[0].key
    n0 = len(ap.rows)
    await run_with_dialog(page, ap.act(ap.new), press="Book", then=fill_new)
    await ap.refresh(); check("new appt added", len(ap.rows) == n0 + 1, (n0, len(ap.rows)))
    # filters
    ap.status.value = "completed"; await ap.refresh(); check("status filter", all(a["status"] == "completed" for a in ap.rows.values()) and ap.rows)
    ap.status.value = "All statuses"; ap.date.value = "bad"; t = asyncio.ensure_future(ap.refresh())
    d = await wait_dialog(page); check("bad date msg", "must look like" in alltext(d)); await click(find_btn(d, "OK")); await t
    await ap.go_today(); check("today", ap.date.value == date.today().strftime("%Y-%m-%d"))
    await ap.shift(1); await ap.all_dates()
    # cancel flow
    pend = [a for a in ap.rows.values() if a["status"] in ("pending", "confirmed")]
    if pend:
        ap.tree.select(pend[0]["id"]); t = asyncio.ensure_future(ap.act(ap.cancel)()); d = await wait_dialog(page)
        await click(find_btn(d, "Yes")); await t; await ap.refresh()
        check("cancelled", ap.rows[pend[0]["id"]]["status"] == "cancelled")
    # details
    ap.tree.select(list(ap.rows)[0]); t = asyncio.ensure_future(ap.act(ap.details)()); d = await wait_dialog(page)
    check("details", "Owner:" in alltext(d)); await click(find_btn(d, "OK")); await t

    # ---- Customers
    await app.goto(pages.Customers); cu = P(pages.Customers)
    n0 = len(cu.tree.data)
    t = asyncio.ensure_future(cu.act(cu.add)()); d = await wait_dialog(page)
    by_label(d, "Full name").value = "Flet Tester"; by_label(d, "Username").value = "flettest"; await click(find_btn(d, "Save"))
    await asyncio.sleep(0.5); d = await wait_dialog(page); check("temp pw shown", "Temporary password" in alltext(d)); await click(find_btn(d, "OK")); await t
    check("customer added", len(cu.tree.data) == n0 + 1)
    new = [r for r in cu.tree.data if r[1][1] == "flettest"][0][0]
    cu.tree.select(new)
    t = asyncio.ensure_future(cu.act(cu.reset_pw)()); d = await wait_dialog(page); await click(find_btn(d, "Yes"))
    d = await wait_dialog(page); check("reset pw shown", "Temporary password" in alltext(d)); await click(find_btn(d, "OK")); await t
    t = asyncio.ensure_future(cu.act(cu.view)()); d = await wait_dialog(page); check("view", "PETS" in alltext(d)); await click(find_btn(d, "OK")); await t
    await cu.act(cu.toggle)(); check("disabled", dict((r[0], r[1][5]) for r in cu.tree.data)[new] == "Disabled")
    cu.q.value = "flet"; await cu.refresh(); check("search", len(cu.tree.data) == 1)
    # validation in add dialog
    t = asyncio.ensure_future(cu.act(cu.add)()); d = await wait_dialog(page)
    await click(find_btn(d, "Save")); await asyncio.sleep(0.05); check("req msg", "required" in alltext(d)); await click(find_btn(d, "Cancel")); await t

    # ---- Inventory
    await app.goto(pages.Inventory); inv = P(pages.Inventory); n0 = len(inv.tree.data)
    await run_with_dialog(page, inv.act(lambda: inv.form(None)), fill={"Name": "FletFood", "Category": "Food", "Price": "99.5", "Stock": "5", "Reorder level": "2", "Batch / lot no. (optional)": "B1", "Expiry date (YYYY-MM-DD, optional)": "2027-12-31"}, press="Save")
    check("product added", len(inv.tree.data) == n0 + 1)
    pid = [r for r in inv.tree.data if r[1][0] == "FletFood"][0][0]
    inv.tree.select(pid)
    await run_with_dialog(page, inv.act(inv.restock), fill={"Units received": "7", "Batch / lot no.": "B2", "Expiry date (YYYY-MM-DD)": "2028-01-01"}, press="Add batch")
    check("restocked 12", [r for r in inv.tree.data if r[0] == pid][0][1][3] == "12", [r for r in inv.tree.data if r[0] == pid])
    await run_with_dialog(page, inv.act(inv.sell), fill={"Quantity": "2"}, press="Sell")
    check("sold 10", [r for r in inv.tree.data if r[0] == pid][0][1][3] == "10")
    await run_with_dialog(page, inv.act(inv.edit), fill={"Price": "120"}, press="Save")
    check("edited", "120.00" in [r for r in inv.tree.data if r[0] == pid][0][1][2])
    t = asyncio.ensure_future(inv.act(inv.sell)()); d = await wait_dialog(page); by_label(d, "Quantity").value = "x"; await click(find_btn(d, "Sell")); await asyncio.sleep(0.05)
    check("qty err", "whole number" in alltext(d)); await click(find_btn(d, "Cancel")); await t
    # ---- Batches
    await app.goto(pages.Batches); ba = P(pages.Batches)
    for f in pages.Batches.FILTERS:
        ba.flt.value = f; await ba.refresh()
    ba.flt.value = "All batches"; await ba.refresh()
    bid = [b for b in ba.rows.values() if b["product_name"] == "FletFood" and b["batch_no"] == "B2"][0]["id"]
    ba.tree.select(bid); t = asyncio.ensure_future(ba.act(ba.discard)()); d = await wait_dialog(page); await click(find_btn(d, "Yes")); await t
    await app.goto(pages.Inventory); check("discard reduced stock", [r for r in inv.tree.data if r[0] == pid][0][1][3] == "3", [r for r in inv.tree.data if r[0] == pid])
    inv.tree.select(pid); t = asyncio.ensure_future(inv.act(inv.delete)()); d = await wait_dialog(page); await click(find_btn(d, "Yes")); await t
    check("deleted", pid not in inv.rows)
    # ---- Vets
    await app.goto(pages.Vets); ve = P(pages.Vets); n0 = len(ve.tree.data)
    await run_with_dialog(page, ve.act(lambda: ve.form(None)), fill={"Name": "Dr Flet", "Working days (Mon,Tue,..)": "Mon,Wed", "Start (HH:MM)": "09:00", "End (HH:MM)": "12:00"}, press="Save")
    check("vet added", len(ve.tree.data) == n0 + 1)
    vid = [r for r in ve.tree.data if r[1][0] == "Dr Flet"][0][0]; ve.tree.select(vid)
    check("vet days", "Mon, Wed" in [r for r in ve.tree.data if r[0] == vid][0][1][2])
    ve.d.value = (date.today() + timedelta(days=(7 - date.today().weekday()) % 7 or 7)).strftime("%Y-%m-%d"); await ve.refresh(); ve.tree.select(vid); check("vet detail", "FREE" in ve.detail.value, ve.detail.value)
    await run_with_dialog(page, ve.act(ve.edit), fill={"Specialty": "Birds"}, press="Save")
    # ---- Services
    await app.goto(pages.Services); se = P(pages.Services); n0 = len(se.tree.data)
    await run_with_dialog(page, se.act(lambda: se.form(None)), fill={"Name": "FletSvc", "Price": "250", "Duration (min)": "30"}, press="Save")
    check("service added", len(se.tree.data) == n0 + 1)
    sid = [r for r in se.tree.data if r[1][0] == "FletSvc"][0][0]; se.tree.select(sid)
    await run_with_dialog(page, se.act(se.edit), fill={"Price": "300"}, press="Save")
    check("service edited", "300.00" in [r for r in se.tree.data if r[0] == sid][0][1][2])
    # ---- Sales
    await app.goto(pages.Sales); sa = P(pages.Sales); check("sales total", "Total PHP" in sa.total.value)
    sa.days.value = "7"; await sa.refresh()
    # ---- reminders
    t = asyncio.ensure_future(app.reminders()); d = await wait_dialog(page); check("reminders", "Reminders sent" in alltext(d)); await click(find_btn(d, "OK")); await t
    # ---- change password
    await run_with_dialog(page, app.change_pw, fill={"Current password": "admin123", "New password (8+ chars, letters + numbers)": "Admin12345", "Repeat new password": "Nope"}, press="Change password") if False else None
    t = asyncio.ensure_future(app.change_pw()); d = await wait_dialog(page)
    by_label(d, "Current password").value = "admin123"; by_label(d, "New password (8+ chars, letters + numbers)").value = "Admin12345"; by_label(d, "Repeat new password").value = "Nope"
    await click(find_btn(d, "Change password")); await asyncio.sleep(0.05); check("mismatch", "do not match" in alltext(d))
    by_label(d, "Repeat new password").value = "Admin12345"; await click(find_btn(d, "Change password")); r = await t
    check("pw changed", r is True)
    # ---- logout stops ticker, goes to login
    s0 = app.session; await app.logout(); check("logout view", "Staff sign in" in alltext(page.controls[0]) and app.session > s0)
    app.user.value, app.pw.value = "admin", "Admin12345"; await app.do_login(); await asyncio.sleep(0.2); check("relogin new pw", app.title_lbl.value == "Dashboard")
    print("PASS", H.PASS, "FAIL", H.FAIL)
    for t in page.tasks: t.cancel()
asyncio.run(main())
