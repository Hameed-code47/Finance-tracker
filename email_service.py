import json
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import parseaddr
from http.client import HTTPException, HTTPSConnection
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parent / ".env")


def send_email(to_email: str, subject: str, body: str) -> None:
    """Send a plain-text email using the selected provider."""
    provider = os.environ.get("EMAIL_PROVIDER", "smtp").strip().lower()

    if provider == "brevo":
        _send_brevo(to_email, subject, body)
    elif provider == "smtp":
        _send_smtp(to_email, subject, body)
    else:
        raise OSError("Unsupported email provider.")


def _send_brevo(to_email: str, subject: str, body: str) -> None:
    """Send through Brevo's HTTPS API."""
    api_key = os.environ.get("BREVO_API_KEY", "").strip()
    sender_name, sender_email = parseaddr(
        os.environ.get("MAIL_FROM", "")
    )

    if not api_key or not sender_email:
        raise OSError("Brevo email configuration is incomplete.")

    payload = {
        "sender": {
            "name": sender_name or "Finance Tracker",
            "email": sender_email,
        },
        "to": [{"email": to_email}],
        "subject": subject,
        "textContent": body,
    }

    connection = HTTPSConnection(
        "api.brevo.com",
        timeout=15,
        context=ssl.create_default_context(),
    )

    try:
        connection.request(
            "POST",
            "/v3/smtp/email",
            body=json.dumps(payload).encode("utf-8"),
            headers={
                "api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        response = connection.getresponse()

        if response.status != 201:
            # Do not expose credentials, reset links, or response bodies.
            raise OSError(
                f"Brevo rejected the email (HTTP {response.status})."
            )
    except (HTTPException, OSError):
        # OSError is already handled by the password-recovery route.
        raise OSError("Email delivery through Brevo failed.") from None
    finally:
        connection.close()


def _send_smtp(to_email: str, subject: str, body: str) -> None:
    """Send through SMTP, including the local Mailtrap sandbox."""
    message = EmailMessage()
    message["From"] = os.environ["MAIL_FROM"]
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(
        host=os.environ["MAIL_SERVER"],
        port=int(os.environ["MAIL_PORT"]),
        timeout=15,
    ) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        smtp.login(
            os.environ["MAIL_USERNAME"],
            os.environ["MAIL_PASSWORD"],
        )
        smtp.send_message(message)