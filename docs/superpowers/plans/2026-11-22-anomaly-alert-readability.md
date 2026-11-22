# Plan DRAFT — Làm dễ hiểu trang Chi tiết Bất thường

- Task identifier: `improve-anomaly-alert-readability`
- Task: `docs/tasks/improve-anomaly-alert-readability.md`
- Đường dẫn dự kiến của plan: `docs/superpowers/plans/2026-11-22-anomaly-alert-readability.md`
- Cơ sở: spec/kế hoạch M9 được dẫn trong `docs/tasks/implement-anomaly-explanations.md`; đề cương V2 mục 2.9 và 3.5.
- Trạng thái: DRAFT, chưa xác minh checkout đích hoặc duyệt triển khai.

> Đợt này chỉ cải thiện cách trình bày bằng dữ liệu hiện có, không thay đổi thuật toán, ngưỡng hoặc kết quả chấm điểm. Việc liên kết và mở đúng phiếu xuất được tách thành task riêng, bao gồm lưu liên kết, xác minh giao dịch và kiểm tra quyền truy cập.

## 1. Thứ tự người kho đọc

1. **Vì sao có cảnh báo?** Điểm, ngưỡng và khoảng chênh nếu dữ liệu hợp lệ. Văn bản: “Điểm cao hơn ngưỡng thì mô hình gắn cờ. Đây không phải xác suất giao dịch sai.” Chỉ mô tả yếu tố có đóng góp dương lớn nhất khi vector và score hợp lệ; tránh suy đoán nhãn “lượng tăng bất thường” từ dấu của SHAP. Nếu không có giải thích đáng tin, nói rõ và chỉ dẫn kiểm tra chung.
2. **Nên kiểm tra gì?** Ví dụ: “Đối chiếu số lượng ghi nhận với chứng từ xuất và đơn vị tính”, “Nếu thời điểm lạ, kiểm tra giờ xuất hoặc giờ ghi nhận”. Đây là việc gợi ý, không phải kết luận. Phân biệt: “Cảnh báo xem lại giao dịch đã ghi nhận; dự báo ước tính nhu cầu tương lai.”
3. **Số liệu đối chiếu + biểu đồ.** Hiển thị giờ giao dịch, thứ trong tuần và số lượng thực tế theo dạng dễ đọc; nếu đang dùng dữ liệu tổng hợp, ghi rõ số lượng ghi trong dữ liệu mẫu, chưa phải số trên phiếu đã xác minh. Giữ ký hiệu +/− bên cạnh màu để không phụ thuộc màu. Nhãn “Làm giảm mức bất thường”/“Làm tăng mức bất thường”. Chú thích “Đóng góp vào điểm của mô hình, không phải phần trăm thay đổi lượng hàng hay bằng chứng nguyên nhân.” Giữ nhãn dữ liệu tổng hợp rõ ràng.
4. **Đánh giá** dùng dữ liệu/luồng hiện hữu: quyết định, ID người đánh giá, thời gian và lý do; giải thích khác với người xuất kho. **Thông tin kỹ thuật** thu gọn mặc định: mã nguồn mờ, mã run/alert, phiên bản, phân đoạn, feature thô, giá trị nền và sai số. Mã rút gọn kèm nút sao chép giá trị gốc, có thông báo thành công/thất bại đọc được bằng công nghệ hỗ trợ.

## 2. Hợp đồng diễn giải

- Áp dụng đúng `anomaly-features/1`, với đủ sáu khóa hợp lệ, mỗi khóa một lần, giá trị hữu hạn và đúng miền. Không đổi hoặc sắp lại vector tách khỏi tên. Dữ liệu không rõ phiên bản/không hợp lệ hiển thị “Không đủ dữ liệu để diễn giải”; không bù 0. Giữ kiểm tra nhất quán của SHAP, không thay dữ liệu backend; chỉ tạo câu giải thích khi điểm, giá trị nền, đóng góp và sai số phù hợp.
- Lấy `Math.expm1` cho lượng giao dịch, lượng xuất trung bình/ngày và số giao dịch. Kiểm tra giá trị giải mã hữu hạn, không âm, hợp lý; lượng/số giao dịch nguyên có sai số số học cho phép nhưng không làm tròn để che dữ liệu sai. Chỉ gọi “lượng ghi trong dữ liệu mẫu”; không tự thêm “cái/kg” nếu không có đơn vị từ API, không gọi đây là số trên phiếu thật. Tỷ lệ kỹ thuật = lượng giao dịch / (1 + trung bình ngày); không ghi “gấp X lần trung bình”, đặc biệt khi mẫu số lịch sử là 0.
- Thời điểm giao dịch hiển thị kèm nhãn múi giờ, ví dụ “Giờ Việt Nam (UTC+07:00)”; phần lịch sử và giờ/thứ mô hình ghi nhãn “UTC”. Giờ/thứ **mô hình** tính từ UTC (`hour/23`; thứ Hai=0, Chủ nhật=6 rồi chia 6), không nhầm với giờ Việt Nam. Đối chiếu thời điểm và đặc trưng giờ/thứ; nếu lệch/không hợp lệ thì không diễn giải trường tương ứng. Lịch sử là **bảy ngày UTC trọn vẹn** trước ngày xuất, cùng sản phẩm/kho/đơn vị, chỉ các lần xuất hợp lệ đã biết ở thời điểm dữ liệu giao dịch khả dụng; không bao gồm ngày giao dịch theo UTC. Thiếu phần lịch sử hợp lệ thì hiển thị “Không đủ dữ liệu lịch sử”, không thay bằng 0; số 0 chỉ dùng khi đủ dữ liệu và thực sự bằng 0. Lượng trung bình là tổng lượng chia 7, không chia số lần xuất. Số giao dịch là tổng cả kỳ.
- So sánh điểm và ngưỡng gốc rồi định dạng. Nếu số khác nhau nhưng hiển thị tròn trùng nhau, hiển thị chênh lệch hoặc tăng độ chính xác để người dùng không hiểu nhầm. Nếu điểm bằng/thấp hơn ngưỡng trong một alert, trình bày dữ liệu không nhất quán, không hiển thị kết luận gắn cờ. Không hỏi catalog khác hoặc suy ra bản ghi phiếu.
- Người xuất/kho/SKU, mã phiếu truy cập được và phiên bản/hủy phiếu để task khác có provenance xác thực; không dùng bất kỳ mã nguồn mờ nào làm đường dẫn phiếu. Không tạo backend fallback. Trong task liên kết sau này, dùng “Chưa liên kết được phiếu xuất đối chiếu” khi thiếu liên kết đã xác minh; nếu liên kết đã được xác minh nhưng người xem không có quyền thì thông báo quyền riêng, không để lộ chi tiết phiếu.

## 3. Thực hiện và xác minh

Đã kiểm tra bằng mã nguồn: nhánh công bố trong `app/anomalies/catalog.py` chỉ tạo cảnh báo nếu `score > result.threshold`; `app/anomalies/features.py` chọn ngày giao dịch theo UTC và lấy các ngày lùi từ 1 đến 7. Đây là hành vi hiện tại của phần chấm điểm, không phải bằng chứng giao diện mới đã kiểm thử.

Allowlist dự kiến: `client/src/features/anomalies/AnomalyDetailPage.tsx`, CSS của tính năng, file test và helper thuần phục vụ trang chi tiết nếu cần. Không thay đổi route, API, permission, mô hình phiên bản hoặc màn danh sách. Bắt đầu với test RED rồi mới sửa.

| Tình huống | Kỳ vọng |
| --- | --- |
| Điểm bằng ngưỡng; chênh rất nhỏ | Bằng không tạo câu “vượt ngưỡng”; chênh dương vẫn so sánh từ số gốc và có cách hiển thị phân biệt. |
| SHAP có +/−/0; thiếu, sai residual hoặc feature lạ | Giải thích nhất quán, không gán nguyên nhân; nếu lỗi không tự tạo lý do. |
| UTC 23:00 thứ Sáu → Việt Nam 06:00 thứ Bảy; fixture 21 lượng/7 ngày, 2 lần xuất, đích 12 | Phân biệt giờ UTC mô hình và giờ hiển thị; trung bình 3/ngày, số lần 2; tỷ lệ kỹ thuật 12/(1+3)=3 nếu hiện. |
| Bảy ngày có 0 thật; thiếu trường, sai phiên bản hoặc xem mã hóa như giờ địa phương | Hiện 0 hợp lệ khác trạng thái “Không đủ dữ liệu lịch sử”. Không giải mã nhầm, không chia 0, không tự gán đơn vị. |
| Sao chép thành công, trình duyệt từ chối; bàn phím/mobile; retry, stale login, người không có quyền | Copy chính xác chuỗi đầy đủ; báo lỗi đúng; không lộ dữ liệu phiên cũ. Hành vi đánh giá, lịch sử và lỗi xung đột giữ nguyên. |

Chạy lệnh trong task, ghi rõ smoke trình duyệt đã chạy hay chưa. Trước READY, xác minh đúng checkout/baseline, dependency M9 DONE, duyệt plan độc lập và chốt không liên kết phiếu. Không sửa task đang chạy, không sửa data thật.
