# Finance Tracker

[![Python tests](https://github.com/Hameed-code47/Finance-tracker/actions/workflows/tests.yml/badge.svg)](https://github.com/Hameed-code47/Finance-tracker/actions/workflows/tests.yml)

A personal expense tracker built with Python, available as a Flask web app and a command-line application.

Record expenses, explore category totals, and understand your monthly spending. The web app includes user accounts, private expense records, a dashboard, and email-based password recovery.

## Features

### Web app

- Register, log in, and log out.
- Keep each user's expenses separate.
- Add expenses with date, category, item, and amount validation.
- Store amounts as integer kobo and display them in Nigerian naira.
- View expense history and all-time spending totals.
- Select a month to view spending totals and category breakdowns.
- View a category bar chart and recent expenses on the dashboard.
- Use responsive pages on desktop and smaller screens.
- Show or hide passwords using visibility buttons.
- Request password-reset links that expire after 15 minutes.
- Reject used reset links and invalidate existing login sessions after a reset.
- Protect forms with CSRF tokens and store hashed passwords.

### Command-line app

- Add expenses through an interactive menu or one-line commands.
- List expenses and filter them by category.
- View monthly totals and month-over-month spending trends.
- Display category spending in a coloured terminal chart.
- Save expenses to a JSON file.
- Use a terminal interface built with [Rich](https://github.com/Textualize/rich).

The CLI and web app currently use separate storage. CLI JSON records are not automatically imported into the web app's database.

## Screenshots

### CLI expense table

![CLI expense table](screenshots/table.png)

### CLI spending chart

![CLI spending chart](screenshots/chart.png)

## Requirements

- Python 3.14, the version used for current development and automated testing.
- Git to clone the repository.
- A web browser for the Flask app.
- A Mailtrap Email Sandbox account to test password-reset emails.

The web chart loads Chart.js from a CDN and requires an internet connection. Category totals remain available in a table if the chart cannot load.

## Installation

Clone the repository and create a virtual environment:

```powershell
git clone https://github.com/Hameed-code47/Finance-tracker.git
cd Finance-tracker
python -m venv venv
```

Activate it in Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

On macOS or Linux:

```bash
source venv/bin/activate
```

Install the dependencies:

```bash
python -m pip install -r requirements.txt
```

## Run the web app locally

### 1. Create your environment file

Create a file named `.env` in the project root, beside `app.py`.

Generate a secret key:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the generated value into `SECRET_KEY` below. Replace the Mailtrap placeholders with the SMTP credentials from your sandbox:

```dotenv
SECRET_KEY=replace_with_your_generated_secret_key
MAIL_SERVER=sandbox.smtp.mailtrap.io
MAIL_PORT=2525
MAIL_USERNAME=replace_with_your_mailtrap_username
MAIL_PASSWORD=replace_with_your_full_mailtrap_password
MAIL_FROM=Finance Tracker <no-reply@example.com>
APP_BASE_URL=http://127.0.0.1:5000
```

Use the full Mailtrap password, not its masked display.

Keep the same secret key between restarts. Changing it invalidates existing signed sessions and password-reset links.

The `.env` file contains private credentials and must remain excluded from Git. Never commit it.

For normal local use, leave `DATABASE_URL` unset. The app defaults to SQLite at `instance/finance.db`.

### 2. Create the database tables

```bash
python -m flask --app app init-db
```

This creates missing tables. It does not migrate changes to existing table definitions.

### 3. Start Flask

```bash
python -m flask --app app run --debug
```

Open:

http://127.0.0.1:5000/register

Create an account, log in, and add your first expense.

The debug server is for local development only.

## Using the web app

| Page | Purpose |
| --- | --- |
| `/register` | Create an account |
| `/login` | Log in |
| `/` | View the monthly dashboard and recent expenses |
| `/expenses` | View your expense history and all-time total |
| `/expenses/new` | Add an expense |
| `/summary` | View monthly totals and category spending |
| `/forgot-password` | Request a password-reset link |

Passwords must contain at least 15 characters, including a number and a symbol.

Enter expense amounts in naira, such as `1250.50`. The app stores this as `125050` kobo.

## Testing password recovery with Mailtrap

Mailtrap Email Sandbox captures development emails. It does not deliver these reset messages to users' real inboxes.

1. Register a test account in the web app.
2. Open the login page and select **Forgot password?**
3. Enter the registered email address.
4. Open your Mailtrap sandbox and find the reset email.
5. Open its reset link on the computer running Flask.
6. Choose and confirm a new password.
7. Log in with the new password.

Links expire after 15 minutes. After a successful reset, previously issued reset links for that account become invalid, and existing login sessions lose access on their next request.

For public use, the app still needs production email delivery and a publicly accessible HTTPS base URL.

## CLI usage

The CLI does not require Mailtrap configuration or web database setup.

### Interactive menu

```bash
python src/main.py
```

### One-line commands

| Command | What it does |
| --- | --- |
| `python src/main.py add 2026-10-29 Food Lunch 8.5` | Add an expense: date, category, item, amount |
| `python src/main.py add 2026-10-29 Food "Iced coffee" 4` | Add an item whose name contains spaces |
| `python src/main.py list` | Show all expenses |
| `python src/main.py list --category food` | Show one category only |
| `python src/main.py summary 2026-10` | Show total spending for a month |
| `python src/main.py trend 2026-10` | Compare a month with the previous month |
| `python src/main.py chart` | Show a category spending bar chart |

## Automated tests

Run the complete suite:

```bash
python -m pytest -v
```

Run only the web tests:

```bash
python -m pytest tests/test_web.py -v
```

The current suite contains **31 tests**:

- 14 CLI tests.
- 17 web test cases covering protected routes, login and logout, CSRF protection, user-specific expenses, and password recovery.

Web tests use an isolated, in-memory SQLite database and a fake email sender. They do not require a `.env` file or Mailtrap credentials, and do not send emails.

The test setup checks the database connection before creating or deleting tables, refusing to continue if it is not the expected in-memory database.

### GitHub Actions

The workflow in `.github/workflows/tests.yml` installs dependencies and runs the test suite on pushes and pull requests. It can also be started manually from the repository's Actions tab.

[View automated test runs](https://github.com/Hameed-code47/Finance-tracker/actions)

## Project structure

```text
Finance-tracker/
├── .github/
│   └── workflows/
│       └── tests.yml           # GitHub Actions test workflow
├── instance/
│   └── finance.db              # Local SQLite database; ignored by Git
├── screenshots/
│   ├── chart.png
│   └── table.png
├── src/
│   ├── main.py                 # CLI and expense-tracking classes
│   └── expenses.json           # Local CLI expense data
├── templates/
│   ├── add_expense.html
│   ├── expenses.html
│   ├── login.html
│   ├── password_recovery.html
│   ├── register.html
│   └── summary.html            # Dashboard and monthly summary
├── tests/
│   ├── conftest.py             # Isolated web-test setup
│   ├── test_main.py            # CLI tests
│   └── test_web.py             # Web tests
├── .env                        # Local configuration; ignored by Git
├── .gitignore
├── app.py                      # Flask routes and application setup
├── design.md
├── email_service.py            # SMTP email helper
├── models.py                   # User and Expense database models
├── requirements.txt
├── LICENSE
└── README.md
```

Local files such as `.env` and `instance/finance.db` are created during setup and are not included in the repository.

## Current status and roadmap

The CLI and local Flask web app are implemented. Automated tests run locally and through GitHub Actions.

Planned work:

- Additional authentication and password-reset protections, including request rate limits.
- Production deployment with HTTPS, persistent storage, and real email delivery.
- Database migrations.
- Shared templates and styles to reduce repeated page code.
- Web app screenshots and expanded documentation.
- AI-powered spending insights.

Passing tests verify the behaviours covered by the suite; they are not a complete security audit.

## License

See the [LICENSE](LICENSE) file.