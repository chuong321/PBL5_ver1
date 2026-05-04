# 🗑️ Trash Classification System - FastAPI + Multiprocessing

**Framework:** FastAPI (ASGI) + Uvicorn  
**Architecture:** Asyncio + Multiprocessing (PRIMARY & SECONDARY processes)  
**Database:** SQLite  
**Real-time Communication:** WebSocket  
**AI Models:** YOLO v8 (2 models - Primary 38 classes & Secondary liquid detection)  

**Workflow:**
```
ESP32-CAM → Gửi ảnh qua WebSocket (Async)
  → FastAPI Buffer 5 ảnh → Multiprocessing Queue
    → PRIMARY: YOLO1 phân loại 38 loại rác + crop ROI
      → SECONDARY: YOLO2 xác nhận có nước/không nước
        → Kết hợp logic weight_grams (4 trường hợp)
          → Output code 1-5 → Relay điều khiển
```

---

## ✨ Tính năng

✅ **FastAPI (ASGI)** - Hiệu năng cao, async/await support  
✅ **Asyncio** - Non-blocking I/O, real-time WebSocket  
✅ **Multiprocessing** - 2 tiến trình song song (PRIMARY + SECONDARY)  
✅ **Output Code 1-5** - Điều khiển 5 relay (có nước/không nước/error/etc.)  
✅ **Smart Liquid Detection** - Kết hợp AI + weight sensor logic  
✅ **WebSocket Real-time** - Image stream + instant results  
✅ **SQLite Database** - Lưu toàn bộ kết quả phân loại  
✅ **REST API** - Statistics, records pagination, health check  
✅ **Performance Optimized** - Multi-worker YOLO inference

---

## 🚀 Quick Start (5 phút)

### Windows (PowerShell)
```powershell
cd d:\PBL5
python -m app.run
```

### macOS / Linux  
```bash
cd /path/to/PBL5
source venv/bin/activate
pip install -r requirements.txt
python -m app.run
```

### Manual Setup
```bash
# 1. Create virtual environment
python -m venv venv

# 2. Activate (Windows: venv\Scripts\activate)
source venv/bin/activate

# 3. Install
pip install -r requirements.txt

# 4. Run
python -m app.run

# 5. Access
# Dashboard: http://localhost:8000
# WebSocket: ws://localhost:8000/ws
# API: http://localhost:8000/api
```

---

## 📡 API & WebSocket

### HTTP Endpoints

**Dashboard**
```
GET http://localhost:8000/
```

**Statistics**
```
GET http://localhost:8000/api/stats
```

**Health Check**
```
GET http://localhost:8000/api/health
```

**Records (Pagination)**
```
GET http://localhost:8000/api/records?page=1&limit=20
```

### WebSocket (ws://localhost:8000/ws)

**Send Image**
```json
{
  "type": "image",
  "data": "base64_encoded_image",
  "weight_grams": 50.0
}
```

**Receive Result (Output Code 1-5)**
```json
{
  "type": "classification_result",
  "data": {
    "batch_id": 1,
    "results": [
      {
        "label": "plastic_bottle",
        "confidence": "89%",
        "has_liquid": "yes",
        "output_code": 1
      }
    ]
  }
}
```

---

## 🏗️ Architecture

### 1️⃣ PRIMARY Process (YOLO1 - 38 Classes)
- Input: 5 ảnh từ image buffer
- Output: Label (38 loại rác) + Confidence + Crop ROI
- Workflow: Inference → Voting → Crop → Intermediate Queue

### 2️⃣ SECONDARY Process (YOLO2 - Liquid Detection)
- Input: Crop từ PRIMARY
- Output: has_liquid ('yes'/'no') + Confidence
- Logic: Kết hợp model + weight_grams (4 cases)

### Output Codes (1-5 → ESP32)
```
1 = CÓ NƯỚC           (HAS LIQUID)
2 = KHÔNG NƯỚC        (NO LIQUID)
3 = LỖI / UNKNOWN     (ERROR)
4 = LOẠI KHÁC         (OTHER)
5 = KHÔNG PHÁT HIỆN   (NO DETECTION)
```

---

## ⚙️ Configuration

**File:** `config.py`

```python
# Multiprocessing
PRIMARY_PROCESS_WORKERS = 2
SECONDARY_PROCESS_WORKERS = 1
MAX_QUEUE_SIZE = 100

# YOLO1 (Classification)
YOLO1_CONF = 0.4       # Lower = catch more
YOLO1_IMGSZ = 416      # Speed vs accuracy
YOLO1_DEVICE = 'cpu'   # or 'cuda'

# YOLO2 (Liquid Detection)
YOLO2_CONF = 0.5       # Higher = strict
YOLO2_IMGSZ = 320      # Lightweight

# Weight Thresholds (grams)
WEIGHT_THRESHOLD = {
    'bottle': 50,      # > 50g → has liquid
    'can': 30,
    'glass': 100
}
```

---

## 📁 Project Structure

### Hoặc chạy nhanh
```bash
python -m app.run
```

---

## 🔧 Cài đặt chi tiết

### 1. Yêu cầu
- Python 3.9+
- pip
- ~50MB disk space

### 2. Virtual Environment

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Cài Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Nếu gặp lỗi:**
```bash
pip cache purge
pip install --no-cache-dir -r requirements.txt
```

### 4. Tải YOLO Model
1. Từ Google Colab → Download `best.pt`
2. Copy vào folder `d:\PBL5\model_weights\primary\best.pt`
3. Test: `python -c "from ultralytics import YOLO; YOLO('model_weights/primary/best.pt')"`

### 5. Chạy Server
```bash
python -m app.run
```

**Output:**
```
✓ Database initialized
✓ YOLO model loaded
✅ Server initialized!
📌 Dashboard: http://localhost:5000
📜 History: http://localhost:5000/history
```

---

## 🏗️ Cấu trúc dự án

```
PBL5/
│
├── app/
│   ├── main.py                   ← FastAPI app (routes, startup)
│   ├── run.py                    ← Entry point
│   ├── api/
│   │   └── routes/               ← HTTP/WS routes
│   ├── services/                 ← Business helpers
│   ├── repositories/             ← Data access layer
│   ├── models/                   ← ORM models
│   ├── schemas/                  ← Pydantic schemas
│   ├── core/                     ← Config, logging, dependencies
│   └── workers/                  ← Multiprocessing pipeline
│
├── templates/                    ← HTML views
├── static/                       ← CSS, JS
├── database/                     ← SQLite DB
├── uploads/                      ← Saved images
├── startup.bat                   ← Windows start script
└── requirements.txt              ← Dependencies
```

---

## 🏛️ Kiến trúc Clean Architecture (3-Layer)

```
ESP32-CAM (ảnh)
    ↓ WebSocket
SocketController (Receive)
    ↓
TrashService (Orchestrate)
    ├─ AIService (YOLO + Voting)
    │   ├─ perform_inference()
    │   ├─ voting_results()
    │   └─ create_composite_image()
    │
    └─ TrashRepository (Save DB)
        └─ create_record()
            ↓ SQLite
Dashboard / API
```

**Khoảng cách giữa các layer:**
- **Repository** - Chỉ xử lý DB queries (SELECT, INSERT, etc.)
- **Service** - Chứa business logic (AI, Voting, Workflow)
- **Controller** - Nhận request, gọi service, trả response

✅ **Lợi ích:** Easy to test, maintain, extend!

---

## 📊 API & WebSocket

### HTTP REST API

| Endpoint | Phương thức | Mô tả |
|----------|-----------|-------|
| `/` | GET | Dashboard - Thống kê |
| `/history` | GET | Lịch sử bản ghi |
| `/api/stats` | GET | JSON stats |
| `/api/records` | GET | JSON records |
| `/api/search` | GET | Tìm kiếm |
| `/api/health` | GET | Health check |

### WebSocket Events

**Từ ESP32 gửi đến server:**
```python
# Gửi ảnh
socket.emit('image', base64_image_data)
```

**Server phản hồi:**
```python
# Xác nhận nhận ảnh
socket.on('response', {'status': 'received', 'count': 1})

# Hiển thị tiến độ (khi < 5 ảnh)
socket.on('progress', {'current': 3, 'total': 5, 'percentage': 60})

# Gửi kết quả cuối cùng
socket.on('result', {'label': 'plastic', 'confidence': '92.34%', 'record_id': 123})
```

---

## 🔌 ESP32-CAM Kết nối

Xem file `ESP32_CLIENT_EXAMPLE.ino` để tham khảo code Arduino.

**Chỉnh sửa:**
```cpp
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
const char* serverIP = "192.168.1.100";  // IP máy tính (dùng ipconfig)
const int serverPort = 5000;
```

**Upload vào ESP32-CAM qua Arduino IDE.**

---

## 🧪 Test Server

```bash
python test.py
```

**Output:**
```
[1] Checking server status... ✅
[2] Testing API endpoints... ✅
[3] Summary: All tests passed!
```

---

## 🆘 Troubleshooting

### ❌ "ModuleNotFoundError: No module named 'flask'"
**→** Virtual environment chưa activate
```bash
# Windows
venv\Scripts\activate

# macOS
source venv/bin/activate
```

### ❌ "Port 5000 already in use"
**→** Port 5000 đã bị chiếm
```bash
# Chỉnh sửa config.py:
SOCKETIO_PORT = 5001  # Dùng port khác
```

### ❌ "YOLO model not found"
**→** best.pt chưa được tải
```bash
# Từ Google Colab → Download best.pt
# Copy vào: d:\PBL5\model_weights\primary\best.pt
```

### ❌ ESP32 không kết nối
**→** Kiểm tra:
1. WiFi ESP32 có connect không?
2. Server IP đúng không? (`ipconfig` để xem)
3. Firewall có allow port 5000 không?

### ❌ Lỗi Pillow/NumPy build
**→** Cache pip & cài lại
```bash
pip cache purge
pip install --no-cache-dir -r requirements.txt
```

---

## 📋 Workflow Phân loại

```
1. ESP32-CAM gửi ảnh (binary)
           ↓
2. SocketController nhận & decode ảnh
           ↓
3. Thêm ảnh vào buffer
           ↓
4. Buffer < 5? → emit('progress')
   Buffer = 5? → Tiếp tục
           ↓
5. AIService.process_batch_images()
   ├─ Perform inference (YOLO x5)
   ├─ Voting (chọn nhãn nhiều nhất)
   └─ Create composite image
           ↓
6. TrashRepository.create_record()
   ├─ Lưu ảnh composite
   ├─ Lưu label, confidence
   └─ Lưu timestamp
           ↓
7. Emit result về ESP32
   ├─ Label: "plastic"
   ├─ Confidence: "92.34%"
   └─ Record ID: 123
           ↓
8. Dashboard update real-time
   ├─ Cập nhật thống kê
   ├─ Thêm bản ghi mới
   └─ Refresh charts
```

---

## 📈 Database Schema

```sql
CREATE TABLE trash_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_path VARCHAR(255) NOT NULL,
    label VARCHAR(50) NOT NULL,      -- plastic, paper, metal, glass, cardboard
    confidence FLOAT NOT NULL,        -- 0.0 - 1.0
    individual_confidences TEXT,      -- JSON of 5 individual scores
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 🎨 Giao diện

### Dashboard (`/`)
- 📊 Thống kê tổng hợp (tổng mẫu, loại rác)
- 📈 Biểu đồ phân bố (doughnut chart)
- 📋 Bản ghi gần đây (10 items, auto-update)
- 🟢 Trạng thái WebSocket

### Lịch sử (`/history`)
- 📝 Danh sách chi tiết (pagination 20/page)
- 🔍 Bộ lọc (theo loại, độ tin cậy)
- 📊 Thống kê chi tiết
- 🔗 Export data (coming soon)

---

## 📂 Config chính

**config.py:**
```python
BUFFER_SIZE = 5              # Số ảnh buffer
UPLOAD_FOLDER = 'uploads'    # Thư mục lưu

# YOLO optimization
YOLO_CONF = 0.4              # Confidence threshold
YOLO_IMGSZ = 416             # Input size (nhỏ = nhanh)
YOLO_DEVICE = 'cpu'          # CPU hoặc cuda
```

---

## 🌟 Tính năng bonus

- ⚡ Auto-refresh dashboard (30s)
- 🔔 Real-time notifications
- ⌨️ Keyboard shortcuts (Ctrl+R refresh, Ctrl+H history)
- 📱 Responsive design (desktop + mobile)
- 🎯 Performance optimized (fast inference)
- 🔐 Error handling & logging

---

## 🚀 Production Tips

1. **Tắt DEBUG mode** - `DEBUG = False` trong config
2. **Set SECRET_KEY** - `SECRET_KEY = 'your-secret'`
3. **HTTPS** - Dùng nginx + SSL
4. **Database** - Migrate sang PostgreSQL
5. **Logging** - Setup proper logging
6. **Monitoring** - Health check endpoint

---

## 📚 Công nghệ

| Công nghệ | Mục đích |
|-----------|---------|
| **Flask** | Web framework |
| **SQLAlchemy** | ORM |
| **SQLite** | Database |
| **Socket.IO** | WebSocket |
| **YOLO v8** | AI Detection |
| **OpenCV** | Image processing |
| **Chart.js** | Charts/Graphs |

---

## 📞 Support

Gặp lỗi? Kiểm tra:
1. ✅ Python version 3.9+
2. ✅ Virtual environment activated
3. ✅ Dependencies installed
4. ✅ best.pt loaded
5. ✅ Port 5000 available

---

## 🔧 Cấu hình
BUFFER_SIZE = 5              # Số ảnh buffer trước khi inference
UPLOAD_FOLDER = 'uploads'    # Thư mục lưu ảnh
MODEL_PATH = 'model_weights/primary/best.pt'  # Đường dẫn YOLO model
```

### YOLO Optimization (Performance)

```python
# app.py - perform_inference()
results = yolo_model(image, conf=0.4, imgsz=416, verbose=False)
# conf=0.4: Giảm confidence threshold → Nhanh hơn
# imgsz=416: Input size nhỏ → Nhanh hơn (tradeoff: ít chính xác hơn)
```

## 📈 Luồng xử lý

```
┌─────────────┐
│ ESP32-CAM   │
│ Gửi ảnh     │
└──────┬──────┘
       │ WebSocket
       ▼
┌─────────────────┐
│ Backend (app.py)│
│ - Buffer ảnh    │
│ - YOLO Inference│
└──────┬──────────┘
       │ 5 ảnh?
       ▼
┌──────────────────┐
│ Voting Algorithm │
│ - Chọn nhãn      │
│ - Avg confidence │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Lưu Database     │
│ - Image composite│
│ - Label          │
│ - Confidence     │
└──────┬───────────┘
       │
       ▼
┌──────────────┐
│ Gửi kết quả  │
│ ESP32-CAM    │
└──────────────┘
```

## 🔍 Database Schema

### TrashRecord Table

| Column | Type | Mô tả |
|--------|------|-------|
| id | Integer (PK) | Auto-increment |
| image_path | String | Đường dẫn file ảnh composite |
| label | String | Nhãn rác (plastic, paper, metal, etc.) |
| confidence | Float | Độ tin cậy AI (0-1) |
| timestamp | DateTime | Thời gian ghi nhận |

## 🎨 Giao diện

### Dashboard (/)
- Thống kê tổng hợp
- Biểu đồ phân bố
- Bản ghi gần đây
- Trạng thái kết nối WebSocket

### Lịch sử (/history)
- Danh sách chi tiết bản ghi
- Pagination
- Lọc theo loại rác
- Lọc theo độ tin cậy

## 📝 Log và Debugging

Enable verbose logging:
```bash
python app.py --debug
```

Xem logs WebSocket:
```javascript
// Browser console
socket.on('*', (event, data) => {
  console.log('Event:', event, 'Data:', data);
});
```

## ⚠️ Lưu ý quan trọng

1. **Real-time Optimization**: 
   - Model inference đã tối ưu (imgsz=416, conf=0.4)
   - Không nên tăng imgsz quá lớn để tránh delay
   - Buffer 5 ảnh giúp tăng độ chính xác

2. **best.pt model**:
  - Cần tải từ Google Colab
  - YOLO1: `model_weights/primary/best.pt`
  - YOLO2: `model_weights/secondary/best.pt`
  - Ứng dụng sẽ tự động load khi khởi động

3. **Database**:
   - SQLite, tự động tạo khi chạy lần đầu
   - Lưu trong `database/trash_classification.db`

4. **Bảo mật**:
   - CORS enabled cho demo
   - Nên thêm authentication trước khi production

## 🔐 Production Deployment

```bash
# Sử dụng Gunicorn + Socket.IO adapter
pip install gunicorn python-socketio-client

gunicorn --worker-class eventlet -w 1 app:app
```

## 📚 Công nghệ sử dụng

- **Backend**: Flask 2.3.3, Python-SocketIO 5.9.0
- **Database**: SQLAlchemy 3.0.5, SQLite
- **AI/ML**: Ultralytics 8.0.195 (YOLO v8)
- **Image Processing**: OpenCV, Pillow
- **Frontend**: HTML5, CSS3, JavaScript + Chart.js

## 📞 Hỗ trợ

Nếu gặp vấn đề:

1. **Error loading YOLO**: Kiểm tra `model_weights/primary/best.pt` và `model_weights/secondary/best.pt`
2. **WebSocket connection fail**: Kiểm tra firewall port 5000
3. **Database error**: Xóa file `database/` và chạy lại

## 📄 License

MIT License - Để sử dụng tự do
