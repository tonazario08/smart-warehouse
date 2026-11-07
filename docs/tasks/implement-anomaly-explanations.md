# implement-anomaly-explanations — Phát hiện và giải thích bất thường

> Phạm vi đồ án và quyền admin/warehouse phản hồi đã được duyệt ngày 2026-11-05. Kế hoạch chi tiết đã được duyệt, task đã DONE trong phạm vi đồ án.

## Metadata

- Status: DONE
- Phase: M9
- Plan: docs/superpowers/plans/2026-10-16-project-completion.md, mục M9, cùng đề xuất trong task này
- Specification: docs/superpowers/specs/2026-10-16-project-completion-design.md
- Depends on: docs/tasks/build-demand-data-pipeline.md
- Created: 2026-11-05
- Started: 2026-11-05
- Completed: 2026-11-07
- Review Result: APPROVED

## Goal

Nhận diện những bản ghi xuất hàng có đặc trưng khác thường, cung cấp lý do mô hình đánh dấu và lưu phản hồi của người kiểm tra để rà soát.

## Context

M8 đã được tích hợp vào feat/figma-ui-v2 ở 0e40a1f, checkpoint hồ sơ dc3af9b đã push. Quality ứng viên M8 41897327496 và Quality nhánh tích hợp 41992859363 đều xanh. Run 41992859363 trên đúng dc3af9b có 1492 backend pass, 3 guard Windows pass, 401 Vitest, 90 host, typecheck/build đạt và 55 lượt browser hồi quy qua 11 profile. M5 DONE theo phạm vi đã nghiệm thu. EventRecord và DailyRecord có số lượng, khóa sản phẩm/kho, thời điểm và bằng chứng dữ liệu, nhưng nguồn thực MEVGAL đã kiểm chứng là một chuỗi tổng hợp bán hàng báo cáo. Nguồn này chưa chứng minh bất thường giao dịch kho hoặc tính đúng của nhãn bất thường. Chưa có bằng chứng về nhãn nghiệp vụ được chuyên gia xác minh.

Package hiện tại chưa khai báo scikit-learn hoặc SHAP. Trước khi khóa kế hoạch cần kiểm tra phiên bản tương thích với Python, NumPy, SciPy đang pin và khả năng giải thích đúng đầu ra Isolation Forest. Không mặc định thêm hai package hoặc tự xây thuật toán thay thế khi chưa duyệt.

## In Scope

Đề xuất một pipeline ngoại tuyến nhận dữ liệu xuất hàng đã qua admission M5, tạo feature snapshot, fit Isolation Forest, chốt ngưỡng trên train/validation và xuất catalog cảnh báo có phiên bản. Khóa thứ tự, đơn vị, phép biến đổi đặc trưng và thời điểm biết được. Mô hình dùng đặc trưng số lượng bản ghi, thời điểm trong lịch và thống kê lịch sử chỉ tính từ các dòng biết được trước bản ghi đang xét. Không dùng event ID hoặc nhãn bất thường làm feature.

Giải thích theo mô hình bằng SHAP sau khi probe xác nhận phù hợp với score và pipeline đã chọn. Lưu giá trị nền, đóng góp từng feature, score được giải thích và sai số đối chiếu. Nếu explainer không chạy được hoặc không nhất quán, hiển thị chưa có giải thích. Không dựng lý do bằng văn bản tự suy đoán.

Lưu cảnh báo và phản hồi bằng persistence có schema, model/input version, khóa idempotency và kiểm tra trạng thái đồng thời. Giao diện tiếng Việt gồm danh sách, bộ lọc, chi tiết và phản hồi. Backend kiểm tra quyền, frontend dùng quyền để hiển thị. Đề xuất admin và warehouse được đọc/đánh giá trong phạm vi quyền nghiệp vụ hiện có; client bị từ chối. Phản hồi chỉ cập nhật hồ sơ cảnh báo, không sửa số lượng, stock hoặc giao dịch.

## Out of Scope

Tự sửa tồn kho, chặn giao dịch hoặc kết luận gian lận. Online retraining, external AI, tải dữ liệu thật hoặc công bố raw data khi chưa có quyền rõ ràng. Dùng dữ liệu fixture để công bố precision/recall thực tế. Mở rộng sang GIS, RAG hoặc thay auth và smart-warehouse-token. Không coi SHAP là quan hệ nhân quả. Không đổi framework hoặc package manager.

## Acceptance Criteria

- [x] AC-1 — Feature snapshot có nguồn, cutoff, thứ tự và phiên bản. Kiểm thử dữ liệu thiếu/constant, schema sai, đổi thứ tự feature, trường không biết và số không hữu hạn. Không bù 0 cho số lượng chưa biết.
- [x] AC-2 — Isolation Forest fit và chọn contamination/ngưỡng hoàn toàn ngoài tập test cuối. Có test thay nhãn và dữ liệu tương lai không ảnh hưởng score trước cutoff. Cùng input/config cho cùng kết quả trong môi trường phiên bản đã khóa.
- [x] AC-3 — Đối chiếu SHAP với đúng score đang hiển thị, pipeline và thứ tự feature, có tolerance đã duyệt. Phải có ít nhất một đường chạy Isolation Forest và SHAP hợp lệ trên fixture, kèm đối chiếu đạt cho score đang giải thích. Kiểm thử explainer thiếu, lỗi hoặc không tương thích. Nếu probe không thành công, giữ AC này chưa hoàn tất và trình lại phạm vi, không thay thuật toán hoặc dùng trạng thái unavailable để đóng phần giải thích.
- [x] AC-4 — Cảnh báo lưu input/model version và mã nguồn cảnh báo, nhập lại cùng batch không trùng. Phản hồi có actor, thời gian, version và trạng thái rõ; thử đồng thời không mất cập nhật hoặc để trạng thái dở dang.
- [x] AC-5 — API/RBAC được kiểm chứng bằng 401/403, truy cập định danh ngoài quyền, ngữ cảnh phiên cũ và kiểm tra stock/giao dịch không đổi sau chấm điểm hoặc phản hồi.
- [x] AC-6 — Browser xác minh admin/warehouse/client, luồng danh sách/chi tiết/phản hồi và empty/error/retry/unavailable trên desktop/mobile. Nội dung tiếng Việt, fixture có nhãn, không hiện giải thích giả.
- [x] AC-7 — Tách bằng chứng kỹ thuật bằng fixture và đánh giá thực tế có nhãn nghiệp vụ. Các ca chèn bất thường luôn ghi synthetic. Chưa có nguồn/nhãn hợp lệ thì precision/recall thực tế giữ NOT VERIFIED. Phạm vi đồ án đã được duyệt cho phép nghiệm thu phần mềm bằng fixture có nhãn; precision/recall trên dữ liệu thực giữ NOT VERIFIED.

## Đề xuất thiết kế và kế hoạch implement-anomaly-explanations

Đề xuất triển khai M9 theo phạm vi đồ án với fixture giao dịch đa sản phẩm/kho có nhãn, giữ hiệu quả trên dữ liệu thật NOT VERIFIED. Chuẩn bị một bộ normal/anomaly cố định để review và một bộ test cuối tách biệt. Ngưỡng chọn trên validation, không sửa lại sau khi xem kết quả test cuối. Nhãn synthetic chỉ dùng để đánh giá ngoài feature và được công bố rõ.

Đầu ra immutable của pipeline offline chứa provenance và score, còn trạng thái rà soát là dữ liệu có version trong PostgreSQL. Import batch dùng khóa duy nhất theo run và bản ghi nguồn. Cập nhật phản hồi cần điều kiện version; gửi lại cùng idempotency key cho kết quả cũ, xung đột version trả 409. Quyền ghi phản hồi cần chốt trong kế hoạch chi tiết và có kiểm thử PostgreSQL đồng thời.

Dự kiến tạo app/anomalies/ và client/src/features/anomalies/, một migration riêng và các test tập trung/API/PostgreSQL/E2E. Các đường dẫn chính xác, schema, endpoint, dependency pin, định nghĩa score, tolerance và tài nguyên test chỉ được khóa sau khi thiết kế được duyệt và probe tương thích có bằng chứng. Đây chưa phải allowlist implementation.

Checkpoint đề xuất theo thứ tự là feature/fit/scoring, attribution/catalog, persistence/API/RBAC, giao diện, rồi E2E và nghiệm thu. Mỗi checkpoint có test đỏ/xanh và review diff, giữ đúng một executable task M9. Triển khai trong worktree riêng với một native implementer và main review. Tách commit logic sau khi verification và có quyền commit; push/merge là bước cấp quyền riêng.

## Kế hoạch thực thi chi tiết implement-anomaly-explanations

> Dùng một native implementer, agent chính review từng checkpoint và toàn bộ diff. Thực thi chỉ sau khi người dùng duyệt kế hoạch này. Một task M9 duy nhất, checkpoint nội bộ không có task identifier riêng.

**Mục tiêu** — Tạo và rà soát cảnh báo bất thường có phiên bản trên dữ liệu fixture, với score và giải thích SHAP kiểm chứng được.

**Kiến trúc** — Pipeline ngoại tuyến đọc bundle M5, tạo feature, fit/scoring/explanation rồi xuất JSON đã xác minh. CLI nhập batch vào ba bảng mới trong PostgreSQL. FastAPI đọc kết quả và ghi phản hồi có version; không huấn luyện hoặc gọi SHAP trong request. React dùng UI foundation, auth và API helper hiện có.

**Stack và spec** — Python/FastAPI/SQLAlchemy/Alembic, React/TypeScript, npm, PostgreSQL và Playwright hiện tại. Theo spec completion, mục M9. Đề xuất extra Python anomalies với scikit-learn==1.9.1, shap==0.52.0, numpy==2.5.4 và scipy==1.18.1. Giữ nguyên extra forecasting và mọi dependency frontend.

### Năm điểm review cần test

Rò rỉ qua thống kê lịch sử hoặc chọn ngưỡng trên test cuối. Nhầm score của Isolation Forest với output của explainer khác. Không đủ lịch sử hoặc thay thứ tự feature mà vẫn có kết quả. Nhập lại hoặc đánh giá đồng thời làm trùng cảnh báo/mất phản hồi. Fixture bị lộ vào môi trường vận hành hoặc response phiên cũ bị hiển thị cho user mới.

### Hợp đồng nguồn và đặc trưng

Tạo app/anomalies/schemas.py, dataset.py và features.py. Các interface chính là load_anomaly_dataset(config: AnomalyConfig, input_root: Path) -> AnomalyDataset và build_feature_snapshot(dataset: AnomalyDataset) -> FeatureSnapshot.

Chỉ nhận bundle demand-data-bundle/1 đã qua xác minh M5, dataset_class=fixture và target gross_fulfilled_units; kiểm tra các EventRecord theo cùng mapping/coverage/availability. Phân tách đúng namespace, SKU, kho và đơn vị. Không chuyển MEVGAL thành lịch sử giao dịch kho. Fixture phải được opt-in tường minh. Phiên bản feature là anomaly-features/1 và thứ tự cố định gồm log_quantity, hour_fraction, weekday_fraction, log_prior_quantity_mean_7d, log_prior_event_count_7d, log_quantity_to_prior_mean.

quantity là số lượng của bản ghi hiện tại; hour_fraction là giờ UTC chia 23, weekday_fraction là thứ trong tuần chia 6. Mean/count tính từ các bản ghi cùng SKU/kho/đơn vị ở 7 ngày lịch hoàn chỉnh trước ngày giao dịch. Chỉ dùng dòng đã available_at không muộn hơn thời điểm thông tin của bản ghi đang chấm; không dùng các dòng khác trong cùng ngày. Cần coverage đầy đủ cho cả 7 ngày và đủ bằng chứng đã biết. Ngày hoàn chỉnh không có giao dịch đóng góp count 0 và quantity 0 hợp lệ. Thiếu coverage hoặc timestamp thì loại mẫu có mã lý do; không bù dữ liệu chưa biết. Tỉ lệ là quantity/(1+prior_mean). Các giá trị lượng và lịch sử biến đổi log1p, kiểm tra hữu hạn sau chuyển đổi.

Config lưu ba partition train/validation/final_holdout theo ngày UTC, các information_cutoff, created_at, seed và schema. Khoảng ngày không chồng lấn, available_at phải nằm trong cutoff của partition. Sắp xếp mẫu theo occurred_at và khóa nguồn để tái lập; ID/nhãn không vào feature. Lịch sử của dòng test chỉ dùng thông tin có trước dòng đó, mọi việc fit và chốt ngưỡng đã kết thúc trước test. Giới hạn input 10.000 event, train 2.048 mẫu, validation 512 mẫu và holdout 256 mẫu. Nếu vượt giới hạn thì từ chối, không cắt âm thầm. Tối thiểu 128 mẫu train và 100 mẫu validation hợp lệ. Tập train toàn constant hoặc tập không đủ mẫu trả unavailable.

### Mô hình, ngưỡng và giải thích

Tạo app/anomalies/scoring.py và explanations.py. Interface fit_and_score(snapshot: FeatureSnapshot) -> AnomalyRunResult. Dùng IsolationForest n_estimators=100, max_samples=min(256,n_train), contamination=auto, max_features=1.0, bootstrap=False, random_state=42 và n_jobs=1. Feature số đã chuẩn hóa theo định nghĩa ở trên, không fit scaler bằng validation/test. Anomaly score hiển thị là -model.score_samples(X), cao hơn nghĩa là bất thường hơn, không phải xác suất.

Ngưỡng cố định bằng quantile 0,99 với phương pháp higher trên score của các mẫu validation được ghi nhãn normal synthetic. Không dùng nhãn holdout để chọn quantile hoặc thay ngưỡng. Đánh dấu nếu score lớn hơn ngưỡng; tie bằng ngưỡng không đánh dấu. Nếu validation không có đủ 100 normal hợp lệ thì unavailable. Nhãn normal/anomaly synthetic chỉ dùng để chọn tập validation normal và chấm điểm, không dùng fit Isolation Forest hay feature.

SHAP dùng ExactExplainer với callable cùng score=-score_samples, Independent masker từ tối đa 16 dòng đầu train theo thứ tự chuẩn hóa, 6 feature và max_evals=64. Giữ background digest và feature order trong model metadata. Đối chiếu base_value + tổng attribution với cùng score, absolute tolerance 1e-8, tất cả số hữu hạn. Thành công mới xuất contributions. Khi package thiếu/lỗi hoặc sai additivity, explanation_state=unavailable với reason code, không xuất contributions thay thế. Pipeline phải tạo được ít nhất một explanation hợp lệ để AC-3 đạt. Giải thích nêu rõ giả định masking độc lập, nhãn synthetic và giới hạn phi nhân quả.

Báo cáo có model/config/input version, seed, package versions, source hashes, cutoffs, counts/exclusions, threshold và score_definition. Holdout có confusion matrix và precision/recall synthetic khi mẫu số hợp lệ, giá trị null khi không xác định. Không ép mô hình đạt một precision/recall được đoán trước. Tạo một bộ ví dụ normal/injected cố định cho review, tách khỏi final holdout. Không có import ML nặng vào HTTP hoặc mặc định nạp pickle từ artifact.

### Artifact và persistence

Tạo app/anomalies/catalog.py và cli.py. CLI evaluate --config --input-root --output-root --allow-fixture tạo artifact JSON riêng tại root do runner sở hữu; ID arv1-<sha256> và schema anomaly-public/1. Verify nội dung, đường dẫn, size/count, canonical JSON, score/explanation consistency và fixture class trước publish hoặc import. Publication atomic không overwrite, xử lý retry/concurrent và không để file stage làm hỏng reader. Chỉ công bố trường allowlist; không có token, đường dẫn máy hoặc raw source nguyên bản.

CLI import-run --run-id --catalog-root --allow-fixture lấy cấu hình DATABASE_URL từ môi trường. Chỉ cho phép import fixture khi Settings app_env=test/integration và anomalies_allow_fixture=true. Kiểm tra digest/projection hoàn toàn trước transaction. Batch nhập atomically và có UNIQUE run_id, UNIQUE (run_id, source_record_key). Replay cùng run/digest trả kết quả cũ; cùng identity nhưng payload khác phải lỗi. Không mở endpoint import hoặc train từ browser.

Tạo app/anomalies/models.py, repository.py và service.py, đăng ký model qua app/models/__init__.py. Migration alembic/versions/20261105_0005_anomaly_reviews.py nối parent 20261019_0004, tạo anomaly_runs, anomaly_alerts, anomaly_reviews. Không sửa bảng stock hoặc giao dịch. Run giữ metadata immutable. Alert có source key opaque, score/threshold, feature/explanation projection, review_status=new, version=1. Review event lưu actor_user_id, expected_version, decision, note, idempotency_key, request_fingerprint và thời gian; UNIQUE actor/idempotency_key. Status đánh giá gồm confirmed hoặc dismissed. Các chuyển đổi quyết định khác nhau cần version hiện hành và note 1–500 ký tự. Cùng trạng thái không có event mới, trả 409. Replay khóa cũ phải trả kết quả cũ trước khi xét version; tái dùng khóa với payload khác trả 409.

Update bằng transaction với khóa hàng/version, ghi history và tăng version cùng nhau. Hai request cùng expected_version chỉ một thay đổi được chấp nhận; request còn lại trả 409. API không ghi lại số liệu gốc sau khi nhận phản hồi. Không retrain bằng reviewer feedback trong M9.

### API, quyền và giao diện

Tạo app/anomalies/router.py, nối app/main.py. Thêm anomaly:read và anomaly:review vào backend permission map cho admin/warehouse; client bị từ chối. Bổ sung frontend helper chỉ để visibility. GET /api/v1/anomalies/status, GET /api/v1/anomalies với page/page_size và status filter allowlist, GET /api/v1/anomalies/{alert_id}, GET /api/v1/anomalies/{alert_id}/reviews, PATCH /api/v1/anomalies/{alert_id}/review với expected_version, decision, note và Idempotency-Key UUID.

Fixture chỉ hiển thị ở test/integration khi anomalies_allow_fixture bật. Mặc định status unavailable, list rỗng và ID fixture nhận 404. Backend kiểm tra quyền trước các nhánh này. Danh sách chỉ có các batch đã xác minh/nhập, không phát cảnh báo tự động từ số liệu vận hành. Dùng lỗi DomainError 401/403/404/409/422 như mẫu hiện tại, không in credentials hoặc exception chứa raw data.

Tạo trang /anomalies và /anomalies/:alertId, Sidebar “Bất thường”, breadcrumb, icon SVG cục bộ. UI reuse Button/Input/Select/Badge/DataTable/PageHeader/FeedbackMessage/Pagination và token hiện tại, tiếng Việt. Thông báo fixture và đánh giá thực tế chưa xác minh. Chi tiết hiển thị score, ngưỡng, các đóng góp với dấu +/- và tên feature tiếng Việt, trạng thái explanation unavailable, reviewer history và form phản hồi. Không gọi contribution là nguyên nhân gian lận hoặc nguyên nhân nghiệp vụ. Chờ API xác nhận trước khi đổi trạng thái. Giữ form note khi lỗi version, cho tải lại bản mới. Response cũ bị bỏ khi identity/token đổi. Nút submit khóa khi đang gửi và giữ idempotency key khi retry cùng payload.

### Allowlist theo checkpoint và kiểm thử

**Checkpoint 1, feasibility/input/scoring.** Tạo app/anomalies/{__init__,schemas,dataset,features,scoring,explanations}.py, tests/anomalies_helpers.py và tests/test_anomalies_{dataset,scoring,explanations}.py. Sửa pyproject.toml chỉ thêm extra anomalies đã pin. Test đỏ trước cho cutoff, thiếu coverage, constant, feature order và đổi dữ liệu tương lai; triển khai rồi chạy xanh. Probe thực tế sklearn/SHAP phải chạy cùng pin, có mẫu normal/injected, constant feature và additivity. Giữ toàn bộ input/output synthetic.

**Checkpoint 2, catalog/persistence.** Tạo app/anomalies/{catalog,cli,models,repository,service}.py, tests/test_anomalies_catalog.py, tests/postgres/test_anomalies_{migration,persistence,concurrency}.py và migration 0005. Sửa app/models/__init__.py. Sửa tests/postgres/test_migrations.py cho revision head và tập bảng mới, tests/postgres/test_purchase_request_migration.py chỉ kỳ vọng current head; giữ mọi guard và assertion nghiệp vụ cũ. Test đỏ rồi xanh cho atomic import, replay, xung đột payload/version, rollback và hai reviewer đồng thời. Test upgrade/downgrade với dữ liệu trước migration, bảo toàn các bảng cũ.

**Checkpoint 3, API/RBAC.** Tạo app/anomalies/router.py, tests/test_anomalies_api.py, tests/postgres/test_anomalies_api.py. Sửa app/main.py, app/core/config.py và app/auth/dependencies.py; không sửa luồng login/token. Test HTTP dùng auth thật và test DB cô lập, bao gồm 401/403/404/422, idempotent retry và conflict, fixture gate, truy cập history và digest stock/transaction không đổi.

**Checkpoint 4, frontend.** Tạo client/src/features/anomalies/{AnomaliesPage,AnomalyDetailPage}.tsx cùng hai file test, api.ts, types.ts và anomalies.css chỉ cho layout đặc thù feature. Tạo icon shared/assets/icons/anomalies.svg. Sửa app/router.tsx, shared/layout/{Sidebar,Breadcrumbs}.tsx, shared/lib/permissions.ts và permissions.test.ts. Cập nhật client/e2e/auth-client.spec.ts chỉ menu role khi thêm mục “Bất thường”, giữ toàn bộ assertion token/login/401/403. Test loading/empty/error/retry, null attribution, role, submit/version conflict và identity thay đổi; chạy toàn bộ test:all/typecheck/build.

**Checkpoint 5, E2E/hồi quy/nghiệm thu.** Tạo docker-compose.anomalies-e2e.yml, tests/prepare_anomalies_e2e.py, client/playwright.anomalies.config.ts và client/e2e-anomalies/anomalies.spec.ts. Sửa .github/workflows/quality.yml chỉ bổ sung anomalies vào extra backend đang cài để full pytest có ML dependency; giữ tất cả job và matrix đang có. Suite M9 riêng phải chạy local và ghi rõ mức coverage hosted CI.

Stack browser riêng sw-m9-anomalies-e2e, cổng 127.0.0.1:58081 (bind đã kiểm tra khi lập kế hoạch), volume/network mang nhãn M9, API/DB internal và web có ingress riêng. Nếu port/resource có sẵn chưa xác minh ownership thì dừng bước đó. Catalog public mount read-only, raw fixture nằm ngoài repo, secrets runtime không in log. DB browser sw_m9_anomalies_e2e/user cùng tên, không publish cổng DB. Hồi quy PostgreSQL dùng namespace Linux cô lập không publish port và hai DB disposable mà guard hiện hữu đã chấp nhận, kết nối loopback 18547 chỉ trong namespace đó. Giữ stack M7 đang chạy.

### Interface và regression phải khóa

catalog.py cung cấp publish_run(result: AnomalyRunResult, root: Path) -> str và verify_run(root: Path, run_id: str) -> PublicAnomalyRun. service.py cung cấp import_run(actor, verified_run: PublicAnomalyRun) -> ImportedRun và review_alert(actor, alert_id: str, key: UUID, request: AnomalyReviewRequest) -> AnomalyReviewResult. Request gồm expected_version, decision và note; response gồm alert_id, status, version, review_id và replayed. Mọi truy cập DB cùng transaction qua Session hiện có, quyền kiểm tra lại phía service.

Test khóa checkpoint 1 gồm test_future_events_do_not_change_prior_features, test_feature_order_mismatch_is_rejected, test_missing_coverage_is_not_zero, test_constant_training_data_is_unavailable, test_final_holdout_cannot_change_threshold và test_shap_reconstructs_displayed_score. Checkpoint 2 gồm test_import_is_atomic_and_replay_safe, test_publication_is_atomic_under_competing_writers và test_only_one_reviewer_wins_expected_version. Checkpoint 3 gồm test_client_cannot_read_or_review, test_fixture_is_hidden_outside_test_environment và test_review_does_not_change_stock_or_transactions. Checkpoint 4 gồm kiểm tra đổi identity trong hai giai đoạn tải, retry giữ đúng payload/key và conflict giữ note. E2E cần kiểm tra explanation thật có additivity, phản hồi được lưu/replay/conflict qua API thật, ba role và desktop/mobile; kết quả discovery không được tính là browser pass.

### Bước review và giới hạn thực thi

Mỗi checkpoint viết test đỏ, xác nhận lỗi theo yêu cầu thiếu, triển khai tối thiểu, chạy test xanh và review phạm vi trước checkpoint tiếp theo. Không sửa file ngoài allowlist nếu chưa có duyệt bổ sung. Các milestone cũ chỉ điều chỉnh kỳ vọng migration/menu rõ ở trên. Chưa có quyền commit/push/merge M9 trong bước duyệt thiết kế.

Khi mọi requirement có implementation, chuyển VERIFYING và chạy focused, full pytest trên PostgreSQL, 3 Windows guard, frontend test:all/typecheck/build, Ruff, diff và Playwright M9. Không dùng build để suy ra browser hoặc hiệu quả mô hình. Đối chiếu 7 AC trước REVIEWING và chỉ DONE khi review độc lập đạt. Giữ hiệu quả trên nguồn thực NOT VERIFIED theo phạm vi đồ án đã duyệt.

### Nguồn kỹ thuật đã kiểm tra

Điểm Isolation Forest theo tài liệu sklearn, model callable và additivity theo tài liệu SHAP. Tính khả thi được kiểm tra bằng probe riêng, không suy ra từ tài liệu.

- https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html
- https://shap.readthedocs.io/en/stable/generated/shap.ExactExplainer.html
- https://shap.readthedocs.io/en/latest/example_notebooks/api_examples/explainers/Exact.html
- https://pypi.org/project/scikit-learn/1.9.1/
- https://pypi.org/project/shap/0.52.0/

## Verification Commands

### Focused

Chốt danh sách test_anomalies_*.py trước khi bắt đầu. Kiểm tra cutoff, thứ tự feature, thiếu/constant, ngưỡng ngoài test, score/attribution và nguồn fixture. Chạy probe package/pipeline trong môi trường cô lập, ghi phiên bản và kết quả thay vì kết luận tương thích từ tên package.

### Regression

Chạy pytest với PostgreSQL disposable đã xác minh danh tính, gồm migration upgrade/downgrade, idempotency và concurrency. Chạy npm.cmd run test:all, npm.cmd run typecheck, npm.cmd run build và Playwright trên stack riêng. Bắt buộc chốt port/database/owner/volume rõ ràng trước khi tạo tài nguyên. Không dùng stack đang demo để thử nghiệm có ghi.

### Static and Diff

Ruff, git diff --check, kiểm tra từng staged path và scan secret không in giá trị. Đối chiếu từng AC với test/code/browser và ghi NOT VERIFIED khi chưa có bằng chứng. Chỉ tuyên bố đã đối chiếu Figma khi có node nguồn được duyệt.

## Progress Log

### 2026-11-05 — Chuẩn bị task M9

Người dùng duyệt tích hợp M8 và chuẩn bị task M9. Đọc roadmap, spec, dependency M5 và cấu trúc hiện tại. Tạo bản đề xuất duy nhất tại đường dẫn roadmap đã chỉ định. Chưa chuyển READY -> IN_PROGRESS hoặc sửa mã nguồn M9. Đề xuất phạm vi fixture và phần quyền phản hồi chưa được người dùng duyệt.

### 2026-11-05 — Builder check cho bản đề xuất

Reviewer đọc task và spec chỉ ra hai quyết định cần người dùng duyệt là nghiệm thu đồ án bằng fixture và quyền admin/warehouse ghi phản hồi. Làm rõ AC-3 theo mục tiêu Isolation Forest/SHAP của roadmap: ít nhất một đường chạy giải thích hợp lệ phải được xác minh. Trạng thái explainer unavailable cần được xử lý đúng nhưng không thay thế bằng chứng giải thích thành công. Các lựa chọn package, score và tolerance thuộc bước lập kế hoạch chi tiết.

### 2026-11-05 — Duyệt phạm vi và chuẩn bị kế hoạch chi tiết

Người dùng trả lời “duyet” cho phạm vi nghiệm thu bằng fixture có nhãn, giữ hiệu quả thực tế NOT VERIFIED và cho admin/warehouse đọc, ghi phản hồi. AC-7 được làm rõ trước khi đóng băng baseline. Task vẫn READY, Started giữ not started. Main chuẩn bị kế hoạch và giao native probe tương thích trong môi trường tạm bên ngoài repository, không sửa dependency hay code dự án. Kế hoạch chi tiết cần chốt score/SHAP, schema, migration, allowlist và test trước triển khai.

### 2026-11-05 — Probe tương thích và hoàn tất kế hoạch đề xuất

Native chạy probe ngoài repository bằng scikit-learn 1.9.1, SHAP 0.52.0, NumPy 2.5.4, SciPy 1.18.1, XGBoost 3.4.1; Windows giữ tzdata 2026.5. Linux amd64 Python 3.12.16 và Windows x86-64 Python 3.14.2 đều import và pip check đạt. ExactExplainer dùng 6 feature, 16 background train và max_evals=64, giải thích score=-score_samples. Residual lớn nhất trên ba mẫu synthetic là 3.3306690738754696e-16 ở Linux và 2.220446049250313e-16 ở Windows. Hai lần fit/explainer riêng cho kết quả bitwise giống trong từng môi trường. Đây là feasibility trên fixture, không phải kiểm thử hồi quy hoặc hiệu quả nghiệp vụ.

Main đọc output và xác minh hash. Evidence ở C:/Users/TQUOCTOAN/AppData/Local/Temp/m9-feasibility-aadb5d4349804ed3b8807b5ea12a081f. probe-six.py SHA256 fe7f3c5d306fa397f1e7026092a0abf43c827c15fa8d330a3b5e313a317f340b; six.stdout a4c4b903fa94b516457b3dc4a7e9a9da38fdd140e3424f0dfe292c8b03f6e1f0; windows-six.stdout f533c42d28c7e5584b8a9e9e7ed7e24cb867c71f0f35660a603fed57ee5788c8. Image probe Linux dẫn xuất 110faeebfa73a991a1647bd7dd9a15bee46e00787d88b8efee3a387a5becbbba. Không sửa dependency hoặc code dự án, môi trường ML hiện hữu giữ nguyên.

Main tự review spec coverage, các interface và test, migration/menu compatibility, isolation và giới hạn. Kế hoạch chi tiết chờ người dùng review trước thực thi; READY và not started giữ nguyên.

### 2026-11-05 — Duyệt kế hoạch và READY -> IN_PROGRESS

Người dùng duyệt kế hoạch chi tiết bằng “ok” sau khi xác nhận bước tiếp theo. Xác minh dependency M5 DONE trên commit baseline dc3af9b77f6a979fe66dbb19d60c5b186c07240b; roadmap/spec và task ID khớp. Tạo worktree managed C:/Users/TQUOCTOAN/.codex/worktrees/m9-anomaly-explanations/smart-warehouse trên codex/m9-anomaly-explanations. Worktree code sạch, npm ci offline/typecheck/build đạt. Baseline backend dùng môi trường M6 read-only: lượt đầu 90 pass và 1 test timeout runner thất bại (exit 125 thay 124). Probe process termination và chạy lại đúng test đạt, sau đó chạy lại toàn nhóm 91 pass và Ruff đạt. Chưa sửa test runner; ghi nhận biểu hiện timing Windows có trước, không coi là regression M9.

Virtualenv M9 được tạo mới để cài đúng extra/pin đã duyệt. Không sửa môi trường ML cũ. Scope là fixture đồ án, admin/warehouse được phản hồi, hiệu quả thực tế giữ NOT VERIFIED. Chưa có quyền commit/push/merge M9. Native thực hiện checkpoint 1 và main review trước khi mở checkpoint tiếp theo.

Baseline SHA-256 dùng nội dung LF của mỗi mục đến heading cấp 2 kế tiếp.

- Goal: 37e1c27ae5d9bfdfa44064c8f315582a957d6949ea6727ba7e1349342b3701f2
- Context: f5d31b02f02c62ab6fe4ea07075bedc29cffe7cf5d7b02b91609f3a7f4d4fab5
- In Scope: 5b3d3a8b1a70dda9f62f5865e185ee282b4c15e42aceef4811b9031c1e88c668
- Out of Scope: d01eb78ba829d6acb9be86a3247f7bad95aaee5ac92a565963c1b6f1730bce89
- Acceptance Criteria: 8d38ff25786478dd97cd32caf0e5fbe9cd1e2c58952f8660a759c34766a972b6
- Verification Commands: c62b147af5a35856077c1179452b20feea129c637481257d9e7af293f65667d1

### 2026-11-05 — Môi trường M9 sẵn sàng và review checkpoint 1 đang chạy

Virtualenv riêng M9 cài thành công baseline dev/forecasting cùng scikit-learn 1.9.1, SHAP 0.52.0, NumPy 2.5.4, SciPy 1.18.1 và XGBoost 3.4.1; pip check không lỗi. npm test:all baseline đạt 401 Vitest và 90 host. Main giữ metadata nguồn M5/M6 và môi trường ML cũ.

Native triển khai checkpoint 1 theo allowlist. Ruling: nhãn synthetic nằm trong config với khóa composite namespace/product/warehouse/unit/event_id, tách khỏi feature, để tránh nhầm event ID cục bộ giữa kho. UTC-only theo kế hoạch được giữ rõ. Review ban đầu phát hiện lọc current event phải theo customer_fulfillment; yêu cầu test bundle M5 thật để loại inbound/transfer và các kind ngoài target. Native đã xác minh luồng bundle M5 đến SHAP và đang hoàn thiện kiểm tra snapshot/temporal và test hồi quy. Chưa đủ evidence checkpoint 1, task giữ IN_PROGRESS.

### 2026-11-05 — Review checkpoint 1 và chuyển checkpoint 2

Main review đúng 11 đường dẫn checkpoint 1, bao gồm pyproject.toml chỉ thêm extra anomalies. Chạy pytest các suite M9 dataset/scoring/explanations cùng M5 semantics: 59 pass, 2 cảnh báo deprecation; Ruff toàn app/tests/alembic đạt. Đã đối chiếu lọc target, ordering composite, information time, snapshot chống gán holdout thành train, fixture M5 đa SKU/kho cùng timestamp, model/SHAP thật và dữ liệu thiếu. Các test mới sau sửa sort ghi là chạy xanh trên hành vi đã đúng, không bịa red evidence.

Native được giao checkpoint 2 gồm catalog/persistence/migration. Ruling về thứ tự: thêm flag anomalies_allow_fixture và gate môi trường trong app/core/config.py sớm ở checkpoint 2 để CLI import fixture có thể được kiểm thử đúng. File đã thuộc tổng allowlist của checkpoint 3, không thêm scope hoặc thay auth. Các file API còn lại giữ ở checkpoint 3. Model estimator là đối tượng private trong lần chạy offline, projection phải xác minh và tách trường trước khi lưu/HTTP. Chưa stage/commit.

### 2026-11-05 — Checkpoint 2 catalog/persistence đã qua kiểm thử tập trung

Main review catalog canonical/hash, score và threshold đối chiếu model, metrics/count/partition, provenance an toàn, atomic publication, import transaction, khóa actor/idempotency/alert, replay trước version và migration 0005. CLI import-run yêu cầu --actor-id của user active thực tế, service xác minh admin/warehouse; tham số này ghi nhận actor cho operator đã có quyền truy cập database, không thay authentication HTTP. Đây là làm rõ interface trong scope đã duyệt.

Windows catalog ban đầu đạt 8 test; PostgreSQL lượt đầu migration đạt nhưng 7 fixture setup lỗi vì Path.home() không xác định ở worker Linux không có home. Native thêm test đỏ tái hiện, sửa catalog xử lý trường hợp này và giữ canonical/symlink/root/workspace guards, không sửa HOME. Catalog mới đạt 9 test. Main chạy lại PostgreSQL trong network namespace riêng, không publish database: 8 pass cho migration, atomic/replay/rollback và concurrency. Log C:/Temp/sw-m9-pg-4_dbvsd4/pytest.log; snapshot có manifest hash. Ruff toàn app/tests/alembic đạt trước sửa portability, Ruff hai file sửa đạt sau đó. Checkpoint 2 được chấp nhận trong phạm vi tập trung, full regression còn chờ. Native tiếp tục checkpoint 3 API/RBAC, chưa commit/push/merge.

### 2026-11-06 — Tiếp tục checkpoint 3, bằng chứng API và amendment đang chờ

Tiếp tục đúng worktree M9, HEAD dc3af9b không đổi, bảo toàn toàn bộ thay đổi có sẵn sau lần native gián đoạn usage limit. Native hoàn thiện router và test checkpoint 3. Main chạy unit API 3 pass, sau đó PostgreSQL + unit API 6 pass trên snapshot hash khớp ba file hiện hành, log C:/Temp/sw-m9-pg-uq9w916e/pytest.log. Test dùng JWT và user thực trong database, xác minh role/activity đổi với token cũ, fixture gate, client bị chặn, replay/conflict và dữ liệu stock/transaction không rỗng không thay đổi sau review. Đây là verification API tập trung, chưa phải browser verification. Native xác minh import router không nạp numpy/sklearn/shap.

Main chạy lại nhóm dataset/scoring/explanations/catalog 37 pass trên Windows, Ruff toàn app/tests/alembic đạt và git diff --check không lỗi. Bằng chứng bổ sung từ phiên trước: 14 legacy migration test pass (C:/Temp/sw-m9-pg-z_gotdlx/pytest.log), 3 Windows guard pass và 47 seed test pass. Docker engine đã khởi động lại qua đường dẫn cài đặt per-user, không reset hoặc xóa dữ liệu.

Main đọc log hồi quy ma trận RBAC từ C:/Temp/sw-m9-pg-yj4tdl3v/pytest.log: 120 pass, một assertion exact mapping thất bại vì thiếu hai expectation ANOMALY_READ và ANOMALY_REVIEW đã được duyệt cho admin/warehouse. File tests/postgres/test_rbac_matrix.py nằm ngoài allowlist checkpoint 3, chưa sửa. Cần người dùng duyệt scope amendment chỉ thêm hai entry kỳ vọng, giữ toàn bộ assertion và quyền cũ. Checkpoint 3 chưa được đóng vì hồi quy này còn đỏ. Task giữ IN_PROGRESS, chưa triển khai checkpoint 4/5 hoặc commit/push/merge.

### 2026-11-06 — Scope amendment được duyệt cho expectation RBAC

Người dùng trả lời “ok” cho đề nghị bổ sung tests/postgres/test_rbac_matrix.py vào allowlist M9. Chỉ thêm hai entry ANOMALY_READ và ANOMALY_REVIEW với tập quyền admin/warehouse trong assertion exact mapping hiện có. Lý do: hồi quy ghi nhận một expectation thiếu sau khi thêm quyền M9 đã được duyệt. Giữ nguyên mọi entry, assertion và kiểm tra nghiệp vụ cũ. Approver: người dùng. Không thay baseline Goal/AC hoặc quyền ứng dụng. Native sửa, main review diff và chạy lại hồi quy trước checkpoint 4. Chưa cấp quyền commit/push/merge.

### 2026-11-06 — Hồi quy RBAC xanh và chuyển checkpoint 4

Native bổ sung đúng hai dòng expectation quyền theo amendment đã duyệt. Main review git diff xác nhận không thay entry/assertion cũ. PostgreSQL chạy test_rbac_matrix cùng API/persistence/concurrency M9 đạt 131 pass, một cảnh báo thư viện, exit 0. Log C:/Temp/sw-m9-pg-vgkgymv_/pytest.log. Chấp nhận checkpoint 3 trong phạm vi tập trung. Native tiếp tục frontend checkpoint 4 theo allowlist, main chạy full backend trên snapshot riêng song song. Task giữ IN_PROGRESS, toàn bộ AC vẫn chờ đối chiếu cuối, chưa commit/push/merge.

### 2026-11-06 — Full regression phát hiện môi trường và finding kiến trúc

Full backend lượt đầu dùng probe image có UID 10001 nhưng không có entry passwd, khác Dockerfile production vốn tạo appuser. Kết quả không đạt: 209 failed, 1311 passed, 16 skipped, 3 deselected và 7 errors, log C:/Temp/sw-m9-pg-cdu4u8jo/pytest.log. Main không coi đây là PASS hoặc quy mọi lỗi về M9. Probe pwd.getpwuid xác nhận thiếu identity; các lỗi Path.home/getpass xuất hiện ở nhiều module cũ và M9. Main sửa riêng verifier ngoài repo để mount passwd read-only có identity UID 10001 tương ứng production, không đổi HOME hoặc guard/source ứng dụng. Ca M5 CLI từng fail chạy lại đạt 1 pass ở C:/Temp/sw-m9-pg-z6355m44/pytest.log. Full regression với worker đã sửa đang chạy.

Trong log có finding thực M9 độc lập với môi trường: tests/unit/test_architecture.py::test_every_router_module_stays_inside_the_service_boundary phát hiện router M9 import SQLAlchemy, gọi database và commit trực tiếp. Main giao native chuyển truy vấn/validation/transaction về service và repository trong các file M9 đã thuộc allowlist, giữ nguyên test kiến trúc và HTTP contract. Đây là sửa regression trong scope, không thay kiến trúc dự án hoặc baseline. Checkpoint 3 được mở lại về mặt review nội bộ; task vốn IN_PROGRESS nên không có state transition giả. Checkpoint 4 tiếp tục kiểm thử, chưa nghiệm thu; full regression cần chạy lại sau sửa source.

### 2026-11-06 — Sửa kiến trúc và review frontend checkpoint 4

Native chuyển SQL và transaction khỏi router về service trong scope M9, giữ nguyên test kiến trúc. Main xác minh 23 unit architecture/API pass; PostgreSQL architecture/API/persistence/concurrency đạt 30 pass (C:/Temp/sw-m9-pg-jhlijptb/pytest.log). Review tiếp yêu cầu dùng permission map thực tế cho cả read/review và rollback khi HTTP write lỗi. Backend require_permission nhận dependency tùy chọn với default cũ không đổi; M9 dùng actor đã refresh. Main kiểm tra diff và chạy API M9, legacy auth, RBAC, architecture trên PostgreSQL: 150 pass (C:/Temp/sw-m9-pg-16fa48eg/pytest.log). Full backend ở C:/Temp/sw-m9-pg-z60dczuh còn chạy trên snapshot trước sửa kiến trúc, không phải evidence cuối của source hiện hành.

Frontend checkpoint 4 có hai trang, API helper, route guard, menu và icon cục bộ. Main review identity guard hai giai đoạn tải, pending review, retry giữ payload/key, note khi conflict, disclaimer synthetic/phi nhân quả và style chung. Native bổ sung test và sửa icon màu tĩnh cho img. Main typecheck/build đạt exit 0, Vite cảnh báo chunk lớn hơn 500 kB. Ruff toàn app/tests/alembic và diff check đạt.

Main test:all lượt đầu có 413 Vitest pass và một assertion timing ở router.integration.test.tsx cho route replenishment thất bại khi kiểm tra fetch ngay sau heading. Không sửa file này. Chạy lại chính test đạt 1 pass, sau đó full Vitest đạt 414 pass/45 file (C:/Temp/sw-m9-vitest-review.log). Ghi nhận timing có thể tái diễn, không coi lượt test:all đầu đã xanh. Host chạy độc lập đạt 88 pass/2 fail (C:/Temp/sw-m9-host-checkpoint4.log): exact menu expectation cho admin/warehouse trong client/tests/ui-shell-remediation.test.js chưa có mục mới. Client và các assertion khác giữ nguyên. File host này ngoài allowlist, native không sửa và dừng trước checkpoint 5. Cần duyệt amendment chỉ thêm ['/anomalies', 'Bất thường'] đầu hai mảng expectedLinks admin/warehouse, rồi chạy lại test:all. Task giữ IN_PROGRESS và review PENDING, chưa browser verification hoặc commit/push/merge.

### 2026-11-06 — Scope amendment được duyệt cho host menu

Người dùng trả lời “ok” cho đề nghị bổ sung client/tests/ui-shell-remediation.test.js. Cho phép thêm đúng ['/anomalies', 'Bất thường'] đầu hai mảng expectedLinks của admin/warehouse, giữ nguyên client và mọi assertion cũ. Lý do: exact menu expectation còn thiếu destination M9 đã duyệt. Approver: người dùng. Native sửa, main review và chạy lại test:all trước checkpoint 5. Không cấp quyền commit/push/merge.

Full backend snapshot cũ với identity worker đã sửa đã kết thúc: 1526 pass, 1 fail architecture đã được khắc phục trên source mới, 16 skip do Linux worker không có Docker CLI, 3 Windows test deselected theo guard. Log C:/Temp/sw-m9-pg-z60dczuh/pytest.log. Không coi run này đạt; cần full run trên source mới. Các kiểm tra Compose/Windows có suite riêng.

### 2026-11-06 — Checkpoint 4 đã qua kiểm thử, bắt đầu checkpoint 5

Main review amendment host menu đúng hai dòng, client/assertion giữ nguyên. npm.cmd run test:all đạt exit 0 gồm 414 Vitest và 90 host, log C:/Temp/sw-m9-frontend-amended.log. Chấp nhận checkpoint 4 trong phạm vi code/unit/host, chưa coi là browser verification. Native tiếp tục đúng allowlist checkpoint 5 để chuẩn bị fixture thực sự chạy pipeline M5/Isolation Forest/SHAP và suite browser riêng. Main full backend snapshot nguồn hiện hành đang chạy ở C:/Temp/sw-m9-pg-2r0vusix, chưa có kết quả cuối. Chưa commit/push/merge hoặc nghiệm thu AC-6.

### 2026-11-06 — Checkpoint 5 bị gián đoạn vì hết dung lượng, dọn cache theo yêu cầu

Đã build thành công image backend/frontend chuẩn M9. Native chuẩn bị fixture M5 hai SKU/kho, model và catalog thật, gồm SHAP available, explainer lỗi có chủ đích và batch không có alert. Hai thiết kế fixture đầu không sinh alert; giữ nguyên thuật toán/ngưỡng, điều chỉnh fixture demo và không coi kết quả demo là đánh giá hiệu quả heldout hay thực tế. Public catalog chỉ mount read-only. Browser suite mới discovery 8 trường hợp qua hai profile, chưa thực thi thành công, không đánh dấu AC-6.

Stack M9 riêng khởi tạo database nhưng migrate gặp connection refused vì healthcheck Unix socket nhận temporary init server trước TCP. Native sửa đúng healthcheck compose thêm -h 127.0.0.1. Chưa xác minh lại stack sau sửa. Trong lúc main sửa công cụ điều phối bên ngoài repo, ổ C hết dung lượng; script C:/Temp/sw-m9-control-2hppsmuh/e2e.py bị truncate về 0 byte. Mã nguồn native không có lỗi ghi. Full backend source mới ở C:/Temp/sw-m9-pg-2r0vusix bị lỗi filesystem ở khoảng 68%, không được coi là PASS. Docker báo không thể khởi động. Native được giữ nguyên source và dừng ghi/test. Tài nguyên stack M9 và bằng chứng vẫn giữ, chưa xóa database hoặc reset Docker.

Người dùng yêu cầu dọn dung lượng không dùng. Main chỉ kiểm kê rồi chạy npm.cmd cache clean --force tại cache thực tế C:/Users/TQUOCTOAN/AppData/Local/npm-cache và python -m pip cache purge tại cache pip tương ứng. Trước dọn npm khoảng 6,04 GB và pip 266,3 MB; sau dọn npm còn khoảng 241 MB và pip 1,4 KB. Dung lượng C trống đo được 5.540.741.120 byte (5,16 GiB), so với khoảng 16,6 MB trước dọn. Không xóa node_modules, virtualenv, source, .env, Docker image/volume, snapshots hay logs. Lệnh xóa snapshot ở phiên trước bị automatic approval review chặn, không chạy lại để lách chặn. git diff --check đạt sau dọn. Task vẫn IN_PROGRESS, review PENDING; cần khôi phục điều phối ngoài repo, kiểm tra Docker và chạy lại verification trước nghiệm thu. Chưa commit/push/merge.

### 2026-11-06 — Trở lại M9 và IN_PROGRESS -> VERIFYING

Người dùng yêu cầu tiếp tục dự án, dừng mọi thao tác gỡ/xóa thêm. Xác minh worktree codex/m9-anomaly-explanations vẫn ở dc3af9b, thay đổi nguồn được bảo toàn và diff check đạt. C trống khoảng 48 GB. Docker Desktop được khởi động lại bằng CLI, engine 29.7.2 đã trả lời. Không reset, xóa database hoặc sửa lịch sử Git. Khôi phục công cụ điều phối ngoài repo ở C:/Temp/sw-m9-control-2hppsmuh/e2e-resume.py, dùng lại metadata ownership/secret riêng và public catalog hiện có; không in credential.

Native review chỉ đọc checkpoint 5 xác nhận có ba pha fixture và hai profile desktop/mobile, ghi rõ browser M9 chưa thực thi và hosted CI chưa gọi config M9. Main đã đọc compose, fixture và browser suite; triển khai năm checkpoint đã có để verification. Chuyển IN_PROGRESS -> VERIFYING, chưa đánh dấu AC hoặc review đạt. Bắt đầu chạy lại full backend trên PostgreSQL cô lập và browser thật. Nếu phát hiện lỗi nguồn cần sửa, phải ghi VERIFYING -> IN_PROGRESS trước.

### 2026-11-06 — Browser pha đầu đạt, VERIFYING -> IN_PROGRESS cho lookup E2E

Main khôi phục Docker/stack, sửa email domain ở cấu hình seed bên ngoài repo theo validation hiện hữu, không thay mã nguồn. Migration/seed/healthcheck đạt. Browser pha unavailable đạt 2 test và pha available-no-alert đạt 2 test, mỗi pha có desktop/mobile; các ca khác skip theo phân pha, không cộng skip thành pass. Frontend test:all mới đạt 414 Vitest + 90 host, typecheck/build/Ruff/3 Windows guard đạt. Full PostgreSQL còn đang chạy tại C:/Temp/sw-m9-pg-39rr3v3s.

Browser pha ready có 2 network retry pass và 2 ca luồng chính fail HTTP500 khi helper findAlerts gửi Promise.all cho tới 100 GET detail đồng thời. Log API xác nhận QueuePool size5/overflow10 hết connection và timeout30s. Đây là cách lookup fixture tạo tải lớn ngoài mục tiêu kiểm thử chức năng; không đổi pool/auth/global API để che lỗi. Main chuyển VERIFYING -> IN_PROGRESS trước khi giao native xác minh và giới hạn concurrency lookup trong đúng client/e2e-anomalies/anomalies.spec.ts, giữ toàn bộ assertion nghiệp vụ, không thêm sleep/retry. Các lỗi chưa được coi đã sửa. Main đã chụp UI từ API thật riêng sau lượt thất bại, chưa nghiệm thu AC-6.

### 2026-11-06 — Lookup E2E đã sửa, IN_PROGRESS -> VERIFYING

Native xác minh log pool timeout rồi đổi findAlerts từ Promise.all trên tới 100 detail sang gọi tuần tự và dừng khi có cả explanation available/unavailable. Không thay assertion, thêm sleep/retry hoặc đổi API/pool. Main đọc diff và tiếp tục verification, discovery vẫn 8 trường hợp chưa tính pass. Chuyển IN_PROGRESS -> VERIFYING để chạy lại browser ready. Snapshot backend đang chạy không bị ảnh hưởng vì sửa chỉ file browser. Main đã xem ảnh danh sách desktop và chi tiết mobile từ dữ liệu/API thật; cả hai document không tràn ngang viewport, chưa coi đây là bằng chứng luồng review đã pass.

### 2026-11-07 — VERIFYING -> REVIEWING

Full backend trên PostgreSQL cô lập đạt 1527 pass, 16 skip do worker Linux thiếu Docker CLI, 3 deselected theo Windows guard. Snapshot 32 file backend khớp hash worktree. Windows chạy 47 seed test gồm phần Compose và 3 guard riêng đều đạt. Frontend 414 Vitest và 90 host, typecheck, build, Ruff và diff check đạt. Vite cảnh báo kích thước chunk lớn hơn 500 kB.

Browser M9 trên Docker chuẩn đạt 2 test unavailable, 2 test empty sau import run không alert, 4 test ready sau import catalog. Tổng 8 lượt đạt qua desktop/mobile, gồm admin/warehouse ghi phản hồi, client 403, replay, 409, SHAP thật và retry. Các skip do phân pha không tính vào kết quả đạt. Kiểm tra hình ảnh danh sách desktop và chi tiết mobile từ API thật, không tràn ngang viewport. Tại pha ready ban đầu, helper dồn tới 100 GET detail làm cạn pool. Helper tuần tự đã kiểm thử lại và giữ assertion. Chưa đánh giá khả năng chịu tải cao.

So sánh build ban đầu lệch vì frontend local dùng API base mặc định còn Docker dùng /api/v1. Build lại với cùng biến và đối chiếu byte trong container cho thấy 4 file web và 16 file Python của API khớp. Kiểm tra 51 đường dẫn nguồn khớp manifest, không có giá trị runtime secret hoặc mẫu credential đã quét. Đây là quét giới hạn theo mẫu. Các probe hợp đồng bổ sung đạt 6 ca, gồm trường lạ, schema sai, NaN, hai Infinity và đổi nhãn holdout giữ nguyên score/ngưỡng. Ba catalog xác minh digest thành công, gồm 383 cảnh báo SHAP thật với residual tối đa 3,33e-16, 383 cảnh báo đi theo đường explainer lỗi có chủ đích và một batch không alert. Chuyển REVIEWING để đối chiếu bảy AC và phạm vi thay đổi.

### 2026-11-07 — Independent review và REVIEWING -> DONE

Main đối chiếu diff 51 file với allowlist và hai amendment đã duyệt. Review xác nhận auth hiện hữu và quyền ngoài M9 giữ hành vi, fixture mặc định ẩn, phản hồi ghi riêng trong PostgreSQL, và workflow CI chỉ thêm extra anomalies vào lệnh cài đặt. Docker API và gói web đã đối chiếu byte với mã nguồn/cấu hình kiểm thử. Sáu mục baseline khớp SHA-256 trước khi đánh dấu checkbox. Review đạt đủ bảy AC theo phạm vi đồ án đã duyệt. Chuyển REVIEWING -> DONE, Review Result APPROVED. Các thay đổi vẫn ở worktree riêng để chờ quyền commit.

### 2026-11-07 — Review trước commit và checkpoint M9

Người dùng yêu cầu review lại rồi commit, push và merge. Main đối chiếu 51 file với manifest nghiệm thu, scan secret trên code và hồ sơ, kiểm tra nhánh đích `feat/figma-ui-v2` ở `dc3af9b` và xác nhận phần việc đang sửa ở checkout chính nằm ngoài diff M9. Backend kiểm thử lại đạt 1527 pass tại `C:/Temp/sw-m9-pg-r031x_5z/pytest.log`. Frontend đạt 414 Vitest, 90 host, typecheck và build. Ruff và ba guard Windows đạt. Kiểm tra staged diff phát hiện ba dòng trống EOF trong frontend. Main bỏ đúng ba dòng đó, kiểm tra lại 35 test frontend tập trung và build đạt. Tên asset build giữ nguyên. Kết quả browser 8 lượt đã được ghi ở phần verification.

Ba checkpoint nguồn gồm `a01e954` (pipeline, API và persistence), `1a8ec52` (workspace và quyền giao diện) và `12e45aa` (fixture và browser E2E). Hồ sơ được chuyển từ checkout chính sang worktree M9 tại cùng đường dẫn tương đối để commit cùng nhánh và tránh ghi đè bản untracked khi merge. Hash khớp trước và sau khi chuyển.

## Verification Evidence

| AC | Bằng chứng |
| --- | --- |
| AC-1 | `test_missing_coverage_is_not_zero`, `test_unknown_past_movement_is_not_a_known_zero`, `test_complete_empty_day_is_valid_zero`, `test_constant_training_data_is_unavailable`, `test_feature_order_mismatch_is_rejected` và probe `contract-probes.log` cho schema sai, trường lạ, NaN và Infinity. Feature snapshot có nguồn, cutoff, version và ordering. |
| AC-2 | `test_future_events_do_not_change_prior_features`, `test_final_holdout_cannot_change_threshold`, `test_fit_is_deterministic_including_provenance` và probe đảo nhãn holdout giữ nguyên toàn bộ score và threshold. Fit trên train, ngưỡng trên validation normal. |
| AC-3 | `test_actual_m5_bundle_through_shap`, `test_shap_reconstructs_displayed_score` và các ca explainer thiếu, lỗi, sai additivity. Browser đối chiếu điểm và SHAP thật. Catalog 383 giải thích đạt residual tối đa 3,33e-16 so với tolerance 1e-8. |
| AC-4 | Migration 0005, các test persistence/rollback và `test_concurrent_import_is_single_batch`, `test_only_one_reviewer_wins_expected_version`, `test_concurrent_same_key_replays_once`. Browser xác nhận history, replay và 409 qua API thật. |
| AC-5 | `test_real_auth_rbac_and_fixture_hidden`, `test_existing_token_role_and_active_state_are_refreshed`, `test_review_replay_conflict_and_stock_unchanged`. Kiểm tra 401/403/404/422, stock và transaction có dữ liệu không thay đổi sau phản hồi. Pipeline chấm điểm chỉ dùng bundle ngoại tuyến. |
| AC-6 | 8 lượt Playwright thực thi đạt qua desktop/mobile và ba pha unavailable, empty, ready. Ba role, list/detail/ghi phản hồi, retry mạng và giải thích unavailable đã chạy với API thật. Ảnh desktop/mobile đã được main xem. |
| AC-7 | Catalog và UI ghi dữ liệu kiểm thử tổng hợp. Metrics holdout chỉ tính từ nhãn synthetic và null khi thiếu điều kiện. Precision/recall thực tế giữ NOT VERIFIED. |

Backend `pytest -q` trên PostgreSQL cô lập đạt 1527 pass, 16 skip thuộc kiểm tra Compose thiếu Docker CLI trong worker Linux, 3 deselected dành cho Windows. Log `C:/Temp/sw-m9-pg-39rr3v3s/pytest.log`. Windows `tests/test_seed.py` đạt 47 pass gồm Compose, và `tests.run_quality_ci windows` đạt 3 guard. Frontend `npm.cmd run test:all` đạt 414 Vitest và 90 host. `npm.cmd run typecheck`, `npm.cmd run build`, Ruff và `git diff --check` đạt. Vite ghi cảnh báo chunk lớn.

Bằng chứng browser và ảnh tại `C:/Temp/sw-m9-e2e-beevwk5p`, log `playwright-unavailable.log`, `playwright-empty.log`, `playwright-ready.log`. `runtime-source-check.json` ghi đối chiếu 16 file API và 4 file web. `source-scan.json` ghi manifest 51 file và kết quả scan giới hạn. Secret, fixture thô và artifact test nằm ngoài repo.

## Review Result

- Result: APPROVED
- Findings: Không còn finding chặn nghiệm thu M9 theo phạm vi đồ án. Lỗi lookup browser do phát đồng thời 100 request đã được xử lý trong test helper và chạy lại đạt. Khả năng chịu tải cao và precision/recall thực tế vẫn NOT VERIFIED. Suite browser M9 chạy local riêng, hosted CI hiện cài dependency và vẫn dùng ma trận browser cũ. Chưa có node Figma M9 được duyệt để đối chiếu riêng.

## Completion Evidence

Ngày 2026-11-07, main nghiệm thu 7/7 AC cho tính năng bất thường trong worktree `codex/m9-anomaly-explanations` trên baseline `dc3af9b`. M9 cung cấp Isolation Forest, giải thích SHAP và luồng admin/warehouse rà soát có lịch sử trên fixture đã xác minh. Các commit nguồn và lần review trước khi tích hợp được ghi trong Progress Log.
