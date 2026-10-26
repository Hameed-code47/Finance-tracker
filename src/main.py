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

def filter_by_category(expenses, category):
    return [e for e in expenses if e["category"].lower() == category.lower()]

def monthly_total(expenses, month):
    return sum(e["amount"] for e in expenses if e["date"].startswith(month))

def previous_month(month):
    year, mon = map(int, month.split("-"))
    if mon == 1:
        return f"{year - 1}-12"
    return f"{year}-{mon - 1:02d}"

def spending_trend(expenses, month):
    this_total = monthly_total(expenses, month)
    last_total = monthly_total(expenses, previous_month(month))
    if last_total == 0:
        return None
    return round((this_total - last_total) / last_total * 100, 1)

def display_expenses(category=None):
    expenses = load_expenses()
    if category:
        expenses = filter_by_category(expenses, category)
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


def show_menu():
    while True:
        print("\n1. Show all expenses")
        print("2. Show expenses by category")
        print("3. Show monthly total")
        print("4. Add an expense")
        print("5. Show spending trend")
        print("6. Quit")
        choice = input("Choose an option: ")

        if choice == "1":
            display_expenses()
        elif choice == "2":
            category = input("Category: ")
            display_expenses(category)
        elif choice == "3":
            month = input("Month (YYYY-MM): ")
            total = monthly_total(load_expenses(), month)
            print(f"Total for {month}: {total}")
        elif choice == "4":
            date = input("Date (YYYY-MM-DD): ")
            category = input("Category: ")
            item = input("Item: ")
            amount = float(input("Amount: "))
            add_expense(date, category, item, amount)
        elif choice == "5":
            month = input("Month (YYYY-MM): ")
            last = previous_month(month)
            trend = spending_trend(load_expenses(), month)
            if trend is None:
                print(f"No spending recorded in {last} to compare with.")
            elif trend >= 0:
                print(f"Spending in {month} is up {trend}% from {last}.")
            else:
                print(f"Spending in {month} is down {abs(trend)}% from {last}.")
        elif choice == "6":
            break
        else:
            print("Invalid choice")


if __name__ == "__main__":
    show_menu()