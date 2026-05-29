# Lidar Data Output Protocol

**Version**: V1.0  
**Date**: May 2026

---

## 1. Communication Method

The system sends target detection data via UDP. The receiver needs to listen on the configured port.

| Item | Value |
|------|-------|
| Protocol | UDP |
| Data Format | JSON (UTF-8 encoded) |
| Port | 10010 (configurable) |
| Frequency | ~100ms when targets exist, ~1s when no targets |

---

## 2. Packet Types

The system sends two types of JSON packets, distinguished by the top-level `type` field:

| type | Packet Type | Description |
|------|-------------|-------------|
| 1 | Target Data | Contains detected target information |
| 2 | Heartbeat | Device status, sent every ~1 second |

---

## 3. Target Data Packet (type=1)

### Complete Example

```json
{
    "type": 1,
    "ver": "01",
    "msgCnt": 1,
    "minOfYear": 210780,
    "second": 45197,
    "cycle": 100,
    "fusDevID": "0001",
    "refPos": {"lat": 0, "lon": 0, "ele": 0},
    "objectsList": [
        {
            "objectID": 1,
            "objectType": 2,
            "objectPos": {"lat": 2013, "lon": -44868626, "ele": 136},
            "speed": 50,
            "heading": 0,
            "posConfid": {"pos": 0, "ele": 0},
            "vehicleSize": {"length": 763, "width": 300, "height": 136},
            "dataSource": 6
        }
    ],
    "eventsList": [],
    "eventstatList": []
}
```

### Top-Level Fields

| Field | Type | Description |
|-------|------|-------------|
| type | int | Packet type, 1 = target data |
| ver | string | Protocol version, fixed "01" |
| msgCnt | int | Message count, fixed 1 |
| minOfYear | int | Minutes elapsed in current year |
| second | int | Current second (with milliseconds) |
| cycle | int | Send period in ms, fixed 100 |
| fusDevID | string | Device ID, fixed "0001" |
| refPos | object | Reference position, reserved |
| objectsList | array | Target list, each element is one target |
| eventsList | array | Event list, reserved |
| eventstatList | array | Event statistics, reserved |

### Fields in Each Target of objectsList

| Field | Type | Description |
|-------|------|-------------|
| objectID | int | Target ID, cycles from 1 to 65535 |
| objectType | int | Target type: 0=Unknown 1=Large Vessel 2=Small Vessel 3=Speedboat |
| objectPos.lat | int | Latitude (degrees), **actual value = lat ÷ 10000000**, requires GPS configured |
| objectPos.lon | int | Longitude (degrees), **actual value = lon ÷ 10000000**, requires GPS configured |
| objectPos.ele | int | Target height above water, **actual value (m) = ele ÷ 20** |
| speed | int | Speed, **actual value (m/s) = speed ÷ 50** |
| heading | int | Heading angle, **actual value (degrees) = heading ÷ 80** |
| posConfid.pos | int | Position confidence, reserved |
| posConfid.ele | int | Height confidence, reserved |
| vehicleSize.length | int | Length, **actual value (m) = length ÷ 100** |
| vehicleSize.width | int | Width, **actual value (m) = width ÷ 100** |
| vehicleSize.height | int | Height, **actual value (m) = height ÷ 20** |
| dataSource | int | Data source, 6 = LiDAR |

### No Target Scenario

When no targets are detected, objectsList contains one empty target:

```json
"objectsList": [
    {
        "objectID": 0,
        "objectType": 0,
        "objectPos": {"lat": 0, "lon": 0, "ele": 0},
        "speed": 0,
        "heading": 0,
        "posConfid": {"pos": 0, "ele": 0},
        "vehicleSize": {"length": 0, "width": 0, "height": 0},
        "dataSource": 6
    }
]
```
Check `objectID == 0` to determine no targets are present.

---

## 4. Heartbeat Packet (type=2)

```json
{
    "type": 2,
    "ver": "01",
    "msgCnt": 2,
    "minOfYear": 210780,
    "second": 45312,
    "cycle": 1000,
    "statusList": [
        {"deviceID": "0001", "deviceType": 4, "statusType": 1}
    ]
}
```

| Field | Description |
|-------|-------------|
| statusList.deviceID | Device ID |
| statusList.deviceType | 4 = LiDAR |
| statusList.statusType | 1 = Normal |

---

## 5. Receiver Examples

### Python

```python
import socket
import json

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('0.0.0.0', 10010))   # Port must match sender configuration

while True:
    data, addr = sock.recvfrom(65535)
    pkt = json.loads(data.decode('utf-8'))
    
    if pkt['type'] == 1:
        for obj in pkt['objectsList']:
            if obj['objectID'] == 0:
                print("No targets detected")
                continue
            lat = obj['objectPos']['lat'] / 10000000.0
            lon = obj['objectPos']['lon'] / 10000000.0
            ele = obj['objectPos']['ele'] / 20.0
            spd = obj['speed'] / 50.0
            L = obj['vehicleSize']['length'] / 100.0
            W = obj['vehicleSize']['width'] / 100.0
            H = obj['vehicleSize']['height'] / 20.0
            types = {0: 'Unknown', 1: 'Large Vessel', 2: 'Small Vessel', 3: 'Speedboat'}
            t = types.get(obj['objectType'], 'Unknown')
            print(f"Target {obj['objectID']} [{t}]: ({lat},{lon}) H={ele}m V={spd}m/s Size={L}x{W}x{H}m")
    elif pkt['type'] == 2:
        pass  # Heartbeat, ignore or use for keep-alive
```

### C#

```csharp
using System;
using System.Net.Sockets;
using System.Text;
using Newtonsoft.Json.Linq;

class Program
{
    static void Main()
    {
        UdpClient udp = new UdpClient(10010);
        IPEndPoint ep = new IPEndPoint(IPAddress.Any, 0);
        
        while (true)
        {
            byte[] data = udp.Receive(ref ep);
            string json = Encoding.UTF8.GetString(data);
            JObject pkt = JObject.Parse(json);
            
            if ((int)pkt["type"] == 1)
            {
                foreach (JObject obj in pkt["objectsList"])
                {
                    if ((int)obj["objectID"] == 0) continue;
                    double lat = (double)obj["objectPos"]["lat"] / 10000000.0;
                    double lon = (double)obj["objectPos"]["lon"] / 10000000.0;
                    double ele = (double)obj["objectPos"]["ele"] / 20.0;
                    double spd = (double)obj["speed"] / 50.0;
                    double L = (double)obj["vehicleSize"]["length"] / 100.0;
                    double W = (double)obj["vehicleSize"]["width"] / 100.0;
                    double H = (double)obj["vehicleSize"]["height"] / 20.0;
                    Console.WriteLine($"Target {obj["objectID"]}: ({lat},{lon}) H={ele}m V={spd}m/s Size={L}x{W}x{H}m");
                }
            }
        }
    }
}
```

---

## 6. Configuration

Edit `./setting/device.ini`:

```ini
[CommonParameters]
CommonNetwork\ResultAddr=<Receiver IP Address>
CommonNetwork\ResultPort=<Receiver Port>
Lidar\SendPageType=1
```

Restart the program after modification.
