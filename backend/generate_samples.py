"""
Generate three realistic CSVs with intentional bias patterns.
Each tells a different story so the audit engine can show off.
"""
import csv
import random
import os
from pathlib import Path

random.seed(42)

OUT = Path(__file__).parent / "sample_data"
OUT.mkdir(parents=True, exist_ok=True)

# -------- helpers ----------
FIRST_M = ["Arjun", "Rohan", "Vikram", "Aditya", "Karan", "Rahul", "Amit", "Sandeep",
           "Manish", "Suresh", "Imran", "Faisal", "Joseph", "Daniel", "Ravi", "Pradeep"]
FIRST_F = ["Priya", "Anjali", "Sneha", "Kavya", "Pooja", "Neha", "Divya", "Riya",
           "Fatima", "Aisha", "Mary", "Sarah", "Lakshmi", "Meera", "Sunita", "Rekha"]
SURNAMES_HINDU = ["Sharma", "Verma", "Patel", "Gupta", "Iyer", "Reddy", "Rao", "Joshi", "Mehta", "Nair"]
SURNAMES_MUSLIM = ["Khan", "Ahmed", "Ali", "Sheikh", "Hussain", "Rahman", "Mirza", "Siddiqui"]
SURNAMES_CHRISTIAN = ["D'Souza", "Fernandes", "Joseph", "Thomas", "George", "Mathew"]
SURNAMES_DALIT = ["Valmiki", "Paswan", "Manjhi", "Chamar", "Dom"]

# Pincodes are picked so each religion clusters tightly in a region
# (mirroring real-world residential segregation patterns)
PINCODE_BANK = {
    "Hindu":     [110001, 110005, 110008, 110010, 110015],   # Central Delhi
    "Muslim":    [110006, 110053, 110055, 110066, 110092],   # Old Delhi / Jamia area
    "Christian": [400050, 400052, 400054, 400061, 400070],   # Mumbai western suburbs
    "Other":     [110044, 110052, 110084, 110086, 110094],   # outer Delhi
}

COLLEGES_TIER1 = ["IIT Bombay", "IIT Delhi", "IIM Ahmedabad", "BITS Pilani", "NIT Trichy"]
COLLEGES_TIER2 = ["DTU Delhi", "VIT Vellore", "Manipal Institute", "Anna University", "Jadavpur University"]
COLLEGES_TIER3 = ["Local Engineering College", "State University", "Tier-3 Pvt College", "Open University"]


# ============================================================
# 1. LOAN APPROVALS — gender + religion bias via pincode proxy
# ============================================================
def gen_loans(n=1000):
    rows = []
    for i in range(n):
        # heavily male-skewed
        gender = random.choices(["Male", "Female"], weights=[72, 28])[0]

        # religion distribution skewed
        religion = random.choices(
            ["Hindu", "Muslim", "Christian", "Other"],
            weights=[70, 18, 8, 4]
        )[0]

        # surname leaks religion (proxy variable)
        if religion == "Hindu":
            surname = random.choice(SURNAMES_HINDU)
        elif religion == "Muslim":
            surname = random.choice(SURNAMES_MUSLIM)
        elif religion == "Christian":
            surname = random.choice(SURNAMES_CHRISTIAN)
        else:
            surname = random.choice(SURNAMES_DALIT)

        first = random.choice(FIRST_M if gender == "Male" else FIRST_F)

        age = random.randint(22, 65)
        income = max(15000, int(random.gauss(55000, 25000)))
        credit_score = max(300, min(850, int(random.gauss(680, 90))))

        # pincode leaks religion — each religion clusters in specific localities
        # (90% within-cluster, 10% noise from other clusters)
        if random.random() < 0.9:
            pincode = random.choice(PINCODE_BANK[religion])
        else:
            other = random.choice([k for k in PINCODE_BANK if k != religion])
            pincode = random.choice(PINCODE_BANK[other])

        loan_amount = random.randint(50000, 2000000)

        # APPROVAL LOGIC — biased toward men + Hindu, even at same credit
        base_prob = (credit_score - 500) / 350  # 0 to ~1
        base_prob *= 0.9 if income > 40000 else 0.6
        if gender == "Female":
            base_prob *= 0.55      # heavy penalty
        if religion == "Muslim":
            base_prob *= 0.65      # heavy penalty
        if religion == "Christian":
            base_prob *= 0.85

        approved = "Yes" if random.random() < base_prob else "No"

        # occasional missing income
        income_str = "" if random.random() < 0.04 else str(income)

        rows.append({
            "applicant_id": f"L{i+1:05d}",
            "first_name": first,
            "surname": surname,
            "gender": gender,
            "age": age,
            "religion": religion,
            "pincode": pincode,
            "income": income_str,
            "credit_score": credit_score,
            "loan_amount": loan_amount,
            "approved": approved
        })

    write_csv(OUT / "loan_data.csv", rows)
    print(f"  loan_data.csv         · {len(rows)} rows")


# ============================================================
# 2. HIRING DECISIONS — gender + college-tier bias
# ============================================================
def gen_hiring(n=820):
    rows = []
    for i in range(n):
        gender = random.choices(["Male", "Female"], weights=[78, 22])[0]
        first = random.choice(FIRST_M if gender == "Male" else FIRST_F)
        surname = random.choice(SURNAMES_HINDU + SURNAMES_MUSLIM)
        age = random.randint(21, 45)

        # tier biases by gender (skewed pipeline)
        tier = random.choices([1, 2, 3], weights=[20, 50, 30])[0]
        college = random.choice({1: COLLEGES_TIER1, 2: COLLEGES_TIER2, 3: COLLEGES_TIER3}[tier])

        years_exp = max(0, int(random.gauss(4, 3)))
        skill_match = round(random.uniform(0.3, 1.0), 2)

        # hobbies are a gender proxy in this fake data
        if gender == "Male":
            hobbies = random.choice(["Football, gaming", "Cricket, coding", "Bike rides", "Gym, gaming"])
        else:
            hobbies = random.choice(["Reading, painting", "Cooking, yoga", "Dancing, music", "Crafts, baking"])

        # SELECTION LOGIC — heavily biased
        score = 0.4 * skill_match + 0.3 * (years_exp / 10) + 0.3 * ((4 - tier) / 3)
        if gender == "Female":
            score *= 0.5

        selected = "Yes" if random.random() < score else "No"

        rows.append({
            "candidate_id": f"H{i+1:05d}",
            "first_name": first,
            "surname": surname,
            "gender": gender,
            "age": age,
            "college": college,
            "tier": tier,
            "years_experience": years_exp,
            "skill_match": skill_match,
            "hobbies": hobbies,
            "selected": selected
        })

    write_csv(OUT / "hiring_data.csv", rows)
    print(f"  hiring_data.csv       · {len(rows)} rows")


# ============================================================
# 3. ADMISSIONS — mostly fair, small regional skew
# ============================================================
def gen_admissions(n=1500):
    rows = []
    for i in range(n):
        gender = random.choices(["Male", "Female"], weights=[53, 47])[0]
        first = random.choice(FIRST_M if gender == "Male" else FIRST_F)
        surname = random.choice(SURNAMES_HINDU + SURNAMES_MUSLIM + SURNAMES_CHRISTIAN)

        region = random.choices(["Urban", "Rural"], weights=[64, 36])[0]
        board = random.choices(["CBSE", "ICSE", "State"], weights=[45, 15, 40])[0]
        coaching = random.choices(["Yes", "No"], weights=[58, 42])[0]

        marks = max(40, min(99, int(random.gauss(72, 12))))
        entrance_score = max(40, min(99, int(random.gauss(marks - 2, 8))))

        # MOSTLY FAIR — small score-based selection with tiny regional noise
        prob = (marks - 50) / 50
        if region == "Rural":
            prob *= 0.92  # mild
        admitted = "Yes" if random.random() < prob else "No"

        rows.append({
            "student_id": f"A{i+1:05d}",
            "first_name": first,
            "surname": surname,
            "gender": gender,
            "region": region,
            "board": board,
            "coaching": coaching,
            "marks": marks,
            "entrance_score": entrance_score,
            "admitted": admitted
        })

    write_csv(OUT / "admissions_data.csv", rows)
    print(f"  admissions_data.csv   · {len(rows)} rows")


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    print("Generating sample datasets…")
    gen_loans()
    gen_hiring()
    gen_admissions()
    print(f"\nAll saved in: {OUT}")
