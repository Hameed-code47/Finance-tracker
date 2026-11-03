from datetime import date
from decimal import Decimal
from pathlib import Path
import os
import re
import sqlite3

import click
from flask import (
    Flask,
    flash,
    get_flashed_messages,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from models import db, User, Expense

@event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(connection, connection_record):
    if isinstance(connection, sqlite3.Connection):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


app = Flask(__name__)

Path(app.instance_path).mkdir(parents=True, exist_ok=True)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///finance.db"
app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]

db.init_app(app)
csrf = CSRFProtect(app)


@app.cli.command("init-db")
def init_db():
    """Create any database tables that do not exist yet."""
    db.create_all()
    click.echo("Database tables created.")


@app.shell_context_processor
def shell_context():
    return {
        "db": db,
        "User": User,
        "Expense": Expense,
    }


@app.route("/")
def home():
    return "Hello from Finance Tracker!"

@app.template_filter("naira")
def format_naira(amount_kobo):
    naira, kobo = divmod(amount_kobo, 100)
    return f"₦{naira:,}.{kobo:02d}"


@app.route("/expenses")
def expenses():
    # Temporary demo account until login is implemented.
    user = db.session.execute(
        db.select(User).where(User.email == "demo@example.com")
    ).scalar_one_or_none()

    if user is None:
        return "Demo user not found. Create the sample user first.", 404

    expense_list = db.session.execute(
        db.select(Expense)
        .where(Expense.user_id == user.id)
        .order_by(Expense.date.desc(), Expense.id.desc())
    ).scalars().all()

    total_kobo = sum(expense.amount_kobo for expense in expense_list)

    return render_template(
        "expenses.html",
        expenses=expense_list,
        total_kobo=total_kobo,
    )


@app.route("/expenses/new", methods=["GET", "POST"])
def add_expense():
    if request.method == "GET":
        messages = get_flashed_messages()
        return render_template(
            "add_expense.html",
            success=" ".join(messages),
        )

    # Retrieve and trim the submitted values.
    date_text = request.form.get("date", "").strip()
    category = request.form.get("category", "").strip()
    item = request.form.get("item", "").strip()
    amount_text = request.form.get("amount", "").strip()

    # Validate the date.
    try:
        expense_date = date.fromisoformat(date_text)
        if expense_date.isoformat() != date_text:
            raise ValueError
    except ValueError:
        return render_template(
            "add_expense.html",
            error="Enter a real date in YYYY-MM-DD format.",
        ), 400

    # Validate the text fields.
    if not category or len(category) > 50:
        return render_template(
            "add_expense.html",
            error="Category must contain between 1 and 50 characters.",
        ), 400

    if not item or len(item) > 200:
        return render_template(
            "add_expense.html",
            error="Item must contain between 1 and 200 characters.",
        ), 400

    # Accept ordinary decimal amounts with at most two decimal places.
    # Limit the whole-number part to 12 digits.
    if not re.fullmatch(r"[0-9]{1,12}(?:\.[0-9]{1,2})?", amount_text):
        return render_template(
            "add_expense.html",
            error=(
                "Enter an amount such as 1250.50, without commas or "
                "a currency symbol. Use at most 12 digits before the "
                "decimal point and 2 after it."
            ),
        ), 400

    amount = Decimal(amount_text)

    if amount <= 0:
        return render_template(
            "add_expense.html",
            error="Amount must be greater than zero.",
        ), 400

    amount_kobo = int(amount * 100)

    # Temporary owner for local development.
    # Replace with the signed-in user when authentication is added.
    user = db.session.execute(
        db.select(User).where(User.email == "demo@example.com")
    ).scalar_one_or_none()

    if user is None:
        return render_template(
            "add_expense.html",
            error="The demo user is missing. Create the sample user first.",
        ), 400

    expense = Expense(
        user=user,
        date=expense_date,
        category=category,
        item=item,
        amount_kobo=amount_kobo,
    )

    try:
        db.session.add(expense)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception("Could not save expense")
        return render_template(
            "add_expense.html",
            error="The expense could not be saved. Please try again.",
        ), 500

    flash("Expense saved successfully.")
    return redirect(url_for("add_expense"))


if __name__ == "__main__":
    app.run(debug=True)