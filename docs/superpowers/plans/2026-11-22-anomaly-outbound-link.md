# Plan DRAFT — Mở đúng phiếu xuất từ cảnh báo bất thường

- Task identifier: `link-anomaly-alert-to-outbound`
- Task: `docs/tasks/link-anomaly-alert-to-outbound.md`
- Đường dẫn dự kiến: `docs/superpowers/plans/2026-11-22-anomaly-outbound-link.md`
- Cơ sở: V2 mục 2.9, 2.10, 3.5, 3.7; spec M9 tham chiếu trong task `implement-anomaly-explanations` và hợp đồng M5.
- Trạng thái: DRAFT. Chưa áp migration, chưa lấy quyền ghi DB demo đang chạy.

## 1. Mở đúng phiếu, không suy đoán

- `tests/prepare_b2b_outbound_anomaly_demo.py` lấy event đích từ **transaction ID của lần fulfill đã commit**. M5 xác minh workflow `approved`/đơn `fulfilled`, phiếu xuất, transaction outbound, `movement_provenance.purpose=purchase_request_fulfillment`, kho/SKU/lượng/chênh tồn và mốc thời gian. M9 dùng khóa nguồn mờ từ (namespace, sản phẩm, kho, đơn vị, event ID), không thể khôi phục đáng tin từ mã mờ hoặc số liệu hiển thị.
- **Đợt này chỉ demo B2B tổng hợp.** Ưu tiên runner hiện có ghi liên kết trong cùng quy trình đáng tin cậy. Runner lấy bằng chứng từ lần chụp M5 đọc-only trên đúng DB riêng, giữ kiểm tra canonical/digest của bundle/cat và writer ghi trên cùng DB; không nhận danh sách `alert_id → outbound_id` từ người dùng/HTTP hoặc file CSV tùy ý. Không đổi schema catalog công khai. Không chạy huấn luyện hoặc đọc file từ HTTP.
- Trước ghi, xác minh `run.input_version == bundle.data_version` và **toàn bộ** `run.source_hashes` khớp các artifact hash cộng `source_checksum` M5, hai artifact đều đúng digest, cùng cấu hình fixture UTC và `gross_fulfilled_units`. Kiểm lại source key từ đường M9 hiện có, đúng giao dịch `tx:<id>`, khớp feature/time của đúng alert; không tạo thuật toán hash mới hay đổi score. Xác minh riêng `tx.outbound_id`, `workflow.outbound_transaction_id/outbound_id`, kho/sản phẩm/đơn vị/lượng, `fulfilled_at`, mục đích B2B và actor thực xuất (`fulfilled_by_id = tx.created_by_id = outbound.created_by_id`). Nếu không xác minh đủ, không ghi.
- Không dùng tên DB/port hoặc ID giống nhau làm chứng minh duy nhất. Giữ guard loopback, tên+role demo, test/integration + cờ fixture; kiểm danh tính cụm/cài đặt riêng trước khi đọc/ghi. Với phát hành mới, quản lý một dấu định danh DB demo tạo riêng và lưu/kiểm cùng lần chụp/ghi; DB bản sao mới không kế thừa dấu để tái lập liên kết từ DB khác. Chốt cách kiểm trên checkout trước khi chuyển READY; chọn phương án cùng DB, không cho qua guard bằng cách gắn nhãn mới sau khi thấy hash.

## 2. Phiếu #451 hiện tại và phương án không đưa nhầm link

- Demo Windows hiện tại: xác minh checkout, revision, định danh DB, đường dẫn artifact thuộc đúng runner; catalog và bundle gốc còn đủ, bất biến. Manifest công khai M5 **không giữ định danh DB đầy đủ**; không coi riêng manifest hoặc cặp số `451` là bằng chứng nguồn. Nếu có hồ sơ chạy đáng tin cậy gắn bản demo đang chạy với artifact gốc, dùng runner riêng tái chụp M5 qua private admission đúng mẫu, buộc trùng `source_checksum` và kiểm exact run/cảnh báo/transaction như mục 1. Đối chiếu thêm mã yêu cầu ngẫu nhiên đã ghi nhận trong bằng chứng chạy gốc với `PurchaseRequest.request_number` và `Outbound.reference` (chúng phải trùng); checksum M5 chưa chứa hai trường này. Lấy mã từ phiếu hiện tại mà không có chứng cứ chạy trước đó không chứng minh được đó là cùng bản seed. Không hardcode hay công bố mã riêng này trong tài liệu hoặc catalog. Không seed lại vào DB đang chạy, không chọn phiếu thủ công.
- Nếu chỉ còn catalog, thiếu bundle/chứng cứ cài đặt, hoặc recapture khác digest: giữ cảnh báo cũ chưa liên kết. Tạo **bản demo khác với DB mới** theo luồng chuẩn và báo đúng mã mới. Ca #451 không được nghiệm thu là đã liên kết trên DB cũ nếu không đủ chứng cứ. Việc migration/backfill demo đang chạy phải có snapshot/đường lui được duyệt riêng trước thao tác.

## 3. Lưu và đọc tối thiểu

- Một migration **chỉ bổ sung** bảng liên kết riêng, nối Alembic head thực tế (bản sao đã thấy `20261122_0008`, không mặc định trên Windows). Khóa duy nhất theo cảnh báo hoặc (run, source key), FK hạn chế đến cảnh báo và transaction/phiếu, có bất biến private gồm bundle/source digest, dấu DB, mốc và chữ ký băm của projection nguồn (transaction/phiếu/workflow, kho/sản phẩm/lượng/đơn vị/thời gian/actor). Không lưu email/notes khách và không đính kèm mapping vào catalog; cùng giao dịch có thể được chấm lại ở run khác với liên kết riêng. Nhập hoặc liên kết cùng bằng chứng trả kết quả cũ; xung đột fail closed; rollback không đổi business row/cảnh báo.
- Đề xuất đúng một API đọc `GET /api/v1/anomalies/{alert_id}/outbound` và frontend route `/anomalies/:alertId/outbound` chỉ đọc. Cả hai dùng đúng quyền `anomaly:read` **và** `inventory:history:read` (admin/warehouse hiện có); kiểm quyền mới nhất trước lookup dữ liệu. Tái sử dụng kiểm `_get_alert`/run integrity, giữ gate M9 fixture; truy nguồn bằng FK đã xác minh, đối chiếu lại drift trước khi trả dữ liệu. Dữ liệu allowlist: mã phiếu, tên/SKU, kho, lượng/đơn vị từ binding lịch sử, thời điểm, ID thực xuất (User hiện không có tên hiển thị; không lấy email làm tên). Không hiển thị mã transaction thô, ghi chú, khách, đường dẫn hoặc thông tin xác thực.
- Ở chi tiết cảnh báo, chỉ hiện **Mở phiếu xuất** khi kiểm tra endpoint cho kết quả đã xác minh; không cần mở thêm quyền trên trang danh sách. 401/403 không phụ thuộc liên kết tồn tại; 404 thống nhất cho không có/không còn xác minh được; lỗi truy cập tách với trạng thái thiếu liên kết và không rò chi tiết. Dùng mã cảnh báo làm đích route, tải qua API đã kiểm quyền, không chuyển hướng tới phiếu khác.
- Thay đổi sau khi chấm không sửa snapshot cũ: mất phiếu, khác số lượng/binding/provenance, hoặc correction tương lai khiến fingerprint khác thì ẩn nút/đích không khả dụng. Không thêm workflow hủy/sửa; repo hiện không có API hủy/sửa phiếu xuất. Liên kết và đọc không chạm quyền review, chấm điểm, tồn kho hoặc phiếu.

## 4. RED, test dữ liệu và chạy demo

| Nhóm | Tình huống bắt lỗi |
| --- | --- |
| Exact | Chọn trước target; tạo decoy cùng lượng/kho/SKU/thời điểm trong fixture, chỉ ID transaction chính xác thông qua provenance được mở. Phiếu #451 nghiệm thu riêng nếu chứng cứ gốc đủ. |
| Toàn vẹn | Catalog/bundle tampered; DB sai/copy trùng ID; khác source hash/namespace/mapping/actor/provenance; alert generic và phiếu thiếu/drift; không công bố link. |
| DB | Composite/FK/index và một head; migration test DB riêng; duplicate/retry atomic; lỗi giữa import + bind rollback; không thay dữ liệu/điểm/SHAP/hồ sơ review. Dữ liệu tamper chỉ ở DB thử cô lập, không sửa demo đang dùng. |
| Quyền/UI | 401 không đăng nhập, 403 client trước lookup, admin/warehouse chỉ đọc, vào trực tiếp không lách; gợi ý mở đúng phiếu desktop/mobile; fallback rõ; giữ tóm tắt và review. |

- Công cụ có sẵn: runner `python -m tests.prepare_b2b_outbound_anomaly_demo --root <thư-mục-mới-ngoài-repo>` (hiện chỉ thực hiện proof trong bộ nhớ); `python -m alembic heads`, kiểm `current` chỉ khi đã xác nhận DB đích. API phiếu sẵn có `GET /api/v1/outbounds/{id}` chỉ đọc theo inventory-history, không thay vai trò chứng thực liên kết.
- Đề xuất, **chưa có**: tích hợp bước lưu link riêng vào runner; lệnh tái xác minh/backfill chỉ cho demo đã có bám cổng mục 2, nếu được duyệt. Lệnh test ở task. Kiểm regression đầy đủ trước nghiệm thu.

## 5. Cổng READY

- Người dùng chọn đúng path task/duyệt hướng triển khai và ghi đủ task/plan; không chạy thêm executable task song song theo AGENTS. Kiểm dependency M4/M5/M9 DONE trên checkout đích; xác minh trạng thái bàn giao của task demo và UI trước, giữ nguyên nhiệm vụ khác. Xác minh head và phần làm việc tách biệt trước mở migration.
- Chốt bằng chứng gốc ca #451, cơ chế định danh DB và kết quả kiểm snapshot đọc-only; nếu không đủ, duyệt dùng bản seed cô lập mới, không cố duy trì ID 451. Chuẩn bị `TEST_DATABASE_URL` riêng, DB migration test độc lập và demo không dùng chung với bản chính. Không đánh dấu đã xác minh các mục này khi chỉ đọc mã.
- Các đường dẫn và phép kiểm trên là phương án duyệt. Chưa triển khai, chưa truy cập/ghi DB demo hay Windows trong lúc soạn.
