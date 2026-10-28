from pathlib import Path
import json
import argparse
from datetime import datetime
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

def is_valid_date(text):
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return False
    return parsed.strftime("%Y-%m-%d") == text

def is_valid_amount(value):
    try:
        number = float(value)
    except (ValueError, TypeError):
        return False
    return number > 0

def is_not_empty(text):
    return bool(text and text.strip())

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
    if not is_valid_date(date):
        print("Error: date must be a real date in YYYY-MM-DD format, e.g. 2026-10-27.")
        return False
    if not is_not_empty(category):
        print("Error: category cannot be empty.")
        return False
    if not is_not_empty(item):
        print("Error: item cannot be empty.")
        return False
    if not is_valid_amount(amount):
        print("Error: amount must be a number greater than 0.")
        return False

    amount = float(amount)
    category = category.strip()
    item = item.strip()

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
    return True


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
            amount = input("Amount: ")
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


def build_parser():
    parser = argparse.ArgumentParser(description="Personal finance tracker")
    subparsers = parser.add_subparsers(dest="command")

    add_parser = subparsers.add_parser("add", help="Add an expense")
    add_parser.add_argument("date", help="Date as YYYY-MM-DD")
    add_parser.add_argument("category", help="Category, e.g. Food")
    add_parser.add_argument("item", help="What you bought")
    add_parser.add_argument("amount", type=float, help="Amount, e.g. 8.5")

    list_parser = subparsers.add_parser("list", help="Show expenses")
    list_parser.add_argument("--category", help="Only show this category")

    summary_parser = subparsers.add_parser("summary", help="Show total spending for a month")
    summary_parser.add_argument("month", help="Month as YYYY-MM")

    trend_parser = subparsers.add_parser("trend", help="Compare a month with the month before")
    trend_parser.add_argument("month", help="Month as YYYY-MM")

    return parser


def main():
    args = build_parser().parse_args()
    if args.command == "add":
        add_expense(args.date, args.category, args.item, args.amount)
    elif args.command == "list":
        display_expenses(args.category)
    elif args.command == "summary":
        total = monthly_total(load_expenses(), args.month)
        print(f"Total for {args.month}: {total}")
    elif args.command == "trend":
        last = previous_month(args.month)
        trend = spending_trend(load_expenses(), args.month)
        if trend is None:
            print(f"No spending recorded in {last} to compare with.")
        elif trend >= 0:
            print(f"Spending in {args.month} is up {trend}% from {last}.")
        else:
            print(f"Spending in {args.month} is down {abs(trend)}% from {last}.")
    else:
        show_menu()


if __name__ == "__main__":
    main()