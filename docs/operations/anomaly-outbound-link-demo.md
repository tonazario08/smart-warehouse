# Demo cô lập: Mở phiếu xuất từ cảnh báo Bất thường

Chỉ chạy trên bản sao checkout và PostgreSQL demo **mới**. Bản đang chạy cổng 15881 và dữ liệu của nó không cần thay đổi. Không có công cụ gắn lại #451 nếu thiếu bằng chứng gốc. Runner không nhận mã phiếu nhập tay và không thay đổi điểm, ngưỡng hoặc SHAP.

## Chạy bản riêng trên Windows (PowerShell)

Dùng hướng dẫn [demo B2B ngoại tuyến](b2b-outbound-anomaly-demo.md) nhưng tạo container **tên mới**, ví dụ `sw-b2b-outbound-link-proof`, và dùng cổng PostgreSQL cục bộ chưa dùng, ví dụ 18550. **Không** kết nối với DB đang chạy. Tên database và role trong container mới vẫn là `sw_b2b_outbound_demo_test`. Giữ cổng API/web riêng, ví dụ 15882/15883 thay cho 15880/15881.

Trước bước Alembic/runner, trong đúng PowerShell dành riêng cho bản mới:

```powershell
# DATABASE_URL phải trỏ đúng DB mới, chứa đúng port bên trên.
$env:APP_ENV = 'integration'
$env:ANOMALIES_ALLOW_FIXTURE = 'true'
$env:ANOMALIES_OUTBOUND_LINK_DEMO_ID = [Guid]::NewGuid().ToString()
$env:CORS_ORIGINS = '["http://127.0.0.1:15883"]'
$fixtureRoot = Join-Path $env:TEMP ("sw-b2b-outbound-link-" + [Guid]::NewGuid().ToString('N'))
python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Không nâng được schema demo mới' }
python -m tests.prepare_b2b_outbound_anomaly_demo --root "$fixtureRoot"
if ($LASTEXITCODE -ne 0) { throw 'Không dựng được dữ liệu demo mới' }
python -m uvicorn app.main:app --host 127.0.0.1 --port 15882
```

Đặt `DATABASE_URL`, `JWT_SECRET_KEY` và `B2B_OUTBOUND_DEMO_PASSWORD` cho phiên theo hướng dẫn liên kết trước khi chạy. **Một UUID demo mới cho một DB mới**, giữ cùng UUID cho runner và API đó. Dùng PowerShell riêng cho API; không đưa UUID sang bản demo cũ, không bao giờ dùng với production. Bản sao đầy đủ của cả DB lẫn cấu hình UUID là cùng một danh tính demo; để tạo demo độc lập phải dùng DB/UUID mới, không sao chép định danh.

Trong PowerShell khác, ở `client/` của cùng bản sao, đặt `$env:VITE_API_BASE_URL = 'http://127.0.0.1:15882/api/v1'`, rồi chạy `npm run dev -- --host 127.0.0.1 --port 15883 --strictPort`. Sau khi đăng nhập tài khoản admin/thủ kho **mẫu**, mở `alert_path` từ kết quả runner rồi bấm **Mở phiếu xuất**. Dùng `outbound_id` từ runner để đối chiếu; ID là kết quả của lần seed, không phải giá trị phải gán thủ công. Trang chỉ đọc; khách không mở được. Các cảnh báo khác không có bằng chứng liên kết sẽ không hiện nút.

## Dữ liệu và an toàn

- Runner kiểm bundle M5/hash catalog M9 và chụp lại nguồn B2B đã commit trong chính DB demo, giữ mã ngẫu nhiên của lần fulfill ở trong bộ nhớ, rồi ghi liên kết riêng. Không thêm mã giao dịch thô vào catalog công khai.
- Ca demo có hai phiếu cùng kho/SKU/lượng/thời điểm và có phiếu khác trùng số với transaction ID. Liên kết xác minh đúng quan hệ qua `transaction.outbound_id`, không đoán.
- Nếu thiếu/hỏng nguồn hoặc dấu DB khác, không mở phiếu. Không sửa phiếu, tồn kho, đơn, điểm, SHAP hay hồ sơ đánh giá khi đọc.
- Không tái sử dụng database đã seed một phần hoặc UUID giữa hai lần độc lập. Nếu cần làm lại, dùng DB+UUID+thư mục mới. Chỉ dừng container và tiến trình mới tạo riêng cho demo này.
