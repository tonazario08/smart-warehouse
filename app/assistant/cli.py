import argparse
import hashlib
import json
import re
from pathlib import Path

import yaml
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.assistant.repository import normalize
from app.core.config import get_settings
from app.db.session import get_engine


def parse_document(path):
    text_value = path.read_text(encoding="utf-8")
    parts = text_value.split("---", 2)
    if len(parts) != 3 or parts[0].strip():
        raise ValueError("Invalid document front matter")
    meta = yaml.safe_load(parts[1])
    required = {"section_id", "title", "version", "source", "read_role"}
    if not isinstance(meta, dict) or set(meta) != required:
        raise ValueError("Invalid document metadata")
    if any(not isinstance(meta[k], str) or not meta[k].strip() for k in required):
        raise ValueError("Invalid document metadata values")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", meta["section_id"]):
        raise ValueError("Invalid section identifier")
    if meta["read_role"] not in {"warehouse", "admin"}:
        raise ValueError("Invalid document role")
    if meta["source"] != f"docs/assistant/{path.name}" or path.suffix != ".md":
        raise ValueError("Invalid document source")
    content = parts[2].strip()
    if not content or len(content) > 50000:
        raise ValueError("Invalid document content")
    if len(meta["section_id"]) > 100 or len(meta["title"]) > 250 or len(meta["version"]) > 100:
        raise ValueError("Document metadata too long")
    return {**meta, "content": content, "normalized": normalize(meta["title"] + " " + content)}


def import_documents(session, paths):
    documents = [parse_document(path) for path in paths]
    if not documents or len({d["section_id"] for d in documents}) != len(documents):
        raise ValueError("Documents must have unique identifiers")
    if session.get_bind().dialect.name == "postgresql":
        session.execute(text("LOCK TABLE assistant_sections IN SHARE ROW EXCLUSIVE MODE"))
    for document in documents:
        fingerprint = hashlib.sha256(
            json.dumps(
                {key: document[key] for key in ("title", "source", "read_role", "content")},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        existing = session.execute(
            text("""SELECT fingerprint FROM assistant_section_versions
            WHERE section_id = :section_id AND version = :version"""),
            document,
        ).scalar_one_or_none()
        if existing is not None and existing != fingerprint:
            raise ValueError("Document version cannot be changed")
        if existing is None:
            session.execute(
                text("""INSERT INTO assistant_section_versions
                (section_id, version, fingerprint) VALUES (:section_id, :version, :fingerprint)"""),
                {**document, "fingerprint": fingerprint},
            )
    session.execute(text("DELETE FROM assistant_sections"))
    session.execute(
        text("""INSERT INTO assistant_sections
        (section_id, title, version, source, read_role, content, normalized)
        VALUES (:section_id, :title, :version, :source, :read_role, :content, :normalized)
    """),
        documents,
    )
    session.commit()
    return len(documents)


def main():
    parser = argparse.ArgumentParser(description="Import the complete approved Markdown corpus")
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    paths = sorted(args.directory.glob("*.md"))
    with Session(get_engine(get_settings().database_url)) as session:
        count = import_documents(session, paths)
    print(f"Imported {count} sections.")


if __name__ == "__main__":
    main()
