# Generates random declined service csv data for testing and demonstration

from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from datetime import time
from datetime import date
import random
import string
import csv

FIRST_NAMES = [
    "Robert", "Jennifer", "Michael", "Linda", "David", "Patricia",
    "James", "Barbara", "William", "Susan", "Richard", "Karen",
    "Joseph", "Nancy", "Thomas", "Lisa", "Christopher", "Betty",
    "Daniel", "Margaret", "Matthew", "Sandra", "Anthony", "Ashley",
    "Mark", "Kimberly", "Steven", "Emily", "Andrew", "Donna",
    "Kenneth", "Michelle", "Brian", "Carol", "Kevin", "Amanda",
    "Jason", "Melissa", "Ryan", "Deborah", "Jacob", "Stephanie",
    "Gary", "Rebecca", "Nicholas", "Laura", "Eric", "Sharon",
    "Jonathan", "Cynthia", "Stephen", "Kathleen", "Justin", "Amy",
    "Scott", "Angela", "Brandon", "Shirley", "Benjamin", "Anna",
    "Amrit", "Priya", "Wei", "Mei", "Ahmed", "Fatima",
    "Carlos", "Sofia", "Dmitri", "Olena", "Tomasz", "Aisha",
    "Ravi", "Nguyen", "Hyun", "Ji-woo", "Omar", "Leila",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Miller",
    "Davis", "Wilson", "Anderson", "Taylor", "Thomas", "Moore",
    "Martin", "Thompson", "White", "Harris", "Clark", "Lewis",
    "Robinson", "Walker", "Young", "Allen", "King", "Wright",
    "Scott", "Hill", "Green", "Adams", "Baker", "Nelson",
    "Campbell", "Mitchell", "Roberts", "Carter", "Phillips", "Evans",
    "Turner", "Parker", "Collins", "Edwards", "Stewart", "Morris",
    "Murphy", "Cook", "Rogers", "Bailey", "Reed", "Kelly",
    "Cooper", "Richardson", "Ward", "Watson", "Brooks", "Sanders",
    "MacDonald", "Fraser", "Gagnon", "Tremblay", "Roy", "Bouchard",
    "Singh", "Gill", "Patel", "Sharma", "Chen", "Wang",
    "Nguyen", "Tran", "Kim", "Park", "Hassan", "Ali",
    "Garcia", "Rodriguez", "Martinez", "Lopez", "Kowalski", "Novak",
]


@dataclass 
class Customer:
    customer_no: int
    name: str
    phone: str
    vehicle: Vehicle

MODELS = {
    "Jeep": ["Wrangler", "Compass", "Cherokee", "Grand Cherokee", "Renegade"],
    "Ram": ["1500", "2500", "3500", "5500", "Promaster1500"],
    "Dodge": ["Journey", "Durango", "Charger", "Challenger", "Hornet", "Grand Caravan"],
    "Fiat": ["500", "Spider"],
    "Chrysler": ["500", "Pacifica"]
}
@dataclass
class Vehicle:
    make: str
    model: str
    year: int
    mileage: int

# common opcodes with descriptions and sample prices
OPCODES = {
    "BRKSERVICE": ("Brake service due every 32,000km", 185.00),
    "BRKFLUSH": ("Brake flush due every 45,000km", 194.00),
    "LOFSYN": ("Synthetic oil change due every 8000km", 190.00),
    "DRIVELINE": ("Driveline service due every 96,000km", 850.00),
    "WA": ("Wheel alignment", 140.00),
    "LEAK": ("Fluid leak identified, needs further diag", 194.95),
    "CABIN": ("Cabin air filter dirty, needs replacement", 60.00),
    "AIRFILTER": ("Engine air filter dirty, needs replacement", 94.00),
    "CFLUSH": ("Coolant flush due every 100,000km", 260.00),
    "SERTRANS": ("Transmission service due every 45,000km", 250.00),
    "WS": ("Windshield heavily damaged, recommend replace", 450.00)
}

@dataclass
class DeclineLine:
    opcode: str
    desc: str
    status: str
    total: float

@dataclass
class RepairOrder:
    ro: int
    closed_date: datetime
    advisor: str
    tech: str
    customer: Customer
    declines: List[DeclineLine]

def _gen_declines(
) -> List[DeclineLine]:
    n = random.randrange(1,5)
    declines = []
    codes = random.sample(list(OPCODES.keys()), n)
    for c in codes:
        declines.append(DeclineLine(
            c,
            str(OPCODES[c][0]),
            str(random.choice(["Caution", "Fail"])),
            str(OPCODES[c][1])))
    return declines
    

def _gen_customers(
    n: int
) -> List[Customer]:
    customers = []
    used_ids = []
    for c in range(n):
        id = random.randint(0, 999999)
        while id in used_ids:
            id = random.randint(0, 999999)
        used_ids.append(id)
        name = random.choice(LAST_NAMES) + ", " + random.choice(FIRST_NAMES)
        phone = "587" + ''.join(random.choices(string.digits, k=7))
        make = random.choice(list(MODELS.keys()))
        model = random.choice(MODELS[make])
        mileage = random.randrange(8000, 200000)
        year = random.randrange(2015, 2026)
        vehicle = Vehicle(make, model, year, mileage)
        customers.append(Customer(id, name, phone, vehicle))
    return customers

def _gen_visits(
    n: int,
    start: date,
    end: date
) -> List[List[datetime]]:
    visits = []
    for i in range(n):
        # each customer will visit 1-4 times per year, with 1 visit being the most common
        visit_count = random.choices([1,2,3,4], [50,30,13,7])[0]
        # computes a random day between the start and end dates
        day = start + timedelta(days=random.randrange((end-start).days))
        days = []
        for _ in range(visit_count):
            # truncate at end date
            if day > end:
                break
            days.append(day)
            min_gap = 21 # minimum 3 week difference between visits
            max_gap = 180 # max 6 month difference between visits
            day += timedelta(random.randrange(min_gap,max_gap))

        # service is open from 7am to 5:30pm
        SERVICE_OPEN = time(7,0)
        SERVICE_CLOSE = time(17,30)
        datetimes = []
        for d in days:
            # sundays are closed, nudge to monday
            if d.weekday() == 6:
                d += timedelta(days=1)
            open_dt = datetime.combine(d, SERVICE_OPEN)
            close_dt = datetime.combine(d, SERVICE_CLOSE)
            # compute total minutes between open and close for day
            span = int((close_dt - open_dt).total_seconds() // 60)
            datetimes.append(open_dt + timedelta(minutes = random.randrange(span)))
        visits.append(datetimes)
    return visits
def _make_ro_rows(ro: RepairOrder) -> List[List[str]]:
    # Each element is prepended with a space to mimic the real output
    # of the crm
    rows = []
    row = [
        " "+str(ro.ro),
        " "+ro.closed_date.strftime('%d/%m/%y %I:%M %p'),
        " "+ro.advisor,
        " "+ro.tech,
        " "+ro.customer.name,
        " "+str(ro.customer.vehicle.year),
        " "+ro.customer.vehicle.make,
        " "+ro.customer.vehicle.model,
        " "+str(ro.customer.vehicle.mileage),
        "",
        "",
        "",
        ""
    ]
    for d in ro.declines:
        
        row[-4] = " "+str(d.opcode)
        row[-3] = " "+str(d.desc)
        row[-2] = " "+d.status
        row[-1] = " "+str(d.total)
        rows.append(row.copy())

    return rows

def build_example(rng, n_customers, start, end):
    # generate customers
    random.seed(rng)
    customers = _gen_customers(n_customers)
    # generate visits
    visits = _gen_visits(len(customers), start, end) 

    # flatten the visits list so we have a list of visits paired with the customer,
    # and sort by the visit dates. This way, we can realistically generate RO numbers
    # sequentially based on visits
    flattened_visits = [(c, dt) for c, visits in zip(customers, visits) for dt in visits]
    flattened_visits.sort(key=lambda p: p[1])

    # generate ROs

    ros = []
    ro_number = random.randrange(100000, 400000)
    for v in flattened_visits:
        ros.append(RepairOrder(
            ro_number,
            v[1],
            random.choice(["Advisor A", "Advisor B", "Advisor C"]),
            random.choice(["Tech A", "Tech B", "Tech C", "Tech D", "Tech E"]),
            v[0],
            _gen_declines()
        ))
        
        # Not all RO's will have declines. Realistically add gaps in ro number sequence
        ro_number += random.randrange(1,12)


#RO #, RO Closed Date, Advisor ,Tech, Customer Name, Year, Make, Model, Mileage/Kilometers, Op Code, Op Code Name, Task Status, Total 
    # generate csv rows
    start_str = start.strftime('%d%m%y')
    end_str = end.strftime('%d%m%y')
    filename = "lists/"+start_str + '-' + end_str + '.csv'



    with open(filename, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(["RO #", "Ro Closed Date", "Advisor ", "Tech", "Customer Name", "Year", "Make", "Model", "Mileage", "Op Code", "Op Code Name", "Task Status", "Total"])

        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        rows = []
        for ro in ros:
            rows += _make_ro_rows(ro)
        w.writerows(rows)
    #for r in ros:
        #print(r)
        #print("\n")




def main():
    rng = 42
    build_example(rng, 20, date(2026,1,1), date(2026,12,31))

if __name__ == "__main__":
    main()
