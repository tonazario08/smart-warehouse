# extend-forecast-chart-window — Biểu đồ tối đa 30 điểm cùng một bước

- Status: DONE
- Phase: Forecasting UX
- Plan: docs/superpowers/plans/2026-11-22-forecast-chart-window.md
- Depends on: docs/tasks/improve-forecasting-readability.md
- Created: 2026-11-22
- Started: 2026-11-22
- Completed: 2026-11-22

## Goal
Biểu đồ đủ dài để trình bày, mặc định ngày thứ 1, độc lập với trang bảng.

## Context
Bảng 20 dòng trộn 7 bước và có thể trộn chuỗi. Không lấy 30 dòng liên tiếp hoặc đổi kích thước trang.

## In Scope
Đường đọc chart riêng, dữ liệu có sẵn/bước/chuỗi/range, UI lọc và chứng cứ. Giữ nguyên bảo mật và trải nghiệm của phiên bản trước.

## Out of Scope
Đổi mô hình/dataset/schema/bảng, nghiên cứu/vận hành, cảnh báo B2B, API bảng, giới hạn phân quyền, main/DB/deploy/push.

## Acceptance Criteria
- [x] AC-1 — Cùng run/algorithm/horizon/lead/series, tối đa 30 ngày mới nhất sắp đúng, count/range không giả và actual null khác 0.
- [x] AC-2 — Mặc định lead 1, có thể chọn lead 6 với horizon 7; h1 không đọc lead 6. Qua trang bảng không đổi chart hoặc gọi lại; bảng vẫn 20.
- [x] AC-3 — Thiếu/lỗi chart không phá bảng, không render response cũ khi đổi lựa chọn/phiên. Role như cũ, query bất hợp lệ từ chối.
- [x] AC-4 — Focused backend/frontend, build và Windows browser demo đã xác minh. Giữ mã/metadata/WAPE/limits và tập E2E cũ.

## Verification Commands
- `python -m pytest -q tests/test_forecast_chart.py tests/test_forecasting_api.py tests/unit/test_architecture.py`
- Client `npm run typecheck`, `npm run build`, `npm run test:all`; Windows riêng đọc dataset pilot có sẵn; scoped diff.

## Progress Log
- 2026-11-22: READY → IN_PROGRESS; Toàn duyệt, prerequisite DONE, exact c660c4f + UX final tree 28034396d4f3bf25e4a559ae9af230c8bf7285c3. Một task duy nhất, không thay prior ledger.

- 2026-11-22: IN_PROGRESS → VERIFYING; source đóng băng để kiểm Chromium độc lập trên demo riêng.

- 2026-11-22: VERIFYING → REVIEWING; Chromium Windows độc lập đạt ở đúng freeze.
- 2026-11-22: REVIEWING → DONE; đạt AC-1…AC-4 trong demo, không đổi main.

## Verification Evidence
- RED trước implementation: hai test API chart không có endpoint; GREEN 29 backend (chart, forecast API, architecture), Ruff sạch. Bản artifact demo thật: h1/lead1 30 ngày 02–31/12/2022; h7/lead1 26/11–25/12, h7/lead6 01–30/12; một chuỗi, cả giá trị thực tế và dự báo bằng 2. Không suy ra độ chính xác vận hành; table vẫn page_size=20.
- Frontend exact 597 Vitest/55 file (40 Forecasting), 88 host; typecheck/build, scoped diff sạch. E2E mặc định không đổi.
- Chromium Windows độc lập `6f8b9f3998b635edf09f36fce87b2c386a7a4ae9` trên API pilot chỉ đọc: h1 lead1 02–31/12, h7 lead1 26/11–25/12, h7 lead6 bằng bàn phím 01–30/12/2022; cả ba đúng 30 ngày API, hai đường nét riêng dù giá trị trùng. Trang 1/2 bảng giữ 20 dòng; qua trang SVG không đổi hoặc gửi lại chart. Màn 390px không tràn; không request bên ngoài hay ghi nghiệp vụ.
- Kiểm nguồn sparse-date: X tỷ lệ theo số ngày lịch, ngắt cả đường dự báo và thực tế khi thiếu một ngày; actual null ngắt riêng đường thực tế, actual 0 vẫn vẽ điểm thật. Không nội suy. Bản demo browser dùng chuỗi liền ngày, sparse/0/null có bằng chứng test/đọc mã riêng.

## Review Result
- Result: APPROVED
- Findings: none

## Completion Evidence
- Đạt AC-1…AC-4 trên bản thử. Bản cuối đổi đúng ledger này so với source đã chạy Chromium; không thay API bảng, mô hình, dữ liệu, DB, main, deploy hoặc GitHub.
