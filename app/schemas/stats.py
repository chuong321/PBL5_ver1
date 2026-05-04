"""Pydantic schemas for stats endpoints."""

from typing import Dict
from pydantic import BaseModel


class StatsResponse(BaseModel):
    total_records: int
    total_by_label: Dict[str, int]
    average_confidence: float
    recent_24h: int


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    orchestrator_status: Dict
    total_records: int
