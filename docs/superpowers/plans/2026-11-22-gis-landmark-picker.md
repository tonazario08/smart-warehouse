# Kế hoạch add-gis-landmark-picker

Task: docs/tasks/add-gis-landmark-picker.md. APPROVED cho bản sao cô lập. Chỉ mở phạm vi đã nêu ở task, không thêm dịch vụ ngoài.

1. RED trước sửa. Trong nhánh Tọa độ của GIS staff, thêm tìm theo tên. Dữ liệu tĩnh nhỏ (tối đa 30 địa danh) có ID, tên chuẩn, alias, tọa độ WGS84, URL nguồn công cộng và ghi công giấy phép phù hợp; chỉ nhập điểm được đối chiếu độc lập và trong vùng snapshot. Nếu không có chứng cứ, bỏ điểm khỏi danh sách. Không dùng tên từ đường không có metadata.
2. Chuẩn hóa Unicode tiếng Việt cho tìm kiếm nội bộ, gợi ý hữu hạn, hỗ trợ bàn phím và tập dữ liệu không khớp. Chỉ chọn gợi ý mới đặt hai tọa độ và marker/tên, chưa gửi POST. Đổi tọa độ, xóa hoặc đổi mode trả trạng thái đúng; dùng abort/scoping cũ, bỏ kết quả cũ.
3. Dùng mã và tên kho sẵn có cho label SVG, né chồng chữ bằng giới hạn hiển thị và tooltip truy cập được; không đổi stock/route semantics, legend, giải thích Google Maps hay A*. Không vẽ danh sách địa danh công cộng khi chỉ có sơ đồ mô phỏng hoặc snapshot sai/rỗng.
4. Verify: Unit tests tìm có/không dấu, select/cancel/clear và point bounds, permission/client guard, no request while typing/selecting, explicit search. Desktop/mobile trên test runtime riêng; dùng đúng catalog OSM đã duyệt, bật no external traffic. Không broadcast hay duyệt model.
