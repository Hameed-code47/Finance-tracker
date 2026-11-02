from pathlib import Path
import sqlite3

import click
from flask import Flask, render_template
from sqlalchemy import event
from sqlalchemy.engine import Engine

from models import db, User, Expense
from src.main import ExpenseTracker, DATA_FILE


@event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(connection, connection_record):
    if isinstance(connection, sqlite3.Connection):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


app = Flask(__name__)

# Ensure Flask's local data folder exists.
Path(app.instance_path).mkdir(parents=True, exist_ok=True)

# Store the SQLite database inside the instance folder.
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///finance.db"

# Connect SQLAlchemy to this Flask application.
db.init_app(app)


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


@app.route("/expenses")
def expenses():
    # This page still uses JSON until we build the database workflow.
    tracker = ExpenseTracker(DATA_FILE)
    total = sum(e.amount for e in tracker.expenses)

    return render_template(
        "expenses.html",
        expenses=tracker.expenses,
        total=total,
    )


if __name__ == "__main__":
    app.run(debug=True)