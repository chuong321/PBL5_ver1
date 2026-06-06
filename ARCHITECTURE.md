# 🏗️ Architecture Documentation - Trash Classification System

## Overview

```
┌─────────────┐
│  ESP32-CAM  │ (Gửi ảnh stream qua WebSocket)
└──────┬──────┘
       │
       ▼
┌──────────────────────────────────────────┐
│  FastAPI Server (ASGI + Asyncio)         │
│  - WebSocket handler (non-blocking)      │
│  - Image buffer (AsyncIO Lock)           │
│  - Background task launcher              │
│  - HTTP REST API                         │
└──────┬──────────────────┬────────────────┘
       │                  │
       │ Buffer 5 images  │ HTTP Requests
       │                  └─→ /api/stats
       ▼                     /api/health
   input_queue               /api/records
       │                     /api/search
       │
   ┌───────────────────────────────────────────┐
   │  Multiprocessing Layer                    │
   │  (2 independent processes)                │
   │                                           │
   │  ┌──────────────────────────────────┐    │
   │  │  PRIMARY Process (YOLO1)         │    │
   │  │  - 38 trash classes              │    │
   │  │  - Confidence threshold: 0.4     │    │
   │  │  - Image size: 416x416           │    │
   │  │  → Output: label + crop ROI      │    │
   │  └──────────────────┬───────────────┘    │
   │                     │                    │
   │                     ▼                    │
   │         intermediate_queue               │
   │                     │                    │
   │  ┌──────────────────────────────────┐    │
   │  │  SECONDARY Process (YOLO2)       │    │
   │  │  - Liquid detection              │    │
   │  │  - Confidence threshold: 0.5     │    │
   │  │  - Image size: 320x320           │    │
   │  │  → Combine with weight_grams     │    │
   │  │  → Output: has_liquid (yes/no)   │    │
   │  └──────────────────┬───────────────┘    │
   │                     │                    │
   └─────────────────────┼────────────────────┘
                         │
                  result_queue
                         │
       ┌─────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│  FastAPI (Asyncio Background Task)   │
│  - Poll result_queue                 │
│  - Save to SQLite DB                 │
│  - Convert to output_code (1-5)      │
│  - Broadcast via WebSocket           │
└──────────────────────────────────────┘
       │
       ▼
    ESP32-CAM (output_code 1-5 → Relay Control)
```

---

## Component Details

### 1. FastAPI Server (main.py)

**Role:** Entry point, request routing, WebSocket management, background tasks

**Key Features:**
- **ASGI Framework:** Built on Starlette (async)
- **Lifespan:** Startup/shutdown hooks (initialize DB, start orchestrator)
- **WebSocket Manager:** Connection tracking, broadcast
- **Image Buffer:** Asyncio-safe (atomic operations with Lock)
- **Background Task:** Continuous polling of result_queue

**Technology Stack:**
- FastAPI 0.104+
- Uvicorn (ASGI server)
- Pydantic (request validation)
- SQLAlchemy ORM (database)

### 2. Multiprocessing Architecture (services/processor.py)

#### A. ProcessorOrchestrator
- **Manages:** All child processes lifecycle
- **Queues:** input_queue → intermediate_queue → result_queue
- **Methods:**
  - `start()` - Spawn PRIMARY & SECONDARY processes
  - `submit_batch()` - Send 5 images for processing
  - `get_result()` - Fetch final results
  - `stop()` - Cleanup & terminate

#### B. PRIMARY Process (YOLO1)
**Purpose:** Classify trash into 38 categories

**Processing Flow:**
1. Load model_weights/primary/best.pt model (YOLO v8)
2. Receive batch of 5 images from input_queue
3. For each image:
   - Run inference (conf=0.4, imgsz=416)
   - Extract highest confidence detection
   - Get bounding box coordinates
   - Crop the detected object (ROI)
   - Store: (batch_id, image_idx, label, confidence, crop_image, weight_grams)
4. Send results to intermediate_queue

**Output Example:**
```python
{
    'batch_id': 1,
    'image_idx': 0,
    'label': 'plastic_bottle',
    'confidence': 0.89,
    'crop_image': numpy_array,  # Cropped object
    'weight_grams': 250.0,
    'timestamp': '2024-01-15T10:30:00'
}
```

#### C. SECONDARY Process (YOLO2)
**Purpose:** Verify liquid content inside container

**Processing Flow:**
1. Load model_weights/secondary/best.pt model (custom YOLO2)
2. Receive crop_image from intermediate_queue (from PRIMARY)
3. Run inference on crop (conf=0.5, imgsz=320)
4. Determine: has_liquid (bool), liquid_confidence (float)
   - Chỉ xem là phát hiện chất lỏng khi YOLO2 có ít nhất 1 detection với class `liquid`
   - Detection class khác `liquid` không được tính là phát hiện chất lỏng

**Smart Logic (4 Cases):**

| Model Output | Weight | Decision | Rationale |
|---|---|---|---|
| has_liquid=YES | > threshold | **YES** | Detect class `liquid` |
| has_liquid=NO | <= threshold | **NO** | Sure it's empty |
| has_liquid=NO | > threshold | **YES** | Water filled bottle, label hidden |
| has_liquid=YES | < threshold | **YES** | Detect class `liquid`, trust AI |

**Example:**
```python
# Bottle weight threshold: 50g
# Case 3: Model says NO but weight=250g
#  → Override: has_liquid = YES (impossible to be 250g empty)
```

**Output Example:**
```python
{
    'batch_id': 1,
    'image_idx': 0,
    'label': 'plastic_bottle',
    'confidence': 0.89,
    'has_liquid': 'yes',
    'liquid_confidence': 0.92,
    'weight_grams': 250.0,
    'timestamp': '2024-01-15T10:30:00'
}
```

### 3. Database Layer (models.py, repositories/)

**TrashRecord Schema:**
```sql
- id: PRIMARY KEY
- image_path: str (reference to saved composite image)
- label: str (38 class names)
- confidence: float (0-1, from PRIMARY)
- has_liquid: str ('yes', 'no', 'unknown')
- weight_grams: float (sensor data)
- timestamp: datetime
- individual_confidences: str (JSON)
- primary_model_output: str (raw YOLO1 output)
- secondary_model_output: str (raw YOLO2 output)
```

**Repository Methods:**
- `create_record()` - Insert classification result
- `get_statistics()` - Count by label, has_liquid
- `get_records_paginated()` - For UI display
- `delete_old_records()` - Cleanup

### 4. Output Code Mapping (1-5)

After receiving results from SECONDARY, map to relay control:

```python
def determine_output_code(label, has_liquid, weight_grams):
    if label == 'no_detection':
        return 5  # No detection → Relay 5
    
    if label == 'error':
        return 3  # Error → Relay 3
    
    if has_liquid == 'yes':
        return 1  # Has liquid → Relay 1
    
    if has_liquid == 'no':
        return 2  # No liquid → Relay 2
    
    return 4  # Other → Relay 4
```

**ESP32 Implementation:**
```c
// Receive output_code (1-5)
// digitalWrite(RELAY_PINS[code-1], HIGH)  // Turn on relay
// delay(2000)
// digitalWrite(RELAY_PINS[code-1], LOW)   // Turn off relay
```

---

## Queue System

### Queue Sizes & Timeouts

```python
MAX_QUEUE_SIZE = 100           # Max 100 items per queue
QUEUE_TIMEOUT = 5              # 5 sec wait before timeout

# Input Flow
ESP32 → WebSocket (Async)
  → image_buffer (5 images)
    → input_queue (async submit)
      → PRIMARY Process (polling)

# Intermediate Flow
PRIMARY (results ready)
  → intermediate_queue (10x per batch if 2 workers)
    → SECONDARY Process (polling)

# Result Flow
SECONDARY (final results)
  → result_queue (from background task)
    → FastAPI (async poll)
      → SQLite DB (sync block, OK)
      → WebSocket broadcast (async)
      → ESP32 (output_code 1-5)
```

### Why This Architecture?

**Problem:** Python GIL (Global Interpreter Lock) prevents true multithreading

**Solution:** Multiprocessing = separate processes per instance

**Benefits:**
1. ✅ TRUE parallel processing (not GIL-limited)
2. ✅ PRIMARY can classify while SECONDARY verifies
3. ✅ No worker waiting (continuous pipeline)
4. ✅ CPU cores fully utilized

**Trade-off:**
- ❌ IPC overhead (inter-process communication via queues)
- ❌ More memory (each process = separate Python runtime)
- ✅ Better for heavy CPU tasks (YOLO inference)

---

## Asyncio Details

### Non-blocking Operations

**WebSocket Handling:**
```python
# Async WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    while True:
        message = await websocket.receive_text()  # Non-blocking
        # ... process ...
        await websocket.send_json(response)        # Non-blocking
```

**Image Buffer (AsyncIO Safe):**
```python
class ImageBuffer:
    def __init__(self):
        self.lock = asyncio.Lock()
    
    async def add_image(self, image):
        async with self.lock:  # Atomic operation
            self.images.append(image)
```

**Background Task (Continuous Polling):**
```python
async def process_batches_background():
    while True:
        result = orchestrator.get_result(timeout=1)  # Non-blocking poll
        if result:
            # Save to DB (sync, OK for small operations)
            # Broadcast to WebSocket (async)
        await asyncio.sleep(0.1)  # Yield control
```

### Why AsyncIO?

**Problem:** WebSocket connections are I/O-bound (network waits)

**Solution:** Async/await = thousands of connections with 1 thread

**Benefits:**
1. ✅ Single thread handles many WebSocket clients
2. ✅ Zero context switch overhead
3. ✅ Better resource usage (no thread pool needed)
4. ✅ Natural fit for real-time applications

---

## Performance Characteristics

### Latency Breakdown

```
1. ESP32 → Server: 10-50ms (network)
2. Server receive: <1ms (async)
3. Buffering 5 images: ~500ms (at 100fps)
4. PRIMARY inference (5 images): 200-500ms (CPU)
5. Crop + intermediate: ~100ms
6. SECONDARY inference (5 crops): 100-300ms (CPU)
7. DB write (5 records): ~10ms
8. WebSocket broadcast: <5ms
──────────────────────────
Total: ~900ms - 1.5s per batch
```

### Throughput

| Setting | Throughput |
|---------|-----------|
| 1 image/sec from ESP32 | 1-2 batches/sec |
| 2 PRIMARY + 1 SECONDARY | ~3x faster |
| GPU-accelerated YOLO | ~5-10x faster |

### Memory Usage

- FastAPI process: ~200MB
- SQLite DB: ~10MB + (records × 1KB)
- PRIMARY process: ~500MB (model + buffer)
- SECONDARY process: ~400MB (model + buffer)
- **Total: ~1.5-2GB** (with models loaded)

---

## Configuration Tuning

### For Speed (real-time, low latency)
```python
PRIMARY_PROCESS_WORKERS = 4     # More workers
YOLO1_CONF = 0.5                # Higher threshold = faster
YOLO1_IMGSZ = 320               # Smaller = faster
YOLO2_IMGSZ = 256               # Smaller = faster
BUFFER_SIZE = 3                 # Process sooner
```

### For Accuracy (correctness over speed)
```python
PRIMARY_PROCESS_WORKERS = 1     # Sequential = consistent
YOLO1_CONF = 0.3                # Lower threshold = catch more
YOLO1_IMGSZ = 640               # Larger = more details
YOLO2_IMGSZ = 512               # Larger = more details
BUFFER_SIZE = 10                # More votes (voting algorithm)
```

### For GPU Acceleration
```python
YOLO1_DEVICE = 'cuda'           # Use GPU
YOLO2_DEVICE = 'cuda'
PRIMARY_PROCESS_WORKERS = 2     # Can be more with GPU
```

---

## Deployment Considerations

### Single Machine
- Recommended: i7+ CPU, 8GB+ RAM, SSD
- Models loaded in RAM (~1GB)
- SQLite OK for <100k records

### Multiple Machines
- REST API can run on one machine
- Multiprocessing on another (via RPC, not recommended)
- Better: Run entire system on single machine

### Cloud Deployment
- Azure Container Instances
- AWS EC2 (t3.large+)
- Lambda functions (serverless) - NOT suitable (no GPU, timeout)

---

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Out of Memory | Large model + many workers | Reduce workers, use GPU |
| Slow inference | CPU bottleneck | Increase workers, use GPU |
| WebSocket timeout | Server overloaded | Check queue sizes, buffer overflow |
| DB lock | Concurrent writes | Not an issue (SQLite handles) |
| No results | Models not loaded | Place best.pt in model_weights/primary |

---

## Version History

- **v2.0.0** (Current) - FastAPI + Multiprocessing
  - 2 YOLO models (PRIMARY + SECONDARY)
  - Asyncio + Multiprocessing hybrid
  - Output code mapping (1-5)
  - Smart liquid detection logic

- **v1.0.0** (Legacy) - Flask + SocketIO
  - Single YOLO model
  - Voting algorithm
  - Threading (limited by GIL)

---

Generated: 2024-01-15  
Updated: 2024-04-08
