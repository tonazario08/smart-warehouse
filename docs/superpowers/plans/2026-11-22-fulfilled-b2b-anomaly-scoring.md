# Plan đã duyệt — Tự chấm mô hình cho lần thực xuất B2B

- Task identifier: `score-fulfilled-b2b-anomalies`
- Task: `docs/tasks/score-fulfilled-b2b-anomalies.md`
- Đường dẫn dự kiến: `docs/superpowers/plans/2026-11-22-fulfilled-b2b-anomaly-scoring.md`
- Cơ sở: hợp đồng fulfillment M4, nguồn dữ liệu M5, Isolation Forest + SHAP M9; mã sau merge local 14520ce cần đối chiếu lại checkout.
- Trạng thái: Đã duyệt code và kiểm thử trong bản sao cô lập; không có phê duyệt vận hành thật.

## 1. Cổng phạm vi

- M4/M5/M9 là dependency thực sự và đã ghi DONE ở bản lưu; kiểm lại checkout đích. Task link fixture hiện VERIFYING **không** là dependency trực tiếp: chỉ dùng hợp đồng nghiệp vụ M4/M5 và giao diện xác minh quyền M9; có thể làm task mới nếu các dependency DONE và không thực sự có task khác đang triển khai. Nếu implementation cần dựa vào task đang VERIFYING thì dừng cổng READY, kết thúc/duyệt dependency đó trước; không đổi trạng thái thay cho bằng chứng.
- Chỉ cho phép code/test trong bản sao tách. Trước khi sửa project, người dùng duyệt plan và chọn đúng path task không phải template; lưu hai file theo quyền phê duyệt, rồi kiểm baseline/DB thử và trạng thái READY. Sao lưu, migration/worker trên DB thật, merge/push/deploy và model/dữ liệu thật cần phê duyệt riêng.

## 2. Từ request đến worker theo thứ tự

1. Tạo/duyệt đơn: không queue việc chấm giao dịch xuất. Khi fulfill đơn đã duyệt, khóa hàng và tồn như hiện tại; tạo phiếu, transaction và provenance `purchase_request_fulfillment`; cập nhật workflow/time/actor, thêm **một** job khóa duy nhất theo transaction ID trong cùng transaction. Không enqueue ở nhánh replay `fulfilled`. Nếu ghi job lỗi, rollback cả lần fulfill, không tạo hiệu ứng một nửa. Migration chỉ thêm cấu trúc, không duyệt qua phiếu cũ.
2. Sau commit, worker riêng mới claim. Tái dùng nguyên tắc deadline/claim-token/backoff có giới hạn của bộ worker hiện có, không trộn hai hàng đợi. Mỗi lần ghi kết quả hoặc complete đòi đúng owner/token; xử lý lại không ghi đè kết quả bất biến và không tạo cảnh báo trùng. Không chạy inference, model load hoặc tạo giải thích trong request. Nếu worker chưa chạy thì trạng thái pending, không nói “đang chấm xong”.
3. Kiểm lineage chính xác: transaction outbound → phiếu qua FK, workflow fulfilled đồng thời khớp transaction/phiếu, purpose đúng, kho/SKU/lượng/actor/giờ và chênh tồn nhất quán; đơn vị là giá trị được cố định bởi nguồn có thẩm quyền. Không suy bằng số ID giống, giờ hoặc lượng. Khóa kết quả theo transaction, dùng (artifact digest, feature version, input fingerprint/as-of, threshold, score semantics) để truy vết.
4. Feature M9 dự kiến giữ 6 trường và quy tắc giờ/thứ UTC; bảy **ngày UTC đầy đủ trước ngày xuất**, cùng cặp kho/SKU/đơn vị; dữ liệu và chứng cứ coverage phải có thời điểm khả dụng không muộn hơn lần xuất. Không dùng các bản ghi đến sau, không dùng ngày đang xét cho lịch sử, không coi cửa sổ thiếu coverage là zero. Lập fingerprint đầu vào và lưu bằng chứng riêng; nếu không có nguồn xác nhận coverage/đơn vị trong môi trường thử/đích thì `INSUFFICIENT_DATA`, không thêm giả lập vận hành. M5 fixture/benchmark hiện có không phải nguồn phê duyệt vận hành.

## 3. Hai chế độ nghiệm thu

**A. Không có artifact vận hành đã duyệt.** Ghi một kết quả terminal `NO_APPROVED_MODEL` (hoặc `MODEL_ARTIFACT_INVALID` nếu cấu hình sai) và hiển thị “Chưa có mô hình vận hành được duyệt”/lý do phù hợp cho người có quyền. Không phát lại liên tục, không thay model khác, không verdict “bình thường”, không tạo cảnh báo hoặc điểm giả. Mọi hoạt động hồi tố và chấm lại sau duyệt model là task riêng; mặc định không áp dụng cho #2 hoặc bất kỳ phiếu cũ nào.

**B. Artifact đã xác thực đúng phiên bản.** Chỉ chạy artifact đã pin đủ model/feature/method/threshold/background/training-release digest và định danh người quản trị phê duyệt; đối chiếu checksum từ cấu hình tin cậy độc lập với file artifact, không nhận URL/đường dẫn người gửi tùy ý. Chốt pin ngay lần xử lý đầu được claim; retry giữ nguyên pin, không đổi model giữa chấm và giải thích. Score cùng ngữ nghĩa `-IsolationForest.score_samples`, so `>` nghiêm theo ngưỡng của bản đã duyệt, không mượn ngưỡng .5921 demo. SHAP giải thích đúng score và background của artifact; sai residual hoặc thiếu explainer không phát cảnh báo “đã giải thích” hay suy normal. DB test riêng có chế độ synthetic **bật riêng**, không làm cho artifact synthetic hợp lệ ở vận hành. Test gồm ca vượt ngưỡng/đúng ngưỡng, thiếu lịch sử, hiển thị mô hình/phiếu chính xác.

## 4. Artifact, quyền và UI tối thiểu

- M9 hiện fit offline fixture, public catalog chỉ chứa đầu ra, không đóng gói estimator deploy, pipeline và link fixture có gate test/integration. Không mở rộng các gate đó, không dùng kết quả cũ như model, không dùng MEVGAL/tập nghiên cứu tổng hợp như event outbound vận hành. Cần bên sở hữu duyệt dữ liệu huấn luyện, quyền sử dụng nguồn/model, metadata, cutoff train/validation/holdout, hiệu chuẩn ngưỡng, chất lượng và releases. Không hardcode hoặc tự nhận quyền sử dụng dữ liệu/model của bên thứ ba. Không đưa dữ liệu huấn luyện thô vào artifact công khai.
- Định dạng đề xuất phê duyệt: snapshot **chỉ dữ liệu** (cây, tham chiếu background và metadata) cấu trúc cố định, giới hạn byte/node/depth/tài nguyên, kiểm finite/cấu trúc/digest/phiên bản, không cho import code hay biểu thức. Đối chiếu với scikit-learn đã pin trên fixture (bao gồm score và quyết định biên) trước khi chấp nhận định dạng. Nếu không đạt parity, dừng, báo chưa có model chứ không fallback. Không load pickle/joblib/cloudpickle hoặc artifact executable. [Tài liệu chính thức scikit-learn về rủi ro lưu/đọc model](https://scikit-learn.org/stable/model_persistence.html#security-maintainability-limitations).
- Giữ bảng job/kết quả vận hành riêng; một kết quả có thể gồm điểm, SHAP, và liên kết đúng phiếu khi flagged, không đưa vào catalog fixture công khai. Màn chi tiết cần phân biệt “chờ”, “thiếu mô hình/dữ liệu”, “không vượt ngưỡng”, “cảnh báo đã xác minh”; giữ cảnh báo fixture/đánh giá hiện có. Muốn xem điểm/cảnh báo cần `anomaly:read`; mở nguồn cần thêm `inventory:history:read`. Cả API và UI kiểm quyền, không lộ trạng thái nguồn cho client/ẩn danh.
- Thiết kế first slice: một migration cộng thêm, hook nội transaction ở đúng nhánh fulfill, worker riêng, bộ load/score giới hạn cho một model release tại một thời điểm, API đọc + UI nhỏ. Không registry/online train, dashboard quản trị, gửi thông báo hay chỉnh catalog demo.

## 5. RED → GREEN và chứng cứ

| Nhóm | Tín hiệu cần thấy |
| --- | --- |
| Transaction | Rollback không job; commit một job; replay/concurrency không lặp; tiến trình riêng chỉ đọc job đã commit; runner không sửa tồn/phiếu/review. |
| A: thiếu model | API đọc chi tiết thấy mã thiếu model; không score/alert; chạy lại không đổi. Artifact sai checksum/phiên bản/fixture ở chế độ vận hành bị từ chối. |
| B: có model | Model synthetic huấn luyện thực trong test cô lập, parity score; ca <, =, > ngưỡng; SHAP additivity và ghi đúng phiên bản. Thiếu chứng cứ as-of hoặc SHAP lỗi không tạo kết luận giả. |
| Nguồn và quyền | Same-shaped decoy, ID transaction khác ID phiếu, actor/warehouse/qty drift; 401/403 và kiểm hai quyền; link đọc không thay dữ liệu. |
| Migration/review | Bản sao DB 0009→head mới, old voucher #2 không có job/link tự sinh, upgrade/downgrade DB khác riêng; test worker lease/retry và full relevant checks, đọc chéo độc lập. |

Kết quả test synthetic chỉ chứng minh đường tích hợp, không chứng minh độ chính xác tác nghiệp. Dù phần code pass, nếu chưa duyệt model/nguồn dữ liệu thật thì không bật production.
