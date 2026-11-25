"""Run the frozen RAG evaluation against the model and corpus on a local test database."""

import argparse
import hashlib
import json
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.assistant.cli import parse_document
from app.assistant.provider import ModelProvider
from app.assistant.repository import AssistantRepository
from app.assistant.service import AssistantService
from app.core.config import get_settings
from app.core.errors import DomainError
from app.db.session import get_engine
from app.models import UserRole

DATA_DIR = Path("docs/assistant")


class RecordedRetrieval(AssistantRepository):
    def __init__(self, session):
        super().__init__(session)
        self.sources = []

    def search(self, question, role, limit):
        sections = super().search(question, role, limit)
        self.sources = [section.section_id for section in sections]
        return sections


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--questions", type=Path, default=DATA_DIR / "evaluation.json")
    args = parser.parse_args()
    settings = get_settings()
    database = make_url(settings.database_url)
    if database.host not in {"127.0.0.1", "localhost", "::1"} or not (
        database.database or ""
    ).endswith("_test"):
        parser.error("Use a loopback PostgreSQL database ending in _test.")

    test_bytes = args.questions.read_bytes()
    cases = json.loads(test_bytes)
    provider = ModelProvider(settings)
    provider.validate_configuration()
    results = []
    with Session(get_engine(settings.database_url)) as session:
        session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        sources = sorted(DATA_DIR.glob("*.md"))
        expected = sorted(
            (parse_document(path) for path in sources), key=lambda row: row["section_id"]
        )
        actual = session.execute(
            text("""
            SELECT section_id, title, version, source, read_role, content, normalized
            FROM assistant_sections ORDER BY section_id
            """)
        ).mappings()
        if [dict(row) for row in actual] != expected:
            parser.error("Database corpus does not match the approved Markdown files.")
        repository = RecordedRetrieval(session)
        service = AssistantService(repository, provider, settings)
        for case in cases:
            repository.sources = []
            try:
                response = service.chat(case["question"], UserRole(case["role"]))
            except DomainError as error:
                outcome = {"error": error.code}
                print(case["id"], error.code, flush=True)
            else:
                outcome = {"response": response.model_dump()}
                print(case["id"], response.status, flush=True)
            results.append({**case, **outcome, "retrieved_sections": repository.sources})
    evidence = {
        "evaluation_sha256": hashlib.sha256(test_bytes).hexdigest(),
        "corpus": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sources
        },
        "model": settings.assistant_model,
        "search_limit": settings.assistant_search_limit,
        "max_context_chars": settings.assistant_max_context_chars,
        "timeout_seconds": settings.assistant_timeout_seconds,
        "results": results,
    }
    with args.output.open("x", encoding="utf-8") as file:
        json.dump(evidence, file, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
