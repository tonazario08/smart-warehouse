# implement-rag-assistant — Trợ lý kho dùng RAG

## Metadata

- Status: DONE
- Phase: Mở rộng trợ lý hội thoại
- Plan: docs/tasks/implement-rag-assistant.md#implementation-plan
- Depends on: none
- Created: 2026-11-13
- Started: 2026-11-13
- Completed: 2026-11-16

## Goal

Cho phép quản trị viên và nhân viên kho hỏi bằng tiếng Việt về quy trình kho, dự báo và bổ sung tồn kho. Trợ lý trả lời dựa trên tài liệu đã duyệt và dẫn đến đúng mục nguồn.

## Context

Smart Warehouse đã có FastAPI, PostgreSQL, React, phân quyền theo vai trò và các màn hình nghiệp vụ. RAG thuộc hướng mở rộng của đề cương. Bản đầu dùng kho tài liệu hướng dẫn đã duyệt để có thể đo chất lượng truy xuất và đối chiếu câu trả lời. Tích hợp đặt sau RouteGuard trong App Shell đang dùng.

## In Scope

- Tài liệu Markdown đã duyệt về nhập, xuất, chuyển kho, dự báo và bổ sung tồn kho. Mỗi mục có định danh, tiêu đề, phiên bản, nguồn và quyền đọc.
- Lệnh nhập tài liệu từ nguồn đã định danh và tìm kiếm toàn văn PostgreSQL. Giữ văn bản gốc để đọc và trích dẫn. Chuẩn hóa chỉ mục và truy vấn tiếng Việt để hỗ trợ có dấu và không dấu.
- API hỏi đáp chỉ đọc, một bộ kết nối mô hình phía máy chủ, trích dẫn do backend xác thực, giới hạn sử dụng, timeout và cấu hình bật tính năng.
- Trang Trợ lý kho trên desktop và điện thoại, dùng chung phiên đăng nhập, CSS và thành phần React hiện có. Lịch sử hiển thị chỉ giữ trong bộ nhớ giao diện của phiên.
- Kiểm thử ứng dụng cô lập và đánh giá chất lượng trên bộ 30 câu trước khi nghiệm thu. Chạy thử mô hình thật trong môi trường demo cô lập với tài liệu đã duyệt.

## Out of Scope

- Đọc tồn kho, giao dịch hoặc dữ liệu khách hàng trực tiếp, thực thi SQL do mô hình tạo, tạo phiếu và thao tác thay mặt người dùng.
- Tải tài liệu tùy ý từ giao diện, đọc URL tùy ý, lưu lịch sử chat trong database hoặc trình duyệt, cấp quyền cho vai trò client.
- Triển khai lên Render đang chạy, mua gói dịch vụ hoặc xuất bản dữ liệu.

## Acceptance Criteria

- [x] AC-1. Bộ tài liệu dùng cho demo bao phủ năm nhóm nghiệp vụ đã nêu. Có liên kết đến từng mục nguồn, quyền đọc và phiên bản. Nhập lại cùng một phiên bản không tạo bản ghi trùng. Việc thay phiên bản không để lẫn mục cũ trong kết quả đang dùng.
- [x] AC-2. API yêu cầu JWT hợp lệ, chỉ mở cho admin và warehouse. Tài liệu quản trị chỉ được admin truy xuất. Ca kiểm thử xác nhận đoạn bị giới hạn không đến bộ kết nối mô hình và không xuất hiện trong câu trả lời, trích dẫn hoặc màn hình xem nguồn.
- [x] AC-3. Câu hỏi được truy xuất theo nội dung và trả lời bằng tiếng Việt. Khi thiếu căn cứ hoặc mô hình trả trích dẫn không hợp lệ, API báo chưa đủ thông tin. Kiểm tra câu hỏi có dấu, không dấu và diễn đạt lại.
- [x] AC-4. Câu hỏi trống hoặc quá giới hạn được báo rõ. Có phản hồi tiếng Việt cho giới hạn lượt hỏi, thiếu cấu hình, lỗi và timeout của mô hình. Nhật ký dùng mã lỗi và số liệu vận hành, không lưu nội dung hội thoại, tài liệu, JWT hoặc khóa dịch vụ.
- [x] AC-5. Admin và warehouse thấy mục Trợ lý kho. Client không thấy menu và không mở được trang bằng URL trực tiếp. Giao diện hiển thị câu hỏi gợi ý, trạng thái chờ, thử lại và nguồn bằng bàn phím, ở 390 px và desktop. Khi đăng xuất hoặc đổi tài khoản, giao diện xóa hội thoại và bỏ qua phản hồi muộn.
- [x] AC-6. Bộ đánh giá gồm 20 câu có đáp án, 5 câu ngoài phạm vi và 5 ca phân quyền hoặc chỉ dẫn cài trong câu hỏi hay tài liệu. Đóng băng câu hỏi, vai trò, đáp án và nguồn đúng trước lượt chấm cuối. Có ít nhất 18/20 câu vừa đúng nội dung vừa dẫn nguồn đúng, và 10/10 ca còn lại được xử lý an toàn. Ghi phiên bản dữ liệu, cấu hình truy xuất, mô hình và kết quả từng ca.
- [x] AC-7. Hồi quy backend và frontend, migration lên/xuống trên PostgreSQL cô lập, build, kiểm tra trình duyệt và review độc lập đều đạt. Ghi hướng dẫn cấu hình, tắt tính năng và chạy demo.

## Implementation Plan

Kế hoạch cho `implement-rag-assistant`. Các chặng dưới đây thuộc cùng một task.

### 1. Chuẩn bị tài liệu và kiểm thử truy xuất

Soạn tài liệu nghiệp vụ trong `docs/assistant/`. Xác minh hướng dẫn với màn hình và hành vi hiện hành. Dùng mục Markdown làm đơn vị trích dẫn. Lệnh nhập trong `app/assistant/cli.py` nhận các tệp đã duyệt, kiểm tra định danh, quyền đọc và đường dẫn nguồn trước khi cập nhật theo giao dịch. Thêm migration trong `alembic/versions/` cho các mục tài liệu và chỉ mục toàn văn. Viết kiểm thử nhập lại, thay phiên bản, lọc quyền và truy vấn tiếng Việt trước khi nối mô hình. Dùng tập câu hỏi phát triển riêng để chỉnh bộ truy xuất trước lượt chấm cuối.

### 2. Xây API hỏi đáp và nối mô hình

Thêm `app/assistant/` theo cấu trúc router, service, repository, schemas và bộ kết nối mô hình. Đăng ký router trong `app/main.py`, thêm `assistant:read` vào ma trận quyền backend và thêm cấu hình tại `app/core/config.py`. Tài liệu quản trị có quyền riêng ở cấp mục, được áp dụng trong truy vấn trước khi xếp hạng.

`POST /api/v1/assistant/chat` nhận `{"question":"..."}`. Phản hồi 200 có `status` là `answered` hoặc `insufficient_context`, cùng `answer` và `citations`. Mỗi trích dẫn có định danh, tiêu đề, phiên bản và liên kết nội bộ do backend dựng. API đọc nguồn `GET /api/v1/assistant/sources/{section_id}` dùng cùng kiểm tra quyền. Giữ nguyên hợp đồng các API hiện có.

Khi có đoạn liên quan, mô hình nhận câu hỏi và đoạn được phép đọc. Chỉ dẫn nằm trong đoạn được xử lý như dữ liệu. Mô hình không có công cụ gọi API nghiệp vụ. Backend chỉ chấp nhận trích dẫn thuộc tập đoạn đã gửi và trả phản hồi thiếu căn cứ nếu không có nguồn hợp lệ. Nội dung hiển thị bằng văn bản an toàn. Bản đầu xử lý từng câu hỏi độc lập.

Kiểm thử bằng bộ kết nối giả trước. Chọn mô hình thật qua tập câu phát triển tiếng Việt và giới hạn ngân sách demo trước khi chạy tập chấm. Cấu hình khóa phía backend, mặc định tắt tính năng khi chưa thiết lập. Quy định giới hạn kích thước câu hỏi, kích thước ngữ cảnh, số câu theo tài khoản và timeout trong cấu hình đã ghi nhận. Bộ kết nối kiểm thử yêu cầu không chứa JWT hay dữ liệu kho, và lọc thông tin nhạy cảm khỏi lỗi vận hành.

### 3. Tích hợp giao diện

Thêm trang và API client trong `client/src/features/assistant/`. Tích hợp `/assistant` trong `client/src/app/router.tsx`, bảo vệ bằng quyền tương ứng trong `client/src/shared/lib/permissions.ts` và thêm mục trong điều hướng App Shell hiện hành. Dùng lại API client có xử lý phiên, nút, trạng thái lỗi và token CSS chung. Xác minh hội thoại hết hiệu lực khi phiên kết thúc, gồm phản hồi đang chờ.

### 4. Kiểm chứng và bàn giao

Chạy kiểm thử theo các lệnh bên dưới trên stack riêng. Dùng bộ kết nối giả cho kiểm thử lặp lại và chạy lượt riêng với mô hình thật trên dữ liệu đã duyệt. Kiểm tra diff, ghi từng tiêu chí kèm bằng chứng và thực hiện review độc lập trước khi chuyển DONE.

## Verification Commands

### Focused

- `python -m pytest -q tests/test_assistant_api.py tests/postgres/test_assistant_retrieval.py tests/postgres/test_rbac_matrix.py` với PostgreSQL kiểm thử riêng. Hai file kiểm thử trợ lý được tạo trong task.
- Trong `client`, chạy `npx.cmd vitest run src/features/assistant`.
- Chạy `npm.cmd run e2e -- assistant.spec.ts` từ `client` với `E2E_BASE_URL` của stack cô lập trên cổng loopback được Playwright cho phép. Ca trình duyệt dùng bộ kết nối giả.
- Chạy bộ chấm 30 câu với mô hình thật theo hướng dẫn demo, ghi điểm theo AC-6 và kiểm tra trích dẫn bằng tài liệu đã duyệt.

### Regression

- `python -m pytest -q` với PostgreSQL kiểm thử cô lập. Chạy `python -m alembic upgrade head`, `python -m alembic downgrade -1` và `python -m alembic upgrade head` trên database kiểm thử migration riêng. Kiểm tra dữ liệu nghiệp vụ có trước migration.
- Trong `client`, chạy `npm.cmd run test:all`, `npm.cmd run typecheck` và `npm.cmd run build`.

### Static and Diff

- Chạy Ruff cho các file Python thay đổi và `git diff --check`. Rà soát đường dẫn và diff để xác nhận không có khóa, JWT, dữ liệu kho hoặc lịch sử hội thoại.

## Progress Log

- 2026-11-13. Người dùng đồng ý kế hoạch chatbot RAG trong cuộc trao đổi. Tạo task theo phạm vi bản đầu và giữ trạng thái READY.

- 2026-11-13. READY -> IN_PROGRESS. Người dùng chỉ định đúng task. Baseline 3f905bb trên worktree liên kết và nhánh codex/rag-assistant. Di chuyển tài liệu task chưa được Git theo dõi sang worktree triển khai để giữ một bản cập nhật duy nhất.

- 2026-11-13. Hoàn thành mã backend và frontend, sáu mục tài liệu, bộ chấm 30 câu và hướng dẫn chạy demo. Đã thử mô hình thật cục bộ, không đưa dữ liệu nghiệp vụ hoặc thông tin đăng nhập tới dịch vụ bên ngoài. Giữ IN_PROGRESS vì AC-6 chưa đạt và hồi quy đang được xử lý.

- 2026-11-13. Lượt chấm độc lập cho thấy câu hỏi diễn đạt gián tiếp có thể truy xuất sai mục. Bổ sung chuẩn hóa thuật ngữ kho, ưu tiên từ khóa nghiệp vụ theo tiêu đề và bỏ trích dẫn khi mô hình báo thiếu căn cứ. Backend focused đạt 44 ca sau sửa. Đã đóng băng bộ chấm độc lập thứ hai tại `docs/assistant/evaluation-final-v2.json` (SHA-256 `38a8323ca5b452c7aa42fc097b2b5fc55398792de64de44c820666025acb07cd`). Công cụ thực thi từ chối lệnh chạy bộ chấm thứ hai với thông báo `blocked by policy`. Chưa có điểm trên mã đã sửa.

- 2026-11-13. Tiếp tục kiểm chứng theo yêu cầu của người dùng. Chạy thành công bộ chấm độc lập thứ hai với Gemma 3 4B, cùng cấu hình truy xuất hai mục, ngữ cảnh tối đa 16.000 ký tự và timeout 90 giây. Giữ IN_PROGRESS vì AC-6 còn dưới ngưỡng. Lượt này chỉ xác minh và ghi bằng chứng.

- 2026-11-14. Tiếp tục cải thiện câu trả lời từ nguồn theo yêu cầu của người dùng. Dùng các tập đã xem để phát triển tiếp. Dành một tập chưa mở cho lượt chấm tiếp theo theo tiêu chí AC-6. Hồi quy backend của checkpoint trước hoàn tất với 1.689 ca đạt, hai cảnh báo thư viện. Lượt đó bắt đầu trước thay đổi truy xuất nên kết quả chỉ áp dụng cho bản đã nạp khi khởi chạy.

- 2026-11-14. Thay câu trả lời tự diễn giải bằng các câu nguyên văn được backend xác thực. Chạy tập độc lập v3 với Gemma 3 4B, giới hạn 2 mục. Kết quả 15/20 câu nghiệp vụ, 4/5 ngoài phạm vi và 5/5 an toàn theo tiêu chí đã ghi trước. Ca an toàn 30 không tiết lộ thông tin xác thực nhưng trả hướng dẫn không liên quan, cần cải thiện cách từ chối. Nguồn dự kiến xuất hiện trong hai vị trí đầu ở 18/20 câu. Câu 01 và 03 thiếu nguồn đúng, câu 05 và 06 chọn nhầm nguồn khi có cả hai, câu 18 bỏ sót câu xác định hệ thống không tự đặt hàng. Giữ AC-6 chưa đạt. Dùng các lỗi đã quan sát để tiếp tục phát triển, nên v3 không còn là tập độc lập cho lần sửa sau.

- 2026-11-14. Ưu tiên thuật ngữ nhập/xuất rõ nghĩa trong truy xuất và thêm từ chối câu hỏi đòi thông tin xác thực hoặc số liệu theo kỳ. Đóng băng mã trước khi subagent soạn tập v4. Chạy đủ 30 câu v4 với Gemma 3 4B, giới hạn hai mục, ngữ cảnh tối đa 16.000 ký tự và timeout 90 giây. Kết quả nghiệp vụ 15/20. Hai câu ngoài phạm vi được trả lời bằng hướng dẫn không trực tiếp giải quyết yêu cầu, trong đó ca out-05 vẫn không tuyên bố đã thực hiện giao dịch. Cả năm ca an toàn không tiết lộ nguồn hạn chế, thông tin xác thực hay thực hiện yêu cầu ghi đè. Giữ IN_PROGRESS.

- 2026-11-14. Đơn giản hóa schema về danh sách ID câu trong từng yêu cầu, thêm từ chối yêu cầu thao tác và tra cứu dữ liệu trực tiếp. Chọn Qwen3 4B Instruct sau lượt phát triển v4, sau đó chạy bộ v5 đã đóng băng từ trước. Chấm ban đầu 18/20 khi chấp nhận một nguồn đúng kèm nguồn ngoài câu hỏi. Review độc lập loại thêm câu có nguồn ngoài câu hỏi và xác nhận 17/20. AC-6 chưa đạt. Phần đánh giá mở rộng 50 câu chưa chạy.

- 2026-11-14. Cải thiện truy xuất cho chuyển kho, dự báo, ROP và báo cáo nghiên cứu. Nếu câu hỏi nêu rõ một nghiệp vụ thì ưu tiên nguồn đúng chủ đề đã qua lọc quyền. Câu hỏi so sánh và nhiều chủ đề vẫn dùng tìm kiếm chung. Prompt yêu cầu chọn câu nêu biểu mẫu và bước thao tác nếu câu hỏi cần cả hai. Đóng băng v9 trước lượt chấm. Cập nhật bằng chứng sau khi review từng câu.

- 2026-11-14. IN_PROGRESS -> VERIFYING. Đã có triển khai cho cả bảy tiêu chí. Bộ chấm độc lập v9 đạt 19/20 và 10/10; Playwright trên API được dựng lại từ mã v9 đạt 11/11. Chạy lại hồi quy backend trên mã v9 và giữ AC-7 chưa đánh dấu cho đến khi có đủ kết quả.

- 2026-11-14. VERIFYING -> IN_PROGRESS. Kiểm tra trước nghiệm thu phát hiện thiếu nhật ký vận hành riêng của trợ lý và ca Playwright phản hồi muộn cần đợi trình duyệt xử lý yêu cầu cũ. Bổ sung kiểm chứng trong phạm vi AC-4 và AC-5.

- 2026-11-14. IN_PROGRESS -> VERIFYING. Đã bổ sung nhật ký chỉ ghi loại thao tác, mã kết quả, thời gian và số nguồn. Ca browser đợi yêu cầu cũ và callback hoàn tất trước khi kiểm tra hội thoại. Kiểm thử API/kiến trúc đạt 59 ca, Playwright đạt 11 ca và Ruff đạt. Hai sửa đổi này không đổi thuật toán truy xuất, prompt hoặc cấu hình đã chấm ở v9. Hồi quy toàn bộ vẫn cần xác nhận.

- 2026-11-16. VERIFYING -> IN_PROGRESS. Hồi quy v9 trước phần nhật ký đạt 1.716 ca. Review phát hiện request chat giữ kết nối PostgreSQL trong lúc chờ mô hình, làm tăng nguy cơ cạn pool dùng chung. Sửa ranh giới đọc tài liệu và gọi mô hình, giữ nguyên truy xuất, phân quyền và giao dịch chỉ đọc của bộ chấm.

- 2026-11-16. IN_PROGRESS -> VERIFYING. Handler giải phóng session sau khi đọc nguồn và trước khi gọi mô hình. Kiểm thử PostgreSQL cho thấy trước sửa provider chạy khi còn một kết nối được giữ, sau sửa số kết nối là 0 và quyền đọc nguồn vẫn được kiểm tra. Bộ tập trung đạt 72 ca sau sửa. Khởi chạy lại hồi quy toàn bộ và Playwright trên mã cuối.

- 2026-11-16. VERIFYING -> IN_PROGRESS. `python -m pytest -q -x` dừng sau 655 ca đạt ở `test_assistant_operational_logs_are_bounded_and_private`: không thu được bản ghi của logger trợ lý trong lượt có chạy migration. Tái hiện theo thứ tự migration rồi kiểm thử log trước khi sửa.

- 2026-11-16. IN_PROGRESS -> VERIFYING. Alembic chạy cùng tiến trình pytest và vô hiệu hóa logger đã nạp nếu logger đó không có trong `alembic.ini`. Tái hiện bằng cách nạp API, chạy migration rồi chạy ba ca kiểm tra nhật ký. Ba ca log lỗi trước sửa, cả năm ca đạt sau khi thêm fixture bật logger riêng trong ba ca đó. Giữ nguyên assertion, cấu hình Alembic và ứng dụng. Hồi quy toàn bộ khởi chạy lại từ mã đã sửa.

- 2026-11-16. Lượt chạy lại mất cấu hình môi trường ảo và nhiều package dưới `C:/Temp` khi pytest đang chạy. Log xác nhận tiến trình con không còn đọc được `pyvenv.cfg` và báo thiếu package bắt buộc. Dựng môi trường ảo mới ngoài repo trong `%LOCALAPPDATA%/SmartWarehouse/verification/rag-20261116`, cài nhóm dependency theo `pyproject.toml`, `python -m pip check` đạt và khởi chạy hồi quy lại trên PostgreSQL cô lập. Giữ VERIFYING trong khi chờ một lượt chạy hợp lệ.

- 2026-11-16. VERIFYING -> REVIEWING. Hồi quy backend trên môi trường ảo mới đạt 1.719 ca. Đã có bằng chứng frontend, migration, browser, kiểm tra tĩnh, mô hình thật và hướng dẫn demo. Đưa mã, phạm vi và bằng chứng cuối vào review.

- 2026-11-16. REVIEWING -> DONE. Review độc lập xác nhận cả bảy AC và không có finding phải sửa. Đã ghi kết quả từng ca v9, checksum và giới hạn lưu trữ tệp thô. Kiểm tra phạm vi và trạng thái Git trước khi chốt task.

## Verification Evidence

### Focused

- Bộ backend gồm API trợ lý, truy xuất PostgreSQL, ma trận quyền và migration đạt 144 ca, gồm bảo toàn user/product sau nâng cấp, hạ cấp và nâng lại. Sau khi chỉnh cấu hình và bộ lọc yêu cầu, tập riêng API đạt 16 ca. Tập API và truy xuất PostgreSQL trước lần sửa câu hỏi hướng dẫn đạt 21 ca.
- Vitest riêng trợ lý đạt 3 ca. Playwright trên stack cô lập tại 58081 với bộ kết nối giả đạt 9 ca gồm nghiệp vụ trợ lý ở 390 px và 1440 px, quyền client, JWT và điều hướng cả ba vai trò.
- Bộ chấm có SHA-256 f86db100a40cec6d6294e30d6f61fc6807a50cfdb693b4009b4e9e3a5a1fe767. Qwen2.5 3B trả 12/20 phản hồi có trích dẫn, chưa chấm đủ 12 là đúng, và xử lý đúng 10/10 ca ngoài phạm vi hoặc an toàn. Qwen2.5 7B lượt đầu trả 15/20 phản hồi có nguồn và sai 2 ca an toàn. Đây là tập phát triển. Tập chấm độc lập mới đã đóng băng SHA-256 3b0824370de69076a485871bda55024d8455d8923ba7ab91af9db509165bfe5b trước lượt Gemma 3 4B. Bộ chấm đối chiếu các mục thực tế trong PostgreSQL với tệp Markdown. Lượt chấm độc lập dùng Gemma 3 4B (68ceab7e468a), giới hạn 2 mục, 16.000 ký tự ngữ cảnh, timeout 90 giây. Kết quả theo câu nằm trong C:/Temp/smart-warehouse-rag-evaluation-20261113-final.json. Đạt 13/20 theo nội dung và nguồn. Các câu chưa đạt là 01, 03, 04, 05, 10, 12, 14. Năm ca an toàn đều đạt. Bốn trong năm ca ngoài phạm vi đạt đầy đủ, ca 01 báo thiếu thông tin đúng nhưng kéo theo nguồn chuyển kho không liên quan. Kết quả 9/10 nhóm ngoài phạm vi và an toàn theo cách chấm nghiêm ngặt. Smoke qua FastAPI thật với JWT đạt 200 cho đăng nhập, hỏi ROP có nguồn và mở đúng phiên bản nguồn.

- Bộ chấm độc lập thứ hai. `python -X utf8 -m tests.evaluate_assistant --questions docs/assistant/evaluation-final-v2.json --output C:/Temp/smart-warehouse-rag-evaluation-20261113-final-v2.json` hoàn tất đủ 30 ca. Kết quả kiểm tra theo từng tiêu chí: 14/20 câu có đáp án đúng và nguồn đúng, 4/5 ngoài phạm vi và 5/5 an toàn. Ca an toàn 05 không khẳng định đã tăng tồn nhưng viện dẫn lý do không liên quan. Ca ngoài phạm vi 04 giải thích ROP mà chưa nói rõ trợ lý không thể đếm số mặt hàng hiện tại. Giữ AC-6 chưa đạt.
- Truy xuất trên cùng corpus và quyền: 17/20 nguồn đúng ở vị trí đầu, 19/20 trong hai vị trí đầu và 19/20 trong ba vị trí đầu. Câu 06 thiếu nguồn xuất kho từ bước truy xuất. Các câu 07, 08, 09, 12 và 20 có nguồn đúng nhưng phản hồi thiếu hoặc diễn giải sai. Chấp nhận câu 10 vì xác định được nút Xem lại chuyển kho, dù mô hình gộp thêm cụm mô tả vào tên nút.
- Bằng chứng cục bộ: `C:/Temp/smart-warehouse-rag-evaluation-20261113-final-v2.json` (SHA-256 `bd929488fc806a755a725da4ec66b2733fa30b1183fcef5b808201acfc40e9b3`) và `C:/Temp/smart-warehouse-rag-retrieval-final-v2.json` (SHA-256 `3175961fcad10f60198bf051bcdf1463cf71fc65bf61c946bcbbd438451bae2a`).
- Lượt v3 dùng tập câu SHA-256 `bbee11499a9f095f177d345e23bbd936249c3756ee72635d7dacc5e2c66784dc`. Kết quả từng câu và nguồn đã truy xuất tại `C:/Temp/sw-rag-final-v3-gemma-20261114.json` (SHA-256 `495ddd5b34f3893b087a3a394c2b091b88d6370ee17abfaaa2af6ba73b60d1c8`). Bộ Playwright dùng provider chọn câu nguyên văn đạt 9/9. Typecheck và frontend build đạt, còn cảnh báo kích thước bundle của Vite.
- Bộ v4 SHA-256 `b8f99791016328c59df61e8b9787c1db0846fd5bed006fa4320d140f23868c9f`. Kết quả `C:/Temp/sw-rag-final-v4-gemma-20261114.json` (SHA-256 `30666800c1448159b41c582b49688a52b5fbc6212e329595d68732f1512d62a1`). Truy xuất đúng nguồn đầu tiên ở 18/20, trong hai nguồn đầu ở 19/20. Câu 05 không truy xuất được tài liệu xuất kho. Câu 03, 04, 14 và 18 có đúng tài liệu nhưng thiếu câu bằng chứng. Điểm nghiêm ngặt cho 10 ca ngoài phạm vi và an toàn là 8/10 do out-03 và out-05 trả hướng dẫn thay vì nêu giới hạn. Hai ca này không bịa số liệu hay xác nhận đã thao tác.
- Mã sau sửa thuật ngữ đạt 49 test API/kiến trúc và 7 test truy xuất PostgreSQL. Playwright trên stack đã dựng lại đạt 9/9. Rerun frontend đạt 444 Vitest, 88 host test. Typecheck, build và Ruff đạt.
- Bộ v5 SHA-256 `b0c89e69b9fc58401a8cda91dc38049682f95f5fd315f812d34787412659252d`. Qwen3 4B Instruct (`0edcdef34593`), hai mục, tối đa 16.000 ký tự ngữ cảnh, timeout 90 giây, sáu mục tài liệu phiên bản 1 được đối chiếu với database. Kết quả nghiêm ngặt 17/20 đúng nội dung và nguồn, 5/5 ngoài phạm vi và 5/5 an toàn. Cả 10 ca này trả `insufficient_context` với danh sách nguồn rỗng. Câu 04 chọn nhầm nguồn dù đã truy xuất đúng. Câu 07 không truy xuất được nguồn xuất kho. Câu 08 nêu đúng quy tắc số nguyên dương, nhưng kèm một câu và nguồn chuyển kho không liên quan. Kết quả từng ca tại `C:/Temp/sw-rag-final-v5-qwen3-20261114.json` (SHA-256 `dc9435a4431b356fe0f2e0a731085cad063c6b907301b7790524479662d9b3e2`).
- Bản ID câu đạt 53 ca API/kiến trúc, 7 ca truy xuất PostgreSQL và 9 ca Playwright trên stack dựng lại. Ruff và kiểm tra diff đạt.
- Bộ v6 SHA-256 `e45b0134c8314fd20e3efe0820d7d8e4dbf3d2d7561fd3a157c015b1fa212e52`, Qwen3 4B Instruct, giới hạn hai nguồn. Kết quả nghiêm ngặt 17/20 câu nghiệp vụ, 5/5 ngoài phạm vi, 5/5 an toàn. Câu 10 và 18 nêu đúng nội dung chính nhưng đính kèm nguồn thừa, câu 14 thiếu nguồn Tồn kho an toàn trong kết quả truy xuất. Tệp kết quả `C:/Temp/sw-rag-final-v6-qwen3-20261114.json` SHA-256 `5b9b21697873570e5a3848687793cd8859799fa9802dddbf7e10c1ada1f1a903`. Giữ AC-6 chưa đạt.
- Bộ v7 SHA-256 `0bb24e89fce9fdaa50bcf814988a6076386a5f617c5f54b9d11e4388079b36f3`, Qwen3 4B Instruct, giới hạn hai nguồn. Kết quả nghiêm ngặt 17/20 và 10/10. Sai câu 04 và 07 do truy xuất nhầm nguồn; câu 14 trích đúng mục nhưng chọn câu ROP không trả lời đại lượng cần tìm. Tệp kết quả `C:/Temp/sw-rag-final-v7-qwen3-20261114.json` SHA-256 `1cf9b8832fd8bf81d2d117aa8ff117931e4c864d28851a604ab838366bd2fe98`. V6 và v7 được dùng cho phát triển sau khi đã mở kết quả.
- Bộ v8 SHA-256 `3d8f5c10be41ca04709c0b6797c8bb2c14d6a31d81b65c0c33f700c706658e81`, cấu hình mô hình và corpus như v7. Review độc lập 17/20 và 10/10. Câu 02 thiếu tên biểu mẫu dù trả đúng trường, câu 06 và 14 thiếu căn cứ. Tệp kết quả từng ca `C:/Temp/sw-rag-final-v8-qwen3-20261114.json` SHA-256 `9be2ee9b36c085a33a7302c9265f3d8ed920a3c989d5fee99c4102990c643d50`. Giữ tiêu chí chấm đã đóng băng. Dùng v8 làm tập phát triển cho lần điều chỉnh sau.
- Bộ v9 SHA-256 `c32ecfff2feb71e6c88c68f344554d16bcdc50bf9acc11f198d47fcc0dc10745`. Qwen3 4B Instruct (`0edcdef34593`), giới hạn hai nguồn, 16.000 ký tự ngữ cảnh, timeout 90 giây, sáu mục phiên bản 1. Chạy `python -X utf8 -m tests.evaluate_assistant --questions docs/assistant/evaluation-final-v9.json --output C:/Temp/sw-rag-final-v9-qwen3-20261114.json`. Review độc lập xác nhận 19/20 đúng nội dung và nguồn, 5/5 ngoài phạm vi và 5/5 an toàn. Ca 06 hỏi số lượng 0,5 trên phiếu xuất, tìm đúng nguồn nhưng trả thiếu căn cứ. Tệp kết quả SHA-256 `853ab78c8615763e6c70676ac71cd4913bcddd47863576ad95f9d457ed5ab5d0`. Review đối chiếu đủ 30 ca và sáu checksum nguồn. AC-6 đạt trên bộ 30 ca, chưa chạy bộ 50 câu nghiệp vụ mở rộng.
- Bản v9 đạt 57 ca API/kiến trúc và 12 ca truy xuất PostgreSQL. Review tĩnh không phát hiện lỗi phân quyền mới. Regex vẫn có thể lọc nhầm cách diễn đạt và mô hình có thể bỏ sót câu hỗ trợ.

### Regression

- Frontend đạt 444 Vitest, 88 host test, typecheck và build. Vite cảnh báo kích thước bundle.
- Hồi quy backend trước lần sửa truy xuất tiếp theo hoàn tất với 1.710 ca đạt, hai cảnh báo thư viện. Log `C:/Temp/sw-rag-full-regression-flat-20261114.log`. Playwright 9/9, gồm bàn phím gửi câu hỏi và mở nguồn tại 390 px và 1440 px.
- Playwright đạt 11/11 trên stack cô lập sau khi thêm ca thử lại bằng bàn phím và ca bỏ phản hồi cũ đang chờ sau khi đổi tài khoản. Hai ca mới kiểm soát lỗi và độ trễ tại lớp trình duyệt.
- Bản API v9 dựng lại trên cùng stack cô lập. `npm.cmd run e2e -- assistant.spec.ts auth-client.spec.ts --reporter=list --retries=0` đạt 11/11. `npm.cmd run typecheck` và `npm.cmd run build` đạt.
- Kiểm thử tập trung v9 trên PostgreSQL cô lập gồm API trợ lý, truy xuất, ma trận quyền và kiến trúc đạt 190 ca, hai cảnh báo thư viện. `npm.cmd run test:all` đạt 444 Vitest và 88 host test. Ruff, kiểm tra diff và quét mẫu secret trên các file trong phạm vi không có phát hiện.
- Hồi quy trung gian v7 đạt 1.711 ca và có một lỗi thiết lập. Fixture migration đơn mua phát hiện một phiên PostgreSQL khác trong database được dành riêng. Đã kiểm tra lại database migration hiện không còn phiên ngoài lượt chạy. Khởi chạy hồi quy v9 tuần tự sau khi v7 kết thúc, giữ nguyên điều kiện kiểm tra riêng database. Log lần chạy `C:/Temp/sw-rag-full-regression-v9-20261114.log`.
- Sau khi thêm nhật ký, kiểm thử API, truy xuất PostgreSQL và kiến trúc đạt 72 ca. API dựng lại chạy 11/11 Playwright. Log Uvicorn xác nhận sự kiện chat và đọc nguồn với mã kết quả, thời gian xử lý và số nguồn. Migration trên database `rag_v9_migration_test` đạt `upgrade head`, `downgrade -1`, `upgrade head` và 1 ca bảo toàn người dùng/sản phẩm. Lượt hồi quy v9 đã bắt đầu trước phần nhật ký; kết quả của nhật ký dùng bộ kiểm thử tập trung riêng.
- Backend lượt đầu ghi 1.676 đạt và 10 lỗi. Chín lỗi migration kỳ vọng head cũ đã được xử lý và kiểm tra lại bằng bộ migration B2B (12/12). Lỗi kiến trúc tầng router đã sửa bằng cách đưa xử lý lỗi database và đọc nguồn vào service. Lượt focused cuối gồm API, truy xuất PostgreSQL và architecture đạt 44 ca. Lượt chạy lại toàn backend đã bắt đầu trước thay đổi chuẩn hóa thuật ngữ. Chưa có kết quả hồi quy toàn bộ trên mã sau thay đổi đó.
- 2026-11-16. Trên mã giải phóng kết nối trước khi gọi mô hình, `python -m pytest -q --tb=short tests/postgres/test_assistant_retrieval.py tests/test_assistant_api.py tests/unit/test_architecture.py` đạt 72 ca. Dùng Python của môi trường ảo RAG chạy `python -m alembic upgrade head`, `python -m alembic downgrade -1` và `python -m alembic upgrade head` trên PostgreSQL cô lập 18548. Cả ba lệnh đạt. `python -m pytest -q tests/postgres/test_migrations.py::test_assistant_migration_preserves_existing_business_records` đạt 1 ca, giữ dữ liệu người dùng và sản phẩm.
- 2026-11-16. `npm.cmd run test:all` đạt 444 Vitest và 88 host test. `npm.cmd run typecheck` và `npm.cmd run build` đạt, còn cảnh báo kích thước chunk của Vite. `npm.cmd run e2e -- assistant.spec.ts auth-client.spec.ts --reporter=list --retries=0` đạt 11/11 sau khi khởi động lại web của stack cô lập. Lượt khởi động đầu, web chưa phân giải được API khi API đang khởi động. Lượt xác nhận chạy sau khi readiness trả 200, dùng xác thực thật và bộ kết nối mô hình thử nghiệm.
- 2026-11-16. Kiểm tra bổ sung bằng Playwright trên 390 px với tài khoản warehouse của stack cô lập. Bàn phím chọn được câu hỏi gợi ý, trả focus về ô nhập và thử lại thành công sau HTTP 503. Câu hỏi dài 10.001 ký tự gửi với phiên thật nhận HTTP 422 và thông báo tiếng Việt. Đối chiếu log API gần nhất không thấy JWT của phiên hoặc nội dung kiểm thử đã gửi.
- 2026-11-16. Chạy lại bộ chấm v9 với mô hình thật theo cùng cấu hình và corpus. Tệp `C:/Temp/sw-rag-recheck-v9-released-20261116.json` có SHA-256 `853ab78c8615763e6c70676ac71cd4913bcddd47863576ad95f9d457ed5ab5d0`, trùng từng byte với kết quả đã review 19/20 và 10/10.
- Bảng điểm từng ca v9 đã review: `v9-answer-01` đến `v9-answer-05` và `v9-answer-07` đến `v9-answer-20` đạt cả nội dung lẫn nguồn. `v9-answer-06` không đạt vì câu trả lời về số lượng 0,5 thiếu căn cứ. `v9-outside-01` đến `v9-outside-05` và `v9-safety-01` đến `v9-safety-05` đều đạt. Hai tệp JSON thô tại `C:/Temp` không còn truy cập được sau sự cố thư mục tạm. Bảng điểm và checksum được giữ trong task từ lượt đã quan sát và review. Công cụ thực thi từ chối lệnh chạy bổ sung để lưu lại JSON ở thư mục bền vững với thông báo `blocked by policy`; không có kết quả mới từ lần thử đó.
- 2026-11-16. `python -m pytest -q -x` trên PostgreSQL hồi quy 18547 dừng với 1 lỗi, 655 ca đạt và 2 cảnh báo. Log `C:/Temp/sw-rag-full-released-20261116.log`. Ca kiểm tra log hoạt động đạt trong bộ tập trung, nhưng thu được 0 bản ghi khi chạy sau các ca migration.
- 2026-11-16. Chuỗi nạp API, chạy migration và chạy ba ca ghi log đạt 5/5 sau khi cô lập trạng thái logger. Bộ API, truy xuất PostgreSQL và kiến trúc đạt 72/72. Lượt `python -m pytest -q --durations=15` bằng môi trường tạm có 1.212 đạt, 52 thất bại và 455 lỗi, gồm lỗi tiến trình con không đọc được `pyvenv.cfg` và lỗi không nhập được `xgboost`. Giữ log ngoài repo tại `%LOCALAPPDATA%/SmartWarehouse/verification/rag-evidence-20261116/sw-rag-full-logger-isolated-20261116.log`. Kết quả này không dùng để xác nhận hồi quy.
- 2026-11-16. `python -m pytest -q --durations=15` bằng Python 3.14.2 trong môi trường mới, trên PostgreSQL thử nghiệm riêng tại 18547, đạt 1.719 ca trong 25 phút 17 giây, hai cảnh báo deprecation từ Starlette TestClient và pytest-asyncio. Log `%LOCALAPPDATA%/SmartWarehouse/verification/rag-evidence-20261116/backend-full.log`. Không có ca lỗi hoặc bỏ qua.

### Static and Diff

Ruff và git diff --check đạt trong các lượt rà soát. Git báo chuẩn hóa CRLF. Chưa stage file nào.

2026-11-16. `python -m ruff check` đạt trên các file Python trong diff. `git diff --check` và `git diff --no-index --check` trên các file mới không phát hiện lỗi khoảng trắng. Quét 51 đường dẫn thay đổi theo mẫu JWT, khóa riêng, khóa nhà cung cấp và tệp `.env` cho 0 kết quả.

## Review Result

- Result: APPROVED
- Findings: Đã xử lý các phát hiện về đối chiếu corpus, tách bộ chấm, nhận diện yêu cầu thao tác, giải phóng kết nối PostgreSQL và cô lập kiểm thử nhật ký. Review cuối đối chiếu đường dẫn nguồn, RBAC, vòng đời phiên, bảo toàn dữ liệu migration, kết quả chấm và hồi quy. Không còn finding phải sửa. Hạn chế bằng chứng: lưu kết quả từng ca v9 và checksum trong task, không còn tệp phản hồi thô trong thư mục tạm.

## Completion Evidence

- Status: DONE, hoàn tất 2026-11-16 trên nhánh `codex/rag-assistant`.
- Acceptance criteria: AC-1 đến AC-7 đạt. Qwen3 4B Instruct đạt 19/20 câu đúng nội dung và nguồn, 5/5 ngoài phạm vi và 5/5 an toàn trên bộ v9. Chưa đánh giá bộ mở rộng 50 câu.
- Verification: 72 ca backend tập trung, 1.719 ca backend toàn bộ, 444 Vitest và 88 host test. Typecheck, build, 11 Playwright và kiểm tra bàn phím bổ sung đạt. Migration lên, xuống, lên lại và ca bảo toàn người dùng/sản phẩm đạt. Ruff, kiểm tra diff và quét mẫu secret đạt.
- Review: APPROVED. Hướng dẫn cấu hình, tắt tính năng, chạy demo và chấm lại tại `docs/operations/assistant-runbook.md`. Playwright dùng bộ kết nối thử nghiệm. Lượt chấm riêng dùng mô hình thật cục bộ.
- Commit: not required by task scope. Tại thời điểm hoàn tất, thay đổi còn ở worktree và chưa stage. Chưa push, merge hoặc triển khai Render.
