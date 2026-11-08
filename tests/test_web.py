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