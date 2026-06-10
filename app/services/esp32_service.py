"""ESP32 helpers: connection state, WebSocket manager, and image decoding."""

import asyncio
import base64
from datetime import datetime
from typing import List, Optional, Tuple

import cv2
import numpy as np
from fastapi import WebSocket

esp32_connected = False
esp32_last_seen: Optional[datetime] = None
esp32_latest_weight_grams: Optional[float] = None
esp32_lock = asyncio.Lock()


class BatchIdGenerator:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._batch_id = 0

    async def next_id(self) -> int:
        async with self._lock:
            self._batch_id += 1
            return self._batch_id


class WebSocketConnectionManager:
    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self.lock:
            self.active_connections.append(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self.lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

    async def broadcast(self, message: dict) -> None:
        # Avoid holding the lock while awaiting network I/O.
        # Slow/blocked clients should not stall everyone else (incl. ESP32).
        async with self.lock:
            connections = list(self.active_connections)

        if not connections:
            return

        async def _safe_send(connection: WebSocket) -> bool:
            try:
                await connection.send_json(message)
                return True
            except Exception:
                return False

        results = await asyncio.gather(*(_safe_send(c) for c in connections), return_exceptions=False)
        dead = [c for c, ok in zip(connections, results) if not ok]
        if dead:
            async with self.lock:
                for c in dead:
                    if c in self.active_connections:
                        self.active_connections.remove(c)


manager = WebSocketConnectionManager()
servo_manager = WebSocketConnectionManager()


async def mark_esp32_seen(weight_grams: Optional[float] = None) -> None:
    global esp32_connected, esp32_last_seen, esp32_latest_weight_grams
    async with esp32_lock:
        esp32_connected = True
        esp32_last_seen = datetime.utcnow()
        if weight_grams is not None:
            esp32_latest_weight_grams = float(weight_grams)


async def mark_esp32_disconnected() -> None:
    global esp32_connected
    async with esp32_lock:
        esp32_connected = False


async def read_esp32_state() -> Tuple[bool, Optional[datetime], Optional[float], Optional[float]]:
    async with esp32_lock:
        connected = esp32_connected
        last_seen = esp32_last_seen
        latest_weight_grams = esp32_latest_weight_grams

    age_seconds = None
    if connected and last_seen:
        age_seconds = (datetime.utcnow() - last_seen).total_seconds()

    return connected, last_seen, age_seconds, latest_weight_grams

def decode_image_from_base64(base64_str: str) -> Optional[np.ndarray]:
    try:
        image_data = base64.b64decode(base64_str)
        nparr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img
    except Exception:
        return None


def resize_with_padding(
    image: np.ndarray,
    target_size: Tuple[int, int] = (320, 320),
    pad_color: Tuple[int, int, int] = (0, 0, 0),
) -> Optional[np.ndarray]:
    if image is None:
        return None

    target_w, target_h = target_size
    height, width = image.shape[:2]
    scale = min(target_w / width, target_h / height)
    new_w = int(round(width * scale))
    new_h = int(round(height * scale))
    interpolation = cv2.INTER_CUBIC if scale > 1.0 else cv2.INTER_AREA
    resized = cv2.resize(image, (new_w, new_h), interpolation=interpolation)

    pad_left = (target_w - new_w) // 2
    pad_right = target_w - new_w - pad_left
    pad_top = (target_h - new_h) // 2
    pad_bottom = target_h - new_h - pad_top

    return cv2.copyMakeBorder(
        resized,
        pad_top,
        pad_bottom,
        pad_left,
        pad_right,
        borderType=cv2.BORDER_CONSTANT,
        value=pad_color,
    )


def preprocess_esp32_image(image: np.ndarray) -> Optional[np.ndarray]:
    if image is None:
        return None

    try:
        resized = resize_with_padding(image, target_size=(320, 320))
        if resized is None:
            return None

        filtered = cv2.bilateralFilter(resized, d=5, sigmaColor=35, sigmaSpace=35)

        lab = cv2.cvtColor(filtered, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l_enhanced = clahe.apply(l_channel)
        enhanced = cv2.merge((l_enhanced, a_channel, b_channel))
        enhanced_bgr = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

        hsv = cv2.cvtColor(enhanced_bgr, cv2.COLOR_BGR2HSV)
        h_channel, s_channel, v_channel = cv2.split(hsv)
        s_boosted = cv2.multiply(s_channel, 1.3)
        hsv_enhanced = cv2.merge((h_channel, s_boosted, v_channel))
        enhanced_bgr = cv2.cvtColor(hsv_enhanced, cv2.COLOR_HSV2BGR)

        dimmed = cv2.convertScaleAbs(enhanced_bgr, alpha=0.9, beta=-15)
        boosted = cv2.convertScaleAbs(dimmed, alpha=1, beta=0)

        blurred = cv2.GaussianBlur(boosted, (0, 0), 1.0)
        sharpened = cv2.addWeighted(boosted, 1.6, blurred, -0.6, 0)
        return sharpened.astype("uint8")
        # return image.copy()
    except Exception:
        return None


def decode_image_from_jpeg_bytes(jpeg_bytes: bytes) -> Optional[np.ndarray]:
    try:
        nparr = np.frombuffer(jpeg_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img
    except Exception:
        return None

