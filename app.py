from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import hashlib
import hmac
import os
import re
import secrets
import smtplib
import sqlite3

import click
from dotenv import load_dotenv
from email_validator import EmailNotValidError, validate_email
from flask import (
    Flask,
    flash,
    get_flashed_messages,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_wtf.csrf import CSRFProtect
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import event, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.security import generate_password_hash
from email_service import send_email
from models import db, User, Expense
from flask import abort

load_dotenv(Path(__file__).resolve().parent / ".env")


@event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(connection, connection_record):
    if isinstance(connection, sqlite3.Connection):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


app = Flask(__name__)
Path(app.instance_path).mkdir(parents=True, exist_ok=True)

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL",
    "sqlite:///finance.db",
)
app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
app.config["APP_BASE_URL"] = os.environ["APP_BASE_URL"].rstrip("/")
app.config["RESET_TOKEN_MAX_AGE"] = 15 * 60
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

db.init_app(app)
csrf = CSRFProtect(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access your expenses."

reset_serializer = URLSafeTimedSerializer(
    app.config["SECRET_KEY"],
    salt="finance-tracker-password-reset",
)

RESET_MESSAGE = (
    "If an account exists for that email, "
    "you will receive a password-reset link."
)


# Shared account helpers.

def password_fingerprint(user, purpose):
    """Create a private marker that changes when the password changes."""
    message = (
        f"{purpose}:{user.id}:{user.password_hash}"
    ).encode("utf-8")

    return hmac.new(
        app.config["SECRET_KEY"].encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()


def normalize_email(email_text):
    info = validate_email(
        email_text.strip(),
        check_deliverability=False,
    )
    email = info.normalized.lower()

    if len(email) > 254:
        raise ValueError("Email address is too long.")

    return email


def password_error(password, confirmation):
    if len(password) < 15:
        return "Your password must contain at least 15 characters."

    if len(password) > 128:
        return "Your password is too long. Please shorten it."

    if not any(character.isdigit() for character in password):
        return "Your password must include at least one number."

    if not any(
        not character.isalnum() and not character.isspace()
        for character in password
    ):
        return (
            "Your password must include at least one symbol, "
            "such as !, @, or #."
        )

    if password != confirmation:
        return "The passwords do not match."

    return None


@login_manager.user_loader
def load_user(user_id):
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return None

    if user_id < 1 or user_id > 9223372036854775807:
        return None

    user = db.session.get(User, user_id)

    if user is None:
        return None

    saved_marker = session.get("password_marker")

    if not isinstance(saved_marker, str):
        return None

    if not hmac.compare_digest(
        saved_marker,
        password_fingerprint(user, "session"),
    ):
        return None

    return user


@app.cli.command("init-db")
def init_db():
    db.create_all()
    click.echo("Database tables created.")


@app.shell_context_processor
def shell_context():
    return {"db": db, "User": User, "Expense": Expense}


@app.template_filter("naira")
def format_naira(amount_kobo):
    naira, kobo = divmod(amount_kobo, 100)
    return f"₦{naira:,}.{kobo:02d}"


# Registration.

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "GET":
        messages = get_flashed_messages(
            category_filter=["registration"]
        )

        return render_template(
            "register.html",
            success=" ".join(messages),
            field_errors={},
        )

    email_text = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    confirmation = request.form.get("confirm_password", "")

    errors = {}
    email = None

    # Validate email.
    if not email_text:
        errors["email"] = "Enter your email address."
    else:
        try:
            email = normalize_email(email_text)
        except (EmailNotValidError, ValueError):
            errors["email"] = "Enter a valid email address."

    # Use the same password rules as password recovery.
    # Confirmation is checked separately below.
    if not password:
        errors["password"] = "Enter a password."
    else:
        policy_error = password_error(password, password)

        if policy_error:
            errors["password"] = policy_error

    # Validate confirmation independently.
    if not confirmation:
        errors["confirm_password"] = "Confirm your password."
    elif password != confirmation:
        errors["confirm_password"] = "The passwords do not match."

    if errors:
        return render_template(
            "register.html",
            field_errors=errors,
            error="Check the highlighted fields and try again.",
        ), 400

    existing_user = db.session.execute(
        db.select(User).where(User.email == email)
    ).scalar_one_or_none()

    if existing_user is not None:
        return render_template(
            "register.html",
            field_errors={
                "email": "An account with this email already exists."
            },
            error="We could not create your account. Check your email below.",
        ), 409

    user = User(email=email)
    user.set_password(password)

    try:
        db.session.add(user)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()

        return render_template(
            "register.html",
            field_errors={
                "email": (
                    "This email may already be registered. "
                    "Try logging in or resetting your password."
                )
            },
            error="The account could not be created.",
        ), 409
    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception("Could not create account")

        return render_template(
            "register.html",
            field_errors={},
            error="We could not save your account. Please try again.",
        ), 500

    flash("Your account was created. Please log in.", "registration")
    return redirect(url_for("login"))

# Login and logout.

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "GET":
        return render_template("login.html")

    password = request.form.get("password", "")
    error = "Email or password is incorrect."

    try:
        email = normalize_email(request.form.get("email", ""))
    except (EmailNotValidError, ValueError):
        return render_template("login.html", error=error), 401

    if not password or len(password) > 128:
        return render_template("login.html", error=error), 401

    user = db.session.execute(
        db.select(User).where(User.email == email)
    ).scalar_one_or_none()

    if user is None or not user.check_password(password):
        return render_template("login.html", error=error), 401

    session.clear()
    login_user(user, remember=False)
    session["password_marker"] = password_fingerprint(user, "session")
    return redirect(url_for("home"))


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    session.clear()
    flash("You have been logged out.", "auth")
    return redirect(url_for("login"))


# Password recovery.

def create_reset_token(user):
    return reset_serializer.dumps({
        "user_id": user.id,
        "marker": password_fingerprint(user, "reset"),
        "nonce": secrets.token_urlsafe(16),
    })


def user_from_reset_token(token):
    if not token or len(token) > 2048:
        return None

    try:
        data = reset_serializer.loads(
            token,
            max_age=app.config["RESET_TOKEN_MAX_AGE"],
        )
    except BadSignature:
        return None

    if not isinstance(data, dict):
        return None

    user_id = data.get("user_id")
    marker = data.get("marker")

    if type(user_id) is not int:
        return None

    if not 1 <= user_id <= 9223372036854775807:
        return None

    if not isinstance(marker, str):
        return None

    user = db.session.get(User, user_id)

    if user is None:
        return None

    if not hmac.compare_digest(
        marker,
        password_fingerprint(user, "reset"),
    ):
        return None

    return user


@app.after_request
def protect_reset_pages(response):
    if request.endpoint in {"forgot_password", "reset_password"}:
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"

    return response


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "GET":
        messages = get_flashed_messages(
            category_filter=["password_reset"]
        )
        return render_template(
            "password_recovery.html",
            mode="request",
            success=" ".join(messages),
        )

    try:
        email = normalize_email(request.form.get("email", ""))
    except (EmailNotValidError, ValueError):
        return render_template(
            "password_recovery.html",
            mode="request",
            error="Enter a valid email address.",
        ), 400

    user = db.session.execute(
        db.select(User).where(User.email == email)
    ).scalar_one_or_none()

    if user is not None:
        token = create_reset_token(user)
        reset_path = url_for("reset_password", token=token)
        reset_url = app.config["APP_BASE_URL"] + reset_path

        body = (
            "Hello,\n\n"
            "We received a request to reset your Finance Tracker "
            "password.\n\n"
            "Open this link to choose a new password:\n"
            f"{reset_url}\n\n"
            "This link expires in 15 minutes and cannot be reused "
            "after a successful password reset.\n\n"
            "If you did not request this, you can ignore this email. "
            "Your password has not changed.\n\n"
            "Finance Tracker"
        )

        try:
            send_email(
                user.email,
                "Reset your Finance Tracker password",
                body,
            )
        except (smtplib.SMTPException, OSError):
            # Avoid logging reset links, passwords, or SMTP credentials.
            app.logger.error("Password-reset email delivery failed.")

    # Give the same response whether the account exists or not.
    flash(RESET_MESSAGE, "password_reset")
    return redirect(url_for("forgot_password"))


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    user = user_from_reset_token(token)

    if user is None:
        return render_template(
            "password_recovery.html",
            mode="invalid",
        ), 400

    if request.method == "GET":
        return render_template(
            "password_recovery.html",
            mode="reset",
            token=token,
        )

    password = request.form.get("password", "")
    confirmation = request.form.get("confirm_password", "")
    error = password_error(password, confirmation)

    if error:
        return render_template(
            "password_recovery.html",
            mode="reset",
            token=token,
            error=error,
        ), 400

    old_hash = user.password_hash
    new_hash = generate_password_hash(password)

    # Update only if the password has not already changed.
    # This also prevents two simultaneous requests reusing one link.
    try:
        result = db.session.execute(
            update(User)
            .where(
                User.id == user.id,
                User.password_hash == old_hash,
            )
            .values(password_hash=new_hash)
            .execution_options(synchronize_session=False)
        )

        if result.rowcount != 1:
            db.session.rollback()
            return render_template(
                "password_recovery.html",
                mode="invalid",
            ), 400

        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        app.logger.error("Could not save password reset.")
        return render_template(
            "password_recovery.html",
            mode="reset",
            token=token,
            error="We could not save your password. Please try again.",
        ), 500

    # Other signed-in sessions fail their password-marker check
    # on their next request.
    logout_user()
    session.clear()

    return render_template(
        "password_recovery.html",
        mode="complete",
    )


# List the signed-in user's expenses.

@app.route("/expenses")
@login_required
def expenses():
    expense_list = db.session.execute(
        db.select(Expense)
        .where(Expense.user_id == current_user.id)
        .order_by(Expense.date.desc(), Expense.id.desc())
    ).scalars().all()

    total_kobo = sum(expense.amount_kobo for expense in expense_list)

    return render_template(
        "expenses.html",
        expenses=expense_list,
        total_kobo=total_kobo,
    )

def expense_today():
    # Use Nigerian time consistently, including after deployment.
    nigeria_time = timezone(timedelta(hours=1))
    return datetime.now(nigeria_time).date()


@app.context_processor
def expense_date_settings():
    return {"max_expense_date": expense_today().isoformat()}

# Shared validation for adding and editing expenses.

class ExpenseFormError(ValueError):
    def __init__(self, errors):
        self.errors = errors
        super().__init__("Check the highlighted fields and try again.")


def validate_expense_form(form):
    errors = {}

    date_text = form.get("date", "").strip()
    category = form.get("category", "").strip()
    item = form.get("item", "").strip()
    amount_text = form.get("amount", "").strip()

    expense_date = None
    amount_kobo = None

    if not date_text:
        errors["date"] = "Choose the date of this expense."
    else:
        try:
            expense_date = date.fromisoformat(date_text)

            if expense_date.isoformat() != date_text:
                raise ValueError
        except ValueError:
            errors["date"] = "Enter a real date in YYYY-MM-DD format."
        else:
            if expense_date > expense_today():
                errors["date"] = (
                    "An expense cannot have a future date. "
                    "Choose today or an earlier date."
                )
    if not category:
        errors["category"] = "Enter a category."
    elif len(category) > 50:
        errors["category"] = "Use no more than 50 characters."

    if not item:
        errors["item"] = "Describe what you spent money on."
    elif len(item) > 200:
        errors["item"] = "Use no more than 200 characters."

    if not amount_text:
        errors["amount"] = "Enter the amount you spent."
    elif not re.fullmatch(
        r"[0-9]{1,12}(?:\.[0-9]{1,2})?",
        amount_text,
    ):
        errors["amount"] = (
            "Enter a positive amount such as 1250.50. "
            "Use no commas or currency symbols, at most 12 digits "
            "before the decimal point, and 2 after it."
        )
    else:
        amount = Decimal(amount_text)

        if amount <= 0:
            errors["amount"] = "Amount must be greater than zero."
        else:
            amount_kobo = int(amount * 100)

    if errors:
        raise ExpenseFormError(errors)

    return {
        "date": expense_date,
        "category": category,
        "item": item,
        "amount_kobo": amount_kobo,
    }


def owned_expense_or_404(expense_id):
    # Keep values within SQLite's integer range.
    if not 1 <= expense_id <= 9223372036854775807:
        abort(404)

    expense = db.session.execute(
        db.select(Expense).where(
            Expense.id == expense_id,
            Expense.user_id == current_user.id,
        )
    ).scalar_one_or_none()

    if expense is None:
        abort(404)

    return expense


# Add an expense.

@app.route("/expenses/new", methods=["GET", "POST"])
@login_required
def add_expense():
    if request.method == "GET":
        messages = get_flashed_messages()

        return render_template(
            "add_expense.html",
            edit_mode=False,
            form_values={},
            success=" ".join(messages),
        )

    try:
        values = validate_expense_form(request.form)
    except ExpenseFormError as error:
        return render_template(
            "add_expense.html",
            edit_mode=False,
            form_values=request.form,
            field_errors=error.errors,
            error=str(error),
        ), 400

    expense = Expense(
        user_id=current_user.id,
        **values,
    )

    try:
        db.session.add(expense)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception("Could not save expense")

        return render_template(
            "add_expense.html",
            edit_mode=False,
            form_values=request.form,
            error="The expense could not be saved. Please try again.",
        ), 500

    flash("Expense saved successfully.")
    return redirect(url_for("add_expense"))


# Edit an expense belonging to the signed-in user.

@app.route(
    "/expenses/<int:expense_id>/edit",
    methods=["GET", "POST"],
)
@login_required
def edit_expense(expense_id):
    expense = owned_expense_or_404(expense_id)

    if request.method == "GET":
        form_values = {
            "date": expense.date.isoformat(),
            "category": expense.category,
            "item": expense.item,
            "amount": (
                f"{expense.amount_kobo // 100}."
                f"{expense.amount_kobo % 100:02d}"
            ),
        }

        return render_template(
            "add_expense.html",
            edit_mode=True,
            expense_id=expense_id,
            form_values=form_values,
        )

    try:
        values = validate_expense_form(request.form)
    except ExpenseFormError as error:
        return render_template(
            "add_expense.html",
            edit_mode=True,
            expense_id=expense_id,
            form_values=request.form,
            field_errors=error.errors,
            error=str(error),
        ), 400

    expense.date = values["date"]
    expense.category = values["category"]
    expense.item = values["item"]
    expense.amount_kobo = values["amount_kobo"]

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception("Could not update expense")

        return render_template(
            "add_expense.html",
            edit_mode=True,
            expense_id=expense_id,
            form_values=request.form,
            error="The changes could not be saved. Please try again.",
        ), 500

    flash("Expense updated successfully.", "expense")
    return redirect(url_for("expenses"))

# Confirm and delete an expense belonging to the signed-in user.

@app.route(
    "/expenses/<int:expense_id>/delete",
    methods=["GET", "POST"],
)
@login_required
def delete_expense(expense_id):
    expense = owned_expense_or_404(expense_id)

    if request.method == "GET":
        return render_template(
            "delete_expense.html",
            expense=expense,
        )

    try:
        db.session.delete(expense)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception("Could not delete expense")

        return render_template(
            "delete_expense.html",
            expense=expense,
            error="The expense could not be deleted. Please try again.",
        ), 500

    flash("Expense deleted successfully.", "expense")
    return redirect(url_for("expenses"))
# Dashboard and monthly summary.

@app.route("/", endpoint="home")
@app.route("/summary")
@login_required
def summary():
    selected_month = request.args.get(
        "month",
        date.today().strftime("%Y-%m"),
    ).strip()

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

    monthly_expenses = db.session.execute(
        db.select(Expense)
        .where(
            Expense.user_id == current_user.id,
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
        category = expense.category.strip().title()
        category_totals[category] = (
            category_totals.get(category, 0) + expense.amount_kobo
        )

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
        recent_expenses=monthly_expenses[:5],
    )


if __name__ == "__main__":
    app.run(debug=True)