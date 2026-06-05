"""CO2e savings estimation helpers for recyclable trash records."""

from collections import defaultdict
from typing import Iterable, Optional

from app.models.trash_record import TrashRecord


EPA_WARM_FACTORS_SOURCE = (
    "U.S. EPA, Waste Reduction Model (WARM) Version 16, "
    "Management Practices Chapters and material-specific chapters."
)
EPA_WARM_FACTORS_URL = (
    "https://www.epa.gov/system/files/documents/2024-01/"
    "warm_management_practices_v16_dec.pdf"
)

KG_PER_SHORT_TON = 907.18474
KG_CO2E_PER_METRIC_TON_CO2E = 1000


def _warm_factor(mtco2e_per_short_ton: float) -> float:
    """Convert WARM MTCO2e/short ton material to kg CO2e/kg material."""
    return mtco2e_per_short_ton * KG_CO2E_PER_METRIC_TON_CO2E / KG_PER_SHORT_TON


# WARM factors are comparative life-cycle factors for material management options.
# For the dashboard we estimate avoided emissions from recycling instead of
# landfilling: avoided CO2e = mass * (EF_landfill - EF_recycling).
RECYCLABLE_LABELS = {
    "book",
    "bucket",
    "cans",
    "cardboard",
    "glass",
    "glass_bottle",
    "paper",
    "paper_box",
    "plastic_bottle",
}

WARM_LABEL_FACTORS = {
    # Recyclables only. The CO2e savings dashboard intentionally ignores
    # hazardous, organic, mixed, and residual detections.
    # Values are MTCO2e/short ton from WARM v16:
    # (WARM material, EF_landfill, EF_recycling).
    "book": ("Textbooks", 1.13, -3.10),
    "bucket": ("Mixed Plastics", 0.02, -0.93),
    "cans": ("Aluminum Cans", 0.02, -9.13),
    "cardboard": ("Corrugated Containers", 0.18, -3.14),
    "glass": ("Glass", 0.02, -0.28),
    "glass_bottle": ("Glass", 0.02, -0.28),
    "paper": ("Office Paper", 1.13, -2.86),
    "paper_box": ("Corrugated Containers", 0.18, -3.14),
    "plastic_bottle": ("PET", 0.02, -1.04),
}

DEFAULT_EMISSION_FACTOR_KG_CO2E_PER_KG = 0.0

EMISSION_FACTORS_KG_CO2E_PER_KG = {
    label: _warm_factor(landfill_factor - recycling_factor)
    for label, (_, landfill_factor, recycling_factor) in WARM_LABEL_FACTORS.items()
}


def get_emission_factor(label: Optional[str]) -> float:
    """Return kg CO2e avoided per kg for recyclable waste labels only."""
    if not label or label not in RECYCLABLE_LABELS:
        return DEFAULT_EMISSION_FACTOR_KG_CO2E_PER_KG

    return EMISSION_FACTORS_KG_CO2E_PER_KG.get(
        label, DEFAULT_EMISSION_FACTOR_KG_CO2E_PER_KG
    )


def is_recyclable_label(label: Optional[str]) -> bool:
    """Return True when a model label belongs to the recyclable group."""
    return label in RECYCLABLE_LABELS


def calculate_record_footprint_kg_co2e(record: TrashRecord) -> float:
    """Estimate avoided CO2e for one recyclable classification record."""
    if (
        not is_recyclable_label(record.label)
        or record.weight_grams is None
        or record.weight_grams <= 0
    ):
        return 0.0

    weight_kg = record.weight_grams / 1000
    return weight_kg * get_emission_factor(record.label)


def summarize_carbon_footprint(records: Iterable[TrashRecord]) -> dict:
    """Summarize total avoided CO2e and per-label contribution."""
    total_kg_co2e = 0.0
    total_weight_kg = 0.0
    by_label = defaultdict(float)

    for record in records:
        if not is_recyclable_label(record.label):
            continue

        footprint = calculate_record_footprint_kg_co2e(record)
        total_kg_co2e += footprint
        by_label[record.label] += footprint

        if record.weight_grams is not None and record.weight_grams > 0:
            total_weight_kg += record.weight_grams / 1000

    return {
        "total_kg_co2e": round(total_kg_co2e, 3),
        "total_weight_kg": round(total_weight_kg, 3),
        "by_label": {
            label: round(value, 3)
            for label, value in sorted(
                by_label.items(), key=lambda item: item[1], reverse=True
            )
        },
    }


def summarize_carbon_footprint_by_label_weight(label_weight_rows: Iterable) -> dict:
    """Summarize avoided CO2e from grouped label and weight rows."""
    total_kg_co2e = 0.0
    total_weight_kg = 0.0
    by_label = {}

    for label, weight_grams in label_weight_rows:
        if (
            not is_recyclable_label(label)
            or weight_grams is None
            or weight_grams <= 0
        ):
            continue

        weight_kg = weight_grams / 1000
        footprint = weight_kg * get_emission_factor(label)
        total_weight_kg += weight_kg
        by_label[label] = by_label.get(label, 0.0) + footprint
        total_kg_co2e += footprint

    return {
        "total_kg_co2e": round(total_kg_co2e, 3),
        "total_weight_kg": round(total_weight_kg, 3),
        "by_label": {
            label: round(value, 3)
            for label, value in sorted(
                by_label.items(), key=lambda item: item[1], reverse=True
            )
        },
    }
