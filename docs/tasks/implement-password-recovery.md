# implement-password-recovery — Quên và đổi mật khẩu

## Metadata

- Status: DONE
- Phase: Xác thực tài khoản
- Plan: docs/tasks/implement-password-recovery.md#implementation-plan
- Depends on: docs/tasks/deploy-smart-warehouse.md
- Created: 2026-11-09
- Started: 2026-11-10
- Completed: 2026-11-10

## Goal

Cho phép người dùng đặt lại mật khẩu qua email khi quên và tự đổi mật khẩu từ tài khoản đang đăng nhập. Sau khi đổi hoặc đặt lại thành công, người dùng đăng nhập lại bằng mật khẩu mới.

## Context

React đã có `/forgot-password` và `/reset-password`, hiện chỉ hiển thị thông báo. FastAPI dùng Argon2 để băm mật khẩu và JWT để xác thực. Backend chưa có chức năng gửi email, mã khôi phục hoặc thu hồi JWT theo phiên bản mật khẩu. Bản demo chạy trên [Render Free](https://render.com/docs/free), nơi các cổng SMTP 25, 465 và 587 bị chặn.

## In Scope

- Hoàn thiện hai màn hình khôi phục và thêm mục **Đổi mật khẩu** trong menu tài khoản cho cả ba vai trò. Giữ giao diện tiếng Việt và dùng biểu mẫu hiện có.
- Thêm API yêu cầu khôi phục, đặt lại và đổi mật khẩu. Giữ chính sách mật khẩu hiện có từ 12 đến 128 ký tự. Thêm migration PostgreSQL để quản lý mã khôi phục và phiên bản JWT.
- Gửi liên kết qua API HTTPS phía backend. Đề xuất dùng Resend, với bộ gửi giả chỉ dành cho kiểm thử. Thêm cấu hình kiểm thử cô lập và hướng dẫn bật email trên Render với hộp thư do chủ tài khoản kiểm soát.

## Out of Scope

- Đăng ký trên web, đổi email, MFA, câu hỏi bảo mật và chức năng đặt lại mật khẩu thay người khác trong Admin.
- Mua tên miền, thay gói Render, tạo tài khoản nhà cung cấp email hoặc thay đổi DNS. Bật gửi email thật và deploy tính năng lên Render cần cấu hình và phê duyệt triển khai riêng.

## Acceptance Criteria

- [x] AC-1. Người dùng nhập email và nhận cùng phản hồi chung cho địa chỉ hợp lệ dù tài khoản tồn tại, không tồn tại hay đã bị vô hiệu hóa. Backend giới hạn gửi lặp và chống gửi hàng loạt. Chỉ tài khoản hoạt động nhận được liên kết qua email.
- [x] AC-2. Liên kết có hiệu lực 30 phút và chỉ dùng một lần. PostgreSQL chỉ lưu hash của mã khôi phục. Từ chối mã giả, hết hạn, đã dùng hoặc bị thu hồi. Khi hai yêu cầu dùng cùng mã chạy đồng thời, chỉ một yêu cầu được đổi mật khẩu.
- [x] AC-3. Đổi mật khẩu trong phiên yêu cầu nhập đúng mật khẩu hiện tại và xác nhận mật khẩu mới. Đổi hoặc đặt lại thành công thu hồi các mã khôi phục và JWT cũ của tài khoản trong cùng giao dịch. Mật khẩu cũ không đăng nhập được. Mật khẩu mới đăng nhập được và vai trò giữ nguyên.
- [x] AC-4. Biểu mẫu tiếng Việt có trạng thái đang gửi, thông báo lỗi và xác nhận thành công. Kiểm thử giao diện ở cả chiều rộng 390 px và desktop, gồm luồng quay lại đăng nhập khi hoàn tất.
- [x] AC-5. Kiểm thử bằng hộp thư giả xác minh liên kết, đổi mật khẩu, thu hồi phiên và thông báo sau khi thay mật khẩu. Có hướng dẫn bật nhà cung cấp trên Render, xử lý khi thiếu cấu hình, và cách thử gửi đến một hộp thư đã được cho phép. Ghi riêng kết quả nhận thư thật nếu có cấu hình và phê duyệt triển khai.

## Implementation Plan

Kế hoạch cho `implement-password-recovery`, được người dùng duyệt ngày 2026-11-10.

1. Tạo migration bổ sung phiên bản xác thực cho người dùng và bản ghi hash mã khôi phục, hạn dùng, trạng thái sử dụng. Các tài khoản hiện có bắt đầu ở phiên bản 0. JWT cũ thiếu trường phiên bản chỉ hợp lệ khi database vẫn là phiên bản 0. JWT mới mang phiên bản lấy cùng bản ghi dùng để xác thực mật khẩu khi đăng nhập. Thêm tham số phiên bản dạng keyword để giữ tương thích với các lời gọi dùng `expires_delta`. Nếu phải quay về backend cũ sau khi đã bật tính năng, thay khóa ký JWT để các phiên đã thu hồi không có hiệu lực trở lại.
2. Thêm `POST /api/v1/auth/forgot-password`, `POST /api/v1/auth/reset-password` và `POST /api/v1/auth/change-password`. Giới hạn số yêu cầu khôi phục trên toàn hệ thống trong PostgreSQL trước khi đưa vào xử lý nền và áp dụng giới hạn theo tài khoản trong tác vụ nền. Chỉ dùng giới hạn theo IP khi có nguồn IP đáng tin cậy từ cấu hình triển khai. Bỏ qua header do máy khách tự khai. Tác vụ nền dùng phiên database riêng và thời gian chờ giới hạn. Lỗi gửi thư hoặc mất tác vụ khi dịch vụ khởi động lại giữ nguyên phản hồi chung và cho phép người dùng gửi lại sau thời gian chờ.
3. Sinh mã ngẫu nhiên bằng bộ sinh số an toàn. Tạo URL từ origin frontend được cấu hình, đưa mã vào fragment để tránh ghi vào log URL phía máy chủ. Trang đặt lại đọc và xóa fragment khỏi thanh địa chỉ. Các thao tác phát hành mã, đổi và đặt lại mật khẩu khóa bản ghi người dùng trước, đọc lại trạng thái tài khoản và phiên bản trực tiếp từ database. Sau đó kiểm tra quyền sử dụng mã hoặc mật khẩu hiện tại. Cập nhật hash Argon2, thu hồi mã và tăng phiên bản JWT trong một giao dịch. Khi email được bật, gửi thông báo sau khi giao dịch thành công. [Hướng dẫn OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html)
4. Tắt khôi phục qua email mặc định. Khi thiếu cấu hình, trang khôi phục báo dịch vụ chưa khả dụng với mọi địa chỉ. Luồng đổi mật khẩu trong phiên vẫn hoạt động. Khi bật gửi thật, kiểm tra origin HTTPS, địa chỉ gửi và API key. Dùng timeout, tắt theo dõi click và lược bỏ dữ liệu nhạy cảm trong log. Tạo tài khoản kiểm thử có hộp thư nhận được thư khi thử Render. [API gửi email Resend](https://resend.com/docs/api-reference/emails/send-email), [Xác minh tên miền gửi](https://resend.com/docs/dashboard/domains/introduction)
5. Kết nối biểu mẫu React, tự đăng xuất phiên hiện tại sau khi đổi thành công và điều hướng đến trang đăng nhập. Kiểm thử hồi quy đăng nhập, quyền và các phiên đang hoạt động của tài khoản khác.

Các bước thực thi theo thứ tự kiểm thử rồi triển khai:

- Backend. Viết ca hồi quy cho API và giao dịch PostgreSQL. Thêm migration, trường `auth_version`, chính sách so khớp JWT, bộ gửi email và logic cho ba endpoint trong `app/auth/`.
- Giao diện. Viết ca kiểm thử cho phản hồi chung, lỗi, trạng thái gửi và đăng nhập lại. Mở rộng `client/src/pages/AuthPages.tsx`, router và menu tài khoản. API quên mật khẩu nhận `email` và trả `202` hoặc `503` khi tắt. API đặt lại nhận `token`, `new_password` và `confirm_password`. API đổi nhận `current_password`, `new_password` và `confirm_password`. Hai API thay mật khẩu trả `204` khi thành công.
- Kiểm chứng. Dùng stack kiểm thử riêng và bộ gửi giả để chạy ca trình duyệt. Kiểm tra migration, hồi quy backend, build, diff và review độc lập trước khi chốt task.

## Verification Commands

### Focused

- `python -m pytest -q tests/test_auth.py tests/unit/test_auth_schemas.py tests/postgres/test_auth_integration.py tests/postgres/test_password_recovery.py` trên database kiểm thử riêng. `test_password_recovery.py` được thêm trong task.
- Chạy `npm.cmd run test:all` trong `client`. Khởi động stack Compose kiểm thử riêng với PostgreSQL riêng và một cổng loopback được `playwright.config.ts` cho phép. Bộ gửi giả ghi vào hộp thư chỉ dùng trong môi trường kiểm thử để Playwright lấy liên kết. Đặt `E2E_BASE_URL` trỏ đúng stack và chạy `npm.cmd run e2e -- password-recovery.spec.ts`. Dọn tài nguyên theo đúng tên project thử nghiệm.

### Regression

- Chạy `python -m pytest -q` với PostgreSQL kiểm thử riêng. Kiểm tra Alembic nâng cấp từ revision hiện tại, hạ cấp và nâng cấp lại, gồm dữ liệu tài khoản có trước migration.
- Chạy `npm.cmd run typecheck` và `npm.cmd run build` trong `client`.

### Static and Diff

- Chạy Ruff cho các file Python thay đổi, `git diff --check` và kiểm tra diff không chứa thông tin đăng nhập, API key, mật khẩu hay mã đặt lại.

## Hướng dẫn bật email trên Render

- Tính năng khôi phục qua email mặc định tắt. Sau khi được duyệt triển khai, dùng tên miền gửi đã xác minh trên Resend, tắt theo dõi click trên tên miền đó và dùng API key chỉ có quyền gửi. Đặt `PASSWORD_RECOVERY_ENABLED=true`, `PASSWORD_RECOVERY_ORIGIN` bằng origin HTTPS của frontend đã có trong `CORS_ORIGINS`, `PASSWORD_RECOVERY_FROM_EMAIL` bằng địa chỉ gửi đã xác minh và `RESEND_API_KEY` bằng secret trong môi trường backend.
- Khi được phép kiểm thử email thật, dùng tài khoản thử riêng với hộp thư do người kiểm thử kiểm soát. Yêu cầu đặt lại, mở thư, đặt mật khẩu mới, xác nhận mật khẩu cũ và JWT trước đó bị từ chối, rồi xác nhận thư báo thay đổi. Giữ mã và mật khẩu khỏi log, ảnh chụp và tài liệu.
- Khi cần tạm dừng gửi email, đặt `PASSWORD_RECOVERY_ENABLED=false`. Nếu phải rollback về bản backend chưa kiểm tra phiên bản JWT, thay secret ký JWT trong lần rollback để buộc mọi phiên cũ xác thực lại.
- Kiểm thử Playwright chỉ được đăng ký khi có `E2E_PASSWORD_RECOVERY=1`. Bật biến này cùng `E2E_BASE_URL=http://127.0.0.1:58081` cho stack chuyên dụng với `docker-compose.password-recovery-e2e.yml`. Bộ browser CI mặc định tiếp tục chạy trên stack riêng hiện có.

## Progress Log

- 2026-11-09. Tạo task tại đường dẫn người dùng đã xác nhận sau khi push hồ sơ triển khai Render. Phạm vi và phương án gửi email đang chờ duyệt.
- 2026-11-10. `READY -> IN_PROGRESS`. Người dùng duyệt kế hoạch. Xác nhận dependency deploy `DONE` và tạo nhánh `codex/password-recovery` từ `8b25cb4` trong worktree hiện có. Baseline xác thực đạt 14 ca.
- 2026-11-10. Hoàn tất migration, ba endpoint, gửi email qua HTTPS, ba màn hình và bộ gửi giả. Lần chạy Playwright đầu phát hiện mất thông báo khi route guard và luồng đổi mật khẩu cùng điều hướng. Đã lưu phản hồi thành công ở trạng thái phiên và kiểm tra lại hai kích thước màn hình. `IN_PROGRESS -> VERIFYING` để chạy bộ kiểm thử cuối.
- 2026-11-10. `VERIFYING -> IN_PROGRESS`. Bộ hồi quy backend phát hiện ca kiểm tra log của bộ gửi phụ thuộc thứ tự khi chạy sau migration. Cần tách cấu hình logger trong ca kiểm thử.
- 2026-11-10. Ca kiểm tra migration cũ cũng phát hiện ORM chèn giá trị mặc định `auth_version` trước khi cột tồn tại. Đã giữ giá trị mặc định ở database và bỏ mặc định trùng lặp trong ORM. Đã cô lập logger trong ca kiểm thử. `IN_PROGRESS -> VERIFYING` để chạy lại hai ca và bộ hồi quy.
- 2026-11-10. `VERIFYING -> IN_PROGRESS`. Hồi quy Cold Start phát hiện bốn đối tượng người dùng giả thiếu `auth_version`. Phải cập nhật đối tượng giả để tiếp tục kiểm tra phân quyền qua dependency xác thực thật.
- 2026-11-10. Cập nhật đối tượng giả với phiên bản 0 và giữ nguyên các assertion phân quyền. Cả 5 ca Cold Start chạy lại đạt. `IN_PROGRESS -> VERIFYING` để chạy bộ hồi quy từ bản sao cuối trong Docker.
- 2026-11-10. `VERIFYING -> IN_PROGRESS`. Ca kiểm tra ranh giới kiến trúc phát hiện router xác thực import SQLAlchemy để khai báo kiểu phiên database. Cần giữ cách khai báo dependency như các router hiện có.
- 2026-11-10. Hồi quy SQLite không hỗ trợ thêm ràng buộc bằng lệnh riêng. Đã chuyển ràng buộc `auth_version >= 0` vào định nghĩa cột để cả PostgreSQL và SQLite giữ được ràng buộc khi nâng cấp. Đã đưa router về mẫu khai báo dependency hiện có.
- 2026-11-10. `IN_PROGRESS -> VERIFYING`. 68 ca SQLite, kiến trúc và xác thực chạy lại đạt. Tách bộ hồi quy Linux thành các nhóm chạy song song, giữ nhóm dùng PostgreSQL chạy tuần tự. Cài `libexpat1` trong image kiểm thử để các ca GIS hoạt động. Chạy ba ca chỉ dành cho Windows bằng runner riêng.
- 2026-11-10. `VERIFYING -> REVIEWING`. Bản sao cuối đã qua toàn bộ 1.659 ca backend khi gộp Linux và Windows, build frontend, hai ca Playwright và kiểm tra diff.
- 2026-11-10. `REVIEWING -> IN_PROGRESS`. Review yêu cầu sửa cách xử lý khi thiếu cấu hình email, chặn origin có cổng sai, giới hạn chờ khóa của tác vụ cấp mã, che tham số database khi lỗi và giữ thông báo thành công nếu phiên cũ nhận `401` song song.
- 2026-11-10. `IN_PROGRESS -> VERIFYING`. Đã bổ sung ca hồi quy cho các phát hiện và xác nhận chúng thất bại trước khi sửa. Khôi phục trả `503` khi thiếu cấu hình, bộ gửi chờ khóa tối đa 2 giây và giới hạn từng câu SQL 5 giây, lỗi giao dịch trả thông báo an toàn, giao diện nhận biết đúng phiên vừa bị `401`.
- 2026-11-10. `VERIFYING -> IN_PROGRESS`. Ruff báo hai dòng quá dài trong ca kiểm thử lỗi database.
- 2026-11-10. Đã xuống dòng cho hai khai báo trong kiểm thử. Không đổi logic hay assertion. `IN_PROGRESS -> VERIFYING`.
- 2026-11-10. `VERIFYING -> REVIEWING`. Bản sau sửa qua 1.666 ca backend, 441 ca Vitest, 88 ca host, hai ca Playwright, typecheck, build, Ruff và kiểm tra diff.
- 2026-11-10. Review lại xác nhận bốn phát hiện đã được xử lý. `REVIEWING -> IN_PROGRESS` để chuyển bước tạo tài khoản lên trước phép so sánh `503`, giúp ca kiểm thử thực sự có một địa chỉ đã tồn tại.
- 2026-11-10. Đã đổi thứ tự sắp xếp dữ liệu trong ca kiểm thử. `IN_PROGRESS -> VERIFYING` để chạy lại nhóm kiểm thử bị ảnh hưởng.
- 2026-11-10. `VERIFYING -> REVIEWING`. Nhóm xác thực và cấu hình chạy lại đạt 39 ca. Ruff và kiểm tra diff đạt. Mã ứng dụng giữ nguyên so với bản đã qua 1.666 ca backend.
- 2026-11-10. `REVIEWING -> DONE`. Review độc lập xác nhận cả bốn phát hiện và ca so sánh `503` đã được xử lý. Đã dọn container và database kiểm thử.

## Verification Evidence

### Focused

- `python -m pytest -q tests/test_auth.py tests/unit/test_auth_schemas.py tests/postgres/test_auth_integration.py tests/postgres/test_password_recovery.py tests/postgres/test_migrations.py --tb=short` trên PostgreSQL 16 cô lập. 29 ca đạt. Đã kiểm tra phản hồi chung, giới hạn gửi, mã hết hạn hoặc bị thu hồi, thay mật khẩu đồng thời, JWT cũ và lỗi bộ gửi. Alembic nâng cấp đến `20261110_0006` và tài khoản cũ nhận phiên bản 0.
- `npm.cmd exec -- vitest run src/pages/PasswordRecovery.test.tsx` đạt 8 ca sau khi sửa thông báo thành công và liên kết mở lại trên cùng trang.
- Compose `sw-password-recovery-e2e` dựng xong với web chỉ bind `127.0.0.1:58081` và bộ gửi giả. Với `E2E_PASSWORD_RECOVERY=1`, `npm.cmd run e2e -- password-recovery.spec.ts --reporter=list --retries=0` đạt 2 ca tại 390 px và 1440 px. Đã xác nhận nội dung inbox, đăng nhập bằng mật khẩu mới, thông báo sau khi đổi và từ chối JWT cũ. Gửi email thật trên Render chưa được kiểm thử.
- Kiểm tra API với hai tài khoản tổng hợp trên stack này. Sau khi tài khoản thứ nhất đổi mật khẩu, JWT cũ của tài khoản đó trả `401`. JWT của tài khoản thứ hai vẫn trả `200`.
- Sau review, `python -m pytest -q --tb=short tests/unit tests/test_auth.py tests/test_migrations.py` đạt 73 ca. Kiểm tra PostgreSQL `tests/postgres/test_password_recovery.py tests/postgres/test_auth_integration.py` đạt 13 ca, gồm tình huống giữ khóa và lỗi SQL khi cập nhật. Ca kiểm thử UI mô phỏng `401` trước phản hồi đổi mật khẩu đã đạt trong bộ Vitest.

### Regression

- Backend Python 3.12 với PostgreSQL 16 cô lập. `python -m pytest --collect-only -q` thu được 1.659 ca. Các nhóm `python -m pytest -q -p no:cacheprovider --tb=short` đạt 563 ca PostgreSQL, 386 ca nhóm 0, 234 ca nhóm 1 và 457 ca nhóm 2. 16 ca Compose bỏ qua vì container thiếu Docker CLI, chạy riêng trên Windows đạt 16 ca với `python -m pytest -q tests/test_seed.py -k compose_config`. Ba ca Windows được tách khỏi Linux và đạt riêng bằng runner. Tổng 1.659 ca đạt, không còn ca thất bại hoặc chưa chạy.
- Xác nhận PostgreSQL có ràng buộc `ck_users_auth_version`. Migration lên `20261110_0006`, hạ cấp và nâng cấp lại trong bộ kiểm thử. Playwright chạy lại sau khi dựng backend từ bản cuối, đạt cả hai ca.
- `npm.cmd run test:all` đạt 440 ca Vitest và 88 ca host. `npm.cmd run typecheck` và `npm.cmd run build` đạt. Vite vẫn cảnh báo bundle trên 500 kB.
- Sau review, `npm.cmd run test:all` đạt 441 ca Vitest và 88 ca host. Typecheck và build đạt lại.
- Sau review, bộ hồi quy chạy lại đạt 565 ca PostgreSQL, 391 ca Linux nhóm 0, 234 ca nhóm 1 và 457 ca nhóm 2. Chạy riêng lại 16 ca Compose và ba ca Windows đều đạt. Tổng 1.666 ca. Playwright chạy lại đạt 2 ca với bản dựng sau review.
- `python -m tests.run_quality_ci windows` đạt 3 ca kiểm tra dành riêng cho Windows.

### Static and Diff

- `python -m ruff check app tests alembic` và `git diff --check` đạt. Đã kiểm tra whitespace của các file mới bằng `git diff --no-index --check`.
- Kiểm tra cấu hình với giá trị giả. Recovery mặc định tắt. Production từ chối origin HTTP, origin ngoài CORS và URL có đường dẫn. Lỗi cấu hình không hiện API key.

## Review Result

- Result: APPROVED
- Findings: Đã xử lý cấu hình email thiếu, xác thực cổng origin, giới hạn chờ khóa, che tham số lỗi database và phản hồi đổi mật khẩu khi phiên cũ nhận `401`. Review lại ca `503` xác nhận có một tài khoản tồn tại và một địa chỉ chưa đăng ký.

## Completion Evidence

- Hoàn tất ngày 2026-11-10 trên nhánh `codex/password-recovery`. Đạt 5/5 tiêu chí. Backend đạt 1.666 ca qua Linux và Windows. Frontend đạt 441 ca Vitest, 88 ca host, hai ca Playwright, typecheck và build. Ruff, kiểm tra diff và review độc lập đều đạt.
- Chức năng gửi email được kiểm chứng bằng hộp thư giả. Việc bật Resend và xác minh nhận email thật trên Render là bước triển khai riêng.
- 2026-11-13. Người dùng duyệt commit bản đã review và push lên `origin/codex/password-recovery`. Trước commit, chạy lại 73 ca backend tập trung, Ruff, frontend build và kiểm tra diff. Tất cả đều đạt. Hồ sơ này nằm cùng commit với tính năng và các ca kiểm thử liên quan.
