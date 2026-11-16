import re
from urllib.parse import urlencode

from sqlalchemy.exc import SQLAlchemyError

from app.assistant.evidence import enumerate_sentences
from app.assistant.repository import normalize
from app.assistant.schemas import ChatResponse, Citation, SourceResponse
from app.core.errors import DomainError
from app.models import UserRole

INSUFFICIENT = "Chưa đủ thông tin trong tài liệu được phép đọc để trả lời câu hỏi này."
RULE_OVERRIDE = re.compile(
    r"\b(?:bo qua|ignore)\b.{0,48}\b(?:quy tac|huong dan|chi dan|instructions|rules)\b"
)
ACTION_REQUEST = re.compile(
    r"\b(?:goi (?:api|he thong)|ket noi he thong|call (?:the )?api|(?:hay |vui long )"
    r"(?:tao|xoa|cap nhat|thay doi|ghi nhan))\b"
)
HOW_TO = re.compile(r"\b(?:nhu the nao|the nao|ra sao|cach nao|lam sao)\b")
RESEARCH_REQUEST = re.compile(r"\b(?:bao cao|ket qua|pham vi) nghien cuu\b")
LIVE_TIME = re.compile(r"\b(?:hien tai|luc nay|bay gio|hom nay)\b")
LIVE_COUNT = re.compile(r"\b(?:bao nhieu|so luong|danh sach|nhung)\b")
LIVE_SUBJECT = re.compile(r"\b(?:ton|hang|san pham|don|phieu|giao dich)\b")
TRANSACTION_ID = re.compile(r"\b(?:phieu|don|giao dich)\b.{0,40}\b(?:so|ma)\s*[a-z0-9-]+")
CREDENTIAL_REQUEST = re.compile(r"\b(?:mat khau|password|jwt|token|khoa api|api key|ma truy cap)\b")
PERIOD_COUNT = re.compile(r"\b(?:bao nhieu|so|tong|dem|liet ke)\b")
PERIOD_REFERENCE = re.compile(
    r"\b(?:hom qua|sang nay|chieu nay|tuan nay|thang nay|tu dau|tu ngay|den ngay)\b"
)
LOCATION_IDENTIFIER = re.compile(r"\b(?i:kho)\s+[A-Z0-9][A-Z0-9_-]*\b")
SKU_IDENTIFIER = re.compile(r"\bsku\b\s*[a-z0-9-]+")
MOVEMENT_REQUEST = re.compile(
    r"\b(?:chuyen|xuat|nhap)\b.{0,50}\b(?:giup toi|ho toi|cho toi)\b"
    r"|\b(?:giup toi|ho toi)\b.{0,50}\b(?:chuyen|xuat|nhap)\b"
)
TRANSACTION_STATE = re.compile(r"\b(?:da|chua)\b")


class AssistantService:
    def __init__(self, repository, provider, settings):
        self.repository = repository
        self.provider = provider
        self.settings = settings

    def chat(self, question, role):
        return self.respond(question, self.retrieve(question, role))

    def retrieve(self, question, role):
        normalized = normalize(question)
        if (
            RULE_OVERRIDE.search(normalized)
            or CREDENTIAL_REQUEST.search(normalized)
            or (
                not HOW_TO.search(normalized)
                and PERIOD_COUNT.search(normalized)
                and PERIOD_REFERENCE.search(normalized)
            )
            or (
                (ACTION_REQUEST.search(normalized) or MOVEMENT_REQUEST.search(normalized))
                and not HOW_TO.search(normalized)
            )
            or (
                not HOW_TO.search(normalized)
                and (SKU_IDENTIFIER.search(normalized) or LOCATION_IDENTIFIER.search(question))
                and re.search(r"\b(?:bao nhieu|so luong|ton|con lai)\b", normalized)
            )
            or (role == UserRole.WAREHOUSE and RESEARCH_REQUEST.search(normalized))
            or (
                not HOW_TO.search(normalized)
                and LIVE_TIME.search(normalized)
                and LIVE_COUNT.search(normalized)
                and LIVE_SUBJECT.search(normalized)
            )
            or (
                not HOW_TO.search(normalized)
                and TRANSACTION_ID.search(normalized)
                and TRANSACTION_STATE.search(normalized)
            )
        ):
            return []
        try:
            sections = self.repository.search(question, role, self.settings.assistant_search_limit)
        except SQLAlchemyError:
            raise DomainError(
                503, "ASSISTANT_DATABASE_ERROR", "Không thể truy xuất tài liệu."
            ) from None
        selected = []
        size = 0
        for section in sections:
            if size + len(section.content) > self.settings.assistant_max_context_chars:
                continue
            selected.append(section)
            size += len(section.content)
        return selected

    def respond(self, question, sections):
        if not sections:
            return ChatResponse(status="insufficient_context", answer=INSUFFICIENT, citations=[])
        try:
            result = self.provider.answer(question, sections)
        except DomainError:
            raise
        except Exception:
            raise DomainError(
                502, "ASSISTANT_PROVIDER_ERROR", "Không thể kết nối trợ lý. Vui lòng thử lại."
            ) from None
        if not isinstance(result, dict):
            return ChatResponse(status="insufficient_context", answer=INSUFFICIENT, citations=[])
        ids = result.get("evidence_ids")
        candidates = enumerate_sentences(sections)
        if (
            not isinstance(ids, list)
            or not ids
            or len(ids) > 6
            or any(type(index) is not int or index < 1 or index > len(candidates) for index in ids)
        ):
            return ChatResponse(status="insufficient_context", answer=INSUFFICIENT, citations=[])
        citations = []
        answer_parts = []
        cited = set()
        for index in sorted(set(ids)):
            section, sentence = candidates[index - 1]
            if RULE_OVERRIDE.search(normalize(sentence)):
                return ChatResponse(
                    status="insufficient_context", answer=INSUFFICIENT, citations=[]
                )
            answer_parts.append(sentence)
            if section.section_id in cited:
                continue
            cited.add(section.section_id)
            query = urlencode({"version": section.version})
            source_url = (
                f"{self.settings.api_v1_prefix}/assistant/sources/{section.section_id}?{query}"
            )
            citations.append(
                Citation(
                    section_id=section.section_id,
                    title=section.title,
                    version=section.version,
                    url=source_url,
                )
            )
        return ChatResponse(status="answered", answer=" ".join(answer_parts), citations=citations)


def read_source(repository, section_id, role, version):
    try:
        result = repository.source(section_id, role)
    except SQLAlchemyError:
        raise DomainError(
            503, "ASSISTANT_DATABASE_ERROR", "Không thể truy xuất tài liệu."
        ) from None
    if result is None or (version is not None and result.version != version):
        raise DomainError(404, "ASSISTANT_SOURCE_NOT_FOUND", "Không tìm thấy nguồn tài liệu.")
    return SourceResponse(**result._mapping)
