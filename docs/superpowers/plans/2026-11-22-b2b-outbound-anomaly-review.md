# Kế hoạch đã rà soát: Nối giao dịch thực xuất B2B với màn Bất thường (demo)

- Task identifier: `implement-b2b-outbound-anomaly-review`
- Task: `docs/tasks/implement-b2b-outbound-anomaly-review.md`
- Đường dẫn dự kiến của plan: `docs/superpowers/plans/2026-11-22-b2b-outbound-anomaly-review.md`
- Cơ sở: Đề cương V2 mục 2.9, 2.10, 3.5, 3.7; spec/kế hoạch M9 được tham chiếu trong `docs/tasks/implement-anomaly-explanations.md`.
- Trạng thái: bản chốt thiết kế để đưa vào repo. Task vẫn DRAFT; chưa xác minh checkout đích, chưa chạy thử luồng mới.

## 1. Luồng demo cần chứng minh

1. Dùng app thật trên PostgreSQL riêng chỉ dành cho demo. Tạo lịch sử và đơn đích bằng dữ liệu tổng hợp theo kịch bản, không dùng dữ liệu người dùng thật. Client gửi yêu cầu, Admin duyệt hoặc từ chối, Admin hoặc Warehouse thực xuất đơn đã duyệt; chỉ fulfillment thành công mới ghi phiếu xuất, giao dịch tồn, provenance, và trạng thái trong cùng transaction.
2. Sau commit, batch ngoại tuyến chụp công việc đã được xác minh bằng M5, tạo bundle UTC, rồi đưa qua M9 hiện có. Đơn đích được xác định trước khi chạy mô hình. Không chọn lại đơn hay thay ngưỡng dựa trên kết quả holdout.
3. Kiểm tra run và nhập qua cổng fixture hiện tại. Hiển thị đúng cảnh báo và SHAP trên màn Bất thường hiện có. Cung cấp chỉ dẫn tìm đúng run/cảnh báo cho buổi demo; không thêm đường dẫn chi tiết đơn hoặc endpoint công khai mới trong lát cắt này.

Phần giữ nguyên: Dự báo, Bổ sung hàng, bộ chọn kho trên UI và **Kiểm tra đơn tạm tính** (Robust Z-score trước phê duyệt). Kiểm tra tạm tính vẫn chạy như trước và không được gắn nhãn Isolation Forest/SHAP. Luồng mới dùng đúng giao dịch đã thực xuất; không thay kết quả trước phê duyệt.

## 2. Hợp đồng trích xuất và liên kết

- Tái sử dụng `app/analytics/snapshot.py` và admission từ M5. Thiết lập kết nối danh tính riêng được kiểm, transaction read-only REPEATABLE READ; nguồn `operational_b2b` trong admission mô tả **kiểu trích xuất**, không biến dữ liệu giả thành dữ liệu vận hành. Bundle đầu ra demo vẫn có `dataset_class=fixture`, `target=gross_fulfilled_units`, representation events, UTC, mappings và coverage có thời điểm rõ ràng. Admission dùng `source.channel=managed_b2b_fulfillment`, `kind_map=OPERATIONAL_KINDS`, ID kho/sản phẩm dạng số, `database_identity` khớp DB demo và `availability_policy_ref` không rỗng. Chứng minh coverage từng ngày khả dụng trước các thời điểm chấm; không thay ngữ nghĩa M5 để bỏ qua validation.
- M5 xác thực workflow đã duyệt/thực xuất, provenance `purchase_request_fulfillment`, đúng liên kết phiếu xuất và stock transaction outbound, chênh tồn và lượng, kho/SKU, thời điểm/cutoff và mapping đơn vị. Sự kiện xuất có `event_id=tx:<id>` bên trong runner. Thiếu/mâu thuẫn thì dừng; nếu nguồn có chuyển kho, nhập kho hoặc dòng khác thì M5 có thể ghi nhận và phân loại chúng, nhưng M9 không được dùng chúng như giao dịch B2B đã thực xuất.
- M9 tạo khóa mờ `aek1-…` theo khóa sự kiện chuẩn hóa đã có. Runner đối chiếu chính xác `(run_id, source_record_key)` từ sự kiện thuộc bundle đã xác minh với artifact đã kiểm digest và bản ghi được nhập; không ghép theo ngày, lượng, SKU hoặc run gần nhất. Dùng lại phép dẫn xuất khóa của M9, không chép lại một công thức khác. Chỉ giữ ánh xạ xác minh trong runner/thử nghiệm. Có thể dùng ID thô trong bundle hoặc cấu hình đầu vào riêng theo hợp đồng M5/M9; không đưa ID thô, khách hàng, ghi chú, đường dẫn hoặc bí mật vào catalog/cảnh báo công khai. Nếu thiếu đúng alert, báo rõ không có cảnh báo phù hợp/không đủ dữ liệu/lỗi theo kết quả, không trỏ sang alert khác.
- Không cần migration hay bảng liên kết ở lát cắt đầu nếu runner có thể xác nhận duy nhất và UI có thể mở đúng alert hiện hữu. Nếu đọc checkout cho thấy cần API/schema mới để đạt AC, cập nhật scope và duyệt trước, không mở thêm quyền mặc định.

## 3. Kịch bản mô hình và giao diện

- Tái lập fixture có seed, thời gian cố định/một đồng hồ kiểm thử có chủ ý, thứ tự sự kiện rõ ràng, cùng một đơn vị; lịch sử đầy đủ trước mỗi đặc trưng bảy ngày. Kịch bản phải có ít nhất 128 mẫu train hợp lệ và 100 mẫu normal validation hợp lệ sau khi xét coverage/cutoff; test cuối tách riêng. Dữ liệu seeding không bỏ qua transaction thực xuất của đơn đích; dùng thiết lập thời gian chỉ trong fixture test, không chỉnh logic timestamp production. Dựng lịch sử tổng hợp bằng bộ nạp test trên DB cô lập với timestamp và các liên kết nhất quán như luồng thật; M5 vẫn phải xác minh tất cả dòng. Cả đơn đích bất thường và đơn đối chứng bình thường phải đi qua API thực xuất. Quy định trước thời điểm, SKU/kho, đơn vị, hai đơn đích, các tập và tiêu chí đạt; không chọn lại trên holdout. Trước READY, xác minh có cách đặt đồng hồ của runner hoặc bản ghi thuộc fixture mà không sửa timestamp vận hành; chừa đủ ngày khởi động trước tập train.
- Chấm bằng Isolation Forest, score `-IsolationForest.score_samples`, ngưỡng validation hiện tại (quantile 0.99 trên normal synthetic, phương pháp `higher`); chỉ gắn cờ khi điểm lớn hơn ngưỡng. Nhãn fixture phục vụ validation và đánh giá; không đi vào feature hoặc fit. Đơn đích được thiết kế có đặc trưng bất thường cố định và đủ tồn để thực xuất, không làm lệch train/validation.
- SHAP dùng đúng callable score của M9; kiểm tra `base + sum(signed contributions)` với tolerance 1e-8. Dùng biểu đồ thanh hai chiều âm/dương và phản hồi đang có. Giải thích thuộc về điểm mô hình, không khẳng định nguyên nhân. Giữ `NOT VERIFIED` cho chất lượng vận hành thực và không thay kết quả RQ1.
- Chỉ chạy runner, nhập và đọc kết quả demo khi `APP_ENV=test` hoặc `integration` và `ANOMALIES_ALLOW_FIXTURE=true` với DATABASE_URL được xác minh là DB demo riêng; actor hiện hữu và hợp lệ. Giữ kiểm tra run công khai trước import, tính nguyên tử/idempotency và RBAC M9. Không hướng dẫn chạy với DB dev chung/production.

## 4. Thứ tự triển khai và tiêu chí RED

| Checkpoint | Test trước khi viết |
| --- | --- |
| RED 1: sau commit | Client không duyệt/xuất, Warehouse không duyệt/từ chối, Admin duyệt hoặc từ chối, Admin hoặc Warehouse xuất đơn đã duyệt. Tạo, duyệt, từ chối và rollback không sinh sự kiện xuất; chụp từ kết nối khác sau commit thì thấy đúng giao dịch. Replay hoặc hai lần trích xuất không tăng số giao dịch. |
| RED 2: liên kết | Hai phiếu cùng kho/SKU/lượng vẫn chỉ khớp đúng ID transaction đích; sai mapping, purpose, cutoff hoặc digest không công bố liên kết. |
| RED 3: mô hình | Dataset ngắn trả thiếu dữ liệu; kịch bản chuẩn có cảnh báo đích và SHAP cộng đúng; lỗi SHAP chỉ báo không thể giải thích. Kiểm tra thay nhãn holdout không đổi ngưỡng. |
| RED 4: import/UI | Nhập lại đúng artifact đã xác minh không tạo run/cảnh báo trùng; client không truy cập được; người quản lý thấy dấu đóng góp và lưu đánh giá; snapshot tồn và nghiệp vụ không đổi giữa trước/sau phân tích. Dự báo, Bổ sung hàng, bộ chọn kho và Kiểm tra đơn tạm tính hoạt động như baseline, không nhận kết quả Isolation Forest/SHAP. |

Test luồng tích hợp phải dùng PostgreSQL riêng, kết nối đọc độc lập với transaction ghi. Chỉ triển khai ở worktree riêng đã đối chiếu với mã hiện hành; không ghi đè các sửa đổi khác. Thêm tài liệu chạy demo sau khi pipeline chạy thành công.

## 5. Lệnh đã có, chưa chạy trong lần soạn

- Cài trong môi trường phù hợp của repo: `python -m pip install -e ".[dev,anomalies]"`.
- Lệnh M5 có sẵn: `python -m app.analytics.cli build --admission <admission.json> --output-root <bundles-root>`, với `ANALYTICS_DATABASE_URL` khớp danh tính đọc-only đã khai báo. Không dùng `--input-root` với `operational_b2b`.
- Lệnh M9 có sẵn: `python -m app.anomalies.cli evaluate --config <config.json> --input-root <bundle-dir> --output-root <catalog-root> --allow-fixture`. Đối số `--input-root` trỏ thẳng vào bundle đã xác minh. Lệnh import: `python -m app.anomalies.cli import-run --run-id <arv1-id> --catalog-root <catalog-root> --actor-id <admin-or-warehouse-id> --allow-fixture`.
- Đối chứng M9 có sẵn: `python -m tests.prepare_anomalies_e2e --root <thư-mục-mới-ngoài-repo>`; dòng `available=...` chứa run có SHAP thực. **Helper này không tạo đơn B2B trong PostgreSQL** và không thay thế AC-1/AC-2.
- Regression backend hiện có: `python -m pytest -q tests/postgres/test_purchase_requests_api.py tests/postgres/test_purchase_request_atomicity.py tests/postgres/test_anomalies_persistence.py tests/postgres/test_anomalies_api.py`, rồi kiểm tra theo task. Xác nhận đúng mục tiêu DB trước khi chạy.

## 6. Lệnh/artifact đề xuất, chưa tồn tại

- `python -m tests.prepare_b2b_outbound_anomaly_demo --root <thư-mục-mới-ngoài-repo>`: runner tích hợp đề xuất; kiểm DB demo, dựng dữ liệu tổng hợp, chạy luồng nghiệp vụ thật, xác minh link và in run/alert ID mờ.
- `python -m pytest -q tests/postgres/test_b2b_outbound_anomaly_demo.py`: test tích hợp đề xuất; file và tên có thể cập nhật lúc duyệt plan.

## 7. Cổng duyệt và bàn giao

- Xác minh 3 task phụ thuộc DONE trên checkout đích, DB test cô lập và quyền actor. Chạy kiểm tra khả thi M5 → M9 bằng fixture có sẵn hoặc fixture riêng ngoài repo, để xác minh bundle nguồn DB đáp ứng hợp đồng M9; nếu chưa chứng minh được thì giữ DRAFT và ghi rõ điểm vướng. Không dùng việc chạy helper M9 riêng làm bằng chứng liên kết giao dịch. Chốt dữ liệu demo/định danh nghiệp vụ với người duyệt. Không cần dữ liệu vận hành thật để nghiệm thu demo.
- Đưa hai file vào đúng đường dẫn repo, chọn rõ task, ghi phê duyệt plan và xác minh baseline trước khi chuyển READY theo AGENTS. Chỉ bắt đầu triển khai khi không có task khác đang được triển khai cùng lúc. Cập nhật phạm vi nếu cần schema/điểm nối trợ giúp ngoài runner. Lưu kết quả mỗi checkpoint và ghi rõ bằng chứng nào chỉ là fixture.
- Hỗ trợ dữ liệu vận hành thật, tự chạy sau fulfillment hoặc chấm điểm liên tục cần task riêng với admission, nhãn/coverage đã được duyệt, giám sát, bảo vệ quyền và hợp đồng xuất bản. Không hạ cổng fixture hoặc dùng z-score để đi tắt.
