"""
ESP32 Camera Image Receiver Server
Chạy file này để nhận ảnh từ ESP32-CAM và lưu vào máy
"""

import base64
import os
import json
import time
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# ================= CẤU HÌNH =================
SAVE_FOLDER = Path("./captured_images")
SAVE_FOLDER.mkdir(exist_ok=True)

HOST = "0.0.0.0"
PORT = 8002

# ================= FASTAPI =================
app = FastAPI(title="ESP32 Image Receiver")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================= MODEL =================
class ImagePayload(BaseModel):
    image_data: str  # Base64 encoded image
    weight_grams: float = 0.0
    timestamp: int = 0

# ================= API ENDPOINT =================
@app.post("/api/esp32/save-image")
async def save_image(payload: ImagePayload):
    """Nhận ảnh từ ESP32 và lưu vào folder"""
    try:
        # Decode base64
        image_bytes = base64.b64decode(payload.image_data)
        
        # Tạo tên file với timestamp
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"img_{timestamp_str}.jpg"
        filepath = SAVE_FOLDER / filename
        
        # Lưu file
        with open(filepath, "wb") as f:
            f.write(image_bytes)
        
        file_size = len(image_bytes)
        
        print(f"[SAVE] {filename} | Size: {file_size} bytes | Weight: {payload.weight_grams:.1f}g")
        
        return {
            "status": "success",
            "filename": filename,
            "filepath": str(filepath),
            "size_bytes": file_size,
            "weight_grams": payload.weight_grams,
            "saved_at": datetime.now().isoformat(),
        }
        
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ================= API ENDPOINT (Form Data) =================
@app.post("/api/esp32/save-image-form")
async def save_image_form(
    image_data: str,
    weight_grams: float = 0.0,
    timestamp: int = 0
):
    """Nhận ảnh dạng form data (alternative)"""
    try:
        image_bytes = base64.b64decode(image_data)
        
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"img_{timestamp_str}.jpg"
        filepath = SAVE_FOLDER / filename
        
        with open(filepath, "wb") as f:
            f.write(image_bytes)
        
        print(f"[SAVE] {filename} | Size: {len(image_bytes)} bytes")
        
        return {
            "status": "success",
            "filename": filename,
            "filepath": str(filepath),
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ================= HEALTH CHECK =================
@app.get("/")
async def root():
    return {
        "service": "ESP32 Image Receiver",
        "status": "running",
        "save_folder": str(SAVE_FOLDER),
        "endpoints": {
            "POST /api/esp32/save-image": "Nhận ảnh JSON (base64)",
            "POST /api/esp32/save-image-form": "Nhận ảnh form data",
        }
    }

@app.get("/api/images")
async def list_images():
    """Liệt kê các ảnh đã lưu"""
    images = []
    for f in sorted(SAVE_FOLDER.glob("*.jpg")):
        images.append({
            "filename": f.name,
            "size": f.stat().st_size,
            "created": datetime.fromtimestamp(f.stat().st_ctime).isoformat(),
        })
    return {
        "count": len(images),
        "images": images
    }

# ================= CHẠY SERVER =================
if __name__ == "__main__":
    print("=" * 50)
    print("ESP32 CAMERA IMAGE RECEIVER SERVER")
    print("=" * 50)
    print(f"Save folder: {SAVE_FOLDER.absolute()}")
    print(f"Server: http://{HOST}:{PORT}")
    print(f"ESP32 endpoint: http://{HOST}:{PORT}/api/esp32/save-image")
    print("=" * 50)
    print("Waiting for images from ESP32...")
    print()
    
    uvicorn.run(app, host=HOST, port=PORT)
