"""Stats and records endpoints."""

import asyncio
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.dependencies import get_db
from app.schemas.stats import StatsResponse, HealthResponse
from app.schemas.esp32 import ImageData
from app.models.trash_record import TrashRecord
from app.workers.processor import get_orchestrator
from app.services.esp32_service import decode_image_from_base64, preprocess_esp32_image
from app.services.carbon_footprint_service import (
    summarize_carbon_footprint_by_label_weight,
)

router = APIRouter(prefix="/api")


@router.get("/stats", response_model=StatsResponse)
async def get_stats(db_session: Session = Depends(get_db)):
    total = db_session.query(TrashRecord).count()

    label_counts = (
        db_session.query(TrashRecord.label, func.count(TrashRecord.id).label("count"))
        .group_by(TrashRecord.label)
        .all()
    )
    total_by_label = {label: count for label, count in label_counts}

    avg_conf_result = db_session.query(func.avg(TrashRecord.confidence)).scalar()
    avg_conf = float(avg_conf_result) if avg_conf_result else 0.0

    time_24h = datetime.utcnow() - timedelta(hours=24)
    recent_24h = db_session.query(TrashRecord).filter(
        TrashRecord.timestamp >= time_24h
    ).count()

    carbon_rows = (
        db_session.query(
            TrashRecord.label,
            func.sum(TrashRecord.weight_grams).label("weight_grams"),
        )
        .filter(TrashRecord.weight_grams.isnot(None), TrashRecord.weight_grams > 0)
        .group_by(TrashRecord.label)
        .all()
    )
    carbon_24h_rows = (
        db_session.query(
            TrashRecord.label,
            func.sum(TrashRecord.weight_grams).label("weight_grams"),
        )
        .filter(
            TrashRecord.timestamp >= time_24h,
            TrashRecord.weight_grams.isnot(None),
            TrashRecord.weight_grams > 0,
        )
        .group_by(TrashRecord.label)
        .all()
    )
    carbon_summary = summarize_carbon_footprint_by_label_weight(carbon_rows)
    carbon_24h_summary = summarize_carbon_footprint_by_label_weight(carbon_24h_rows)

    return StatsResponse(
        total_records=total,
        total_by_label=total_by_label,
        average_confidence=avg_conf,
        recent_24h=recent_24h,
        carbon_footprint_kg_co2e=carbon_summary["total_kg_co2e"],
        carbon_footprint_24h_kg_co2e=carbon_24h_summary["total_kg_co2e"],
        carbon_footprint_by_label=carbon_summary["by_label"],
        total_weight_kg=carbon_summary["total_weight_kg"],
    )


@router.get("/health")
async def health_check(db_session: Session = Depends(get_db)) -> HealthResponse:
    try:
        orchestrator = get_orchestrator()
        stats = orchestrator.get_queue_stats()
        total = db_session.query(TrashRecord).count()

        return HealthResponse(
            status="healthy",
            timestamp=datetime.utcnow().isoformat(),
            orchestrator_status=stats,
            total_records=total,
        )
    except Exception:
        return HealthResponse(
            status="error",
            timestamp=datetime.utcnow().isoformat(),
            orchestrator_status={},
            total_records=0,
        )


@router.get("/records")
async def get_records(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db_session: Session = Depends(get_db),
):
    skip = (page - 1) * limit
    records = (
        db_session.query(TrashRecord)
        .order_by(TrashRecord.timestamp.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    total = db_session.query(TrashRecord).count()

    return {
        "records": [r.to_dict() for r in records],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
    }


@router.post("/image")
async def upload_image(image_data: ImageData, request: Request):
    image = decode_image_from_base64(image_data.data)
    processed_image = await asyncio.to_thread(preprocess_esp32_image, image)
    if processed_image is None:
        raise HTTPException(status_code=400, detail="Invalid image")

    batch_id = await request.app.state.batch_id_generator.next_id()
    orchestrator = get_orchestrator()
    result = orchestrator.submit_batch(
        batch_id, [processed_image], [image_data.weight_grams]
    )

    if result != -1:
        return {"status": "batch_submitted", "batch_id": batch_id, "image_count": 1}

    return {"status": "queued", "batch_id": batch_id, "image_count": 1}
