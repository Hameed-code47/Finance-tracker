# Finance Tracker — Design

## Expense Data Model
Each expense record will store:
- date — when the expense happened
- category — broad grouping (e.g. Food, Transport, Bills)
- item — specific description (e.g. Coffee, Bus fare)
- amount — cost in Naira
## Features
- Add a new expense and save it to the data file
- View all expenses in a clean table
- Filter expenses by category
- Show monthly summary (totals per category, per month)
- Show spending trend (this month vs last month, % change)
- Run everything through CLI commands (add, list, summary, trend)
- Validate input (reject bad dates, negative amounts, empty fields)
- Show clear error messages when something's invalid
## Web App — Version 2

### Goal
Turn the CLI finance tracker into a Flask web app where each
user can record and review their own expenses.

### Pages and Routes

| Page or action | URL | Methods | Purpose |
|---|---|---|---|
| Dashboard | / | GET | Monthly total, category breakdown, recent expenses |
| Expense list | /expenses | GET | View expenses and filter by category or month |
| Add expense | /expenses/new | GET, POST | Display a form and save an expense |
| Edit expense | /expenses/<int:expense_id>/edit | GET, POST | Display and update an expense |
| Delete expense | /expenses/<int:expense_id>/delete | POST | Delete an expense after confirmation |
| Register | /register | GET, POST | Create a user account |
| Login | /login | GET, POST | Sign into an account |
| Logout | /logout | POST | End the session |

### Navigation
- Overview
- Expenses
- Add expense
- Login/Register when signed out
- Logout when signed in

### Database

Use SQLite with Flask-SQLAlchemy.

#### User
- id: integer primary key
- email: required and unique
- password_hash: required; never store plain-text passwords

#### Expense
- id: integer primary key
- user_id: required foreign key referencing User
- date: required calendar date
- category: required text
- item: required text describing the expense
- amount_kobo: required positive integer

### Relationships and Access
- One user can have many expenses.
- Each expense belongs to exactly one user.
- Expense pages require login once authentication is implemented.
- Users can only view, edit, or delete their own expenses.
- Ownership must be checked on the server.

### Money
- Display amounts in naira.
- Store amounts as integer kobo.
- Example: NGN 1,250.50 is stored as 125050 kobo.
- Reject zero, negative, non-finite amounts, and fractions of a kobo.

### Dashboard Layout
1. Month selector and Add expense button
2. Total spending for the selected month
3. Spending by category
4. Monthly spending trend
5. Recent expenses

### Development Order
1. Define pages, routes, and database models.
2. Connect SQLite and verify the tables.
3. Build the expense form and database-backed expense list.
4. Add summaries and charts.
5. Implement authentication and enforce user ownership before deployment.
6. Test and polish the web app.
7. Add AI features later.

### Existing CLI
Keep the existing CLI working while developing the web app.
The current JSON expenses will not be imported automatically.