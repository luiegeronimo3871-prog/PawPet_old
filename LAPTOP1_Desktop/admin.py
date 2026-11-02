"""PawPet desktop app for admin and staff (Python + Flet).
Run: pip install -r requirements.txt, then python admin.py. The server must be running."""
import asyncio
import os
import traceback
from datetime import datetime

import flet as ft

from api_client import Api, ApiError
from pages import ALL_PAGES, Appointments, Dashboard
from ui import (AMBER, BG, GREEN, GREEN_D, LINE, MUTED, PANEL, PANEL2, RED, SIDEBAR, TEXT, card, danger, dropdown, field,
                label, plain, primary, t12)

REFRESH_S = 8          # auto-refresh interval (seconds)
DEFAULT_URL = "http://localhost:5000"
ADDR_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server_address.txt")


def saved_url():
    """Server address from the last successful login."""
    try:
        with open(ADDR_FILE, encoding="utf-8") as f:
            return f.read().strip() or DEFAULT_URL
    except OSError:
        return DEFAULT_URL


def remember_url(url):
    try:
        with open(ADDR_FILE, "w", encoding="utf-8") as f:
            f.write(url)
    except OSError:
        pass


class App:
    def __init__(self, page: ft.Page):
        self.page = page
        self.api = Api()
        self.session = 0              # bumped on every login/logout so old refresh loops stop
        self.open = []                # futures of the dialogs that are currently open
        self._dlgs = {}
        self.pages, self.nav, self.nav_text = {}, {}, {}
        self.current = None
        self.offline = False
        self.seen_pending = None
        page.title = "PawPet Admin"
        page.padding = 0
        page.spacing = 0
        page.bgcolor = BG
        page.theme_mode = ft.ThemeMode.DARK
        page.theme = ft.Theme(color_scheme_seed=GREEN)
        page.dark_theme = ft.Theme(color_scheme_seed=GREEN)
        page.window.width = 1280
        page.window.height = 760
        page.window.min_width = 1200
        page.window.min_height = 640

    # ================================================================ plumbing
    async def call(self, fn, *args, **kwargs):
        """Run the (slow) API call in a thread so the window does not freeze."""
        return await asyncio.to_thread(fn, *args, **kwargs)

    def show(self, *controls):
        self.page.controls = list(controls)
        self.page.update()

    async def fail(self, e, quiet=False):
        """Decide what to do with an API error."""
        if e.status == 401 and self.api.token:
            return await self.session_expired()
        if e.must_change:
            if not getattr(self, "_forcing", False):
                await self.force_change()
            return
        if quiet:                       # background refresh: no pop-up, just say so in the header
            self.offline = True
            return
        await self.info("PawPet", str(e))

    # ================================================================ dialogs
    def _hide(self, dlg):
        """Close this dialog (not just the top one, a toast may be on top)."""
        dlg.open = False
        try:
            dlg.update()
        except Exception:
            self.page.update()

    def _close(self, dlg, fut, result):
        if dlg.open:
            self._hide(dlg)
        if fut in self.open:
            self.open.remove(fut)
        if not fut.done():
            fut.set_result(result)

    def close_all(self):
        for fut in list(self.open):
            self.open.remove(fut)
            dlg = self._dlgs.pop(fut, None)
            if dlg is not None and dlg.open:
                self._hide(dlg)
            if not fut.done():
                fut.set_result(False)

    @staticmethod
    def _click(handler, close):
        async def click(e=None):            # a real coroutine function, so Flet awaits it
            await handler(close)
        return click

    async def _show(self, title, body, buttons, modal=True):
        """buttons: list of (text, kind, handler(close)). Returns what the dialog is closed with."""
        fut = asyncio.get_running_loop().create_future()
        dlg = ft.AlertDialog(modal=modal, title=label(title, 17, TEXT, True), bgcolor=PANEL, content=body, actions=[])

        def close(result=None):
            self._close(dlg, fut, result)
        acts = []
        for text, kind, handler in buttons:
            mk = {"primary": primary, "danger": danger, "plain": plain}.get(kind, plain)
            acts.append(mk(text, self._click(handler, close)))
        dlg.actions = acts
        dlg.on_dismiss = lambda e: (fut.set_result(False) if not fut.done() else None)
        self.open.append(fut)
        self._dlgs[fut] = dlg
        self.page.show_dialog(dlg)
        return await fut

    async def info(self, title, message):
        body = ft.Container(label(message, 13, TEXT, selectable=True), width=440)

        async def ok(close):
            close(True)
        await self._show(title, body, [("OK", "primary", ok)])

    async def confirm(self, message, yes="Yes"):
        body = ft.Container(label(message, 13, TEXT), width=420)

        async def y(close):
            close(True)

        async def n(close):
            close(False)
        return bool(await self._show("PawPet", body, [("No", "plain", n), (yes, "primary", y)]))

    def toast(self, message):
        self.page.show_dialog(ft.SnackBar(content=label(message, 13, "#ffffff"), bgcolor=GREEN_D, duration=3500))

    async def custom_form(self, title, controls, on_save, save_text="Save", cancel_text="Cancel"):
        """Dialog with ready-made controls. on_save() is async; raise ValueError/ApiError to show a message
        inside the dialog, return False to keep it open. Returns True when saved."""
        err = label("", 12, RED)
        body = ft.Container(ft.Column(list(controls) + [err], tight=True, spacing=10, scroll=ft.ScrollMode.AUTO),
                            width=470)
        busy = {"on": False}

        async def save(close):
            if busy["on"]:
                return
            busy["on"] = True
            try:
                r = await on_save()
            except (ApiError, ValueError) as ex:
                if isinstance(ex, ApiError) and ex.status == 401 and self.api.token:
                    close(False)
                    return await self.session_expired()
                err.value = str(ex)
                self.page.update()
                return
            finally:
                busy["on"] = False
            if r is not False:
                close(True)

        async def cancel(close):
            close(False)
        return bool(await self._show(title, body, [(cancel_text, "plain", cancel), (save_text, "primary", save)]))

    async def form(self, title, fields, on_save, save_text="Save"):
        """fields: (key, label, kind, default, options); kind = entry | text | password | combo | check.
        on_save(values) is async. Combo values are the option key (a string)."""
        widgets = {}
        for key, text, kind, default, opts in fields:
            if kind == "combo":
                w = dropdown(text, opts, default, width=420)
            elif kind == "check":
                w = ft.Checkbox(label=text, value=bool(int(default or 0)))
            elif kind == "password":
                w = field(text, "", width=420, password=True)
            else:
                w = field(text, default, width=420)
            widgets[key] = w

        def values():
            out = {}
            for k, w in widgets.items():
                v = w.value
                out[k] = v if isinstance(w, ft.Checkbox) else ("" if v is None else v)
            return out

        async def save():
            return await on_save(values())
        return await self.custom_form(title, list(widgets.values()), save, save_text)

    # ================================================================ login
    async def start(self):
        self.login_view()

    def login_view(self, message=""):
        self.close_all()
        self.session += 1
        self.pages, self.nav, self.nav_text, self.current = {}, {}, {}, None
        self.url = field("Server address (server laptop IP)", saved_url(), width=360)
        self.user = field("Username", "", width=360, autofocus=True)
        self.pw = field("Password", "", width=360, password=True, on_submit=self.do_login)
        self.login_err = label(message, 12, RED)
        self.login_btn = primary("Sign in", self.do_login, ft.Icons.LOGIN)
        self.login_btn.width = 360
        self.spin = ft.ProgressRing(width=18, height=18, visible=False)
        hero = ft.Container(
            expand=True, bgcolor="#0f5132", alignment=ft.Alignment.CENTER,
            content=ft.Column([
                label("🐾  PawPet", 30, "#ffffff", True),
                ft.Container(height=18),
                label("Run the clinic.\nNot the paperwork.", 34, "#ffffff", True),
                ft.Container(height=8),
                label("Inventory • vet schedules • appointments • sales", 13, "#bfe3cd")],
                tight=True, horizontal_alignment=ft.CrossAxisAlignment.START))
        form = ft.Container(
            expand=True, alignment=ft.Alignment.CENTER,
            content=card(ft.Column([
                label("Staff sign in", 22, TEXT, True), label("PawPet Admin Dashboard", 12, MUTED),
                ft.Container(height=6), self.url, self.user, self.pw, self.login_err,
                ft.Row([self.login_btn, self.spin], spacing=10)], tight=True, spacing=10), padding=30))
        self.show(ft.Row([hero, form], expand=True, spacing=0))

    async def do_login(self, e=None):
        self.login_err.value = ""
        self.login_btn.disabled = True
        self.spin.visible = True
        self.page.update()
        self.api = Api((self.url.value or "").strip() or DEFAULT_URL)
        try:
            await self.call(self.api.login, (self.user.value or "").strip(), self.pw.value or "")
        except ApiError as ex:
            self.login_err.value = str(ex)
            self.login_btn.disabled = False
            self.spin.visible = False
            self.page.update()
            return
        remember_url(self.api.base)
        if self.api.user.get("must_change"):
            self.login_btn.disabled = False
            self.spin.visible = False
            self.page.update()
            if not await self.change_pw(forced=True):        # must choose a new password before anything else
                await self.call(self.api.logout)
                return self.login_view("You must change your temporary password to continue.")
        self.main_view()

    async def force_change(self):
        """A request came back 'must change password' (e.g. an admin reset it while we were signed in)."""
        self._forcing = True
        try:
            if not await self.change_pw(forced=True):
                await self.logout()
        finally:
            self._forcing = False

    async def change_pw(self, forced=False):
        async def save(v):
            if v["new"] != v["again"]:
                raise ValueError("The two new passwords do not match.")
            await self.call(self.api.change_password, v["old"], v["new"])
            self.api.user["must_change"] = False
            self.toast("Password changed.")
        await self.form("Choose a new password" if forced else "Change password", [
            ("old", "Current password", "password", "", None),
            ("new", "New password (8+ chars, letters + numbers)", "password", "", None),
            ("again", "Repeat new password", "password", "", None)], save, "Change password")
        return not self.api.user.get("must_change")

    async def session_expired(self):
        self.api.token = ""
        self.login_view("Your session expired. Please sign in again.")

    # ================================================================ main window
    def main_view(self):
        u = self.api.user
        self.session += 1
        gen = self.session
        classes = [c for c in ALL_PAGES if not (c.admin_only and u["role"] != "admin")]
        nav = []
        for cls in classes:
            txt = label(cls.title, 13, MUTED)
            item = ft.Container(
                content=ft.Row([ft.Icon(cls.icon, size=18, color=MUTED), txt], spacing=12),
                padding=ft.Padding.symmetric(vertical=11, horizontal=14), border_radius=ft.BorderRadius.all(10),
                ink=True, on_click=(lambda e, c=cls: self.page.run_task(self.goto, c)))
            self.nav[cls], self.nav_text[cls] = item, txt
            nav.append(item)
        side = ft.Container(
            width=232, bgcolor=SIDEBAR, padding=ft.Padding.all(12),
            content=ft.Column([
                ft.Container(label("🐾  PawPet", 20, "#ffffff", True), padding=ft.Padding.only(left=8, top=10, bottom=18)),
                ft.Column(nav, spacing=3, expand=True, scroll=ft.ScrollMode.AUTO),
                plain("Log out", lambda e: self.page.run_task(self.logout), ft.Icons.LOGOUT)], expand=True))
        self.title_lbl = label("", 24, TEXT, True)
        self.status_lbl = label("", 11, MUTED)
        head = ft.Row([self.title_lbl, ft.Row([
            self.status_lbl,
            plain("Password", lambda e: self.page.run_task(self.change_pw), ft.Icons.KEY),
            plain("Send reminders", lambda e: self.page.run_task(self.reminders), ft.Icons.NOTIFICATIONS),
            label("%s  (%s)" % (u["full_name"], u["role"]), 12, MUTED)], spacing=12)],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        self.alert_txt = label("", 13, "#06210f", True)
        self.alert = ft.Container(content=self.alert_txt, bgcolor=AMBER, visible=False, padding=ft.Padding.all(10),
                                  border_radius=ft.BorderRadius.all(10), ink=True, on_click=self.dismiss_alert)
        self.body = ft.Container(expand=True)
        content = ft.Container(expand=True, padding=ft.Padding.all(22),
                               content=ft.Column([head, self.alert, self.body], expand=True, spacing=12))
        self.seen_pending = None
        self.offline = False
        self.show(ft.Row([side, content], expand=True, spacing=0))
        for cls in classes:
            self.pages[cls] = cls(self)
        self.page.run_task(self.goto, Dashboard)
        self.page.run_task(self.ticker, gen)

    async def goto(self, cls):
        if cls not in self.pages:
            return
        self.current = self.pages[cls]
        for c, item in self.nav.items():
            on = c is cls
            item.bgcolor = GREEN_D if on else None
            self.nav_text[c].color = "#ffffff" if on else MUTED
        self.title_lbl.value = cls.title
        self.body.content = self.current.root
        self.page.update()
        await self.current.refresh()

    def dismiss_alert(self, e=None):
        self.alert.visible = False
        self.page.update()

    def note_pending(self, pending):
        """Badge on the Appointments menu item and a banner when a customer books something new."""
        ids = {a["id"] for a in pending}
        new = [a for a in pending if self.seen_pending is not None and a["id"] not in self.seen_pending]
        self.seen_pending = ids
        txt = self.nav_text.get(Appointments)
        if txt is not None:
            txt.value = "Appointments (%d pending)" % len(ids) if ids else "Appointments"
        if new:
            a = new[-1]
            self.alert_txt.value = "🔔 New booking request: %s (%s) · %s on %s %s   [click to dismiss]" % (
                a["pet_name"], a["customer_name"], a["service_name"], a["appt_date"], t12(a["appt_time"]))
            self.alert.visible = True
        self.page.update()

    async def reminders(self):
        try:
            r = await self.call(self.api.post, "/reminders/send")
        except ApiError as e:
            return await self.fail(e)
        await self.info("PawPet", "Reminders sent: %d" % r["sent"])

    async def logout(self):
        self.session += 1                       # stops the refresh loop
        self.current = None
        await self.call(self.api.logout)
        self.login_view()

    # ================================================================ live updates
    async def ticker(self, gen):
        """Every few seconds: refresh the visible page and look for new booking requests.
        A 1.5 s health check comes first, so a missing/slow server never freezes the window for long."""
        delay = REFRESH_S
        while gen == self.session:
            await asyncio.sleep(delay)
            if gen != self.session:
                return
            delay = REFRESH_S
            try:
                page = self.current
                if page is None or self.open:           # do not disturb an open dialog
                    continue
                if not await self.call(self.api.health):
                    self.offline = True
                    delay = REFRESH_S * 2
                else:
                    self.offline = False
                    if page.auto:
                        await page.refresh(quiet=True)
                    if gen == self.session and not self.offline and not isinstance(page, Dashboard):
                        try:
                            self.note_pending((await self.call(self.api.get, "/dashboard"))["pending_list"])
                        except ApiError as e:
                            await self.fail(e, quiet=True)
                if gen == self.session:
                    self.status_lbl.value = ("Server not reachable, retrying…" if self.offline else
                                             "Auto-refresh on · updated " + datetime.now().strftime("%H:%M:%S"))
                    self.page.update()
            except Exception:                           # keep the loop running
                traceback.print_exc()


async def main(page: ft.Page):
    await App(page).start()


if __name__ == "__main__":
    ft.run(main)
