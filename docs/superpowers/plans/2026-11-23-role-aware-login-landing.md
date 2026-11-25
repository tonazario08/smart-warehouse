# Plan: fix-role-aware-login-landing
Toàn duyệt đúng task, 23/11 VN. Sau đăng nhập mặc định, dùng `/` để RoleHome hiện có chọn Bảng điều khiển cho admin, Tồn kho cho thủ kho, Sản phẩm cho khách. Giữ logic lấy đích nội bộ explicit `from`, guard và thông báo thật từ các đích trái quyền, không mount trang trái quyền hoặc thay đổi chính sách quyền.
- RED: hosted ca auth-client báo 1 alert thay vì 0 tại bước tải lại sau đăng nhập thông thường.
- GREEN: kiểm thử qua entrypoint đăng nhập thật 3 vai trò thông thường không sinh alert, đích hợp lệ giữ nguyên, khách truy cập trực tiếp Dashboard trước đăng nhập nhận đúng thông báo sau đăng nhập. Không bỏ assertion cũ, giữ 53 ca/9 tệp.
- Static/full frontend và Chromium Windows cô lập. Hosted CI là gate phát hành riêng, không tích hợp main/chạy dữ liệu thật trong task.
