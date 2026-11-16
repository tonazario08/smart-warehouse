import logging
from collections import defaultdict, deque
from contextlib import contextmanager
from threading import Lock
from time import monotonic
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.assistant.provider import ModelProvider
from app.assistant.repository import AssistantRepository
from app.assistant.schemas import ChatRequest, ChatResponse, SourceResponse
from app.assistant.service import AssistantService, read_source
from app.auth.dependencies import Permission, require_permission
from app.core.config import Settings, get_settings
from app.core.errors import DomainError
from app.db.session import get_session
from app.models import User

router = APIRouter(prefix="/assistant", tags=["assistant"])
Actor = Annotated[User, Depends(require_permission(Permission.ASSISTANT_READ))]
logger = logging.getLogger("uvicorn.error.assistant")
SAFE_ERROR_CODES = frozenset(
    {
        "ASSISTANT_INVALID_QUESTION",
        "ASSISTANT_NOT_CONFIGURED",
        "ASSISTANT_RATE_LIMIT",
        "ASSISTANT_TIMEOUT",
        "ASSISTANT_PROVIDER_ERROR",
        "ASSISTANT_DATABASE_ERROR",
        "ASSISTANT_SOURCE_NOT_FOUND",
    }
)


@contextmanager
def operational_event(event):
    started = monotonic()
    outcome = {"citation_count": 0}
    code = "OK"
    try:
        yield outcome
    except DomainError as error:
        code = error.code if error.code in SAFE_ERROR_CODES else "OTHER_ERROR"
        raise
    except Exception:
        code = "INTERNAL_SERVER_ERROR"
        raise DomainError(500, "INTERNAL_SERVER_ERROR", "An internal error occurred.") from None
    finally:
        elapsed_ms = max(0, int((monotonic() - started) * 1000))
        logger.info(
            "event=%s code=%s elapsed_ms=%d citation_count=%d",
            event,
            code,
            elapsed_ms,
            outcome["citation_count"],
        )


class RateLimiter:
    def __init__(self):
        self.lock = Lock()
        self.events = defaultdict(deque)

    def check(self, user_id, limit, window):
        with self.lock:
            now = monotonic()
            # Prune inactive accounts as well as this account to bound retention.
            for key in list(self.events):
                events = self.events[key]
                while events and events[0] <= now - window:
                    events.popleft()
                if not events:
                    del self.events[key]
            events = self.events[user_id]
            if len(events) >= limit:
                raise DomainError(
                    429, "ASSISTANT_RATE_LIMIT", "Bạn đã hết lượt hỏi. Vui lòng thử lại sau."
                )
            events.append(now)


@router.post("/chat", response_model=ChatResponse)
def chat(
    body: ChatRequest,
    request: Request,
    actor: Actor,
    session: Annotated[object, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    with operational_event("chat") as outcome:
        question = body.question.strip()
        if not question or len(question) > settings.assistant_max_question_chars:
            raise DomainError(
                422, "ASSISTANT_INVALID_QUESTION", "Câu hỏi trống hoặc vượt quá giới hạn độ dài."
            )
        if not settings.assistant_enabled:
            raise DomainError(503, "ASSISTANT_NOT_CONFIGURED", "Trợ lý chưa được cấu hình.")
        request.app.state.assistant_rate_limiter.check(
            actor.id, settings.assistant_rate_limit, settings.assistant_rate_window_seconds
        )
        provider = getattr(request.app.state, "assistant_provider", None) or ModelProvider(settings)
        if isinstance(provider, ModelProvider):
            provider.validate_configuration()
        service = AssistantService(AssistantRepository(session), provider, settings)
        try:
            sections = service.retrieve(question, actor.role)
        finally:
            session.close()
        reply = service.respond(question, sections)
        outcome["citation_count"] = len(reply.citations)
        return reply


@router.get("/sources/{section_id}", response_model=SourceResponse)
def source(
    section_id: str,
    actor: Actor,
    session: Annotated[object, Depends(get_session)],
    version: str | None = None,
):
    with operational_event("source") as outcome:
        result = read_source(AssistantRepository(session), section_id, actor.role, version)
        outcome["citation_count"] = 1
        return result
