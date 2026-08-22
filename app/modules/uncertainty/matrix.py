"""Controlled FlowLab Matrix range resolver."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MatrixBand:
    minimum_lpm: float
    maximum_lpm: float
    pump: str
    tank: str
    diverter: str
    weighing_system: str
    reference_meter: str
    temperature_instrument: str
    pressure_instrument: str
    procedure: str


class MatrixResolver:
    LPM_FACTORS = {"L/min": 1.0, "LPM": 1.0, "m³/h": 1000.0 / 60.0,
                   "m3/h": 1000.0 / 60.0, "BPD": 158.987294928 / 1440.0}

    @classmethod
    def to_lpm(cls, value: float, unit: str) -> float:
        try:
            return float(value) * cls.LPM_FACTORS[unit]
        except KeyError as error:
            raise ValueError(f"Unsupported matrix flow unit '{unit}'.") from error

    @classmethod
    def resolve_range(cls, bands, minimum, maximum, unit):
        low, high = cls.to_lpm(minimum, unit), cls.to_lpm(maximum, unit)
        if high < low:
            raise ValueError("Maximum flow must not be below minimum flow.")
        matches = tuple(band for band in bands
                        if low <= band.maximum_lpm and high >= band.minimum_lpm)
        if not matches or low < min(b.minimum_lpm for b in bands) or high > max(b.maximum_lpm for b in bands):
            raise ValueError("Requested flow range is outside the approved FlowLab Matrix.")
        return matches

    @classmethod
    def resolve_point(cls, bands, point, unit):
        value = cls.to_lpm(point, unit)
        matches = tuple(band for band in bands if band.minimum_lpm <= value <= band.maximum_lpm)
        if len(matches) != 1:
            raise ValueError("Flow point does not resolve to exactly one approved matrix band.")
        return matches[0]
