"""Classification helpers."""

from typing import Optional


def determine_output_code(label: str, has_liquid: str, weight_grams: Optional[float]) -> int:
    if label == "no_detection":
        return 5

    if label == "error":
        return 3

    if has_liquid == "yes":
        return 1

    if has_liquid == "no":
        return 2

    if "plastic" in label.lower() or "bottle" in label.lower():
        return 2

    return 4
