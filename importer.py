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
            print(nraw)
            #check header aliases and build mapping from 
            #normalized raw headers to standard internal header names
            internal = COLUMN_ALIASES.get(nraw)
            print(internal)
            if internal:
                mapping[raw] = internal
            print(mapping)

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
        for h in mapping:
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
        if r["ro_number"] not in ros:
            ros[r["ro_number"]] = {
                "ro_number": r["ro_number"],
                "customer_name": r["customer_name"],
                "ro_date": r["ro_closed_date"],
                "advisor": r["advisor"],
                "year": r["year"],
                "make": r["make"],
                "model": r["model"],
                "odometer": r["odometer"],
                "status": r["status"],
                "lines": []
            }
        ros[r["ro_number"]]["lines"].append({
            "opcode": r["opcode"],
            "desc": r["desc"],
        })
    return list(ros.values())

# for each ro, assign a sequence number to each decline line so they can be
# uniquely keyed in the database
def assign_seq_numbers(ros):
    for r in ros:
        for seq, line in enumerate(r["lines"], start=1):
            line["seq"] = seq

def main():
    rows = read_rows('lists/010126-311226.csv')
    ros = group_ros(rows)
    assign_seq_numbers(ros)
    print(ros)

if __name__ == "__main__":
    main()
