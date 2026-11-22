# Plan: polish-replenishment-comparison-display
Chỉ trình bày UI tại bản thử, được Toàn duyệt 2026-11-23 (VN).
1. Dùng ID rút gọn và cơ chế sao chép nguyên văn đã có ở Dự báo; tách tên/mã sản phẩm và kho, bỏ lặp trong mỗi trường.
2. Đặt ví dụ local 13/14/15 ngay dưới kết quả gốc, trước phần giải thích; không đổi lựa chọn gốc hoặc gửi API.
3. Ghi ba đầu vào tồn hiện tại/chờ giao/tồn dự kiến một lần. Giữ hai phép đối chiếu demo riêng: tồn hiện tại và tồn dự kiến; báo thiếu tồn một lần, không kết luận khi thiếu/xung đột dữ liệu. Giữ nguồn/đơn vị/ngày/role/validity và EOQ, phân biệt số 0 với thiếu số, không thay endpoint hay ngữ nghĩa.
4. Mô tả Điểm đặt hàng là min/max ROP qua các ngày mô phỏng: bằng nhau ghi một số; khác ghi thấp nhất/cao nhất, giữ độ chính xác đủ phân biệt.
5. RED→GREEN focused, typecheck/build/test:all, độc lập Windows cô lập. Kiểm tra trường hợp có dữ liệu và thiếu bằng trình duyệt; nếu cần mô phỏng response cục bộ, ghi rõ, không thay artifact hoặc dữ liệu.
