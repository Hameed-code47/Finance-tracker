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