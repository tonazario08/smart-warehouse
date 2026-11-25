"""Local-only app entry point with an in-memory inbox for browser tests."""

from threading import Lock

from fastapi import HTTPException, Response
from sqlalchemy.engine import make_url

from app.auth.password_mail import get_password_mailer
from app.core.config import get_settings
from app.main import create_app

settings = get_settings()
db = make_url(settings.database_url)
if (
    settings.app_env != "integration" or db.host != "db" or db.database != "smart_warehouse_e2e"
    or not settings.password_recovery_enabled or not settings.password_recovery_origin
    or not settings.password_recovery_origin.startswith("http://127.0.0.1:")
):
    raise RuntimeError("The password recovery inbox requires the isolated browser test stack.")

app = create_app(settings)


class BrowserInbox:
    def __init__(self):
        self.lock = Lock()
        self.links: dict[str, str] = {}
        self.notices: dict[str, int] = {}

    def send(self, recipient: str, subject: str, body: str) -> None:
        if not recipient.endswith("@example.com"):
            return
        with self.lock:
            for line in body.splitlines():
                if line.startswith(f"{settings.password_recovery_origin}/reset-password#token="):
                    self.links[recipient] = line
                    return
            self.notices[recipient] = self.notices.get(recipient, 0) + 1


inbox = BrowserInbox()
app.dependency_overrides[get_password_mailer] = lambda: inbox


@app.get("/api/v1/_test/password-inbox", include_in_schema=False)
def read_inbox(email: str, response: Response) -> dict[str, str | int | None]:
    if not email.endswith("@example.com"):
        raise HTTPException(404)
    response.headers["Cache-Control"] = "no-store"
    with inbox.lock:
        return {"reset_url": inbox.links.get(email), "change_notices": inbox.notices.get(email, 0)}
