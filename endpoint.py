from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import core
import sqlite3
from datetime import date

app = FastAPI()
templates = Jinja2Templates(directory="templates")
def get_connection():
    con = sqlite3.connect("test.db")
    con.row_factory = sqlite3.Row
    return con

@app.get("/contact")
def contact_next(request: Request):
    con = get_connection()
    res = core.next_contact(con)
    if res is None:
        return templates.TemplateResponse(request, "empty.html", {})
    customer, ros = res
    core.assign_line_ids(ros)
    today = date.today().isoformat()
    for r in ros:
        for l in r["lines"]:
            l["actions"] = core.get_legal_actions(l["state"])
    return templates.TemplateResponse(request, "contact.html", {"customer" : customer, "ros": ros, "today": today})

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
    return templates.TemplateResponse(request, "contact.html", {"customer" : customer, "ros": ros, "today": today})

@app.post("/contact/{customer_no}/line/{line_id}")
def apply(customer_no: str, line_id: int, action:str = Form(...), explicit_date: str = Form(None)):
    con = get_connection()
    core.update_decline_state(con, line_id, action, explicit_date)
    return RedirectResponse(f"/contact/{customer_no}", status_code=303)
