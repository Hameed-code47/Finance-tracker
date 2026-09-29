from pathlib import Path
import json
DATA_FILE = Path(__file__).parent / "expenses.json"

def add_expense(date, category, item, amount):
    expense = {
        "date": date,
        "category": category,
        "item": item,
        "amount": amount
    }
    if DATA_FILE.exists():
        with open(DATA_FILE, "r") as file:
            expenses = json.load(file)
    else:
        expenses = []
    expenses.append(expense)

    with open(DATA_FILE, "w") as file:
        json.dump(expenses, file, indent=2)

    print(f"Added: {item} - ${amount:.2f} ({category})")
add_expense("2026-09-30", "Food", "Coffee", 5.00)
add_expense("2026-09-30", "Transport", "Bus fare", 2.00)