from pathlib import Path

import pytest
from sqlalchemy import text

from app.assistant.cli import import_documents
from app.assistant.repository import AssistantRepository
from app.models import UserRole

pytestmark = pytest.mark.postgres


def document(path: Path, section_id, title, version, role, content):
    path.write_text(
        f'''---
section_id: {section_id}
title: {title}
version: "{version}"
source: docs/assistant/{path.name}
read_role: {role}
---
{content}
''',
        encoding="utf-8",
    )
    return path


def test_import_replaces_versions_and_retrieval_filters_roles(postgres_session, tmp_path):
    public = document(
        tmp_path / "public.md",
        "receiving",
        "Nhập kho",
        "1",
        "warehouse",
        "Kiểm đếm kiện hàng khi nhập kho",
    )
    restricted = document(
        tmp_path / "private.md",
        "admin-guide",
        "Bí mật quản trị",
        "1",
        "admin",
        "Quản trị nhập kho hạn chế",
    )
    import_documents(postgres_session, [public, restricted])
    import_documents(postgres_session, [public, restricted])
    repo = AssistantRepository(postgres_session)
    assert (
        postgres_session.execute(text("SELECT count(*) FROM assistant_sections")).scalar_one() == 2
    )
    assert [
        s.section_id for s in repo.search("kiem dem kien hang nhap kho", UserRole.WAREHOUSE, 10)
    ] == ["receiving"]
    assert repo.search("Nhập học đại học ở đâu?", UserRole.WAREHOUSE, 10) == []
    assert repo.source("admin-guide", UserRole.WAREHOUSE) is None
    assert repo.source("admin-guide", UserRole.ADMIN) is not None
    public = document(
        tmp_path / "public.md",
        "receiving",
        "Nhập kho",
        "2",
        "warehouse",
        "Đối chiếu phiếu giao hàng",
    )
    import_documents(postgres_session, [public])
    assert repo.source("receiving", UserRole.ADMIN).version == "2"
    assert repo.source("admin-guide", UserRole.ADMIN) is None
    postgres_session.execute(text("DELETE FROM assistant_sections"))
    postgres_session.execute(text("DELETE FROM assistant_section_versions"))
    postgres_session.commit()


def test_chat_releases_database_before_model_and_enforces_source_access(
    postgres_session, postgres_engine, tmp_path, postgres_url
):
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    from app.auth.dependencies import get_current_user
    from app.core.config import Settings
    from app.db.session import get_session
    from app.main import create_app

    public = document(
        tmp_path / "public.md", "receiving", "Nhập kho", "1", "warehouse", "Kiểm đếm nhập kho"
    )
    private = document(
        tmp_path / "private.md", "admin-guide", "Nhập kho quản trị", "1", "admin", "MẬT nhập kho"
    )
    import_documents(postgres_session, [public, private])
    settings = Settings(
        app_env="test",
        database_url=postgres_url,
        jwt_secret_key="test-only-jwt-secret-with-at-least-32-characters",
        assistant_enabled=True,
        _env_file=None,
    )
    app = create_app(settings)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=1, role=UserRole.WAREHOUSE
    )
    app.dependency_overrides[get_session] = lambda: postgres_session
    database_state_during_model_call = []

    class Provider:
        def answer(self, question, sections):
            database_state_during_model_call.append(
                (postgres_session.in_transaction(), postgres_engine.pool.checkedout())
            )
            assert all("MẬT" not in item.content for item in sections)
            return {"evidence_ids": [1]}

    app.state.assistant_provider = Provider()
    with TestClient(app) as client:
        response = client.post("/api/v1/assistant/chat", json={"question": "nhập kho"})
        assert response.status_code == 200
        assert response.json()["status"] == "answered"
        assert "MẬT" not in response.text
        assert client.get("/api/v1/assistant/sources/admin-guide").status_code == 404
        assert client.get(response.json()["citations"][0]["url"]).json()["version"] == "1"
        assert client.get("/api/v1/assistant/sources/receiving?version=0").status_code == 404
    postgres_session.execute(text("DELETE FROM assistant_sections"))
    postgres_session.execute(text("DELETE FROM assistant_section_versions"))
    postgres_session.commit()
    assert database_state_during_model_call == [(False, 0)]


def test_invalid_import_leaves_existing_corpus(postgres_session, tmp_path):
    public = document(tmp_path / "public.md", "receiving", "Nhập kho", "1", "warehouse", "Kiểm đếm")
    import_documents(postgres_session, [public])
    invalid = document(tmp_path / "invalid.md", "receiving", "Khác", "2", "admin", "Không hợp lệ")
    with pytest.raises(ValueError):
        import_documents(postgres_session, [public, invalid])
    assert AssistantRepository(postgres_session).source("receiving", UserRole.ADMIN).version == "1"
    postgres_session.execute(text("DELETE FROM assistant_sections"))
    postgres_session.execute(text("DELETE FROM assistant_section_versions"))
    postgres_session.commit()


def test_import_rejects_changed_content_for_a_reused_version(postgres_session, tmp_path):
    path = document(tmp_path / "public.md", "receiving", "Nhập kho", "1", "warehouse", "Bản gốc")
    import_documents(postgres_session, [path])
    document(path, "receiving", "Nhập kho", "1", "warehouse", "Nội dung đã đổi")
    with pytest.raises(ValueError, match="version"):
        import_documents(postgres_session, [path])
    postgres_session.rollback()
    assert (
        AssistantRepository(postgres_session).source("receiving", UserRole.ADMIN).content
        == "Bản gốc"
    )
    document(path, "receiving", "Nhập kho", "2", "warehouse", "Bản mới")
    import_documents(postgres_session, [path])
    document(path, "receiving", "Nhập kho", "1", "warehouse", "Nội dung đã đổi")
    with pytest.raises(ValueError, match="version"):
        import_documents(postgres_session, [path])
    postgres_session.rollback()
    postgres_session.execute(text("DELETE FROM assistant_sections"))
    postgres_session.execute(text("DELETE FROM assistant_section_versions"))
    postgres_session.commit()


def test_import_waits_for_another_import_transaction(postgres_engine, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from sqlalchemy.orm import Session

    path = document(tmp_path / "lock.md", "lock-test", "Kho", "1", "warehouse", "Nội dung")
    started = Event()

    def run_import():
        with Session(postgres_engine) as session:
            started.set()
            return import_documents(session, [path])

    with postgres_engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(text("LOCK TABLE assistant_sections IN SHARE ROW EXCLUSIVE MODE"))
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(run_import)
            assert started.wait(2)
            from concurrent.futures import TimeoutError

            with pytest.raises(TimeoutError):
                future.result(timeout=0.3)
            transaction.commit()
            assert future.result(timeout=5) == 1
    with postgres_engine.begin() as connection:
        connection.execute(text("DELETE FROM assistant_sections"))
        connection.execute(text("DELETE FROM assistant_section_versions"))


def test_concurrent_version_conflict_is_rejected_after_lock(postgres_engine, tmp_path):
    from concurrent.futures import ThreadPoolExecutor, TimeoutError
    from threading import Event

    from sqlalchemy.orm import Session

    path = document(tmp_path / "race.md", "race-test", "Kho", "1", "warehouse", "New text")
    started = Event()

    def run_import():
        with Session(postgres_engine) as session:
            started.set()
            return import_documents(session, [path])

    with postgres_engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(text("LOCK TABLE assistant_sections IN SHARE ROW EXCLUSIVE MODE"))
        connection.execute(
            text(
                "INSERT INTO assistant_section_versions "
                "(section_id, version, fingerprint) VALUES ('race-test', '1', :fingerprint)"
            ),
            {"fingerprint": "0" * 64},
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(run_import)
            assert started.wait(2)
            with pytest.raises(TimeoutError):
                future.result(timeout=0.3)
            transaction.commit()
            with pytest.raises(ValueError, match="version"):
                future.result(timeout=5)
    with postgres_engine.begin() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM assistant_sections WHERE section_id = 'race-test'")
            ).scalar_one()
            == 0
        )
        connection.execute(
            text("DELETE FROM assistant_section_versions WHERE section_id = 'race-test'")
        )


def test_affirmed_operation_anchor_ranks_authorized_matching_guide(postgres_session, tmp_path):
    incoming = document(
        tmp_path / "in.md",
        "inbound",
        "Ghi nhận nhập kho",
        "1",
        "warehouse",
        "Chọn sản phẩm, số lượng và xác nhận phiếu nhập.",
    )
    outgoing = document(
        tmp_path / "out.md",
        "outbound",
        "Ghi nhận xuất kho",
        "1",
        "warehouse",
        "Chọn kho xuất, sản phẩm, số lượng và xác nhận phiếu xuất.",
    )
    private = document(
        tmp_path / "private.md",
        "admin-extra",
        "Xuất kho quản trị",
        "1",
        "admin",
        "Xác nhận xuất kho cho quản trị.",
    )
    import_documents(postgres_session, [incoming, outgoing, private])
    repo = AssistantRepository(postgres_session)
    cases = [
        ("Phiếu nhập cần nhập các mục chi tiết nào trước khi tiếp tục bước kế tiếp?", "inbound"),
        ("Làm sao xác nhận hàng đưa ra khỏi kho khi vừa nhập sai mô tả?", "outbound"),
    ]
    for question, expected in cases:
        result = repo.search(question, UserRole.WAREHOUSE, 5)
        assert result and result[0].section_id == expected
        assert all(section.section_id != "admin-extra" for section in result)
    postgres_session.execute(text("DELETE FROM assistant_sections"))
    postgres_session.execute(text("DELETE FROM assistant_section_versions"))
    postgres_session.commit()


def test_explicit_operations_return_only_matching_authorized_guide(postgres_session, tmp_path):
    incoming = document(
        tmp_path / "incoming.md",
        "receiving",
        "Hướng dẫn nhập kho",
        "1",
        "warehouse",
        "Kiểm tra số lượng phiếu nhập kho trước khi xác nhận.",
    )
    outgoing = document(
        tmp_path / "outgoing.md",
        "dispatch",
        "Hướng dẫn xuất kho",
        "1",
        "warehouse",
        "Ghi nhận phiếu xuất hàng ra khỏi kho sau khi kiểm tra số lượng.",
    )
    transfer = document(
        tmp_path / "transfer.md",
        "transfer",
        "Chuyển kho",
        "1",
        "warehouse",
        "Kiểm tra số lượng phiếu xuất và nhập khi chuyển kho.",
    )
    private = document(
        tmp_path / "private.md",
        "restricted",
        "Xuất kho quản trị",
        "1",
        "admin",
        "Chỉ quản trị viên được đọc mục này.",
    )
    import_documents(postgres_session, [incoming, outgoing, transfer, private])
    repo = AssistantRepository(postgres_session)
    for question, expected in [
        ("Theo hướng dẫn nhập kho cần kiểm tra gì?", "receiving"),
        ("Hàng được ghi nhận đưa ra khỏi kho sau khi chọn sản phẩm thế nào?", "dispatch"),
        ("Số lượng nhập trên phiếu xuất phải được kiểm tra sao?", "dispatch"),
    ]:
        result = repo.search(question, UserRole.WAREHOUSE, 5)
        assert [row.section_id for row in result] == [expected]
    mixed = repo.search("Phiếu nhập và phiếu xuất", UserRole.WAREHOUSE, 5)
    assert {row.section_id for row in mixed} >= {"receiving", "dispatch"}
    assert all(row.section_id != "restricted" for row in mixed)
    postgres_session.execute(text("DELETE FROM assistant_sections"))
    postgres_session.execute(text("DELETE FROM assistant_section_versions"))
    postgres_session.commit()


def test_operation_filter_falls_back_if_no_permitted_title_matches(postgres_session, tmp_path):
    generic = document(
        tmp_path / "general.md",
        "general",
        "Hướng dẫn chung",
        "1",
        "warehouse",
        "Quy trình nhập kho gồm chọn kho nhận và sản phẩm.",
    )
    private = document(
        tmp_path / "admin.md",
        "admin-inbound",
        "Hướng dẫn nhập kho",
        "1",
        "admin",
        "Quy trình nhập kho cho quản trị viên.",
    )
    import_documents(postgres_session, [generic, private])
    rows = AssistantRepository(postgres_session).search("Hướng dẫn nhập kho", UserRole.WAREHOUSE, 5)
    assert [row.section_id for row in rows] == ["general"]
    postgres_session.execute(text("DELETE FROM assistant_sections"))
    postgres_session.execute(text("DELETE FROM assistant_section_versions"))
    postgres_session.commit()


def test_concept_anchors_isolate_authorized_sources_and_keep_mixed_fallback(
    postgres_session, tmp_path
):
    transfer = document(
        tmp_path / "move.md",
        "transfer",
        "Chuyển hàng giữa hai kho",
        "1",
        "warehouse",
        "Phiếu chuyển ghi xuất kho nguồn và nhập kho đích.",
    )
    inbound = document(
        tmp_path / "in.md",
        "incoming",
        "Ghi nhận nhập kho",
        "1",
        "warehouse",
        "Nhập kho ghi số lượng và phiếu.",
    )
    forecast = document(
        tmp_path / "forecast.md",
        "forecast",
        "Đọc màn hình dự báo",
        "1",
        "warehouse",
        "Dự báo có sai số nhu cầu trong thời gian chờ.",
    )
    policy = document(
        tmp_path / "policy.md",
        "policy",
        "Tồn kho an toàn và điểm đặt hàng lại",
        "1",
        "warehouse",
        "Tồn kho an toàn dự phòng sai số dự báo nhu cầu.",
    )
    research = document(
        tmp_path / "research.md",
        "research",
        "Cách đọc báo cáo nghiên cứu",
        "1",
        "admin",
        "Báo cáo nghiên cứu đối chiếu mô hình dự báo.",
    )
    import_documents(postgres_session, [transfer, inbound, forecast, policy, research])
    repo = AssistantRepository(postgres_session)
    cases = [
        ("Phiếu chuyển kho tạo xuất và nhập thế nào?", UserRole.WAREHOUSE, "transfer"),
        ("Tồn kho an toàn dự phòng sai số dự báo nhu cầu là gì?", UserRole.WAREHOUSE, "policy"),
        ("Báo cáo nghiên cứu về mô hình dự báo dùng để làm gì?", UserRole.ADMIN, "research"),
    ]
    for question, role, expected in cases:
        assert [row.section_id for row in repo.search(question, role, 5)] == [expected]
    mixed = repo.search("So sánh phiếu chuyển kho và nhập kho", UserRole.WAREHOUSE, 5)
    assert {row.section_id for row in mixed} >= {"transfer", "incoming"}
    assert all(row.section_id != "research" for row in mixed)
    postgres_session.execute(text("DELETE FROM assistant_sections"))
    postgres_session.execute(text("DELETE FROM assistant_section_versions"))
    postgres_session.commit()


def test_alternate_phrases_find_matching_permitted_sections(postgres_session, tmp_path):
    outbound = document(
        tmp_path / "out.md",
        "outbound",
        "Ghi nhận xuất kho",
        "1",
        "warehouse",
        "Chọn kho xuất và nhập số lượng nguyên dương.",
    )
    move = document(
        tmp_path / "move.md",
        "transfer",
        "Chuyển hàng giữa hai kho",
        "1",
        "warehouse",
        "Chọn kho nguồn và kho đích khác nhau.",
    )
    policy = document(
        tmp_path / "policy.md",
        "policy",
        "Tồn kho an toàn và điểm đặt hàng lại",
        "1",
        "warehouse",
        "Tồn an toàn dự phòng sai số dự báo nhu cầu.",
    )
    forecast = document(
        tmp_path / "forecast.md",
        "forecast",
        "Đọc màn hình dự báo",
        "1",
        "warehouse",
        "Dự báo nhu cầu có thể có sai số.",
    )
    private = document(
        tmp_path / "private.md",
        "private",
        "Chuyển kho quản trị",
        "1",
        "admin",
        "Chỉ quản trị viên được phép đọc.",
    )
    import_documents(postgres_session, [outbound, move, policy, forecast, private])
    repo = AssistantRepository(postgres_session)
    for question, expected in [
        ("Phiếu hàng ra cần nhập số lượng gì?", "outbound"),
        ("Phiếu chuyển ghi nhận điều gì?", "transfer"),
        ("Chuyển hàng từ một kho sang chính kho đó được không?", "transfer"),
        ("Lượng dự phòng trước các sai số của dự báo nghĩa là gì?", "policy"),
        ("Ngưỡng để cân nhắc bổ sung hàng được tính từ gì?", "policy"),
    ]:
        assert [row.section_id for row in repo.search(question, UserRole.WAREHOUSE, 5)] == [
            expected
        ]
    postgres_session.execute(text("DELETE FROM assistant_sections"))
    postgres_session.execute(text("DELETE FROM assistant_section_versions"))
    postgres_session.commit()


def test_strong_workflow_forecast_and_policy_priority_respects_role(postgres_session, tmp_path):
    outbound = document(
        tmp_path / "out.md",
        "dispatch",
        "Ghi nhận xuất kho",
        "1",
        "warehouse",
        "Chọn kho xuất và nhập số lượng nguyên dương.",
    )
    inbound = document(
        tmp_path / "in.md",
        "receiving",
        "Ghi nhận nhập kho",
        "1",
        "warehouse",
        "Chọn kho nhận hàng và sản phẩm.",
    )
    forecast = document(
        tmp_path / "forecast.md",
        "forecast",
        "Đọc màn hình dự báo",
        "1",
        "warehouse",
        "Dự báo có thể lệch so với quan sát.",
    )
    policy = document(
        tmp_path / "policy.md",
        "policy",
        "Tồn kho an toàn và điểm đặt hàng lại",
        "1",
        "warehouse",
        "Tồn kho an toàn dự phòng sai số dự báo.",
    )
    research = document(
        tmp_path / "research.md",
        "research",
        "Báo cáo nghiên cứu",
        "1",
        "admin",
        "Nghiên cứu đối chiếu mô hình dự báo.",
    )
    import_documents(postgres_session, [outbound, inbound, forecast, policy, research])
    repo = AssistantRepository(postgres_session)
    cases = [
        ("Phiếu xuất chọn nơi nhận hàng hay nơi cấp hàng?", UserRole.WAREHOUSE, "dispatch"),
        ("Dự báo có thể khác quan sát không?", UserRole.WAREHOUSE, "forecast"),
        ("Tồn kho an toàn dự phòng sai số dự báo gì?", UserRole.WAREHOUSE, "policy"),
        ("Báo cáo nghiên cứu về dự báo có ý nghĩa gì?", UserRole.ADMIN, "research"),
        ("Phiếu nhập để bổ sung hàng cần làm gì?", UserRole.WAREHOUSE, "receiving"),
    ]
    for question, role, expected in cases:
        assert [row.section_id for row in repo.search(question, role, 5)] == [expected]
    assert all(
        row.section_id != "research"
        for row in repo.search("Báo cáo nghiên cứu về dự báo có ý nghĩa gì?", UserRole.WAREHOUSE, 5)
    )
    postgres_session.execute(text("DELETE FROM assistant_sections"))
    postgres_session.execute(text("DELETE FROM assistant_section_versions"))
    postgres_session.commit()
