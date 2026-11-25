import re
import unicodedata

from sqlalchemy import text

from app.models import UserRole


def normalize(value):
    value = value.lower().replace("đ", "d")
    return "".join(
        c for c in unicodedata.normalize("NFD", value) if unicodedata.category(c) != "Mn"
    )


STOP_WORDS = frozenset(
    {
        "ma",
        "so",
        "cho",
        "toi",
        "biet",
        "quy",
        "trinh",
        "kho",
        "la",
        "gi",
        "the",
        "nao",
        "va",
        "voi",
        "cua",
        "ve",
        "nhu",
        "mot",
        "nhung",
        "duoc",
        "can",
        "co",
        "khi",
        "lam",
        "sao",
        "theo",
        "hay",
        "ban",
        "vui",
        "long",
        "xin",
        "hoi",
    }
)

WAREHOUSE_TERMS = {
    "chung tu": "phieu",
    "nhan hang": "nhap kho",
    "tiep nhan hang": "nhap kho",
    "lo hang moi": "hang nhap kho",
    "hang roi kho": "xuat kho",
    "hang dua ra khoi kho": "xuat kho",
    "hang duoc dua ra khoi kho": "xuat kho",
    "hang ra kho": "xuat kho",
    "hang ra khoi kho": "xuat kho",
    "dieu chuyen": "chuyen kho",
    "luan chuyen": "chuyen kho",
    "dich chuyen": "chuyen kho",
    "hang dang co": "ton hien tai",
    "uoc luong tuong lai": "du bao",
}
WAREHOUSE_PHRASE = re.compile(
    r"\b(?:" + "|".join(sorted(WAREHOUSE_TERMS, key=len, reverse=True)) + r")\b"
)


def search_terms(question):
    normalized = WAREHOUSE_PHRASE.sub(
        lambda match: WAREHOUSE_TERMS[match.group()], normalize(question)
    )
    return [word for word in re.findall(r"[a-z0-9]+", normalized) if word not in STOP_WORDS]


OPERATION_PHRASES = {
    "nhap": re.compile(
        r"(?:\b(?:phieu nhap|nhap kho|nhap hang|hang (?:vao|ve) kho)\b|"
        r"(?<!xac )(?<!ghi )\bnhan hang\b)"
    ),
    "xuat": re.compile(
        r"\b(?:phieu xuat|(?:phieu|chung tu) hang ra|xuat kho|xuat hang|hang roi kho|"
        r"hang(?:\s+[a-z0-9]+){0,6}\s+ra\s+(?:khoi\s+)?kho)\b"
    ),
    "chuyen": re.compile(
        r"\b(?:chuyen kho|chuyen hang|phieu chuyen|dieu chuyen|luan chuyen|dich chuyen)\b"
    ),
    "nghien cuu": re.compile(r"\bnghien cuu\b"),
    "du bao": re.compile(r"\bdu bao\b"),
    "an toan": re.compile(
        r"\b(?:ton kho an toan|ton an toan|rop|diem dat hang lai|bo sung hang|"
        r"nguong(?:\s+[a-z0-9]+){0,4}\s+bo sung|"
        r"du phong(?:\s+[a-z0-9]+){0,5}\s+sai so(?:\s+[a-z0-9]+){0,3}\s+du bao)\b"
    ),
}
NEGATED_OPERATION = re.compile(r"\b(?:khong|khong phai|khac|ngoai|tru)(?:\s+[a-z0-9]+){0,3}\s*$")
MULTI_TOPIC = re.compile(r"\b(?:so sanh|phan biet|khac nhau|khac biet|lich su)\b")


def operation_anchor(question):
    normalized = normalize(question)
    if MULTI_TOPIC.search(normalized):
        return None
    found = set()
    strong_operations = set()
    strong_policy = False
    joined_operation = False
    for operation, pattern in OPERATION_PHRASES.items():
        for match in pattern.finditer(normalized):
            prefix = normalized[max(0, match.start() - 50) : match.start()]
            prefix = re.split(r"[,;.!?]", prefix)[-1]
            if not NEGATED_OPERATION.search(prefix):
                found.add(operation)
                if operation in {"nhap", "xuat"} and re.match(
                    r"(?:phieu|nhap|xuat)\s+(?:nhap|xuat|kho)\b", match.group()
                ):
                    strong_operations.add(operation)
                if operation == "an toan" and match.group() != "bo sung hang":
                    strong_policy = True
                if re.search(r"\b(?:va|hoac)\s*$", prefix):
                    joined_operation = True
    if len(found) == 1:
        return next(iter(found))
    if joined_operation:
        return None
    if found == {"chuyen", "nhap"} or found == {"chuyen", "xuat"}:
        return "chuyen"
    if found in ({"du bao", "nghien cuu"}, {"du bao", "an toan"}):
        return next(iter(found - {"du bao"}))
    if len(strong_operations) == 1 and found <= {"nhap", "xuat", "an toan"}:
        if "an toan" not in found or not strong_policy:
            return next(iter(strong_operations))
    return None


class AssistantRepository:
    def __init__(self, session):
        self.session = session

    def search(self, question, role, limit):
        terms = search_terms(question)
        if not terms:
            return []
        terms = list(dict.fromkeys(terms))
        anchor = operation_anchor(question) or ""
        query = " | ".join(dict.fromkeys([*terms, *anchor.split()]))
        title_terms = sorted(set(terms).intersection({"nhap", "xuat", "chuyen", "du", "bao"}))
        title_query = " | ".join(title_terms)
        minimum_matches = max(1, (len(terms) * 3 + 7) // 8)
        rows = self.session.execute(
            text("""
            WITH readable AS MATERIALIZED (
                SELECT section_id, title, version, content, search_vector,
                    to_tsvector('simple', replace(regexp_replace(
                        normalize(lower(title), NFD), '[̀-ͯ]', '', 'g'
                    ), 'đ', 'd')) AS title_vector
                FROM assistant_sections
                WHERE (read_role = 'warehouse' OR :is_admin)
                  AND search_vector @@ to_tsquery('simple', :query)
            )
            SELECT section_id, title, version, content FROM readable
            WHERE (
                (SELECT count(*) FROM unnest(CAST(:terms AS text[])) AS token
                 WHERE search_vector @@ plainto_tsquery('simple', token)) >= :minimum_matches
                OR (:anchor <> '' AND title_vector @@ plainto_tsquery('simple', :anchor))
            )
            AND (
                :anchor = ''
                OR NOT EXISTS (
                    SELECT 1 FROM readable AS candidate
                    WHERE candidate.title_vector @@ plainto_tsquery('simple', :anchor)
                )
                OR title_vector @@ plainto_tsquery('simple', :anchor)
            )
            ORDER BY
                CASE WHEN :anchor <> '' AND title_vector @@ plainto_tsquery('simple', :anchor)
                     THEN 1 ELSE 0 END DESC,
                CASE WHEN :title_query = '' THEN 0 ELSE
                     ts_rank_cd(title_vector, to_tsquery('simple', :title_query)) END DESC,
                ts_rank_cd(search_vector, to_tsquery('simple', :query)) DESC, section_id
            LIMIT :limit
        """),
            {
                "is_admin": role == UserRole.ADMIN,
                "query": query,
                "title_query": title_query,
                "anchor": anchor,
                "terms": terms,
                "minimum_matches": minimum_matches,
                "limit": limit,
            },
        )
        return rows.all()

    def source(self, section_id, role):
        return self.session.execute(
            text("""
            SELECT section_id, title, version, content FROM assistant_sections
            WHERE section_id = :section_id AND (read_role = 'warehouse' OR :is_admin)
        """),
            {"section_id": section_id, "is_admin": role == UserRole.ADMIN},
        ).first()
