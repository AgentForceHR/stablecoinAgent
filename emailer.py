import os
import smtplib
from email.mime.text import MIMEText

def send_email(subject: str, body: str) -> None:
    if os.getenv("EMAIL_ENABLED", "false").lower() != "true":
        return

    to_addr = os.getenv("EMAIL_TO")
    user = os.getenv("GMAIL_USER")
    app_pass = os.getenv("GMAIL_APP_PASSWORD")

    if not (to_addr and user and app_pass):
        raise RuntimeError("Missing EMAIL_TO / GMAIL_USER / GMAIL_APP_PASSWORD environment variables.")

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_addr

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(user, app_pass)
        smtp.sendmail(user, [to_addr], msg.as_string())