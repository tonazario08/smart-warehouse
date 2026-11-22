# Plan: polish-frontend-navigation-and-status
- Giao diện bản thử được Toàn duyệt 23/11 (VN); giữ nguyên quyền và dữ liệu.
- Dùng danh sách quyền đã có cho menu thật, có nhóm dễ đọc và nút có nhãn trên màn hình nhỏ; liên kết Sản phẩm hiện với thủ kho đúng quyền. Nút bỏ qua điều hướng, focus rõ, breadcrumb dễ đọc, bỏ chức năng tìm kiếm/thông báo giả dạng nút.
- Tách không xác thực với không đủ quyền: còn chuyển tới đăng nhập nếu không có phiên, khi bị từ chối hiện giải thích và đường về đúng vai trò; không mount trang bị cấm và giữ các guard lồng nhau. Không đổi chính sách.
- Giữ API dashboard, không hiển thị tổng số lượng trộn đơn vị; ghi tồn thấp theo ngưỡng danh mục. Phân biệt kịch bản với vận hành/nghiên cứu trong Dự báo, không suy ra độ mới vận hành cho fixture.
- Chuẩn hóa các tiêu đề, khoảng cách, focus và nhãn trạng thái của shell cùng màn mục tiêu. Không sửa luồng Bất thường/B2B/GIS. RED/GREEN, desktop và mobile Chromium độc lập theo ba vai trò, không ghi dữ liệu nghiệp vụ.
