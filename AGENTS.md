# Git và GitHub Rules

Áp dụng các quy tắc này trước mọi thao tác Git hoặc GitHub trong repository.

## 1. Nguyên tắc chung

- Mỗi task nên tạo một logical checkpoint riêng khi có thể.
- Commit phải phản ánh đúng thay đổi thực tế trong repository.
- Không commit code chưa được verification phù hợp.
- Không tự ý thay đổi lịch sử Git.
- Không tự ý push, tạo Pull Request hoặc thao tác trên remote nếu chưa được yêu cầu.
- Không đưa secret, credential hoặc dữ liệu cục bộ vào repository.
- Không sửa unrelated code chỉ để tạo một commit "đẹp" hơn.
- Không gom nhiều task không liên quan vào cùng một commit nếu có thể tách riêng.

## 2. Task routing

- Mọi implementation phải được yêu cầu bằng đúng một đường dẫn task rõ ràng bên dưới `docs/tasks/`.
- Đường dẫn thiếu, mơ hồ, không tồn tại, nằm ngoài `docs/tasks/`, hoặc trỏ đến template sẽ chặn mọi sửa đổi project; yêu cầu người dùng cung cấp một đường dẫn duy nhất.
- Khi routing, chỉ đọc task đã chọn, các dependency được khai báo rõ ràng, cùng plan/spec/rules ổn định mà chúng tham chiếu.
- Không suy luận task bằng cách quét trạng thái, số thứ tự plan, thời gian sửa file, hay chọn task chưa hoàn thành đầu tiên.
- Mỗi dependency phải là một đường dẫn task tường minh và phải `DONE` trước `READY -> IN_PROGRESS`.
- Kiểm tra plan authority, plan chứa task identifier, stable specification liên quan, scope, acceptance criteria, và verification commands trước khi bắt đầu.
- File task được chọn là nguồn duy nhất cho lịch sử, state transition, evidence, review, và completion; chỉ file này được cập nhật.
- File shared-task legacy trong `docs/plans/` không được đọc, cập nhật, hoặc dùng để routing.

## 3. State-aware execution

- `READY`: sau khi dependency, plan/spec và execution baseline hợp lệ, bắt đầu và ghi `READY -> IN_PROGRESS`.
- `IN_PROGRESS`: chỉ tiếp tục implementation của task đã chọn theo baseline đã đóng băng và progress history append-only.
- `VERIFYING`: chỉ tiếp tục verification; thay đổi implementation cần ghi `VERIFYING -> IN_PROGRESS` trước.
- `REVIEWING`: chỉ thực hiện independent review; finding bắt buộc ghi `REVIEWING -> IN_PROGRESS` trước implementation.
- `DONE`: báo completion evidence hiện có và không chạy lại nếu không có yêu cầu riêng, tường minh về công việc mới.

Chuỗi đi tới duy nhất là `READY -> IN_PROGRESS -> VERIFYING -> REVIEWING -> DONE`. Chỉ hai chuyển trạng thái lùi hợp lệ là `VERIFYING -> IN_PROGRESS` và `REVIEWING -> IN_PROGRESS`; failure verification hoặc review phải trở về `IN_PROGRESS`. Không đủ evidence là `NOT VERIFIED`, không phải `DONE`.

## 4. Baseline và execution model

- Khi task vào `IN_PROGRESS`, đóng băng `Goal`, `Context`, `In Scope`, `Out of Scope`, `Acceptance Criteria`, và `Verification Commands`.
- Chỉ thay đổi baseline sau phê duyệt rõ ràng của người dùng và scope amendment được append vào `Progress Log`, nêu lý do, approver, và ngày.
- Repository dùng Model A: một milestone tương ứng đúng một executable task; workstream nội bộ không có task identifier riêng.
- Mặc định strict single-task execution: chỉ một executable task được implementation tại một thời điểm. Multi-task chỉ hợp lệ khi một rule được phê duyệt riêng định nghĩa điều phối đầy đủ.
- Stable task path không được đổi sau `IN_PROGRESS` nếu không có phê duyệt rõ ràng và migration evidence.

## 5. Trước khi commit

Trước mọi `git commit`, bắt buộc kiểm tra:

```bash
git status
git diff
git diff --staged
```

## Before committing

- Inspect `git status`, the staged diff, and the unstaged diff before choosing a commit message.
- Base the commit message on the actual changes, not on a generic task title.
- Use a concise Conventional Commit prefix when it accurately describes the change, such as `feat:`, `fix:`, `docs:`, `test:`, `build:`, or `chore:`.
- Run the relevant verification command for changed code. Run both `python -m pytest -q` and `npm.cmd run build` when backend and frontend change together.
- Do not stage or commit `.env`, credentials, tokens, private keys, `node_modules`, build artifacts, caches, virtual environments, or generated local data.
- Review the staged file list after `git add` and before `git commit`.

## Before publishing to GitHub

- Inspect the current branch and `git remote -v` before pushing.
- Push only to a configured, explicitly intended remote and branch.
- Never force-push, delete branches, rewrite history, change repository visibility, or create a pull request unless the user explicitly requests that action.
- After a successful push or pull request creation, report the commit hash and the resulting remote URL or pull request URL.

## Commit handoff

- Report the verification commands run and their results.
- Report the commit hash, subject, and whether the working tree is clean.
