# Demo: từ thực xuất B2B đến Isolation Forest và SHAP

Chỉ dùng dữ liệu tổng hợp và PostgreSQL riêng cho demo. **Không dùng DB hiện tại của bạn, DB dev dùng chung hay DB production.** Runner tạo dữ liệu kiểm thử; không tạo bản sao dữ liệu thật. Không cần chạy worker analytics hoặc sửa cấu hình dự báo/bổ sung hàng.

## Chuẩn bị và chạy (PowerShell)

Chạy ở thư mục gốc của repo với Python phù hợp, PostgreSQL 16 và Node đã cài. Ví dụ sau dùng container mới, chỉ lắng nghe trên loopback, không gắn volume dữ liệu đang dùng. Đặt mật khẩu ngẫu nhiên riêng cho phiên demo và không chia sẻ với người dùng thật. Port ví dụ có thể đổi đồng thời ở container và URL.

```powershell
python -m pip install -e '.[dev,anomalies]'
if ($LASTEXITCODE -ne 0) { throw 'Cài dependencies thất bại' }
$demoDbPassword = [Guid]::NewGuid().ToString('N')
docker run --name sw-b2b-outbound-proof --detach --rm -p 127.0.0.1:18549:5432 `
  -e POSTGRES_DB=sw_b2b_outbound_demo_test `
  -e POSTGRES_USER=sw_b2b_outbound_demo_test `
  -e "POSTGRES_PASSWORD=$demoDbPassword" postgres:16-alpine
if ($LASTEXITCODE -ne 0) { throw 'Không tạo được container demo mới' }
docker exec sw-b2b-outbound-proof pg_isready -U sw_b2b_outbound_demo_test
```

Chỉ khi PostgreSQL báo `accepting connections`, thiết lập môi trường sau trong PowerShell dùng riêng cho demo:

```powershell
$env:APP_ENV = 'integration'
$env:ANOMALIES_ALLOW_FIXTURE = 'true'
$env:DATABASE_URL = "postgresql+psycopg://sw_b2b_outbound_demo_test:${demoDbPassword}@127.0.0.1:18549/sw_b2b_outbound_demo_test"
$env:JWT_SECRET_KEY = [Guid]::NewGuid().ToString('N') + [Guid]::NewGuid().ToString('N')
$env:B2B_OUTBOUND_DEMO_PASSWORD = [Guid]::NewGuid().ToString('N')
$env:CORS_ORIGINS = '["http://127.0.0.1:15881"]'
$fixtureRoot = Join-Path $env:TEMP ("sw-b2b-outbound-" + [Guid]::NewGuid().ToString('N'))
python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Migration DB demo thất bại' }
python -m tests.prepare_b2b_outbound_anomaly_demo --root "$fixtureRoot"
if ($LASTEXITCODE -ne 0) { throw 'Runner demo thất bại; không khởi động API trên DB này' }
```

Runner đòi DB trống, tên DB và role đều là `sw_b2b_outbound_demo_test`, ở loopback có cổng cụ thể, schema đúng checkout, cờ fixture bật và đường dẫn kết quả mới ở ngoài repo. Không dùng `python -O`. Runner không dọn hoặc ghi đè DB. Nếu chạy lỗi một phần, hãy kiểm tra lỗi rồi tạo **container demo khác, DB mới và thư mục kết quả mới**; không chạy lại trên DB đã được seed. Kiểm tra idempotency chỉ áp dụng cho việc nhập lại cùng artifact, không phải chạy lại toàn bộ bước seed.

Kết quả JSON chứa `bundle_id`, `run_id`, `alert_path`, điểm của giao dịch đích/đối chứng, ngưỡng và sai số SHAP. Thư mục `bundles` là đầu vào kỹ thuật riêng, có định danh fixture; không dùng như catalog để chia sẻ. Catalog chỉ có khóa mờ và đã được kiểm tra toàn vẹn trước nhập.

## Mở đúng cảnh báo

1. Trong PowerShell trên, mở API: `python -m uvicorn app.main:app --host 127.0.0.1 --port 15880`.
2. Trong PowerShell khác, ở `client/`: chạy `npm ci` nếu chưa có dependencies; đặt `$env:VITE_API_BASE_URL = 'http://127.0.0.1:15880/api/v1'` rồi chạy `npm run dev -- --host 127.0.0.1 --port 15881 --strictPort`.
3. Đăng nhập frontend tại `http://127.0.0.1:15881/login` bằng `b2b-outbound-demo-warehouse@example.com` hoặc `b2b-outbound-demo-admin@example.com` và mật khẩu demo đã đặt ở PowerShell (biến `B2B_OUTBOUND_DEMO_PASSWORD`). Nối địa chỉ frontend với đúng `alert_path` được in. Màn **Bất thường** hiện điểm, ngưỡng, giá trị nền, sáu thanh đóng góp theo dấu và nhãn dữ liệu tổng hợp.
4. Ghi chú thử và lưu đánh giá. Đánh giá chỉ thay đổi hồ sơ cảnh báo. Tài khoản `b2b-outbound-demo-client@example.com` không được xem hoặc đánh giá cảnh báo.
5. Khi xong, dừng Vite và API bằng Ctrl+C. Chỉ dừng đúng container mới tạo cho bài demo: `docker stop sw-b2b-outbound-proof`. Không giữ cấu hình test/fixture khi trở lại môi trường thường.

## Mô tả đúng trong báo cáo

Kịch bản sử dụng 1.200 giao dịch tổng hợp trên hai cặp kho/SKU. Hai đơn giữ cố định trong holdout đi qua API tạo → duyệt → thực xuất. M5 đọc các giao dịch đã commit; M9 fit với train, chọn ngưỡng riêng trên validation. Đúng giao dịch 10.000 `each` liên kết với cảnh báo qua khóa nguồn đã xác minh; đối chứng 2 `each` cùng kho/SKU vẫn dưới ngưỡng. Các giá trị và metrics chỉ phản ánh fixture, không chứng minh precision/recall vận hành hoặc nguyên nhân nghiệp vụ. **Kiểm tra đơn tạm tính** trước phê duyệt, Dự báo, Bổ sung hàng và bộ chọn kho không thay đổi.
