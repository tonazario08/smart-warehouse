import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, select
from sqlalchemy.exc import OperationalError

from app.auth.password_mail import get_password_mailer
from app.auth.password_recovery import RECOVERY_REQUESTS_PER_MINUTE
from app.auth.security import hash_password
from app.core.config import Settings, get_settings
from app.db.session import get_engine
from app.main import create_app
from app.models import PasswordRecoveryBudget, PasswordResetToken, User, UserRole

pytestmark = pytest.mark.postgres
API = "/api/v1/auth"
EMAIL = "recovery@example.com"
INITIAL = "initial-test-password"
REPLACEMENT = "replacement-test-password"


class Inbox:
    def __init__(self):
        self.messages: list[tuple[str, str, str]] = []

    def send(self, recipient: str, subject: str, body: str) -> None:
        self.messages.append((recipient, subject, body))

    def reset_token(self) -> str:
        link = self.messages[-1][2].splitlines()[1]
        url = urlsplit(link)
        assert (url.scheme, url.netloc, url.path, url.query) == (
            "https", "warehouse.example.com", "/reset-password", "",
        )
        return parse_qs(url.fragment)["token"][0]


@pytest.fixture
def recovery(postgres_url, postgres_session):
    settings = Settings(
        app_env="test",
        database_url=postgres_url,
        jwt_secret_key="test-only-jwt-secret-with-at-least-32-characters",
        cors_origins=["https://warehouse.example.com"],
        password_recovery_enabled=True,
        password_recovery_origin="https://warehouse.example.com",
        password_recovery_from_email="no-reply@example.com",
        resend_api_key="test-only-no-transport",
        _env_file=None,
    )
    inbox = Inbox()
    app = create_app(settings)
    app.dependency_overrides[get_password_mailer] = lambda: inbox
    postgres_session.add_all([
        User(email=EMAIL, password_hash=hash_password(INITIAL), role=UserRole.WAREHOUSE),
        User(email="disabled@example.com", password_hash="unused", role=UserRole.CLIENT,
             is_active=False),
    ])
    postgres_session.commit()
    try:
        with TestClient(app) as client:
            yield client, inbox, app
    finally:
        postgres_session.rollback()
        postgres_session.execute(delete(PasswordRecoveryBudget))
        postgres_session.commit()


def test_recovery_is_generic_and_stores_only_the_digest(recovery, postgres_session):
    client, inbox, _ = recovery
    responses = [client.post(f"{API}/forgot-password", json={"email": email}) for email in (
        f" {EMAIL.upper()} ", "disabled@example.com", "absent@example.com", EMAIL,
    )]
    assert [response.status_code for response in responses] == [202] * 4
    assert all(response.json() == responses[0].json() for response in responses)
    assert len(inbox.messages) == 1
    token = inbox.reset_token()
    record = postgres_session.scalar(select(PasswordResetToken))
    assert record is not None
    assert record.digest == sha256(token.encode()).hexdigest()
    assert record.expires_at - record.issued_at == timedelta(minutes=30)
    assert token not in responses[0].text


def test_password_reset_is_single_use_under_concurrency(recovery):
    client, inbox, _ = recovery
    login = client.post(f"{API}/login", json={"email": EMAIL, "password": INITIAL})
    previous_token = login.json()["access_token"]
    client.post(f"{API}/forgot-password", json={"email": EMAIL})
    body = {
        "token": inbox.reset_token(), "new_password": REPLACEMENT,
        "confirm_password": REPLACEMENT,
    }

    def reset(_):
        return client.post(f"{API}/reset-password", json=body).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(reset, range(2))) == [204, 400]

    stale = client.get(f"{API}/me", headers={"Authorization": f"Bearer {previous_token}"})
    assert stale.status_code == 401
    old_login = client.post(f"{API}/login", json={"email": EMAIL, "password": INITIAL})
    assert old_login.status_code == 401
    new_login = client.post(f"{API}/login", json={"email": EMAIL, "password": REPLACEMENT})
    assert new_login.status_code == 200
    assert new_login.json()["user"]["role"] == "warehouse"
    assert len(inbox.messages) == 2
    assert REPLACEMENT not in inbox.messages[-1][2]
    assert body["token"] not in inbox.messages[-1][2]


def test_expired_forged_and_revoked_reset_links_are_rejected(recovery, postgres_session):
    client, inbox, _ = recovery
    client.post(f"{API}/forgot-password", json={"email": EMAIL})
    previous = inbox.reset_token()
    record = postgres_session.scalar(select(PasswordResetToken))
    assert record is not None
    record.issued_at = datetime.now(UTC) - timedelta(hours=1)
    record.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    postgres_session.commit()

    def reset(token):
        return client.post(f"{API}/reset-password", json={
            "token": token, "new_password": "unused-test-password",
            "confirm_password": "unused-test-password",
        }).status_code

    assert reset(previous) == reset("forged-token") == 400
    client.post(f"{API}/forgot-password", json={"email": EMAIL})
    fresh = inbox.reset_token()
    assert fresh != previous
    login = client.post(f"{API}/login", json={"email": EMAIL, "password": INITIAL})
    headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    change = client.post(f"{API}/change-password", headers=headers, json={
        "current_password": INITIAL, "new_password": REPLACEMENT, "confirm_password": REPLACEMENT,
    })
    assert change.status_code == 204
    assert reset(fresh) == 400


def test_shared_budget_rejects_mail_without_trusting_client_headers(recovery, postgres_session):
    client, inbox, _ = recovery
    window = datetime.now(UTC).replace(second=0, microsecond=0) + timedelta(minutes=1)
    postgres_session.add(PasswordRecoveryBudget(
        id=1, window_start=window, requests=RECOVERY_REQUESTS_PER_MINUTE,
    ))
    postgres_session.commit()
    response = client.post(f"{API}/forgot-password", json={"email": EMAIL}, headers={
        "X-Forwarded-For": "192.0.2.55",
    })
    assert response.status_code == 202
    assert not inbox.messages


def test_mailer_failure_does_not_change_the_public_response(recovery, caplog, monkeypatch):
    client, _, app = recovery
    # The Alembic test can replace the process logging configuration before this test runs.
    monkeypatch.setattr(logging.getLogger("app.auth.password_mail"), "disabled", False)

    class FailingMailer:
        def send(self, recipient, subject, body):
            raise RuntimeError("fake provider secret must not appear")

    app.dependency_overrides[get_password_mailer] = FailingMailer
    active = client.post(f"{API}/forgot-password", json={"email": EMAIL})
    unknown = client.post(f"{API}/forgot-password", json={"email": "absent@example.com"})
    assert active.status_code == unknown.status_code == 202
    assert active.json() == unknown.json()
    assert "Password email could not be delivered" in caplog.text
    assert "fake provider secret must not appear" not in caplog.text


def test_locked_account_does_not_hold_a_recovery_worker_indefinitely(recovery, postgres_session):
    client, inbox, _ = recovery
    postgres_session.scalar(select(User.id).where(User.email == EMAIL).with_for_update())

    def forgot():
        return client.post(f"{API}/forgot-password", json={"email": EMAIL})

    with ThreadPoolExecutor(max_workers=1) as pool:
        try:
            result = pool.submit(forgot).result(timeout=6)
            assert result.status_code == 202
            assert not inbox.messages
        finally:
            postgres_session.rollback()
    assert forgot().status_code == 202
    assert len(inbox.messages) == 1


def test_database_failure_rolls_back_reset_without_logging_parameters(
    recovery, caplog, monkeypatch,
):
    client, inbox, app = recovery
    monkeypatch.setattr(logging.getLogger("app.auth.password_recovery"), "disabled", False)
    assert client.post(f"{API}/forgot-password", json={"email": EMAIL}).status_code == 202
    token = inbox.reset_token()
    body = {"token": token, "new_password": REPLACEMENT, "confirm_password": REPLACEMENT}
    engine = get_engine(app.dependency_overrides[get_settings]().database_url)

    def fail_update(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE users SET"):
            raise OperationalError(
                statement, parameters, RuntimeError("synthetic database failure")
            )

    event.listen(engine, "before_cursor_execute", fail_update)
    try:
        with TestClient(app, raise_server_exceptions=False) as failed_client:
            failed = failed_client.post(f"{API}/reset-password", json=body)
    finally:
        event.remove(engine, "before_cursor_execute", fail_update)
    assert failed.status_code == 503
    assert "Password operation could not complete in the database" in caplog.text
    assert "synthetic database failure" not in caplog.text
    assert "$argon2" not in caplog.text
    assert sha256(token.encode()).hexdigest() not in caplog.text
    unchanged = client.post(f"{API}/login", json={"email": EMAIL, "password": INITIAL})
    assert unchanged.status_code == 200
    assert client.post(f"{API}/reset-password", json=body).status_code == 204
