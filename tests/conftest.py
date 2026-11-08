import importlib
from datetime import date
from limits.storage import MemoryStorage
import pytest


@pytest.fixture
def web_module(monkeypatch):
    # Apply these before importing app.py.
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("SECRET_KEY", "automated-tests-only-secret-key")
    monkeypatch.setenv("APP_BASE_URL", "http://localhost")
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "memory://")

    module = importlib.import_module("app")

    monkeypatch.setitem(module.app.config, "TESTING", True)
    monkeypatch.setitem(module.app.config, "WTF_CSRF_ENABLED", True)
    monkeypatch.setitem(
        module.app.config,
        "APP_BASE_URL",
        "http://localhost",
    )
    monkeypatch.setitem(
        module.app.config,
        "RESET_TOKEN_MAX_AGE",
        15 * 60,
    )

    # Safety check: never create or remove tables in a file database.
    with module.app.app_context():
        database_url = module.db.engine.url

        if (
            database_url.get_backend_name() != "sqlite"
            or database_url.database != ":memory:"
        ):
            pytest.fail(
                "Web tests stopped: the database is not in memory. "
                "Check the DATABASE_URL change in app.py."
            )
            
    # Use isolated local counters and clear them before each test.
    # Refuse to reset any external rate-limit storage.
    with module.app.app_context():
        if not isinstance(module.limiter.storage, MemoryStorage):
            pytest.fail(
                "Web tests stopped: rate-limit storage is not in memory."
            )

        module.limiter.reset()

    # Capture outgoing emails without connecting to Mailtrap.
    sent_emails = []

    def fake_send_email(to_email, subject, body):
        sent_emails.append({
            "to": to_email,
            "subject": subject,
            "body": body,
        })

    monkeypatch.setattr(module, "send_email", fake_send_email)
    monkeypatch.setattr(
        module,
        "test_sent_emails",
        sent_emails,
        raising=False,
    )

    with module.app.app_context():
        module.db.create_all()

        alice = module.User(email="alice@example.com")
        alice.set_password("AliceTestingPassword123!")

        bob = module.User(email="bob@example.com")
        bob.set_password("BobTestingPassword456!")

        module.db.session.add_all([alice, bob])
        module.db.session.flush()

        module.db.session.add_all([
            module.Expense(
                user_id=alice.id,
                date=date(2026, 1, 10),
                category="Food",
                item="Alice private lunch",
                amount_kobo=125050,
            ),
            module.Expense(
                user_id=bob.id,
                date=date(2026, 1, 12),
                category="BobOnlyCategory",
                item="Bob private purchase",
                amount_kobo=900000,
            ),
        ])

        module.db.session.commit()

    try:
        yield module
    finally:
        with module.app.app_context():
            module.db.session.remove()
            module.db.drop_all()


@pytest.fixture
def web_client(web_module):
    return web_module.app.test_client()