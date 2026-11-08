import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parent / ".env")


def send_email(to_email: str, subject: str, body: str) -> None:
    """Send a plain-text email using the configured SMTP server."""
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