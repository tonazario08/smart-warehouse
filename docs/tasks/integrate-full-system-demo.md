# Ghép bản demo toàn hệ thống Smart Warehouse

- Status: DONE
- Phase: Demo tích hợp đồ án
- Plan: docs/tasks/integrate-full-system-demo.md#implementation-plan
- Depends on: docs/tasks/implement-b2b-nearest-warehouse.md, docs/tasks/implement-replenishment-alerts.md, docs/tasks/implement-rag-assistant.md, docs/tasks/implement-demand-forecasting.md, docs/tasks/implement-product-cold-start.md, docs/tasks/implement-anomaly-explanations.md, docs/tasks/implement-warehouse-gis.md
- Created: 2026-11-16
- Started: 2026-11-16
- Completed: 2026-11-16

## Goal

Chạy một bản demo cục bộ có đầy đủ các màn hình đã triển khai và đủ dữ liệu để trình diễn. Tái dùng đúng kết quả dự báo mà kịch bản bổ sung tham chiếu, nạp tài liệu vào RAG và gọi mô hình thật cục bộ.

## Context

Stack cổng 58080 đang phục vụ demo kho và B2B. Bản demo mới chạy trên cổng loopback 58082 và database riêng. Cùng worktree có thay đổi chưa commit của RAG, cảnh báo bổ sung và B2B cần giữ nguyên. Dữ liệu fixture và tài khoản demo tách khỏi dữ liệu vận hành.

## In Scope

- Compose cục bộ, dữ liệu mẫu ghi rõ nguồn, và hướng dẫn chạy tại task này.
- Dự báo, cold-start, mô phỏng bổ sung, cảnh báo, bất thường/giải thích, GIS, RAG mô hình thật, luồng B2B và giao dịch kho.
- Kiểm tra bằng API thực và trình duyệt với ba vai trò trên cùng URL. Giữ nguyên dữ liệu/cấu hình của các stack cũ.

## Out of Scope

- Sửa tính năng nghiệp vụ, thêm biểu đồ SHAP, mở rộng quyền, bổ sung chức năng GIS chưa triển khai hoặc đổi hợp đồng API.
- Dùng dữ liệu kho thật, triển khai Render, stage, commit, push hoặc merge.

## Acceptance Criteria

- [x] AC-1. Stack 58082 cô lập, migration và bootstrap thành công, API sẵn sàng, frontend tải được. Stack 58080 còn hoạt động và không đổi dữ liệu.
- [x] AC-2. Dự báo và bổ sung hàng có cùng mã dự báo và binding SKU/kho/đơn vị. Mở được cold-start và cảnh báo trên dữ liệu mẫu phù hợp.
- [x] AC-3. Mở được GIS trên dữ liệu đường có nhãn, xếp hạng/tính tuyến và hiển thị một kết quả heatmap hoặc trạng thái theo kỳ có giải thích. Mở được kết quả bất thường có đóng góp SHAP.
- [x] AC-4. RAG dùng Ollama cục bộ chạy mô hình đã chấm, trả lời tiếng Việt có nguồn thật từ corpus đã duyệt. Client không được phép mở trợ lý.
- [x] AC-5. Đăng nhập được bằng admin, warehouse và client. Client tìm kho gần đủ tồn và gửi yêu cầu qua luồng hiện có. Xác nhận ít nhất một luồng nhập/xuất hoặc chuyển kho và lịch sử.
- [x] AC-6. Ghi lệnh chạy, dữ liệu, bằng chứng kiểm thử có thể truy vết và thứ tự quay video. Review diff, phạm vi và kiểm tra chức năng; không commit.

## Verification Commands

- `docker compose ... config --quiet`, `docker compose ... ps`, migration/bootstrap/import dữ liệu và HTTP readiness trên 58082, đối chiếu readiness của 58080.
- `python -m tests.prepare_cold_start_e2e`, `python -m tests.prepare_gis_e2e catalog`, `python -m tests.prepare_anomalies_e2e` để tạo fixture qua quy trình đã có, hoặc xác minh các fixture dùng lại.
- Chạy smoke xác thực và trình duyệt Chromium với API thật, ba vai trò và các kết quả nêu tại AC. Lưu bằng chứng ngoài Git, không ghi mật khẩu hoặc bearer token.
- `git diff --check` và rà soát file mới.

## Implementation Plan

Plan cho `integrate-full-system-demo`. Thêm cấu hình `docker-compose.full-demo.yml` và một script chỉ seed bảng demo sau bootstrap, nếu cần. Các catalog, log và cấu hình có thông tin xác thực nằm ngoài Git.

1. Xác minh ảnh API/web hiện tại và các catalog. Tạo catalog lạnh, bất thường và GIS bằng công cụ sẵn có. Ghép đúng catalog dự báo và bổ sung vào cùng database demo.
2. Tạo database, network và URL riêng, migrate, seed, nạp tài liệu RAG và import lượt bất thường đã xác minh. Dùng volume mô hình Ollama đã có ở chế độ chỉ đọc và địa chỉ loopback trong namespace API.
3. Kiểm tra endpoint, chạy luồng demo bằng Chromium, ghi trước/sau với stack nguồn, rồi review và bàn giao URL, dữ liệu và kịch bản quay.

## Progress Log

- 2026-11-16. READY. Người dùng chỉ định tạo và triển khai chính xác task này. Plan và phạm vi demo đã xác định.
- 2026-11-16. READY -> IN_PROGRESS. Bảy dependency đều DONE. Baseline worktree `codex/rag-assistant` tại `3f905bb` cùng các thay đổi B2B, RAG và cảnh báo đang có. Cổng 58082 chưa có tiến trình lắng nghe. Catalog dự báo `frv1-a635…` khớp tham chiếu và binding (1, 2, unit) của catalog bổ sung `rrv1-7833…`.
- 2026-11-16. Dựng stack `sw-full-demo` với hai image bất biến đang có, database riêng, catalog mount chỉ đọc. Bootstrap ban đầu từ chối miền email `example.test`; dùng `example.com` cho đúng quy tắc email. NVIDIA hook của Docker trả SIGSEGV, cấu hình Ollama chạy CPU với timeout 120 giây. Không đổi stack cũ.
- 2026-11-16. IN_PROGRESS -> VERIFYING. Migration và bootstrap của stack mới thoát 0. Nạp sáu mục RAG và import kết quả bất thường. Ollama nội bộ đọc được đúng digest mô hình đã chấm; 58082 và 58080 đều trả API readiness. Bắt đầu smoke Chromium ba vai trò.
- 2026-11-16. VERIFYING -> REVIEWING. Smoke Chromium chính và phép thử GIS đạt. Duyệt rồi xuất yêu cầu B2B đã gửi, đối chiếu heatmap phản ánh đúng hai đơn vị xuất. Kiểm tra lại dữ liệu stack 58080, ghi hướng dẫn chạy, dữ liệu, bằng chứng và kịch bản quay.
- 2026-11-16. REVIEWING -> DONE. Review độc lập xác nhận cô lập tài nguyên, hướng dẫn chạy lại đầy đủ và bằng chứng sáu AC. Không còn finding bắt buộc. Cả hai stack vẫn sẵn sàng, index trống.

## Verification Evidence

- Catalog phát sinh bằng ba lệnh fixture gốc. Cold-start chọn K=2, forecast mẫu 1 ngày 8, 7 ngày 56. GIS `gsv1-9da6fd6d99951e9d9d59ca36b31b691e0de2b2f2b19316ddfebe8c5c3bef783b` dùng đồ thị đường tổng hợp. Anomaly `arv1-0aefcb079b4a8dbfd39ddbde32000ac757e735f59fa0c8979c9c3363b8d5e3ec` đã import. Forecast và replenishment dùng catalog fixture chung nguồn, không sửa artifact.
- `docker compose --env-file <full-demo.env> -f docker-compose.full-demo.yml config --quiet` và Ruff cho script seed đạt. Readiness API tại cả hai cổng trả `ready` sau triển khai.
- `docker exec sw-full-demo-api-1 python -m app.assistant.cli /demo/assistant` báo nạp 6 mục. Lệnh gọi `/api/tags` nội bộ thấy `qwen3:4b-instruct`, digest `0edcdef34593`, trùng lượt chấm RAG.
- Chromium tại 58082 đăng nhập admin, warehouse và client, mở dự báo/cold-start, đọc cảnh báo bổ sung hàng và giải thích SHAP, gửi yêu cầu mua HTTP 201, xác nhận client bị từ chối RAG và GIS quản trị. Tạo chuyển kho 1, kiểm tra lịch sử và tuyến GIS, sau đó chuyển bù để tồn tại kho 2 quay về 2. Qwen trả lời câu về chuyển kho có một nguồn, mở đúng phiên bản tài liệu. API ghi thời gian lượt hỏi 25.629 ms trên CPU.
- Smoke trình duyệt GIS tra phiếu chuyển kho 1, thấy tuyến tham khảo và link Google Maps. Màn hình heatmap theo kỳ hiển thị trạng thái chưa phát sinh lượng xuất trước bước xuất hàng B2B.
- Admin duyệt yêu cầu `PR-93e38324dda34ae7b7b65738cdab33ec`, warehouse xuất hai đơn vị bằng giao diện, cả hai HTTP 200. Script đầu tiên dừng ở matcher không thuộc Playwright sau khi các thao tác ghi đã thành công. Lượt kiểm tra chỉ đọc sau đó thấy phiếu `fulfilled`, heatmap HCM-01 có 2 đơn vị/1 giao dịch và tồn kho 2 dùng cho cảnh báo vẫn là 2.
- Trên stack 58080, yêu cầu `PR-512d0bea45cd4743a711099069bd4a73` vẫn `pending`, tồn SKU mẫu tại kho 2 vẫn là 2, API trả `ready`. Mọi ghi dữ liệu demo khi chạy smoke chỉ ở stack 58082.
- `git diff --check` đạt với các thông báo CRLF có sẵn. Kiểm tra từng file mới bằng `git diff --no-index --check` không có lỗi khoảng trắng. Index chưa có thay đổi.

## Hướng dẫn chạy lại

Chạy PowerShell từ root worktree trên máy đã chuẩn bị demo. Catalog và cấu hình cục bộ nằm ở `%LOCALAPPDATA%/SmartWarehouse/full-demo-20261116`. File `demo-accounts.txt` chỉ chứa ba tài khoản demo. Không đưa file đó hoặc `full-demo.env` vào repo hoặc video. Container API và web dùng ID bất biến đã lưu trong file cấu hình.

```powershell
$demoRoot = Join-Path $env:LOCALAPPDATA 'SmartWarehouse/full-demo-20261116'
$demoEnv = Join-Path $demoRoot 'full-demo.env'
docker compose --env-file $demoEnv -f docker-compose.full-demo.yml config --quiet
docker compose --env-file $demoEnv -f docker-compose.full-demo.yml up -d
docker compose --env-file $demoEnv -f docker-compose.full-demo.yml ps -a
Invoke-RestMethod 'http://127.0.0.1:58082/api/v1/health/ready'
docker exec sw-full-demo-api-1 python -m app.assistant.cli /demo/assistant
$anomalyRun = (Get-Content (Join-Path $demoRoot 'anomaly.log') | Where-Object { $_ -like 'available=*' }).Split('=')[1]
docker exec sw-full-demo-api-1 python -m app.anomalies.cli import-run --run-id $anomalyRun --catalog-root /demo/anomaly --actor-id 1 --allow-fixture
```

Database giữ dữ liệu qua các lần dừng và mở lại. Lệnh nạp tài liệu có thể chạy lại. Chỉ import lượt bất thường khi cần nạp vào database mới. Giữ volume mô hình `sw-rag-ollama-data` để Ollama đọc đúng Qwen đã chuẩn bị.

| Biến | Nguồn |
| --- | --- |
| `FULL_DEMO_API_IMAGE`, `FULL_DEMO_WEB_IMAGE` | ID image cục bộ của mã đã kiểm chứng |
| `FULL_DEMO_FORECAST_ROOT`, `FULL_DEMO_REPLENISHMENT_ROOT` | Hai catalog `cli-fixture-0d9370fc0505489fb21f0bc26a5de165/catalog` trong `artifacts/forecasting` và `artifacts/replenishment` |
| `FULL_DEMO_COLD_START_ROOT` | `$demoRoot/cold/catalogs/ready` |
| `FULL_DEMO_ANOMALY_ROOT` | `$demoRoot/anomaly/catalog` |
| `FULL_DEMO_GIS_ROOT`, `FULL_DEMO_GIS_SNAPSHOT_ID` | `$demoRoot/gis` và snapshot trong `gis.log` |

Bằng chứng trình duyệt ở `browser-smoke.log`, `browser-gis.log` và `browser-heatmap-readonly.log` trong thư mục trên. Sau khi đã xuất hàng, từ `client` có thể dùng `node (Join-Path $demoRoot 'browser-heatmap-readonly.cjs')` để đối chiếu lại kết quả mà không ghi thêm nghiệp vụ. Smoke tổng hợp `browser-smoke.cjs` tạo yêu cầu và chuyển kho trong database demo, nên chỉ dùng khi cần ghi thêm dữ liệu kiểm thử.

## Kịch bản quay video

1. Đăng nhập admin tại `http://127.0.0.1:58082/login`. Mở dashboard và tồn kho, rồi mở dự báo và cold-start. Dữ liệu dự báo 2022 là fixture lịch sử và có thể hiện cảnh báo cũ.
2. Mở chi tiết bổ sung hàng `rrv1-7833aac3f3e1ed9595cb419a261cf70031fd2849253441054d9adf930fad09fe`. Tồn kho 2, ROP tham chiếu 2, EOQ 86 ở lead time 1 ngày. Nêu rõ đây là kết quả mô phỏng.
3. Mở **Bất thường** và chi tiết cảnh báo có giá trị nền và đóng góp SHAP. Mở **Trợ lý kho**, hỏi “Chuyển kho thế nào?” và bấm nguồn.
4. Đăng nhập client, vào **Tạo yêu cầu mua hàng**, chọn `DEMO-001`, số lượng 2, vĩ độ 10.778, kinh độ 106.694. Tìm kho và chọn `HCM-01`, sau đó xem lại hoặc gửi một yêu cầu demo.
5. Dùng warehouse mở **Bản đồ kho**, chọn **Tra phiếu chuyển kho**, nhập ID 1 để xem tuyến. Dùng khoảng ngày 15–17/11/2026 và SKU `DEMO-001` để xem lượng xuất đáp ứng yêu cầu.

## Review Result

- Result: APPROVED
- Findings: Thiếu hướng dẫn chạy lại và đường dẫn bằng chứng trong bản tài liệu đầu đã được bổ sung và review lại. Không còn finding bắt buộc.

## Completion Evidence

- Status: DONE ngày 2026-11-16. Đạt 6/6 tiêu chí trong phạm vi demo tích hợp.
- Demo: `http://127.0.0.1:58082/login`. Ba tài khoản, các catalog, giao dịch mẫu và mô hình Ollama cùng dùng stack này. Stack 58080 tiếp tục hoạt động.
- Verification: migration/bootstrap, readiness, smoke Chromium/API thực, kiểm tra Compose/Ruff/diff và review độc lập đạt. Dữ liệu mô hình và kho là fixture dùng để trình diễn. Các luồng gửi email thật và những tính năng ngoài phạm vi task không được xác minh trong stack này.
- Commit: not required by task scope. Chưa stage, commit, push hoặc triển khai Render.
