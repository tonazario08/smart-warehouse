# Bàn giao và checkpoint Git

Tài liệu được tạo theo yêu cầu trực tiếp của người dùng để lưu quy tắc checkpoint. Đọc cùng `AGENTS.md`. Đây không phải executable task, không dùng để chọn task hay thay thế lịch sử, acceptance criteria và evidence trong task chính thức.

## Quy tắc checkpoint

Mỗi commit chứa một thay đổi logic độc lập đã được kiểm chứng. Không cần chờ hoàn thành toàn bộ Phase hoặc milestone, nhưng checkpoint phải giữ được trạng thái nhất quán và các dependency cần thiết; không tách code khỏi test hoặc cấu hình bắt buộc chỉ để chia nhỏ commit.

Chỉ commit khi người dùng cấp quyền rõ ràng cho phạm vi checkpoint. Phê duyệt implementation hoặc yêu cầu tiếp tục không tự động cấp quyền commit. Không tự push, merge, tạo PR hoặc sửa lịch sử Git.

Trước mỗi commit, đọc `git status`, `git diff` và `git diff --staged`; đối chiếu task được chọn, allowlist và thay đổi có sẵn. Kiểm tra cả file untracked dự định đưa vào checkpoint vì chúng chưa xuất hiện trong diff thông thường. Giữ nguyên thay đổi không liên quan hoặc chưa rõ mục đích và báo cụ thể.

Chạy verification phù hợp với đúng phiên bản code chuẩn bị commit. Khi backend và frontend cùng thay đổi, chạy cả `python -m pytest -q` và `npm.cmd run build`, cùng các kiểm tra task yêu cầu. Kiểm tra `git diff --check`. Nếu code đổi sau lần verification, chạy lại kiểm tra bị ảnh hưởng. Không suy diễn browser/Figma verification từ test hoặc build.

Chỉ stage các đường dẫn đã rà soát thuộc checkpoint; kiểm tra lại danh sách staged và toàn bộ staged diff trước commit. Không đưa `.env`, credential, secret, dữ liệu cục bộ, dataset, file `.docx`, dependency cài đặt, cache hoặc build artifact vào checkpoint. Dùng Conventional Commit khi phù hợp với diff thực tế.

Sau mỗi checkpoint, cập nhật task chính thức và tài liệu này với phạm vi, commit hash/subject, verification, trạng thái working tree và việc còn lại. Evidence chi tiết, state transition và acceptance criteria chỉ nằm trong task chính thức; tại đây chỉ tóm tắt và tham chiếu. Commit không tự làm task thành DONE.

Commit hash chỉ được ghi sau khi commit thành công. Nếu cập nhật bàn giao sau commit tạo ra diff tài liệu mới, báo rõ phần chưa commit; không tự amend hoặc tạo thêm commit khi chưa được cấp quyền. Không tuyên bố working tree sạch khi còn thay đổi.

## Thông tin cần ghi sau mỗi checkpoint

Mỗi bản ghi cần có ngày thực hiện, đường dẫn task duy nhất dưới `docs/tasks/`, checkout/worktree và branch hoặc detached HEAD thực tế; commit hash và subject; các file/phạm vi đã commit; lệnh verification và kết quả; thay đổi còn lại cùng blocker hoặc việc tiếp theo; trạng thái quyền commit/push/merge. Không ghi giá trị secret vào bàn giao.

## Bàn giao hiện tại

Task được chọn vẫn là `docs/tasks/build-demand-data-pipeline.md` (M5). Sau phần mở lại đã được duyệt, main đã review độc lập và ghi DONE / APPROVED ngày2026-10-26 cho phạm vi reported-sales hồi cứu; AC1–11 và bằng chứng chi tiết nằm duy nhất trong task chính thức. Đây không phải bằng chứng mô hình dự báo đã được huấn luyện hay đạt hiệu quả, cũng không chứng nhận nhu cầu thực hoặc xuất kho. Không dùng tài liệu bàn giao này để tự đổi trạng thái hoặc chọn task tiếp theo.

Mã M5 nằm trong worktree `C:/Users/TQUOCTOAN/.codex/worktrees/m5-demand-data/smart-warehouse`, nhánh `codex/m5-demand-data`. Checkpoint mã đã tạo ngày2026-10-27: `eb2bf64b0d1a60ed0b16d5774a1517af88c8a5fc`, subject `feat: add validated demand data pipeline`, đúng18 file mã/test/cấu hình M5. Worktree source sạch, artifact dữ liệu vẫn local/ignored. Task chính thức và tài liệu này vẫn ở checkout chính `feat/figma-ui-v2` tại `ed8140e4ce821d6c4108a2227c70a0b571cf3179`, đang chuẩn bị commit tài liệu riêng. Không copy ledger hoặc tích hợp hai checkout.

Bằng chứng hoàn tất26Oct: backend1257/focused355, frontend354+90/typecheck/build và đối chiếu độc lập dữ liệu thật/reuse/legacy đạt. Trước checkpoint27Oct đã chạy mới backend1257 test/478.29s, typecheck/build/Ruff/diff đều đạt; source vẫn đúng manifest đã review. Cảnh báo cũ và giới hạn nguồn được giữ rõ trong task. Không suy diễn browser/Figma/model verification từ test hoặc build; bộ vending mô tả cũ vẫn NOT_FORECAST_READY.

Native giữ SOURCE/ARTIFACT HOLD, không có quyền sửa tiếp;2/3 vòng sửa mới và3/3 vòng cũ giữ nguyên. Người dùng đã duyệt đúng hai commit local: checkpoint mã ở source branch đã tạo, checkpoint chỉ gồm task này và handoff ở checkout chính còn chờ rà soát/stage/commit. Mọi file ngoài phạm vi vẫn được giữ lại, không đưa vào commit. Chưa push, merge, deploy hay tạo M6; không tự thêm commit thứ ba hoặc amend để xử lý metadata bàn giao phát sinh sau commit tài liệu.
