#
#- CSV Import
#- Import and sanitize csv files containing service decline data
#- Evenly split csv data and give the option to import subsets into
#  app or output styled html tables for printing
#- Sanitize malformed data and column names (constraint from CRM we're
#  getting data from, as it regularly changes the date format and column names
#- bundle decline lines by RO (repair order) number
#- move RO's to lookup queue
#


# load file
# normalize and map column headers
# read rows into dicts using DictReader

import os
import io
import csv
import sqlite3
import argparse
from datetime import datetime as dt
from datetime import date
from datetime import timedelta

COLUMN_ALIASES = {
        "ro #": "ro_number",
        "ro closed date": "ro_closed_date",
        "advisor": "advisor",
        "customer name": "customer_name",
        "year": "year",
        "make": "make",
        "model": "model",
        "mileage": "odometer",
        "kilometers": "odometer",
        "op code": "opcode",
        "op code name": "desc",
        "task status": "status"
}

def clear_terminal():
    os.system('cls' if os.name == 'nt' else 'clear')

def read_rows_from_file(f):
    reader = csv.DictReader(f)

    # map imported raw header names to standard names for internal use
    mapping = {}

    REQUIRED = {
        "ro_number",
        "ro_closed_date",
        "advisor",
        "customer_name",
        "year",
        "make",
        "model",
        "odometer",
        "opcode",
        "desc",
        "status"
    }


    for raw in reader.fieldnames:
        #normalize header to lowercase and remove leading/trailing whitespace
        nraw = " ".join(raw.lower().split())

        #check header aliases and build mapping from 
        #normalized raw headers to standard internal header names
        internal = COLUMN_ALIASES.get(nraw)
        if internal:
            mapping[raw] = internal

        
    # make sure required columns are present
    # if any are missing, output which ones to inspect crm output
    MISSING = REQUIRED - set(mapping.values())
    if MISSING:
        raise ValueError(f"Missing required columns: {sorted(MISSING)}")

    rows = []
    for row in reader:
        line = {}
        for h in mapping:
            line[mapping[h]] = row[h]
        rows.append(line)

    # return a row in the form:
    # {"ro_number": "123456", "ro_closed_date": "datetime"...}
    return rows

def read_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return read_rows_from_file(f)

# Needed for file upload on web frontend
def read_rows_from_bytes(data, filename=""):
    text = io.TextIOWrapper(io.BytesIO(data), newline="", encoding="utf-8-sig")
    return read_rows_from_file(text)
       
def group_ros(rows):
    # group rows by repair order
    ros = {}
    for r in rows:
        if r["ro_number"].strip() not in ros:
            ros[r["ro_number"].strip()] = {
                "ro_number": r["ro_number"].strip(),
                "customer_name": r["customer_name"].strip(),
                "ro_date": dt.strptime(r["ro_closed_date"].strip(), '%d/%m/%y %I:%M %p').date().isoformat(),
                "advisor": r["advisor"].strip(),
                "year": r["year"].strip(),
                "make": r["make"].strip(),
                "model": r["model"].strip(),
                "odometer": r["odometer"].strip(),
                "lines": []
            }
        ros[r["ro_number"].strip()]["lines"].append({
            "opcode": r["opcode"].strip(),
            "desc": r["desc"].strip(),
            "status": r["status"].strip(),
        })
    return list(ros.values())

# for each ro, assign a sequence number to each decline line so they can be
# uniquely keyed in the database
def assign_seq_numbers(ros):
    for r in ros:
        for seq, line in enumerate(r["lines"], start=1):
            line["seq"] = seq

def init_db(con):
    cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS repair_order(
        ro_number       TEXT PRIMARY KEY,
        customer_name   TEXT NOT NULL,
        customer_no     TEXT REFERENCES customer(id),
        customer_phone  TEXT,
        ro_date         TEXT NOT NULL,
        advisor         TEXT NOT NULL,
        year            INTEGER NOT NULL,
        make            TEXT NOT NULL,
        model           TEXT NOT NULL,
        vin             TEXT,
        odometer        INTEGER NOT NULL)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS decline_line(
        id              INTEGER PRIMARY KEY,
        ro_number       TEXT NOT NULL REFERENCES repair_order(ro_number),
        line_seq        INTEGER NOT NULL,
        opcode          TEXT NOT NULL,
        description     TEXT,
        status          TEXT,
        state           TEXT NOT NULL DEFAULT 'new',
        next_due        TEXT,
        UNIQUE (ro_number, line_seq))""")

    cur.execute("""CREATE TABLE IF NOT EXISTS customer(
        id      TEXT PRIMARY KEY,
        name    TEXT NOT NULL,
        phone   TEXT NOT NULL)""")
    con.commit()


def import_to_database(con, ros):

    cur = con.cursor()

    inserted = skipped = 0

    with con:
        for ro in ros:
            #insert ro
            cur.execute("""INSERT INTO repair_order
              (ro_number, customer_name, ro_date, advisor, year, make, model, odometer)
              VALUES (?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING
            """, 
            (
            ro["ro_number"],
            ro["customer_name"],
            ro["ro_date"],
            ro["advisor"],
            ro["year"],
            ro["make"],
            ro["model"],
            ro["odometer"],
            ))
            for line in ro["lines"]:
                cur.execute("""INSERT INTO decline_line (
                ro_number, line_seq, opcode, description, status) 
                VALUES (?, ?, ?, ?, ?) ON CONFLICT DO NOTHING""",
                (ro["ro_number"],
                 line["seq"],
                 line["opcode"],
                 line["desc"],
                 line["status"]))
                if cur.rowcount:
                    inserted += 1
                else:
                    skipped += 1

    return inserted, skipped 


# Fetch the next unenriched RO. Freshly imported RO's require "enrichment",
# as they don't include the customer ID number or customer phone number
# We'll serve up unenriched RO's in one queue, and as the user inputs the 
# customer information (requires manual CRM lookup), they'll be shifted to
# the actual decline contact queue
def next_unenriched(con):
    sql = """
        SELECT *
        FROM repair_order 
        WHERE customer_no IS NULL
        ORDER BY ro_date, ro_number
        LIMIT 1
        """
    cur = con.execute(sql)
    return cur.fetchone()

# Take sqlite3 row object
def display_ro(ro, lines):
    clear_terminal()
    print("RO Number:", ro["ro_number"])
    print("RO Date:", ro["ro_date"])
    print("Customer name:", ro["customer_name"])
    print("Customer no:", ro["customer_no"])
    print("Advisor:", ro["Advisor"])
    print("Vehicle:", ro["year"], ro["make"], ro["model"])
    print("Odometer:", ro["odometer"])
    for l in lines:
        display_line(l)

# Fetch decline lines associated with a single RO
def fetch_lines(con, ro):
    sql = """
    SELECT *
    FROM decline_line d
    WHERE d.ro_number = (?)
    """
    res = con.execute(sql, (ro["ro_number"],))
  
    return res.fetchall()

def display_line(l):
    print("Line",str(l["line_seq"])+":", l["opcode"],"---",l["description"],"Due:",l["next_due"],l["state"])

# Add customer info to Customer table and add customer id and phone to RO
def enrich_ro(con, ro, cid, phone):
    with con:
        con.execute("""
        INSERT INTO customer (id, name, phone) VALUES (?, ?, ?) ON CONFLICT DO NOTHING""", 
        (cid, ro["customer_name"], phone))

        con.execute("""
        UPDATE repair_order
        SET customer_no = (?), customer_phone = (?)
        WHERE ro_number = (?)
        """, (cid, phone, ro["ro_number"]))
        
        next_due = (date.fromisoformat(ro["ro_date"]) + timedelta(days=14)).isoformat()
        con.execute("""
        UPDATE decline_line
        SET next_due = (?), state = "awaiting_contact"
        WHERE ro_number = (?)
        """, (next_due, ro["ro_number"]))

# Serve unenriched RO's one-by-one, take user input to add customer ID and phone number
def serve_unenriched_ros(con):
    while True:
        ro = next_unenriched(con)

        if ro is None:
            clear_terminal()
            print("All RO's enriched")
            break

        lines = fetch_lines(con, ro)    
        display_ro(ro,lines)

        cid = input("Enter id: ")
        while not cid.isdigit() or len(cid) != 6:
            cid = input("Invalid id. Enter id: ")

        phone = input("Enter phone number: ")
        while not phone.isdigit() or len(phone) != 10:
            phone = input("Invalid phone number. Enter phone number: ")

        enrich_ro(con, ro, cid, phone)

        
    

# Form: (current_state, action) -> (next_state, due_date)
# due_date is tuple (type, value), where type is an offset and value is number of days to add,
# or type is "explicit" and value is none. If type is "explicit", we'll input a specific date for the next due date
# type can also be "none", which means we set the due_date on the decline line to NULL, signalling no further contact regarding that decline
TRANSITIONS = {
        ("awaiting_contact",    "text_sent"):          ("awaiting_reply",      ("offset", 3)),
        ("awaiting_contact",    "call_made"):          ("awaiting_reply",      ("offset", 3)),
        ("awaiting_contact",    "skip"):               ("awaiting_contact",    ("offset", 7)),
        ("awaiting_contact",    "do_not_contact"):     ("closed_opt_out",      ("none", None)),
        ("awaiting_contact",    "already_done"):       ("closed_complete",     ("none", None)),
        ("awaiting_reply",      "no_reply"):           ("awaiting_contact",    ("offset", 14)),
        ("awaiting_reply",      "declined_again"):     ("awaiting_contact",    ("offset", 90)),
        ("awaiting_reply",      "opt_out"):            ("closed_opt_out",      ("none", None)),
        ("awaiting_reply",      "postpone"):           ("awaiting_contact",    ("explicit", None)),
        ("awaiting_reply",      "booked"):             ("awaiting_appointment",("explicit", None)),
        ("awaiting_appointment","complete"):           ("closed_complete",     ("none", None)),
        ("awaiting_appointment","no_show"):            ("awaiting_contact",    ("offset", 1)),
        ("awaiting_appointment","cancel"):             ("awaiting_contact",    ("offset", 7)),

}

def get_legal_actions(state):
    legal_actions = []
    for key in TRANSITIONS.keys():
        if key[0] == state:
            legal_actions.append(key[1])
    return legal_actions

# Helper function for next_contact and get_customer
# takes list of sqlite3.Row objects from the second query in
# next_contact and groups ro's together with their decline lines per customer
def group_by_ro(rows):
    ros = {}

    for r in rows:
        key = r["ro_number"]

        if key not in ros:
            ros[key] = {
                "ro_number": key,
                "ro_date": r["ro_date"],
                "advisor": r["advisor"],
                "year": r["year"],
                "make": r["make"],
                "model": r["model"],
                "odometer": r["odometer"],
                "lines": []
            }
        ros[key]["lines"].append({
            "id": r["id"],
            "opcode": r["opcode"],
            "description": r["description"],
            "state": r["state"],
            "next_due": r["next_due"]
        })
    return list(ros.values())


def next_contact(con):
    
    
    res = con.execute("""
        SELECT r.customer_no, c.name, c.phone, MIN(d.next_due) AS due
        FROM decline_line d
        JOIN repair_order r ON r.ro_number = d.ro_number
        JOIN customer c ON c.id = r.customer_no
        WHERE d.next_due <= (?) AND state != 'new'
        GROUP BY r.customer_no
        ORDER BY due
        LIMIT 1
        """, (dt.today().isoformat(),))

    customer_rows = res.fetchone()
    if not customer_rows:
        return None

    return get_customer(con, customer_rows["customer_no"])

def get_customer(con, customer_no):
    
    res = con.execute("""
        SELECT r.customer_no, c.name, c.phone
        FROM decline_line d
        JOIN repair_order r ON r.ro_number = d.ro_number
        JOIN customer c ON c.id = r.customer_no
        WHERE c.id = ?
        LIMIT 1
        """, (customer_no,))

    customer = res.fetchone()

    if not customer:
        return None

    res = con.execute("""
        SELECT r.ro_number, r.ro_date, r.advisor, r.year, r.make, r.model, r.odometer, 
               d.id, d.line_seq, d.opcode, d.description, d.state, d.next_due
        FROM decline_line d
        JOIN repair_order r ON d.ro_number = r.ro_number
        WHERE r.customer_no = (?)
        ORDER BY r.ro_date, d.line_seq
        """, (customer["customer_no"],))

    ros = group_by_ro(res.fetchall())
    assign_line_ids(ros)

    return (customer, ros)


def update_decline_state(con, decline_id, next_state, new_date):
    con.execute("""
    UPDATE decline_line
    SET next_due = (?), state = (?)
    WHERE id = (?)
    """, (new_date, next_state, decline_id))

    con.commit()

# Serve due contact tasks one-by-one. Presents a customer with any due
# contact tasks - displays all active RO's and decline lines
def serve_contact_queue(con):
    while True:
        contact = next_contact(con)
        if contact is None:
            print("Contact Queue Empty")
            break
        display_contact(*contact)

        # select line
        line = input("Select Decline Line: ")
        while not line.isdigit():
            line = input("Invalid selection. Select Decline Line: ")

        line = int(line)
        selected_line = None

        while selected_line == None:
            for r in contact[1]:
                for l in r["lines"]:
                    if l["line_id"] == line:
                        selected_line = l
            if selected_line == None:
                line = input("Invalid selection. Select Decline Line: ")
                while not line.isdigit():
                    line = input("Invalid selection. Select Decline Line: ")
                line = int(line)


        # generate actionable items for that line
        legal_actions = get_legal_actions(selected_line["state"])

        action_id = 0
        if not legal_actions:
            input("No available actions, press ENTER to continue...")
            continue

        for a in legal_actions:
            action_id +=1
            print(str(action_id)+". "+a)

        selected_action = input("Select action: ")

        while not selected_action.isdigit() or int(selected_action) < 1 or int(selected_action) > action_id:
            selected_action = input("Invalid choice. Select action: ")

        selected_action = int(selected_action)
        action_str = legal_actions[selected_action-1]
        next_state, next_due = TRANSITIONS[(selected_line["state"],action_str)]

        def compute_new_date(rule, value, today):
            if rule == "offset":
                new_date = today + timedelta(days=value)
                return new_date
            if rule == "none":
                return None
            if rule == "explicit":
                in_date = input("Input date (YYYY-MM-DD): ")
                return date.fromisoformat(in_date)

        new_date = None
        while True:
            try:
                new_date = compute_new_date(*next_due, date.today())
                break
            except ValueError:
                print("Not a valid date. Use YYYY-MM-DD.")

        if new_date:
            new_date = new_date.isoformat()

        update_decline_state(con, selected_line["id"], next_state, new_date)

def assign_line_ids(ros):
    line_id = 1
    for r in ros:
        for l in r["lines"]:
            l["line_id"] = line_id
            line_id += 1

def display_contact(customer, ros):
    clear_terminal()
    print(f"ID {customer['customer_no']:<17} {customer['name']:^20} {customer['phone']:>20}")
    for r in ros:
        print()
        print(f"RO {r['ro_number']} -- {r['ro_date']} -- {r['year']} {r['make']} {r['model']} -- {r['odometer']}km")
        for l in r["lines"]:
            print(f"  {f'{l["line_id"]}. [{l["opcode"]}]':<15.15} {l['description']:<60.60} {l['state']:>30.30}, {l['next_due']}")

def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=str, help="Filepath to csv")
    args = parser.parse_args()
    rows = read_rows(args.path)
    ros = group_ros(rows)
    assign_seq_numbers(ros)
    con = sqlite3.connect("test.db")
    con.row_factory = sqlite3.Row

    init_db(con)
    import_to_database(con, ros)
    serve_unenriched_ros(con)
    serve_contact_queue(con)


if __name__ == "__main__":
    main()
