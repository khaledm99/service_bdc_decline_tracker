# Declined Service Tracker

A follow-up system for dealership service declines: imports the weekly CRM export,
tracks each declined line item through a contact workflow, and serves customers
one at a time when they are due to be called.

Built to replace a manual process I run daily as a service BDC representative.

---

## The problem

When a customer declines recommended service, that recommendation is worth money to
the dealership and worth a phone call later. The CRM records declines but has no
follow-up workflow, so the work is done out of a spreadsheet: read a line, look the
customer up, call them, remember what happened, remember to call again in a month.

Three constraints shaped the whole design:

**No API access.** The CRM exposes nothing but a CSV export. Every customer number
and phone number has to be looked up by hand, one repair order at a time.

**The export is an append-only event feed, not a snapshot.** A decline appears
exactly once, on the repair order where it happened, and is never re-listed. If a
customer declines a brake flush in March and comes back in July without doing it,
the July export says nothing about the brake flush. There is therefore no way to
learn from the data whether a decline is still open - that information exists only
as the result of a manual CRM check.

---

## How it works

### Pipeline

```
CSV  ->  read  ->  group  ->  load  ->  lookup queue  ->  contact queue
```

**Read.** Headers are normalized (lowercased, whitespace collapsed) and mapped
through an alias table onto internal names, so `Mileage`, `KILOMETERS`, and
`  Kilometers ` all resolve to `odometer`. Columns with no alias are dropped.
Required columns are checked up front so a wrong file fails with a useful message
rather than a `KeyError`.

**Group.** The export is flat: one row per decline line, with the repair order's
details repeated on every row. Grouping collapses that into one repair order holding
a list of decline lines.

**Identify.** Decline lines have no natural identifier. Op codes repeat within a
single repair order - `MISC` is used for general notes and is frequently split
across several lines - so `(ro_number, opcode)` is not unique. Lines are instead
keyed by `(ro_number, line_seq)`, where the sequence number is assigned from the
line's position within its repair order. This relies on the export listing a
repair order's lines in a stable order, which it does.

**Load.** Two tables, written in one transaction per file, with
`INSERT ... ON CONFLICT DO NOTHING` against a uniqueness constraint. Re-importing a
file already loaded inserts nothing and reports zero new lines.

### Lookup queue

Imported repair orders have a customer name but no customer number, and a name is
not a usable key - it is stable per customer but not unique. So repair orders exist
in two phases, and nothing enters the contact rotation until it has been enriched.

The lookup queue serves one repair order at a time: the RO number displayed large
for copying into the CRM, the customer name and vehicle for verification, and the
declined lines for context. Entering a customer number and phone links the repair
order to a customer record, creating it or linking to the existing one if that
customer has been seen before, and moves its lines into the contact queue with a
first due date computed from the decline date.

### Contact queue

The main focus is the customer, rather than a repair order or its lines. A customer
with multiple repair orders should be contacted once regarding all of them (granted a sufficient time has
passed from the last visit), so the queue selects whoever has the oldest due line 
and then shows all declines across every repair order, grouped by visit.

Outcomes are recorded **per line**, because a customer can book two items and defer
three in the same conversation. Line state and line due dates are independent; the
customer resurfaces whenever their earliest line matures.

### Transition engine

A dictionary maps
`(current_state, action)` to `(next_state, due_date_rule)`:

```python
("awaiting_contact", "text_sent"): ("awaiting_reply", ("offset", 3)),
("awaiting_reply",   "booked"):    ("awaiting_appointment", ("explicit", None)),
("awaiting_reply",   "no_reply"):  ("awaiting_contact", ("offset", 14)),
```

We don't need many due-date rules: `offset` adds N days, `explicit` takes a date
supplied at the time of the action, `none` clears the date and marks the line
as terminal.

Three properties result:

- Applying an action is a dictionary lookup, not a branch. There are no
  state-machine conditionals anywhere in the application.
- Illegal transitions are rejected because the key is absent.
- The buttons rendered for a line are generated from that line's legal transitions,
  so the interface cannot offer an action the engine would reject, and cannot drift
  out of sync with the rules.

Adding a new action is one dictionary entry.

### Frontend

Server-rendered HTML over FastAPI and Jinja2 for simplicity. Every
interaction is a form post followed by a redirect, so refreshing never re-applies an
action.

The pages are shaped around the task rather than the data: on the contact page the
phone number is the largest element because it is what you are about to dial; on the
lookup page the RO number is, because it is what you are about to type into the CRM.
Line state is carried by a colour on the left edge of each row so a customer with
nine declines can be read at a glance while the call is already connected.

The frontend was built with heavy AI assistance, as frontend work was not the point
or within the scope of the application's core logic.

---

## Running it

```bash
pip install -r requirements.txt

# generate a year of synthetic exports to work against
python generator.py

# web interface
uv run fastapi dev endpoint.py   # then open http://localhost:8000/import

# or the CLI, which drives the same core functions
python core.py lists/010126-311226.csv
```

No real customer data is included in this repository, and the database file is
gitignored. The generator produces synthetic repair orders with realistic
distributions: multi-line ROs, repeat customers across the year, sparse RO number
sequences, the leading-whitespace quirk of the real export, plus a separate file
mapping RO numbers to customer numbers, which stands in for the manual CRM lookup.

---

## Layout

| File | |
|---|---|
| `core.py` | Import pipeline, queries, transition engine, CLI |
| `endpoint.py` | FastAPI routes |
| `generator.py` | Synthetic export generator |
| `templates/` | Jinja2 templates |

---

## Known limitations

**Date format detection is not implemented.** The real CRM I use randomly changes
the date format between month-first and day-first. I use a small quick script
during real work to split the csv lists for other members of service BDC department, and currently
I manually edit the date format each week. The importer currently hardcodes
day-first parsing, so a month-first export will either fail or, worse, parse
silently wrong whenever both components are ≤ 12. The intended fix is a
pre-parse scan of the file: any date component above 12 cannot be a month, so a
single unambiguous row determines the format for the whole file, and a file with
no such row is rejected rather than guessed at.

**No event log.** State transitions overwrite the line's current state, so history
is lost. The next piece of work is an append-only `observation` table written
alongside every transition, recording `(line_id, timestamp, action, from_state,
to_state, note)`. This addition will allow useful data analytics: conversion rate by op code,
whether contact at 30 days converts better than at 60, how many bookings actually show up.

**Single user, no auth.** It runs on localhost against a local SQLite file.

---

## Roadmap

- [x] CSV import and sanitization
- [x] Repair order grouping and line identity
- [x] Lookup queue
- [x] Contact queue
- [x] Transition engine
- [x] Web frontend
- [ ] Per-file date format detection
- [ ] Append-only event log
- [ ] Appointment confirmation stage
- [ ] Conversion reporting
