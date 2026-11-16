# Task: Gợi ý kho gần nhất cho luồng B2B

- **Task path:** `docs/tasks/implement-b2b-nearest-warehouse.md`
- **Task identifier:** `implement-b2b-nearest-warehouse`
- Status: DONE
- Phase: Gợi ý kho gần cho B2B
- Plan: docs/tasks/implement-b2b-nearest-warehouse.md#implementation-plan
- Depends on: docs/tasks/implement-b2b-purchase-requests.md, docs/tasks/implement-warehouse-gis.md
- Created: 2026-11-16
- Started: 2026-11-16
- Completed: 2026-11-16
- **Scope authority:** Goal, In scope, Out of scope and Acceptance criteria in this task.
- **Dependencies:** `docs/tasks/implement-b2b-purchase-requests.md` (`DONE`) and `docs/tasks/implement-warehouse-gis.md` (`DONE`).
- **Execution baseline:** frozen at `READY -> IN_PROGRESS` on 2026-11-16; unchanged.

## Goal

Trên trang `/purchase-requests/new`, sau khi khách chọn sản phẩm và số lượng, cho phép nhập vĩ độ/kinh độ điểm nhận và bấm “Tìm kho gần có đủ tồn”. Chỉ gợi ý kho còn tồn đủ cho số lượng yêu cầu, có tọa độ hợp lệ, xếp theo khoảng cách đường chim bay tăng dần. Chọn một gợi ý sẽ điền kho vào biểu mẫu hiện tại; khách vẫn xác nhận và gửi theo luồng B2B cũ. Không mở rộng quyền GIS quản trị.

## Context

- `PurchaseRequestFormPage` hiện tải sản phẩm đang hoạt động và toàn bộ kho, chọn kho thủ công bằng `Select`, xác nhận bằng dialog và gửi `POST /purchase-requests` với `Idempotency-Key`.
- `Permission.PURCHASE_REQUEST_CREATE` chỉ cấp cho `client`; trang `/purchase-requests/new` cũng chỉ dành cho quyền này.
- `Warehouse` có `latitude`/`longitude` tùy chọn và ràng buộc DB phải đi kèm nhau và nằm trong miền hợp lệ; mô hình không có cờ `is_active`, nên “kho đang hoạt động” trong task này được hiểu là kho còn tồn tại và có bản ghi tồn cho sản phẩm với số lượng đủ yêu cầu. Kho không có tồn hoặc tồn thấp hơn yêu cầu bị loại.
- `app.gis.schemas.distance_mm` đã cài đặt khoảng cách cầu (haversine) trên mặt cầu; dùng lại hàm này thay vì viết công thức mới.
- `app.gis.service.warehouse_options` đã có xếp hạng kho nhưng yêu cầu quyền `gis:route`, phụ thuộc snapshot đường bộ và trả nhiều dữ liệu nội bộ. Không tái sử dụng endpoint đó cho B2B.

## In scope

1. Thêm một endpoint chỉ đọc trong phân hệ Purchase Request: `GET /api/v1/purchase-requests/nearest-warehouses` với `product_id`, `quantity`, `latitude`, `longitude`. Quyền `purchase_request:create` (chỉ `client`). Không đổi quyền GIS, không mở `gis:read`/`gis:route` cho client.
2. Endpoint chỉ trả các kho có bản ghi tồn cho sản phẩm với `quantity >=` số lượng yêu cầu, tọa độ hữu hạn và trong miền hợp lệ. Sản phẩm phải tồn tại và đang hoạt động; ngược lại trả lỗi an toàn, không lộ dữ liệu kho.
3. Xếp theo khoảng cách đường chim bay tăng dần, hòa nhau thì theo `warehouse_id` tăng dần. Dùng lại `distance_mm`; trả `distance_km` đã làm tròn và metadata phương pháp `great_circle_haversine` cùng bán kính Trái Đất để UI ghi rõ cách tính.
4. Dữ liệu trả về tối thiểu: `warehouse_id`, `code`, `name`, `available_quantity`, `distance_km`; không trả địa chỉ, tọa độ, tồn của kho khác hay dữ liệu sản phẩm ngoài phạm vi.
5. Trên form B2B: thêm hai ô vĩ độ/kinh độ và nút “Tìm kho gần có đủ tồn”. Hiển thị danh sách gợi ý kèm khoảng cách và tồn khả dụng; nút “Chọn kho này” điền `warehouse_id` vào `Select` kho hiện tại. Giữ nguyên chọn kho thủ công, dialog xác nhận và luồng gửi cũ.
6. Khi đổi sản phẩm, số lượng hoặc điểm nhận, xóa kết quả gợi ý và bỏ qua phản hồi đến muộn của lần tìm trước. Nếu kho đang chọn là do gợi ý tự điền và đầu vào thay đổi, bỏ chọn kho đó để tránh gửi tồn không còn đúng; lựa chọn thủ công của khách vẫn giữ nguyên.
7. Khi không có kho phù hợp, API lỗi hoặc dữ liệu nhập sai, hiện thông báo tiếng Việt và vẫn cho khách chọn kho thủ công.

## Out of scope

- Không thêm cột/cờ trạng thái kho, migration, endpoint GIS mới hoặc thay đổi quyền GIS.
- Không tính tuyến đường thực tế, thời gian giao hàng, phí vận chuyển hay giữ chỗ tồn kho.
- Không thay đổi quy tắc tạo/duyệt/xuất yêu cầu mua hàng, không thêm luồng gửi mới.
- Không commit, push, mở PR hoặc deploy nếu chưa được yêu cầu riêng.

## Acceptance criteria

- [x] Endpoint mới chỉ cho `client`; `admin`, `warehouse`, người chưa đăng nhập bị từ chối (401/403) trước khi lộ dữ liệu.
- [x] Chỉ kho có `quantity >= quantity` yêu cầu được trả; kho thiếu tồn, không có bản ghi tồn hoặc tọa độ thiếu/không hữu hạn/ngoài miền bị loại.
- [x] Kết quả xếp tăng dần theo khoảng cách haversine, hòa nhau theo `warehouse_id`.
- [x] Sản phẩm không tồn tại hoặc không hoạt động trả lỗi an toàn, không trả danh sách kho.
- [x] UI hiển thị đúng thứ tự, khoảng cách km, tồn khả dụng và ghi rõ “đường chim bay / haversine”.
- [x] Chọn gợi ý điền đúng kho vào `Select`; gửi yêu cầu vẫn dùng `POST /purchase-requests` hiện có với `warehouse_id` đã chọn.
- [x] Đổi sản phẩm/số lượng/điểm nhận xóa kết quả cũ; phản hồi muộn không ghi đè kết quả mới.
- [x] Không có kho phù hợp hoặc API lỗi hiện thông báo tiếng Việt và giữ chọn kho thủ công.
- [x] Test backend, test frontend, typecheck, build và `git diff --check` đạt; thử được bằng tài khoản client trên stack demo cục bộ.

## Verification commands

```bash
python -m pytest -q
cd client
npm.cmd run test:all
npm.cmd run typecheck
npm.cmd run build
git diff --check
```

Bộ test bổ sung: sắp xếp kho theo khoảng cách; loại kho thiếu tồn; loại tọa độ sai/thiếu; phân quyền client/admin/warehouse/anonymous; phản hồi muộn; gửi yêu cầu qua luồng hiện có; OpenAPI contract cập nhật số endpoint.

## Implementation plan

1. Bổ sung schema request/response và phương thức repository/service chỉ đọc trong `app/purchase_requests`; dùng `distance_mm` của GIS, lọc và sắp xếp ổn định.
2. Đăng ký route tĩnh trước route `/{request_id}` trong `app/purchase_requests/router.py`, giới hạn `purchase_request:create`; từ chối query trùng/không hợp lệ.
3. Thêm API client, type và khối UI tìm kho gần trên `PurchaseRequestFormPage`; quản lý trạng thái theo scope, xóa kết quả khi đầu vào đổi, bỏ qua phản hồi muộn, giữ chọn kho thủ công.
4. Bổ sung test backend/frontend, cập nhật OpenAPI contract, chạy toàn bộ verification và thử bằng tài khoản client trên stack demo cục bộ.

## Progress log (append-only)

- **2026-11-16 — READY:** task authored by explicit user request; dependencies `implement-b2b-purchase-requests` and `implement-warehouse-gis` are `DONE`; plan/scope/acceptance/verification defined above. **Verification:** baseline code and routes inspected; no changes made yet.
- **2026-11-16 — IN_PROGRESS:** baseline frozen; starting read-only endpoint and B2B form integration without touching RAG or replenishment-alert changes. **Verification:** pending.
- **2026-11-16 — IN_PROGRESS (implementation):** added `NearestWarehouseQuery/Read/Response`, `PurchaseRequestRepository.nearest_warehouse_stock`, `PurchaseRequestService.nearest_warehouses` (reusing `app.gis.schemas.distance_mm`), and the static `GET /purchase-requests/nearest-warehouses` route guarded by `purchase_request:create` and registered before `/{request_id}`. Frontend added coordinates + lookup panel, scoped result state, late-response guard, suggestion select, and auto-fill reset. **Verification:** `ruff check` clean; unit + API + form tests, typecheck and build pass.
- **2026-11-16 — IN_PROGRESS -> VERIFYING:** implementation frozen; no further code changes unless a verification or review finding requires returning to `IN_PROGRESS`. **Verification:** full command set below.
- **2026-11-16 — VERIFYING -> IN_PROGRESS:** independent review returned minor findings; re-opening to fix the read-only `FOR SHARE` lock on the product row, the sub-kilometre distance formatting, an unguarded suggestion id, and to close test gaps (axis-swap-sensitive distance assertion, manual warehouse selection preserved, unknown suggestion id). **Verification:** re-run after the fixes.
- **2026-11-16 — IN_PROGRESS -> VERIFYING:** Mã hiện tại đã có truy vấn sản phẩm không khóa dòng, định dạng khoảng cách dưới 1 km đến ba chữ số thập phân, và kiểm tra ID gợi ý với danh sách kho trên form. Không tìm thấy tiến trình pytest của lần bàn giao hoặc log hoàn tất có thể xác nhận. Đã bắt đầu lượt hồi quy mới trên cặp database kiểm thử cô lập tại 18546 bằng môi trường Python 3.14.2 đã nhập thành công XGBoost, scikit-learn, SHAP và osmium.
- **2026-11-16 — VERIFYING -> IN_PROGRESS:** Rà soát độc lập phát hiện hai truy vấn đọc trạng thái sản phẩm và tồn có thể dùng hai snapshot khác nhau, và tìm kho chấp nhận số lượng mà form gửi sẽ từ chối. Ghi nhận thêm trường hợp cùng điểm ở kinh tuyến ±180° có thể xếp sai thứ tự ID. Dừng lượt hồi quy của bản trước để xác minh lại mã sau sửa.
- **2026-11-16 — IN_PROGRESS -> VERIFYING:** Dùng một câu SQL chỉ đọc để kiểm tra sản phẩm đang hoạt động và lấy tồn đủ, cùng một quy tắc kiểm tra số lượng cho tìm và gửi. Chuẩn hóa kinh tuyến ±180° và tính khoảng cách tới cực theo kinh độ tương đương. Kiểm thử PostgreSQL bắt hai truy vấn trước sửa, hai ca đồng vị trí từng sai thứ tự, và kiểm thử form bắt định dạng số lượng chưa hợp lệ. Sau sửa, bộ backend tập trung đạt 156 ca; cả ba ca số lượng đạt. Bắt đầu lại hồi quy đầy đủ trên mã sau review.
- **2026-11-16 — VERIFYING (hoàn tất bộ lệnh):** Hồi quy đầy đủ trên mã sau review đạt 1.750 ca, không lỗi hoặc bỏ qua. Đã đối chiếu đủ chín tiêu chí và bằng chứng demo trước đó. Giữ `VERIFYING` theo bước bàn giao hiện tại.
- **2026-11-16 — VERIFYING -> REVIEWING:** Tiếp nhận bước hoàn thiện dự án. Đối chiếu lại chín tiêu chí, kết quả hồi quy cuối và phản hồi rà soát độc lập về truy vấn nhất quán, kiểm tra số lượng và thứ tự khoảng cách.
- **2026-11-16 — REVIEWING -> DONE:** Chín tiêu chí đạt trong phạm vi B2B. Rà soát lại không có lỗi cần sửa. Kiểm tra diff của cả file đã theo dõi và file mới đạt, index trống.

## Verification evidence

- **Backend unit/contract:** `uv run python -m pytest -q tests/test_purchase_request_nearest.py tests/test_purchase_request_schemas.py` → 80 passed.
- **Backend PostgreSQL scoped:** `tests/postgres/test_purchase_requests_api.py`, `test_purchase_request_atomicity.py`, `test_purchase_request_concurrency.py`, `test_rbac_matrix.py` → 253 passed (includes new nearest-warehouse ranking/tie-break, stock filtering, missing coordinates, inactive/unknown product, 401/403, query bounds/duplicates/unknown fields, and OpenAPI contract 7 paths / 8 operations).
- **Migrations/snapshot:** `tests/postgres/test_purchase_request_migration.py` + `test_transfer_migration.py` → 15 passed; `tests/postgres/test_demand_data_snapshot.py` → 17 passed (guarded test/migration database pair on 127.0.0.1:18546).
- **Lint:** `uv run ruff check app/purchase_requests tests/test_purchase_request_nearest.py tests/postgres/test_purchase_requests_api.py` → All checks passed.
- **Frontend:** `npm.cmd run test -- --run src/features/purchaseRequests/PurchaseRequestFormPage.test.tsx` → 29 passed (8 new nearest-warehouse tests); `npm.cmd run test:all` → vitest suite plus 88 host tests, 0 failures; `npm.cmd run typecheck` → clean; `npm.cmd run build` → success (pre-existing >500 kB chunk-size warning only).
- **Whitespace:** `git diff --check` → exit 0 (only CRLF normalization warnings from pre-existing files).
- **Demo stack (client account):** rebuilt `api`/`web` images, `GET /purchase-requests/nearest-warehouses?product_id=1&quantity=2&latitude=10.78&longitude=106.70` returned `HCM-01` 0.358 km / 25 units then `WH-DEMO-02` 5.776 km / 2 units with `method: great_circle_haversine`; `admin` and `warehouse` got 403, anonymous 401. UI showed the ordered suggestions, "Chọn kho này" filled the warehouse select, and the existing dialog + `POST /purchase-requests` succeeded with HTTP 201 (`PR-512d0bea45cd4743a711099069bd4a73`, `warehouse_id: 1`).
- **Hồi quy đầy đủ:** Lượt OpenCode dùng Python 3.12 chưa có kết quả có thể xác nhận trong phiên này. Lượt thay thế chạy `python -m pytest -q --durations=12` bằng Python 3.14.2, dùng hai database kiểm thử riêng ở 18546 sau khi xác nhận chủ sở hữu, không có phiên khác và migration lên head đạt. Log mới tại `%LOCALAPPDATA%/SmartWarehouse/verification/b2b-nearest-20261116/backend-full.log`.
- **Đối chiếu demo sau bàn giao:** Bốn file backend trong container API trùng SHA-256 với worktree. Container web đang dùng image hiện tại, được dựng sau các thay đổi frontend. Readiness trả `ready`, yêu cầu ẩn danh trả HTTP 401. Truy vấn chỉ đọc xác nhận yêu cầu demo đã lưu ở kho 1 với số lượng 2, trạng thái `pending`, và tồn tương ứng là 25 ở `HCM-01` và 2 ở `WH-DEMO-02`. Không tạo thêm yêu cầu hoặc thay đổi tồn khi đối chiếu.
- **Frontend sau bàn giao:** `npm.cmd run test:all` đạt 480 Vitest trên 50 file và 88 host test, không lỗi hoặc bỏ qua. `npm.cmd run typecheck`, `npm.cmd run build`, Ruff cho phạm vi B2B và `git diff --check` đều đạt. Vite báo chunk lớn hơn 500 kB. Bản ghi test ở `%LOCALAPPDATA%/SmartWarehouse/verification/b2b-nearest-20261116/frontend-tests.log`.
- **Mã sau review:** 156 test backend tập trung gồm PostgreSQL và schema, 483 Vitest trên 50 file, 88 host test, typecheck, build, Ruff và kiểm tra khoảng trắng đạt. Các báo cáo liệt kê tại thư mục bằng chứng bên ngoài repo. Frontend vẫn báo chunk lớn hơn 500 kB.
- **Demo sau review:** Dựng lại API và web của `sw-alerts-demo` nhưng giữ database và dữ liệu demo. Bốn module API trùng SHA-256 với mã mới, readiness trả `ready`, đường dẫn `/purchase-requests/new` trả HTTP 200 với bundle mới và request ẩn danh vẫn 401. Luồng trình duyệt có tài khoản client và yêu cầu HTTP 201 là từ lần bàn giao trước các sửa đổi sau review.
- **Hồi quy đầy đủ trên mã sau review:** `python -m pytest -q --durations=12` thoát 0, 1.750 ca đạt trong 17 phút 58 giây, hai cảnh báo deprecation từ Starlette TestClient và pytest-asyncio, không lỗi hoặc bỏ qua. Log `%LOCALAPPDATA%/SmartWarehouse/verification/b2b-nearest-20261116/backend-full-after-review.log`.

## Review Result

- Result: APPROVED
- Findings: Rà soát kỹ thuật độc lập sau sửa xác nhận cả ba phát hiện đã được xử lý và không có lỗi mới cần sửa.

## Completion Evidence

- Status: DONE, hoàn tất 2026-11-16. Đạt 9/9 tiêu chí. Hồi quy 1.750 test backend, 483 Vitest và 88 host test đạt. Typecheck, build, Ruff, kiểm tra diff và review độc lập đạt.
- Demo: Bằng chứng tài khoản client và HTTP 201 được ghi ở lượt trước sửa. Lượt cuối đã dựng lại bản sửa, kiểm tra API sẵn sàng, URL trang trả 200 và request ẩn danh 401. Chưa lặp lại thao tác gửi có đăng nhập trên bản dựng cuối.
- Commit: not required by task scope. Chưa stage, commit, push hoặc deploy lên Render.
- Quay video trên `http://127.0.0.1:58080/purchase-requests/new` bằng tài khoản client của stack demo. Chọn `DEMO-001`, số lượng 2, vĩ độ 10.78 và kinh độ 106.70. Bấm tìm, chọn `HCM-01` rồi xem lại yêu cầu. Yêu cầu demo đã kiểm chứng vẫn ở trạng thái `pending`.
