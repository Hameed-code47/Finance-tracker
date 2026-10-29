from src.main import (
    previous_month,
    is_valid_date,
    is_valid_amount,
    is_not_empty,
    Expense,
    ExpenseTracker,
)

SAMPLE_EXPENSES = [
    {"date": "2026-09-30", "category": "Food", "item": "Coffee", "amount": 5.0},
    {"date": "2026-09-15", "category": "Transport", "item": "Bus fare", "amount": 3.5},
    {"date": "2026-10-05", "category": "Food", "item": "Lunch", "amount": 12.0},
]


def make_tracker(tmp_path):
    tracker = ExpenseTracker(tmp_path / "test_expenses.json")
    for e in SAMPLE_EXPENSES:
        tracker.add(Expense.from_dict(e))
    return tracker


def test_previous_month_regular():
    assert previous_month("2026-10") == "2026-09"


def test_previous_month_january_goes_to_previous_year():
    assert previous_month("2026-01") == "2025-12"


def test_is_valid_date_accepts_real_date():
    assert is_valid_date("2026-10-27") is True


def test_is_valid_date_rejects_bad_dates():
    assert is_valid_date("2026-13-45") is False
    assert is_valid_date("27-10-2026") is False
    assert is_valid_date("2026-1-5") is False


def test_is_valid_amount_accepts_positive_numbers():
    assert is_valid_amount("8.5") is True
    assert is_valid_amount(12) is True


def test_is_valid_amount_rejects_bad_values():
    assert is_valid_amount("-50") is False
    assert is_valid_amount("0") is False
    assert is_valid_amount("abc") is False
    assert is_valid_amount("") is False


def test_is_not_empty():
    assert is_not_empty("Food") is True
    assert is_not_empty("") is False
    assert is_not_empty("   ") is False
    assert is_not_empty(None) is False


def test_expense_dict_round_trip():
    data = {"date": "2026-10-29", "category": "Food", "item": "Lunch", "amount": 8.5}
    assert Expense.from_dict(data).to_dict() == data


def test_tracker_add_and_reload(tmp_path):
    data_file = tmp_path / "test_expenses.json"
    tracker = ExpenseTracker(data_file)
    tracker.add(Expense("2026-10-29", "Food", "Lunch", 8.5))

    reloaded = ExpenseTracker(data_file)
    assert len(reloaded.expenses) == 1
    assert reloaded.expenses[0].item == "Lunch"
    assert reloaded.expenses[0].amount == 8.5


def test_tracker_monthly_total(tmp_path):
    tracker = make_tracker(tmp_path)
    assert tracker.monthly_total("2026-09") == 8.5
    assert tracker.monthly_total("2026-08") == 0


def test_tracker_by_category(tmp_path):
    tracker = make_tracker(tmp_path)
    result = tracker.by_category("food")
    assert len(result) == 2


def test_tracker_trend(tmp_path):
    tracker = make_tracker(tmp_path)
    assert tracker.trend("2026-10") == 41.2
    assert tracker.trend("2026-09") is None

def test_tracker_category_totals(tmp_path):
    tracker = make_tracker(tmp_path)
    assert tracker.category_totals() == {"Food": 17.0, "Transport": 3.5}