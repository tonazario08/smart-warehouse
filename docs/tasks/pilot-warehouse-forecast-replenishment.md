# pilot-warehouse-forecast-replenishment — Nối dự báo và bổ sung hàng trên một cặp demo

- Status: DONE
- Phase: Forecasting → Replenishment, pilot học thuật
- Plan: docs/superpowers/plans/2026-11-22-warehouse-forecast-replenishment-pilot.md
- Depends on: docs/tasks/build-demand-data-pipeline.md; docs/tasks/implement-demand-forecasting.md; docs/tasks/implement-replenishment-policy.md; docs/tasks/implement-replenishment-alerts.md
- Created: 2026-11-22
- Started: 2026-11-22
- Completed: 2026-11-22

## Goal
Minh họa đúng một kho/SKU/đơn vị giả: thấy nguồn dự báo tạo nên ROP và hiểu so sánh ngưỡng/EOQ, không nhầm với cảnh báo vận hành.

## Context
Dairy Product 2 là doanh số cấp công ty nghiên cứu hồi cứu. M6/M7 đã có model, mô phỏng và API. Operational chính thức chưa có nguồn được duyệt; pilot cố định dữ liệu giả với cutoff lịch sử.

## In Scope
Một panel tại run bổ sung, một endpoint chỉ đọc nối hai artifact đúng lineage và role, dùng fixture CLI sẵn có, xem một ngày/lead time có kiểm soát.

## Out of Scope
Dữ liệu thật, sửa model/policy/forecast hoặc worker nghiệp vụ, PO/tồn/DB main, thuật toán mới, retrain trong HTTP, triển khai/push.

## Acceptance Criteria
- [x] AC-1 — Fixture M5/M6/M7 cặp demo tái tạo và xác minh: kho, SKU, đơn vị, ID/hash nguồn, cutoff, đúng 7 dự báo cùng origin và một ROP không warmup.
- [x] AC-2 — Dùng vị thế tồn mô phỏng riêng, bằng/dưới ROP khác trên; EOQ hợp lệ mới có số. Không cộng đơn chờ vào dự báo hoặc trừ hai lần; không ghi nghiệp vụ.
- [x] AC-3 — Fixture/off, research, data mismatch/tamper/missing, sai quyền fail closed; quyền admin/warehouse mới đọc.
- [x] AC-4 — UI rõ demo, cutoff/ngày/horizon, chi tiết và link nguồn; không trở thành cảnh báo vận hành. Kiểm thử browser thật cô lập, frontend, backend và diff.

## Verification Commands
- `python -m pytest -q tests/test_warehouse_forecast_pilot.py tests/test_forecasting_api.py tests/test_replenishment_api.py`
- Fixture: `tests.prepare_replenishment_e2e.prepare(None, profile="synthetic-only")` tại checkout cô lập theo guard; browser có catalog thật của demo và DB giả.
- Client typecheck/build/test:all; baseline regression và diff.

## Progress Log
- 2026-11-22: READY → IN_PROGRESS. Toàn duyệt exact task và plan; các dependency DONE; HEAD `c660c4f05bd2a67fdee42fbb29764a1517dbda05`, tree `ceb00e7e4c103b9265d7c224c7d65f5f8c8c2b34` clean. Một task được thực thi; không mở lại ledger cũ.

- 2026-11-22: IN_PROGRESS → VERIFYING; chốt code và artifacts demo để chạy nghiệm thu browser cô lập.

- 2026-11-22: VERIFYING → REVIEWING; browser Windows độc lập và kiểm tra lineage/giới hạn đã đạt trên đúng freeze.
- 2026-11-22: REVIEWING → DONE; chỉ nghiệm thu kịch bản demo cô lập, không phê duyệt vận hành.

## Verification Evidence
- Offline đúng c660c4f: tái dùng helper M5/M6, chạy verify upstream và run/verify/reconcile/publish M7. M7 khớp 36 trường hợp/6.408 ngày mô phỏng, không kết nối DB. Forecast `frv1-96f99dca2c706b19e144b975e591724c777b096001c537e3288b06320d73c472`; M7 `rrv1-b34198da244add0ec1009c56dba0f651b380380b82eb31c76f24d28f2621d250`. Các catalog này chỉ cài bản cô lập với hai flag fixture, kho/SKU M7-E2E-SYNTHETIC (`2/2/unit`).
- Origin 07/07/2022, ngày mô phỏng 08/07/2022, cutoff huấn luyện 01/01/2022 00:00 UTC. Bảy dự báo 2/ngày = 14; safety stock 0; ROP 14, vị thế tồn mô phỏng 9.986, trên ROP; EOQ tham khảo 86. Holdout 359 origin và 2.513 dự báo, WAPE và MAE tổng 7 ngày đều 0 vì chuỗi giả luôn bằng 2, các baseline cũng bằng 0; không có bằng chứng mô hình tốt hơn hoặc vận hành thật. Test quyết định biên riêng kiểm vị thế 13/14/15 trước ROP 14.
- Backend 40 pass (pilot/catalog, API dự báo, API bổ sung, kiến trúc), Ruff và diff sạch. Frontend typecheck/build, 587 Vitest và 88 host đạt; Playwright 53 ca mặc định, 54 nếu bật pilot cô lập, vẫn 53 ở GitHub Actions. Không đổi matrix hiện hành.
- Kiểm âm độc lập: catalog scratch chứa bản dự báo hợp lệ mới hơn cùng khóa kho/SKU/UoM. Danh sách xếp bản thử mới lên trước; endpoint pilot giữ đúng bản cũ được chính sách ghim. Xóa riêng bản cũ trong scratch: SOURCE_UNAVAILABLE, không ghép bản mới. Đổi byte manifest của cùng ID nhưng vẫn tự nhất quán: ARTIFACT_MISMATCH.
- Browser Windows độc lập đúng patch `5fcbcf84fc1690f34bf9e47696b4de78630ac6a45b55b5022da60c43c9d3c929`: admin/warehouse thấy panel và mở đúng run dự báo nguồn; client API 403. Kịch bản thật từ fixture trả forecast 14, ROP 14, vị thế mô phỏng 9.986, không đặt lại. Kiểm biên 13/14/15 riêng xác nhận bằng và dưới ngưỡng đều được phân loại at_or_below; không đọc đó là cảnh báo kho thật.
- Không đưa artifact, DB hay credentials vào patch; không đổi sản phẩm/nguồn mô hình, tồn hoặc PO, không ghép đơn chờ vào nhu cầu dự báo.

## Review Result
- Result: APPROVED
- Findings: none
- Phạm vi độc lập: pilot dữ liệu giả, không suy ra độ chính xác/công suất kho thật.

## Completion Evidence
- AC-1…AC-4 đã đạt với đúng cặp fixture và quyền hiện hữu. Không thay main, dữ liệu thật, runtime có sẵn hoặc bật dự báo/ROP vận hành. Bản cuối chỉ sửa ledger so với freeze đã kiểm.
- Vị thế tồn là của ngày mô phỏng, không phải tồn hoặc đơn chờ hôm nay. EOQ 86 là số tham khảo giả với chi phí giả; WAPE/MAE bằng 0 trên dãy hằng không chứng minh XGBoost vượt baseline. Dairy chỉ là dữ liệu doanh số nghiên cứu hồi cứu, không được dùng vào kho/SKU vận hành.
