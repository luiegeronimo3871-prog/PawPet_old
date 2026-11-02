import json, sys, urllib.request, urllib.error
from datetime import date, timedelta
B = "http://localhost:5000/api"
def call(method, path, body=None, tok=None):
    req = urllib.request.Request(B+path, method=method, data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type":"application/json", **({"Authorization":"Bearer "+tok} if tok else {})})
    try:
        with urllib.request.urlopen(req) as r: return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read())
fails = 0
def check(name, cond, extra=""):
    global fails
    print(("PASS " if cond else "FAIL ")+name, extra if not cond else "")
    fails += (not cond)
s, r = call("POST","/login",{"username":"admin","password":"admin123","portal":"admin"}); A = r["token"]; check("admin login", s==200)
s, r = call("POST","/login",{"username":"megan","password":"pass123"}); C = r["token"]; check("customer login", s==200)
s, r = call("POST","/login",{"username":"megan","password":"pass123","portal":"admin"}); check("customer blocked from admin portal", s==403)
s, r = call("POST","/login",{"username":"megan","password":"bad"}); check("bad password 401", s==401)
s, r = call("POST","/register",{"username":"newbie","password":"abc12345","full_name":"New Bie"}); check("register", s==201)
s, r = call("POST","/register",{"username":"newbie","password":"abc12345","full_name":"New Bie"}); check("duplicate username 409", s==409)
s, r = call("POST","/register",{"username":"x","password":"123","full_name":"X"}); check("short password 400", s==400)
s, r = call("GET","/products?category=Medicine"); check("product filter", s==200 and all(p["category"]=="Medicine" for p in r) and len(r)==3, r)
s, r = call("GET","/products?q=dog"); check("product search", s==200 and len(r)==1)
s, r = call("GET","/vets"); check("vets list", len(r)==3)
d = date.today()+timedelta(days=3)
while d.weekday() not in (1,2,3): d += timedelta(days=1)
D = d.strftime("%Y-%m-%d")
s, r = call("GET",f"/availability?vet_id=1&service_id=1&date={D}"); check("slots exist", s==200 and len(r)>10, r)
sun = date.today()
while sun.weekday()!=6: sun += timedelta(days=1)
s, r = call("GET",f"/availability?vet_id=1&service_id=1&date={sun}"); check("vet off on Sunday -> no slots", r==[])
body = {"pet_id":1,"service_id":4,"vet_id":1,"appt_date":D,"appt_time":"10:00"}
s, r = call("POST","/appointments",body,C); check("book 60-min service", s==201, r); aid = r.get("id")
s, r = call("POST","/appointments",{**body,"service_id":1,"appt_time":"10:30"},C); check("overlap blocked (10:30 inside 10:00-11:00)", s==409, r)
s, r = call("POST","/appointments",{**body,"service_id":1,"appt_time":"11:00"},C); check("adjacent slot ok", s==201, r)
s, r = call("POST","/appointments",{**body,"pet_id":3,"appt_time":"15:00"},C); check("cannot book someone else's pet", s==404, r)
s, r = call("GET","/appointments",None,C); check("customer sees only own", s==200 and all(a["customer_id"]==3 for a in r))
s, r = call("GET","/customers",None,C); check("customer cannot list customers", s==403)
s, r = call("POST",f"/appointments/{aid}/status",{"status":"confirmed"},C); check("customer cannot confirm", s==403)
s, r = call("POST",f"/appointments/{aid}/status",{"status":"confirmed"},A); check("staff confirms", s==200)
s, r = call("GET","/notifications",None,C); check("customer got notifications", s==200 and any("confirmed" in n["title"].lower() for n in r), r)
s, r = call("GET","/products"); before = {p["id"]:p["stock"] for p in r}
s, r = call("POST",f"/appointments/{aid}/complete",{"products":[{"product_id":3,"qty":2}],"notes":"all good"},A); check("complete + sale", s==200 and r["total"]==600+360, r)
s, r = call("GET","/products"); after = {p["id"]:p["stock"] for p in r}; check("stock deducted", after[3]==before[3]-2)
s, r = call("POST",f"/appointments/{aid}/complete",{},A); check("cannot complete twice", s==409)
s, r = call("POST","/appointments/1/complete",{"products":[{"product_id":9,"qty":1}]},A); check("out-of-stock product refused", s==409, r)
s, r = call("POST",f"/appointments/{aid}/followup",{"appt_date":D,"appt_time":"14:00"},A); check("follow-up scheduled", s==201, r); fid = r.get("id",0)
s, r = call("POST",f"/appointments/{aid}/cancel",None,C); check("cannot cancel completed", s==409)
s, r = call("POST",f"/appointments/{fid}/cancel",None,C); check("customer cancels own follow-up", s==200, r)
s, r = call("POST","/products/5/adjust",{"delta":-99},A); check("stock cannot go negative", s==409)
s, r = call("POST","/products/6/sell",{"qty":1},A); check("walk-in sale", s==200)
s, r = call("POST","/products",{"name":"","price":"x"},A); check("product validation", s==400)
s, r = call("GET","/dashboard",None,A); check("dashboard", s==200 and r["sales_30"]>0 and isinstance(r["top_items"][0]["qty"], int), r)
s, r = call("GET","/sales?days=7",None,A); check("sales list", s==200 and len(r)>=4)
s, r = call("POST","/reminders/send",None,A); check("reminders", s==200)
s, r = call("POST","/vets",{"name":"Dr X"},A); check("admin adds vet", s==201)
st = call("POST","/login",{"username":"staff","password":"staff123"})[1]["token"]
s, r = call("POST","/vets",{"name":"Dr Y"},st); check("staff cannot add vet", s==403)
s, r = call("GET","/me"); check("no token 401", s==401)

from datetime import date as _d, timedelta as _td
s, r = call("GET","/batches",None,A); check("batches listed", s==200 and any(b["status"]=="expired" for b in r) and any(b["status"]=="expiring" for b in r), r[:2])
s, r = call("GET","/batches",None,C); check("customer cannot see batches", s==403)
s, r = call("GET","/products",None,A); vd = [p for p in r if p["id"]==5][0]; check("expired stock not sellable (usable 0)", vd["stock"]==0 and vd["expired_qty"]==4 and vd["physical_stock"]==4, vd)
s, r = call("POST","/products/5/sell",{"qty":1},A); check("selling expired medicine refused", s==409, r)
s, r = call("POST","/appointments/1/complete",{"products":[{"product_id":5,"qty":1}]},A); check("expired product refused in visit", s in (409,), r)
tomorrow=(_d.today()+_td(days=40)).strftime("%Y-%m-%d")
s, r = call("POST","/products/5/restock",{"qty":10,"batch_no":"VD-002","expiry_date":tomorrow},A); check("restock new batch", s==201 and r["stock"]==10, r)
s, r = call("POST","/products/5/restock",{"qty":1,"expiry_date":"2020-01-01"},A); check("restock past expiry refused", s==400, r)
s, r = call("POST","/products/5/restock",{"qty":1,"expiry_date":"bad"},A); check("restock bad date refused", s==400, r)
s, r = call("GET","/batches?product_id=5",None,A); old=[b for b in r if b["status"]=="expired"][0]
s, r = call("POST",f"/batches/{old['id']}/discard",None,A); check("discard expired batch", s==200 and r["discarded"]==4, r)
s, r = call("GET","/products",None,A); vd = [p for p in r if p["id"]==5][0]; check("after discard physical=usable", vd["physical_stock"]==10 and vd["stock"]==10 and vd["expired_qty"]==0, vd)
s, r = call("POST","/products/3/sell",{"qty":30},A); check("FEFO takes soon-to-expire batch first", s==200, r)
s, r = call("GET","/batches?product_id=3",None,A); live=[b for b in r if b["qty"]>0]; check("FEFO leaves the later batch", len(live)>=1 and all(b["batch_no"]!="DW-002" for b in live), r)
s, r = call("GET","/dashboard",None,A); check("dashboard has expiring + pending list", s==200 and "expiring" in r and "pending_list" in r and isinstance(r["expired_count"],int), list(r))

print("\nFAILS:", fails); sys.exit(1 if fails else 0)
