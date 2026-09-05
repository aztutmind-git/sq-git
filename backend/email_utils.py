"""
Sends password-reset emails via Resend's HTTP API instead of SMTP.

Render's free web services block outbound SMTP ports (25, 465, 587)
entirely, so a normal SMTP library can never connect from a free-tier
backend — see:
https://render.com/changelog/free-web-services-will-no-longer-allow-outbound-traffic-to-smtp-ports

Resend (and other transactional email APIs) send over a normal HTTPS POST
request instead, which isn't affected by that block. Uses only Python's
built-in urllib, so no extra dependency is needed.

If RESEND_API_KEY isn't set, `send_password_reset_email` is a no-op that
returns False — the caller (routers/auth.py) then falls back to returning
the reset link directly in the API response, which is convenient for local
development but should be disabled in production once this is set up.
"""
import json
import urllib.request
import urllib.error

from config import settings

RESEND_API_URL = "https://api.resend.com/emails"


def send_password_reset_email(to_name: str, to_email: str, reset_link: str) -> bool:
    if not settings.RESEND_API_KEY or not settings.EMAIL_FROM:
        return False

    body_text = (
        f"Hi {to_name},\n\n"
        f"We received a request to reset the password for your SyllabusQuest account.\n"
        f"Click the link below to set a new password. This link expires in "
        f"{settings.RESET_TOKEN_EXPIRE_MINUTES} minutes.\n\n"
        f"{reset_link}\n\n"
        f"If you did not request this, you can safely ignore this email.\n"
    )

    payload = json.dumps({
        "from": settings.EMAIL_FROM,
        "to": [to_email],
        "subject": "Reset your SyllabusQuest password",
        "text": body_text,
    }).encode("utf-8")

    request = urllib.request.Request(
        RESEND_API_URL,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.RESEND_API_KEY}",
            "Content-Type": "application/json",
            # Resend's API sits behind Cloudflare, which blocks the default
            # "Python-urllib/x.y" User-Agent as a suspected bot (error 1010).
            # Any normal-looking value avoids that.
            "User-Agent": "SyllabusQuest-Backend/1.0",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if 200 <= response.status < 300:
                return True
            print(f"[email_utils] Resend API returned status {response.status}")
            return False
    except urllib.error.HTTPError as e:
        # Resend returns a JSON error body worth surfacing (e.g. unverified domain)
        try:
            detail = e.read().decode("utf-8")
        except Exception:
            detail = str(e)
        print(f"[email_utils] Resend API error {e.code}: {detail}")
        return False
    except Exception as e:  # pragma: no cover - best effort, log and fall back
        print(f"[email_utils] Failed to send reset email: {e}")
        return False
