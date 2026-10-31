from flask import Flask, render_template
from src.main import ExpenseTracker, DATA_FILE

app = Flask(__name__)


@app.route("/")
def home():
    return "Hello from Finance Tracker!"


@app.route("/expenses")
def expenses():
    tracker = ExpenseTracker(DATA_FILE)
    total = sum(e.amount for e in tracker.expenses)
    return render_template("expenses.html", expenses=tracker.expenses, total=total)


if __name__ == "__main__":
    app.run(debug=True)