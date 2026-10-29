from pathlib import Path
import json
import argparse
from datetime import datetime
from rich.console import Console
from rich.table import Table

DATA_FILE = Path(__file__).parent / "expenses.json"


class Expense:
    def __init__(self, date, category, item, amount):
        self.date = date
        self.category = category
        self.item = item
        self.amount = amount

    def to_dict(self):
        return {
            "date": self.date,
            "category": self.category,
            "item": self.item,
            "amount": self.amount,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(data["date"], data["category"], data["item"], data["amount"])


class ExpenseTracker:
    def __init__(self, data_file):
        self.data_file = data_file
        self.expenses = self.load()

    def load(self):
        if self.data_file.exists():
            with open(self.data_file, "r") as file:
                return [Expense.from_dict(item) for item in json.load(file)]
        return []

    def save(self):
        with open(self.data_file, "w") as file:
            json.dump([e.to_dict() for e in self.expenses], file, indent=2)

    def add(self, expense):
        self.expenses.append(expense)
        self.save()

    def monthly_total(self, month):
        return sum(e.amount for e in self.expenses if e.date.startswith(month))

    def by_category(self, category):
        return [e for e in self.expenses if e.category.lower() == category.lower()]

    def trend(self, month):
        this_total = self.monthly_total(month)
        last_total = self.monthly_total(previous_month(month))
        if last_total == 0:
            return None
        return round((this_total - last_total) / last_total * 100, 1)

    def category_totals(self):
        totals = {}
        for e in self.expenses:
            name = e.category.title()
            totals[name] = totals.get(name, 0) + e.amount
        return totals

def previous_month(month):
    year, mon = map(int, month.split("-"))
    if mon == 1:
        return f"{year - 1}-12"
    return f"{year}-{mon - 1:02d}"

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


def display_expenses(expenses):
    console = Console()
    total = sum(e.amount for e in expenses)
    table = Table(
        title="Your Expenses",
        header_style="bold cyan",
        caption=f"Items: {len(expenses)}   Total: ${total:.2f}",
        caption_style="bold green",
    )
    table.add_column("Date", style="dim")
    table.add_column("Category", style="magenta")
    table.add_column("Item")
    table.add_column("Amount", justify="right", style="green")
    for e in expenses:
        table.add_row(e.date, e.category, e.item, f"${e.amount:.2f}")
    console.print(table)

def display_chart(totals):
    console = Console()
    if not totals:
        console.print("No expenses to chart.")
        return
    biggest = max(totals.values())
    console.print("[bold cyan]Spending by category[/bold cyan]")
    for category, amount in sorted(totals.items(), key=lambda pair: pair[1], reverse=True):
        bar = "█" * max(1, round(amount / biggest * 30))
        console.print(f"{category:<12} [green]{bar}[/green] ${amount:.2f}")

def add_expense(tracker, date, category, item, amount):
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

    expense = Expense(date, category.strip(), item.strip(), float(amount))
    tracker.add(expense)
    print(f"Added: {expense.item} - ${expense.amount:.2f} ({expense.category})")
    return True


def print_trend(tracker, month):
    last = previous_month(month)
    trend = tracker.trend(month)
    if trend is None:
        print(f"No spending recorded in {last} to compare with.")
    elif trend >= 0:
        print(f"Spending in {month} is up {trend}% from {last}.")
    else:
        print(f"Spending in {month} is down {abs(trend)}% from {last}.")


def show_menu(tracker):
    while True:
        print("\n1. Show all expenses")
        print("2. Show expenses by category")
        print("3. Show monthly total")
        print("4. Add an expense")
        print("5. Show spending trend")
        print("6. Show spending chart")
        print("7. Quit")
        choice = input("Choose an option: ")

        if choice == "1":
            display_expenses(tracker.expenses)
        elif choice == "2":
            category = input("Category: ")
            display_expenses(tracker.by_category(category))
        elif choice == "3":
            month = input("Month (YYYY-MM): ")
            print(f"Total for {month}: {tracker.monthly_total(month)}")
        elif choice == "4":
            date = input("Date (YYYY-MM-DD): ")
            category = input("Category: ")
            item = input("Item: ")
            amount = input("Amount: ")
            add_expense(tracker, date, category, item, amount)
        elif choice == "5":
            month = input("Month (YYYY-MM): ")
            print_trend(tracker, month)
        elif choice == "6":
            display_chart(tracker.category_totals())
        elif choice == "7":
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

    subparsers.add_parser("chart", help="Show spending by category as a bar chart")

    return parser


def main():
    tracker = ExpenseTracker(DATA_FILE)
    args = build_parser().parse_args()
    if args.command == "add":
        add_expense(tracker, args.date, args.category, args.item, args.amount)
    elif args.command == "list":
        if args.category:
            display_expenses(tracker.by_category(args.category))
        else:
            display_expenses(tracker.expenses)
    elif args.command == "summary":
        print(f"Total for {args.month}: {tracker.monthly_total(args.month)}")
    elif args.command == "trend":
        print_trend(tracker, args.month)
    elif args.command == "chart":
        display_chart(tracker.category_totals())
    else:
        show_menu(tracker)


if __name__ == "__main__":
    main()