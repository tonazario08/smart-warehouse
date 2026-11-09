# open-gis-in-google-maps — Mở chỉ đường GIS trên điện thoại

## Metadata

- Status: DONE
- Phase: Bổ sung sau M10
- Plan: docs/tasks/open-gis-in-google-maps.md#implementation-plan
- Depends on: docs/tasks/implement-warehouse-gis.md
- Created: 2026-11-08
- Started: 2026-11-08
- Completed: 2026-11-08

## Goal

Mở chỉ đường ô tô từ kết quả GIS trong Google Maps trên điện thoại.

## Context

M10 hiển thị tuyến tham khảo và trả tọa độ gốc của hai đầu tuyến. Người dùng đã chọn thêm liên kết Google Maps ngay tại kết quả tuyến và xác nhận đường dẫn task này.

## In Scope

- Thêm liên kết tiếng Việt cạnh kết quả tuyến trong `client/src/features/gis/GISPage.tsx`.
- Kiểm thử URL và điều kiện hiển thị trong `client/src/features/gis/GISPage.test.tsx`.

## Out of Scope

- Nhúng bản đồ Google, thay đổi định tuyến M10, API, phân quyền hoặc dependency.
- Chuyển liên kết giữa hai thiết bị, kiểm tra thiết bị vật lý và xuất bản Git.

## Acceptance Criteria

- [x] AC-1. Khi kết quả có hai đầu tuyến, liên kết truy cập được bằng bàn phím, mở Google Maps bằng HTTPS và truyền đúng tọa độ gốc theo thứ tự vĩ độ, kinh độ cho chỉ đường ô tô.
- [x] AC-2. Khi thiếu tọa độ điểm đi hoặc điểm đến, không hiển thị liên kết. Khi người dùng chọn mở, dữ liệu nghiệp vụ gửi qua URL chỉ gồm hai cặp tọa độ.
- [x] AC-3. Kết quả GIS và các luồng hiện tại tiếp tục hoạt động. Kiểm thử frontend, kiểm tra kiểu, build và kiểm tra diff đạt.

## Implementation Plan

Task identifier `open-gis-in-google-maps`. Người dùng xác nhận ngày 2026-11-08.

1. Bổ sung assertion URL vào luồng xem tuyến sẵn có. Kiểm thử cả hai trường hợp thiếu một đầu tuyến.
2. Dùng tọa độ gốc từ `RouteRead` và `URLSearchParams` để tạo liên kết theo hợp đồng Maps URLs. Đặt liên kết cạnh thông tin tuyến và nêu Google Maps tự tính đường từ hai điểm.
3. Chạy các lệnh kiểm chứng bên dưới và review diff riêng so với nội dung M10 trước khi sửa.

## Verification Commands

### Focused

`cd client; npm.cmd run test -- --run src/features/gis/GISPage.test.tsx`

### Regression

`cd client; npm.cmd run test:all`

### Static and Diff

Chạy `npm.cmd run typecheck` rồi `npm.cmd run build` trong `client`. Chạy `git diff --check` ở thư mục gốc và so sánh trực tiếp các file GIS chưa được Git theo dõi với snapshot trước khi sửa.

## Progress Log

- 2026-11-08. `READY -> IN_PROGRESS`. Đã xác nhận task, kế hoạch cùng định danh và dependency M10 `DONE`. Chốt baseline và giữ nguyên các thay đổi M10 chưa commit.
- 2026-11-08. `IN_PROGRESS -> VERIFYING`. Đã thêm liên kết và các ca kiểm thử, sẵn sàng chạy regression và kiểm tra tĩnh.
- 2026-11-08. `VERIFYING -> REVIEWING`. Các lệnh kiểm chứng bắt buộc đạt, chuyển sang review độc lập.
- 2026-11-08. `REVIEWING -> DONE`. Review độc lập `APPROVED`, đủ bằng chứng cho 3 AC, diff đúng phạm vi.

## Verification Evidence

### Focused

- `npm.cmd run test -- --run src/features/gis/GISPage.test.tsx` trong `client` trước khi sửa giao diện: 12 đạt, 1 lỗi đúng kỳ vọng vì chưa có liên kết.
- Cùng lệnh sau khi thêm liên kết: 13/13 đạt, gồm tham số URL, tab bằng bàn phím và hai trường hợp thiếu tọa độ.
- Reviewer chạy độc lập `npm.cmd run test -- --run --no-cache src/features/gis/GISPage.test.tsx`: 13/13 đạt.

### Regression

- `npm.cmd run test:all` trong `client`: 432/432 ca Vitest và 90/90 ca host đạt.

### Static and Diff

- `npm.cmd run typecheck` và `npm.cmd run build` trong `client`: exit 0. Vite cảnh báo chunk JS lớn hơn 500 kB.
- `git diff --check`: exit 0. So sánh snapshot trước sửa với hai file GIS chưa được theo dõi xác nhận chỉ có 16 dòng thêm ở giao diện và 23 dòng thêm ở test, không có lỗi whitespace. File mới duy nhất là task này.

## Review Result

- Result: APPROVED
- Findings: none. Reviewer xác nhận mã đọc tọa độ gốc, dùng liên kết có tên truy cập và chính sách không gửi referrer. Kiểm tra URL theo [tài liệu Maps URLs](https://developers.google.com/maps/documentation/urls/get-started#directions-action).

## Completion Evidence

`DONE` ngày 2026-11-08. AC-1 và AC-2 có test URL, bàn phím và hai nhánh thiếu tọa độ. AC-3 có 522 ca regression đạt, kiểm tra kiểu, build và diff đạt. Review độc lập `APPROVED`. Chưa thử mở ứng dụng trên điện thoại thật. Commit `not required by task scope`. Thay đổi chưa stage.
