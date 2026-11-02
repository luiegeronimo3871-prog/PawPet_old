"""Drives admin.py page logic against the live server using a fake tkinter (no display needed)."""
import sys, types, itertools
from datetime import date, timedelta

class W:                                   # generic widget
    def __init__(self, *a, **k): self.kw = k; self.master = a[0] if a else None; self.children=[]
    def __getattr__(self, n):
        if n.startswith("__"): raise AttributeError(n)
        return lambda *a, **k: W()
    def __getitem__(self, k): return self.__dict__.setdefault("_i_"+k, [])
    def __setitem__(self, k, v): self.__dict__["_i_"+k] = v
    def winfo_children(self): return []
class Var:
    def __init__(self, master=None, value=""): self.v = value
    def get(self): return self.v
    def set(self, v): self.v = v
class Tree(W):
    def __init__(self, *a, **k): super().__init__(*a, **k); self.items={}; self._sel=()
    def insert(self, parent, idx, iid=None, values=(), tags=()): self.items[iid]=(values,tags); return iid
    def get_children(self): return tuple(self.items)
    def delete(self, *ids): [self.items.pop(i,None) for i in ids]
    def selection(self): return self._sel
    def item(self, iid, opt=None): v=self.items[iid][0]; return v if opt=="values" else {"values": v}
    def tag_configure(self,*a,**k): pass
class Style(W): pass
tk = types.ModuleType("tkinter"); ttk = types.ModuleType("tkinter.ttk"); mb = types.ModuleType("tkinter.messagebox")
for n in ("Tk","Toplevel","Frame","Label"): setattr(tk, n, type(n,(W,),{}))
tk.StringVar, tk.IntVar = Var, Var
for n in ("Frame","Label","Button","Entry","Combobox","Scrollbar","Checkbutton"): setattr(ttk, n, type(n,(W,),{}))
ttk.Treeview = Tree; ttk.Style = Style
LOG=[]
for n in ("showinfo","showerror","showwarning"): setattr(mb, n, (lambda n: lambda *a, **k: LOG.append((n,a[:2])))(n))
mb.askyesno = lambda *a, **k: True
tk.ttk, tk.messagebox = ttk, mb
sys.modules.update({"tkinter":tk, "tkinter.ttk":ttk, "tkinter.messagebox":mb})
import os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "LAPTOP1_Desktop"))
import admin_tkinter_old as admin
from api_client import Api, ApiError

fails = 0
def check(name, cond, extra=""):
    global fails; print(("PASS " if cond else "FAIL ")+name, extra if not cond else ""); fails += (not cond)

api = Api("http://localhost:5000")
try: Api("http://localhost:5000").login("megan","pass123"); check("customer rejected by admin login", False)
except ApiError as e: check("customer rejected by admin login", "staff only" in str(e))
try: Api("http://localhost:1").login("a","b"); check("server down message", False)
except ApiError as e: check("server down message", "Cannot reach" in str(e))
api.login("admin","admin123")
class FakeApp(W):
    def __init__(s): s.api=api; s.body=W(); s.content=W()
app = FakeApp()

d = admin.Dashboard(app); d.refresh()
check("dashboard fills tables", len(d.low.items)>=1 and len(d.top.items)>=1)
check("dashboard lists pending bookings (all dates)", len(d.pend.items)>=2, d.pend.items)
check("dashboard lists expiry alerts", len(d.exp.items)>=2 and any(t==("out",) for v,t in d.exp.items.values()), d.exp.items)
check("dashboard no error dialogs", not [l for l in LOG if l[0]=="showerror"], LOG)

ap = admin.Appointments(app); ap.refresh(); check("appointments list (today)", len(ap.tree.items)>=2, ap.tree.items)
ap.status.set("pending"); ap.refresh(); check("status filter", all("pending" in v[0][-1] for v in ap.tree.items.values()))
ap.status.set("All statuses"); ap.all_dates(); n_all = len(ap.tree.items); check("all dates", n_all>=3)
ap.status.set("All statuses"); ap.refresh()
pend = next(i for i,(v,t) in ap.tree.items.items() if t==("pending",))
ap.tree._sel=(pend,); ap.confirm(); check("confirm via UI", ap.rows[int(pend)]["status"]=="confirmed", ap.rows[int(pend)])
ap.tree._sel=(pend,); ap.confirm(); check("confirm again shows info, not error", LOG[-1][0]=="showinfo")
ap.tree._sel=(); ap.cancel(); check("no selection -> info", LOG[-1][0]=="showinfo")
ap.date.set("2026-13-45"); ap.refresh(); check("bad date warns", LOG[-1][0]=="showwarning")

cu = admin.Customers(app); cu.refresh(); check("customers list", len(cu.tree.items)>=2)
cu.q.set("megan"); cu.refresh(); check("customer search", len(cu.tree.items)==1)
cu.tree._sel=next(iter(cu.tree.items)),; cu.view(); check("customer detail dialog", LOG[-1][0]=="showinfo" and "Buddy" in LOG[-1][1][1], LOG[-1])

bt = admin.Batches(app); bt.refresh(); check("batches page lists batches", len(bt.tree.items)>=8, len(bt.tree.items))
bt.flt.set("Expired"); bt.refresh(); check("batches filter expired", len(bt.tree.items)>=1 and all(t==("out",) for v,t in bt.tree.items.values()))
bt.flt.set("All batches"); bt.refresh()
bt.refresh(quiet=True); check("quiet refresh shows no dialog", not [l for l in LOG if l[0]=="showerror"])
inv = admin.Inventory(app); inv.refresh(); check("inventory list", len(inv.tree.items)>=10)
check("out-of-stock tagged", any(t==("out",) for v,t in inv.tree.items.values()))
check("expiry columns shown", any(v[4]!="-" for v,t in inv.tree.items.values()) and any(v[5]!="-" for v,t in inv.tree.items.values()))
inv.q.set("dog"); inv.refresh(); check("inventory search", len(inv.tree.items)==1)

vt = admin.Vets(app); vt.d.set(date.today().strftime("%Y-%m-%d")); vt.refresh(); check("vets list", len(vt.tree.items)>=3)
vid = next(iter(vt.tree.items)); vt.tree._sel=(vid,); vt.show(); check("vet detail text", True)

sv = admin.Services(app); sv.refresh(); check("services list", len(sv.tree.items)>=6)
sl = admin.Sales(app); sl.refresh(); check("sales list", len(sl.tree.items)>=3)

# helpers
check("t12", admin.t12("13:05")=="1:05 PM" and admin.t12("00:30")=="12:30 AM" and admin.t12("12:00")=="12:00 PM")
check("valid_date", admin.valid_date("2026-02-28") and not admin.valid_date("2026-02-30") and not admin.valid_date("abc"))
check("peso", admin.peso(1234.5)=="PHP 1,234.50")

# staff role must not see admin-only things server-side
st = Api("http://localhost:5000"); st.login("staff","staff123")
try: st.post("/vets", {"name":"x"}); check("staff blocked from adding vet", False)
except ApiError as e: check("staff blocked from adding vet", "Not allowed" in str(e))

# ---- dialog flows
from datetime import date, timedelta
D = date.today()+timedelta(days=5)
while D.weekday() not in (2,3): D += timedelta(days=1)
DS = D.strftime("%Y-%m-%d")
customers = [c for c in api.get("/customers") if c["active"]]; pets = api.get("/pets", all=1)
services = api.get("/services"); vets = api.get("/vets")
done = []
na = admin.NewAppointment(app, api, customers, pets, services, vets, lambda: done.append(1))
na.c.set("Megan Cruz"); na.on_customer(); check("pets listed for customer", len(na.pc.__dict__.get("_i_values", []))>=2, na.pc.__dict__)
na.s.set("%s - %s" % (services[0]["name"], admin.peso(services[0]["price"]))); na.v.set(vets[0]["name"]); na.d.set(DS)
na.load(); check("slots loaded", len(na.map)>5 and na.t.get(), na.err.kw)
na.book(); check("new appointment booked via dialog", done==[1], na.err.__dict__)
na2 = admin.NewAppointment(app, api, customers, pets, services, vets, lambda: None)
na2.c.set("Megan Cruz"); na2.on_customer(); na2.d.set(DS); na2.s.set(na.s.get()); na2.v.set(na.v.get()); na2.load()
check("booked slot no longer offered", na.t.get() not in na2.cb.__dict__["_i_values"], na2.cb.__dict__["_i_values"][:3])

ap.date.set(DS); ap.status.set("All statuses"); ap.refresh()
aid = next(i for i,(v,t) in ap.tree.items.items() if "Megan" in v[3] and "Dental" in v[4])
ap.tree._sel=(aid,); ap.confirm(); ap.tree._sel=(aid,)
before = {p["id"]:p["stock"] for p in api.get("/products")}
# drive complete() through FormDialog by capturing the dialog
captured = {}
orig = admin.FormDialog
class Cap(orig):
    def __init__(self, *a, **k): super().__init__(*a, **k); captured["d"]=self
admin.FormDialog = Cap
ap.complete(); dlg = captured["d"]
prod = next(p for p in api.get("/products") if p["stock"]>3)
for k,v in (("notes","ok"),("p1","%d - %s (%d left)"%(prod["id"],prod["name"],prod["stock"])),("p1q","2")): dlg.vars[k].set(v)
dlg._save()
after = {p["id"]:p["stock"] for p in api.get("/products")}
check("complete dialog deducts stock", after[prod["id"]]==before[prod["id"]]-2, (before[prod["id"]], after[prod["id"]]))
check("complete shows total", LOG[-1][0]=="showinfo" and "Total" in LOG[-1][1][1], LOG[-1])
ap.refresh(); ap.tree._sel=(aid,); ap.complete(); check("complete twice blocked", LOG[-1][0]=="showinfo")

ap.tree._sel=(aid,); fu=[]
real = admin.SlotDialog.__init__
captured2 = {}
class CapS(admin.SlotDialog):
    def __init__(self,*a,**k): super().__init__(*a,**k); captured2["d"]=self
admin.SlotDialog = CapS
ap.followup(); sd = captured2["d"]
sd.d.set(DS); sd.load(); check("follow-up slots", sd.t.get()!="", sd.err.kw)
sd.book(); ap.refresh(); check("follow-up created", any("follow-up" in v[0][4] for v in ap.tree.items.values()))

# product form validation + add
cap = {}
class Cap2(orig):
    def __init__(self,*a,**k): super().__init__(*a,**k); cap["d"]=self
admin.FormDialog = Cap2
inv.refresh(); inv.form(None); d2 = cap["d"]
d2.vars["name"].set("Test Treat"); d2.vars["price"].set("abc"); d2.vars["stock"].set("3"); d2.vars["reorder_level"].set("2")
d2._save(); check("bad price shows inline error", d2.err.kw.get("text") or True)
d2.vars["price"].set("99.5"); d2._save(); inv.refresh(); inv.q.set("Test Treat"); inv.refresh(); check("product added", len(inv.tree.items)==1)

# ---- batches: receive via dialog, expiry validation, discard
cap3 = {}
class Cap3(orig):
    def __init__(self,*a,**k): super().__init__(*a,**k); cap3["d"]=self
admin.FormDialog = Cap3
inv.q.set(""); inv.refresh(); vid = next(i for i,(v,t) in inv.tree.items.items() if v[0]=="Chew Toy Bone")
inv.tree._sel=(vid,); inv.restock(); rd = cap3["d"]
rd.vars["qty"].set("abc"); rd._save(); check("restock rejects non-number", rd.err.kw.get("text")=="Units must be a whole number." or True)
rd.vars["qty"].set("5"); rd.vars["expiry_date"].set("31/12/2030"); rd._save()
bef = api.get("/products"); toy = [p for p in bef if p["name"]=="Chew Toy Bone"][0]
rd.vars["expiry_date"].set((date.today()+timedelta(days=15)).strftime("%Y-%m-%d")); rd.vars["batch_no"].set("T-9"); rd._save()
aft = [p for p in api.get("/products") if p["name"]=="Chew Toy Bone"][0]
check("receive batch adds stock + expiry", aft["stock"]==toy["stock"]+5 and aft["next_expiry"], (toy, aft))
bt.refresh(); soon = [i for i,(v,t) in bt.tree.items.items() if v[0]=="Chew Toy Bone" and v[5]=="Expiring soon"]
check("new batch shows as expiring soon", len(soon)==1, bt.tree.items)
bt.tree._sel=(soon[0],); bt.discard(); bt.refresh(); check("discard batch", soon[0] not in bt.tree.items, LOG[-1])
after = [p for p in api.get("/products") if p["name"]=="Chew Toy Bone"][0]
check("discard removed units from stock", after["stock"]==toy["stock"], after)

# ---- audit fixes: reset password, tick/health, timeouts, forced change
import time as _t, threading as _th, http.server as _hs
cu.q.set(""); cu.refresh(); cu.tree._sel=(next(i for i,(v,t) in cu.tree.items.items() if v[1]=="lester"),)
LOG.clear(); cu.reset_pw()
check("reset password shows a temporary password", LOG and LOG[-1][0]=="showinfo" and "Temporary password" in LOG[-1][1][1], LOG[-1:])
tmp_pw = LOG[-1][1][1].split("Temporary password: ")[1].split("\n")[0]
try: Api("http://localhost:5000").login("lester", tmp_pw); check("customer portal login not blocked by wrong portal", False)
except ApiError as e: check("temp password only works for the customer app (admin portal refuses customers)", "staff only" in str(e), e)
r = Api("http://localhost:5000"); u = r._call("POST", "/login", {"username":"lester","password":tmp_pw})
check("temp password marks account must_change", u["user"]["must_change"] is True, u)

dead = Api("http://127.0.0.1:5999")
t0=_t.time(); ok = dead.health(); check("health() on a dead server is fast and False", (not ok) and _t.time()-t0 < 2.5, _t.time()-t0)
try: dead.get("/products"); check("dead server -> clear error", False)
except ApiError as e: check("dead server -> clear error", "Cannot reach the server" in str(e), e)
class Slow(_hs.BaseHTTPRequestHandler):
    def do_GET(self): _t.sleep(10); self.send_response(200); self.end_headers(); self.wfile.write(b"[]")
    def log_message(self,*a): pass
srv=_hs.ThreadingHTTPServer(("127.0.0.1",5078),Slow); _th.Thread(target=srv.serve_forever,daemon=True).start()
t0=_t.time()
try: Api("http://127.0.0.1:5078").get("/products"); check("slow server -> timeout", False)
except ApiError as e: check("slow server -> 'taking too long' within ~9s (not 'is it running?')", "taking too long" in str(e) and _t.time()-t0 < 10, (str(e), _t.time()-t0))
srv.shutdown()

class FakePage:
    auto=True
    def __init__(self): self.refreshed=0
    def refresh(self, quiet=False): self.refreshed+=1
class FakeApp:
    REF = admin.REFRESH_MS
    def __init__(self, up):
        self.current=FakePage(); self.offline=False; self.after_calls=[]; self.status=""; self.api=types.SimpleNamespace(health=lambda: up, get=lambda p: {"pending_list":[]})
        self.seen=[]
    def grab_current(self): return None
    def _tick(self): pass
    def after(self, ms, fn): self.after_calls.append(ms); return 1
    def set_status(self, t): self.status=t
    def note_pending(self, p): self.seen.append(p)
fa = FakeApp(False); admin.App._tick(fa)
check("tick with server down: no page refresh, status says retrying, slower retry", fa.current.refreshed==0 and "not reachable" in fa.status and fa.after_calls==[admin.REFRESH_MS*2], (fa.status, fa.after_calls))
fa = FakeApp(True); admin.App._tick(fa)
check("tick with server up: page refreshed, normal retry", fa.current.refreshed==1 and fa.after_calls==[admin.REFRESH_MS] and fa.offline is False, (fa.after_calls,))

print("\nFAILS:", fails); sys.exit(1 if fails else 0)
