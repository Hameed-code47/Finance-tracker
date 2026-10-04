from pathlib import Path
import json
from rich.console import Console
from rich.table import Table

DATA_FILE = Path(__file__).parent / "expenses.json"

def load_expenses():
    if DATA_FILE.exists():
        with open(DATA_FILE, "r") as file:
            return json.load(file)
    else:
        return []
    
def display_expenses():
    expenses = load_expenses()
    console = Console()
    table = Table(title="Your Expenses")
    table.add_column("Date")
    table.add_column("Category")
    table.add_column("Item")
    table.add_column("Amount")
    for expense in expenses:
        table.add_row(
            expense["date"],
            expense["category"],
            expense["item"],
            str(expense["amount"])
        )
    console.print(table)
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
# add_expense("2026-09-30", "Food", "Coffee", 5.00)
display_expenses()