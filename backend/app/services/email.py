"""Sending email through Brevo (BREVO_API_KEY) or Resend (RESEND_API_KEY); without either, nothing.

Brevo wins when both are set. Callers get True only when the email was handed to the service, so
the UI can say "sent" honestly.
"""

import json
import logging
import urllib.error
import urllib.request
from email.utils import parseaddr

from app.core.config import settings

log = logging.getLogger(__name__)
BREVO_URL = "https://api.brevo.com/v3/smtp/email"
RESEND_URL = "https://api.resend.com/emails"
# Both APIs sit behind Cloudflare, which refuses Python's default "Python-urllib" agent (403).
USER_AGENT = "Roommates/1.0"


def enabled() -> bool:
    return bool(settings.brevo_api_key or settings.resend_api_key)


def _request(to: str, subject: str, text: str) -> tuple[str, urllib.request.Request]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    if settings.brevo_api_key:
        name, address = parseaddr(settings.email_from)  # "Roommates <invites@…>"
        body = {
            "sender": {"name": name or "Roommates", "email": address},
            "to": [{"email": to}],
            "subject": subject,
            "textContent": text,
        }
        headers["api-key"] = settings.brevo_api_key
        return "Brevo", urllib.request.Request(
            BREVO_URL, data=json.dumps(body).encode(), headers=headers, method="POST"
        )
    body = {"from": settings.email_from, "to": [to], "subject": subject, "text": text}
    headers["Authorization"] = f"Bearer {settings.resend_api_key}"
    return "Resend", urllib.request.Request(
        RESEND_URL, data=json.dumps(body).encode(), headers=headers, method="POST"
    )


def send(to: str, subject: str, text: str) -> bool:
    if not enabled():
        return False
    service, request = _request(to, subject, text)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return 200 <= response.status < 300
    except urllib.error.HTTPError as e:
        # The service said no: log why (bad key, unverified sender, …).
        detail = e.read().decode(errors="replace")[:500]
        log.error("Couldn't send email to %s: %s %s %s", to, service, e.code, detail)
        return False
    except Exception:  # a failed email shouldn't fail the invite; it can be re-sent
        log.exception("Couldn't send email to %s", to)
        return False
