"""
Minimal SMTP sender for password-reset emails.

If SMTP_HOST is not configured, `send_password_reset_email` is a no-op that
returns False — the caller (routers/auth.py) then falls back to returning
the reset link directly in the API response, which is convenient for local
development but should be disabled in production once SMTP is set up.
"""
import smtplib
from email.mime.text import MIMEText

from config import settings


def send_password_reset_email(to_name: str, to_email: str, reset_link: str) -> bool:
    if not settings.SMTP_HOST or not settings.SMTP_FROM:
        return False

    body = (
        f"Hi {to_name},\n\n"
        f"We received a request to reset the password for your SyllabusQuest account.\n"
        f"Click the link below to set a new password. This link expires in "
        f"{settings.RESET_TOKEN_EXPIRE_MINUTES} minutes.\n\n"
        f"{reset_link}\n\n"
        f"If you did not request this, you can safely ignore this email.\n"
    )
    msg = MIMEText(body)
    msg["Subject"] = "Reset your SyllabusQuest password"
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to_email

    try:
		with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:            
		server.starttls()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM, [to_email], msg.as_string())
        return True
    except Exception as e:  # pragma: no cover - best effort, log and fall back
        print(f"[email_utils] Failed to send reset email: {e}")
        return False
