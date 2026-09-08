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

import csv
import sqlite3
from datetime import datetime as dt

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

def read_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        mapping = {}
        for raw in reader.fieldnames:
            #normalize header to lowercase and remove leading/trailing whitespace
            nraw = " ".join(raw.lower().split())
            #check header aliases and build mapping from 
            #normalized raw headers to standard internal header names
            internal = COLUMN_ALIASES.get(nraw)
            if internal:
                mapping[raw] = internal

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
        return rows
        # return a row in the form:
        # {"ro_number": "123456", "ro_closed_date": "datetime"...}

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
        vin             TEXT
        odometer        INTEGER NOT NULL)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS decline_line(
        id              INTEGER PRIMARY KEY,
        ro_number       TEXT NOT NULL REFERENCES repair_order(ro_number),
        line_seq        INTEGER NOT NULL,
        opcode          TEXT NOT NULL,
        description     TEXT,
        status          TEXT,
        UNIQUE (ro_number, line_seq))""")

    cur.execute("""CREATE TABLE IF NOT EXISTS customer(
        id      TEXT PRIMARY KEY,
        name    TEXT NOT NULL,
        phone   TEXT NOT NULL)""")


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
    print("RO Number:", ro["ro_number"])
    print("RO Date:", ro["ro_date"])
    print("Customer name:", ro["customer_name"])
    print("Customer no:", ro["customer_no"])
    print("Advisor:", ro["customer_name"])
    print("Vehicle:", ro["year"], ro["make"], ro["model"])
    print("Odometer:", ro["odometer"])
    for l in lines:
        display_line(l)

def fetch_lines(con, ro):
    sql = """
    SELECT *
    FROM decline_line d
    WHERE d.ro_number = (?)
    """
    res = con.execute(sql, (ro["ro_number"],))
  
    return res.fetchall()

def display_line(l):
    print("Line",str(l["line_seq"])+":", l["opcode"],"---",l["description"])

def serve_unenriched_ros(con):
    while True:
        ro = next_unenriched(con)
        if ro is None:
            print("All RO's enriched")
            break
        lines = fetch_lines(con, ro)    
        display_ro(ro,lines)
        cid = input("Enter id: ")
        phone = input("Enter phone number: ")
        con.execute("""
        UPDATE repair_order
        SET customer_no = (?), customer_phone = (?)
        WHERE ro_number = (?)
        """, (cid, phone, ro["ro_number"]))

        con.execute("""
        INSERT INTO customer (id, name, phone) VALUES (?, ?, ?) ON CONFLICT DO NOTHING""", 
        (cid, ro["customer_name"], phone))
        con.commit()
    


def main():
    rows = read_rows('lists/010126-311226.csv')
    ros = group_ros(rows)
    assign_seq_numbers(ros)
    con = sqlite3.connect("test.db")
    con.row_factory = sqlite3.Row

    init_db(con)
    import_to_database(con, ros)
    serve_unenriched_ros(con)


if __name__ == "__main__":
    main()
