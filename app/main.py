"""FastAPI application entry point."""

import asyncio
import json
from datetime import datetime
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import (
    CORS_ORIGINS,
    CORS_ALLOW_CREDENTIALS,
    CORS_ALLOW_METHODS,
    CORS_ALLOW_HEADERS,
    STATIC_DIR,
    SQLALCHEMY_DATABASE_URI,
)
from app.models.trash_record import init_db, get_session_factory
from app.repositories.trash_repository import TrashRepository
from app.services.classification_service import determine_output_code
from app.services.esp32_service import manager, BatchIdGenerator
from app.workers.processor import start_orchestrator, stop_orchestrator, get_orchestrator
from app.api.routes import dashboard_router, stats_router, esp32_router


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

                        output_code = determine_output_code(label, has_liquid, weight_grams)

                        record = TrashRepository.create_record(
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

                        if record is not None:
                            response_data["results"].append(
                                {
                                    "image_idx": idx,
                                    "label": label,
                                    "confidence": f"{confidence:.2%}",
                                    "has_liquid": has_liquid,
                                    "weight_grams": weight_grams,
                                    "output_code": output_code,
                                }
                            )

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


@app.on_event("startup")
async def on_startup() -> None:
    init_db(SQLALCHEMY_DATABASE_URI)
    app.state.session_factory = get_session_factory(SQLALCHEMY_DATABASE_URI)
    app.state.batch_id_generator = BatchIdGenerator()

    start_orchestrator()
    asyncio.create_task(process_batches_background(app))


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


# Include routers
app.include_router(dashboard_router)
app.include_router(stats_router)
app.include_router(esp32_router)
