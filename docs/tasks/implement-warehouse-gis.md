# implement-warehouse-gis — GIS kho hàng

> Hoàn tất kiểm chứng M10 trong worktree riêng với bản đường Geofabrik 261105.

## Metadata

- Status: DONE
- Phase: M10
- Plan: docs/superpowers/plans/2026-10-16-project-completion.md, mục M10
- Specification: docs/superpowers/specs/2026-10-16-project-completion-design.md
- Depends on: docs/tasks/implement-stock-transfers.md; docs/tasks/implement-b2b-purchase-requests.md; docs/tasks/implement-replenishment-policy.md
- Created: 2026-11-07
- Started: 2026-11-07
- Completed: 2026-11-08
- Review Result: APPROVED

## Goal

Giúp người vận hành tìm kho có đủ tồn cho một SKU và số lượng cần, xem đường đi trên mạng đường có nguồn, và quan sát lượng xuất đã ghi nhận theo vị trí kho trong kỳ chọn.

## Context

Baseline đề xuất là `547eb1c363d6804c45fcbb159d14a8fe7eef095c` trên `feat/figma-ui-v2`. Quality tích hợp M9 `42343140367` đạt cả bốn job. Ba task phụ thuộc M3, M4, M7 đang `DONE`.

`Warehouse` đã có cặp `latitude`/`longitude` có thể rỗng, kiểm tra biên và trang chi tiết có liên kết xem vị trí. `Stock` cung cấp lượng hiện có theo kho và sản phẩm. `Region` và `RouteLog` chưa cung cấp mạng đường hoặc kết quả định tuyến. M3 chuyển kho tức thời, có liên kết và provenance hai chân. M4 yêu cầu mua hàng đã gắn kho và có quyền truy cập riêng. Catalog M7 công bố kết quả nghiên cứu hoặc fixture với phạm vi áp dụng, cần kiểm tra binding trước khi trình bày cho kho cụ thể.

## In Scope

Đề xuất một trang GIS tiếng Việt cho `admin` và `warehouse` để chọn điểm đến, SKU, số lượng và kỳ thống kê. Backend xác định quyền, trả danh sách kho đủ tồn và tuyến đi trên đồ thị khi có thể. Giao diện trình bày vị trí kho, hình học tuyến, trạng thái nguồn và lớp màu theo lượng xuất từng kho. Dùng React, CSS và thành phần dùng chung hiện tại.

Chuẩn bị một bản chụp đường công cộng có phiên bản, kiểm tra giấy phép, hệ tọa độ, phạm vi, checksum, chiều đường, giới hạn truy cập và chất lượng trước khi dùng. Xử lý ngoại tuyến. API đọc bản chụp đã kiểm tra và tính tuyến cục bộ. Đo thời gian và bộ nhớ trên vùng đã duyệt trước khi chốt giới hạn.

Giữ liên hệ với M3, M4 và M7 qua dữ liệu đọc đã có quyền. Có thể xem tuyến giữa hai kho của chuyển kho, dùng kho đã gắn với yêu cầu mua hàng làm điểm đến tham khảo, và trình bày kết quả M7 khi phiên bản được phép đọc và khớp SKU/kho. Giữ ngữ cảnh M7 tách khỏi quyết định đủ tồn và thứ tự tuyến.

## Out of Scope

Tự tạo hoặc thực hiện giao dịch, giữ chỗ, chọn lại kho của yêu cầu mua hàng, hoặc sửa luồng chuyển kho. Tính thời gian giao hàng, định tuyến nhiều điểm, hỗ trợ quy định tải trọng xe tải hoặc dẫn đường thời gian thực. Tự geocode địa chỉ kho hoặc gửi tọa độ, dữ liệu tồn hay giao dịch cho dịch vụ bên ngoài. Thêm framework UI, dịch vụ bản đồ trả phí, PostGIS hoặc migration khi chưa có nhu cầu đã kiểm chứng. Công bố hiệu quả logistics trên dữ liệu vận hành chưa được phép dùng.

## Acceptance Criteria

- [x] AC-1 — Bản chụp đường có nguồn, thời điểm dữ liệu, phạm vi, phiên bản, checksum, giấy phép và attribution hiển thị. Kiểm tra bản sai checksum, CRS/đơn vị sai, ngoài vùng và quá hạn. Có ít nhất một tuyến dựng từ đường công cộng đã được thẩm định.
- [x] AC-2 — Kết quả A* trên đồ thị có hướng khớp Dijkstra tham chiếu cho các ca kiểm soát. Kiểm tra đường một chiều, hạn chế rẽ thuộc profile, nhiều lựa chọn cùng chi phí, cạnh không hợp lệ và đồ thị không liên thông. Heuristic có chứng minh phù hợp với trọng số.
- [x] AC-3 — Tồn kho thật từ DB cô lập quyết định eligibility theo SKU và lượng yêu cầu. Kho gần nhất thiếu hàng bị loại. Có test nhiều kho đủ tồn, bằng đúng số lượng, thiếu bản ghi tồn, sản phẩm không hợp lệ và tọa độ thiếu/sai. Kết quả chứa thời điểm đọc tồn, đơn vị và căn cứ xếp hạng.
- [x] AC-4 — Tuyến và lớp màu dựa trên đúng phiên bản và đơn vị. Đường nối thẳng chỉ hiện dưới nhãn khoảng cách địa lý nếu được dùng. Lớp màu theo kho có SKU, kỳ, chú giải và số liệu đối chiếu được. Kiểm tra biên kỳ, không có giao dịch, thiếu tọa độ và phân loại chân chuyển kho đúng.
- [x] AC-5 — Quyền backend cho ba role, 401/403 và truy cập ID ngoài quyền được kiểm chứng. Đọc M3/M4/M7 theo quyền hiện có, với ca được phép và ca từ chối. Kiểm tra quyền M4 trước khi trả dữ liệu của ID được yêu cầu, cùng kết quả M7 sai SKU/kho hoặc chỉ thuộc nghiên cứu. So sánh tồn, giao dịch, chuyển kho và yêu cầu mua hàng trước/sau cho thấy thao tác GIS chỉ đọc. Các API hiện có giữ contract.
- [x] AC-6 — Browser desktop/mobile chạy với API thật và stack cô lập. Kiểm chứng kho đủ tồn, tuyến có/không có, trạng thái đang tải/rỗng/lỗi/thử lại/không có quyền, điều khiển bàn phím và bản dữ liệu có nhãn. Có bằng chứng trực quan theo thiết kế đã duyệt.
- [x] AC-7 — Tách kiểm thử đồ thị tổng hợp, bằng chứng tuyến trên snapshot đường công cộng và đánh giá hiệu quả logistics. Tài liệu ghi phạm vi địa lý, giới hạn profile và nguồn dữ liệu. Hiệu quả vận hành giữ `NOT VERIFIED` khi thiếu số liệu đủ điều kiện.

## Thiết kế đề xuất

### Nguồn đường và quyền sử dụng

Đề xuất bản trích xuất OpenStreetMap Việt Nam do Geofabrik cung cấp, cắt ngoại tuyến một vùng công cộng giới hạn tại TP.HCM. Kế hoạch bên dưới đề xuất bounding box, bản phát hành có ngày, giới hạn kích thước và tài nguyên chuẩn bị. Chọn các điểm kho mô phỏng nằm trong vùng cho lần nghiệm thu. Cần xác minh dữ liệu tọa độ của kho vận hành trước khi công bố có hỗ trợ. Hiện đã đọc trang nguồn và giấy phép. Bản tải, checksum, phạm vi khả dụng và hiệu năng còn chờ xác minh.

Manifest đề xuất lưu URL nguồn, thời điểm snapshot, SHA-256 nguồn và đầu ra, phạm vi, phiên bản bộ chuyển đổi và profile định tuyến, CRS và đơn vị. Dữ liệu OpenStreetMap từ Geofabrik dùng ODbL 1.0. Giữ tệp gốc và đồ thị ngoài Git, mount bản đồ thị đã kiểm tra chỉ đọc cho runtime. Tách dữ liệu đường khỏi bản ghi kho và giao dịch. Hiển thị `© OpenStreetMap contributors` cạnh bản đồ với liên kết giấy phép và ghi nguồn trong manifest.

Đề xuất nghiệm thu cục bộ. API có quyền trả hình học của tuyến được yêu cầu và các điểm kho cần hiển thị, với kho/tồn kiểm thử được ghi nhãn fixture. Cung cấp bản đồ đã dựng và tuyến theo truy vấn, chưa có chức năng xuất toàn bộ đồ thị hay tải tệp dẫn xuất. Trước khi công khai đồ thị hoặc sản phẩm tạo từ đồ thị dẫn xuất, chốt cách thực hiện attribution và cung cấp dữ liệu theo điều khoản ODbL 1.0 áp dụng, gồm mục 4.4 và 4.6.

- [Bản trích xuất Việt Nam của Geofabrik](https://download.geofabrik.de/asia/vietnam.html)
- [Giấy phép và cách ghi nguồn OpenStreetMap](https://www.openstreetmap.org/copyright)
- [Hướng dẫn ghi nguồn của OpenStreetMap Foundation](https://osmfoundation.org/wiki/Licence/Attribution_Guidelines)
- [Văn bản giấy phép ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/)

### Định tuyến và gợi ý kho

Mỗi truy vấn chọn SKU, số lượng dương và điểm đến có tọa độ hợp lệ. Đọc tồn và tọa độ kho trong cùng ảnh chụp dữ liệu có thời điểm rõ. Kho thiếu bản ghi tồn, thiếu tọa độ hoặc không đủ lượng có lý do riêng. Kho đủ tồn và có tuyến xếp theo chiều dài đường, sau đó theo khóa kho cố định để phân giải hòa. Khi chỉ tính được khoảng cách địa lý, trình bày ở danh sách riêng có nhãn. Kết quả gợi ý có thời điểm đọc, vì tồn có thể thay đổi trước khi người dùng thực hiện thao tác nghiệp vụ.

Đề xuất đồ thị có hướng từ dữ liệu đường, profile ô tô tham khảo, trọng số chiều dài bằng mét và tọa độ WGS84. Trường latitude/longitude có tên rõ, còn GeoJSON xuất theo thứ tự longitude/latitude. Dùng A* với cận dưới là khoảng cách đường chim bay nếu trọng số duy trì cận dưới này. Đối chiếu Dijkstra trên cùng graph và profile. Chiều đường, truy cập và hạn chế rẽ cần đặc tả trong plan. Phạm vi giới hạn hoặc dữ liệu hạn chế chưa đủ để kết luận đường dành cho xe tải. Điểm ngoài vùng, không snap trong ngưỡng, snapshot quá hạn hoặc không tìm được đường đều trả lý do phù hợp. Phân biệt đoạn snap với hình học đoạn đường.

### Bản đồ nhiệt và các luồng liên quan

Đề xuất lớp màu theo vị trí kho, đo lượng xuất thực hiện của một SKU trong khoảng ngày nửa mở theo `Asia/Ho_Chi_Minh`. Đổi biên kỳ sang UTC khi truy vấn. Dùng các giao dịch có provenance `purchase_request_fulfillment` theo hợp đồng M3/M4, tách `transfer_in`, `transfer_out`, xuất thông thường và nghiệp vụ chưa phân loại. Số 0 chỉ nói về bản ghi đáp ứng bộ lọc trong kỳ. Bảng dưới bản đồ vẫn ghi những kho thiếu vị trí và các khoản bị loại. Ghi đơn vị theo SKU và chú giải cường độ.

Khi đọc M3, dùng cặp kho đã có và ghi rõ chuyển kho tức thời. Khi đọc M4, áp dụng quyền truy cập yêu cầu trước khi đọc ID, dùng kho đã gắn làm điểm đến tham khảo. Với M7, kiểm tra quyền và binding SKU/kho, phiên bản và thời điểm. Kết quả tổng hợp hoặc hồi cứu có nhãn riêng, chỉ hiện trong đúng phạm vi của nó.

Trang bản đồ đề xuất vẽ hình học và lớp màu bằng SVG từ dữ liệu cục bộ, có bảng và điều khiển bàn phím. Giữ App Shell và design tokens hiện tại. Chưa có node Figma GIS được duyệt. Thiết kế màn hình cần duyệt trước khi triển khai giao diện.

### Quyết định thuộc kế hoạch chi tiết

Các quyết định về quyền, dữ liệu, đồ thị, API, giao diện, file được phép sửa và lệnh verification nằm trong kế hoạch bên dưới. Kế hoạch được đóng băng khi task vào `IN_PROGRESS`.

## Kế hoạch triển khai chi tiết

**Mục tiêu.** Chứng minh tuyến đường có hướng trên bản chụp đường công cộng, chọn kho đủ tồn bằng dữ liệu hiện có và hiển thị số lượng xuất đã ghi nhận theo vị trí kho.

**Kiến trúc.** CLI ngoại tuyến tạo snapshot bất biến. API FastAPI đọc graph cục bộ đã xác minh và truy vấn PostgreSQL theo quyền hiện có. React hiển thị tuyến và điểm kho bằng SVG, có bảng tương đương. Giữ Python, SQLAlchemy, React, TypeScript, Vite, npm, CSS và design tokens hiện tại. Không đổi schema PostgreSQL.

**Thẩm quyền.** Mục M10 của `docs/superpowers/plans/2026-10-16-project-completion.md` và `docs/superpowers/specs/2026-10-16-project-completion-design.md`. Dùng `superpowers:subagent-driven-development` với một native subagent triển khai các checkpoint tuần tự. Main đối chiếu diff, kiểm chứng từng AC và review độc lập. Tối đa ba vòng sửa finding. Checkpoint đã xác minh có thể commit riêng khi được cấp quyền. Các checkpoint dưới đây thuộc cùng task M10.

### 1. Chốt nguồn đường, chuẩn bị và xác minh snapshot

- [ ] Tạo worktree riêng từ `547eb1c363d6804c45fcbb159d14a8fe7eef095c`, dùng nhánh `codex/m10-warehouse-gis`. Xác nhận ba dependency còn `DONE`, bảo toàn file chưa commit tại checkout chính và xác nhận lại tài nguyên. Ghi `READY -> IN_PROGRESS` khi kế hoạch được duyệt và baseline hợp lệ.
- [ ] Chọn bản archive `vietnam-261105.osm.pbf` trong [danh mục Geofabrik Việt Nam](https://download.geofabrik.de/asia/vietnam.html). Vùng cắt tại TP.HCM là WGS84 `[106.64, 10.72, 106.76, 10.82]` theo thứ tự tây, nam, đông, bắc. Trước khi xử lý, kiểm tra HTTPS và MD5 do nguồn cung cấp, tính SHA-256, đối chiếu timestamp replication trong header PBF và lưu metadata. Timestamp header quyết định hạn 30 ngày tại thời điểm sử dụng. Snapshot có thời gian tương lai, metadata mâu thuẫn hoặc không còn đạt hạn tuổi phải bị từ chối. Dừng và báo nếu archive hoặc checksum nguồn không truy cập được. Việc thay archive, phạm vi hoặc ngưỡng sau khi bắt đầu cần sửa baseline theo workflow.
- [ ] Viết test admission trước. Đọc đúng thư mục theo ID `gsv1-<sha256>` của manifest JSON canonical và tên cố định `manifest.json`, `graph.json`. Manifest ghi `warehouse-road-graph/1`, `public_osm` hoặc `synthetic_fixture`, UTC snapshot và thời điểm chuẩn bị, URL và checksum nguồn, SHA-256 graph, bounds, `EPSG:4326`, đơn vị `mm`, phiên bản converter/profile, giấy phép, attribution và số lượng nút/cạnh/restriction. Mỗi cạnh có ID, hướng, đầu mút và trọng số. Loại trùng ID, tọa độ ngoài biên, cạnh treo, restriction sai, trọng số lệch công thức, tampering, schema lạ, symlink/path traversal và artifact vượt giới hạn. Root là đường dẫn tuyệt đối dành riêng, chỉ đọc khi chạy API. Từ chối fixture theo mặc định, chỉ bật ở môi trường test/integration và phải hiện nhãn.
- [ ] Thêm CLI `python -m app.gis.cli prepare --input <PBF> --source-url <HTTPS> --source-sha256 <SHA256> --output-root <DIR>` và `python -m app.gis.cli verify --catalog-root <DIR> --snapshot-id <ID>`. CLI đọc file cục bộ, kiểm tra hash trước parse, ghi staging cùng volume rồi publish nguyên tử. Lần chạy lặp chỉ tái sử dụng artifact đã verify trùng byte. Với cùng PBF, metadata nguồn và converter, graph phải tái tạo cùng SHA-256. Timestamp chuẩn bị tách khỏi phép so sánh hash graph. Lưu PBF, manifest, graph và logs ngoài Git, không đưa bản ghi kho vào snapshot. Chỉ CLI import tùy chọn `osmium==4.3.2` từ extra `gis`. Dùng Python 3.12 trên Linux cho checkpoint parser để trùng Quality. [PyPI osmium 4.3.2](https://pypi.org/project/osmium/4.3.2/)
- [ ] Parse bằng callback, giữ ID/tọa độ dạng primitive trong vùng và chỉ tạo segment giữa hai node liên tiếp hợp lệ trong vùng. Dùng ID OSM để xác định giao điểm. Profile ô tô tham khảo gồm `motorway`, `trunk`, `primary`, `secondary`, `tertiary`, các link tương ứng, `unclassified`, `residential`, `living_street` và `service`. Xét quyền truy cập theo `motorcar`, `motor_vehicle`, `vehicle`, `access`. Chấp nhận quyền công cộng tường minh (`yes`, `designated`, `permissive`) hoặc mặc định hợp lệ theo loại đường. Loại access/oneway có điều kiện, cấm hoặc mơ hồ. Hỗ trợ `oneway=yes/no/-1`, mặc định chiều của motorway và roundabout, và restriction `no_*`/`only_*` đơn giản có một via-node với hướng xác định. Khi gặp via-way, nhiều via, điều kiện hoặc restriction ô tô không thể giải nghĩa, loại các way liên quan trong vùng. Nếu không xác định được ảnh hưởng để loại an toàn, từ chối snapshot. Kiểm tra barrier liên quan trên node, loại kết nối tại node chặn hoặc có quyền mơ hồ. Ghi số lượng trường hợp bị loại. Fixture nhỏ phải chứng minh cầu vượt không nối khi ID khác, restriction giữ đúng chiều và segment bỏ khi vượt biên.
- [ ] Áp ngưỡng nguồn 400 MiB, một triệu node ứng viên trong vùng, 120.000 node graph, 360.000 cạnh, 50.000 cặp ràng buộc chuyển cạnh và graph 96 MiB. Đo lần chuẩn bị thực tế với ngân sách 10 phút và 2 GiB peak RSS. Ghi lại thời gian và bộ nhớ quan sát được. Nếu vượt ngưỡng, ghi blocker trước khi điều chỉnh. CI chạy parser trên PBF tổng hợp nhỏ do test tạo, không tải archive công cộng.
- **Tạo** `app/gis/__init__.py`, `app/gis/schemas.py`, `app/gis/catalog.py`, `app/gis/osm_import.py`, `app/gis/cli.py`, `tests/gis_helpers.py`, `tests/test_gis_catalog.py`, `tests/test_gis_osm.py`. **Sửa** `pyproject.toml` và bước cài dependency của job backend trong `.github/workflows/quality.yml`.

### 2. A* và phép đo khoảng cách

- [ ] Viết test với Dijkstra tham chiếu độc lập trước. Đối chiếu chi phí trên graph nhỏ. `test_reverse_oneway_is_unreachable` cho A→B tồn tại và B→A thất bại. `test_turn_restriction_uses_incoming_edge` cho A→B→C bị cấm, A→D→C vẫn được và kết quả bằng Dijkstra. `test_ties_repeat_with_shuffled_input` kiểm tra tuyến lặp lại khi đổi thứ tự đầu vào. `test_same_snapped_node_returns_point` trả chi phí 0. Bao phủ graph rời, cạnh quay lại và graph nhỏ sinh với seed cố định.
- [ ] Cài `verify_snapshot(root, snapshot_id, now, allow_fixture)` trả snapshot bất biến và `route(snapshot, origin, destination, *, budget)` trả hình học và chi phí hoặc reason code. A* dùng trạng thái `(node_id, incoming_edge_id)` để áp restriction. Dùng Haversine bán kính 6.371.008,8 m và trọng số cạnh làm tròn lên theo mm. Heuristic là khoảng cách Haversine đến đích làm tròn xuống theo mm. Bất đẳng thức tam giác làm heuristic thành cận dưới theo trọng số, kể cả khi loại một số lượt rẽ. Soát consistency trên cạnh hợp lệ và heuristic bằng 0 ở điểm đích. Tie-break cố định theo ID, thứ tự duyệt cạnh và thứ tự queue đã xác định.
- [ ] Snap từng đầu mút tới node gần nhất trong 200 m, phá hòa bằng node ID, dùng index không gian cục bộ để tránh quét toàn graph cho mỗi kho. Trả connector tách riêng cùng độ dài, không cộng vào chiều dài đường. Dùng GeoJSON theo thứ tự `[longitude, latitude]`. Hai đầu trùng node trả Point và chiều dài đường 0. Trả lý do riêng cho `outside_coverage`, `snap_too_far`, `no_route`, `budget_exceeded` và `geometry_limit`. Chia ngân sách tối đa 250.000 trạng thái settle cho một truy vấn; khi không tính hết, không công bố thứ hạng tuyến dở dang. Giới hạn 4.000 tọa độ trên một tuyến, không cắt mất đầu mút.
- **Tạo** `app/gis/routing.py` và `tests/test_gis_routing.py`. Dùng lại graph/schema của checkpoint 1. Chạy oracle và đo một tuyến công cộng có hai điểm chọn từ snapshot đủ điều kiện. Lưu ID phiên bản, hai điểm snap, chi phí A*/Dijkstra và thời gian. Tuyến chỉ có ý nghĩa trong vùng/profile đã nêu.

### 3. API và dữ liệu đọc

- [ ] Viết test auth, contract và DB trước. Thêm `gis:read` và `gis:route` cho `admin`, `warehouse`. Dùng `require_permission`, 401 khi thiếu/hỏng phiên và 403 cho client. Giữ nguyên quyền của API khác. Dùng `DomainError` và kiểu phản hồi hiện tại cho lỗi. Thêm settings `GIS_CATALOG_ROOT`, `GIS_SNAPSHOT_ID`, `GIS_ALLOW_FIXTURE` với mặc định chưa cấu hình và fixture tắt. API xác minh snapshot trước khi phục vụ GIS và trả trạng thái riêng khi thiếu artifact. Có thể cache một graph đã verify theo ID trong bộ nhớ của mỗi worker và kiểm tra lại hạn tuổi mỗi truy vấn. Health và API cũ vẫn hoạt động khi catalog GIS chưa cấu hình hoặc bị lỗi. Không đọc PBF, gọi mạng hoặc in đường dẫn/tệp/credential trong API.
- [ ] Chốt 5 endpoint dưới `/api/v1/gis` theo bảng. POST dùng để tính toán, không thay đổi trạng thái. ID/số lượng dương, dùng giới hạn `MAX_STOCK_QUANTITY` hiện có, body typed phân biệt mode, từ chối trường lạ và tọa độ không hữu hạn. Kiểm tra lỗi không lộ ID ngoài quyền.

| Phương thức và đường dẫn | Quyền | Đầu vào và kết quả |
| --- | --- | --- |
| `GET /status` | `gis:read` | Trạng thái `available`, `unconfigured`, `invalid` hoặc `stale`. Metadata an toàn gồm ID, nguồn, lớp dữ liệu, thời điểm UTC, bounds, CRS, đơn vị và attribution khi có. |
| `POST /warehouse-options` | `gis:route` | `product_id`, `quantity`, `destination` có `kind` là `coordinate` với latitude/longitude, `warehouse` với warehouse_id hoặc `purchase_request` với request_id. Trả `stock_as_of`, thông tin SKU/đơn vị, lượng yêu cầu, snapshot, `ranked`, `geographic_only`, `excluded`. Phần ranked có chiều dài đường và ID nguồn, không lặp lại hình học của mọi tuyến. |
| `POST /route` | `gis:route` | `kind=warehouse_to_target` với warehouse_id nguồn và destination, hoặc `kind=transfer` với transfer_id. Trả snapshot, hai đầu, snap, hình học, chiều dài đường mm hoặc trạng thái không có tuyến. |
| `GET /heatmap` | `gis:read` | `product_id`, `start_date`, `end_date` (biên cuối loại trừ). Trả SKU, đơn vị, UTC boundaries, múi giờ nghiệp vụ, thời điểm truy vấn, các kho có điểm/vắng tọa độ và thống kê loại trừ. |
| `GET /policy-context` | `gis:read` | `run_id`, `product_id`, `warehouse_id`. Trả trạng thái và provenance tối thiểu của M7 khi binding hợp lệ trong môi trường được phép. Không trả dữ liệu run sai phạm vi. |

- [ ] Dùng `GISRepository` đọc sản phẩm, kho và left join tồn theo SKU trong cùng statement với `statement_timestamp()`; xử lý được SKU hợp lệ dù chưa có kho. Loại SKU không hoạt động. Kho đủ tồn khi quantity đọc được lớn hơn hoặc bằng yêu cầu. Tách thiếu bản ghi tồn, thiếu hàng, thiếu vị trí và tọa độ lỗi. Giới hạn 100 kho cho phép tính xếp hạng trong một truy vấn, trả 422 có lý do nếu vượt, không cắt bớt danh sách. Sắp kho đủ tồn và có tuyến theo chiều dài mm rồi ID kho. Kho đủ tồn và chỉ tính được Haversine vào `geographic_only`, hiện nhãn riêng, kể cả khi snapshot thiếu/quá hạn. Nếu tính tuyến vượt ngân sách, trả trạng thái chưa có thứ hạng tuyến và các khoảng cách địa lý có nhãn. Đọc tồn là tham khảo tại thời điểm ghi nhận và không giữ chỗ.
- [ ] Với M3, kiểm tra `INVENTORY_HISTORY_READ` trước `TransferService(TransferRepository(session)).get(transfer_id)`. Dùng cặp kho có sẵn, hiển thị ngữ cảnh chuyển kho tức thời, không xác nhận xe đã đi. Với M4, gọi `PurchaseRequestService(PurchaseRequestRepository(session)).get(actor, request_id)` trước khi đọc kho của yêu cầu. Dùng đúng kho đã gắn. Nếu truy vấn warehouse-options theo request thì SKU và lượng phải khớp request, trả 422 nếu mâu thuẫn. Với M7, gọi `ReplenishmentService.get(actor, run_id)` trên repository đã kiểm tra quyền và artifact. Đối chiếu mode, applicability, binding SKU/kho và đơn vị hiện tại. M7 hiện chỉ có fixture cho mode operational. Bật fixture ở stack cô lập và trả run ID, phiên bản dữ liệu, `created_at` của run, nhãn và đường dẫn trang M7 hiện có khi khớp. Research, sai binding hoặc tắt fixture trả trạng thái không áp dụng. M7 không đổi eligibility hay thứ hạng.
- [ ] Heatmap dùng khoảng tối đa 90 ngày `[start_date,end_date)` theo `Asia/Ho_Chi_Minh`, chuyển sang UTC khi truy vấn. Aggregate `StockTransaction.transaction_type=outbound` có `MovementProvenance.purpose=purchase_request_fulfillment`, join một lần theo khóa transaction. Đối chiếu lượng và số giao dịch, ghi riêng hai chân chuyển kho, xuất thông thường và xuất không có provenance xác định. Không gán số lượng 0 thành kết luận về nhu cầu. Không nội suy ngoài tọa độ kho. Không lọc mất kho chỉ vì nằm ngoài phạm vi snapshot đường.
- [ ] Kiểm chứng ở PostgreSQL disposable bằng dữ liệu ghi qua API hiện có hoặc fixture thiết lập rõ. Tập trung vào kho gần nhất thiếu tồn, hòa hoặc đúng bằng lượng cần, múi giờ và biên kỳ, M3/M4/M7, metadata lỗi và đủ ba role. Chụp digest/counter trước và sau truy vấn GIS cho `stocks`, `transactions`, `movement_provenance`, `stock_transfers`, `purchase_requests` và workflow. Giữ nguyên regression auth và contract.
- **Tạo** `app/gis/repository.py`, `app/gis/service.py`, `app/gis/router.py`, `tests/test_gis_api.py`, `tests/postgres/test_gis_api.py`. **Sửa** `app/main.py`, `app/core/config.py`, `app/auth/dependencies.py`. Tái sử dụng service/repository M3/M4/M7 qua read adapter của M10. Bao phủ ma trận quyền GIS trong test mới.

### 4. Giao diện và hợp đồng trực quan

- [ ] Viết test component trước, gồm role guard, loading/retry, rỗng, snapshot lỗi, đổi tham số/phiên khi request chưa xong, điều khiển bàn phím, bảng thay thế và tính nhất quán chú giải.
- [ ] Thêm `/gis` dưới App Shell và menu/breadcrumb **Bản đồ kho**, sau mục Kho hàng cho admin/warehouse. Dùng chung permission helpers và API client của app. Client không thấy menu và bị guard khi nhập route trực tiếp. Query nhận context phiên hiện tại, hủy hoặc bỏ kết quả đã cũ khi logout, đổi role hoặc thay bộ lọc. Có trạng thái 401/403 hiện hành. Không sửa lưu trữ token hoặc auth behavior.
- [ ] Desktop tham chiếu 1440 px. Header và điều khiển SKU, lượng, điểm đến ở đầu. Hai cột gồm danh sách kho và sơ đồ tuyến. Kho đã chọn hiển thị chiều dài, đoạn nối snap nét đứt, phiên bản/nguồn, thời điểm đọc tồn, reason khi không có đường và tham khảo M7 nếu hợp lệ. Điểm đến nhập tọa độ, chọn kho hoặc nhập ID yêu cầu mua hàng. Có mode đọc tuyến theo ID chuyển kho. Bên dưới là bảng nhiệt theo kỳ với điểm kho, thang màu và bảng số liệu. SVG hiển thị hình học tuyến và điểm kho có dữ liệu; không có nền bản đồ từ dịch vụ ngoài. Tách viewport đường và heatmap để kho ngoài vùng tuyến vẫn đọc được. Mobile xếp một cột, bảng có scroll riêng nếu cần, điều khiển focus rõ, thông báo cập nhật có trạng thái hỗ trợ trình đọc màn hình. Dùng tiếng Việt, shared Button/Input/Select/PageHeader/EmptyState/FeedbackMessage/DataTable và tokens, không thêm thư viện UI hoặc bản đồ. Ghi attribution bên cạnh hình. Dùng nhãn “Kho và tồn kiểm thử” khi chạy fixture nghiệm thu. Review ảnh theo hợp đồng này vì chưa có node Figma GIS được duyệt.
- **Tạo** `client/src/features/gis/GISPage.tsx`, `GisMap.tsx`, `GISPage.test.tsx`, `GisMap.test.tsx`, `api.ts`, `types.ts`, `gis.css` (cùng thư mục) và `client/src/shared/assets/icons/gis.svg`. **Sửa** `client/src/app/router.tsx`, `client/src/shared/layout/Sidebar.tsx`, `client/src/shared/layout/Breadcrumbs.tsx`, `client/src/shared/lib/permissions.ts`, `client/src/shared/lib/permissions.test.ts`, `client/e2e/auth-client.spec.ts` và `client/tests/ui-shell-remediation.test.js`. Hai file test cuối chỉ bổ sung kỳ vọng menu GIS theo role và breadcrumb liên quan, giữ các assertion auth và menu khác. Ca truy cập thẳng `/gis` của client nằm trong test M10.

### 5. E2E, review và bàn giao

- [ ] Dùng stack M10 `sw-m10-gis-e2e` với volume/network/image có nhãn M10, web bind `127.0.0.1:18082`, DB riêng nội bộ `sw_m10_gis_e2e` không publish cổng. Cổng 18082 đã bind thử thành công khi lập kế hoạch. Xác minh lại cổng, project/label, DB owner, DB schema, phiên kết nối và đường dẫn catalog trước mọi seed. Mật khẩu và JWT test lấy từ env ngoài repo, không in ra log. Dùng PostgreSQL 16 và Dockerfile hiện tại. Migration dùng bản hiện có. Seed ba role qua luồng hiện có, tạo kho/stock/giao dịch có tên fixture. Mount catalog và file seed M10 chỉ đọc. Seed script chạy dưới user API qua `/fixtures/prepare_gis_e2e.py`. Dùng một DB mới cho mỗi lần chạy synthetic/public hoặc seed idempotent có kiểm tra receipt M10. Runner yêu cầu `E2E_BASE_URL=http://127.0.0.1:18082` và `E2E_GIS_SCENARIO=synthetic` hoặc `public`, kiểm tra ID snapshot thực tế trước bước nghiệp vụ. Runner chỉ chấp nhận đúng HTTP loopback 18082, không gửi credential qua URL, không thu trace chứa token. Không đụng tài nguyên M7–M9.
- [ ] Viết và chạy Playwright với API/DB thật. Chạy suite synthetic và public tách biệt theo snapshot ID. Synthetic bao phủ ca lỗi, đứt đường, bất đồng thứ hạng và định kỳ. Public chạy ít nhất một tuyến thật với kho/tồn fixture; đối chiếu hướng và chiều dài theo graph đã verify. Kiểm tra desktop 1440 px và mobile 390 px, bàn phím, danh sách/heatmap, 401/403, token, reload và sidebar ba role. Đo runtime, lưu ảnh đã loại credential ngoài Git. Không dùng request mocking để chứng minh những ca này.
- [ ] Chạy focused, regression và static theo phần dưới. Khi đủ implementation, chuyển `IN_PROGRESS -> VERIFYING`; sau verification đạt, chuyển `VERIFYING -> REVIEWING` để main đối chiếu diff, ảnh, quyền, attribution, provenance và từng AC. Nếu còn finding thì ghi trạng thái lùi đúng workflow, giới hạn ba vòng sửa. Chỉ đánh dấu AC có bằng chứng trực tiếp. Phân biệt chứng minh phần mềm với hiệu quả logistics. Nếu snapshot công cộng hay browser chưa kiểm được, giữ AC tương ứng chưa hoàn tất. Hiệu quả vận hành giữ `NOT VERIFIED` khi thiếu dữ liệu đủ điều kiện. Cập nhật bằng chứng, review và trạng thái trong task này.
- **Tạo** `docker-compose.gis-e2e.yml`, `tests/prepare_gis_e2e.py`, `client/playwright.gis.config.ts`, `client/e2e-gis/gis.spec.ts`. Không sửa runner hay guard của milestone khác. File task là ledger duy nhất. Mọi file ngoài danh sách cần amendment trước khi sửa.

## Verification Commands

### Focused

- Backend từ root với Python 3.12 và môi trường cô lập có extra phù hợp. Cài `python -m pip install -e ".[dev,forecasting,anomalies,gis]"`. Chạy `python -m pytest -q tests/test_gis_catalog.py tests/test_gis_osm.py`, `python -m pytest -q tests/test_gis_routing.py`, rồi `python -m pytest -q tests/test_gis_api.py tests/postgres/test_gis_api.py` sau khi guard xác nhận DB test và migration head.
- Snapshot công cộng. Chạy `python -m app.gis.cli prepare --input <PBF> --source-url <HTTPS> --source-sha256 <SHA256> --output-root <DIR>` và `python -m app.gis.cli verify --catalog-root <DIR> --snapshot-id <ID>`. Ghi hash đã đối chiếu, timestamp, bounds, graph stats, peak RSS và phép thử tuyến. Hash dùng để tái lập dữ liệu công cộng, không in giá trị credential.
- Frontend trong `client/`. Chạy `npm.cmd run test -- --run src/features/gis/GISPage.test.tsx src/features/gis/GisMap.test.tsx src/shared/lib/permissions.test.ts` và `npm.cmd run test:host`.
- E2E M10. Dùng `docker compose --env-file <ENV-M10-OUTSIDE-GIT> -f docker-compose.gis-e2e.yml up -d --build`, xác nhận isolation rồi chạy `docker compose --env-file <ENV-M10-OUTSIDE-GIT> -f docker-compose.gis-e2e.yml exec -T api python /fixtures/prepare_gis_e2e.py`. Chạy `npm.cmd run e2e -- --config playwright.gis.config.ts` trong `client/` cho hai lần cấu hình snapshot riêng. Ghi số test, API outcomes, ảnh desktop/mobile và trạng thái dữ liệu.

### Regression

- Backend chạy `python -m pytest -q` với PostgreSQL disposable đã được kiểm tra identity và migrate. Reuse hai DB guard hiện có `sw_m7_replenishment_test` và `sw_m7_replenishment_migration_test` trên loopback 18547 trong tài nguyên mới có label M10. Đây là định danh do guard yêu cầu, tuyệt đối không trỏ vào DB hoặc volume của M7. Cổng 18547 đã bind thử được; kiểm tra lại trước khi mở. Trước migration và pytest local, xác nhận loopback, label/tên container, owner cả hai DB, không có session cạnh tranh và `DATABASE_URL` trùng `TEST_DATABASE_URL`. Chỉ migrate DB test chính tới head, dành DB migration riêng cho fixture. Chạy `python -m tests.run_quality_ci windows` trên Windows để xác nhận riêng đúng ba test guard. `python -m tests.run_quality_ci backend` dành cho job Linux trên GitHub Actions vì runner yêu cầu context CI. Nếu không thể dựng tài nguyên local đúng định danh, ghi blocker hoặc bổ sung kết quả Quality sau khi được phép publish. Giữ nguyên guard.
- Frontend trong `client/`. Chạy `npm.cmd ci`, `npm.cmd run test:all`, `npm.cmd run typecheck` và `npm.cmd run build`. Chạy lại luồng auth/menu hiện có trên stack cô lập với config Playwright hiện tại. Ghi rõ phạm vi riêng của browser M10, regression và CI.

### Review Focus

- AC-1 và AC-2 dùng bằng chứng checksum và header thực, ca tampering/CRS/đường ngoài biên, Dijkstra và một tuyến công cộng. Fixture PBF chỉ chứng minh parser và profile.
- AC-3 và AC-4 so sánh query với dữ liệu PostgreSQL, gồm kho gần nhưng thiếu hàng, kho chưa có tọa độ, hai chân chuyển kho và biên kỳ UTC. Kiểm tra đơn vị, nhãn và từng lớp kết quả.
- AC-5 kiểm tra quyền trước khi đọc ID, dữ liệu research hoặc binding M7 sai và digest trước/sau. AC-6 yêu cầu ảnh desktop/mobile và Playwright qua API thật. AC-7 kiểm tra ba lớp bằng chứng tách biệt, attribution và giới hạn profile trước khi ghi kết quả.

### Static and Diff

- Chạy `python -m ruff check app tests alembic`, `git diff --check`, review từng file theo allowlist và scan secret chỉ báo kết quả. Kiểm tra diff staged/unstaged và chạy test liên quan trước mỗi commit được duyệt.
- Đối chiếu bằng chứng từng AC, nguồn OSM và hiển thị attribution, phân quyền cùng DB before/after, số liệu và nhãn fixture. Lưu kết quả vào task. Ghi rõ cách xử lý artifact khi chuyển giao, không đưa PBF, graph, ảnh chứa dữ liệu riêng hoặc credential vào Git.

## Progress Log

### 2026-11-07 — Tạo bản đề xuất M10

Người dùng đồng ý chuẩn bị task M10 sau khi xác minh Quality M9 trên nhánh tích hợp. Đọc roadmap, spec, ba dependency đã khai báo, cấu trúc tọa độ/tồn và nguồn đường chính thức. Tạo task tại đường dẫn do roadmap chỉ định. Đề xuất dùng bản chụp Geofabrik/OSM vùng TP.HCM, xử lý cục bộ và kiểm tra tuyến thực. Đang chờ duyệt thiết kế và kế hoạch chi tiết.

Builder review chỉ đọc đối chiếu bảy AC với roadmap và spec. Main làm rõ phạm vi đầu ra bản đồ và nghĩa vụ ODbL trước công bố, nhãn fixture cho kho/tồn dùng nghiệm thu và ca phân quyền/binding khi đọc M3/M4/M7. Thiết kế vẫn chờ người dùng duyệt.

### 2026-11-07 — Duyệt thiết kế, chuẩn bị kế hoạch chi tiết

Người dùng trả lời “ok” để duyệt thiết kế và chuẩn bị kế hoạch. Main đối chiếu service và schema M3/M4/M7, thống nhất điểm đọc hiện có và ghi rõ giới hạn M7 fixture. Đã bind thử loopback 18082 và 18547 rồi giải phóng. Bổ sung các checkpoint, hợp đồng API, giới hạn artifact, thiết kế màn hình, allowlist và lệnh kiểm thử. Chờ duyệt kế hoạch trước khi chuyển trạng thái.

### 2026-11-07 — Kiểm tra trước triển khai M10

Người dùng trả lời “ok” duyệt kế hoạch chi tiết. Xác nhận ba dependency `DONE`, tạo worktree riêng và nhánh `codex/m10-warehouse-gis` từ `547eb1c363d6804c45fcbb159d14a8fe7eef095c`. Checkout chính giữ nguyên các thay đổi ngoài task.

Checkpoint nguồn bị chặn. HTTPS trả 404 cho cả `vietnam-261027.osm.pbf` và tệp MD5 đã khóa. Danh mục Geofabrik hiện liệt kê `vietnam-261105.osm.pbf`. HTTPS HEAD cho bản này trả 200 với 332.216.218 byte và tệp MD5 qua HTTPS hợp lệ về định dạng và tên. Chưa tải PBF, chưa kiểm hash hoặc đọc header. Đề xuất thay riêng archive/sidecar thành bản 261105, giữ vùng, giấy phép, quy tắc hash, freshness, giới hạn và các AC. Dừng trước triển khai theo checkpoint 1 và chờ duyệt đổi nguồn. Task giữ `READY`.

### 2026-11-07 — Phê duyệt đổi archive và bắt đầu M10

Người dùng trả lời “ok” để duyệt thay archive `vietnam-261027.osm.pbf` cùng MD5 bằng `vietnam-261105.osm.pbf` cùng MD5, vì nguồn cũ trả 404. Phạm vi, giới hạn tài nguyên, định tuyến, giấy phép, freshness và bảy AC giữ nguyên.

`READY -> IN_PROGRESS`. Xác nhận baseline Git 547eb1c, ba dependency `DONE`, plan/spec authority và allowlist đã duyệt. Chuyển tài liệu task chưa được track vào cùng đường dẫn tương đối trong worktree M10 để chỉ có một ledger. Giao native subagent triển khai từng checkpoint; main giữ trách nhiệm review và verification.

### 2026-11-07 — Checkpoint 1 đã xác minh

Native subagent đã làm TDD và triển khai bộ nhập đường, schema, catalog và CLI trong allowlist. Main review điều kiện đổi byte PBF giữa hash và parse, tái sử dụng snapshot, junction tròn và restriction theo thời gian/loại xe. Đã sửa và chạy lại test. Checkpoint 2 bắt đầu sau khi đồ thị thật lần đầu đạt giới hạn; bản CLI sau sửa cũng đã được chạy và xác minh riêng.

### 2026-11-07 — Checkpoint 2 đã xác minh

A* dùng trạng thái theo cạnh đi vào và chỉ mục snap không gian, có ngân sách dùng chung và kết quả lỗi riêng. Main review implementation cùng oracle test và đối chiếu thêm ba cặp điểm trên snapshot đường công cộng. Chuyển tiếp checkpoint 3 cho cùng native subagent.

### 2026-11-07 — Review checkpoint 3

Checkpoint 3 API đã xác minh tập trung. Native subagent tiếp tục trên code đã lưu sau khi phiên trước bị giới hạn sử dụng. Main review năm endpoint, cache snapshot, lọc theo quyền, truy vấn một statement, fallback và provenance. Phát hiện test ma trận quyền cũ so sánh toàn bộ bảng và chưa có hai quyền GIS. Đã xin duyệt bổ sung đúng hai kỳ vọng trong file ngoài allowlist. Giao checkpoint 4 cho cùng subagent trong lúc chờ.

### 2026-11-07 — Amendment kiểm thử ma trận quyền

Người dùng trả lời “Duyệt thêm đúng hai kỳ vọng GIS”. Cho phép bổ sung đúng hai kỳ vọng `Permission.GIS_READ` và `Permission.GIS_ROUTE` cho `admin` và `warehouse` trong `tests/postgres/test_rbac_matrix.py`. Lý do là test regression so sánh toàn bộ `PERMISSION_ROLES` và 22 mục hiện có đều khớp. Đây là amendment duy nhất của allowlist checkpoint 3. Giữ nguyên các assertion, grant, hợp đồng API và baseline còn lại.

### 2026-11-08 — Checkpoint 4 và sửa regression

Hai kỳ vọng GIS đã được bổ sung theo amendment, test chính xác qua. Full backend lần đầu thấy import SQLAlchemy ngoài ranh giới router và thư mục artifact M7 không ghi được trên mount read-only. Native subagent đã sửa router bằng kiểu dependency sẵn có. Main xác minh test artifact M7 qua với tmpfs tách riêng rồi chạy lại toàn bộ backend.

Checkpoint 4 hoàn tất implementation. Main review route guard, lựa chọn SKU/kho thật, xử lý request đến muộn và cách trình bày tuyến/khoảng cách địa lý. Chuyển checkpoint 5 cho cùng subagent để chuẩn bị Compose, seed an toàn và Playwright. Kiểm tra ảnh desktop/mobile còn chờ.

### 2026-11-08 — Bắt đầu verification cuối

`IN_PROGRESS -> VERIFYING`. Native subagent đã hoàn tất Compose, seed, config và suite E2E trong allowlist. Public Playwright đã qua trước điều chỉnh cách chụp ảnh; auth regression qua. Main review code, thêm yêu cầu chụp từ đầu trang và giữ mask tài khoản. Chạy lại cả hai kịch bản với bằng chứng ảnh cuối, rồi xác nhận toàn bộ AC trước khi review cuối.

### 2026-11-08 — Vòng sửa verification 1

`VERIFYING -> IN_PROGRESS`. Sau public GIS 6/6 và auth regression 6/6, synthetic GIS desktop/mobile có 5 pass, 1 fail. Lỗi ở test mobile khi đăng nhập role warehouse sau admin. Listener bắt response `/gis/status` từ trang cũ và `page.goto` giải phóng response body. Sửa trong file E2E đã duyệt để chỉ điều hướng nếu cần, chờ GIS hiện hành và đọc API qua phiên hiện tại. Giữ mọi assertion quyền, token, dữ liệu và route. Đây là vòng sửa 1 trong verification cuối.

### 2026-11-08 — Verification lại sau sửa đồng bộ

`IN_PROGRESS -> VERIFYING`. Subagent sửa duy nhất helper mở GIS trong test E2E. Main kiểm diff cho thấy các assertion metadata và reload vẫn giữ. Rebuild stack từ cây hiện tại, chạy lặp ca mobile đổi role rồi chạy đầy đủ trên cả hai snapshot.

### 2026-11-08 — Vòng sửa verification 2

`VERIFYING -> IN_PROGRESS`. Sau sửa đổi role, synthetic ca mobile chạy lặp 5/5 và suite 6/6. Public chạy đồng thời frontend regression có 3 ca desktop hết timeout assertion 5 giây ở nhãn tồn khi trạng thái còn “Đang tải dữ liệu đường”. Ba ca mobile sau khi cache nóng đạt. Thời gian đọc catalog công cộng lần đầu đã quan sát hơn 5 giây. Sửa thứ tự helper để chờ response thật của phiên hiện hành trước khi assert các nhãn. Không thêm sleep/retry và không đổi ứng dụng. Vòng sửa verification 2.

### 2026-11-08 — Verification cold cache

`IN_PROGRESS -> VERIFYING`. Đã đổi đúng thứ tự chờ trong helper E2E theo vòng sửa 2. Main kiểm diff xác nhận không đổi assertion, timeout, retry hoặc app. Frontend regression độc lập đạt đủ 430 Vitest, 90 host, typecheck/build. Khởi động lại API công cộng để kiểm chứng cold cache trước khi nghiệm thu.

### 2026-11-08 — Vào review cuối

`VERIFYING -> REVIEWING`. Sau hai sửa đồng bộ test, cả hai scenario đều qua trên desktop/mobile với API và PostgreSQL thật. Đã kiểm thử auth regression, đối chiếu ảnh desktop/mobile, regression backend/frontend, static/diff và các tiêu chí theo bằng chứng. Main review cuối toàn bộ diff với baseline được duyệt.

### 2026-11-08 — Review đạt và hoàn tất M10

`REVIEWING -> DONE`. Main đối chiếu implementation do native subagent viết với toàn bộ baseline, bảy AC, quyền backend, tính chỉ đọc, provenance, ảnh và diff theo allowlist. Các finding kiến trúc, ma trận quyền và đồng bộ browser đã được sửa và xác minh lại. Review `APPROVED`. Giữ stack local ở snapshot công cộng để xem lại. Chưa stage, commit, push hoặc merge.

## Verification Evidence

Đã kiểm tra trạng thái dependency và trang nguồn/giấy phép. Bản đồ thị, tuyến, API, browser và hiệu quả thực tế chưa xác minh.

Preflight trên baseline `547eb1c`. `npm.cmd ci` thành công. `npm.cmd run test:all` qua 414 Vitest và 90 host test. `npm.cmd run build` thành công, có cảnh báo bundle trên 500 kB. Backend smoke `python -m pytest -q -p no:cacheprovider tests/test_health.py tests/unit/test_config.py tests/test_warehouses.py` qua 35 test trên Python 3.12.16 với container ngắt mạng và mã nguồn mount chỉ đọc.

Backend regression chưa được xác minh trong lượt preflight này. Lọc `-m 'not postgres'` vẫn chọn test DB không gắn marker nên lần đầu dừng. Lần chạy `--ignore=tests/postgres` ghi nhận 952 pass, 20 fail, 16 skip và 3 deselect. Image tái sử dụng chạy UID 10001 không có username nên các test artifact gặp lỗi `getpass.getuser()`. Đã thử chạy lại với `LOGNAME` và giới hạn luồng rồi chủ động dừng bộ rộng trong lúc checkpoint nguồn còn bị chặn. Chưa chạy PostgreSQL hoặc browser. Hai cổng 18082/18547 bind thử thành công và đã giải phóng. `git diff --check` đạt và worktree code sạch.

Nguồn công cộng 261105 đã tải ngoài Git. Kích thước 332.216.218 byte, MD5 khớp sidecar chính thức qua HTTPS và SHA-256 `b82d04d01ac84789d46d688ee5cd1f3b0d8c96c26466c31818986ba26ad78250`. Đọc độc lập header PBF cho replication timestamp `2026-11-05T21:23:02Z`, sequence 4961. Chưa xác minh extraction, graph hoặc tuyến.

Checkpoint 1. `python -m pytest -q -p no:cacheprovider tests/test_gis_catalog.py tests/test_gis_osm.py` có 49 pass trên Python 3.12 Linux, osmium 4.3.2. `python -m ruff check --no-cache app tests alembic` và `git diff --check` đạt. Dùng container không có mạng, mount PBF chỉ đọc. Lần quét sơ bộ trong vùng có 380.153 node, 36.584 way ứng viên và 137.902 đoạn trước khi lọc.

CLI `prepare` bản sau review tạo snapshot `gsv1-83bb3fea3577b8821509cb5d7cbe0fd2de608965e81485045241bcdbd044f889` trong 223,85 giây, peak RSS 273.572 KiB. Graph 12.084.338 byte có 96.249 node, 178.796 cạnh và 126 cặp hạn chế. Hai lần trích xuất cho cùng SHA-256 graph `01280b60a4dbc0ee197177561f9a80f2b2e7c4d17d4147b48bba4923cd377986`. Hash đồ thị được kiểm độc lập, CLI `verify` qua khi mount catalog chỉ đọc. Mốc này chưa chứng minh tuyến.

Baseline tích hợp. PostgreSQL chỉ nghe 127.0.0.1:18547 trong network namespace của container M10, không publish ra host. Đã kiểm danh tính, owner và session cạnh tranh trước migration head `20261105_0005`. Test hai file `tests/postgres/test_transfers_api.py` và `tests/postgres/test_purchase_requests_api.py` qua 96 ca với guard SQL. `python -m tests.run_quality_ci windows` xác nhận đủ ba guard Windows. Chromium cache và ba image nền cho Dockerfile E2E đã sẵn sàng.

Checkpoint 2. Main chạy `python -m pytest -q -p no:cacheprovider tests/test_gis_catalog.py tests/test_gis_osm.py tests/test_gis_routing.py`, 64 pass. Với snapshot `gsv1-83bb3fea3577b8821509cb5d7cbe0fd2de608965e81485045241bcdbd044f889`, hai đầu WGS84 (106.6921, 10.7767) và (106.70042, 10.78077) snap tới ID 14118824113 và 7501051433. A* và oracle Dijkstra độc lập cùng trả 4.088.267 mm, 124 tọa độ; A* settle 1.113 trạng thái trong 3,49 ms. Khoảng cách nối snap riêng 20.629 mm và 4.693 mm. Hai cặp điểm khác trong vùng đều trả `no_route` nhất quán với Dijkstra. Số đo là bằng chứng đường công cộng theo profile và vùng M10. Hiệu quả logistics chưa xác minh.

Checkpoint 3. Native subagent chạy 93 test GIS ngoài PostgreSQL và 3 test GIS trên PostgreSQL, đều đạt. Main chạy độc lập bản 91 test trước khi thêm hai ca cache/nhãn fixture và chạy 99 test API PostgreSQL (GIS, M3, M4) với guard trước/sau, đều đạt. Bộ test GIS kiểm digest của tồn, giao dịch, provenance, chuyển kho, yêu cầu mua hàng và workflow trước/sau. Ruff và git diff check đạt. Full backend regression đang chờ cập nhật test ma trận quyền đã phát hiện.

Checkpoint 4. Native subagent chạy `npm.cmd run test:all` qua 430 Vitest + 90 host, `npm.cmd run typecheck` và `npm.cmd run build` qua. Main chạy độc lập 40 test UI/quyền và typecheck/build thành công. Build có cảnh báo bundle trên 500 kB. Bản build API Dockerfile thành công. CLI của image đọc được catalog công cộng từ mount chỉ đọc. Backend Windows `tests/test_seed.py` có 47 pass, gồm kiểm tra Compose.

Backend regression lần chạy cuối. `python -m pytest -q --tb=short -p no:cacheprovider` với SQL guard, PostgreSQL disposable và 3 node dành riêng cho Windows deselect có 1.623 pass, 16 skip, 3 deselect, 0 fail trong 496,38 giây. 16 skip là các ca kiểm tra Compose do container không có Docker CLI. Suite `tests/test_seed.py` trên Windows đã chạy đủ 47 pass, gồm 16 ca này, và runner Windows riêng có 3 pass. Guard PostgreSQL qua trước và sau. Mã nguồn mount chỉ đọc, vùng fixture M7 dùng tmpfs riêng tại `/workspace/artifacts`.

Verification cuối. `npm.cmd run e2e -- --config playwright.gis.config.ts` qua 6/6 với snapshot công cộng sau khi khởi động lại API (15,8 giây), và 6/6 với đồ thị tổng hợp (7,8 giây). Ca đổi role mobile chạy lặp 5/5 sau sửa vòng 1. `npm.cmd run e2e -- e2e/auth-client.spec.ts --reporter=line` qua 6/6 sau khi thử snapshot công cộng. Compose build thành công với Dockerfile hiện có. Seed và verify receipt chạy đúng DB riêng, volume riêng, web `127.0.0.1:18082`, DB/API không publish cổng và mount catalog chỉ đọc. Ảnh công cộng `m10-gis-public-desktop.png`, `m10-gis-public-mobile.png` và cặp ảnh synthetic lưu ở `C:/Temp/codex-m10-gis-artifacts/browser-evidence`, đã che khối tài khoản. Review desktop 1440 px và mobile 390 px theo thiết kế M10 đã duyệt.

Frontend độc lập lần cuối `npm.cmd run test:all` có 430 Vitest + 90 host pass, `npm.cmd run typecheck` và `npm.cmd run build` đạt. Một ca timing router Replenishment dao động ở lần chạy trước và đã qua ở lần chạy độc lập cuối. Vite cảnh báo bundle JS 703,13 kB. Ruff, `git diff --check`, kiểm whitespace file mới và allowlist 41 file đạt. Scan credential trong thay đổi có 0 ứng viên, giá trị không được in.

### Đối chiếu acceptance criteria

- AC-1. MD5 Geofabrik, SHA-256 nguồn/graph, UTC header, WGS84/bounds, giấy phép và attribution kiểm qua CLI/Playwright. Test catalog kiểm tampering, CRS sai, đơn vị sai và stale. Browser và graph test kiểm ngoài vùng. Tuyến công cộng đã khớp oracle.
- AC-2. 15 ca routing kiểm A*/Dijkstra, chiều đường, rẽ theo cạnh trước, tie, graph rời, khoảng snap và giới hạn. Catalog từ chối cạnh lỗi. Cận dưới và cách làm tròn ghi trong thiết kế và code.
- AC-3. PostgreSQL và browser kiểm kho gần thiếu tồn, nhiều kho đủ tồn, đúng bằng lượng cần, thiếu stock, SKU ngừng hoạt động, kho thiếu vị trí và dữ liệu ngoài biên bị từ chối. Timestamp, đơn vị và kết quả xếp hạng có trong response.
- AC-4. Browser kiểm tuyến, đoạn snap và khoảng cách địa lý tách riêng. Heatmap chọn SKU/kỳ theo `Asia/Ho_Chi_Minh`, so biên UTC, mốc đầu/cuối, số 0, kho thiếu vị trí, hai chân chuyển kho và chú giải kèm đơn vị.
- AC-5. Unit/DB/E2E kiểm ba role, 401/403, lookup M3/M4 có quyền, ID ngoài phạm vi và M7 đúng/sai binding hoặc research. DB digest trước/sau xác nhận GIS chỉ đọc. Regression backend và auth qua.
- AC-6. Hai suite browser trên desktop/mobile thật trong stack riêng. Các ca tải, rỗng, offline/thử lại, không quyền, bàn phím, tuyến có/không và nhãn dữ liệu đã chạy qua. Ảnh được review theo hợp đồng trực quan M10.
- AC-7. Bằng chứng graph tổng hợp, tuyến đường công cộng và đánh giá vận hành được tách. Mạng đường theo profile ô tô tham khảo trong vùng TP.HCM đã nêu. Hiệu quả logistics giữ `NOT VERIFIED`.

## Review Result

- Result: APPROVED
- Findings: Đã giải quyết các finding về kiểm chứng byte nguồn, áp dụng restriction, ranh giới router, ma trận quyền và đồng bộ Playwright. Không còn finding chặn phạm vi M10. Hiệu quả vận hành giữ `NOT VERIFIED` theo AC-7.

## Completion Evidence

`DONE`, 7/7 AC đã xác minh, review `APPROVED`. Backend regression 1.623 pass trên Linux với PostgreSQL và guard; các ca Compose được chạy trên Windows, ba guard Windows pass. Frontend 520 pass, typecheck/build pass. Hai kịch bản GIS có tổng 12 Playwright pass, auth regression 6 pass. Ruff, diff, allowlist và scan credential đạt. Dữ liệu nghiên cứu hiệu quả logistics chưa xác minh. Commit `not required by task scope`; thay đổi chưa stage. Ngày hoàn tất là 2026-11-08.
