# deploy-smart-warehouse — Demo Smart Warehouse trên Render Free

## Metadata

- Status: IN_PROGRESS
- Phase: Triển khai demo
- Plan: docs/tasks/deploy-smart-warehouse.md#implementation-plan
- Depends on: docs/tasks/implement-warehouse-gis.md; docs/tasks/open-gis-in-google-maps.md
- Created: 2026-11-09
- Started: 2026-11-09
- Completed: not completed

## Goal

Có URL HTTPS của Smart Warehouse trên Render Free để đăng nhập trên điện thoại và mở chỉ đường Google Maps từ một kết quả GIS.

## Context

Người dùng chọn Render Free, đã đăng nhập Dashboard và xác nhận tiếp tục theo task này. M10 và liên kết Google Maps đã được kiểm chứng trong worktree hiện tại. Các thay đổi này chưa commit, nên phải rà soát và xuất bản theo checkpoint riêng trước khi Render lấy mã. Kho dữ liệu demo mới tách khỏi dữ liệu hiện có.

## In Scope

- Tạo `render.yaml`, dùng Static Site, Docker Web Service và Render Postgres Free.
- Thêm lệnh khởi động riêng cho Render tại `deploy/render/start.py`, copy vào `Dockerfile` và kiểm thử hồi quy ở `tests/test_render_start.py`.
- Dùng bản đường công cộng M10 đã xác minh. Đưa manifest và graph có ghi nguồn vào GitHub Release riêng sau khi duyệt checkpoint xuất bản. Nạp qua HTTPS và xác minh theo định danh nội dung M10 khi khởi động.
- Dùng database demo trống và lệnh migration/seed hiện có. Gán tọa độ kho và thử tuyến qua giao diện với dữ liệu demo.
- Chạy thử Docker cô lập có giới hạn tài nguyên, kiểm tra cấu hình và smoke test trên URL HTTPS Render sau khi deploy.

## Out of Scope

- Gói trả phí, sửa DNS, đổi backend API, auth, RBAC hoặc dữ liệu thật.
- Nhập DB, file `.env`, secret, token, file build hoặc dữ liệu nghiên cứu cục bộ.
- Merge, thay đổi lịch sử Git, hoặc xuất bản checkpoint chưa review và chưa được cấp quyền.

## Acceptance Criteria

- [ ] AC-1. Cấu hình Render chỉ tạo tài nguyên miễn phí. DB dùng kết nối nội bộ, không mở kết nối công khai. Web/API dùng HTTPS và origin frontend được cấu hình rõ ràng.
- [ ] AC-2. Backend dùng cấu hình production, migration và seed có thể chạy lại, secret do Render hoặc chủ tài khoản cấp, cài đặt snapshot từ bản Geofabrik/OpenStreetMap có attribution và kiểm tra định danh, hash, tuổi dữ liệu.
- [x] AC-3. Thử lạnh cục bộ trong giới hạn 512 MB RAM, 0.1 CPU bằng dữ liệu demo. Kiểm tra health, đăng nhập, tài nguyên GIS và liên kết Google Maps. Kiểm tra build, hồi quy liên quan và diff.
- [ ] AC-4. Bản Render Free triển khai từ phiên bản đã review. HTTPS, refresh trang GIS, đăng nhập, tìm tuyến và URL Google Maps được kiểm chứng từ dịch vụ Render. Bàn giao URL và cách kiểm tra bằng điện thoại thật.

## Implementation Plan

Task identifier `deploy-smart-warehouse`. Người dùng chọn demo miễn phí, chỉ định Render và xác nhận tiếp tục ngày 2026-11-09.

1. Kiểm tra các dependency đã DONE, khóa phạm vi, dùng worktree M10 hiện có và giữ riêng thay đổi deploy.
2. Kiểm thử lệnh khởi động có chuẩn hóa URL Render Postgres, chặn sai cấu hình, giới hạn tải và xác thực snapshot. Chuẩn bị Blueprint và lệnh khởi động không chứa secret.
3. Thử với container demo mới có giới hạn tài nguyên. Build frontend như Render, chạy kiểm thử liên quan, so sánh diff và rà soát checkpoint M10, Google Maps, Render theo thứ tự phụ thuộc.
4. Sau khi được phép xuất bản, dùng nhánh deploy riêng và phát hành hai file của snapshot công cộng đã xác minh, kèm giấy phép, attribution và phạm vi dữ liệu. Áp Blueprint trong workspace Render đã đăng nhập, đặt giá trị bí mật trong Dashboard, không đưa vào Git.
5. Kiểm tra endpoint health, đường dẫn SPA khi tải lại, API/auth, tuyến GIS và liên kết Google Maps từ URL Render. Ghi bằng chứng và bàn giao URL. Bản Free có cold start và database chỉ tồn tại 30 ngày.

## Verification Commands

### Focused

`python -m pytest -q tests/test_render_start.py tests/test_seed.py tests/test_gis_catalog.py`

### Regression

Build backend Docker bằng Dockerfile hiện có, thử trên DB riêng, giới hạn API theo cấu hình Render Free. Chạy `npm.cmd run test:all`, `npm.cmd run typecheck` và `npm.cmd run build` trong `client`. Chạy smoke qua HTTPS của Render sau deploy.

### Static and Diff

Kiểm tra cấu hình Blueprint theo đặc tả Render, kiểm tra Ruff cho script và test, chạy `git diff --check` và kiểm tra riêng file mới.

## Progress Log

- 2026-11-09. `READY -> IN_PROGRESS`. Xác minh hai dependency `DONE`, chốt baseline. Tìm thấy graph công cộng M10 đã review, dung lượng 12.084.338 byte; Docker Desktop đã kết nối lại.
- 2026-11-09. Đã chuẩn bị Blueprint và image. Review checkpoint phát hiện lỗi nội suy phần trăm tại Alembic, khả năng ghi đè tên database bằng `dbname` và kiểm tra chuyển hướng sau khi kết nối. Đã sửa trong lệnh khởi động riêng cho Render, bổ sung hồi quy và được reviewer duyệt lại. Task giữ `IN_PROGRESS` vì chưa deploy và chưa có smoke từ HTTPS.
- 2026-11-09. Người dùng duyệt tách commit, push nhánh `codex/render-smart-warehouse-demo` và phát hành hai tệp GIS công cộng. Đã chốt checkpoint M10 `434bfa9` và Google Maps `0b32700`. Kiểm tra lại 74 ca backend tập trung, 522 ca frontend, typecheck, build và staged diff đều đạt. Bộ backend đầy đủ đang chạy với PostgreSQL cô lập.

## Verification Evidence

### Focused

- `python -m pytest -q -p no:cacheprovider tests/test_render_start.py tests/test_seed.py tests/test_gis_catalog.py`: 66 pass, 16 skip do container xác minh không có Docker CLI để chạy các ca Compose cũ. Reviewer chạy độc lập và có cùng kết quả.

### Regression

- `docker --context desktop-linux build -t sw-render-demo-api:local .`: build backend đạt, gồm lệnh khởi động mới.
- `npm.cmd run test:all`: 432 Vitest và 90 host test đạt. Typecheck và build với API base HTTPS đạt. Vite cảnh báo bundle lớn hơn 500 kB.
- Build web trong Docker với `VITE_API_BASE_URL` HTTPS đạt. Hồi quy `tests/test_gis_api.py tests/test_gis_routing.py tests/test_auth.py`: 53 pass sau khi cài ba dependency forecasting từ `pyproject.toml` vào container test riêng. Lần thử thiếu dependency đã fail một ca dựng fixture policy.
- Smoke cục bộ đầu tiên dưới 512 MiB và 0,1 CPU đạt health sau 110,5 giây. Request GIS đầu tiên vượt timeout 90 giây của harness. Lần chạy sau đo riêng từng bước, dùng mật khẩu database có ký tự cần mã hóa và filesystem của container.
- Lần chạy với image đã sửa, DB riêng và graph đã xác minh: readiness 96,5 giây; lần đọc GIS đầu 75,5 giây; cgroup peak 196,3 MiB. Đã xác minh login, `/auth/me`, CORS chấp nhận đúng origin và từ chối origin khác, snapshot `public_osm`, tìm kho đủ tồn và tuyến thật từ hai tọa độ demo. Lần này dùng file graph có sẵn trong filesystem container. Luồng tải GitHub đã có test, chưa thử từ Release thật.
- Sau restart, Alembic/seed và readiness đạt. Docker cấp lại cổng loopback động nên probe của harness dùng cổng cũ. Probe độc lập qua loopback bên trong đúng container xác nhận đăng nhập được và chỉ có một kho `HCM-01` với tọa độ đã sửa. Assertion trên giao diện về URL Google Maps đã chạy trong bộ test frontend.

### Static and Diff

- Render JSON Schema xác nhận cấu trúc `render.yaml`. Kiểm tra chỉ có gói Free và DB dùng `ipAllowList: []`. Chưa xác minh va chạm tên tài nguyên trong workspace Render.
- Ruff trên hai file Python mới đạt. Đã đối chiếu SHA-256 của manifest với snapshot ID và SHA-256 của graph với manifest.
- `git diff --check` và kiểm tra whitespace riêng cho file mới đạt. Quét mẫu credential trên 47 file ứng viên, không khớp mẫu kiểm tra. Index Git còn trống.

## Thiết lập trên Render

Blueprint dùng nhánh được chọn khi áp dụng. Tắt tự deploy theo commit. Giữ database và Web Service cùng vùng Singapore. Kiểm tra tên thực tế của hai dịch vụ trước khi đặt biến môi trường.

- `CORS_ORIGINS` là mảng JSON gồm đúng URL HTTPS của Static Site, ví dụ `["https://smart-warehouse-demo.onrender.com"]`.
- `VITE_API_BASE_URL` là URL HTTPS của Web Service kèm `/api/v1`. Đặt lại và build lại nếu tên Render cấp có hậu tố khác.
- `GIS_RELEASE_ASSET_BASE` dùng URL GitHub Release dạng `https://github.com/<owner>/<repo>/releases/download/<tag>`. Hai asset là `manifest.json` và `graph.json`. Snapshot đã chọn là `gsv1-83bb3fea3577b8821509cb5d7cbe0fd2de608965e81485045241bcdbd044f889`.
- Release ghi nguồn Geofabrik ngày 2026-11-05, phạm vi TP.HCM, ghi công © OpenStreetMap contributors và [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/). Snapshot này hết hạn sau 21:23:02 UTC ngày 2026-12-05 theo giới hạn tuổi dữ liệu hiện tại.
- Nhập ba tài khoản demo riêng qua `SEED_*_EMAIL` và `SEED_*_PASSWORD` trong Dashboard. Dùng mật khẩu ngẫu nhiên khác nhau cho từng role. Render sinh JWT secret.
- Sau khi đăng nhập admin, đặt vị trí kho demo `HCM-01` thành vĩ độ `10.7767`, kinh độ `106.6921`. Trong Bản đồ kho chọn `DEMO-001`, số lượng 5, điểm đến vĩ độ `10.78077`, kinh độ `106.70042`. Xem tuyến rồi đối chiếu hai tọa độ trong link Google Maps.

## Review Result

- Result: PENDING
- Findings: Review checkpoint mã triển khai đã được duyệt lại sau ba sửa đổi. Review toàn task chờ verification trên Render.

## Completion Evidence
