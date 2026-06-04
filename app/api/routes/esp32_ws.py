"""ESP32 WebSocket endpoints."""

import asyncio
import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.esp32_service import (
    manager,
    mark_esp32_seen,
    mark_esp32_disconnected,
    read_esp32_state,
    decode_image_from_base64,
    preprocess_esp32_image,
)
from app.workers.processor import get_orchestrator

router = APIRouter()


def extract_weight_grams(data: dict) -> Optional[float]:
    weight_grams = data.get("weight_grams", data.get("weight"))

    payload = data.get("data")
    if weight_grams is None and isinstance(payload, dict):
        weight_grams = payload.get("weight_grams", payload.get("weight"))

    if weight_grams is None:
        return None

    try:
        return float(weight_grams)
    except (TypeError, ValueError):
        return None


async def submit_image_with_weight(
    websocket: WebSocket,
    processed_image,
    weight_grams: float,
) -> None:
    batch_id = await websocket.app.state.batch_id_generator.next_id()
    orchestrator = get_orchestrator()
    result = orchestrator.submit_batch(batch_id, [processed_image], [weight_grams])

    if result != -1:
        await websocket.send_json(
            {
                "type": "batch_submitted",
                "batch_id": batch_id,
                "weight_grams": weight_grams,
                "message": "Processing 1 image...",
            }
        )


@router.get("/api/esp32/status")
async def get_esp32_status():
    connected, last_seen, age_seconds, latest_weight_grams = await read_esp32_state()
    return {
        "connected": connected,
        "last_seen": last_seen.isoformat() if last_seen else None,
        "age_seconds": age_seconds,
        "latest_weight_grams": latest_weight_grams,
    }


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    pending_image = None

    try:
        while True:
            message = await websocket.receive_text()

            try:
                data = json.loads(message)
                msg_type = data.get("type", "")

                if msg_type == "image":
                    base64_image = data.get("data", "")
                    await mark_esp32_seen()
                    await manager.broadcast(
                        {
                            "type": "frame",
                            "data": f"data:image/jpeg;base64,{base64_image}",
                            "detections": [],
                        }
                    )

                    image = decode_image_from_base64(base64_image)
                    processed_image = await asyncio.to_thread(preprocess_esp32_image, image)
                    if processed_image is None:
                        await websocket.send_json({"type": "error", "message": "Invalid image"})
                        continue

                    if pending_image is not None:
                        await websocket.send_json(
                            {
                                "type": "warning",
                                "message": "Previous image discarded because no weight arrived.",
                            }
                        )

                    pending_image = processed_image
                    await websocket.send_json(
                        {
                            "type": "image_received",
                            "message": "Image received. Waiting for next weight sample...",
                        }
                    )

                elif msg_type in {"weight", "sensor_data"}:
                    weight_grams = extract_weight_grams(data)
                    if weight_grams is None:
                        await websocket.send_json(
                            {"type": "error", "message": "Invalid weight"}
                        )
                        continue

                    await mark_esp32_seen(weight_grams=weight_grams)
                    await manager.broadcast(
                        {
                            "type": "sensor_data",
                            "data": {"weight_grams": weight_grams},
                        }
                    )

                    if pending_image is not None:
                        image_to_submit = pending_image
                        pending_image = None
                        await submit_image_with_weight(
                            websocket, image_to_submit, weight_grams
                        )

                elif msg_type == "ping":
                    await mark_esp32_seen()
                    await websocket.send_json(
                        {"type": "pong", "timestamp": datetime.utcnow().isoformat()}
                    )
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await mark_esp32_disconnected()
        await manager.disconnect(websocket)
