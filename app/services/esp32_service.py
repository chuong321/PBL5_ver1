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
        async with self.lock:
            for connection in list(self.active_connections):
                try:
                    await connection.send_json(message)
                except Exception:
                    pass


manager = WebSocketConnectionManager()


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
