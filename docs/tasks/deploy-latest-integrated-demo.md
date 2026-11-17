# Deploy bản Smart Warehouse tích hợp mới nhất trên Render

## Metadata

- Status: IN_PROGRESS
- Plan: docs/tasks/deploy-latest-integrated-demo.md#implementation-plan
- Depends on: docs/tasks/deploy-smart-warehouse.md, docs/tasks/integrate-full-system-demo.md, docs/tasks/verify-integrated-demo-ci.md
- Created: 2026-11-18
- Started: 2026-11-18

## Goal

Cập nhật bản demo HTTPS Render từ baseline a5a34f7 và xác minh các luồng nghiệp vụ, phân tích và RAG cần cho buổi demo.

## Context

Nhánh feat/figma-ui-v2 tại a5a34f7 đã qua Quality. Nhánh Render hiện tại đang ở 8b25cb4, là tổ tiên của baseline. Dashboard có đúng dịch vụ web, API và PostgreSQL demo đang hoạt động. render.yaml ở baseline chưa có cấu hình catalog phân tích hay trợ lý. Stack 58082 dùng catalog cục bộ và Ollama trong namespace của API. Các catalog nghiên cứu cục bộ không thuộc gói triển khai public.

## In Scope

- Nhánh deploy riêng, dùng chung checkout cách ly hiện tại nếu không có thay đổi tracked.
- Giữ cấu hình Render Free và HTTPS hiện có. Chỉ dùng database demo chuyên dụng. Xác minh database trước migration.
- Chuẩn bị và nạp corpus RAG đã version hóa từ docs/assistant trong image. Dùng kết nối HTTPS tương thích API hiện có với nhà cung cấp và mô hình do người dùng xác định cho Render. Giữ dẫn nguồn và quyền tài liệu. Không ghi secret hoặc gửi dữ liệu nghiệp vụ cho provider.
- Chuẩn bị catalog tổng hợp từ đầu vào synthetic do repo tạo để demo dự báo, bổ sung, cold-start và SHAP. Đánh dấu rõ nguồn demo, dùng cấu hình integration có giới hạn tại entry point Render và giữ nguyên kiểm tra chặn fixture của production. Tái dùng công cụ tạo, thẩm định và nhập có sẵn. Cấu hình GIS tiếp tục dùng snapshot public đã xác minh.
- Kiểm chứng triển khai qua HTTPS và các vai trò hiện có, ghi commit được Render phục vụ và kết quả theo từng mô-đun.
- Giải thích yêu cầu cấu hình Resend cho quên mật khẩu. Xác minh giao diện và đổi mật khẩu qua luồng hiện có nếu có tài khoản demo được phép kiểm thử. Gửi email thật chỉ sau khi có sender và secret của người dùng tại Render.

## Out of Scope

- Gói trả phí, thay DNS, tạo/xóa database hoặc volume đang dùng, ghi đè dữ liệu nghiệp vụ trên Render, nới RBAC hoặc thay đổi hợp đồng API.
- Công bố dữ liệu nghiên cứu cục bộ, mật khẩu, token, file .env hoặc đầu ra cục bộ ngoài bộ tổng hợp riêng đã review.
- Đổi nhà cung cấp RAG, truyền tài liệu tới bên mới hoặc sử dụng chi phí mà chưa xác định phạm vi với người dùng. Dùng khóa từ Render Environment.
- Merge vào nhánh chính hoặc sửa lịch sử Git. Xuất bản cấu hình deploy theo quyền đã cấp tại thời điểm bàn giao checkpoint.

## Acceptance Criteria

- [ ] AC-1. Build và smoke với PostgreSQL cô lập thành công. Chỉ Render demo được mở cấu hình synthetic, không làm yếu cấu hình production mặc định. Startup chỉ vào database demo, seed có thể chạy lại, không ghi đè dữ liệu đang dùng và không in giá trị bí mật.
- [ ] AC-2. API và Static Site trên Render xác nhận cùng revision đã kiểm thử, readiness trả 200 và refresh deep link hoạt động. Phân quyền admin, warehouse, client và tra tồn/mua B2B/GIS chạy được bằng dữ liệu demo.
- [ ] AC-3. Dự báo, bổ sung, cold-start và bất thường hiển thị lượt tổng hợp hợp lệ và gắn nhãn. Phân biệt bằng chứng mô phỏng với số liệu nghiên cứu trong đề cương.
- [ ] AC-4. Trợ lý dùng model thật ở môi trường Render, câu hỏi chuyển kho trả câu có nguồn và mở được phiên bản tài liệu. Quyền client vẫn bị từ chối. Ghi model đã xác minh và giới hạn so với cấu hình chấm local.
- [ ] AC-5. Ghi bằng chứng hỗ trợ mật khẩu, trạng thái quên mật khẩu qua email và các điều kiện chưa được xác minh. Bàn giao URL và cách rollback cấu hình/revision sau khi kiểm tra tương thích migration.

## Implementation Plan

Task identifier deploy-latest-integrated-demo. Người dùng yêu cầu tạo và triển khai task này ngày 2026-11-18. Thiết kế dựa trên render.yaml và deploy/render/start.py hiện có, giao thức catalog của full demo và kịch bản CI synthetic. Không chuyển cấu hình test rộng ra ứng dụng production.

1. Rà commit đã qua CI, ancestor của nhánh Render, trạng thái ba dịch vụ và thay đổi migration. Test các ràng buộc khởi động trước khi chạm endpoint hoặc dịch vụ.
2. Sửa Dockerfile, deploy/render/start.py và tests/test_render_start.py để đưa đúng corpus vào image và chỉ nạp khi cấu hình RAG hợp lệ, sau migration và seed. Giữ cấu hình cũ hoạt động nếu trợ lý tắt.
3. Chuẩn bị bộ phân tích synthetic mới từ các bộ tạo fixture committed trong tests/prepare_*_e2e.py. Chọn cách đóng gói theo khả năng build lạnh, ghi manifest và hash để xác minh, giữ public GIS độc lập. Dùng script deploy riêng trong deploy/render nếu cần nạp dữ liệu; sửa render.yaml để ràng buộc đúng image, catalog và startup demo có kiểm soát. Bổ sung test startup, seed và kiểm tra hồ sơ catalog.
4. Chạy API + web trên database demo cô lập, kiểm tra giới hạn tài nguyên và hành vi khi thiếu cấu hình. Review diff, kiểm tra CI và xác minh nhà cung cấp RAG thật. Cập nhật nhánh/dịch vụ chỉ sau khi gói deploy đạt.
5. Deploy API rồi Static Site với cùng revision. Xác minh Render Deploys, readiness, mở deep link bằng HTTPS, đọc dữ liệu từ các luồng demo, kiểm tra RAG và các vai trò. Ghi bằng chứng và cách quay về revision phù hợp nếu cần.

## Verification Commands

- .venv/Scripts/python.exe -m pytest -q tests/test_render_start.py
- .venv/Scripts/python.exe -m ruff check deploy/render tests/test_render_start.py
- python -m pytest -q với PostgreSQL test cô lập
- npm.cmd run build trong client
- git diff --check và kiểm tra cấu hình build image với Docker
- Render Deploys và kiểm tra HTTPS readiness, xác thực account demo, deep link và luồng demo trình duyệt với API thật

## Progress Log

- 2026-11-18. READY -> IN_PROGRESS. Xác nhận ba dependency DONE, baseline a5a34f7 và ancestor 8b25cb4. GitHub Quality đạt. Dashboard hiển thị API và Static Site Deployed, Postgres Available. Docker Desktop Linux engine cục bộ hiện chưa kết nối.


- 2026-11-18. Ba ca khởi động được viết trước. Khi chưa sửa, hai ca bật trợ lý thất bại vì startup không nạp corpus hoặc không phát hiện thiếu model. Sau khi sửa, tests/test_render_start.py đạt 13/13 và Ruff đạt. npm.cmd run build thành công, chỉ có cảnh báo kích thước chunk hiện hữu. Docker build đạt. Sáu mục corpus trong image đều parse hợp lệ.
- 2026-11-18. Docker Desktop đã chạy. Smoke image với giới hạn 512 MB, 0,1 CPU, database PostgreSQL demo cô lập và GIS release thật. Startup hoàn tất migration, seed, nạp 6 mục corpus; readiness HTTP 200 và đường đọc nguồn khi chưa đăng nhập HTTP 401. Cấu hình mô hình thử nghiệm phục vụ kiểm tra startup; lượt smoke không gọi mô hình bên ngoài.
- 2026-11-18. tests/test_replenishment_cli.py -k real_owned đạt 1/1, gồm dự báo synthetic, verify/publish và đối soát độc lập 6.408 ngày mô phỏng. Catalog cold-start tổng hợp được tạo lại. Chạy tạo mới catalog SHAP không thành công trong các image cache không có bộ thư viện phân tích. Catalog SHAP tổng hợp đã tạo và kiểm chứng trong full demo được xác minh lại bằng verify_run trước khi đóng gói. Candidate ZIP chứa 10 thành viên synthetic có hash, 240.075 byte, SHA-256 fb6cd70ec8968482eafcd7f40be7e81c96c20c2199b3e1476d9a17caae83b3a6; chỉ tồn tại cục bộ ngoài Git.
- 2026-11-18. Candidate dùng binding (product_id=1, warehouse_id=2, unit=unit) của dữ liệu test. Seed mặc định Render tạo DEMO-001 với unit=each. Cần chuẩn bị binding riêng với kho/sản phẩm demo trống hoặc tạo lại forecast/policy theo binding thực đã xác minh; không thay unit hay giả định ID của dữ liệu đang chạy.

- 2026-11-18. Người dùng xác nhận triển khai đầy đủ và không chọn phát hành riêng phần nghiệp vụ.
- 2026-11-18. Thêm bộ nạp bundle có SHA-256 và allowlist đường dẫn. Render khởi động với cấu hình production đã kiểm tra trước. Chỉ sau khi bundle hợp lệ, launcher mới bật bốn fixture phân tích cho process của database demo. GIS vẫn dùng snapshot public. SKU DEMO-ANALYTICS-001 và kho WH-ANALYTICS-DEMO có ID dành riêng; nếu trùng dữ liệu không đúng binding, bootstrap dừng.
- 2026-11-18. Tạo lại forecast/policy với binding (70004001, 70004002, unit), đối soát 6.408 ngày, xác minh với cold-start và SHAP đã kiểm chứng. Artifact cục bộ: C:/Temp/sw-render-fixture-20261118/smart-warehouse-synthetic-render-integrated.zip. SHA-256 042c35b792209a06c48575878d40c935609b028af0b63f9d8447d628ac7458d4, 240.092 byte. ZIP chỉ chứa 10 mục tổng hợp và một manifest, chưa phát hành.
- 2026-11-18. 20/20 tests/test_render_start.py, Ruff, git diff --check và Docker image build đều đạt. Smoke riêng với PostgreSQL 16 cô lập và TestClient gọi API thật: migration/seed, cả ba vai trò đăng nhập, readiness 200, dự báo/bổ sung/cold-start ready, bất thường available, client tìm được kho mẫu và nhận 403 ở API bất thường. Seed chạy lại giữ số lượng đã đổi và đơn vị DEMO-001 giữ each. Kiểm tra này đọc bundle cục bộ qua callback, không xác minh tải ZIP từ GitHub Release hay các tính năng trên Render. Kiểm tra trình duyệt online, CI revision mới và toàn bộ pytest vẫn chưa chạy.
- 2026-11-18. Đề xuất Groq qwen/qwen3.8-27b vì tài liệu xác nhận Structured Outputs strict. Chưa chọn nhà cung cấp, chưa gửi câu hỏi/tài liệu đến Groq và chưa có API key. RAG online tiếp tục chưa xác minh.

## Trạng thái bàn giao

IN_PROGRESS. Phần cấu hình và dữ liệu mẫu đã có bằng chứng cục bộ. Chưa commit, push, upload hoặc cập nhật dịch vụ Render. Cần nhà cung cấp mô hình được người dùng thiết lập để kiểm thử RAG online và chốt bản đầy đủ.

## Handoff tiếp theo

- Hoàn tất review, publish đúng nhánh deploy và asset tổng hợp đã xác minh. Deploy API với RENDER_DEMO_BUNDLE_URL và RENDER_DEMO_BUNDLE_SHA256. Không đặt APP_ENV=integration trực tiếp, launcher đảm bảo cấu hình production trước khi kiểm tra bundle.
- Mô hình do người dùng cấu hình trong Render Environment. Với ứng viên Groq, base URL https://api.groq.com/openai/v1, model qwen/qwen3.8-27b. Bật ASSISTANT_ENABLED, dùng ASSISTANT_API_KEY từ Dashboard và smoke đúng payload có JSON Schema. Ca chấm Ollama cục bộ không thay cho smoke model online.
- Chỉ bật email khôi phục khi có RESEND_API_KEY, sender hợp lệ và HTTPS origin cùng CORS. Chọn Save only nếu cấu hình provider trước deploy để giữ bản hiện tại.


## Khôi phục sau cập nhật

- Khi API đã chạy migration 20261110_0006 và 20261113_0007, revision đang phục vụ trước đó thiếu hai migration này. Không rollback trực tiếp API về 8b25cb4/cf1ae3d, vì launcher cũ chạy alembic upgrade head và không nhận diện được revision mới.
- Phương án giảm chức năng giữ schema mới: lưu ASSISTANT_ENABLED=false, bỏ hai cấu hình RENDER_DEMO_BUNDLE_* ở Render và redeploy revision đã có các migration (ưu tiên revision phát hành hiện tại; fallback mã a5a34f7). Lưu lại cấu hình cũ của từng biến để có thể bật lại. Xác minh readiness và login sau deploy.
- Không downgrade PostgreSQL. Việc lưu cấu hình có thể được Blueprint ghi lại khi sync lần sau; đối chiếu cấu hình hiệu lực trước khi deploy lại.

## Kiểm chứng trước phát hành

- 2026-11-18. Người dùng xác nhận đã lưu key. Chỉ xác minh tên ASSISTANT_API_KEY xuất hiện trong Render Environment. Pin cấu hình công khai trong Blueprint, bắt buộc HTTPS cho model hosted và bổ sung test từ chối loopback. Cold-start được tạo từ fixture tổng hợp, các biến bí mật vẫn nhập riêng trên Render.
