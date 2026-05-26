# Kế hoạch kỹ thuật — Ứng dụng trung gian LiDAR → OPC UA → SCADA

**Phiên bản:** 1.0 · Tháng 5/2026
**Phạm vi:** Chỉ phần middleware Python trung gian — không bao gồm phần AI detection trên Ubuntu, không bao gồm cấu hình SCADA.

---

## 1. Phân tích sơ đồ kiến trúc v3

### 1.1 Luồng dữ liệu chính (4 bước)

Sơ đồ kiến trúc v3 mô tả luồng dữ liệu đi qua 5 bước tuần tự:

**Bước ①** — Máy Ubuntu (chạy LidarPerceptWindow, AI detection, tracking) gửi dữ liệu thuyền đã xử lý sang ứng dụng Python qua **WebSocket** (không phải HTTP polling).

**Bước ②** — Ứng dụng Python nhận message WebSocket, parse JSON (hoặc dạng dữ liệu khác), ép kiểu dữ liệu (validate + chuyển sang Double).

**Bước ③** — Dữ liệu được ghi vào các OPC UA node trong bộ nhớ đệm nội bộ của OPC UA server.

**Bước ④** — SCADA **subscribe** các node dữ liệu thuyền từ OPC UA server, nhận cập nhật tự động mỗi khi giá trị thay đổi.

### 1.2 Vai trò thực tế của middleware

Theo sơ đồ v3, ứng dụng Python đóng **hai vai trò đồng thời**:

- **WebSocket server** (port 8080): nhận dữ liệu thuyền đẩy từ máy Ubuntu. Đây là mô hình push — Ubuntu chủ động gửi, middleware lắng nghe — khác với mô hình poll (middleware chủ động hỏi) (có thể sử dụng NATS để tối ưu tốc độ).

- **OPC UA server** (port 4840, thư viện asyncua): host toàn bộ address space chứa các node dữ liệu thuyền, để SCADA kết nối vào đọc/ghi. Middleware **không phải OPC UA client** ghi vào SCADA, mà chính nó **là** OPC UA server.

### 1.3 Các thành phần bên trong ứng dụng Python

Dựa trên sơ đồ, ứng dụng Python chạy trên Windows gồm 4 thành phần logic chính:

1. **WebSocket server** — lắng nghe port 8080, nhận JSON từ Ubuntu
2. **Bộ parse + validate** — ép kiểu, kiểm tra range, chuẩn hóa dữ liệu
3. **Bộ nhớ đệm** — lưu snapshot mới nhất của tất cả thuyền (dict trong RAM hoặc Redis)
4. **OPC UA server** — expose các node cho SCADA subscribe/write, tự cập nhật node khi cache thay đổi

Tất cả chạy trong một tiến trình asyncio duy nhất trên Windows.

---

## 2. Thư viện áp dụng cho luồng dữ liệu

| Vị trí trong luồng | Thư viện | Vai trò |
|---|---|---|
| Bước ① — Nhận dữ liệu từ Ubuntu | `websockets` | WebSocket server, lắng nghe port 8080 |
| Bước ②③④⑤ — OPC UA server | `asyncua` | Host address space, phục vụ subscription và write từ SCADA |

Cả hai thư viện đều async-native, chạy chung một event loop `asyncio` trong cùng tiến trình Python ≥ 3.11.

**`asyncua`** là thư viện OPC UA duy nhất cho Python còn được bảo trì tích cực (thư viện cũ `python-opcua` đã deprecated từ 7/2022). Trong kiến trúc v3, asyncua đóng vai trò **Server** — không phải Client.

---

## 3. Thiết kế OPC UA Address Space

### 3.1 Namespace

| Mục | Giá trị đề xuất |
|---|---|
| Namespace URI | `urn:<site-name>:lidar-bridge` (đổi theo quy ước nội bộ) |
| Namespace Index | `ns=2` (runtime, không hard-code index vì index 0 và 1 đã dành cho OPC UA core) |

### 3.2 Cấu trúc node đề xuất

Dựa trên sơ đồ v3, OPC UA address space nên có cấu trúc sau:

```
Objects/
└── Ships/
    ├── Count          [UInt16, RO]     ← số thuyền đang phát hiện
    ├── DataSource     [String, RO]     ← "LIVE" | "SIM" | "STALE"
    ├── Request        [String, RW]     ← node để SCADA ghi lệnh vào
    ├── Ship_01/
    │   ├── Distance   [Double, m, RO]
    │   ├── Width      [Double, m, RO]
    │   ├── Length     [Double, m, RO]
    │   ├── Height     [Double, m, RO]
    │   └── Speed      [Double, kn, RO]
    ├── Ship_02/ ... Ship_10/
    └── Timestamp      [DateTime, RO]   ← thời điểm snapshot gần nhất
```

**Tổng: ~55 node Variable** (50 node thuyền + Count + DataSource + Request + Timestamp + dự phòng)

**Lưu ý:**
- Các node thuyền đặt **ReadOnly** (AccessLevel = CurrentRead) — chỉ middleware ghi nội bộ, SCADA chỉ đọc/subscribe.
- Node `Request` đặt **ReadWrite** — SCADA có thể ghi vào để gửi lệnh (bước ④ trong sơ đồ).
- Kiểu `Double` cho tất cả thông số đo, đơn vị mét (m) cho geometric và hải lý/giờ (kn) cho speed.
- Nên khai báo property `EngineeringUnits` (UNECE code `MTR` cho mét, `KNT` cho knots) và `EURange` để SCADA HMI tự hiển thị đơn vị và bound chart.

### 3.3 Cách SCADA tương tác

**Subscribe (bước ⑤):** SCADA tạo OPC UA subscription trên các node Distance, Width, Length, Height, Speed của Ship_01..10. Mỗi khi middleware cập nhật giá trị node (khoảng 1 Hz), asyncua server tự gửi notification cho SCADA. Đây là cơ chế chuẩn của OPC UA — hiệu quả hơn polling vì chỉ gửi khi có thay đổi.

**Write (bước ④):** SCADA ghi vào node `Request` để gửi lệnh. Middleware cần đăng ký callback (`write handler`) trên node này để xử lý khi SCADA ghi. Ví dụ: SCADA ghi `"RESET"` vào Request → middleware nhận callback → thực hiện reset cache.

---

## 4. Chiến lược chịu lỗi (Resilience)

### 4.1 Phía WebSocket (nhận dữ liệu từ Ubuntu)

| Tình huống | Hành vi đề xuất |
|---|---|
| Ubuntu chưa kết nối / mất kết nối | WebSocket server vẫn chạy, chờ reconnect. Chuyển sang chế độ SIM sau N giây không có message. |
| Message JSON lỗi format | Log warning, bỏ qua message đó, giữ giá trị cũ trong cache |
| Thiếu field cho 1 thuyền | Bỏ thuyền đó trong tick này, không bỏ cả batch |
| Giá trị ngoài range hợp lệ | Vẫn cập nhật vào OPC UA node (để operator thấy anomaly), log warning |
| Mất kết nối kéo dài | Chuyển DataSource sang "STALE" sau 5s, sang "SIM" sau 30s |

### 4.2 Chế độ SIM (mô phỏng)

Khi nguồn dữ liệu thật không khả dụng, middleware **không được để dashboard SCADA đứng im**. Cần có bộ sinh dữ liệu mô phỏng (SIM) chạy song song, tự động thay thế khi mất kết nối:

- Dữ liệu SIM dùng seed cố định + nhiễu Gaussian nhẹ, tạo giá trị hợp lý nhưng phân biệt được với dữ liệu thật.
- Node `DataSource` chuyển từ `"LIVE"` sang `"SIM"` — SCADA có thể dùng giá trị này để đổi màu hiển thị (xanh = LIVE, vàng = SIM).
- Chỉ log **sự kiện chuyển đổi** (`"Source switched to SIM"` / `"Source switched to LIVE"`), không log mỗi tick — tránh spam log trong thời gian mất kết nối dài.
- Về mặt OPC UA, khi ghi giá trị SIM nên đặt `StatusCode = UncertainSubstituteValue` — đây là cách chuẩn OPC UA báo hiệu "giá trị này là thay thế, không phải đo thực". Các HMI đạt chuẩn sẽ hiển thị quality flag tương ứng.

### 4.3 Phía OPC UA server

- asyncua server tự quản lý session và subscription — không cần logic reconnect phía server (SCADA tự reconnect khi mất kết nối).
- Cần bật `watchdog` để phát hiện session chết (SCADA tắt đột ngột mà không close session), giải phóng tài nguyên.
- Đồng bộ thời gian NTP: cả máy middleware và máy SCADA phải cùng NTP source. Lệch > 5 phút sẽ gây lỗi `BadSecurityChecksFailed` khi security bật.
