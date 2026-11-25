# link-anomaly-alert-to-outbound — Mở đúng phiếu xuất từ cảnh báo bất thường

> Đã duyệt triển khai trên bản sao cloud; chỉ DB demo mới trong phạm vi.

## Metadata

- Status: VERIFYING
- Phase: M9 (truy vết cảnh báo demo)
- Plan: `docs/superpowers/plans/2026-11-22-anomaly-outbound-link.md` (đã duyệt)
- Depends on: `docs/tasks/implement-b2b-purchase-requests.md`, `docs/tasks/build-demand-data-pipeline.md`, `docs/tasks/implement-anomaly-explanations.md`
- Created: 2026-11-22
- Started: 2026-11-22
- Completed: not completed

## Goal

Người kho bấm **Mở phiếu xuất** từ một cảnh báo demo B2B và xem đúng giao dịch đã thực xuất. Nếu không xác minh được liên kết, hiển thị rõ thay vì mở một phiếu gần giống.

## Context

M5 xác minh chuỗi yêu cầu B2B đã xuất, phiếu xuất và giao dịch tồn; runner demo hiện kiểm được liên kết trong bộ nhớ rồi bỏ, không lưu để giao diện truy cập. Catalog M9 chỉ có mã bản ghi mờ; endpoint chi tiết phiếu có sẵn, nhưng không chứng minh cảnh báo liên kết với phiếu nào. Ca demo kỹ thuật đang nói tới **phiếu xuất #451**, lượng 10.000 `each`; đây là ca nghiệm thu của dữ liệu mẫu hiện tại, không dùng số 451 làm khóa tìm mặc định hoặc giả định các bản seed mới có cùng ID.

## In Scope

- Lưu liên kết riêng, bất biến giữa cảnh báo demo và phiếu/giao dịch đã được xác minh từ cùng bundle M5, catalog M9 và DB demo cô lập. Dùng migration cộng thêm sau head đã xác minh; nhập lại đúng bằng chứng không tạo trùng.
- Chỉ đọc. Nút và trang đích hiển thị mã phiếu, SKU/tên sản phẩm, kho, số lượng/đơn vị, thời điểm và người thực xuất theo dữ liệu đã xác minh; phân biệt người thực xuất với người đánh giá. Mở qua đường dẫn theo mã cảnh báo, không dùng khóa nhập từ trình duyệt để đoán phiếu.
- Duy trì trạng thái “Chưa liên kết được phiếu xuất đối chiếu” cho fixture thường, thiếu/hỏng bằng chứng hoặc phiếu không còn khớp. Người không có quyền không nhận thông tin về sự tồn tại hoặc nội dung phiếu.

## Out of Scope

- Không đổi điểm, ngưỡng, SHAP, quy trình đánh giá, dự báo, bổ sung hàng hoặc kiểm tra B2B tạm tính.
- Không tạo, sửa, xóa hoặc hủy phiếu xuất từ Bất thường; không sửa tồn, đơn, giao dịch hay dữ liệu thực. Không mở quyền mới, không hỗ trợ liên kết kho production hoặc công khai ID nguồn, email, ghi chú khách và các trường riêng tư trong catalog.

## Acceptance Criteria

- [ ] AC-1 — Ca #451 trên đúng snapshot demo, nếu đủ chứng cứ gốc, mở đúng phiếu/transaction qua nút, hiển thị 10.000 `each` và người thực xuất đã xác minh. Fixture mới có thể sinh ID khác; bộ kiểm thử xác nhận đúng giao dịch đích và nêu ID tìm thấy. Hai giao dịch cùng SKU/kho/lượng/thời điểm vẫn không ghép nhầm.
- [ ] AC-2 — Fixture chung vẫn xem cảnh báo như trước nhưng không có nút mở phiếu. Sai DB, bundle/catalog/digest, key, transaction, mapping hoặc provenance đều không tạo liên kết. Phiếu không còn khớp sau khi nhập thì liên kết không dùng được; không sửa phiếu để “khớp lại”.
- [ ] AC-3 — API/trang đích yêu cầu cả `anomaly:read` và `inventory:history:read`; admin/thủ kho có quyền xem, client không truy cập được kể cả mở trực tiếp; quyền được kiểm trước lookup nguồn. Phản hồi dành cho người không có quyền không phân biệt có/không có phiếu.
- [ ] AC-4 — Import hoặc backfill được xác minh ghi atomically, cùng bằng chứng replay không trùng, khác bằng chứng bị từ chối chứ không ghi đè. Trước/sau khi liên kết hoặc mở, đơn, tồn, phiếu, giao dịch, các cột chấm điểm/SHAP và hồ sơ review không đổi. Không nới gate fixture.
- [ ] AC-5 — Migration upgrade/downgrade trên PostgreSQL riêng có bằng chứng giữ nguyên bảng và dữ liệu gốc. Browser demo desktop/mobile xác nhận nút mở chi tiết chỉ đọc; link stale và báo quyền đúng; Bất thường UI hiện có vẫn chạy.

## Verification Commands

### Focused

- Đề xuất, chưa tồn tại: `python -m pytest -q tests/postgres/test_anomaly_outbound_link.py tests/postgres/test_anomaly_outbound_link_migration.py`.
- Trong `client/`: `npm exec -- vitest run src/features/anomalies/AnomalyDetailPage.test.tsx` và test trang phiếu theo tên đã chốt khi triển khai.

### Regression

- `python -m pytest -q` trên PostgreSQL test/setup được repo duyệt; migration test DB riêng. Ghi rõ điều kiện Docker/Windows nếu có.
- Trong `client/`: `npm run typecheck`, `npm run build`, `npm run test:all`; smoke trên demo cô lập, không động bản chính.

### Static and Diff

- `python -m ruff check app tests alembic`, `git diff --check`; kiểm allowlist, không trộn thay đổi của task trước.

## Progress Log

- 2026-11-22 — Soạn bản DRAFT. Chưa xác minh đầy đủ bằng chứng nguồn của demo hiện tại và chưa triển khai.

- 2026-11-22 — Người dùng duyệt task đã chọn/plan độc lập; cả ba dependency M4/M5/M9 DONE và spec M9 tồn tại. Xác nhận không còn implementation đồng thời; tài liệu task trước giữ nguyên. Baseline 301260fb + vá demo/UX; head mã nguồn dự kiến 0008. Dùng PostgreSQL 16 thử/migration riêng sẵn có và demo synthetic mới; không backfill #451 đang chạy khi thiếu chứng cứ gốc. Chốt guard DB demo mới bằng UUID riêng (ngoài DB) khớp snapshot M5 và hàng liên kết. DRAFT → READY → IN_PROGRESS.

- 2026-11-22 — RED xác nhận thiếu bridge và trang phiếu. Hoàn thành link demo mới, migration 0009, UI chỉ đọc, kiểm thử và hướng dẫn chạy. Không backfill #451 đang dùng. IN_PROGRESS → VERIFYING.

## Verification Evidence

### Focused

- 30 tests PostgreSQL/API đạt (một cảnh báo deprecation TestClient): phiếu đích đòi đúng transaction có mã khác mã phiếu; có decoy trùng số và decoy trùng kho/SKU/lượng/thời điểm. Wrong UUID/reference, mất provenance, link drift và xung đột bị từ chối; generic fixture và quyền cũ giữ nguyên. Migration upgrade/downgrade và head 0009 được kiểm trên DB migration riêng, không đổi alert cũ.
- 36 test UI trọng tâm đạt trong nhóm detail/link/router. Runner demo mới đã chạy với DB test riêng và dữ liệu tổng hợp: 1.200 sự kiện, điểm đích 0,7709 > ngưỡng 0,5921, đối chứng 0,5509; giải thích SHAP giữ nguyên. Không chạy mục #451 trên môi trường cũ.

### Regression

- Frontend typecheck, build, 520 Vitest và 88 host tests đều đạt. Backend toàn bộ Linux (loại 3 ca chỉ Windows như CI): đang chạy. Smoke thực trên trình duyệt demo Windows desktop/mobile: NOT VERIFIED tại thời điểm đóng gói cloud.

### Static and Diff

- Ruff, git diff --check và git apply --check --whitespace=error-all trên baseline đã vá UX đạt; kiểm round-trip tất cả file. Không đổi mô hình/điểm/catalog công khai hoặc quy trình xuất/tồn.

## Review Result

- Result: Đã đọc chéo phần provenance/quyền, chưa nghiệm thu browser.
- Findings: Nội dung trang phiếu ghi rõ dữ liệu tổng hợp; lấy mã yêu cầu từ response fulfill đã commit trước khi fit, giữ UUID riêng và fingerprint riêng; không giả định phiếu có cùng mã với giao dịch.

## Completion Evidence

Chưa có.
