# implement-product-cold-start — Dự báo ban đầu cho sản phẩm mới

> Phạm vi đồ án đã được duyệt ngày 2026-11-05. Kế hoạch chi tiết đã được duyệt. Task đang IN_PROGRESS.

## Metadata

- Status: DONE
- Phase: M8
- Plan: docs/superpowers/plans/2026-10-16-project-completion.md, mục M8, và đề xuất triển khai trong task này
- Specification: docs/superpowers/specs/2026-10-16-project-completion-design.md
- Depends on: docs/tasks/build-demand-data-pipeline.md; docs/tasks/implement-demand-forecasting.md
- Created: 2026-11-05
- Started: 2026-11-05
- Completed: 2026-11-05
- Review Result: APPROVED

## Goal

Cung cấp ước tính nhu cầu ban đầu cho sản phẩm chưa có lịch sử đủ dùng bằng nhóm sản phẩm tham chiếu, kèm nguồn, thời điểm thông tin và giới hạn của kết quả.

## Context

M5 và M6 đã DONE trong phạm vi nghiệm thu đã ghi. Bản tích hợp 9d026b4 đã qua Quality 41885629210. Nguồn MEVGAL đã xác minh chỉ cung cấp một chuỗi bán hàng báo cáo ở cấp công ty. Bộ đọc M6 hiện yêu cầu một chuỗi tương ứng mỗi bundle/cấu hình. Cả hai điều kiện này khiến artifact M6 hiện có không đủ để đánh giá giữ lại SKU trên nhiều sản phẩm. Schema sản phẩm hiện có danh mục, nhà cung cấp tùy chọn, đơn vị và mức tồn tối thiểu. Chưa có trường giá, cân nặng hay lịch sử thay đổi metadata theo thời điểm. M8 cần một đầu vào metadata có nguồn và thời điểm biết được riêng, không suy ngược từ bản ghi hiện tại.

## In Scope

Xác minh và đọc tập nhiều chuỗi được ghép từ các bundle M5 đủ điều kiện bằng kiểm tra nguồn, phiên bản và ngữ nghĩa hiện có. Cố định namespace, loại mục tiêu, đơn vị, vị trí, ngày cắt và thời điểm thông tin có thể biết. Dùng tập metadata đã xác minh cho đúng khóa và thời điểm. Tách train/validation/holdout theo SKU và theo thời gian, lưu bản phân chia để chạy lại. Đánh giá theo horizon 1 và 7 ngày, theo dõi mẫu hợp lệ, bị loại và lý do.

Chạy ngoại tuyến K-means với metadata dùng được, so với baseline cùng danh mục hoặc trung vị cùng tập tham chiếu. Tạo kết quả riêng có schema phiên bản, tham số, nguồn tham chiếu, cutoff, horizon, độ tin cậy định tính và giới hạn. Dùng API chỉ đọc và màn hình tiếng Việt thuộc khu Dự báo, hiển thị trạng thái sẵn sàng, thiếu dữ liệu, lỗi hoặc quá hạn. Giữ phân quyền hiện hành của M6 cho bề mặt đọc tương ứng và kiểm tra phía backend.

## Out of Scope

Thu thập hoặc công bố dữ liệu mới khi chưa có căn cứ sử dụng được duyệt. Dự báo từ dữ liệu một SKU, từ fixture giả danh nguồn thật hoặc từ metadata chưa có bằng chứng theo thời điểm. Tự sửa danh mục, tồn kho, giao dịch hoặc đề xuất đặt hàng. Tích hợp sang M7, thay hợp đồng API M5/M6, tạo migration, đổi dependency hoặc mở milestone khác. Các trường giá và cân nặng chỉ được xem xét trong scope amendment riêng nếu có nguồn hợp lệ.

## Acceptance Criteria

- [x] AC-1 — Đầu vào xác minh được bundle, khóa SKU, snapshot metadata, ngày cắt, vị trí, mục tiêu và đơn vị. Nguồn thiếu, schema sai, metadata ngoài thời điểm hoặc tập tham chiếu không đủ trả về trạng thái có lý do.
- [x] AC-2 — SKU được giữ lại không xuất hiện trong fit preprocessing, K-means, chọn tham số hoặc ước tính tham chiếu. Sửa dữ liệu tương lai hoặc lịch sử riêng của SKU giữ lại không làm đổi kết quả trước cutoff. Feature chưa biết, thiếu danh mục, nhà cung cấp hoặc đơn vị, và cụm rỗng đều có test.
- [x] AC-3 — Cùng đầu vào và phiên bản cấu hình tạo cùng phân nhóm, tham chiếu và kết quả. Báo cáo horizon 1/7 có baseline, số mẫu bao phủ, số loại, MAE và WAPE khi mẫu số dương. Không tuyên bố cải thiện nếu so sánh không chứng minh.
- [x] AC-4 — Artifact mang phiên bản, mục tiêu, thời điểm thông tin, cutoff, tập tham chiếu và giới hạn. API chỉ đọc chiếu ra trường được phép và áp dụng RBAC như M6. Kiểm thử 401/403, định danh ngoài phạm vi, artifact hỏng và thiếu dữ liệu. Không ghi dữ liệu nghiệp vụ khi xem.
- [x] AC-5 — Browser xác minh admin/warehouse/client, các trạng thái kết quả và màn hình tiếng Việt trên desktop/mobile. Kết quả thử nghiệm luôn có nhãn nguồn; không hiển thị giá trị giả khi thiếu dữ liệu.
- [x] AC-6 — Báo cáo tách rõ bằng chứng phần mềm từ fixture và bằng chứng đánh giá trên nguồn nhiều SKU được phép dùng. Đánh giá thực tế giữ NOT VERIFIED nếu chưa có nguồn đáp ứng mục tiêu, metadata theo thời điểm và đối chiếu khóa. Phạm vi đồ án đã duyệt cho phép nghiệm thu phần mềm bằng fixture đa SKU có nhãn. Đánh giá thật giữ NOT VERIFIED và dự báo vận hành luôn chưa sẵn sàng trong M8.

## Đề xuất thiết kế và kế hoạch implement-product-cold-start

Giữ luồng offline và tách catalog đầu ra khỏi artifact M6. Thực thi bước kiểm tra nguồn trước khi chọn thiết kế cuối. Fixture nhiều SKU tự tạo, có nhãn rõ, được dùng cho oracle và E2E. Không dùng một chuỗi MEVGAL làm nhiều SKU. Nguồn thực nếu có phải kiểm tra quyền sử dụng, bằng chứng thời điểm, khóa và độ bao phủ trước khi truy cập hay đưa vào kết quả.

Dự kiến dùng danh mục và nhà cung cấp đã biết tại cutoff để mã hóa categorical. Đơn vị, mục tiêu và phạm vi vị trí là điều kiện tương thích cứng. Không dùng mức tồn tối thiểu hiện tại như đặc trưng lịch sử. Fit mã hóa và scaling nếu cần bằng các SKU train. Khóa thứ tự SKU, seed và cách xử lý tie. Chọn cấu hình trên validation, đóng băng rồi mới tính holdout. Cho phép fallback cùng danh mục, sau đó cùng phạm vi nếu vẫn đủ tham chiếu. Dưới ngưỡng thì báo không đủ dữ liệu. Ngưỡng đề xuất tối thiểu ba SKU tham chiếu, với các ca dưới, đúng và trên ngưỡng. Điểm độ tin cậy chỉ là nhãn dựa trên độ phủ và cách fallback.

Khi lấy giá trị tham chiếu, chỉ dùng các cửa sổ hoàn chỉnh có ngày và thời điểm biết được nằm trong cutoff. Dùng trung vị tổng mục tiêu theo từng horizon và cố định quy tắc ghép cửa sổ trước khi chạy holdout. So sánh dự báo K-means và baseline trên cùng cặp SKU/origin; nếu coverage khác nhau, báo riêng từng tập và tập giao nhau. Giá trị thật của SKU giữ lại chỉ được đọc ở bước chấm điểm sau khi tạo dự báo. Tách kiểu kết quả hồi cứu và vận hành, và giữ phần vận hành ở trạng thái không sẵn sàng khi chưa có binding đủ căn cứ.

Dự kiến app/cold_start/ sở hữu hợp đồng dữ liệu, kiểm tra cutoff, fit/evaluate, CLI và catalog chỉ đọc. Có thể tái sử dụng phần xác minh bundle và mẫu projection/RBAC của M5/M6. Không đổi schema artifact M6 để nhận nhiều chuỗi. Dự kiến màn hình nằm trong client/src/features/forecasting/ và chỉ thêm route/API trong phạm vi đã duyệt. Các nhóm kiểm thử dự kiến nằm ở tests/test_cold_start_*.py, frontend colocated tests và client/e2e/cold-start.spec.ts. Đây là ranh giới đề xuất, chưa phải allowlist. Thiết kế chi tiết sẽ chốt định dạng snapshot, version/ID artifact, tên endpoint, điều kiện freshness và danh sách file chính xác trước READY -> IN_PROGRESS.

Thứ tự thực hiện trong một task. Đầu tiên chốt hợp đồng đầu vào và viết test đỏ về rò rỉ, thời điểm, thiếu dữ liệu. Sau đó xây pipeline offline, kiểm thử độ tái lập và baseline trước khi mở API. Tiếp theo xác minh artifact và RBAC, rồi tích hợp giao diện với API thật trong stack kiểm thử cô lập. Cuối cùng đối chiếu từng AC, kiểm tra ma trận browser, rà diff độc lập và trình các checkpoint logic đã kiểm chứng để duyệt commit.

## Kế hoạch triển khai chi tiết implement-product-cold-start

> Thực thi một task M8 qua các checkpoint tuần tự. Một native subagent viết và chạy test. Agent chính review độc lập từng checkpoint. Chỉ commit khi đã được người dùng cho phép.

**Mục tiêu** — Chạy và công bố một benchmark cold-start đa SKU có thể chạy lại trên fixture, cùng màn hình đọc báo cáo và trạng thái vận hành trung thực.

**Kiến trúc** — Offline đọc bundle M5 đã xác minh, tạo projection cold-start riêng. FastAPI chỉ xác minh và đọc projection. React dùng auth, quyền và thành phần giao diện đang có. Không lấy thông tin bán hàng hoặc huấn luyện trong HTTP.

**Stack và spec** — Python, FastAPI, Pydantic, React, TypeScript, Playwright và các package pin sẵn. Theo spec completion mục M8 và quy tắc workflow. Không đổi dependency, migration hoặc API hiện tại.

### Hợp đồng dữ liệu và benchmark

- Dùng `ColdStartConfig`, `ColdStartDataset` và `ColdStartReport` trong `app/cold_start/schemas.py`. `load_fixture_dataset(config: ColdStartConfig, input_root: Path) -> ColdStartDataset` trong `dataset.py` nhận chỉ định mỗi SKU theo bundle path tương đối, phiên bản `ddv1`, khóa product/warehouse, đơn vị, mục tiêu và snapshot metadata có `available_at`. Xác minh qua reader M5/M6, dùng đúng ngữ nghĩa `gross_fulfilled_units`, từ chối lớp dữ liệu khác fixture trong luồng M8. Không tin ID sản phẩm hoặc category hiện tại trong DB để dựng lịch sử.
- Giới hạn đầu vào của benchmark fixture là 64 SKU, 366 ngày mỗi chuỗi và một namespace/kho/đơn vị. Ngày UTC, cutoff là cuối ngày gốc theo lịch. Một quan sát có mask hoặc chưa sẵn sàng tại cutoff không tham gia cửa sổ tham chiếu. Chấp nhận số 0 thực. Snapshot có category hoặc supplier đã biết mới đủ đặc trưng để ước tính. Giá và cân nặng vắng mặt trong schema. Đơn vị thiếu hoặc không khớp trả lỗi đầu vào; SKU không có cả category lẫn supplier trả trạng thái không đủ dữ liệu.
- Ba tập SKU rời nhau và ba khoảng ngày rời nhau. Fit chỉ dùng snapshot SKU train biết được trước cutoff train. SKU validation chỉ dùng làm đích để chọn cấu hình. Chốt cấu hình và centroid trước final holdout. Không refit với SKU validation hoặc holdout. Ngày đích của horizon 1/7 phải nằm trọn trong đúng partition. Chỉ bộ scorer đọc actual của SKU validation hoặc holdout sau khi đã tính dự báo. Không chọn lại SKU, origin hoặc tham số sau khi xem holdout.
- `evaluate_cold_start(dataset: ColdStartDataset) -> ColdStartReport` trong `benchmark.py`. One-hot category/supplier theo từ vựng train, cột unknown/missing rõ ràng, trọng số hai trường bằng nhau. K-means xác định bằng thứ tự SKU và chọn tâm đầu từ SKU đầu, tâm tiếp theo là vector xa nhất, tie theo thứ tự SKU. Lloyd tối đa 50 vòng. Thử k 1–3 khi đủ vector khác nhau; loại k có cụm rỗng hoặc không hội tụ. Chọn MAE tổng theo horizon 7 trên giao tập validation có dự báo và actual hợp lệ; dùng tập giao giữa các ứng viên, tie chọn k nhỏ hơn. Nếu không có tập giao dùng k=1 nếu hợp lệ và ghi lý do.
- Tại mỗi origin/horizon, mỗi SKU tham chiếu đóng góp tổng của đúng h ngày kết thúc vào ngày gốc, chỉ khi đủ quan sát biết được tại cutoff. Chọn trung vị của ít nhất 3 SKU, ưu tiên cụm, rồi cùng category, rồi toàn tập train tương thích. Baseline luôn dùng cùng category rồi toàn tập train. Nếu thiếu 3 SKU sau fallback, dự báo là null và ghi lý do. Báo riêng số mẫu đủ dự báo, đủ actual và đủ so sánh, cùng MAE/WAPE trên giao tập với baseline theo từng horizon. WAPE null khi tổng actual bằng 0. Độ tin cậy là nhãn định tính dựa trên nguồn tham chiếu, không phải khoảng xác suất.

### Hợp đồng artifact, API và giao diện

- `app/cold_start/catalog.py` sở hữu `publish_report(report, root) -> str` và `read_report(root, run_id) -> ColdStartReport`. Dùng canonical JSON, ID `csv1-<sha256>` từ nội dung chuẩn hóa, projection `cold-start-public/1`. Projection chứa ngày tạo/cutoff chuẩn hóa từ cấu hình, hai horizon, tóm tắt metric, dự báo mẫu, số/khóa tham chiếu tổng hợp và mã giới hạn. Không chứa raw actual từng ngày, đường dẫn máy, bí mật hoặc thông tin về nguồn ngoài fixture. Lưu atomically bằng stage cùng filesystem, kiểm tra symlink/reparse, containment, giới hạn file, schema và digest; fail closed. Root ghi nhận bản test phải là thư mục riêng do runner sở hữu. Dùng cùng input cho hai lần chạy để kiểm tra cùng ID.
- `app/cold_start/cli.py` cung cấp `python -m app.cold_start.cli evaluate --config <fixture-config> --input-root <root> --output-root <root> --allow-fixture`. Từ chối chạy fixture khi thiếu opt-in. Dữ liệu sinh trong thư mục tạm bên ngoài Git. Bản test không thể mở từ production hoặc development.
- `app/cold_start/router.py` nối vào `app/main.py`. GET `/api/v1/forecasts/cold-start/status` trả `{state, reason_code, latest_run_id, operational_state}`. GET `/api/v1/forecasts/cold-start/runs/{run_id}` trả projection của đúng ID. Trạng thái `ready`, `unavailable`, `failed`, `stale`. Status không kèm ID nếu catalog thiếu, hỏng hoặc stale. Run cũ truy cập trực tiếp vẫn có cờ stale và nhãn dữ liệu thử nghiệm. Với fixture, stale nếu thời điểm tạo ở tương lai hoặc đã quá 7 ngày theo UTC. Root chưa cấu hình trả unavailable, lỗi I/O trả 503, nội dung/schema hỏng trả 409, ID sai phạm vi hoặc fixture bị tắt trả 404. Dùng `forecast:read` cho admin/warehouse, client nhận 403, thiếu xác thực 401. Giữ `operational_state=unavailable` ở mọi môi trường. Hai setting mới `cold_start_catalog_root`, `cold_start_allow_fixture` trong `app/core/config.py`; flag chỉ được bật trong test/integration. Không mở rộng quyền nghiên cứu hay phục vụ artifact nghiên cứu trong M8.
- Thêm trang `/forecasting/cold-start` trong nhóm route được bảo vệ hiện tại. Nối từ trang Dự báo, bổ sung breadcrumb tiếng Việt và dùng lại stylesheet, token, primitives và API request helper của M6. Trang hiển thị horizon, baseline, nguồn/giới hạn, nhãn “Dữ liệu kiểm thử”, tình trạng vận hành, và phản hồi loading/lỗi/rỗng/quá hạn. Bỏ response cũ khi identity đổi. Không hiển thị kết quả stale như mới và không hiện số thay thế khi thiếu dữ liệu.

### Allowlist đề xuất và thứ tự test trước

**1. Input và benchmark** — Tạo `app/cold_start/__init__.py`, `schemas.py`, `dataset.py`, `benchmark.py` trong cùng thư mục. Tạo `tests/cold_start_helpers.py`, `tests/test_cold_start_dataset.py` và `tests/test_cold_start_benchmark.py`. Viết test đỏ trước cho bundle sai digest, trùng SKU, snapshot đến sau cutoff và mask. Benchmark phải cho dự báo 0 hợp lệ, WAPE null khi actual toàn 0, giữ nguyên dự báo khi đổi lịch sử SKU holdout/giá trị tương lai, và loại prediction khi chỉ có 2 tham chiếu. Chạy hai suite, xác minh đỏ theo tính năng còn thiếu rồi xanh sau implementation. Tái chạy hai lần với thứ tự input khác nhau để so projection chuẩn hóa.

**2. Artifact và API** — Tạo `app/cold_start/catalog.py`, `cli.py`, `router.py`, `tests/test_cold_start_catalog.py`, `tests/test_cold_start_api.py`. Sửa `app/main.py`, `app/core/config.py`. Viết test đỏ cho publish lặp cùng ID, từ chối tamper, traversal và fixture ngoài môi trường test. Test quyền gọi hai endpoint bằng auth thật trong test harness, bao gồm 401/403/404, trạng thái lỗi/hết hạn, và truy vấn đọc không cập nhật bảng nghiệp vụ. Chạy bốn suite M8 và test API/RBAC M6 trước khi giao frontend.

**3. Giao diện** — Tạo `client/src/features/forecasting/ColdStartPage.tsx`, `ColdStartPage.test.tsx`, `coldStartApi.ts`. Sửa `client/src/features/forecasting/ForecastingPage.tsx`, `client/src/app/router.tsx`, `client/src/shared/layout/Breadcrumbs.tsx`. Viết test cho quyền và các trạng thái, session cũ bị bỏ, forecast null không hiện 0, dữ liệu fixture luôn có nhãn. Chạy test trang rồi chạy `npm.cmd run test:all`, `npm.cmd run typecheck` và `npm.cmd run build`.

**4. Trình duyệt và review** — Tạo `docker-compose.cold-start-e2e.yml`, `tests/prepare_cold_start_e2e.py`, `client/playwright.cold-start.config.ts`, `client/e2e-cold-start/cold-start.spec.ts`. Dùng project/volume/network cố định riêng `sw-m8-cold-start-e2e`, DB nội bộ và chỉ bind web `127.0.0.1:58081`. Nếu cổng bận, dừng bước E2E và báo; không dừng stack đang chạy. Kiểm tra compose project, label, mount, UID 10001 đọc được public catalog và identity database trước seed/truy cập. Seed ba role bằng helper sẵn, credentials runtime. Chạy Playwright qua config riêng kế thừa guard hiện có, không thêm spec vào matrix M7. Kiểm tra browser desktop/mobile, status ready/missing/failed/stale, 401/403 và không có giá trị giả. Dùng root catalog riêng cho từng profile. Chạy focused pytest, Ruff và diff check. Full regression PostgreSQL chỉ dùng hai database disposable qua guard hiện có trên Linux CI hoặc môi trường tương đương đã xác minh danh tính; nếu chưa chạy, ghi NOT VERIFIED, không đóng task. Chạy `npm.cmd exec -- playwright test --config playwright.cold-start.config.ts` trong client với stack riêng. Review toàn bộ diff theo AC-1–6 và trình các checkpoint đã kiểm chứng để duyệt commit.

### Phạm vi nghiệm thu đã duyệt

Fixture đa SKU chứng minh luồng phần mềm và phương pháp kiểm thử holdout. Đánh giá trên nguồn thực giữ NOT VERIFIED. Forecast vận hành giữ chưa sẵn sàng. Bản chạy M8 không dùng, tải hay sao chép dữ liệu nghiên cứu thật và không thay đổi nguồn M5/M6. Tiêu chí đóng M8 gồm xác minh rõ giới hạn này ở API, giao diện và tài liệu.

## Verification Commands

### Focused

Sau khi chốt allowlist, chạy python -m pytest -q tests/test_cold_start_*.py với danh sách file tường minh tương ứng. Kiểm tra holdout, metadata ngoài cutoff, SKU khác đơn vị, danh mục/nhà cung cấp thiếu, cụm rỗng, tie và tái lập. Kiểm tra fixture mang nhãn và source thật nếu được duyệt, ghi riêng số mẫu và coverage.

### Regression

Chạy python -m pytest -q với PostgreSQL kiểm thử cô lập đã được guard chấp nhận. Chạy npm.cmd run test:all, npm.cmd run typecheck và npm.cmd run build trong client. Chạy Playwright trên stack riêng với API thật và fixture kiểm thử đã kiểm chứng, bao gồm role và desktop/mobile. Không dùng checkout demo làm môi trường thử có ghi.

### Static and Diff

Chạy python -m ruff check app tests alembic, git diff --check và rà phạm vi staged. Ghi source SHA và bằng chứng từng AC; chỉ ghi kết quả Figma nếu có node đã được duyệt và đã đối chiếu.

## Progress Log

### 2026-11-05 — Chuẩn bị task

Người dùng xác nhận đường dẫn M8 sau khi M1–M7 đã được push và xác minh Quality. Đối chiếu roadmap, spec, trạng thái M5/M6 và giới hạn đầu vào. Chỉ tạo đề xuất tài liệu. Chưa chuyển trạng thái, chưa sửa code và chưa xác nhận có dữ liệu đa SKU phù hợp.

### 2026-11-05 — Review bản đề xuất

Builder check xác nhận hai quyết định liên quan đến nguồn: mức nghiệm thu khi chưa có lịch sử đa SKU, và có cần dự báo vận hành cho SKU thật trong đợt này hay không. Phương án đề xuất là triển khai và nghiệm thu phần mềm bằng fixture nhiều SKU được gắn nhãn trong phạm vi đồ án, giữ đánh giá thực tế NOT VERIFIED và giữ dự báo vận hành ở trạng thái chưa sẵn sàng cho đến khi có nguồn cùng ánh xạ hợp lệ. Phương án này chưa được duyệt và không thay đổi AC-6. Nếu người dùng yêu cầu đánh giá thực tế hoặc vận hành ngay, cần chốt nguồn, quyền sử dụng và bằng chứng ánh xạ trước.

### 2026-11-05 — Duyệt phạm vi đồ án và chuẩn bị kế hoạch thực thi

Người dùng đồng ý nghiệm thu phần mềm bằng fixture nhiều SKU có nhãn, giữ đánh giá thực tế NOT VERIFIED và dự báo vận hành chưa sẵn sàng. Cập nhật cách diễn đạt AC-6 trước khi đóng băng baseline. Rà lại code M5/M6, pin hiện hành, RBAC và giới hạn Playwright, rồi bổ sung hợp đồng dữ liệu, thiết kế đánh giá, allowlist và các checkpoint. Chờ review kế hoạch chi tiết. Chưa tạo worktree triển khai hoặc chuyển READY -> IN_PROGRESS.

### 2026-11-05 — Duyệt kế hoạch và cổng E2E, READY -> IN_PROGRESS

Người dùng duyệt kế hoạch chi tiết. Stack M7 đang dùng 58082. Người dùng duyệt chuyển riêng E2E M8 sang 58081 sau khi bind thử thành công. Cổng này đã nằm trong guard hiện có. M7 giữ nguyên. Đã xác minh M5/M6 DONE tại baseline 9d026b4 và worktree managed m8-product-cold-start trên codex/m8-product-cold-start. Baseline worktree sạch, 91 test tập trung, Ruff, npm ci offline, typecheck và production build đạt. Native triển khai từng phần, main review. Không commit/push/merge trong lượt này khi chưa có cấp quyền riêng.

Baseline SHA-256 theo nội dung LF của từng mục đến heading cấp 2 tiếp theo.

- Goal: 937df712019d8ac2b97296dbc012434bf130349dee25ca9d269f624cfd4f73fb
- Context: 5b108f5ff5a7ae9855866dfa238b2af81dd163d7f31bd56cb493fdfc480a0d63
- In Scope: 189e620859d5c85abe6c4621f83e588c847a34c3ace5817bb3068ce023b54e4e
- Out of Scope: 482205d72fde802cc9260dd9a2f9b5d44e7ed5eaf604b8c65b268ff4ce53e185
- Acceptance Criteria: ba4b9630f1b365e1da25cb680d25b24dac1774eca83615a4b40e90d215cd6a26
- Verification Commands: f11bf9b02b4c90224cf3bcfe615157ce923c14354772d6107afe97346a95be12

### 2026-11-05 — Checkpoint 1, benchmark và dữ liệu

Native chỉ tạo đúng 7 file checkpoint 1. Red/green ghi nhận lỗi thiếu module ban đầu và lỗi do chưa kiểm tra provenance, thời gian tạo báo cáo, nguyên nhân không đủ dữ liệu. Sau một lượt sửa, main review độc lập 7 đường dẫn, chạy 20 test gồm M8 dataset/benchmark và M6 dataset. Ruff đạt. Ruling về thời điểm chốt: origin D dùng 00:00 UTC của D+1, tính cả quan sát đến đúng ranh giới này theo quy ước coverage M5. Ngày quan sát vẫn không vượt D. Test phân biệt đúng ranh giới và muộn hơn một microsecond. Đã kiểm tra thêm tách SKU, dữ liệu tương lai, mask, zero, cutoff và nguồn bundle. Chưa stage/commit. Chuyển native sang checkpoint 2.

Môi trường PostgreSQL hồi quy dùng container mới có nhãn M8, network none và không publish port, test runner dùng chung namespace cô lập. Guard xác minh hai database disposable và owner, migration đến 20261019_0004, 29 test snapshot/migration baseline đạt. Không sử dụng database M7 đang chạy. Full regression cho mã M8 vẫn chờ.

### 2026-11-05 — Checkpoint 2, catalog và API chỉ đọc

Native sửa đúng 7 file checkpoint 2. Review chính kiểm tra projection, RBAC, giới hạn fixture theo môi trường, schema và hành vi không ghi dữ liệu nghiệp vụ. Hai lượt sửa tập trung đã xử lý đồng thời và phạm vi mẫu. Catalog dùng publish atomic không ghi đè, giới hạn 128 mục dưới khóa writer, không khóa reader và không xóa khóa ngoại lai. Projection dùng đơn vị fixture đã xác minh, chọn mẫu cả horizon 1/7, giữ trạng thái không đủ kết quả và loại raw metadata. Native chạy 35 test trước correction cuối, sau đó 14 test API/catalog và Ruff đạt trên bản correction. Main chạy lại focused/Windows guard và mở full regression trên snapshot chỉ đọc. Giao native checkpoint 3 frontend.

### 2026-11-05 — Checkpoint 3, giao diện M8

Native chỉ sửa 6 file trong allowlist frontend. Main review route dưới forecast:read, link và breadcrumb, hợp đồng dữ liệu và bỏ kết quả khi phiên thay đổi. Đã yêu cầu dùng formatter chung, tiếng Việt cho mốc so sánh, hiện số cụm và cập nhật khóa phiên ở commit phase. Main chạy 18 test Vitest M6/M8 đạt. Native chạy 401 Vitest, 90 host test, TypeScript và build đều đạt. Build có cảnh báo kích thước bundle. Backend main chạy lại 21 test API/catalog và 3 guard Windows đều đạt, Ruff đạt. Full backend trên snapshot vẫn đang chạy. Giao native bước 4, chuẩn bị fixture đa SKU hai cụm và stack E2E riêng cổng 58081.

### 2026-11-05 — Checkpoint 4 và IN_PROGRESS -> VERIFYING

Native tạo đúng bốn file E2E. Fixture ngoại tuyến tạo 8 SKU, 6 SKU train thành hai cụm, xác minh K=2, horizon 1 dự báo/mốc 8/5 và horizon 7 là 56/35. Compose config và discovery 7 test đạt. Chưa tính discovery là bằng chứng browser. Main review tách project, network, volume, port 58081, mount read-only và test role, desktop/mobile, trạng thái, no-write. Mở chạy browser trên stack cô lập. Phạm vi code đã triển khai, frozen baseline giữ nguyên, chuyển VERIFYING. Không stage/commit.

Hồi quy backend lần đầu có 1475 pass, 16 skip do thiếu Docker CLI trong container, 3 test Windows tách riêng và 1 lỗi test M7 cần ghi artifact vào snapshot read-only. Main cấu hình mount tmpfs riêng cho artifact sinh tự động, giữ code chỉ đọc và chạy lại trên đúng snapshot. Nhóm seed/Compose bù bằng 47 test đạt trên Windows. Lỗi môi trường không dẫn đến sửa mã M8 hoặc M7.

### 2026-11-05 — VERIFYING -> IN_PROGRESS cho kết nối E2E

Hồi quy backend trên PostgreSQL cô lập đã đạt 1476 test. 16 ca Compose cần Docker CLI được phủ trong 47 test seed Windows đạt. 3 ca guard Windows đã chạy riêng và đạt. E2E chưa vào browser vì Docker Desktop không chuyển tiếp port loopback khi web chỉ nối vào Docker network internal. Probe dùng HTTP server tối giản trong hai network tạm xác nhận internal không truy cập được và bridge thường truy cập được qua cùng port 58081. Ruling kỹ thuật: chỉ thêm bridge ingress riêng cho service web, giữ API/DB ở internal và giữ bind loopback 58081. Sửa đúng Compose trong allowlist, không đổi app, API, firewall hoặc stack M7. Task lùi để thực hiện correction rồi kiểm thử lại.

### 2026-11-05 — IN_PROGRESS -> VERIFYING sau sửa ingress

Native chỉ đổi docker-compose.cold-start-e2e.yml. API, DB, migrate và bootstrap giữ internal; web vào cả internal và ingress riêng, ingress là gateway ưu tiên, host chỉ publish 127.0.0.1:58081. Compose config đã kiểm tra topology. Main dựng lại stack với resource mới, chỉ chạy sau preflight và không đụng M7. Typecheck riêng của cấu hình/spec Playwright đạt với --ignoreConfig để dùng các flag TypeScript tường minh. Task trở lại VERIFYING.

### 2026-11-05 — VERIFYING -> REVIEWING

Main chạy lại frontend sau checkpoint 4: 401 Vitest, 90 host, typecheck, build và TypeScript strict của spec/config E2E đạt. Backend guarded PostgreSQL 1476 pass, 16 test Compose skip trong Linux do không có Docker CLI (Windows seed/Compose 47 pass), 3 node Windows-only tách riêng đạt. Ruff đạt. Playwright Chromium trên API/web build từ worktree M8, DB disposable, kiểm tra cả UID 10001 đọc public catalog: ready 4/3, empty 3/4, failed 3/4, stale 3/4 (pass/skip theo profile), 0 fail. K=2 và hai giá trị dự báo/mốc so sánh được xác nhận. Stack E2E đã dọn theo đúng label và danh tính, giữ nguyên M7. Log browser đã che credential ở C:/Temp/sw-m8-browser-ibuin_kk. Snapshot backend chỉ đọc ở C:/Temp/sw-m8-pg-sc0uojmu, các file backend khớp hash snapshot.

Scope diff đúng 24 file, không stage. Fingerprint chuẩn hóa LF của diff source/test: 85713c57eddae7c8f5d4a1879ad30fbb6ccb42d85cf0e78491a682179f703ee8. Git diff --check đạt và kiểm tra whitespace của cả file mới đạt. Chuyển REVIEWING để đối chiếu từng AC và giới hạn phạm vi.

### 2026-11-05 — REVIEWING -> DONE

Main review độc lập 24 đường dẫn, tất cả thuộc allowlist. Đối chiếu theo bảng dưới, giữ nguyên frozen baseline ngoài checkbox nghiệm thu. Không còn finding chặn trong phạm vi đồ án đã duyệt. Kết quả từ fixture, đánh giá dữ liệu thật vẫn NOT VERIFIED và trạng thái vận hành chưa sẵn sàng. Source đã được kiểm thử nhưng chưa commit; không stage, push hoặc merge. Chờ quyền cho các checkpoint Git theo logic.

### 2026-11-05 — Checkpoint Git local M8

Người dùng duyệt commit local riêng cho benchmark, API, giao diện, E2E và hồ sơ task. Main đối chiếu lại fingerprint 24 file với bản nghiệm thu và hash snapshot PostgreSQL. Fresh pytest M8 30 pass, Vitest M6/M8 18 pass, Ruff, typecheck, build, E2E TypeScript và diff check đều đạt. Đối chiếu log Playwright đã xác minh 13 lượt pass. Bốn checkpoint mã và test được tạo tuần tự, với danh sách staged và hash từng file khớp allowlist.

- 39c660fce7ee8335e44943f76dac0531b64234a5 — feat: add cold-start data and benchmark
- 0f35b9e22c0306c68c78a144b7bf5e53babb1669 — feat: expose verified cold-start fixture reports
- d99ab4cad5088cf2a6885cd4a2497fde6a3374d3 — feat: show cold-start reports in forecasting
- 1c385c00993036792f2aa8b7903e991086b93e19 — test: verify cold-start flows in isolated browser stack

Hồ sơ chuyển nguyên đường dẫn tương đối vào worktree M8 để commit riêng trên cùng nhánh, tránh bản nháp trùng ở checkout chính. Không thay đổi status, AC hoặc giới hạn nghiệm thu.

### 2026-11-05 — Công bố M8 và hợp nhất vào nhánh tích hợp

Người dùng duyệt push riêng M8, sau đó duyệt merge và push feat/figma-ui-v2 trước khi chuẩn bị M9. Commit 6bad4b9ab999fe9145ebd5c9312775bff1939d74 đã có trên origin/codex/m8-product-cold-start. Quality 41897327496 kết thúc success trên đúng SHA với bốn job xanh. Log xác nhận 1492 backend pass, 3 deselect có 3 guard Windows pass, 401 Vitest, 90 host, typecheck/build đạt và 55 lượt browser hồi quy qua 11 profile. Suite browser riêng M8 giữ bằng chứng local 13 pass, không tính là đã chạy trong Quality.

Merge local 0e40a1fc897c4e50bf3ff8f3f7de4a922d0b295a có hai parent 9d026b4e024997e6757b3bd951c724f0a5d407eb và 6bad4b9ab999fe9145ebd5c9312775bff1939d74. Tree 47f48ec1526d24fd29e59d6565321262f94bcc1d trùng hoàn toàn commit M8 đã đạt CI. Index trước/sau đúng phạm vi và hash 22 file local không đổi. Main chạy typecheck/build trên checkout tích hợp, cả hai đạt, bundle warning giữ nguyên. Checkpoint tài liệu này ghi nhận kết quả trước push nhánh đích; trạng thái remote kiểm chứng riêng qua ls-remote và Quality theo SHA đã push.

## Verification Evidence

- Backend: 1476 pytest trên PostgreSQL disposable với SQL guard và migration tới 20261019_0004, 0 fail. Tách 3 test guard Windows, cả 3 đạt. 16 ca Compose skip trong Linux không có Docker CLI, nhóm Windows tests/test_seed.py đạt 47/47 gồm các ca Compose. Ruff đạt.
- Frontend: npm.cmd run test:all đạt 401 Vitest và 90 host. npm.cmd run typecheck và npm.cmd run build đạt. TypeScript strict riêng của config/spec Playwright đạt. Build cảnh báo bundle trên 500 kB.
- Browser: Playwright Chromium dùng stack M8 riêng và API thật trên 58081. Ready 4 pass, empty 3 pass, failed 3 pass, stale 3 pass. 15 skip theo profile, 0 fail. Kiểm tra DB trước/sau, UID 10001 đọc projection, desktop 1440 và mobile 390, và không có thay đổi stock/transactions. Log ở C:/Temp/sw-m8-browser-ibuin_kk.
- Static: git diff --check và kiểm tra whitespace file mới đạt. Đúng 24 file source/test, index rỗng. Fingerprint LF 85713c57eddae7c8f5d4a1879ad30fbb6ccb42d85cf0e78491a682179f703ee8.

## Review Result

- Result: APPROVED
- Findings: Không còn blocker trong phạm vi đồ án đã duyệt. Giới hạn dữ liệu thật và vận hành giữ riêng bên dưới.

| AC | Bằng chứng đã đối chiếu |
| --- | --- |
| AC-1 | Xác minh bundle M5 fixture, integrity/digest, unit/namespace/warehouse/availability và mask. Test metadata quá cutoff, nguồn thiếu policy và thiếu SKU tham chiếu. |
| AC-2 | Test thay dữ liệu SKU giữ lại, dữ liệu tương lai, snapshot đến muộn và actual validation ngoài cutoff. Xác minh tie, cụm rỗng/không đủ vector, unknown/missing, exact cutoff và muộn hơn một microsecond. |
| AC-3 | Test reorder tái lập, 0 hợp lệ, WAPE null nếu không có mẫu số, và denominator/coverage. Fixture 8 SKU chọn K=2 với dự báo/mốc so sánh 8/5 và 56/35 ở horizon 1/7. |
| AC-4 | API GET có fixture gate, projection, hash/canonical, quyền 401/403/404 và 409/503. Test publish đồng thời, không overwrite, stale, unavailable, invalid. Browser xác minh stock/transactions không đổi sau khi xem. |
| AC-5 | Browser admin/warehouse/client, tiếng Việt, desktop/mobile, bốn trạng thái. Không hiện báo cáo stale như hiện hành hoặc số thay thế khi thiếu dữ liệu. |
| AC-6 | Bằng chứng phần mềm từ fixture có nhãn. Đánh giá trên nguồn thật NOT VERIFIED. Dự báo vận hành chưa sẵn sàng trong mọi môi trường. |

## Completion Evidence

M8 DONE / APPROVED ngày 2026-11-05, đủ AC-1–AC-6 trong phạm vi đồ án đã duyệt. Base 9d026b4e024997e6757b3bd951c724f0a5d407eb trên worktree codex/m8-product-cold-start. Bốn commit mã và test được liệt kê trong Progress Log, kèm checkpoint riêng cho hồ sơ này. M8 đã push và merge local theo phê duyệt bổ sung trong Progress Log. Bằng chứng nghiên cứu thật vẫn NOT VERIFIED và phạm vi nghiệm thu đồ án giữ nguyên.
