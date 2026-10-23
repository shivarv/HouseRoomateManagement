"""Sending email. Uses Resend's HTTP API when RESEND_API_KEY is set; otherwise does nothing.

Callers get True only when the email was handed to Resend, so the UI can say "sent" honestly.
"""

import json
import logging
import urllib.error
import urllib.request

from app.core.config import settings

log = logging.getLogger(__name__)
RESEND_URL = "https://api.resend.com/emails"
# Resend's API sits behind Cloudflare, which refuses Python's default "Python-urllib" agent (403).
USER_AGENT = "Roommates/1.0 (+https://resend.com/docs/api-reference)"


def enabled() -> bool:
    return bool(settings.resend_api_key)


def send(to: str, subject: str, text: str) -> bool:
    if not enabled():
        return False
    request = urllib.request.Request(
        RESEND_URL,
        data=json.dumps({"from": settings.email_from, "to": [to], "subject": subject, "text": text}).encode(),
        headers={
            "Authorization": f"Bearer {settings.resend_api_key}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return 200 <= response.status < 300
    except urllib.error.HTTPError as e:  # Resend said no: log why (bad key, unverified domain, …)
        detail = e.read().decode(errors="replace")[:500]
        log.error("Couldn't send email to %s: Resend %s %s", to, e.code, detail)
        return False
    except Exception:  # a failed email shouldn't fail the invite; it can be re-sent
        log.exception("Couldn't send email to %s", to)
        return False
