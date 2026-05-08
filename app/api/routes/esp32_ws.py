"""ESP32 WebSocket endpoints."""

import json
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.esp32_service import (
    manager,
    mark_esp32_seen,
    mark_esp32_disconnected,
    read_esp32_state,
    decode_image_from_base64,
)
from app.workers.processor import get_orchestrator

router = APIRouter()


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

    try:
        while True:
            message = await websocket.receive_text()

            try:
                data = json.loads(message)
                msg_type = data.get("type", "")

                if msg_type == "image":
                    base64_image = data.get("data", "")
                    weight_grams = data.get("weight_grams", 50.0)
                    await mark_esp32_seen(weight_grams=weight_grams)
                    await manager.broadcast(
                        {
                            "type": "sensor_data",
                            "data": {"weight_grams": float(weight_grams)},
                        }
                    )
                    await manager.broadcast(
                        {
                            "type": "frame",
                            "data": f"data:image/jpeg;base64,{base64_image}",
                            "detections": [],
                        }
                    )

                    image = decode_image_from_base64(base64_image)
                    if image is None:
                        await websocket.send_json({"type": "error", "message": "Invalid image"})
                        continue

                    batch_id = await websocket.app.state.batch_id_generator.next_id()
                    orchestrator = get_orchestrator()
                    result = orchestrator.submit_batch(batch_id, [image], [weight_grams])

                    if result != -1:
                        await websocket.send_json(
                            {
                                "type": "batch_submitted",
                                "batch_id": batch_id,
                                "message": "Processing 1 image...",
                            }
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
