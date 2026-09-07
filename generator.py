# Generates random declined service csv data for testing and demonstration

from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from datetime import time
from datetime import date
import random
import string

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

#RO #, RO Closed Date, Advisor ,Tech, Customer Name, Year, Make, Model, Mileage/Kilometers, Op Code, Op Code Name, Task Status, Total 

@dataclass 
class Customer:
    customer_no: int
    name: str
    phone: str

@dataclass
class Vehicle:
    vin: str
    make: str
    model: str
    year: int
    mileage: int

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
    vehicle: Vehicle
    declines: List[DeclineLine]

def _gen_customers(
    rng: int,
    n: int
) -> List[Customer]:
    random.seed(rng)
    customers = []
    used_ids = []
    for c in range(n):
        id = random.randint(0, 999999)
        while id in used_ids:
            id = random.randint(0, 999999)
        used_ids.append(id)
        name = random.choice(LAST_NAMES) + ", " + random.choice(FIRST_NAMES)
        phone = "587" + ''.join(random.choices(string.digits, k=7))
        customers.append(Customer(id, name, phone))
    return customers
def _gen_visits(
    n: int,
    start: date,
    end: date
) -> List[datetime]:
    visits = []
    for i in range(n):
        # each customer will visit 1-4 times per year, with 1 visit being the most common
        visit_count = random.choices([1,2,3,4], [60,30,8,2])[0]
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


def build_example(rng, n_customers, start, end):
    # generate customers
    random.seed(rng)
    customers = _gen_customers(rng, n_customers)
    # generate visits
    visits = _gen_visits(len(customers), start, end) 


    for i in range(len(customers)):
        print(customers[i])
        for v in visits[i]:
            # example format: d/m/y h:m am/pm
            print(v.strftime('%d/%m/%y %I:%M%p'))
        print("\n")


    # generate decline lines per visit


def main():
    rng = 42
    build_example(rng, 20, date(2026,1,1), date(2026,12,31))

if __name__ == "__main__":
    main()
