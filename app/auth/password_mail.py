"""Transactional password email sent from the backend over HTTPS."""

import json
import logging
from typing import Annotated, Protocol
from urllib.request import HTTPRedirectHandler, Request, build_opener

from fastapi import Depends

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class PasswordMailer(Protocol):
    def send(self, recipient: str, subject: str, body: str) -> None: ...


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ResendPasswordMailer:
    def __init__(self, sender: str, key: str) -> None:
        self.sender = sender
        self.key = key

    def send(self, recipient: str, subject: str, body: str) -> None:
        request = Request(
            "https://api.resend.com/emails",
            data=json.dumps({
                "from": self.sender,
                "to": [recipient],
                "subject": subject,
                "text": body,
            }).encode(),
            headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
            method="POST",
        )
        with build_opener(NoRedirect()).open(request, timeout=5):
            pass


def get_password_mailer(
    settings: Annotated[Settings, Depends(get_settings)],
) -> PasswordMailer | None:
    if not settings.password_recovery_configured:
        return None
    assert settings.password_recovery_from_email is not None and settings.resend_api_key is not None
    return ResendPasswordMailer(
        settings.password_recovery_from_email, settings.resend_api_key.get_secret_value()
    )


def send_password_email(mailer: PasswordMailer, recipient: str, subject: str, body: str) -> None:
    try:
        mailer.send(recipient, subject, body)
    except Exception:
        logger.warning("Password email could not be delivered")
