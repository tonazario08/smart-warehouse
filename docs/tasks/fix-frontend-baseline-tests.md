# fix-frontend-baseline-tests — Sửa 2 test frontend fail trên baseline

## Metadata

- Status: DONE
- Phase: P1
- Plan: Báo cáo P0.2 `P0_RUNTIME_VERIFICATION.md` §4.9 và §11 (Task 11); báo cáo P0.1 `P0_FINAL_VERIFICATION.md` §11
- Depends on: none
- Created: 2026-11-25
- Started: 2026-11-25
- Completed: 2026-11-25

## Goal

Điều tra nguyên nhân gốc của 2 test Vitest thất bại đã có sẵn trên baseline và sửa đúng nguyên nhân, để bộ test frontend trở lại xanh trước khi triển khai các task P1 khác.

## Context

- Repo: https://github.com/tonazario08/smart-warehouse, branch `feat/figma-ui-v2`, baseline `7b332d231fad49dcd89f2f3254e1502321087650`.
- P0.2 đã chạy `npx vitest run` 2 lần, kết quả giống hệt: **612 passed / 2 failed, 55 file (53 passed / 2 failed)**; `npm run test:host` 88 passed / 0 failed; typecheck và build PASS.
- 2 test fail:
  1. `src/features/purchaseRequests/PurchaseRequestsPage.test.tsx` — “renders real-shaped scoped admin list with role actions and IDs, not a user-directory call” — `TestingLibraryElementError: Unable to find role="link" and name "PR-0008"`.
  2. `src/features/transfers/TransfersPage.test.tsx` — “applies the shared wrapping pagination layout and usable button height” — `Unable to find role="link" and name "Phiếu chuyển #8"` (`test.tsx:16`).
- Cả hai đều là danh sách không render ra dòng mong đợi trong đúng test case đó, trong khi các test anh em cùng file, cùng mock helper, cùng assert link đó lại PASS (ví dụ `TransfersPage.test.tsx` “shows real paired identities…” PASS với `findByRole('link', {name: 'Phiếu chuyển #8'})`; các test PR khác PASS với `PR-0008`). Khả năng cao là vấn đề test/isolation, không phải list render hỏng toàn cục — cần xác minh, không suy đoán.
- Quyết định đã phê duyệt: D-01 và D-04 tạm giữ hành vi hiện tại, chưa thay đổi chính sách phân quyền nghiệp vụ.

## In Scope

- Điều tra nguyên nhân gốc: test isolation, mock state, pagination, async rendering, hành vi production của 2 trang trên.
- Chỉ sửa code hoặc test sau khi xác định được nguyên nhân.
- Chạy lại toàn bộ Vitest, host test, typecheck và build.

## Out of Scope

- Sửa `navigation.ts` (Task 5, chưa nằm trong P1 này).
- Thay đổi logic nghiệp vụ, RBAC, API contract hoặc thuật toán AI.
- Vô hiệu hóa test, hạ assertion, bỏ qua test lỗi để đạt PASS.
- Sửa các test khác đang pass.

## Acceptance Criteria

- [x] AC-1 — Nguyên nhân gốc của cả 2 test fail đã được xác định bằng bằng chứng (log/render output), ghi trong Progress Log.
- [x] AC-2 — `npx vitest run` đạt 614/614 passed, 55/55 file passed.
- [x] AC-3 — `npm run test:host` vẫn 88/88 passed.
- [x] AC-4 — `npm run typecheck` và `npm run build` exit 0.
- [x] AC-5 — Không test nào bị vô hiệu hóa, không assertion nào bị hạ.

## Verification Commands

### Focused

- `cd client && npx vitest run src/features/purchaseRequests/PurchaseRequestsPage.test.tsx src/features/transfers/TransfersPage.test.tsx`

### Regression

- `cd client && npx vitest run`
- `cd client && npm run test:host`
- `cd client && npm run typecheck`
- `cd client && npm run build`

### Static and Diff

- `git status`
- `git diff`
- `git diff --staged`

## Progress Log

- 2026-11-25 — READY -> IN_PROGRESS. HEAD đã xác minh: `7b332d231fad49dcd89f2f3254e1502321087650`, `git status` chỉ có 4 file task mới (untracked), không có thay đổi nào khác. Bắt đầu điều tra nguyên nhân gốc 2 test fail.
- 2026-11-25 — Chạy focused 2 file: `npx vitest run src/features/purchaseRequests/PurchaseRequestsPage.test.tsx src/features/transfers/TransfersPage.test.tsx` → **19/19 passed** (PR 14 tests, Transfers 5 tests). Cả 2 test fail đều PASS khi chạy riêng → không phải lỗi mock/dữ liệu xác định, mà là phụ thuộc thứ tự/tải khi chạy toàn bộ suite.
- 2026-11-25 — Chạy toàn bộ suite lần 1: `npx vitest run` → **613/614, chỉ 1 fail**: PR `it.each` case `admin` (dòng 9, `findByRole('link', {name: 'PR-0008'})`, thời lượng test 1313ms). Transfers PASS lần này. P0.2 chạy 2 lần đều 612/614 (cả 2 fail); lần này 613/614 (chỉ PR fail) → tập hợp test fail **thay đổi giữa các lần chạy** → flaky theo tải, không phải lỗi xác định.
- 2026-11-25 — Bằng chứng timing: không có timeout tùy chỉnh nào trong `vite.config.ts` (chỉ `environment: jsdom`, `setupFiles: ./src/test/setup.ts`, `include: src/**/*.test.{ts,tsx}`) → `findBy*` dùng mặc định 1000ms của Testing Library. Chuỗi render đầu tiên của 2 trang này là auth `/auth/me` (AuthProvider) rồi mới `Promise.all` (list + products + warehouses) rồi render dòng — dưới tải song song 55 file trên máy 1.5 CPU, chuỗi này mất ~900–1100ms. Test fail có thời lượng 1313ms (vượt ngân sách 1000ms của `findByRole`); test Transfers tương tự mất 1406ms trong cùng lần chạy nhưng PASS (findBy kịp hoàn thành sát nút). 54 test riêng lẻ trong suite mất ≥1000ms tổng thời lượng, cho thấy nhiều test đang chạy sát giới hạn. DOM dump lúc fail chỉ còn sidebar/app-frame, không có error/empty state → trang vẫn đang tải khi hết 1000ms, không phải dữ liệu sai. `management.css` chỉ 4KB nên không phải nguyên nhân (loại trừ giả thuyết stylesheet).
- 2026-11-25 — Đang chạy toàn bộ suite lần 2 (chưa sửa gì) để xác nhận tính flaky trước khi sửa.
- 2026-11-25 — Toàn bộ suite lần 2: **612/614, đúng 2 test fail** — PR case `admin` (1297ms) và Transfers test đầu (1608ms), cả hai đều vượt ngân sách 1000ms của `findByRole`. Tính flaky đã xác nhận qua 4 lần chạy toàn bộ (P0.2 ×2: 612/614; lần 1: 613/614; lần 2: 612/614), tập hợp fail luôn là tập con của 2 test này, luôn là test đầu tiên trong file, luôn tại `findByRole` đầu tiên.
- 2026-11-25 — **Thử sửa toàn cục rồi hoàn tác:** đã thử `configure({ asyncUtilTimeout: 5000 })` trong `src/test/setup.ts`; toàn bộ suite lần 3 cho 613/614 nhưng test fail **đổi sang test khác**: `AuthProvider.test.tsx` — “does not retain a token or user after login fails” (5018ms, `Test timed out in 5000ms`). Nguyên nhân: test đó cố tình dùng `screen.findByText(...).catch(() => undefined)` (dòng 114) để chờ một user không bao giờ load — nó dựa vào timeout mặc định 1000ms để tiếp tục. Nâng toàn cục phá vỡ test này. Đã hoàn tác hoàn toàn `setup.ts` (git diff trống). Kết luận: sửa toàn cục là sai hướng; sửa có mục tiêu tại 2 assertion flaky mới đúng.
- 2026-11-25 — **Sửa có mục tiêu:** thêm `{ timeout: 5000 }` vào đúng 2 `findByRole` flaky (PR `PurchaseRequestsPage.test.tsx:9`, Transfers `TransfersPage.test.tsx:16`), kèm comment giải thích. Không đổi assertion nào, không đổi mock/dữ liệu, không chạm `setup.ts`, `navigation.ts`, logic nghiệp vụ, RBAC hay API contract. Đang chạy verification.
- 2026-11-25 — Verification sau sửa: focused 2 file **19/19 passed**; toàn bộ suite lần 4 **614/614 passed, 55/55 file, exit 0**; toàn bộ suite lần 5 (chạy lại để xác nhận ổn định vì lỗi cũ là flaky) **614/614 passed, 55/55 file, exit 0**. `npm run test:host` **88/88 passed, exit 0**; `npm run typecheck` **exit 0**; `npm run build` **exit 0** (chỉ cảnh báo chunk > 500 kB, đã có từ trước). AC-1..AC-5 đều đạt. Chuyển IN_PROGRESS -> VERIFYING.
- 2026-11-25 — Self-review (người thực hiện): đọc lại `git diff` — chỉ 2 file test thay đổi, mỗi file 1 assertion thêm `{ timeout: 5000 }` + comment; không test nào bị vô hiệu hóa, không assertion nào bị hạ (cùng `findByRole` + cùng `toHaveAttribute`/assert tiếp theo), không file production nào thay đổi, `setup.ts` đã hoàn tác về nguyên trạng, không có gì được stage. Chuyển VERIFYING -> REVIEWING. Lưu ý: đây là self-review của người thực hiện, review độc lập và commit vẫn do parent xử lý.

## Verification Evidence

### Focused

- `cd client && npx vitest run src/features/purchaseRequests/PurchaseRequestsPage.test.tsx src/features/transfers/TransfersPage.test.tsx` (trước khi sửa): **19 passed / 19, 2 file passed**.
- Sau khi sửa (targeted `{ timeout: 5000 }`): cùng lệnh → **19 passed / 19, 2 file passed**.

### Regression

- `cd client && npx vitest run` — trước khi sửa, lần 1: **613/614 (1 failed, PR admin)**; lần 2: **612/614 (2 failed, PR admin + Transfers)**. Sau khi sửa, lần 4: **614/614 passed, 55/55 file, exit 0**; lần 5 (chạy lại để xác nhận ổn định): **614/614 passed, 55/55 file, exit 0**.
- `cd client && npm run test:host`: **88 passed / 0 failed, exit 0**.
- `cd client && npm run typecheck`: **exit 0** (`tsc -b --pretty false`, không lỗi).
- `cd client && npm run build`: **exit 0** (built in 1.57s; chỉ cảnh báo chunk > 500 kB, đã có từ trước).
- Thử sửa toàn cục đã hoàn tác: `configure({ asyncUtilTimeout: 5000 })` trong `src/test/setup.ts` → toàn bộ suite 613/614 với test fail khác (`AuthProvider.test.tsx` “does not retain a token or user after login fails”, 5018ms, test timeout). `setup.ts` đã hoàn tác về nguyên trạng (git diff trống cho file này).

### Static and Diff

- `git rev-parse HEAD`: `7b332d231fad49dcd89f2f3254e1502321087650` (khớp baseline).
- `git status --short`: chỉ 2 file sửa (`M client/src/features/purchaseRequests/PurchaseRequestsPage.test.tsx`, `M client/src/features/transfers/TransfersPage.test.tsx`) + 4 file task mới (untracked). Không có thay đổi nào khác.
- `git diff`: mỗi file test chỉ thêm `{ timeout: 5000 }` vào 1 `findByRole` + comment giải thích (6 dòng thêm mỗi file). Không file production nào thay đổi.
- `git diff --staged`: trống (không stage gì).

## Review Result

- Result: PASSED (independent review by parent)
- Findings: Diff tối thiểu và đúng phạm vi — 2 assertion `findByRole` được thêm `{ timeout: 5000 }` + comment, assertion không đổi, không test nào bị vô hiệu hóa, không mock/dữ liệu nào đổi, không chạm `setup.ts` (đã hoàn tác), `navigation.ts`, logic nghiệp vụ, RBAC hay API contract. Parent đã đọc lại toàn bộ `git diff` và task file, và chạy độc lập toàn bộ Vitest: **614/614 passed, 55/55 file, exit 0** (lần chạy thứ 3 liên tiếp xanh sau sửa, 147.89s). Không có finding bắt buộc nào.

## Completion Evidence

- Independent verification by parent: `cd client && npx vitest run` → **614 passed / 614, 55 passed / 55, exit 0**.
- Executor verification: toàn bộ suite 614/614 ×2 liên tiếp, `npm run test:host` 88/88, `npm run typecheck` exit 0, `npm run build` exit 0.
- AC-1..AC-5 đều đạt. REVIEWING -> DONE ngày 2026-11-25.
