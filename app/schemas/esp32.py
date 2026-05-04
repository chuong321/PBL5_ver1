"""Pydantic schemas for ESP32 communication."""

from typing import Optional
from pydantic import BaseModel


class ImageData(BaseModel):
    data: str
    weight_grams: Optional[float] = 50.0
