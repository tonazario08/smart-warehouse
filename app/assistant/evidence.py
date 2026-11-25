import re


def split_sentences(content: str) -> list[str]:
    """Return nonempty whole source sentences in original order."""
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", content) if part.strip()]


def enumerate_sentences(sections):
    """Map request-local sentence IDs to authorized sections and original text."""
    return [
        (section, sentence) for section in sections for sentence in split_sentences(section.content)
    ]
