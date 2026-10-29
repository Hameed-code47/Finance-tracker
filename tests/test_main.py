from src.main import (
    previous_month,
    is_valid_date,
    is_valid_amount,
    is_not_empty,
    monthly_total,
    filter_by_category,
    spending_trend,
)

SAMPLE_EXPENSES = [
    {"date": "2026-09-30", "category": "Food", "item": "Coffee", "amount": 5.0},
    {"date": "2026-09-15", "category": "Transport", "item": "Bus fare", "amount": 3.5},
    {"date": "2026-10-05", "category": "Food", "item": "Lunch", "amount": 12.0},
]


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


def test_monthly_total_adds_one_month_only():
    assert monthly_total(SAMPLE_EXPENSES, "2026-09") == 8.5
    assert monthly_total(SAMPLE_EXPENSES, "2026-10") == 12.0
    assert monthly_total(SAMPLE_EXPENSES, "2026-08") == 0


def test_filter_by_category_ignores_case():
    result = filter_by_category(SAMPLE_EXPENSES, "food")
    assert len(result) == 2
    assert all(e["category"] == "Food" for e in result)


def test_spending_trend():
    assert spending_trend(SAMPLE_EXPENSES, "2026-10") == 41.2
    assert spending_trend(SAMPLE_EXPENSES, "2026-09") is None