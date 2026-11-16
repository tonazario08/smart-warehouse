# Task: Cảnh báo bổ sung hàng trên màn hình kết quả mô phỏng

- **Task path (duy nhất):** `docs/tasks/implement-replenishment-alerts.md`
- **Task identifier:** `implement-replenishment-alerts`
- Status: DONE
- Phase: Cảnh báo bổ sung hàng cho demo
- Plan: docs/tasks/implement-replenishment-alerts.md#implementation-plan
- Depends on: docs/tasks/implement-replenishment-policy.md
- Created: 2026-11-16
- Started: 2026-11-16
- Completed: 2026-11-16
- **Scope authority:** Goal, In scope, Out of scope and Acceptance criteria in this task (confirmed 2026-11-16).
- **Execution baseline:** frozen when the task entered `IN_PROGRESS` on 2026-11-16; unchanged.

## Goal

Chỉ bổ sung **cảnh báo tham khảo cho demo** ngay trên trang `client/src/features/replenishment/ReplenishmentRunPage.tsx`. Đọc tồn kho bằng API hiện có; chỉ đối chiếu một **ROP (reorder point) của ngày mô phỏng được chỉ rõ** với số tồn hợp lệ khi đồng nhất **SKU, kho và đơn vị tính**. Khi tồn kho **nhỏ hơn hoặc bằng ROP**, hiển thị lời nhắc **"Đề xuất xem xét bổ sung"**, không biến thành đơn đặt hàng hoặc mệnh lệnh vận hành. Chỉ nêu lượng đặt tham khảo nếu EOQ hợp lệ. Ghi rõ dữ liệu fixture/demo và lead time giả định.

## Context / evidence từ các file đã nhận

- Trang chi tiết hiện có bộ chọn `algorithm`, `horizon` (lead time 1 hoặc 7 ngày), `service`, `policy` và `page`; có bảng so sánh tổng hợp (`rop_min`, `rop_max`) và bảng diễn biến theo ngày (`reorder_point`).
- `GET /replenishment/runs/{run_id}` trả `manifest`, `calibration`, `summaries`, `applicability`, `fixture_label`, `entity`. Backend `ReplenishmentService._view` chỉ đính kèm `entity` khi binding có `product_id`, `warehouse_id` và kiểm tra `product.unit == binding.unit`; `entity` ở backend có thêm `product_id`, `warehouse_id`, `sku`, `warehouse_code` nhưng TypeScript `ReplenishmentRun.entity` chưa khai báo ID.
- `GET /replenishment/runs/{run_id}/days` trả `reorder_point` theo **từng ngày** và từng tổ hợp bộ lọc; bảng `rop_min`/`rop_max` là khoảng của nhiều ngày, không phải một ROP có thể đối chiếu trực tiếp.
- API inventory hiện có `GET /stock` với bộ lọc `product_id`, `warehouse_id`, phân trang và `StockRow { product_id, warehouse_id, quantity, created_at }`. `StockRow` không chứa đơn vị; việc xác minh đơn vị cần thông tin sản phẩm từ API danh mục hiện hữu hoặc nguồn đáng tin cậy khác đã có trong frontend.
- `ReplenishmentMode` phân biệt `operational` với `research`; `applicability` phân biệt `fixture_scenario` với `research_scenario`. **Không dùng ROP nghiên cứu tổng hợp công ty để cảnh báo theo tồn của một kho**.
- `calibration.eoq` hiện có `quantity`, `raw`, `reason_code`; giá trị `quantity = 0` hoặc giá trị thiếu không phải lượng đặt nên hiển thị.

## In scope

1. **Chỉ sửa frontend trên trang chi tiết đã có** và các helper/test/style tối thiểu cần thiết trong cùng feature. Giữ nguyên bộ chọn và bảng hiện có; cảnh báo chỉ đọc, không phát sinh thao tác nghiệp vụ.
2. **Ưu tiên tái sử dụng API**: dùng `GET /stock?product_id=...&warehouse_id=...` qua API/client đang dùng, cùng endpoint tra cứu sản phẩm/kho nếu cần xác minh SKU và đơn vị. Kiểm tra cơ chế token, phân quyền, `ApiClient`/`request` và dạng phản hồi trước khi nối hai feature; **không thêm backend endpoint** nếu API hiện tại đáp ứng.
3. **Guard bắt buộc trước khi đối chiếu:**
   - Run là fixture/demo thuộc kho cụ thể: `manifest.mode === 'operational'`, `manifest.dataset_class === 'fixture'`, `applicability === 'fixture_scenario'`, `manifest.reporting_scope === 'warehouse'`, `entity`/binding tồn tại và đáng tin cậy.
   - Đối chiếu `product_id`, `warehouse_id` ở kết quả replenishment với **từng StockRow** được API trả về, không chỉ tin vào tham số lọc; xác thực SKU theo dữ liệu sản phẩm hiện tại và `entity.sku`, kho theo ID (và mã kho nếu nguồn hiện có hỗ trợ), đơn vị `manifest.unit`/binding với `product.unit` và đơn vị tồn kho thực tế. Không tự quy đổi đơn vị.
   - Tồn kho và ROP phải là số hữu hạn, không âm; tồn không được mặc định là 0 khi API trả trống. Nếu response có nhiều bản ghi mà chưa xác định được chính xác một snapshot duy nhất, **không cộng/trừ hoặc chọn đại**.
   - Lấy ROP của **một `SimulationDay` hợp lệ, không phải warmup**, tương ứng đúng bộ lọc `algorithm`, `horizon`, `service`, `policy` đang hiển thị. Hiển thị **ngày của ROP tham chiếu**. Nếu dùng ngày trên trang diễn biến đang mở, cảnh báo phải cập nhật hoặc vô hiệu hóa khi người dùng đổi trang/bộ lọc; tuyệt đối không dùng `rop_min`/`rop_max` thay cho ROP ngày.
   - Chặn so sánh khi dữ liệu mất liên kết, lỗi quyền, thiếu xác minh SKU/kho/đơn vị, ngày/ROP thiếu hoặc API lỗi; hiển thị trạng thái **"Thiếu dữ liệu để đối chiếu"** và lý do phù hợp. Trong thời gian tải, hiển thị trạng thái đang kiểm tra, không chớp cảnh báo dựa vào dữ liệu cũ.
4. **Hiển thị trạng thái:**
   - `on_hand <= ROP`: **"Đề xuất xem xét bổ sung"** kèm tồn, ROP, SKU/kho/đơn vị đã xác minh và ngày mô phỏng tham chiếu.
   - `on_hand > ROP`: **"Tồn kho trên ngưỡng ROP tham chiếu"**, không gợi ý đặt hàng.
   - Thiếu căn cứ so sánh: **"Thiếu dữ liệu để đối chiếu"**, không suy diễn khuyến nghị.
   - Nếu đang ở run nghiên cứu, nêu **"Kịch bản nghiên cứu — không đối chiếu với tồn kho"** thay vì báo bổ sung.
5. **EOQ:** chỉ hiển thị `"Lượng đặt tham khảo theo EOQ"` trong cảnh báo chạm/dưới ngưỡng khi EOQ có `quantity` là số nguyên dương hữu hạn và không có `reason_code` lỗi; ngoài ra ẩn con số, có thể ghi "Chưa đủ cơ sở hiển thị lượng đặt". Không thay thế EOQ bằng số lượng từ diễn biến mô phỏng.
6. **Disclosure bắt buộc:** ngay cạnh cảnh báo ghi rõ **"Dữ liệu demo/fixture, chỉ dùng trình diễn; lead time X ngày là giả định của kịch bản; ROP thuộc ngày mô phỏng, không phải ngưỡng đã phê duyệt cho vận hành thực tế."** Dùng đúng lead time người dùng đang chọn. Thay đổi lựa chọn phải làm mới đánh giá; không giữ kết quả cũ.
7. **Không làm lộ dữ liệu:** tuyệt đối không đưa `.env`, token, credentials, dữ liệu kho thật hoặc log phản hồi thật vào patch, test fixture, ảnh chụp hay tài liệu. Test chỉ dùng dữ liệu giả lập.

## Out of scope

- Không tạo/sửa đơn đặt hàng, nhập/xuất kho, tồn kho hoặc chạy lại tính toán ROP/EOQ ở backend.
- Không tạo API mới, không thay chính sách replenishment, không sửa thuật toán simulation, không mở rộng quyền truy cập.
- Không lấy ROP nghiên cứu / `company_aggregate` làm ngưỡng cho SKU/kho thật.
- Không xây dashboard hoặc cảnh báo nền, lịch chạy tự động, thông báo push/email.
- Không sửa code ngoài phạm vi task, không `git commit`, `push`, mở PR hay chỉnh lịch sử Git nếu chưa được yêu cầu riêng.

## Acceptance criteria

- [x] Cảnh báo chỉ xuất hiện trong màn hình `ReplenishmentRunPage` hiện hữu, không thêm route hay tác vụ backend.
- [x] Từ một fixture run có binding đầy đủ, các kiểm tra SKU, kho và đơn vị phải **đồng thời** thành công trước khi lấy tồn so ROP.
- [x] ROP đúng case/ngày mô phỏng được hiển thị, không lấy min/max hoặc ROP từ research run làm ngưỡng.
- [x] Tồn **bằng** ROP và **dưới** ROP đều hiển thị "Đề xuất xem xét bổ sung"; **trên** ROP không hiển thị đề xuất đó.
- [x] Thiếu hàng tồn, ROP, EOQ, đơn vị, binding hoặc truy cập API không hợp lệ được xử lý fail-closed; EOQ thiếu không cản trở đánh giá ngưỡng khi tồn/ROP vẫn đủ căn cứ.
- [x] SKU không khớp, kho không khớp hoặc đơn vị khác đều **không** có khuyến nghị; xác minh lại dữ liệu API trả về.
- [x] Chỉ hiển thị số lượng EOQ nếu là số nguyên dương hữu hạn và hợp lệ; không coi EOQ=0 là lượng đặt.
- [x] UI ghi rõ fixture/demo, ngày ROP tham chiếu, lead time **giả định** và tính chất chỉ tham khảo.
- [x] Đổi case, lead time, trang, run hoặc session không hiển thị nhầm cảnh báo/stock của lượt tải trước.
- [x] Test tự động và build frontend chạy thành công trong repo thật; ghi kết quả và evidence trong task.

## Verification commands (đề xuất; xác minh scripts trong `client/package.json` trước khi chạy)

```bash
cd client
npm.cmd run test:all
npm.cmd run typecheck
npm.cmd run build
```

Bộ test tối thiểu (mock API, không chứa dữ liệu kho thật): `stock == ROP`, `stock < ROP`, `stock > ROP`, thiếu stock, thiếu ROP/trace, sai SKU, sai warehouse ID, sai đơn vị, run nghiên cứu, EOQ=0/null/bất hợp lệ, thay đổi lead time/filters không dùng state cũ, API từ chối hoặc lỗi.

## Implementation plan

Plan đề xuất cho `implement-replenishment-alerts`.

1. Kiểm tra task, phạm vi đã xác nhận, dependency và thay đổi hiện có theo `AGENTS.md`.
2. Nối trang chi tiết mô phỏng với API đọc tồn và danh mục hiện có. Dùng chung kiểm tra liên kết để quyết định gọi API, chờ dữ liệu và đối chiếu ROP.
3. Chạy test và thử trên stack demo cục bộ có bản mô phỏng gắn đúng SKU, kho, đơn vị. Xác nhận ngày ROP tham chiếu, dữ liệu demo và lead time giả định. Ghi kết quả thực tế và review.

## Progress log (append-only)

- **2026-11-16 — DRAFT (task authored):** soạn task theo yêu cầu người dùng và 12 source files trong `feat-01.zip`, cùng `AGENTS.md`; chưa có plan authority/stable spec; chưa chuyển state, chưa sửa code và chưa chạy kiểm thử trên repository. **Evidence:** task draft này. **Verification:** NOT VERIFIED.
- **2026-11-16 — READY:** routing/baseline verified in worktree `codex/rag-assistant`: task path exists after bundle apply, plan authority is this task's `#implementation-plan`, dependency `docs/tasks/implement-replenishment-policy.md` is `DONE`, Goal/In scope/Out of scope/Acceptance Criteria/Verification Commands are complete and frozen unchanged. Authority: user explicitly requested implementation of this exact task path with the attached patch, keeping existing RAG changes. **Verification:** `git apply --check --whitespace=error` passed before apply.
- **2026-11-16 — IN_PROGRESS:** bundle patch applied unchanged (7 frontend files + this task). Baseline frozen; no scope amendment. Existing uncommitted RAG changes left untouched. **Verification:** pending test/typecheck/build and real-API demo run.
- **2026-11-16 — VERIFYING:** frontend suite, typecheck and build passed; local demo stack with real API returned the expected alert states for equal/below ROP, above ROP and missing stock. **Verification:** see Verification evidence; independent review still pending, so state stays `VERIFYING`, not `DONE`.
- **2026-11-16 — VERIFYING -> IN_PROGRESS:** Review phát hiện ca đổi lead time hoặc trang có thể dùng tồn của lượt tải trước, ca quay lại run có thể hiện kết quả cũ trước khi tải xong, và lỗi liên kết 409 chưa hiện thông báo thiếu dữ liệu trong cảnh báo. Sửa trong phạm vi frontend đã đóng băng.
- **2026-11-16 — IN_PROGRESS -> VERIFYING:** Dữ liệu tồn và ROP thuộc cùng lượt tải chi tiết và cùng lựa chọn. Đổi bộ lọc hoặc trang đọc lại tồn. Lỗi 409 báo thiếu dữ liệu, và lỗi đọc tồn được ưu tiên khi ROP vẫn chờ. Bốn ca giao diện tái hiện lỗi trước sửa, bộ tập trung đạt 25 ca sau sửa.
- **2026-11-16 — VERIFYING -> REVIEWING:** Frontend chạy lại toàn bộ, typecheck và build đạt. Dựng lại web của stack demo, kiểm tra đường dẫn chi tiết trả HTTP 200, API sẵn sàng và tồn kho thuộc dữ liệu demo vẫn là 2.
- **2026-11-16 — REVIEWING -> DONE:** Review độc lập xác nhận các phát hiện đã được xử lý, không còn lỗi cần sửa trong phạm vi demo. Đã đối chiếu 10 tiêu chí, kết quả test và diff. Chưa stage, commit, push hoặc deploy lên Render.

## Verification evidence

- **Hồi quy lỗi giao diện:** Bốn ca với ID sản phẩm hoặc kho bằng 0 hay âm thất bại trước khi dùng chung phép kiểm tra liên kết. Sau sửa, giao diện báo thiếu dữ liệu và cả bốn ca đạt.
- **Bản vá:** `git apply --check --whitespace=error` đạt, sau đó `git apply` áp dụng đúng 7 file frontend và task này. Các thay đổi RAG chưa commit trong worktree `codex/rag-assistant` được giữ nguyên.
- **Frontend (2026-11-16, worktree thật):** `npm.cmd run test:all` đạt 463 Vitest (50 file) và 88 host test; `npm.cmd run typecheck` đạt; `npm.cmd run build` đạt (Vite còn cảnh báo chunk > 500 kB).
- **Tích hợp API thật (2026-11-16):** stack demo cục bộ `sw-alerts-demo` (Postgres + API + web build từ worktree) đọc catalog fixture `rrv1-7833aac…` với binding `product_id=1, warehouse_id=2, unit=unit`.
  - `on_hand = 2`, ROP ngày `2022-07-08` = 2 (lead time 1) → UI hiện “Đề xuất xem xét bổ sung”, EOQ 86.
  - Đổi lead time sang 7 → ROP 14, cảnh báo tự đánh giá lại, không dùng ROP cũ.
  - `on_hand = 20` → UI hiện “Tồn kho trên ngưỡng ROP tham chiếu”, không hiện lượng đặt EOQ.
  - Xoá bản ghi tồn → UI hiện “Thiếu dữ liệu để đối chiếu. Không xác định được đúng một bản ghi tồn kho.” (fail-closed).
  - Đã khôi phục `on_hand = 2` để quay video.
- **Sau sửa vòng đời dữ liệu (2026-11-16):** `npx.cmd --no-install vitest run src/features/replenishment/alert.test.ts src/features/replenishment/ReplenishmentRunPage.test.tsx` đạt 25/25. `npm.cmd run test:all` đạt 466 Vitest (50 file) và 88 host test, không lỗi hoặc bỏ qua. Typecheck, build và `git diff --check` đạt, còn cảnh báo chuẩn hóa CRLF và kích thước chunk.
- **Kiểm tra stack sau sửa:** Dựng lại riêng web `sw-alerts-demo` trên `127.0.0.1:58080`. Đường dẫn kết quả trả HTTP 200 với bundle `index-L9dVzEcq.js` mới, API readiness trả `ready`; truy vấn chỉ đọc xác nhận tồn 2 đúng binding. Các thao tác cảnh báo bằng trình duyệt với phiên đã đăng nhập là bằng chứng của lượt demo trước sửa; hậu kiểm bản sửa dùng ca hồi quy frontend và kiểm tra readiness. Không chạy Playwright với API thật trong lượt sau sửa.

## Review Result

- Result: APPROVED
- Findings: Đã xử lý tồn cũ khi đổi lựa chọn, hiện thoáng dữ liệu cũ khi quay lại kết quả, và trạng thái thiếu dữ liệu khi gặp lỗi mất liên kết. Review lại xác nhận lượt tải được khóa theo kết quả chi tiết và lựa chọn đang xem. Không còn finding bắt buộc.

## Completion Evidence

- Status: DONE, hoàn tất 2026-11-16. Đạt 10/10 tiêu chí trong phạm vi cảnh báo tham khảo cho demo.
- Verification: 25/25 test tập trung, 466 Vitest, 88 host test, typecheck, build, kiểm tra diff và stack demo HTTP/readiness đạt. Kiểm tra trình duyệt với API thật được ghi riêng từ lượt trước sửa. Review độc lập APPROVED.
- Demo: [Chi tiết kết quả bổ sung hàng](http://127.0.0.1:58080/replenishment/runs/rrv1-7833aac3f3e1ed9595cb419a261cf70031fd2849253441054d9adf930fad09fe). Tồn demo hiện là 2. So sánh theo ngày mô phỏng và lead time giả định.
- Commit: not required by task scope. Không stage, commit, push hoặc triển khai Render.
