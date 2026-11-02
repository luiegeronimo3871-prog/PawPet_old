"""Small UI helpers for the desktop app: colors, formatting, cards, buttons and the table."""
from datetime import date

import flet as ft

# theme
BG, SIDEBAR, PANEL, PANEL2, LINE = "#0f1a15", "#0b140f", "#16241d", "#1b2d24", "#27402f"
TEXT, MUTED = "#e8f3ec", "#8fa89a"
GREEN, GREEN_D, AMBER, RED, BLUE = "#2fb36d", "#1f8a52", "#f0a94b", "#e5645a", "#4aa8d8"
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

STATUS_COLOR = {"pending": AMBER, "confirmed": BLUE, "completed": GREEN, "cancelled": RED, "no_show": RED,
                "low": AMBER, "out": RED}


# formatting helpers
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
    """Days until a date (negative = already past), None if blank."""
    if not s:
        return None
    try:
        y, m, d = [int(x) for x in s.split("-")]
        return (date(y, m, d) - date.today()).days
    except Exception:
        return None


# small widgets
def label(text, size=13, color=TEXT, bold=False, **kw):
    return ft.Text(str(text), size=size, color=color, weight=ft.FontWeight.BOLD if bold else None, **kw)


def card(content, padding=16, expand=False, width=None):
    return ft.Container(content=content, bgcolor=PANEL, border_radius=ft.BorderRadius.all(14),
                        border=ft.Border.all(1, LINE), padding=ft.Padding.all(padding), expand=expand, width=width)


def stat_card(title):
    """Returns (box, value text, small text) so the page can change the numbers later."""
    value = label("-", 24, TEXT, True)
    sub = label("", 11, MUTED)
    box = card(ft.Column([label(title, 10, MUTED, True), value, sub], spacing=4, tight=True), expand=True)
    return box, value, sub


def primary(text, on_click, icon=None):
    return ft.FilledButton(content=text, icon=icon, on_click=on_click,
                           style=ft.ButtonStyle(bgcolor=GREEN, color="#06210f"))


def danger(text, on_click, icon=None):
    return ft.FilledButton(content=text, icon=icon, on_click=on_click,
                           style=ft.ButtonStyle(bgcolor=RED, color="#2b0907"))


def plain(text, on_click, icon=None):
    return ft.OutlinedButton(content=text, icon=icon, on_click=on_click,
                             style=ft.ButtonStyle(color=TEXT, side=ft.BorderSide(1, LINE)))


def field(text="", value="", width=None, password=False, on_submit=None, expand=False, autofocus=False):
    return ft.TextField(label=text, value="" if value is None else str(value), width=width, password=password,
                        can_reveal_password=password, on_submit=on_submit, expand=expand, autofocus=autofocus,
                        border_color=LINE, filled=True, bgcolor=PANEL2, border_radius=ft.BorderRadius.all(10),
                        content_padding=ft.Padding.symmetric(vertical=10, horizontal=12))


def dropdown(text, options, value=None, width=None, on_select=None):
    """options: a list of strings or (key, text) pairs."""
    opts = []
    for o in options:
        k, t = (o if isinstance(o, (tuple, list)) else (o, o))
        opts.append(ft.DropdownOption(key=str(k), text=str(t)))
    return ft.Dropdown(label=text, options=opts, value=None if value is None else str(value), width=width,
                       on_select=on_select, border_color=LINE, filled=True, bgcolor=PANEL2,
                       border_radius=ft.BorderRadius.all(10))


# table
class Table:
    """Table made of rows you can click. Columns share the width by weight, so it always fills the window.

    set(rows) takes a list of (row_id, [text for each column], color or None)."""

    def __init__(self, headings, weights=None, on_change=None):
        self.weights = weights or [1] * len(headings)
        self.on_change = on_change
        self.selected = None
        self.data = []
        self.rows = {}
        self.page = None
        head = ft.Container(
            content=ft.Row([ft.Container(label(h, 11, MUTED, True), expand=w) for h, w in zip(headings, self.weights)],
                           spacing=10),
            bgcolor=PANEL2, padding=ft.Padding.symmetric(vertical=10, horizontal=14),
            border_radius=ft.BorderRadius.all(8))
        self.list = ft.ListView(controls=[], expand=True, spacing=0)
        self.empty = label("Nothing to show.", 12, MUTED)
        self.root = ft.Column([head, self.list], expand=True, spacing=4)

    def attach(self, page):
        self.page = page
        return self

    def set(self, rows):
        self.data = rows
        if self.selected not in [r[0] for r in rows]:
            self.selected = None
        self.rows = {r[0]: self._row(r) for r in rows}
        self.list.controls = list(self.rows.values()) or [self.empty]
        if self.page is not None:
            self.page.update()

    def _row(self, r):
        rid, cells, color = r
        texts = [ft.Container(ft.Text(str(c), size=12, color=color or TEXT, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                              expand=w) for c, w in zip(cells, self.weights)]
        return ft.Container(
            content=ft.Row(texts, spacing=10), padding=ft.Padding.symmetric(vertical=11, horizontal=14),
            bgcolor=GREEN_D if rid == self.selected else None, border=ft.Border.only(bottom=ft.BorderSide(1, LINE)),
            ink=True, on_click=lambda e, i=rid: self.select(i))

    def select(self, rid):
        self.selected = rid
        for i, row in self.rows.items():
            row.bgcolor = GREEN_D if i == rid else None
        if self.on_change:
            self.on_change(rid)
        if self.page is not None:
            self.page.update()
