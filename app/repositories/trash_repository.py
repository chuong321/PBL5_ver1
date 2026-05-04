"""TrashRecord data access layer."""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.models.trash_record import TrashRecord


class TrashRepository:
    """Repository for TrashRecord database operations."""

    @staticmethod
    def create_record(
        db_session: Session,
        image_path: str,
        label: str,
        confidence: float,
        has_liquid: str = None,
        weight_grams: float = None,
        individual_confidences: str = None,
        primary_model_output: str = None,
        secondary_model_output: str = None,
    ) -> TrashRecord:
        try:
            record = TrashRecord(
                image_path=image_path,
                label=label,
                confidence=confidence,
                has_liquid=has_liquid,
                weight_grams=weight_grams,
                individual_confidences=individual_confidences,
                primary_model_output=primary_model_output,
                secondary_model_output=secondary_model_output,
                timestamp=datetime.utcnow(),
            )
            db_session.add(record)
            db_session.commit()
            return record
        except Exception:
            db_session.rollback()
            return None

    @staticmethod
    def get_record_by_id(db_session: Session, record_id: int) -> TrashRecord:
        return db_session.query(TrashRecord).filter(TrashRecord.id == record_id).first()

    @staticmethod
    def get_all_records(db_session: Session, limit: int = None) -> list:
        query = db_session.query(TrashRecord).order_by(desc(TrashRecord.timestamp))
        if limit:
            query = query.limit(limit)
        return query.all()

    @staticmethod
    def get_records_paginated(db_session: Session, page: int = 1, per_page: int = 20):
        total = db_session.query(TrashRecord).count()
        skip = (page - 1) * per_page
        records = (
            db_session.query(TrashRecord)
            .order_by(desc(TrashRecord.timestamp))
            .offset(skip)
            .limit(per_page)
            .all()
        )
        return records, total

    @staticmethod
    def get_records_by_label(db_session: Session, label: str, limit: int = 50) -> list:
        return (
            db_session.query(TrashRecord)
            .filter(TrashRecord.label == label)
            .order_by(desc(TrashRecord.timestamp))
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_records_by_has_liquid(
        db_session: Session, has_liquid: str, limit: int = 50
    ) -> list:
        return (
            db_session.query(TrashRecord)
            .filter(TrashRecord.has_liquid == has_liquid)
            .order_by(desc(TrashRecord.timestamp))
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_records_by_confidence(
        db_session: Session, min_confidence: float = 0.5
    ) -> list:
        return (
            db_session.query(TrashRecord)
            .filter(TrashRecord.confidence >= min_confidence)
            .order_by(desc(TrashRecord.timestamp))
            .all()
        )

    @staticmethod
    def get_recent_records(db_session: Session, minutes: int = 60, limit: int = 10) -> list:
        time_threshold = datetime.utcnow() - timedelta(minutes=minutes)
        return (
            db_session.query(TrashRecord)
            .filter(TrashRecord.timestamp >= time_threshold)
            .order_by(desc(TrashRecord.timestamp))
            .limit(limit)
            .all()
        )

    @staticmethod
    def count_total_records(db_session: Session) -> int:
        return db_session.query(TrashRecord).count()

    @staticmethod
    def get_statistics(db_session: Session) -> dict:
        total = TrashRepository.count_total_records(db_session)

        label_counts = (
            db_session.query(TrashRecord.label, func.count(TrashRecord.id).label("count"))
            .group_by(TrashRecord.label)
            .all()
        )
        stats_by_label = {label: count for label, count in label_counts}

        liquid_counts = (
            db_session.query(TrashRecord.has_liquid, func.count(TrashRecord.id).label("count"))
            .filter(TrashRecord.has_liquid.isnot(None))
            .group_by(TrashRecord.has_liquid)
            .all()
        )
        stats_by_liquid = {liquid: count for liquid, count in liquid_counts}

        avg_conf = db_session.query(func.avg(TrashRecord.confidence)).scalar() or 0.0

        time_24h = datetime.utcnow() - timedelta(hours=24)
        recent_24h = db_session.query(TrashRecord).filter(
            TrashRecord.timestamp >= time_24h
        ).count()

        return {
            "total": total,
            "by_label": stats_by_label,
            "by_liquid": stats_by_liquid,
            "average_confidence": float(avg_conf),
            "recent_24h": recent_24h,
            "timestamp": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def delete_old_records(db_session: Session, days: int = 30):
        try:
            time_threshold = datetime.utcnow() - timedelta(days=days)
            deleted_count = db_session.query(TrashRecord).filter(
                TrashRecord.timestamp < time_threshold
            ).delete()
            db_session.commit()
            return deleted_count
        except Exception:
            db_session.rollback()
            return 0
