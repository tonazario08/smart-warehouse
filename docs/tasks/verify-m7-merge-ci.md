# verify-m7-merge-ci — Kiểm chứng CI trước khi hợp nhất M7

## Metadata

- Status: DONE
- Phase: Follow-up tích hợp sau M7
- Plan: Kế hoạch verify-m7-merge-ci và thiết kế trong tài liệu này, người dùng duyệt ngày 2026-11-04
- Depends on: docs/tasks/implement-replenishment-policy.md
- Created: 2026-11-04
- Started: 2026-11-04
- Completed: 2026-11-05
- Review Result: APPROVED

## Goal

Khắc phục sai lệch giữa GitHub Actions và bộ kiểm thử đã xác minh M2–M7 để có một bản tích hợp xanh trước khi đưa M7 vào feat/figma-ui-v2.

## Context

Nhánh đích feat/figma-ui-v2 ở 3806018 có Quality xanh trong run 41842039983. M7 ở 59c95f3 có Quality đỏ trong run 41842030040. Backend ghi 1396 test đạt, 34 thất bại, 19 lỗi thiết lập và một cảnh báo. Frontend đạt. E2E bị bỏ qua vì phụ thuộc backend. M5 và M6 cũng có CI đỏ. Bản xem trước merge f663dc89e95856e0a10375cb77fe47c63825bf2b không có xung đột, giữ cả hai lịch sử và khác mã nguồn M7 chỉ ở 10 file tài liệu. Không có file đến trùng với 23 file đang sửa hoặc chưa theo dõi trong checkout chính tại thời điểm kiểm tra.

Quality hiện cài .[dev] nên thiếu các thư viện dự báo đã pin trong .[forecasting]. Job PostgreSQL dùng danh tính cũ trên 5432 và không cung cấp TEST_MIGRATION_DATABASE_URL. Một số test điều phối Windows dùng msvcrt, đường dẫn worktree và Docker Desktop cố định. Job browser vẫn dùng 58080, trong khi các suite Forecasting, B2B và M7 cần fixture và guard theo đúng cổng. Checkout chính có hai lỗi TS2554 từ LegacyProductsPage.tsx chưa theo dõi, xác minh trước merge và nằm ngoài phạm vi.

M7 đã DONE/APPROVED trong phạm vi nghiên cứu hồi cứu đã duyệt. Tài liệu nguồn là task M7 và roadmap/spec dự án được task đó tham chiếu. Yêu cầu hiện tại là sửa CI trước khi hợp nhất. Đây là một task tích hợp riêng, với baseline chi tiết và phạm vi dưới đây chờ duyệt.

## In Scope

Workflow .github/workflows/quality.yml, test helper và cấu hình fixture cần thiết để tái tạo đủ ba job trên checkout sạch. Dùng đúng dependency pins và npm lockfile hiện tại. Trên Ubuntu, tạo hai PostgreSQL database disposable đúng danh tính và owner đã được guard chấp nhận. Cài cả .[dev,forecasting] và chạy migration, toàn bộ backend pytest và Ruff. Giữ kiểm tra phần điều phối phụ thuộc Docker Desktop/Windows trên runner Windows thích hợp, với phân loại cụ thể từng test và bằng chứng chạy. Các unit test portable tiếp tục chạy trên Linux.

Dựng browser stack từ checkout CI với DB/volume cô lập và chỉ công bố cổng web loopback. Dùng fixture tổng hợp có nhãn và được kiểm chứng, nhận ID legacy từ seeder. Chạy lại critical paths cũ, M2–M7 và các trạng thái catalog tái tạo được bằng fixture. Đường dẫn kiểm thử cần danh mục nghiên cứu thật giữ gate cục bộ với artifact đã duyệt và ghi rõ điều kiện chạy. Đối chiếu các node trong ma trận CI và local, chỉ sử dụng skip theo điều kiện fixture đã định danh. Giữ các assertion nghiệp vụ và guard cũ.

Cô lập thay đổi CI trên nhánh riêng từ 59c95f3 trong worktree M7 đã liên kết sau khi hoàn tất lượt review đang chạy. Dùng một native implementer, main review và xác minh. Kết quả Quality xanh của SHA ứng viên là điều kiện trước khi merge vào feat/figma-ui-v2. Tách cấp quyền cho commit/push ứng viên nếu cần. Chỉ cập nhật file task này cho trạng thái tích hợp.

Allowlist khóa trước khi bắt đầu. Sửa .github/workflows/quality.yml, tests/test_replenishment_verification.py, tests/prepare_replenishment_e2e.py và client/e2e/replenishment.spec.ts. Tạo tests/run_quality_ci.py, tests/test_quality_ci.py và docker-compose.quality-e2e.yml. Dùng chọn node tường minh, không cần sửa pyproject.toml. Không sửa runner M7 gốc. Windows gate gồm đúng test_runner_lock_rejects_simultaneous_owner, test_runner_lock_rejects_dangling_symlink_path và test_e2e_bind_guard_accepts_only_exact_desktop_path.

## Out of Scope

Sửa code nghiệp vụ, API, RBAC, UI, dữ liệu nghiên cứu, dependency pins, package manager hoặc file chưa theo dõi ở checkout chính. Không đưa dữ liệu thật, credential, catalog/ảnh/log sinh tự động lên remote. Không nới guard bằng regex chung, tắt job, dùng continue-on-error để che lỗi hoặc đặt mặc định báo pass cho kiểm thử thiếu dữ liệu. Không thay đổi lịch sử Git, deploy hoặc mở M8.

## Acceptance Criteria

- [x] AC-1 — Tái hiện và đối chiếu từng nhóm lỗi của run đỏ với thiết lập CI hoặc test tương ứng. Chốt allowlist và baseline theo workflow.
- [x] AC-2 — Ubuntu cài đúng dependency đã pin, xác minh đúng hai database/owner, migration và full pytest qua. Các test chỉ chạy Windows có danh sách và gate thực sự, không mất kiểm tra bảo vệ tài nguyên.
- [x] AC-3 — Frontend test:all, TypeScript và production build qua. Biến build cùng origin được cô lập với môi trường unit test.
- [x] AC-4 — Job Playwright chạy với API/DB cô lập và fixture hợp lệ. Ghi kết quả theo suite/case; tách riêng case phụ thuộc dữ liệu nghiên cứu được duyệt, có chứng cứ local trên đúng nguồn. Không dùng fixture giả làm bằng chứng nghiên cứu thật.
- [x] AC-5 — Quality xanh trên SHA ứng viên, scope diff và bảo toàn worktree chính được review độc lập. Chỉ sau đó merge local vào feat/figma-ui-v2 và xác minh tree/parents; push bản merge cần phạm vi rõ ràng.

## Verification Commands

### Focused

Chạy các module tái hiện lỗi forecast, snapshot/migration PostgreSQL và runner trên môi trường phù hợp. Kiểm tra ownership, hai tên DB và kết nối lạ trước mọi test có ghi dữ liệu. Kiểm tra pipeline fixture tổng hợp, role và Playwright collection/skip manifest. Chạy `python -m pytest -q tests/test_quality_ci.py tests/test_replenishment_verification.py` trên Windows. Dùng `python -m tests.run_quality_ci backend` để thực hiện bootstrap/guard/migration/full pytest trên GitHub Linux. Dùng `python -m tests.run_quality_ci e2e` cho browser stack riêng, bao gồm các trạng thái catalog và bảng tổng hợp Playwright.

### Regression

`python -m pytest -q` trên CI Ubuntu với hai DB disposable và forecast extras. `npm ci`, `npm run test:all`, `npm run typecheck`, `npm run build` và Playwright trên stack CI. Chạy lại nhóm Windows-only bằng runner M7 có guard. Xác minh GitHub Quality của SHA ứng viên bằng `gh run list` và `gh run view`, lưu run ID, số test và kết quả từng job.

### Static and Diff

`python -m ruff check app tests alembic`, `git diff --check`, review staged paths và secret scan giới hạn. So sánh merge tree với candidate đã kiểm chứng, kiểm tra trạng thái và hash các file chưa commit có sẵn trước/sau thao tác.

## Kế hoạch verify-m7-merge-ci

1. Xác định hợp đồng CI Ubuntu cho install, test DB, migration và guard. Tái hiện red theo nhóm và tách chính xác các test đặc thù Windows.
2. Chuẩn hóa fixture browser trên CI theo cổng guarded, cấp seed role, xuất ID M4 và chuẩn bị forecast/replenishment catalogs tổng hợp. Xác định case nghiên cứu chỉ được chứng minh local. Tạo bảng ánh xạ mỗi test với môi trường chạy và lý do.
3. Review từng diff và chạy focused, regression, static checks. Chốt allowlist dựa trên các file thật sự cần sửa trước khi bắt đầu code.
4. Khi có quyền publish ứng viên, chạy Quality đúng SHA. Nếu xanh và review đạt, tạo merge local đã được yêu cầu, bảo toàn checkout chính. Kiểm chứng kết quả bằng Git và ghi bằng chứng.

### Thiết kế đề xuất và allowlist

**PostgreSQL và Linux.** Giữ job Ubuntu hiện tại, cài .[dev,forecasting] với pins hiện hữu và đưa cả hai URL về danh tính M7 trên 127.0.0.1:18547. Khởi tạo migration DB riêng bằng tên chính xác. Xác minh driver, host, port, tên DB, user, owner và không có phiên ngoài job trước khi chạy migration hoặc pytest. Bật kiểm tra SQL có tính phá hủy tương đương guard hiện tại trên runner disposable. Tái sử dụng các test snapshot/migration và test role hiện hữu. Chỉnh những test orchestration dùng giả lập để giả lập đúng worktree kỳ vọng, không sửa đường dẫn cho phép ở production runner. Hai kiểm tra msvcrt và kiểm tra path Docker Desktop có gate Windows riêng với kết quả thực tế, cả ba vẫn là kiểm tra bắt buộc trong Quality. Linux chỉ loại đúng các node đã định danh, với một job kiểm tra tập hợp node Windows chính xác.

**Trình duyệt và fixture.** Dùng một Compose riêng cho hosted CI, build đúng Dockerfile hiện có, APP_ENV=integration, project/DB/volume riêng và web chỉ bind 127.0.0.1:58082. Dùng bộ sinh Forecasting hiện có cho các catalog tổng hợp. Tái sử dụng nguồn synthetic và CLI M7 để tạo và đối soát artifact vận hành tổng hợp, seed thực thể binding và request legacy có xác minh owner và stock digest. Chỉ mount các catalog tổng hợp ở chế độ chỉ đọc. CI có chế độ synthetic-only được chỉ định tường minh và fail closed nếu thiếu receipt hoặc profile. Browser giữ toàn bộ critical paths, 5 kịch bản M7 và 5 kịch bản forecast còn lại. Case admin đọc kết quả nghiên cứu thật chạy với artifact thật trong worktree được duyệt. Trong CI, kiểm tra admin thấy trạng thái research unavailable, warehouse nhận 403 và ID không có trong phạm vi nhận 404. Mọi test local đang dùng research ID thật vẫn phải giữ assertion cũ và chạy ở profile local. Không lấy dữ liệu nghiên cứu từ máy người dùng để đưa vào GitHub Actions.

**File cho phép dự kiến.** Sửa .github/workflows/quality.yml, pyproject.toml chỉ nếu cần khai báo pytest marker, tests/test_replenishment_verification.py và client/e2e/replenishment.spec.ts. Có thể tách job runner/fixture CI vào tests/run_quality_ci.py và tests/test_quality_ci.py, thêm docker-compose.quality-e2e.yml để không thay đổi Compose đã duyệt của M7 hay stack demo. Khi cần dùng lại cơ chế sinh fixture, chỉ bổ sung option hẹp có test ở tests/prepare_replenishment_e2e.py. Các file khác, đặc biệt app/ và lockfiles, không thuộc allowlist. Chốt lựa chọn file mới và marker cụ thể trước khi sửa code, dùng một native implementer và review độc lập.

**Gate tích hợp.** Không đánh dấu pass theo kết quả local. Chạy và đọc Quality của SHA ứng viên đã review, đối chiếu count/skip từng job và xác minh bộ source hash. Tích hợp local vào feat/figma-ui-v2 sau khi Quality xanh, bảo toàn checkout chính, kiểm tra merge parents và diff. Quyền tạo commit/push ứng viên sẽ được xác nhận khi có diff đã kiểm chứng. Không thay đổi lịch sử các nhánh đã push.

## Progress Log

### 2026-11-04 — Mở task và ghi nhận blocker

Người dùng chọn “Sửa CI trước khi merge” cho đúng task path đã đề xuất. Review đọc trực tiếp GitHub Actions, xác nhận nhánh đích xanh, các nhánh M5–M7 đỏ và kiểm tra bản merge không có xung đột. Chưa thực hiện merge hoặc sửa workflow. Bản frontend sạch đạt 390 Vitest và 90 host test sau khi tách biến môi trường build khỏi test, typecheck/build qua. Đây là bằng chứng của checkout sạch, chưa thay thế Quality trên GitHub.

### 2026-11-04 — Duyệt kế hoạch CI

Người dùng trả lời “Duyệt kế hoạch CI” sau khi xem đề xuất chính xác. Backend và frontend chạy đầy đủ trên các runner thích hợp. Browser CI dùng fixture tổng hợp, case đọc artifact nghiên cứu thật tiếp tục được kiểm chứng local. M7 dependency vẫn DONE/APPROVED. Worktree hiện tại đã là worktree liên kết. Chờ lượt backend review kết thúc để tách nhánh CI và khóa allowlist, sau đó mới bắt đầu sửa code. Không có quyền commit/push mới ở thời điểm ghi nhận.

### 2026-11-04 — READY -> IN_PROGRESS

Main xác nhận user đã duyệt thiết kế, M7 là dependency DONE/APPROVED và workflow/plan chứa đúng task ID. Native preflight xác nhận allowlist tối thiểu bảy file và phân loại ba test Windows. M7 sạch ở 59c95f3 và đã hoàn tất lượt review PostgreSQL cô lập 1449 pass, hai cảnh báo, 791.70s, log backend-pytest-34f5415d05424a348be9abfda95a2b1e.log. Bản frontend sạch 390 Vitest và 90 host pass, build/typecheck qua và build bytes khớp E2E. Không dùng kết quả local để thay thế trạng thái CI đỏ đã xác nhận. Tách nhánh codex/verify-m7-merge-ci từ đúng 59c95f3 trong worktree đã liên kết. Checkout chính vẫn ở 3806018 và giữ WIP. Native bắt đầu phần Linux/Windows CI backend, main review. Baseline SHA-256 được khóa dưới đây.

Goal: 87d4927cea4f793255187f06f17d317f0dc65b3a7500b44b2e1923e2ac3250ed
Context: 0f7d1bbf82726124faae58a44133fa0c5dabcf0ca11a48d9dbfb7fa6ff206271
In Scope: b77298827b7bc2011f1a3f7ad065a0429e0625d74bebe322dcaa6588c045e986
Out of Scope: 5b9578b793c35d385d362a41671a09c1f6ffb31aaf321cccbd89f8f89bbd501c
Acceptance Criteria: ef0e410316654212270db74db7b7e6b433ef5cfd87a41a87c55e8ec6eed59f54
Verification Commands: e51f0277095868fff02b70a290ac614afcac681c692c1e71876da7f91f9d7de5

### 2026-11-04 — Backend CI review

Native implemented the scoped backend and Windows CI jobs and tests. Main reviewed the two exact PostgreSQL identities, disposable migration bootstrap, owner/session checks, reuse of the destructive SQL guard and separation of the three exact Windows nodes. Main requested exact Linux/GitHub workspace/import guards, no Docker endpoint overrides and removal of an unnecessary timeout mock. Native regression tests reproduced four guard omissions before correction. Main independently verified focused pytest at 73 passed, two warnings, and exact Windows gate at 3 passed, zero skipped, two warnings. Ruff, workflow YAML parse and diff check passed. Linux hosted backend and actual GitHub CI remain NOT VERIFIED. Main released only the approved browser CI slice to the same native implementer. Status remains IN_PROGRESS.

### 2026-11-04 — IN_PROGRESS -> VERIFYING

Native finished the seven-path CI candidate on codex/verify-m7-merge-ci. Main reviewed the scope, source, workflow commands, exact scenario counts, isolated PostgreSQL/Docker safety and synthetic-only profile. SHA-256 fingerprint of the seven sorted normalized file hashes: fbfe331afec963f239ac823f039f182c0b014ad66d03b9d6f427b71d411a159c. No extra tracked changes, index empty, bounded secret scan and git diff --check passed.

Main independently ran focused pytest (77 passed, two warnings), the exact Windows gate (3 passed, no skips, two warnings), Ruff, strict E2E TypeScript and Playwright collection (46 tests, 8 files). The existing local synthetic and real research receipts reverified. Actual Docker Compose config passed the new shape guard without changing resources. Main ran the local retrospective admin and role checks against the known isolated M7 artifact and both passed without skips. Protected stock/outbound/transaction digests and service identities matched before and after. Evidence: e2e-quality-local-research-b9d4a518c8a649f4912f60d5f789fe50.log and the paired before/after logs.

Hosted Linux bootstrap, browser synthetic matrix and Quality on the candidate SHA remain NOT VERIFIED. The target branch stays at 3806018 while awaiting permission to commit and push the exact CI candidate branch for Actions. The user's merge request applies after Quality and independent review pass.

### 2026-11-04 — Commit và push ứng viên CI

Người dùng trả lời “Duyệt commit và push nhánh CI” cho đúng bản sửa bảy file. Main chạy lại 77 test tập trung, gate Windows 3/3 không skip, Ruff, build, typecheck và E2E TypeScript. Kiểm tra fingerprint của cả working tree và index khớp bản review. Commit 0977e24f17907c7f06bd8f28b5c912f410e055c6 được push lên origin/codex/verify-m7-merge-ci và xác nhận bằng ls-remote. Đang theo dõi GitHub Quality đúng SHA. Task vẫn VERIFYING.

### 2026-11-04 — VERIFYING -> IN_PROGRESS sau Quality thất bại

GitHub Quality run 41854439303 trên 0977e24 có frontend và Windows xanh. Linux backend xanh với 1459 pass, 3 deselect được gate Windows kiểm chứng, 1 cảnh báo. E2E valid có 29 pass, 11 skip theo profile và 6 fail, dừng trước các catalog sau. Lỗi gốc quan sát được từ browser là HTTP 503 ở status của Replenishment khi tải artifact vận hành. Publisher giữ mode 0700 của stage sau rename. API Dockerfile chạy UID/GID 10001. Kiểm tra độc lập trên WSL Ubuntu dùng đúng UID/GID 10001 tái hiện PermissionError với 0700 và đọc được cùng file tổng hợp khi cấp quyền read/traverse. Sửa trong allowlist chỉ áp dụng quyền đọc cho public synthetic catalog CI và kiểm tra quyền thực tế qua container. Không sửa app/publisher hay artifact nghiên cứu local. Chưa merge. Task lùi về IN_PROGRESS theo workflow, native thực hiện sửa và kiểm thử.

### 2026-11-04 — IN_PROGRESS -> VERIFYING cho bản sửa quyền đọc CI

Native sửa đúng ba file test/runner trong allowlist. Quyền đọc/traverse được cấp cho cây public synthetic của CI sau khi kiểm tra đầy đủ reparse và containment. Profile local và private roots giữ nguyên. Preflight mở manifest bằng UID/GID thực của API container mà không in nội dung. Main chạy 80 test tập trung và Ruff thành công. Kiểm tra WSL với thân hàm bản sửa thực tế, guard context giả lập trên fixture tạm, xác nhận UID/GID 10001 đọc được file public và thư mục private giữ 0700. Diff check và bounded secret scan đạt. Fingerprint các file sửa: fbea7becfe297d380ac513d1096bc852984185131f011eb4e08e92a5d274a729. Chưa push bản sửa mới hoặc xác minh lại GitHub Quality.

### 2026-11-05 — Push bản sửa quyền đọc CI

Người dùng duyệt commit và push đúng ba file test/runner. Main xác minh lại fingerprint của working tree và index, chạy 80 test tập trung, Ruff và git diff --check thành công. Commit 28a96195394ee86dd874522dadf063060c6edf18 đã có trên origin/codex/verify-m7-merge-ci. Quality run 41876185000 đang kiểm thử đúng SHA. Merge preview tree 1306d7b3944fd711ec5703769f8d518e0a8677e4 không xung đột và chỉ khác ứng viên CI ở 10 file tài liệu. Task vẫn VERIFYING.

### 2026-11-05 — VERIFYING -> REVIEWING

GitHub Quality 41876185000 kết thúc success trên 28a96195394ee86dd874522dadf063060c6edf18. Main đọc log của cả workflow và đối chiếu từng bước của bốn job. API GitHub còn báo trạng thái tổng hợp backend in_progress tại thời điểm đọc dù mọi bước thành công, log pytest đã chốt và workflow đã completed/success. Ubuntu chạy migration đến 20261019_0004 và pytest 1462 pass, 3 deselect đúng danh sách Windows. Windows chạy 3 pass, không skip. Frontend chạy 390 Vitest và 90 host test, typecheck và production build qua. Playwright profile valid có 35 pass, 11 skip. Năm catalog Replenishment unavailable, failed, stale, corrupt, unsupported có 2 pass và 12 skip mỗi catalog. Năm catalog Forecasting unavailable, failed-valid, corrupt, unsupported, ratio có 2 pass và 8 skip mỗi catalog. Cả 11 hàng có 0 fail và khớp ma trận runner. Hai ca research giữ bằng chứng local đã ghi ở trên.

Main đối chiếu lỗi CI gốc với bootstrap, migration, Windows gate và quyền đọc catalog, review phạm vi đúng 7 file từ 59c95f3, không có diff app, API, lockfile hoặc dữ liệu. Git diff --check đạt. Preview 1306d7b3944fd711ec5703769f8d518e0a8677e4 khác tree CI đúng 10 file tài liệu. Đối chiếu 200 đường dẫn đến với 24 file local ở checkout đích không có giao nhau. Chỉ merge local theo yêu cầu người dùng sau gate này.

### 2026-11-05 — REVIEWING -> DONE

Quality đạt và review độc lập không còn finding chặn merge. Đã merge local vào feat/figma-ui-v2 tại fca68c5aa1477d932f4efed56b08e33cc24dc50e. Kiểm tra hai parent 38060186026bbf6e4748a1a1de6ccc1bba27fec4 và 28a96195394ee86dd874522dadf063060c6edf18. Tree 1306d7b3944fd711ec5703769f8d518e0a8677e4 trùng preview đã review. Diff staged khớp chính xác patch preview và git diff --staged --check đạt. Nội dung 24 file local có trước được xác minh theo hash, index rỗng sau commit. Nhánh local ahead 19, origin/feat/figma-ui-v2 vẫn 3806018. Task evidence cập nhật local ngoài commit.

### 2026-11-05 — Rà soát trước khi công bố bản tích hợp

Người dùng yêu cầu rà soát và push đầy đủ các task đã hoàn tất. M1–M7 có hồ sơ DONE trong lịch sử Git. Xác minh phần ngoài docs/ của fca68c5 trùng với ứng viên 28a9619 đã đạt Quality. Chạy lại TypeScript và production build trên checkout chính thành công sau khi lưu riêng file LegacyProductsPage.tsx chưa được theo dõi. Chạy lại 80 test tập trung và Ruff trên worktree M7 cô lập đều đạt. Lần chạy cùng nhóm test tại checkout chính có 5 lỗi ở guard môi trường có .env local; giữ nguyên guard và cấu hình local.

Review diff và rà mẫu secret trên 19 commit sắp được đưa vào nhánh tích hợp, chỉ nhận diện fixture kiểm thử và kết nối database cô lập, không in giá trị. Phạm vi công bố gồm lịch sử đã review và checkpoint riêng cho hồ sơ này. Hai bản sửa metadata M5/handoff và các file local khác được giữ ngoài checkpoint.

## Verification Evidence

- GitHub Quality M7: https://github.com/tonazario08/smart-warehouse/actions/runs/41842030040
- GitHub Quality nhánh đích: https://github.com/tonazario08/smart-warehouse/actions/runs/41842039983
- Merge preview: f663dc89e95856e0a10375cb77fe47c63825bf2b. Không có xung đột. Mã nguồn trùng M7. Typecheck ở checkout cũ có hai lỗi TS2554 trong file local chưa theo dõi.
- CI sau sửa: https://github.com/tonazario08/smart-warehouse/actions/runs/41876185000 (success trên 28a9619). Ubuntu 1462 pass, Windows 3 pass, frontend 390 Vitest và 90 host test, typecheck/build qua.
- Playwright: 35 pass ở profile valid, 20 pass qua 10 profile âm, không có lỗi. Skip theo profile đã định danh. Hai ca nghiên cứu thật có log local riêng.

## Review Result

- Result: APPROVED
- Findings: không còn blocker trong scope. Hai lỗi TS2554 có trước thuộc LegacyProductsPage.tsx chưa theo dõi ở checkout chính và không nằm trong merge tree.

## Completion Evidence

AC-1–AC-5 đã xác minh theo Progress Log và kết quả Quality. Merge local tại fca68c5aa1477d932f4efed56b08e33cc24dc50e có đúng hai parent và tree đã kiểm tra. Bản merge được giữ local tại thời điểm đóng task.
