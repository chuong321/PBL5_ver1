"""Carbon footprint estimation helpers for classified trash records."""

from collections import defaultdict
from typing import Iterable, Optional

from app.models.trash_record import TrashRecord


DEFAULT_EMISSION_FACTOR_KG_CO2E_PER_KG = 1.0

EMISSION_FACTORS_KG_CO2E_PER_KG = {
    # Hazardous and e-waste
    "battery": 2.5,
    "dangerous": 2.5,
    "electronic": 3.0,
    "light": 2.0,
    "lighter": 2.0,
    "medicine": 2.5,
    "pressurized_can": 2.0,
    "thermometer": 2.5,
    # Recyclables
    "book": 0.9,
    "bucket": 2.3,
    "cans": 8.6,
    "cardboard": 0.7,
    "CD": 3.0,
    "glass": 0.8,
    "glass_bottle": 0.8,
    "paper": 0.9,
    "paper_box": 0.7,
    "plastic_bottle": 1.7,
    "milk_carton": 1.2,
    "nylon": 2.5,
    "liquid": 0.3,
    # Organic waste
    "coffee_residue": 0.4,
    "egg_shell": 0.3,
    "food_organics": 0.5,
    "teabag": 0.4,
    # Mixed/residual waste
    "household": 1.1,
    "pants": 3.0,
    "shirt": 3.0,
    "shoes": 4.0,
    "bowl": 1.2,
    "cigarette": 1.0,
    "diaper": 1.4,
    "mask": 2.0,
    "pen": 2.5,
    "tissues": 0.9,
}


def get_emission_factor(label: Optional[str]) -> float:
    """Return kg CO2e per kg of waste for a label."""
    if not label:
        return DEFAULT_EMISSION_FACTOR_KG_CO2E_PER_KG

    return EMISSION_FACTORS_KG_CO2E_PER_KG.get(
        label, DEFAULT_EMISSION_FACTOR_KG_CO2E_PER_KG
    )


def calculate_record_footprint_kg_co2e(record: TrashRecord) -> float:
    """Estimate carbon footprint for one classification record."""
    if record.weight_grams is None or record.weight_grams <= 0:
        return 0.0

    weight_kg = record.weight_grams / 1000
    return weight_kg * get_emission_factor(record.label)


def summarize_carbon_footprint(records: Iterable[TrashRecord]) -> dict:
    """Summarize total carbon footprint and per-label contribution."""
    total_kg_co2e = 0.0
    total_weight_kg = 0.0
    by_label = defaultdict(float)

    for record in records:
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
    """Summarize carbon footprint from grouped label and weight rows."""
    total_kg_co2e = 0.0
    total_weight_kg = 0.0
    by_label = {}

    for label, weight_grams in label_weight_rows:
        if weight_grams is None or weight_grams <= 0:
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
