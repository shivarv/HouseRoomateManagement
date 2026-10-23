"""Sending email through Brevo (BREVO_API_KEY) or Resend (RESEND_API_KEY); without either, nothing.

Brevo wins when both are set. Callers get True only when the email was handed to the service, so
the UI can say "sent" honestly.
"""

import html as html_lib
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


def button_email(paragraphs: list[str], button: str, url: str, footer: str = "") -> str:
    """A simple HTML email: a few lines, a big button to `url`, and the link spelled out too."""
    e = html_lib.escape
    lines = "".join(f'<p style="margin:0 0 14px">{e(p)}</p>' for p in paragraphs)
    small = f'<p style="margin:18px 0 0;color:#64748b;font-size:13px">{e(footer)}</p>' if footer else ""
    return (
        '<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;'
        'max-width:520px;margin:0 auto;padding:24px;color:#0f172a;font-size:15px;line-height:1.5">'
        f"{lines}"
        f'<p style="margin:22px 0"><a href="{e(url)}" style="display:inline-block;padding:12px 22px;'
        'border-radius:12px;background:#6366f1;color:#ffffff;font-weight:600;text-decoration:none">'
        f"{e(button)}</a></p>"
        f'<p style="margin:0;color:#64748b;font-size:13px">Or open this link: <a href="{e(url)}" '
        f'style="color:#4f46e5">{e(url)}</a></p>'
        f"{small}</div>"
    )


def _request(to: str, subject: str, text: str, html: str | None = None) -> tuple[str, urllib.request.Request]:
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
            **({"htmlContent": html} if html else {}),
        }
        headers["api-key"] = settings.brevo_api_key
        return "Brevo", urllib.request.Request(
            BREVO_URL, data=json.dumps(body).encode(), headers=headers, method="POST"
        )
    body = {"from": settings.email_from, "to": [to], "subject": subject, "text": text}
    if html:
        body["html"] = html
    headers["Authorization"] = f"Bearer {settings.resend_api_key}"
    return "Resend", urllib.request.Request(
        RESEND_URL, data=json.dumps(body).encode(), headers=headers, method="POST"
    )


# Why an email didn't go out, for the people sending it (see deliver()).
NOT_SET_UP = "not_set_up"  # no email service configured
BAD_ADDRESS = "bad_address"  # the service says the address isn't valid
UNAVAILABLE = "unavailable"  # the service is down, slow or rate-limiting: try again later
REFUSED = "refused"  # the service turned it down for another reason (our setup): see the log


def _reason(code: int, detail: str) -> str:
    text = detail.lower()
    # (Resend's test sender also says "invalid `to`" for any address but yours: that's our setup.)
    if (
        code in (400, 422)
        and "email" in text
        and ("invalid" in text or "not valid" in text)
        and "testing" not in text
    ):
        return BAD_ADDRESS
    if code == 429 or code >= 500:
        return UNAVAILABLE
    return REFUSED


def deliver(to: str, subject: str, text: str, html: str | None = None) -> str | None:
    """None when the email was handed to the service; otherwise why not (one of the codes above)."""
    if not enabled():
        return NOT_SET_UP
    service, request = _request(to, subject, text, html)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return None if 200 <= response.status < 300 else UNAVAILABLE
    except urllib.error.HTTPError as e:
        # The service said no: log why (bad key, unverified sender, …).
        detail = e.read().decode(errors="replace")[:500]
        log.error("Couldn't send email to %s: %s %s %s", to, service, e.code, detail)
        return _reason(e.code, detail)
    except Exception:  # unreachable or timed out; a failed email shouldn't fail the invite
        log.exception("Couldn't send email to %s", to)
        return UNAVAILABLE


def send(to: str, subject: str, text: str, html: str | None = None) -> bool:
    return deliver(to, subject, text, html) is None
