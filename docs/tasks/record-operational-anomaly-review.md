# record-operational-anomaly-review — Ghi nhận đánh giá cảnh báo sau xuất B2B

- Status: DONE
- Phase: M9 vận hành
- Plan: `docs/superpowers/plans/2026-11-22-operational-anomaly-review.md` (đã duyệt)
- Depends on: `docs/tasks/score-fulfilled-b2b-anomalies.md`
- Created: 2026-11-22
- Started: 2026-11-22
- Completed: 2026-11-22

## Goal

Cho nhân viên có quyền ghi và tra lịch sử đánh giá cảnh báo sau xuất B2B. Tách nhận định của người xem khỏi điểm Isolation Forest, SHAP và kết luận nguyên nhân.

## Context

Đề cương V2 §2.9 yêu cầu bằng chứng/phản hồi riêng cho nguyên nhân nghiệp vụ; §3.5 mô tả đánh giá từng cảnh báo. M9 fixture đã có lịch sử đánh giá nhưng luồng chấm theo giao dịch xuất B2B chỉ có API đọc. Không có tập nhãn thật để báo cáo chất lượng thực địa.

## In Scope

- Migration cộng thêm lưu lịch sử append-only theo giao dịch, dấu vân tay kết quả và phiên bản đánh giá.
- Xem lịch sử/ghi đánh giá trên chi tiết cảnh báo hợp lệ; trạng thái: Ghi nhận vấn đề nghiệp vụ / Giao dịch hợp lệ / Chưa đủ bằng chứng. Kèm ghi chú bắt buộc, lưu người đánh giá và thời điểm.
- Phân quyền và cô lập fixture theo cổng hiện có; kiểm thử bằng PostgreSQL dùng một lần và tài khoản test.

## Out of Scope

Không thay đổi mô hình/điểm/ngưỡng/SHAP/link phiếu, dữ liệu kho hoặc luồng duyệt/xuất; không chấm lại, bật artifact vận hành, triển khai Shadow Mode, tự huấn luyện/tinh chỉnh, hoặc xem đánh giá người dùng là ground truth đã xác minh. Không sửa M9 fixture, không migrate/deploy/merge hệ thống chính trong task này.

## Acceptance Criteria

- [x] AC-1. Cảnh báo flagged đã hoàn tất có lineage hợp lệ và nhìn thấy được mới có quyền ghi/xem đánh giá. Không để khách/ẩn danh thấy dữ liệu; fixture chỉ hiển thị trong test cô lập và opt-in.
- [x] AC-2. Lần ghi tạo phiên bản kế tiếp có actor/thời điểm, trạng thái và ghi chú. Reload/đăng nhập lại vẫn đọc được; giữ lịch sử cũ. Không ghi đè bản cũ.
- [x] AC-3. Retry cùng key và nội dung trả đúng kết quả đã lưu, không tăng phiên bản; cùng key khác nội dung hoặc expected version cũ trả 409. Hai thao tác đồng thời không bỏ qua xung đột.
- [x] AC-4. Pending, unavailable, failed, normal, kết quả không hợp lệ hoặc provenance lệch: không nhận/xem đánh giá. Không đổi score/threshold/explanation, tồn, đơn, phiếu hoặc bảng M9.
- [x] AC-5. Giao diện ghi rõ đây là nhận định riêng; không suy nguyên nhân từ SHAP. Xem lịch sử, xử lý 409 và refresh trạng thái đúng; client không tải đánh giá.
- [x] AC-6. Migration 0010→head→0010 trên DB riêng, không backfill, job/stock/voucher giữ nguyên.

## Verification Commands

- Đề xuất ca mới (chưa tồn tại): `python -m pytest -q tests/postgres/test_operational_anomaly_reviews.py`.
- Hồi quy: `python -m pytest -q tests/postgres/test_operational_anomaly_worker.py tests/test_operational_anomaly_artifact.py`; thêm bộ migration mới và full suite là điều kiện nghiệm thu.
- Client: `npm run typecheck`, `npm run build`, `npm run test:all`; smoke trình duyệt thật trên DB dùng một lần, không filesystem/DB main.
- `python -m ruff check app tests alembic`, `git diff --check`.

## Progress Log

- 2026-11-22: Soạn nháp ngoài repo, chưa đổi dự án. Chờ route chính xác, phê duyệt plan và dependency DONE.

- 2026-11-22: DRAFT → READY → IN_PROGRESS. Người dùng duyệt đúng đường dẫn và plan; dependency DONE. Baseline cô lập là 14520ce cùng bản vá 0010 đã kiểm chứng (không tự nhận mang đúng Git object Windows 4982123), head 0010 duy nhất.


- 2026-11-22: RED chứng minh GET history của một giao dịch flagged thật trong DB thử trả 404 trước khi có code. API, migration, UI hoàn thành; IN_PROGRESS → VERIFYING. Đối chiếu lại base bằng Git bundle 4982123117ff7ec468a8e3d263670ac7b69e3b33: chỉ có diff đúng phạm vi task (bao gồm chốt ledger của prerequisite).

- 2026-11-22: VERIFYING → REVIEWING. Hoàn tất bộ backend đầy đủ trên Linux và trình duyệt thật Windows trên bản vá đóng băng; đối chiếu AC-1–6.
- 2026-11-22: REVIEWING → DONE. Review độc lập không còn vấn đề cản trở; chỉ nghiệm thu bản cô lập.

## Verification Evidence

- Backend: 59 ca PostgreSQL/model đạt, một cảnh báo TestClient có sẵn. Suite gồm history reload, phiên bản/retry/CAS và concurrent writers, quyền, synthetic opt-in, source drift, migration 0010→0011→0010, worker và hồi quy migration.
- Uvicorn/API và worker thật, PostgreSQL riêng: transaction flagged #2 → voucher #400, warehouse ghi nhận đánh giá phiên bản 1 và admin đọc lại; thử lại cùng key giữ nguyên phiên bản, key mới với phiên bản cũ bị 409, client 403. Score, tồn và bảng M9 không đổi. Không liên quan phiếu nào trong hệ thống chính.
- Frontend: typecheck/build, 543 Vitest và 88 Node host đạt, 21 ca tập trung (bao gồm 11 ca mới). Chromium thật Windows với PG18/API/Vite và worker riêng trên bản vá đóng băng đạt: warehouse ghi đánh giá, tải lại vẫn giữ nội dung/phiên bản, admin đọc được, client bị chặn; không ghi cho giao dịch thiếu mô hình và không đổi điểm/SHAP. Fixture có nhãn tổng hợp.
- Bộ backend Linux đầy đủ trên PG riêng: 1.847 đạt, ba ca chỉ dành cho Windows được loại, một cảnh báo Starlette/TestClient có sẵn, 711,42 giây. Không dùng kết quả này để suy rằng ba ca loại đã chạy; Windows đã kiểm thử browser độc lập. Xác nhận các tiến trình thử nghiệm đã dừng.
- Ruff và diff check đạt. Không merge, không migrate hệ thống chính, không bật model hoặc huấn luyện.

## Review Result

- Result: APPROVED (review độc lập, không finding cản trở).

## Completion Evidence

- Hoàn thành AC-1–6 trong phạm vi đã duyệt trên bản sao cô lập của `4982123`; các file ứng dụng đã kiểm thử giữ nguyên byte sau khi đóng băng.
- Không commit, merge, triển khai hoặc migrate hệ thống chính, không bật artifact thật, không huấn luyện hay chấm lại dữ liệu cũ. Những kiểm thử browser/scorer dùng fixture riêng; không xác nhận hiệu quả trên dữ liệu thật.
