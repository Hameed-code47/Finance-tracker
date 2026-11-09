import json

import pytest

import email_service


def test_default_provider_uses_smtp(monkeypatch):
    monkeypatch.delenv("EMAIL_PROVIDER", raising=False)
    calls = []

    monkeypatch.setattr(
        email_service,
        "_send_smtp",
        lambda *args: calls.append(args),
    )

    email_service.send_email(
        "recipient@example.com", "Test subject", "Test body"
    )

    assert calls == [
        ("recipient@example.com", "Test subject", "Test body")
    ]


@pytest.mark.parametrize("outcome", [201, 401, "timeout"])
def test_brevo_delivery(monkeypatch, outcome):
    monkeypatch.setenv("EMAIL_PROVIDER", "brevo")
    monkeypatch.setenv("BREVO_API_KEY", "test-key-not-real")
    monkeypatch.setenv(
        "MAIL_FROM", "Finance Tracker <sender@example.com>"
    )
    recorded = {}

    class FakeResponse:
        status = outcome

    class FakeConnection:
        def __init__(self, host, timeout, context):
            recorded["host"] = host
            recorded["timeout"] = timeout

        def request(self, method, path, body, headers):
            recorded["method"] = method
            recorded["path"] = path
            recorded["payload"] = json.loads(body)
            recorded["headers"] = headers

            if outcome == "timeout":
                raise TimeoutError("Connection timed out")

        def getresponse(self):
            return FakeResponse()

        def close(self):
            recorded["closed"] = True

    monkeypatch.setattr(
        email_service, "HTTPSConnection", FakeConnection
    )

    if outcome == 201:
        email_service.send_email(
            "recipient@example.com", "Reset password", "Private reset link"
        )
    else:
        with pytest.raises(OSError) as error:
            email_service.send_email(
                "recipient@example.com",
                "Reset password",
                "Private reset link",
            )

        assert "test-key-not-real" not in str(error.value)
        assert "Private reset link" not in str(error.value)

    assert recorded["host"] == "api.brevo.com"
    assert recorded["timeout"] == 15
    assert recorded["method"] == "POST"
    assert recorded["path"] == "/v3/smtp/email"
    assert recorded["headers"]["api-key"] == "test-key-not-real"
    assert recorded["payload"] == {
        "sender": {
            "name": "Finance Tracker",
            "email": "sender@example.com",
        },
        "to": [{"email": "recipient@example.com"}],
        "subject": "Reset password",
        "textContent": "Private reset link",
    }
    assert recorded["closed"] is True