# Plan: polish-anomaly-score-display
Toàn duyệt đúng task, 23/11 (VN); chỉ UI trong bản thử cô lập.
- Dùng quan hệ từ điểm và ngưỡng thô, không từ số đã làm tròn. Hiện dưới/bằng/vượt đúng; tăng chữ số (fallback đủ chính xác) nếu hai biểu diễn gần nhau bị trùng. Giữ kiểm tra finite/threshold/đủ dữ liệu và ý nghĩa strict >. Không trình bày số tự suy diễn khi không có dữ liệu xác minh.
- Trật tự nghiệp vụ trước: lý do được phép diễn giải, việc cần đối chiếu, và Mở phiếu xuất nếu liên kết xác minh theo quyền/sẵn có; không gán nguyên nhân, không khiếu nại/writes tự động, không nhìn điểm như lỗi đã xác nhận.
- Thu gọn phần kỹ thuật và giữ khả năng mở/xem dữ liệu dùng đối chiếu hiện có. Không trộn demo với vận hành, không đổi chứng từ hoặc hành vi đánh giá.
- RED/GREEN focused cases, cập nhật các test hiển thị cần thiết, static và full frontend; Windows Chromium độc lập trên bản thử. Ghi rõ case nào thật từ API bản thử và case nào mô phỏng response.
