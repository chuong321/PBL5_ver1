# ESP8266 Servo Controller - Hướng dẫn

## Thư viện Arduino cần cài đ�

Trong Arduino IDE, vào **Sketch > Include Library > Manage Libraries**, cài:

1. **WebSockets** by Markus Sattler
2. **Servo** (built-in, không cần cài)

---

## Kết nối phần cứng

| ESP8266 (NodeMCU) | Servo 1 (Gạt) | Servo 2 (Quay) |
|-------------------|---------------|----------------|
| D1 (GPIO5)        | Signal        |               |
| D2 (GPIO4)        |               | Signal        |
| 3.3V              | VCC           | VCC           |
| GND               | GND           | GND           |

> ⚠️ Nếu servo cần 5V, dùng module nguồn ngoài hoặc chia 5V từ USB

---

## Cấu hình WiFi & Server

Trong file `servo_esp8266.ino`, chỉnh:

```cpp
// WiFi
const char* ssid = "TAN TIEN T2";
const char* password = "86868686";

// Server (IP máy tính chạy Python)
const char* server_host = "192.168.1.2";  // Đổi IP máy bạn
```

### Kiểm tra IP máy
```bash
ipconfig
```
Tìm IPv4 Address của card mạng đang dùng.

---

## Cách hoạt động

```
ESP32-CAM → Server (AI phân loại) → Server broadcast WebSocket → ESP8266 nhận lệnh
```

### Flow:
1. ESP32-CAM gửi ảnh lên Server
2. Server AI phân loại → ra số 1-5
3. Server gửi WebSocket: `{"type":"servo_command","output_code":3}`
4. ESP8266 nhận → gạt → quay → về vị trí cũ

---

## Endpoint WebSocket

```
ws://192.168.1.2:8000/ws/servo
```

---

## Test thủ công

### Cách 1: Serial Monitor
Gửi ký tự `1` đến `5` trong Serial Monitor (115200 baud)

### Cách 2: Web Server (tùy chọn)
Mở `http://<ESP_IP>` trên trình duyệt (cần thêm code HTML server)

---

## Debug

Serial Monitor baud rate: **115200**

Log mẫu:
```
[WS] Connected!
[SERVO] Command: 3
SERVO1: PUSH
SERVO2: 90
SERVO1: REST
```

---

## Khắc phục lỗi

### ESP8266 không kết nối WebSocket
1. Kiểm tra IP server đúng chưa
2. Kiểm tra port 8000 đang mở
3. Tắt firewall hoặc cho phép Python qua firewall

### Servo không quay
1. Kiểm tra nguồn servo (3.3V/5V)
2. Kiểm tra kết nối D1, D2
3. Thử test servo riêng trước
