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
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from calendar import monthrange
from email_validator import validate_email, EmailNotValidError
from models import db, User, Expense
from flask_login import LoginManager

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

login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return None

    if user_id < 1 or user_id > 9223372036854775807:
        return None

    return db.session.get(User, user_id)


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


@app.route("/", endpoint="home")
@app.route("/summary")
def summary():
    # Default to the current month.
    selected_month = request.args.get(
        "month", date.today().strftime("%Y-%m")
    ).strip()

    # Validate the month before querying the database.
    try:
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}", selected_month):
            raise ValueError

        year, month = map(int, selected_month.split("-"))
        first_day = date(year, month, 1)
        last_day = date(year, month, monthrange(year, month)[1])
    except ValueError:
        return render_template(
            "summary.html",
            error="Choose a valid month in YYYY-MM format.",
            selected_month="",
        ), 400

    # Temporary demo account until login is implemented.
    user = db.session.execute(
        db.select(User).where(User.email == "demo@example.com")
    ).scalar_one_or_none()

    if user is None:
        return "Demo user not found. Create the sample user first.", 404

    monthly_expenses = db.session.execute(
        db.select(Expense)
        .where(
            Expense.user_id == user.id,
            Expense.date >= first_day,
            Expense.date <= last_day,
        )
        .order_by(Expense.date.desc(), Expense.id.desc())
    ).scalars().all()

    total_kobo = sum(
        expense.amount_kobo for expense in monthly_expenses
    )

    category_totals = {}

    for expense in monthly_expenses:
        # Group "food", "Food", and "FOOD" together.
        category = expense.category.strip().title()
        category_totals[category] = (
            category_totals.get(category, 0) + expense.amount_kobo
        )

    # Highest spending first; alphabetical order breaks ties.
    ranked_categories = sorted(
        category_totals.items(),
        key=lambda pair: (-pair[1], pair[0]),
    )

    return render_template(
        "summary.html",
        selected_month=selected_month,
        month_label=first_day.strftime("%B %Y"),
        total_kobo=total_kobo,
        expense_count=len(monthly_expenses),
        categories=ranked_categories,
    )
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        messages = get_flashed_messages(category_filter=["registration"])

        return render_template(
            "register.html",
            success=" ".join(messages),
        )

    email_text = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    confirmation = request.form.get("confirm_password", "")

    # Validate the email and use lowercase for account lookups.
    try:
        email_info = validate_email(
            email_text,
            check_deliverability=False,
        )
        email = email_info.normalized.lower()
    except EmailNotValidError:
        return render_template(
            "register.html",
            error="Enter a valid email address.",
        ), 400

    if len(email) > 254:
        return render_template(
            "register.html",
            error="Your email address is too long.",
        ), 400

    # Check the password requirements.
    if len(password) < 15:
        return render_template(
            "register.html",
            error="Your password must contain at least 15 characters.",
        ), 400

    if len(password) > 128:
        return render_template(
            "register.html",
            error="Your password is too long. Please shorten it.",
        ), 400

    if not any(character.isdigit() for character in password):
        return render_template(
            "register.html",
            error="Your password must include at least one number.",
        ), 400

    if not any(
        not character.isalnum() and not character.isspace()
        for character in password
    ):
        return render_template(
            "register.html",
            error="Your password must include at least one symbol, such as !, @, or #.",
        ), 400

    if password != confirmation:
        return render_template(
            "register.html",
            error="The passwords do not match.",
        ), 400

    # Check whether this email is already registered.
    existing_user = db.session.execute(
        db.select(User).where(User.email == email)
    ).scalar_one_or_none()

    if existing_user is not None:
        return render_template(
            "register.html",
            error="An account with this email already exists.",
        ), 409

    # Create the account using the model's password-hashing method.
    user = User(email=email)
    user.set_password(password)

    try:
        db.session.add(user)
        db.session.commit()
    except IntegrityError:
        # A duplicate submission can reach the database after our check.
        db.session.rollback()

        return render_template(
            "register.html",
            error="The account could not be created. This email may already be registered.",
        ), 409
    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception("Could not create account")

        return render_template(
            "register.html",
            error="We could not save your account. Please try again.",
        ), 500

    flash("Your account was created successfully.", "registration")
    return redirect(url_for("register"))
if __name__ == "__main__":
    app.run(debug=True)