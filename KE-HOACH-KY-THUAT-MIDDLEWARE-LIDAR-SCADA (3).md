# Kế hoạch kỹ thuật — Ứng dụng giả lập LiDAR & SCADA Client

**Phiên bản:** 2.0 · Tháng 5/2026
**Phạm vi:** py-service — ứng dụng Python chạy trên máy dev, đóng vai trò giả lập nguồn dữ liệu LiDAR và giả lập SCADA client (PLC S7-1500) để test hệ thống trước khi có phần cứng thật.

---

## 1. Kiến trúc tổng thể

```
┌─────────────────────────────────────────────────────────────────┐
│                    Hệ thống thực tế (production)                │
│                                                                  │
│  Ubuntu (LiDAR AI)  ──UDP/HTTP──►  Middleware OPC UA Server     │
│                                   (192.168.0.43:4840)           │
│                                        ▲  │                     │
│                                   write│  │push / read          │
│                                        │  ▼                     │
│                                   PLC S7-1500 (SCADA client)    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    Môi trường dev / test                        │
│                                                                  │
│  py-service (máy dev)                                           │
│  ├── Giả lập LiDAR   ──UDP/HTTP──►  Middleware OPC UA Server    │
│  │   (gửi dữ liệu thuyền)           (192.168.0.43:4840)        │
│  │                                       ▲  │                   │
│  └── Giả lập SCADA  ──OPC UA──────  write│  │read              │
│      (đọc/ghi node)                       │  ▼                  │
│                                      (thay thế PLC S7-1500)     │
└─────────────────────────────────────────────────────────────────┘
```

**Điểm quan trọng:**
- **Middleware** (máy khác, `192.168.0.43:4840`) là **OPC UA Server** — host toàn bộ address space, do team khác phát triển và vận hành.
- **PLC S7-1500** là **OPC UA Client** — kết nối vào middleware để đọc dữ liệu thuyền và ghi dữ liệu hạ tầng.
- **py-service** không phải middleware, không phải OPC UA server — chỉ là công cụ test/giả lập trên máy dev.

---

## 2. Vai trò của py-service

py-service có **hai nhóm chức năng độc lập**:

### 2.1 Giả lập nguồn dữ liệu LiDAR

Thay thế máy Ubuntu (chạy AI detection) trong môi trường dev. Sinh dữ liệu thuyền giả rồi đẩy lên middleware theo cùng giao thức mà Ubuntu thật sẽ dùng.

| Endpoint | Mô tả |
|---|---|
| `POST /api/v1/ship` | Bắt đầu giả lập, đẩy dữ liệu thuyền qua WebSocket lên middleware |
| `POST /api/v1/stop` | Dừng giả lập |
| `GET /api/v1/status` | Xem trạng thái giả lập |
| `POST /api/v1/lidar/ingest` | Nhận dữ liệu LiDAR từ ngoài đưa vào (dùng khi test thủ công) |
| `GET /api/v1/lidar/latest` | Xem payload LiDAR mới nhất đã nhận |
| `POST /api/v1/mid/start` | Bắt đầu push dữ liệu thuyền lên middleware qua HTTP |
| `POST /api/v1/mid/stop` | Dừng push HTTP |
| `GET /api/v1/mid/status` | Xem trạng thái push HTTP |
| `POST /api/v2/ship/start` | Bắt đầu push dữ liệu thuyền qua UDP |
| `POST /api/v2/ship/stop` | Dừng push UDP |
| `GET /api/v2/ship/status` | Xem trạng thái push UDP |

### 2.2 Giả lập SCADA client (PLC S7-1500)

Thay thế PLC S7-1500 trong môi trường dev. Kết nối vào middleware OPC UA server tại `opc.tcp://192.168.0.43:4840` để đọc dữ liệu thuyền và ghi dữ liệu hạ tầng — đúng như PLC thật sẽ làm.

| Endpoint | Mô tả |
|---|---|
| `GET /api/v1/scada/nodes` | Trả về danh sách node mặc định (để tham khảo) |
| `POST /api/v1/scada/browse` | Duyệt address space của OPC UA server |
| `POST /api/v1/scada/read` | **Đọc** các node từ middleware (giả lập PLC đọc dữ liệu thuyền) |
| `POST /api/v1/scada/write` | **Ghi** các node vào middleware (giả lập PLC ghi dữ liệu hạ tầng) |

---

## 3. OPC UA Address Space (trên Middleware)

Toàn bộ node nằm trên middleware server. py-service chỉ là client kết nối vào.

### 3.1 Node đọc (SCADA/py-service đọc từ middleware)

Dữ liệu thuyền do middleware cập nhật từ LiDAR. SCADA/py-service đọc hoặc subscribe để nhận.

```
ns=2;s=Ships/Ship_01/Distance      [Double, m]
ns=2;s=Ships/Ship_01/Speed         [Double, kn]
ns=2;s=Ships/Ship_01/WarningLevel  [Double]
ns=2;s=Ships/Ship_01/Length        [Double, m]
ns=2;s=Ships/Ship_01/Width         [Double, m]
ns=2;s=Ships/Ship_01/Height        [Double, m]
```

### 3.2 Node ghi (SCADA/py-service ghi vào middleware)

Dữ liệu hạ tầng do SCADA đo và ghi lên. Middleware nhận rồi phân phối cho các hệ thống khác.

```
ns=2;s=Infrastructure/WaterLevelUpstream    [Double, m]   — mực nước thượng lưu
ns=2;s=Infrastructure/WaterLevelDownstream  [Double, m]   — mực nước hạ lưu
ns=2;s=Infrastructure/GateLock             [Bool]        — trạng thái đóng/mở âu
ns=2;s=Infrastructure/SluiceGate           [Double]      — cống
```

---

## 4. Luồng dữ liệu chi tiết

### 4.1 Luồng LiDAR → Middleware → SCADA

```
Ubuntu / py-service (giả lập)
    │  UDP hoặc HTTP push dữ liệu thuyền
    ▼
Middleware OPC UA Server (192.168.0.43:4840)
    │  cập nhật node Ships/Ship_XX/...
    ▼
PLC S7-1500 / py-service (giả lập)
    │  OPC UA Read hoặc Subscribe
    ▼
Nhận dữ liệu: Distance, Speed, Width, Length, Height, WarningLevel
```

### 4.2 Luồng SCADA → Middleware (ghi hạ tầng)

```
PLC S7-1500 / py-service (giả lập)
    │  OPC UA Write
    ▼
Middleware OPC UA Server (192.168.0.43:4840)
    │  cập nhật node Infrastructure/...
    ▼
Các hệ thống khác subscribe nhận giá trị mực nước, trạng thái cổng
```

---

## 5. Ví dụ sử dụng API

### Đọc dữ liệu thuyền từ middleware

```http
POST /api/v1/scada/read
Content-Type: application/json

{
  "endpoint_url": "opc.tcp://192.168.0.43:4840",
  "node_ids": [
    "ns=2;s=Ships/Ship_01/Distance",
    "ns=2;s=Ships/Ship_01/Speed"
  ]
}
```

Response:
```json
{
  "endpoint_url": "opc.tcp://192.168.0.43:4840",
  "values": {
    "ns=2;s=Ships/Ship_01/Distance": 12.5,
    "ns=2;s=Ships/Ship_01/Speed": 3.2
  }
}
```

### Ghi dữ liệu hạ tầng lên middleware

```http
POST /api/v1/scada/write
Content-Type: application/json

{
  "endpoint_url": "opc.tcp://192.168.0.43:4840",
  "nodes": [
    { "node_id": "ns=2;s=Infrastructure/WaterLevelUpstream", "value": 5.4, "value_type": "double" },
    { "node_id": "ns=2;s=Infrastructure/GateLock", "value": true, "value_type": "bool" }
  ]
}
```

Response:
```json
{
  "endpoint_url": "opc.tcp://192.168.0.43:4840",
  "results": {
    "ns=2;s=Infrastructure/WaterLevelUpstream": 5.4,
    "ns=2;s=Infrastructure/GateLock": true
  }
}
```

---

## 6. Dependency

| Thư viện | Vai trò |
|---|---|
| `asyncua` | OPC UA client — kết nối vào middleware để read/write/browse node |
| `websockets` | WebSocket client — đẩy dữ liệu thuyền giả lập lên middleware |
| `fastapi` | REST API server — expose các endpoint kiểm soát giả lập |

`asyncua` ở đây đóng vai **OPC UA Client**, không phải server.
