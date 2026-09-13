from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import core
import sqlite3
from datetime import date, timedelta

app = FastAPI()
templates = Jinja2Templates(directory="templates")

def get_connection():
    con = sqlite3.connect("test.db")
    con.row_factory = sqlite3.Row
    return con

@app.post("/import")
def import_csv(request: Request, file: UploadFile = File(...)):
    con = get_connection()
    try:
        rows = core.read_rows_from_bytes(file.file.read(), file.filename)
        ros = core.group_ros(rows)
        core.assign_seq_numbers(ros)
        core.init_db(con)
        inserted, skipped = core.import_to_database(con, ros)
    except ValueError as e:
        return templates.TemplateResponse(
                request, "import.html", {"error": str(e)}, status_code=400)
    return templates.TemplateResponse(
            request, "import.html",
            {"result": {"inserted": inserted, "skipped": skipped,
                        "ros": len(ros), "filename": file.filename}},
            )

@app.get("/import")
def import_form(request: Request):
    con = get_connection()
    return templates.TemplateResponse(request, "import.html",{
        "imports": [],
    })

SKIPPED: set[str] = set()  
@app.get("/enrich")
def enrich_next(request: Request):
    con = get_connection()
    res = core.next_unenriched(con, skip=SKIPPED)
    if res is None:
        return templates.TemplateResponse(request, "enrich_done.html", {})
    return templates.TemplateResponse(request, "enrich.html", {
        "ro": res,
        "lines": core.fetch_lines(con, res),
        "remaining": core.count_unenriched(con),
    })

@app.post("/enrich/{ro_number}")
def apply_enrich(request: Request, ro_number: str, customer_no: str = Form(...), phone: str = Form(...)):
    con = get_connection()
    core.enrich_ro(con, ro_number, customer_no, phone)
    return RedirectResponse("/enrich", status_code=303)

@app.post("/enrich/{ro_number}/skip")
def enrich_skip(ro_number: str):
    SKIPPED.add(ro_number)
    return RedirectResponse("/enrich", status_code=303)
    
@app.get("/contact")
def contact_next(request: Request):
    con = get_connection()
    res = core.next_contact(con)
    if res is None:
        return templates.TemplateResponse(request, "contact_done.html", {})
    customer, ros = res
    core.assign_line_ids(ros)
    today = date.today().isoformat()
    for r in ros:
        for l in r["lines"]:
            l["actions"] = core.get_legal_actions(l["state"])
    return templates.TemplateResponse(request, "contact.html", {"customer" : customer, "ros": ros, "today": today, "date_actions": core.DATE_ACTIONS})

@app.get("/find")
def find(request: Request, customer_no: str = ""):
    con = get_connection()
    if not customer_no:
        return templates.TemplateResponse(request, "find.html", {})
    res = core.get_customer(con, customer_no.strip())
    if not res:
        return templates.TemplateResponse(request, "find.html", {"query": customer_no, "not_found": True})
    return RedirectResponse(f"/contact/{customer_no.strip()}", status_code=303)

@app.get("/contact/{customer_no}")
def contact_one(request: Request, customer_no: str):
    con = get_connection()
    res = core.get_customer(con, customer_no)
    
    if res is None:
        return templates.TemplateResponse(request, "empty.html", {})
    customer, ros = res
    core.assign_line_ids(ros)
    today = date.today().isoformat()
    for r in ros:
        for l in r["lines"]:
            l["actions"] = core.get_legal_actions(l["state"])
    return templates.TemplateResponse(request, "contact.html", {"customer" : customer, "ros": ros, "today": today, "date_actions": core.DATE_ACTIONS})

@app.post("/contact/{customer_no}/line/{line_id}")
def apply(customer_no: str, line_id: int, action:str = Form(...), explicit_date: str = Form(None)):
    con = get_connection()
    res = con.execute("SELECT state FROM decline_line WHERE id = ?", (line_id,))
    state = res.fetchone()["state"]
    next_state, next_due = core.TRANSITIONS[(state, action)]
    #if not explicit_date:
        #date = next_due
    #else:
        #date = explicit_date
    def compute_new_date(rule, value, today, explicit_date = None):
        print(explicit_date)
        if rule == "offset":
            new_date = today + timedelta(days=value)
            return new_date.isoformat()
        if rule == "none":
            return None
        if explicit_date is None:
            raise ValueError("This action requires a date")
        return explicit_date
    new_date = None
    try:
        new_date = compute_new_date(*next_due, date.today(), explicit_date)
    except ValueError as e:
        print(e)



    core.update_decline_state(con, line_id, next_state, new_date)
    return RedirectResponse(f"/contact/{customer_no}", status_code=303)
