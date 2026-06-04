"""Pydantic schemas for stats endpoints."""

from typing import Dict
from pydantic import BaseModel


class StatsResponse(BaseModel):
    total_records: int
    total_by_label: Dict[str, int]
    average_confidence: float
    recent_24h: int
    carbon_footprint_kg_co2e: float
    carbon_footprint_24h_kg_co2e: float
    carbon_footprint_by_label: Dict[str, float]
    total_weight_kg: float


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    orchestrator_status: Dict
    total_records: int
