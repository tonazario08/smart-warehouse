# Plan: align-analytics-ui-release-e2e
Toàn duyệt 23/11 VN. Chỉ căn chỉnh assertion/selector E2E hiện hữu đã lệch sau khi đổi giao diện.
- Chọn Sản phẩm trong vùng nguồn theo ngữ nghĩa; không phụ thuộc chuỗi ghép cũ.
- Logout trên mobile mở menu thật rồi đến menu tài khoản; desktop không cần thêm bước.
- Dự báo kiểm tra nhãn fixture, không gắn freshness vận hành, và xác minh đường dẫn/mã đầy đủ qua ngữ nghĩa link rút gọn.
- Giữ mọi ca và matrix 53/9, giữ hành vi kiểm tra và các fixture/guard. Không sửa code sản phẩm, API, database, cấu hình CI, mức bảo vệ hay dữ liệu.
- Tái hiện đỏ trên bản cũ, xác minh xanh trên Windows cô lập với artifact tổng hợp đã xác minh. Chỉ sau gate local mới chuẩn bị release, còn CI hậu push độc lập.
