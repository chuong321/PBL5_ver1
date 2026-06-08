"""FastAPI application entry point."""

import asyncio
import base64
import json
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import (
    CORS_ORIGINS,
    CORS_ALLOW_CREDENTIALS,
    CORS_ALLOW_METHODS,
    CORS_ALLOW_HEADERS,
    STATIC_DIR,
    UPLOAD_FOLDER,
    SQLALCHEMY_DATABASE_URI,
)
from app.models.trash_record import init_db, get_session_factory
from app.repositories.trash_repository import TrashRepository
from app.services.esp32_service import (
    manager,
    servo_manager,
    BatchIdGenerator,
    mark_esp32_seen,
    mark_esp32_disconnected,
    read_esp32_state,
    decode_image_from_base64,
    preprocess_esp32_image,
)
from app.workers.processor import start_orchestrator, stop_orchestrator, get_orchestrator
from app.api.routes import dashboard_router, stats_router


async def process_batches_background(app: FastAPI) -> None:
    orchestrator = get_orchestrator()

    while True:
        try:
            result = orchestrator.get_result(timeout=1)

            if result:
                batch_id = result["batch_id"]
                results = result["results"]

                response_data = {"batch_id": batch_id, "results": []}

                try:
                    session = app.state.session_factory()

                    for idx, res in enumerate(results):
                        label = res["label"]
                        confidence = res["confidence"]
                        has_liquid = res["has_liquid"]
                        liquid_conf = res["liquid_confidence"]
                        weight_grams = res["weight_grams"]
                        detections = res.get("detections", [])
                        image_shape = res.get("image_shape")

                        group_id = res.get("group_id")
                        group_name = res.get("group_name")
                        output_code = group_id if group_id is not None else 0

                        response_data["results"].append(
                            {
                                "image_idx": idx,
                                "label": label,
                                "confidence": confidence,
                                "has_liquid": has_liquid,
                                "weight_grams": weight_grams,
                                "detections": detections,
                                "image_shape": image_shape,
                                "group_id": group_id,
                                "group_name": group_name,
                                "output_code": output_code,
                            }
                        )

                        try:
                            TrashRepository.create_record(
                                db_session=session,
                                image_path=f"batch_{batch_id}_image_{idx}.jpg",
                                label=label,
                                confidence=confidence,
                                has_liquid=has_liquid,
                                weight_grams=weight_grams,
                                individual_confidences=json.dumps(
                                    {"primary_conf": confidence, "liquid_conf": liquid_conf}
                                ),
                                primary_model_output=label,
                                secondary_model_output=f"liquid={has_liquid}",
                            )
                        except Exception as exc:
                            print(f"[MAIN] Failed to save trash record for batch #{batch_id}: {exc}")

                        # Gui lenh xuong ESP8266-SERVO qua WebSocket
                        if 1 <= output_code <= 5:
                            await servo_manager.broadcast({
                                "type": "servo_command",
                                "output_code": output_code,
                            })
                            print(f"[MAIN] Sent servo_command C{output_code} to ESP8266")

                    session.close()
                except Exception:
                    pass

                await manager.broadcast({"type": "classification_result", "data": response_data})
        except Exception:
            pass

        await asyncio.sleep(0.1)


app = FastAPI(
    title="Trash Classification System",
    description="Real-time Trash Classification with FastAPI + Multiprocessing",
    version="2.0.0",
)

RAW_DEBUG_DIR = UPLOAD_FOLDER / "esp32_raw_debug"


def save_first_raw_esp32_frame(app: FastAPI, base64_image: str) -> Optional[str]:
    if getattr(app.state, "raw_esp32_frame_saved", False):
        return None

    try:
        if "," in base64_image:
            base64_image = base64_image.split(",", 1)[1]

        image_bytes = base64.b64decode(base64_image)
        RAW_DEBUG_DIR.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        image_path = RAW_DEBUG_DIR / f"esp32_raw_before_ai_{timestamp}.jpg"
        image_path.write_bytes(image_bytes)

        app.state.raw_esp32_frame_saved = True
        print(f"[DEBUG] Saved raw ESP32 frame before AI: {image_path}")
        return str(image_path)
    except Exception as exc:
        print(f"[DEBUG] Failed to save raw ESP32 frame: {exc}")
        return None


# ============================================================
# WEBSOCKET: /ws  — ESP32-CAM gui anh + can
# ============================================================
@app.websocket("/ws")
async def websocket_esp32(websocket: WebSocket):
    await manager.connect(websocket)
    ping_task: asyncio.Task | None = None

    async def _keepalive() -> None:
        while True:
            await asyncio.sleep(20)
            try:
                await websocket.send_json({"type": "ping", "timestamp": datetime.utcnow().isoformat()})
            except Exception:
                return

    try:
        ping_task = asyncio.create_task(_keepalive())
        while True:
            message = await websocket.receive()

            if message.get("type") == "websocket.disconnect":
                break

            if message.get("type") != "websocket.receive" or "text" not in message:
                continue

            text = message.get("text") or ""

            try:
                data = json.loads(text)
                msg_type = data.get("type", "")

                if msg_type == "image":
                    base64_image = data.get("data", "")
                    weight_grams_data = data.get("weight_grams", data.get("weight"))
                    if weight_grams_data is None:
                        payload = data.get("data")
                        if isinstance(payload, dict):
                            weight_grams_data = payload.get("weight_grams", payload.get("weight"))
                    weight_grams = float(weight_grams_data) if weight_grams_data is not None else None

                    await mark_esp32_seen(weight_grams=weight_grams)
                    debug_image_path = save_first_raw_esp32_frame(websocket.app, base64_image)
                    if debug_image_path:
                        await websocket.send_json({
                            "type": "debug_image_saved",
                            "path": debug_image_path,
                            "message": "Saved raw ESP32 frame before AI",
                        })

                    batch_id = await websocket.app.state.batch_id_generator.next_id()

                    await manager.broadcast({
                        "type": "frame",
                        "batch_id": batch_id,
                        "data": f"data:image/jpeg;base64,{base64_image}",
                        "detections": [],
                    })
                    await manager.broadcast({
                        "type": "sensor_data",
                        "data": {"weight_grams": weight_grams},
                    })

                    image = decode_image_from_base64(base64_image)
                    if image is None:
                        continue

                    processed_image = await asyncio.to_thread(preprocess_esp32_image, image)
                    if processed_image is None:
                        continue

                    orchestrator = get_orchestrator()
                    result = orchestrator.submit_batch(batch_id, [processed_image], [weight_grams or 0.0])
                    if result != -1:
                        await websocket.send_json({
                            "type": "batch_submitted",
                            "batch_id": batch_id,
                            "weight_grams": weight_grams,
                            "message": "Processing 1 image...",
                        })

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
        if ping_task:
            ping_task.cancel()
        await mark_esp32_disconnected()
        await manager.disconnect(websocket)


# ============================================================
# WEBSOCKET: /ws/servo  — ESP8266-SERVO nhan lenh
# ============================================================
@app.websocket("/ws/servo")
async def websocket_servo(websocket: WebSocket):
    await servo_manager.connect(websocket)
    ping_task: asyncio.Task | None = None

    async def _keepalive() -> None:
        while True:
            await asyncio.sleep(20)
            try:
                await websocket.send_json({"type": "ping", "timestamp": datetime.utcnow().isoformat()})
            except Exception:
                return

    try:
        ping_task = asyncio.create_task(_keepalive())

        # Gui thong bao connected
        await websocket.send_json({"type": "connected", "message": "Servo controller connected"})
        print("[WS] ESP8266-SERVO connected")

        while True:
            message = await websocket.receive()

            if message.get("type") == "websocket.disconnect":
                break

            if message.get("type") != "websocket.receive" or "text" not in message:
                continue

            text = message.get("text") or ""
            try:
                data = json.loads(text)
                msg_type = data.get("type", "")

                if msg_type in {"servo_ready", "servo_ack", "servo_status", "pong"}:
                    print(f"[SERVO WS] {msg_type}: {data}")
                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": datetime.utcnow().isoformat()})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if ping_task:
            ping_task.cancel()
        await servo_manager.disconnect(websocket)
        print("[WS] ESP8266-SERVO disconnected")


@app.on_event("startup")
async def on_startup() -> None:
    init_db(SQLALCHEMY_DATABASE_URI)
    app.state.session_factory = get_session_factory(SQLALCHEMY_DATABASE_URI)
    app.state.batch_id_generator = BatchIdGenerator()

    start_orchestrator()
    asyncio.create_task(process_batches_background(app))

    print("[STARTUP] Backend ready — waiting for ESP32-CAM and ESP8266-SERVO")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    stop_orchestrator()


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=CORS_ALLOW_METHODS,
    allow_headers=CORS_ALLOW_HEADERS,
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/favicon.ico")
async def favicon():
    favicon_path = STATIC_DIR / "favicon.ico"
    if favicon_path.exists():
        return FileResponse(str(favicon_path))
    return Response(status_code=204)


@app.get("/api/esp32/status")
async def get_esp32_status():
    connected, last_seen, age_seconds, latest_weight_grams = await read_esp32_state()
    return {
        "connected": connected,
        "last_seen": last_seen.isoformat() if last_seen else None,
        "age_seconds": age_seconds,
        "latest_weight_grams": latest_weight_grams,
    }


# Include HTTP routers
app.include_router(dashboard_router)
app.include_router(stats_router)
