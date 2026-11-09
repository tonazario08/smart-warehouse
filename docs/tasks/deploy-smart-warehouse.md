# deploy-smart-warehouse — Demo Smart Warehouse trên Render Free

## Metadata

- Status: DONE
- Phase: Triển khai demo
- Plan: docs/tasks/deploy-smart-warehouse.md#implementation-plan
- Depends on: docs/tasks/implement-warehouse-gis.md; docs/tasks/open-gis-in-google-maps.md
- Created: 2026-11-09
- Started: 2026-11-09
- Completed: 2026-11-09

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

- [x] AC-1. Cấu hình Render chỉ tạo tài nguyên miễn phí. DB dùng kết nối nội bộ, không mở kết nối công khai. Web/API dùng HTTPS và origin frontend được cấu hình rõ ràng.
- [x] AC-2. Backend dùng cấu hình production, migration và seed có thể chạy lại, secret do Render hoặc chủ tài khoản cấp, cài đặt snapshot từ bản Geofabrik/OpenStreetMap có attribution và kiểm tra định danh, hash, tuổi dữ liệu.
- [x] AC-3. Thử lạnh cục bộ trong giới hạn 512 MB RAM, 0.1 CPU bằng dữ liệu demo. Kiểm tra health, đăng nhập, tài nguyên GIS và liên kết Google Maps. Kiểm tra build, hồi quy liên quan và diff.
- [x] AC-4. Bản Render Free triển khai từ phiên bản đã review. HTTPS, refresh trang GIS, đăng nhập, tìm tuyến và URL Google Maps được kiểm chứng từ dịch vụ Render. Bàn giao URL và cách kiểm tra bằng điện thoại thật.

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
- 2026-11-09. Push đủ ba checkpoint lên [nhánh deploy](https://github.com/tonazario08/smart-warehouse/tree/codex/render-smart-warehouse-demo), HEAD `cf1ae3d`. [GIS Release](https://github.com/tonazario08/smart-warehouse/releases/tag/gis-render-demo-20261105) có đúng hai asset `manifest.json` và `graph.json`. Đã tải công khai qua HTTPS và kiểm hash, nguồn và tuổi dữ liệu bằng lệnh khởi động production trong image. [Quality](https://github.com/tonazario08/smart-warehouse/actions/runs/42574327020) đang chạy. Render Blueprint chưa được áp dụng.
- 2026-11-09. Đã mở đúng Blueprint từ nhánh deploy. Trình duyệt tích hợp yêu cầu đăng nhập; phiên Brave đã đăng nhập đang thu nhỏ. Chờ mở Blueprint trong phiên Brave để tiếp tục provision Free. Chưa tạo tài nguyên Render.
- 2026-11-09. GitHub Actions đã qua frontend và Windows guards. Backend đầy đủ tiếp tục trên GitHub; lần chạy cục bộ lặp lại đã dừng và dọn tài nguyên cô lập trong khi chờ phiên Render. Lần kiểm tra 74 ca tập trung trước commit đạt.
- 2026-11-09. Quality cho commit `cf1ae3d` hoàn tất cả bốn job. Backend với PostgreSQL và migration guard đạt 1.649 ca, 3 ca Windows được tách sang job Windows guards. Blueprint trong Brave đã nhận đúng repo và nhánh. Đã điền tên Blueprint, origin, API base, GIS Release, snapshot ID và email demo. Người dùng nhập ba mật khẩu riêng trực tiếp trên Render trước khi gửi biểu mẫu.
- 2026-11-09. Blueprint `smart-warehouse-render` đã tạo Postgres 16 và hai dịch vụ từ commit `cf1ae3d`. Frontend thật là `https://smart-warehouse-demo-8mla.onrender.com`, API giữ `https://smart-warehouse-demo-api.onrender.com`. Lần chạy API đầu dừng ở `validate environment`; ba khóa mật khẩu seed vắng trong cấu hình đã lưu. Đã chuẩn bị origin chính xác và ba trường mật khẩu trong Environment, chờ người dùng sinh/lưu giá trị rồi chạy lại deploy.
- 2026-11-09. Sau bàn giao Environment, chưa xác nhận được lần lưu vì cửa sổ Brave thu nhỏ. Thử readiness công khai trong bốn phút không nhận phản hồi HTTP. CORS, đăng nhập và GIS trên Render vẫn `NOT VERIFIED`.
- 2026-11-09. Người dùng xác nhận đã lưu ba biến mật khẩu. Dashboard hiện đủ ba khóa. Deploy `dep-dboskfmc6qcc738ko4s0` và lần sau khi đặt `PORT=10000` (`dep-dbosmc3rjlhs73c6eta0`) vẫn dừng tại bước kiểm tra cấu hình. Đã đối chiếu origin CORS, môi trường production, cổng, ba biến GIS và ba email demo đã lưu, tất cả khớp cấu hình dự kiến.
- 2026-11-09. Hai cách truyền lệnh chẩn đoán có dấu nháy không chạy được trên Render. Lệnh trực tiếp không có dấu nháy đã được kiểm tra bằng image demo cục bộ với dữ liệu giả. Deploy `dep-dbostlu417fc739agbfg` xác nhận lỗi ở bước `load_seed_settings()` do `SEED_ADMIN_PASSWORD` không đạt độ dài 12–128 ký tự. Log chỉ có dòng mã, loại lỗi và tên biến. Không in giá trị mật khẩu, JWT hoặc URL database.
- 2026-11-09. Phép kiểm tra tổng hợp `dep-dbosueui0phs73eo3hr0` xác nhận cả ba khóa mật khẩu seed đều `INVALID` theo quy tắc không rỗng và dài 12–128 ký tự. Phép kiểm tra chỉ ghi tên khóa và kết quả, không khởi động API. Đã khôi phục và xác nhận Docker Command `python /app/render-start.py`. Bàn giao thao tác nhập và lưu ba mật khẩu mới trong Render Environment cho chủ tài khoản. Chờ deploy bình thường trước khi kiểm tra API, đăng nhập và GIS qua HTTPS.
- 2026-11-09. Người dùng xác nhận đã lưu mật khẩu mới. Deploy `dep-dbot1hc9v7es738ae6gg` từ `cf1ae3d` chạy lệnh chuẩn, qua migration và báo Live. `IN_PROGRESS -> VERIFYING`. Đã mở frontend tại `/gis`, xác nhận trình duyệt chuyển sang `/login` khi chưa xác thực. Chờ người dùng đăng nhập admin để tiếp tục kiểm tra GIS.
- 2026-11-09. Chủ tài khoản đăng nhập admin trên bản demo. Đã lưu và xác nhận tọa độ kho mẫu `HCM-01`, tải lại `/gis` trong phiên xác thực, tìm kho và mở tuyến trên Google Maps. `VERIFYING -> REVIEWING` sau khi ghi bằng chứng cho bốn tiêu chí.
- 2026-11-09. `REVIEWING -> DONE`. Review độc lập xác nhận bốn tiêu chí, chạy lại kiểm tra HTTPS và CORS, đối chiếu commit triển khai, CI và hash của hai tệp GIS. Đã bỏ định danh đăng nhập admin khỏi hướng dẫn bàn giao.

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
- Static Site Render trả HTTP 200 cho đường dẫn trực tiếp `/gis`. Bundle HTTPS phục vụ có API base đúng và mẫu URL Google Maps. API deploy và luồng đăng nhập/GIS từ HTTPS còn chờ kiểm chứng.
- Render đã provision Web Service và Postgres Free cùng vùng Singapore, Static Site miễn phí và Postgres không có IP ngoài được phép. API kết nối qua cấu hình `fromDatabase` và chạy migration đến `20261105_0005`. Readiness qua HTTPS trả `200` với `status=ready`. Preflight đăng nhập trả `200` và cho phép đúng origin frontend. Origin `https://example.invalid` trả `400` và không có header cấp quyền. GIS status khi chưa đăng nhập trả `401`.
- Phiên admin hoạt động sau khi tải lại `/gis`. Giao diện xác nhận dữ liệu đường công cộng OpenStreetMap, liên kết nguồn Geofabrik và giấy phép ODbL 1.0. Lệnh khởi động production kiểm tra định danh, hash và tuổi snapshot trước khi chạy migration và seed. Phép thử restart cục bộ đã xác nhận migration và seed có thể chạy lại và giữ tọa độ đã lưu.
- Trên Render, yêu cầu `DEMO-001`, số lượng 5, điểm giao `10.78077,106.70042` trả kho `HCM-01` với 25 đơn vị tồn. GIS trả tuyến 4,088 km. Nút Google Maps mở chỉ đường lái xe từ `10.7767,106.6921` đến đúng điểm giao. Google Maps tính một tuyến riêng dài 1,3 km trên trình duyệt kiểm thử.

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

- Result: APPROVED
- Findings: Review độc lập xác nhận API readiness và trang `/gis` trả `200`, GIS yêu cầu xác thực, CORS cho phép đúng origin và từ chối origin khác. Cả bốn job CI đạt trên `cf1ae3d`. Hai tệp Release có SHA-256 khớp M10. Đã xử lý phát hiện về định danh đăng nhập trong tài liệu. Kiểm thử Google Maps đã thực hiện trên trình duyệt máy tính, còn thao tác mở ứng dụng trên điện thoại được bàn giao theo AC-4.

## Completion Evidence

- Bản demo hoạt động qua HTTPS tại [Bản đồ kho](https://smart-warehouse-demo-8mla.onrender.com/gis), deploy API `dep-dbot1hc9v7es738ae6gg` từ `cf1ae3d`.
- Trên điện thoại, mở URL demo, đăng nhập bằng tài khoản admin demo đã thiết lập trên Render, chọn `DEMO-001`, nhập số lượng 5, vĩ độ `10.78077` và kinh độ `106.70042`. Chọn **Tìm kho đủ tồn**, **Xem tuyến** từ `HCM-01`, rồi **Mở chỉ đường trong Google Maps**. Phép thử thực tế đã chạy trên trình duyệt máy tính. Mở ứng dụng Google Maps trên điện thoại vẫn chờ kiểm tra trên thiết bị.
