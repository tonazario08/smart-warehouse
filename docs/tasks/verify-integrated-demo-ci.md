# verify-integrated-demo-ci — Khôi phục kiểm tra E2E cho nhánh demo tích hợp

## Metadata

- Status: VERIFYING
- Phase: Tích hợp và phát hành bản demo
- Plan: docs/tasks/verify-integrated-demo-ci.md#implementation-plan
- Depends on: docs/tasks/implement-rag-assistant.md, docs/tasks/integrate-full-system-demo.md
- Created: 2026-11-16
- Started: 2026-11-16
- Completed: not completed

## Goal

Sửa điều kiện kiểm tra số ca E2E cho nhánh demo tích hợp, xác minh GitHub Actions và đưa bản đã kiểm chứng vào `feat/figma-ui-v2`.

## Context

Quality run 43890425350 dừng hai lần ở E2E trong khi backend, frontend và kiểm tra Windows đều đạt. Bộ E2E tổng hợp tăng từ 46 lên 51 ca. Năm ca mới trong `assistant.spec.ts` yêu cầu stack trợ lý riêng. Hồ sơ synthetic-only bỏ qua các ca đó và bộ kiểm tra kết quả hiện chỉ chấp nhận 11 ca bỏ qua.

## In Scope

- Đồng bộ điều kiện đếm cho bộ tổng hợp, giữ các phép kiểm tra ca bắt buộc, số ca đạt và số ca thất bại.
- Giữ hồ sơ CI công khai ở synthetic-only và kiểm thử hồi quy bộ chạy.
- Đẩy commit sửa lên nhánh hiện tại, kiểm tra Quality, review độc lập và fast-forward nhánh tích hợp khi bản sửa đạt.

## Out of Scope

- Thay đổi frontend, API, quyền, dữ liệu demo, deployment, hoặc bật provider RAG trong CI tổng hợp.
- Chỉnh hồ sơ E2E chuyên biệt hoặc thay đổi kiểm tra an toàn môi trường và cơ sở dữ liệu.

## Acceptance Criteria

- [ ] AC-1. Hồ sơ E2E tổng hợp chấp nhận đúng 35 ca đạt, 16 ca bỏ qua và 0 ca lỗi. Sai số lượng hoặc thiếu ca bắt buộc vẫn bị từ chối.
- [ ] AC-2. Năm ca trợ lý tiếp tục dành cho stack riêng. Các hồ sơ kiểm thử bổ sung và các kiểm tra cô lập giữ nguyên.
- [ ] AC-3. Kiểm thử bộ chạy, Ruff, git diff và Quality với đủ backend, Windows, frontend, E2E đạt. Review độc lập xác nhận phạm vi.
- [ ] AC-4. GitHub xác nhận `feat/figma-ui-v2` chứa bản sửa đã kiểm chứng; không có tệp sinh cục bộ hoặc dữ liệu thử nghiệm riêng được thêm.

## Verification Commands

- `python -m pytest -q tests/test_quality_ci.py` trước và sau sửa.
- `python -m ruff check tests/run_quality_ci.py tests/test_quality_ci.py`; `git diff --check`, kiểm tra staged diff.
- Playwright `test --list` cho bộ tổng hợp và `playwright test e2e/assistant.spec.ts --reporter=list --retries=0` với `E2E_ASSISTANT=0`.
- Xác nhận `gh run view` cho đúng commit sửa; xem kết quả backend, frontend, Windows và E2E. Kiểm tra nhánh đích qua `git ls-remote` sau fast-forward.

## Implementation Plan

Plan cho `verify-integrated-demo-ci`. Thêm test tái hiện số ca mới và sai số lượng. Cập nhật đúng kỳ vọng tổng hợp và tắt tường minh bộ trợ lý trong môi trường tổng hợp. Xác minh local, push nhánh hiện tại, kiểm tra CI và review rồi fast-forward nhánh đích.

## Progress Log

- 2026-11-16. READY. Người dùng duyệt tạo và triển khai chính xác task này để tiếp tục merge sau khi CI đạt. Hai dependency đã DONE.
- 2026-11-16. READY -> IN_PROGRESS. Baseline `e9ed295`, nhánh đích `547eb1c`. Phạm vi code giới hạn trong bộ kiểm tra CI và test tương ứng.
- 2026-11-16. IN_PROGRESS -> VERIFYING. Thêm kiểm thử cho số ca, ca bắt buộc, ca lỗi và cấu hình cô lập trợ lý. Sửa điều kiện đếm và môi trường synthetic-only. Kiểm tra local đã đạt, chờ run từ commit sửa.

## Verification Evidence

- RED. `python -m pytest -q tests/test_quality_ci.py` trước sửa bộ chạy: 3 lỗi đúng kỳ vọng và 18 ca đạt.
- GREEN. `python -m pytest -q tests/test_quality_ci.py tests/test_replenishment_verification.py` đạt 85 ca, một cảnh báo deprecation của Starlette.
- Ruff hai file Python và kiểm tra diff đạt. Playwright liệt kê 51 ca trên 9 file. Chạy riêng `assistant.spec.ts` với `E2E_ASSISTANT=0` cho đúng 5 ca bỏ qua.

## Review Result

- Result: PENDING

## Completion Evidence

Chưa hoàn tất.
