from app.assistant.evidence import enumerate_sentences
from app.core.config import get_settings
from app.main import create_app


class FixtureProvider:
    def answer(self, question, sections):
        if "chuyển kho" in question.casefold():
            for index, (section, sentence) in enumerate(enumerate_sentences(sections), 1):
                if section.section_id == "chuyen-kho" and "kho đích" in sentence:
                    return {"evidence_ids": [index]}
        return {"evidence_ids": []}


settings = get_settings()
if settings.app_env != "integration" or not settings.assistant_enabled:
    raise RuntimeError("Assistant fixture requires an isolated integration environment")

app = create_app(settings)
app.state.assistant_provider = FixtureProvider()
