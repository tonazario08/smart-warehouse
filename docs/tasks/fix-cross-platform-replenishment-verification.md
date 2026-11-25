# fix-cross-platform-replenishment-verification — Khắc phục phụ thuộc Windows trong tooling replenishment

## Metadata

- Status: DONE
- Phase: P1
- Plan: Báo cáo P0.2 `P0_RUNTIME_VERIFICATION.md` §6 (RT-02) và §4.1
- Depends on: docs/tasks/normalize-replay-timestamps.md
- Created: 2026-11-25
- Started: 2026-11-25
- Completed: 2026-11-25

## Goal

Khắc phục phụ thuộc Windows trong tooling kiểm thử replenishment để 3 test fail trên Linux pass được, giữ nguyên các biện pháp bảo vệ filesystem path, symlink, database identity và execution lock.

## Context

- Repo: https://github.com/tonazario08/smart-warehouse, branch `feat/figma-ui-v2`, baseline `7b332d231fad49dcd89f2f3254e1502321087650`.
- RT-02 (mới, Low, tooling, P0.2): `tests/run_replenishment_verification.py:496` import `msvcrt` vô điều kiện (module chỉ có trên Windows); `e2e_bind_matches` chỉ chấp nhận đường dẫn Windows Desktop. Trên Linux 3 test không bao giờ pass:
  1. `test_runner_lock_rejects_simultaneous_owner` — `ModuleNotFoundError: No module named 'msvcrt'`.
  2. `test_runner_lock_rejects_dangling_symlink_path` — cùng nguyên nhân `msvcrt`.
  3. `test_e2e_bind_guard_accepts_only_exact_desktop_path` — chỉ chấp nhận đường dẫn kiểu Windows Desktop, fail với `tmp_path` Linux.
- Không ảnh hưởng logic nghiệp vụ; chặn CI Linux cho 3 test này.

## In Scope

- Sử dụng cơ chế khóa phù hợp từng nền tảng (Windows dùng `msvcrt`, Linux dùng cơ chế tương đương, ví dụ `fcntl`).
- `e2e_bind_matches` chấp nhận đường dẫn Linux hợp lệ theo đúng quy tắc bảo vệ hiện có.
- Giữ nguyên các biện pháp bảo vệ filesystem path, symlink, database identity và execution lock.
- Kiểm chứng trên Linux.

## Out of Scope

- Không mở rộng allowlist một cách thiếu kiểm soát chỉ để test PASS.
- Không thay đổi logic nghiệp vụ replenishment, thuật toán AI, kiến trúc hệ thống.
- Không sửa các test khác.

## Acceptance Criteria

- [x] AC-1 — 3 test fail trong P0.2 pass trên Linux.
- [x] AC-2 — Các biện pháp bảo vệ (filesystem path, symlink, database identity, execution lock) vẫn hoạt động: test từ chối đường dẫn/symlink/identity không hợp lệ vẫn pass.
- [x] AC-3 — Không mở rộng allowlist thiếu kiểm soát: chỉ chấp nhận các đường dẫn hợp lệ theo quy tắc đã định.
- [x] AC-4 — Windows NOT VERIFIED (ghi rõ, vì chưa có môi trường Windows để kiểm chứng).

## Verification Commands

### Focused

- `python -m pytest -q tests/test_replenishment_verification.py`

### Regression

- `python -m pytest -q -m "not postgres"`

### Static and Diff

- `git status`
- `git diff`
- `git diff --staged`
- `ruff check app tests`

## Progress Log

- 2026-11-25 — READY -> IN_PROGRESS. HEAD đã xác minh: `8b5ba977e29a767d1dc2fa0439ecf51f36e88d27` (Task 9), `git status` sạch trừ đúng 1 file task này (untracked). Dependencies Task 11, Task 1, Task 9 đều DONE.
- 2026-11-25 — Tái hiện 3 lỗi trên baseline (chưa sửa): `python -m pytest -q tests/test_replenishment_verification.py -k "test_runner_lock_rejects_simultaneous_owner or test_runner_lock_rejects_dangling_symlink_path or test_e2e_bind_guard_accepts_only_exact_desktop_path"` → **3 failed, 61 deselected**. 2 test lock fail với `ModuleNotFoundError: No module named 'msvcrt'` tại `run_replenishment_verification.py:496` (`import msvcrt` vô điều kiện, là câu lệnh đầu tiên trong `execution_lock()` nên cả guard symlink cũng không chạy tới). Test e2e bind fail: `e2e_bind_matches('/tmp/pytest-of-root/pytest-14/test_e2e_bind_guard_accepts_on0/catalog', ...)` trả `False` — hàm chỉ chấp nhận dạng Windows `[A-Za-z]:/.+`.
- 2026-11-25 — Đã đọc các caller của `e2e_bind_matches` (dòng 1453, 1704, 1794, 1799): đều so sánh `mount["Source"]` từ Docker inspect với đường dẫn kỳ vọng. Trên Linux Docker, Source là đường dẫn POSIX của host; trên Docker Desktop Windows là dạng `C:\...` hoặc `/run/desktop/mnt/host/c/...`. Nhánh POSIX là trường hợp production thật trên Linux, không phải nới lỏng cho test.
- 2026-11-25 — Thiết kế sửa (tối thiểu, giữ nguyên nhánh Windows): (1) `execution_lock()` dùng helper `_acquire_execution_lock`/`_release_execution_lock` rẽ nhánh theo `os.name`: Windows giữ `msvcrt.locking` (LK_NBLCK/LK_UNLCK), Linux dùng `fcntl.flock` (LOCK_EX|LOCK_NB / LOCK_UN). Import `msvcrt`/`fcntl` lazy trong helper nên module import được trên cả hai nền tảng. Guard symlink/reparse-point hiện có giữ nguyên và chạy trước khi khóa. (2) `e2e_bind_matches` giữ nguyên nhánh Windows (kể cả dịch tiền tố Docker Desktop `/run/desktop/mnt/host/`, `/host_mnt/`), thêm nhánh POSIX cho source bắt đầu bằng `/`: từ chối mọi thành phần rỗng/`.`/`..`/chứa `:` trước khi so sánh (nên `.../catalog/../catalog` vẫn bị từ chối dù normpath sẽ trùng), so sánh bằng `posixpath.normpath` phân biệt hoa/thường, không dùng `ntpath.normcase`.
- 2026-11-25 — Đã triển khai: chỉ sửa `tests/run_replenishment_verification.py` (+49/−10, 1 file): thêm `import posixpath`, 2 helper khóa theo nền tảng, `execution_lock()` gọi helper, `e2e_bind_matches` thêm nhánh POSIX. Không sửa file test, không sửa logic nghiệp vụ replenishment, không đổi assertion nào.
- 2026-11-25 — Verification sau sửa: focused file **64 passed** (trước: 61 passed + 3 failed); kiểm tra biên `e2e_bind_matches` 12 trường hợp đều đúng; khóa liên-process: process con giữ lock → process cha nhận `GuardError RUNNER_BUSY`, lock giải phóng sau khi con thoát; ruff pass; regression non-postgres **1225 passed, 0 failed, 16 skipped, 302 errors** (P0.2: 1222 passed, 3 failed, 302 errors) — 302 errors đã xác minh là lỗi môi trường có sẵn (`TEST_DATABASE_URL must name a database ending in _test`), giống hệt P0.2, không phải do task này. Chuyển IN_PROGRESS -> VERIFYING.
- 2026-11-25 — Self-review (người thực hiện): đọc lại toàn bộ `git diff` — nhánh Windows của `e2e_bind_matches` giữ nguyên logic từng byte (chỉ đổi cấu trúc `if not ...: return False` thành `if ...:`); nhánh POSIX từ chối `..` trước khi normpath, so sánh phân biệt hoa/thường, cùng quy tắc `:`; helper khóa import lazy, hành vi Windows không đổi, flock non-blocking nên lock lồng nhau trong cùng process vẫn raise RUNNER_BUSY; không có file nào ngoài `tests/run_replenishment_verification.py` thay đổi; không có gì được stage. Windows vẫn NOT VERIFIED (không có môi trường Windows). Chuyển VERIFYING -> REVIEWING. Lưu ý: đây là self-review của người thực hiện, review độc lập và commit vẫn do parent xử lý.

## Verification Evidence

### Focused

- `python -m pytest -q tests/test_replenishment_verification.py` (trước khi sửa): 61 passed + 3 failed (3 test RT-02). Sau khi sửa: **64 passed, 0 failed, 1 warning (Starlette/httpx deprecation có sẵn), 4.02s**.
- Kiểm tra biên `e2e_bind_matches` bằng script tạm ngoài repo (12 trường hợp, đều đúng): khớp chính xác POSIX → True; hậu tố `-other` → False; `..` (`catalog/../catalog`) → False; `/host_mnt/unknown` → False; sai hoa/thường → False; trailing slash → False; thành phần chứa `:` → False; `//` → False; thành phần `.` → False; non-string → False; NUL byte → False; dạng Windows `C:/work/catalog` so với expected POSIX → False.
- Khóa liên-process (script tạm): process con giữ `execution_lock()` 3s → process cha gọi `execution_lock()` nhận `GuardError RUNNER_BUSY`; sau khi con thoát, cha acquire lock thành công.

### Regression

- `ruff check app tests`: **All checks passed!**
- `python -m pytest -q -m "not postgres"`: **1225 passed, 16 skipped, 372 deselected, 13 warnings, 302 errors in 807.15s**. So với P0.2 (1222 passed, 3 failed, 16 skipped, 302 errors): +3 passed đúng bằng 3 test đã sửa, 0 failed mới. 302 errors đã xác minh bằng 1 test mẫu (`tests/postgres/test_warehouses.py::test_warehouse_delete_in_use_preserves_each_reference[inbounds]` → `TEST_DATABASE_URL must name a database ending in _test`): lỗi môi trường có sẵn do chạy không có `TEST_DATABASE_URL`, giống hệt P0.2, không liên quan task này.
- Các test guard trong focused file vẫn pass (AC-2): `test_runner_lock_rejects_dangling_symlink_path` (symlink → OUTPUT_INVALID), `test_e2e_bind_guard_accepts_only_exact_desktop_path` (4 assert từ chối), cùng toàn bộ 64 test của file.

### Static and Diff

- `git rev-parse HEAD`: `8b5ba977e29a767d1dc2fa0439ecf51f36e88d27` (khớp Task 9).
- `git status --short`: chỉ `M tests/run_replenishment_verification.py` + 1 file task này (untracked). Không có thay đổi nào khác.
- `git diff --stat`: 1 file, 49 insertions, 10 deletions.
- `git diff --staged`: trống (không stage gì).

### Focused

### Regression

### Static and Diff

## Review Result

- Result: SELF-REVIEWED (người thực hiện tự review; review độc lập và commit do parent xử lý)
- Findings: Diff tối thiểu và đúng phạm vi — 1 file `tests/run_replenishment_verification.py` (+49/−10): nhánh Windows của `e2e_bind_matches` giữ nguyên logic, nhánh POSIX mới áp cùng quy tắc bảo vệ (từ chối rỗng/`.`/`..`/`:` trước khi so sánh, so sánh phân biệt hoa/thường); helper khóa rẽ nhánh theo `os.name`, Windows không đổi, Linux dùng `fcntl.flock` non-blocking. Không sửa file test, không đổi assertion, không chạm logic nghiệp vụ replenishment. Verification đầy đủ: focused 64/64, regression non-postgres 1225 passed / 0 failed (302 errors môi trường có sẵn, đã xác minh), ruff pass. Windows NOT VERIFIED (không có môi trường Windows).

## Completion Evidence

- Task file Status: REVIEWING (từ VERIFYING sau self-review). Không đánh dấu DONE (parent quyết định và commit).
