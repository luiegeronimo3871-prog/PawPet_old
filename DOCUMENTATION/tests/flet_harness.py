"""Drives the real Flet 1.0.5 controls (from the cloned source) against a live test server, with a fake page."""
import os, sys, asyncio, inspect, dataclasses, traceback
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "LAPTOP1_Desktop"))
try:
    import flet  # noqa  (a normal "pip install flet")
except ImportError:
    raise SystemExit("Install Flet first:  pip install flet==1.0.5")
import flet as ft
import admin, pages, ui
from api_client import Api

class W: pass
class FakePage:
    def __init__(s):
        s.controls = []; s.window = W(); s.dialogs = []; s.updates = 0; s.tasks = []
    def update(s): s.updates += 1
    def show_dialog(s, d): d.open = True; s.dialogs.append(d)
    def pop_dialog(s):
        for d in reversed(s.dialogs):
            if d.open:
                d.open = False
                return d
    def run_task(s, fn, *a):
        assert inspect.iscoroutinefunction(fn), fn
        t = asyncio.ensure_future(fn(*a)); s.tasks.append(t); return t
    def open_dialogs(s): return [d for d in s.dialogs if d.open and not isinstance(d, ft.SnackBar)]

def children(c):
    out = []
    if isinstance(c, (list, tuple)):
        for x in c: out += [x] + children(x)
        return out
    if not dataclasses.is_dataclass(c): return out
    for f in dataclasses.fields(c):
        if f.name in ("data", "key") or f.name.startswith("_"): continue
        v = getattr(c, f.name, None)
        if isinstance(v, ft.Control) or (dataclasses.is_dataclass(v) and isinstance(v, ft.BaseControl)):
            out += [v] + children(v)
        elif isinstance(v, list):
            for x in v:
                if isinstance(x, ft.BaseControl): out += [x] + children(x)
    return out

def walk(c): return [c] + children(c)
def texts(c):
    out = []
    for x in walk(c):
        if isinstance(x, ft.Text) and x.value: out.append(str(x.value))
    return out
def alltext(c): return "\n".join(texts(c))
def btn_text(b):
    c = getattr(b, "content", None)
    return c if isinstance(c, str) else (getattr(c, "value", None) if c is not None else None)
def buttons(c): return [x for x in walk(c) if isinstance(x, (ft.FilledButton, ft.OutlinedButton, ft.TextButton, ft.Button))]
async def click(b):
    r = b.on_click(None)
    if inspect.iscoroutine(r): await r
def by_label(c, text):
    for x in walk(c):
        if isinstance(x, (ft.TextField, ft.Dropdown, ft.Checkbox)) and x.label == text: return x
    raise KeyError(text)
def find_btn(c, text):
    for b in buttons(c):
        if btn_text(b) == text: return b
    raise KeyError("button " + text + " in " + str([btn_text(b) for b in buttons(c)]))

async def wait_dialog(page, n=1, tries=300):
    for _ in range(tries):
        if len(page.open_dialogs()) >= n: return page.open_dialogs()[-1]
        await asyncio.sleep(0.01)
    raise AssertionError("no dialog appeared")

async def run_with_dialog(page, coro_fn, fill=None, press=None, expect=None, then=None):
    """Start an action that opens a dialog, fill fields, check text, press a button."""
    t = asyncio.ensure_future(coro_fn())
    d = await wait_dialog(page)
    for k, v in (fill or {}).items():
        w = by_label(d, k); w.value = v
    if expect:
        txt = alltext(d)
        assert expect in txt, (expect, txt)
    if then: await then(d)
    if press: await click(find_btn(d, press))
    await asyncio.wait_for(t, 15)
    return d

PASS = FAIL = 0
def check(name, cond, extra=""):
    global PASS, FAIL
    if cond: PASS += 1
    else:
        FAIL += 1; print("FAIL:", name, extra)
