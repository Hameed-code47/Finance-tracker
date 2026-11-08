from html.parser import HTMLParser
from urllib.parse import urlsplit
import re

import pytest


ALICE_EMAIL = "alice@example.com"
ALICE_PASSWORD = "AliceTestingPassword123!"
NEW_PASSWORD = "ChangedTestingPassword789!"


class CSRFParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.token = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)

        if (
            tag == "input"
            and attributes.get("name") == "csrf_token"
        ):
            self.token = attributes.get("value")


def post_form(client, page, data, target=None):
    """Read a real CSRF token, then submit the form."""
    response = client.get(page)
    assert response.status_code == 200

    parser = CSRFParser()
    parser.feed(response.get_data(as_text=True))

    assert parser.token, f"No CSRF token found on {page}"

    return client.post(
        target or page,
        data={
            **data,
            "csrf_token": parser.token,
        },
    )


def login(client, password=ALICE_PASSWORD):
    return post_form(
        client,
        "/login",
        {
            "email": ALICE_EMAIL,
            "password": password,
        },
    )


def request_reset(client, web_module):
    response = post_form(
        client,
        "/forgot-password",
        {"email": ALICE_EMAIL},
    )

    assert response.status_code == 302
    assert len(web_module.test_sent_emails) == 1

    email = web_module.test_sent_emails[0]
    assert email["to"] == ALICE_EMAIL

    match = re.search(
        r"http://localhost/reset-password/[^\s]+",
        email["body"],
    )
    assert match, "No reset link found in the captured email"

    return urlsplit(match.group(0)).path


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/expenses",
        "/expenses/new",
        "/summary",
    ],
)
def test_private_pages_require_login(web_client, path):
    response = web_client.get(path)

    assert response.status_code == 302
    assert urlsplit(response.headers["Location"]).path == "/login"


def test_login_and_logout(web_client):
    response = login(web_client)

    assert response.status_code == 302
    assert web_client.get("/expenses").status_code == 200

    response = post_form(
        web_client,
        "/",
        {},
        target="/logout",
    )

    assert response.status_code == 302
    assert web_client.get("/expenses").status_code == 302


def test_wrong_password_does_not_log_user_in(web_client):
    response = login(
        web_client,
        password="DefinitelyWrongPassword123!",
    )

    assert response.status_code == 401
    assert web_client.get("/expenses").status_code == 302


def test_post_without_csrf_token_is_rejected(web_client):
    response = web_client.post(
        "/login",
        data={
            "email": ALICE_EMAIL,
            "password": ALICE_PASSWORD,
        },
    )

    assert response.status_code == 400
    assert web_client.get("/expenses").status_code == 302


def test_expense_list_only_shows_signed_in_users_data(web_client):
    login(web_client)

    response = web_client.get("/expenses")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Alice private lunch" in page
    assert "Bob private purchase" not in page
    assert "BobOnlyCategory" not in page
    assert "₦1,250.50" in page
    assert "₦9,000.00" not in page


def test_monthly_summary_only_counts_signed_in_users_data(web_client):
    login(web_client)

    response = web_client.get("/summary?month=2026-01")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "₦1,250.50" in page
    assert "BobOnlyCategory" not in page
    assert "₦9,000.00" not in page


def test_new_expense_belongs_to_signed_in_user(
    web_client,
    web_module,
):
    login(web_client)

    with web_module.app.app_context():
        bob = web_module.db.session.execute(
            web_module.db.select(web_module.User).where(
                web_module.User.email == "bob@example.com"
            )
        ).scalar_one()

        bob_id = bob.id

    response = post_form(
        web_client,
        "/expenses/new",
        {
            "date": "2026-01-20",
            "category": "Transport",
            "item": "Ownership test bus fare",
            "amount": "500.25",
            # Trying to assign the expense to Bob must have no effect.
            "user_id": str(bob_id),
        },
    )

    assert response.status_code == 302

    with web_module.app.app_context():
        expense = web_module.db.session.execute(
            web_module.db.select(web_module.Expense).where(
                web_module.Expense.item == "Ownership test bus fare"
            )
        ).scalar_one()

        assert expense.amount_kobo == 50025
        assert expense.user.email == ALICE_EMAIL


def test_invalid_amount_does_not_save_an_expense(
    web_client,
    web_module,
):
    login(web_client)

    response = post_form(
        web_client,
        "/expenses/new",
        {
            "date": "2026-01-20",
            "category": "Food",
            "item": "Invalid amount test",
            "amount": "-10",
        },
    )

    assert response.status_code == 400

    with web_module.app.app_context():
        expense = web_module.db.session.execute(
            web_module.db.select(web_module.Expense).where(
                web_module.Expense.item == "Invalid amount test"
            )
        ).scalar_one_or_none()

        assert expense is None


def test_unknown_email_receives_same_reset_message(
    web_client,
    web_module,
):
    response = post_form(
        web_client,
        "/forgot-password",
        {"email": "unknown@example.com"},
    )

    assert response.status_code == 302

    unknown_page = web_client.get(
        response.headers["Location"]
    ).get_data(as_text=True)

    assert web_module.RESET_MESSAGE in unknown_page
    assert web_module.test_sent_emails == []

    response = post_form(
        web_client,
        "/forgot-password",
        {"email": ALICE_EMAIL},
    )

    known_page = web_client.get(
        response.headers["Location"]
    ).get_data(as_text=True)

    assert web_module.RESET_MESSAGE in known_page
    assert len(web_module.test_sent_emails) == 1


def test_password_reset_changes_password_and_rejects_reuse(
    web_client,
    web_module,
):
    reset_path = request_reset(web_client, web_module)

    response = post_form(
        web_client,
        reset_path,
        {
            "password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
    )

    assert response.status_code == 200
    assert "Password updated" in response.get_data(as_text=True)

    with web_module.app.app_context():
        user = web_module.db.session.execute(
            web_module.db.select(web_module.User).where(
                web_module.User.email == ALICE_EMAIL
            )
        ).scalar_one()

        assert user.check_password(NEW_PASSWORD)
        assert not user.check_password(ALICE_PASSWORD)

    assert web_client.get(reset_path).status_code == 400

    assert login(web_client, ALICE_PASSWORD).status_code == 401
    assert login(web_client, NEW_PASSWORD).status_code == 302


def test_expired_reset_link_is_rejected(
    web_client,
    web_module,
    monkeypatch,
):
    reset_path = request_reset(web_client, web_module)

    # Force expiry without waiting 15 minutes.
    monkeypatch.setitem(
        web_module.app.config,
        "RESET_TOKEN_MAX_AGE",
        -1,
    )

    response = web_client.get(reset_path)

    assert response.status_code == 400
    assert "Link unavailable" in response.get_data(as_text=True)


def test_modified_reset_link_is_rejected(web_client, web_module):
    reset_path = request_reset(web_client, web_module)
    token = reset_path.rsplit("/", 1)[1]

    replacement = "B" if token[0] == "A" else "A"
    changed_token = replacement + token[1:]

    response = web_client.get(
        f"/reset-password/{changed_token}"
    )

    assert response.status_code == 400


def test_mismatched_passwords_do_not_consume_reset_link(
    web_client,
    web_module,
):
    reset_path = request_reset(web_client, web_module)

    response = post_form(
        web_client,
        reset_path,
        {
            "password": NEW_PASSWORD,
            "confirm_password": "DifferentTestingPassword123!",
        },
    )

    assert response.status_code == 400
    assert "The passwords do not match." in response.get_data(
        as_text=True
    )

    # The user can correct the mistake using the same link.
    assert web_client.get(reset_path).status_code == 200

    with web_module.app.app_context():
        user = web_module.db.session.execute(
            web_module.db.select(web_module.User).where(
                web_module.User.email == ALICE_EMAIL
            )
        ).scalar_one()

        assert user.check_password(ALICE_PASSWORD)


def test_reset_invalidates_an_existing_login(
    web_client,
    web_module,
):
    # Browser one is already logged in.
    login(web_client)
    assert web_client.get("/expenses").status_code == 200

    # Browser two completes the password reset.
    other_browser = web_module.app.test_client()
    reset_path = request_reset(other_browser, web_module)

    response = post_form(
        other_browser,
        reset_path,
        {
            "password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
    )

    assert response.status_code == 200

    # Browser one's old session must no longer grant access.
    response = web_client.get("/expenses")

    assert response.status_code == 302
    assert urlsplit(response.headers["Location"]).path == "/login"
def find_test_expense_id(web_module, item):
    with web_module.app.app_context():
        expense = web_module.db.session.execute(
            web_module.db.select(web_module.Expense).where(
                web_module.Expense.item == item
            )
        ).scalar_one()

        return expense.id


def test_edit_own_expense(web_client, web_module):
    login(web_client)

    expense_id = find_test_expense_id(
        web_module,
        "Alice private lunch",
    )
    path = f"/expenses/{expense_id}/edit"

    response = web_client.get(path)
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'value="Alice private lunch"' in page
    assert 'value="1250.50"' in page

    response = post_form(
        web_client,
        path,
        {
            "date": "2026-02-15",
            "category": "Transport",
            "item": "Updated bus fare",
            "amount": "650.75",
        },
    )

    assert response.status_code == 302

    with web_module.app.app_context():
        expense = web_module.db.session.get(
            web_module.Expense,
            expense_id,
        )

        assert expense.item == "Updated bus fare"
        assert expense.category == "Transport"
        assert expense.date.isoformat() == "2026-02-15"
        assert expense.amount_kobo == 65075
        assert expense.user.email == ALICE_EMAIL

        # Editing must not create another expense.
        records = web_module.db.session.execute(
            web_module.db.select(web_module.Expense)
        ).scalars().all()

        assert len(records) == 2

    page = web_client.get("/expenses").get_data(as_text=True)
    assert "Expense updated successfully." in page
    assert "Updated bus fare" in page
    assert "₦650.75" in page


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_cannot_edit_another_users_expense(
    web_client,
    web_module,
    method,
):
    login(web_client)

    expense_id = find_test_expense_id(
        web_module,
        "Bob private purchase",
    )
    path = f"/expenses/{expense_id}/edit"

    if method == "GET":
        response = web_client.get(path)
    else:
        # Submit a valid CSRF token so this checks ownership,
        # rather than merely being rejected by CSRF protection.
        response = post_form(
            web_client,
            "/expenses/new",
            {
                "date": "2026-01-20",
                "category": "Changed",
                "item": "Attempted modification",
                "amount": "1.00",
            },
            target=path,
        )

    assert response.status_code == 404
    assert "Bob private purchase" not in response.get_data(as_text=True)

    with web_module.app.app_context():
        expense = web_module.db.session.get(
            web_module.Expense,
            expense_id,
        )

        assert expense.item == "Bob private purchase"
        assert expense.amount_kobo == 900000
        assert expense.user.email == "bob@example.com"


def test_edit_missing_expense_returns_404(web_client):
    login(web_client)

    response = web_client.get("/expenses/999999/edit")

    assert response.status_code == 404


@pytest.mark.parametrize(
    "field,bad_value",
    [
        ("date", "2026-02-30"),
        ("category", "   "),
        ("amount", "-10"),
    ],
)
def test_invalid_edit_leaves_expense_unchanged(
    web_client,
    web_module,
    field,
    bad_value,
):
    login(web_client)

    expense_id = find_test_expense_id(
        web_module,
        "Alice private lunch",
    )
    path = f"/expenses/{expense_id}/edit"

    submitted = {
        "date": "2026-01-20",
        "category": "Transport",
        "item": "Unsaved correction",
        "amount": "500.00",
    }
    submitted[field] = bad_value

    response = post_form(web_client, path, submitted)

    assert response.status_code == 400

    # Preserve the user's entered item so they can correct the error.
    assert 'value="Unsaved correction"' in response.get_data(as_text=True)

    with web_module.app.app_context():
        expense = web_module.db.session.get(
            web_module.Expense,
            expense_id,
        )

        assert expense.item == "Alice private lunch"
        assert expense.category == "Food"
        assert expense.date.isoformat() == "2026-01-10"
        assert expense.amount_kobo == 125050


def test_edit_without_csrf_is_rejected(web_client, web_module):
    login(web_client)

    expense_id = find_test_expense_id(
        web_module,
        "Alice private lunch",
    )

    response = web_client.post(
        f"/expenses/{expense_id}/edit",
        data={
            "date": "2026-01-20",
            "category": "Food",
            "item": "Should not save",
            "amount": "1.00",
        },
    )

    assert response.status_code == 400

    with web_module.app.app_context():
        expense = web_module.db.session.get(
            web_module.Expense,
            expense_id,
        )

        assert expense.item == "Alice private lunch"
        assert expense.amount_kobo == 125050
def test_delete_confirmation_does_not_remove_expense(
    web_client,
    web_module,
):
    login(web_client)

    expense_id = find_test_expense_id(
        web_module,
        "Alice private lunch",
    )

    response = web_client.get(f"/expenses/{expense_id}/delete")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Delete this expense?" in page
    assert "Alice private lunch" in page
    assert "₦1,250.50" in page

    with web_module.app.app_context():
        expense = web_module.db.session.get(
            web_module.Expense,
            expense_id,
        )

        assert expense is not None

    # Returning to the list without submitting also leaves it intact.
    response = web_client.get("/expenses")

    assert "Alice private lunch" in response.get_data(as_text=True)


def test_delete_own_expense(web_client, web_module):
    login(web_client)

    expense_id = find_test_expense_id(
        web_module,
        "Alice private lunch",
    )

    response = post_form(
        web_client,
        f"/expenses/{expense_id}/delete",
        {},
    )

    assert response.status_code == 302
    assert urlsplit(response.headers["Location"]).path == "/expenses"

    with web_module.app.app_context():
        deleted = web_module.db.session.get(
            web_module.Expense,
            expense_id,
        )

        assert deleted is None

        remaining = web_module.db.session.execute(
            web_module.db.select(web_module.Expense)
        ).scalars().all()

        assert len(remaining) == 1
        assert remaining[0].item == "Bob private purchase"

    page = web_client.get("/expenses").get_data(as_text=True)

    assert "Expense deleted successfully." in page
    assert "Alice private lunch" not in page
    assert "₦0.00" in page

    summary_page = web_client.get(
        "/summary?month=2026-01"
    ).get_data(as_text=True)

    assert "₦0.00" in summary_page
    assert "No expenses this month" in summary_page

    # A second attempt cannot delete the same record again.
    assert web_client.get(
        f"/expenses/{expense_id}/delete"
    ).status_code == 404


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_cannot_delete_another_users_expense(
    web_client,
    web_module,
    method,
):
    login(web_client)

    expense_id = find_test_expense_id(
        web_module,
        "Bob private purchase",
    )
    path = f"/expenses/{expense_id}/delete"

    if method == "GET":
        response = web_client.get(path)
    else:
        response = post_form(
            web_client,
            "/expenses/new",
            {},
            target=path,
        )

    assert response.status_code == 404
    assert "Bob private purchase" not in response.get_data(as_text=True)

    with web_module.app.app_context():
        expense = web_module.db.session.get(
            web_module.Expense,
            expense_id,
        )

        assert expense is not None
        assert expense.user.email == "bob@example.com"


def test_delete_without_csrf_is_rejected(web_client, web_module):
    login(web_client)

    expense_id = find_test_expense_id(
        web_module,
        "Alice private lunch",
    )

    response = web_client.post(
        f"/expenses/{expense_id}/delete",
        data={},
    )

    assert response.status_code == 400

    with web_module.app.app_context():
        assert web_module.db.session.get(
            web_module.Expense,
            expense_id,
        ) is not None


def test_delete_missing_expense_returns_404(web_client):
    login(web_client)

    response = web_client.get("/expenses/999999/delete")

    assert response.status_code == 404


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_delete_requires_login(web_client, web_module, method):
    expense_id = find_test_expense_id(
        web_module,
        "Alice private lunch",
    )
    path = f"/expenses/{expense_id}/delete"

    if method == "GET":
        response = web_client.get(path)
    else:
        # Obtain a valid CSRF token without signing in.
        response = post_form(
            web_client,
            "/login",
            {},
            target=path,
        )

    assert response.status_code == 302
    assert urlsplit(response.headers["Location"]).path == "/login"

    with web_module.app.app_context():
        assert web_module.db.session.get(
            web_module.Expense,
            expense_id,
        ) is not None
def test_add_shows_multiple_field_errors_and_preserves_values(
    web_client,
    web_module,
):
    login(web_client)

    response = post_form(
        web_client,
        "/expenses/new",
        {
            "date": "2026-01-20",
            "category": "   ",
            "item": "Keep this description",
            "amount": "0",
        },
    )

    page = response.get_data(as_text=True)

    assert response.status_code == 400
    assert 'id="category-error"' in page
    assert 'id="amount-error"' in page
    assert "Enter a category." in page
    assert "Amount must be greater than zero." in page
    assert 'value="Keep this description"' in page
    assert 'value="2026-01-20"' in page
    assert page.count('aria-invalid="true"') == 2

    with web_module.app.app_context():
        records = web_module.db.session.execute(
            web_module.db.select(web_module.Expense)
        ).scalars().all()

        assert len(records) == 2

    # Correct the errors and submit successfully.
    response = post_form(
        web_client,
        "/expenses/new",
        {
            "date": "2026-01-20",
            "category": "Food",
            "item": "Keep this description",
            "amount": "500.00",
        },
    )

    assert response.status_code == 302

    with web_module.app.app_context():
        saved = web_module.db.session.execute(
            web_module.db.select(web_module.Expense).where(
                web_module.Expense.item == "Keep this description"
            )
        ).scalar_one()

        assert saved.amount_kobo == 50000
        assert saved.user.email == ALICE_EMAIL


def test_edit_shows_multiple_field_errors_without_saving(
    web_client,
    web_module,
):
    login(web_client)

    expense_id = find_test_expense_id(
        web_module,
        "Alice private lunch",
    )

    response = post_form(
        web_client,
        f"/expenses/{expense_id}/edit",
        {
            "date": "2026-02-30",
            "category": "Transport",
            "item": "Keep my attempted correction",
            "amount": "0",
        },
    )

    page = response.get_data(as_text=True)

    assert response.status_code == 400
    assert 'id="date-error"' in page
    assert 'id="amount-error"' in page
    assert 'value="Transport"' in page
    assert 'value="Keep my attempted correction"' in page
    assert page.count('aria-invalid="true"') == 2

    with web_module.app.app_context():
        expense = web_module.db.session.get(
            web_module.Expense,
            expense_id,
        )

        assert expense.item == "Alice private lunch"
        assert expense.category == "Food"
        assert expense.date.isoformat() == "2026-01-10"
        assert expense.amount_kobo == 125050

@pytest.mark.parametrize("mode", ["add", "edit"])
@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_expense_date_cannot_be_in_the_future(
    web_client,
    web_module,
    monkeypatch,
    mode,
    offset,
):
    from datetime import date, timedelta

    # Fix "today" so this test remains reliable on future runs.
    today = date(2026, 11, 8)
    monkeypatch.setattr(web_module, "expense_today", lambda: today)

    login(web_client)

    expense_id = find_test_expense_id(
        web_module,
        "Alice private lunch",
    )

    if mode == "add":
        path = "/expenses/new"
    else:
        path = f"/expenses/{expense_id}/edit"

    page = web_client.get(path).get_data(as_text=True)
    assert 'max="2026-11-08"' in page

    chosen_date = today + timedelta(days=offset)

    response = post_form(
        web_client,
        path,
        {
            "date": chosen_date.isoformat(),
            "category": "Food",
            "item": "Date boundary test",
            "amount": "100.00",
        },
    )

    if offset > 0:
        assert response.status_code == 400
        assert "An expense cannot have a future date." in (
            response.get_data(as_text=True)
        )
    else:
        assert response.status_code == 302

    with web_module.app.app_context():
        saved = web_module.db.session.execute(
            web_module.db.select(web_module.Expense).where(
                web_module.Expense.item == "Date boundary test"
            )
        ).scalar_one_or_none()

        if offset > 0:
            assert saved is None

            original = web_module.db.session.get(
                web_module.Expense,
                expense_id,
            )
            assert original.item == "Alice private lunch"
            assert original.date.isoformat() == "2026-01-10"
        else:
            assert saved is not None
            assert saved.date == chosen_date
            assert saved.amount_kobo == 10000  
def test_registration_shows_multiple_field_errors(
    web_client,
    web_module,
):
    response = post_form(
        web_client,
        "/register",
        {
            "email": "not-an-email",
            "password": "short",
            "confirm_password": "different",
        },
    )

    page = response.get_data(as_text=True)

    assert response.status_code == 400
    assert 'id="email-error"' in page
    assert 'id="password-error"' in page
    assert 'id="confirm-password-error"' in page
    class InvalidInputParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.invalid_fields = []

        def handle_starttag(self, tag, attrs):
            attributes = dict(attrs)

            if tag == "input" and attributes.get("aria-invalid") == "true":
                self.invalid_fields.append(attributes.get("name"))

    parser = InvalidInputParser()
    parser.feed(page)

    assert sorted(parser.invalid_fields) == [
        "confirm_password",
        "email",
        "password",
    ]

    assert 'value="not-an-email"' in page
    assert 'value="short"' not in page
    assert 'value="different"' not in page

    with web_module.app.app_context():
        users = web_module.db.session.execute(
            web_module.db.select(web_module.User)
        ).scalars().all()

        # Only the two accounts created by the test setup exist.
        assert len(users) == 2


def test_registration_rejects_duplicate_email(
    web_client,
    web_module,
):
    response = post_form(
        web_client,
        "/register",
        {
            "email": "ALICE@EXAMPLE.COM",
            "password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
    )

    page = response.get_data(as_text=True)

    assert response.status_code == 409
    assert 'id="email-error"' in page
    assert "An account with this email already exists." in page

    with web_module.app.app_context():
        users = web_module.db.session.execute(
            web_module.db.select(web_module.User)
        ).scalars().all()

        assert len(users) == 2

        alice = web_module.db.session.execute(
            web_module.db.select(web_module.User).where(
                web_module.User.email == ALICE_EMAIL
            )
        ).scalar_one()

        # Registration must not change an existing account's password.
        assert alice.check_password(ALICE_PASSWORD)


def test_registration_creates_account_and_allows_login(
    web_client,
    web_module,
):
    email = "newuser@example.com"
    password = "NewAccountTesting123!"

    response = post_form(
        web_client,
        "/register",
        {
            "email": email,
            "password": password,
            "confirm_password": password,
        },
    )

    assert response.status_code == 302
    assert urlsplit(response.headers["Location"]).path == "/login"

    with web_module.app.app_context():
        user = web_module.db.session.execute(
            web_module.db.select(web_module.User).where(
                web_module.User.email == email
            )
        ).scalar_one()

        assert user.password_hash != password
        assert user.check_password(password)

    # Registration should not automatically sign the user in.
    assert web_client.get("/expenses").status_code == 302

    response = post_form(
        web_client,
        "/login",
        {
            "email": email,
            "password": password,
        },
    )

    assert response.status_code == 302
    assert web_client.get("/expenses").status_code == 200


def test_registration_without_csrf_is_rejected(
    web_client,
    web_module,
):
    response = web_client.post(
        "/register",
        data={
            "email": "blocked@example.com",
            "password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
    )

    assert response.status_code == 400

    with web_module.app.app_context():
        user = web_module.db.session.execute(
            web_module.db.select(web_module.User).where(
                web_module.User.email == "blocked@example.com"
            )
        ).scalar_one_or_none()

        assert user is None
def test_login_shows_errors_for_missing_fields(web_client):
    response = post_form(
        web_client,
        "/login",
        {
            "email": "",
            "password": "",
        },
    )

    page = response.get_data(as_text=True)

    assert response.status_code == 400
    assert 'id="email-error"' in page
    assert 'id="password-error"' in page
    assert "Enter your email address." in page
    assert "Enter your password." in page
    assert web_client.get("/expenses").status_code == 302


def test_login_rejects_malformed_email_and_preserves_it(web_client):
    password = "NeverEchoThisPassword123!"

    response = post_form(
        web_client,
        "/login",
        {
            "email": "not-an-email",
            "password": password,
        },
    )

    page = response.get_data(as_text=True)

    assert response.status_code == 400
    assert 'id="email-error"' in page
    assert "Enter a valid email address." in page
    assert 'value="not-an-email"' in page
    assert password not in page
    assert web_client.get("/expenses").status_code == 302


@pytest.mark.parametrize(
    "email",
    [
        ALICE_EMAIL,
        "unknown@example.com",
    ],
)
def test_login_uses_generic_message_for_invalid_credentials(
    web_client,
    email,
):
    password = "IncorrectTestingPassword123!"

    response = post_form(
        web_client,
        "/login",
        {
            "email": email,
            "password": password,
        },
    )

    page = response.get_data(as_text=True)

    assert response.status_code == 401
    assert "Email or password is incorrect." in page
    assert 'id="login-errors"' in page

    # Do not identify either field as the incorrect credential.
    assert 'id="email-error"' not in page
    assert 'id="password-error"' not in page

    assert f'value="{email}"' in page
    assert password not in page
    assert web_client.get("/expenses").status_code == 302