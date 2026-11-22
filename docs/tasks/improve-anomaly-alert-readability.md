# improve-anomaly-alert-readability — Làm dễ hiểu trang chi tiết cảnh báo bất thường

> Kế hoạch đã duyệt, chỉ triển khai UI trên bản sao demo cô lập.

## Metadata

- Status: VERIFYING
- Phase: M9 (trải nghiệm đọc cảnh báo)
- Plan: `docs/superpowers/plans/2026-11-22-anomaly-alert-readability.md` (đã duyệt)
- Depends on: `docs/tasks/implement-anomaly-explanations.md`
- Created: 2026-11-22
- Started: 2026-11-22
- Completed: not completed

## Goal

Người quản lý kho đọc nhanh vì sao mô hình gắn cờ, hiểu số liệu theo đơn vị dễ đọc và biết nên kiểm tra gì tiếp theo, mà không nhầm cảnh báo với kết luận giao dịch sai hay kết quả dự báo.

## Context

Trang Chi tiết Bất thường hiện có điểm, ngưỡng, đặc trưng đã biến đổi, SHAP, phiên bản và lịch sử đánh giá. API không cung cấp liên kết đã xác minh đến phiếu xuất, đơn vị thực của phiếu hay tên người xuất. Nguồn hiện tại là dữ liệu tổng hợp; đề cương V2 mục 2.9 và 3.5 tách giải thích mô hình khỏi xác nhận nguyên nhân nghiệp vụ.

## In Scope

> Đợt này chỉ cải thiện cách trình bày bằng dữ liệu hiện có, không thay đổi thuật toán, ngưỡng hoặc kết quả chấm điểm. Việc liên kết và mở đúng phiếu xuất được tách thành task riêng, bao gồm lưu liên kết, xác minh giao dịch và kiểm tra quyền truy cập.

- Chỉ trang chi tiết Bất thường: tóm tắt theo SHAP đã kiểm tra; gợi ý công việc đối chiếu; diễn giải điểm, ngưỡng, dấu đóng góp, thời gian và dữ liệu đối chiếu.
- Hiển thị giờ giao dịch, thứ trong tuần và số lượng thực tế theo dạng dễ đọc. Với dữ liệu tổng hợp chưa đối chiếu được phiếu, ghi rõ đó là số lượng ghi trong dữ liệu mẫu. Thu gọn phần kỹ thuật mặc định và cho sao chép mã đầy đủ. Giữ luồng ràng buộc quyền và lịch sử đánh giá hiện có.

## Out of Scope

- Không đổi API, schema, mô hình, ngưỡng, provenance, stock, phiếu xuất, quyền hay cách lưu đánh giá; không thay trang danh sách, Dự báo hoặc Bổ sung hàng.
- Link mở phiếu xuất, sản phẩm/kho của phiếu và tên người thực hiện chỉ làm trong task riêng có liên kết nguồn đã được xác minh. Không đoán phiếu theo giờ/lượng/mã mờ hoặc thêm chức năng sửa/hủy phiếu. Task liên kết phải phân biệt “Chưa liên kết được phiếu xuất đối chiếu” với “Bạn không có quyền xem phiếu xuất” khi được phép thông báo trạng thái quyền; không tiết lộ chi tiết phiếu cho người không có quyền.

## Acceptance Criteria

- [ ] AC-1 — Tóm tắt nêu yếu tố làm tăng điểm nhiều nhất nếu SHAP hợp lệ. Thông tin và gợi ý kiểm tra tách bạch; thiếu SHAP, không có đóng góp dương hoặc dữ liệu sai thì không tạo lý do giả. Giữ nhãn dữ liệu tổng hợp và lưu ý không chứng minh nguyên nhân.
- [ ] AC-2 — Nêu điểm phải lớn hơn ngưỡng mới gắn cờ, không phải xác suất. Không so sánh số đã làm tròn; khi bằng ngưỡng hoặc không nhất quán, không hiện kết luận “vượt ngưỡng”.
- [ ] AC-3 — Đặc trưng đúng phiên bản được diễn giải có kiểm tra. Mốc giờ/thứ giao dịch ghi rõ múi giờ (giờ Việt Nam nếu dùng UTC+07:00). Ghi rõ lịch sử gồm bảy ngày lịch UTC trước ngày xuất, không bao gồm ngày giao dịch theo UTC. Hiện “Không đủ dữ liệu lịch sử” nếu thiếu dữ liệu lịch sử; số 0 chỉ hiển thị khi đủ dữ liệu và thực sự bằng 0; không bịa đơn vị, không gán số đặc trưng thành thông tin phiếu xuất.
- [ ] AC-4 — Biểu đồ có chú thích hai dấu, ý nghĩa đóng góp không phải phần trăm lượng hàng. Phần kỹ thuật thu gọn mặc định và dùng được bằng bàn phím; mã dài hiển thị gọn và sao chép đúng mã đầy đủ, chỉ báo thành công khi sao chép được.
- [ ] AC-5 — Quyền, thao tác đánh giá và lịch sử người đánh giá (ID hiện có), thời gian, lý do giữ nguyên. Kiểm thử lỗi, đổi phiên/role, review, ranh giới UTC và bảo toàn biệt lập với dự báo.

## Verification Commands

### Focused

Trong `client/`: `npm exec -- vitest run src/features/anomalies/AnomalyDetailPage.test.tsx src/features/anomalies/AnomaliesPage.test.tsx`.

### Regression

Trong `client/`: `npm run test:all`, `npm run typecheck`, `npm run build`. Smoke trang chi tiết bằng demo fixture trên desktop/mobile và xác nhận tương tác bàn phím; không mở cổng fixture trên môi trường vận hành.

### Static and Diff

`git diff --check`; kiểm allowlist và không có thay đổi backend, schema, môi trường hoặc nguồn dữ liệu.

## Progress Log

- 2026-11-22 — Cập nhật DRAFT theo góp ý về cách diễn đạt và đối chiếu mã nguồn về ngưỡng và cửa sổ lịch sử. Chưa vào repo hoặc triển khai.

- 2026-11-22 — Người dùng chọn task này và yêu cầu triển khai trên demo. Đối chiếu task/plan đã duyệt, dependency M9 DONE, rule AGENTS, scope và hợp đồng feature API trên bản sao cloud tách biệt (301260fb + các bản vá demo). DRAFT → READY → IN_PROGRESS; khóa phạm vi UI-only, không sửa backend hoặc dữ liệu.

- 2026-11-22 — Xác nhận hash của ba file UI khớp checkout Windows demo; hai file task/plan chưa có ở đó. RED: hai test về tóm tắt/múi giờ và điểm bằng ngưỡng thất bại trên UI cũ. Thực hiện UI và test trong bản sao cloud, không sửa danh sách/API/model/quyền. IN_PROGRESS → VERIFYING.

## Verification Evidence

### Đối chiếu mã nguồn (chưa nghiệm thu UI)

- `app/anomalies/catalog.py` công bố cảnh báo khi `score > result.threshold`: điểm bằng ngưỡng không được gắn cờ.
- `app/anomalies/features.py` dùng `occurred_at.astimezone(UTC).date()` và các độ lệch từ 1 đến 7 ngày, không bao gồm ngày giao dịch theo UTC.
- Đã xác minh hai quy tắc trên bằng đọc mã ở bản sao phát triển hiện có. Cách trình bày, sai khác do làm tròn, ranh giới UTC/giờ Việt Nam và trạng thái lịch sử vẫn phải kiểm thử khi triển khai.

### Focused

32 test đạt ở nhóm AnomalyDetailPage và AnomaliesPage: điểm bằng ngưỡng và sai khác dưới mức làm tròn, decode đặc trưng, UTC/Việt Nam, lịch sử 0/thiếu, SHAP không nhất quán hoặc thiếu yếu tố dương, sao chép đúng mã/thất bại, đổi phiên và lịch sử đánh giá. Không coi JSDOM là bằng chứng thao tác bàn phím trong trình duyệt.

### Regression

`npm run typecheck`, `npm run build`, 511 Vitest và 88 Node host tests đạt. Smoke demo desktop/mobile và bàn phím trên trình duyệt Windows: chưa chạy trong môi trường cloud.

### Static and Diff

`git diff --check` và `git apply --check` trên baseline phù hợp đạt. Patch chỉ gồm ba file UI/test/CSS có sẵn, một helper UI mới và task/plan đã chọn; không sửa API, schema, quyền, dữ liệu hoặc màn danh sách.

## Review Result

- Result: Đọc chéo độc lập không thấy lỗi trọng yếu. Task vẫn VERIFYING, chưa xác minh smoke trình duyệt demo.
- Findings: Đã đối chiếu quy tắc giờ/thứ và lịch sử UTC, ngưỡng nghiêm ngặt, hợp đồng feature/SHAP, thiếu dữ liệu và giữ nguyên API/quyền.

## Completion Evidence

Chưa có.
