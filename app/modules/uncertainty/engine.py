"""Auditable uncertainty and CMC calculation domain services.

No UI framework belongs in this module.  Inputs are explicit and results are
immutable value objects that can be serialized into a reproducible snapshot.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from math import inf, sqrt
from statistics import mean, stdev
from typing import Iterable


CALCULATION_VERSION = "flp-rss-1.0"


@dataclass(frozen=True)
class Budget2Rule:
    input_type: str
    distribution: str
    divisor: float
    requires_coverage_factor: bool = False
    version: str = "1"

    def __post_init__(self):
        if self.divisor <= 0:
            raise ValueError("A controlled Budget 2 divisor must be greater than zero.")


@dataclass(frozen=True)
class UncertaintyInput:
    source: str
    source_type: str
    source_origin: str
    input_value: float
    unit: str
    uncertainty_input_type: str
    distribution: str
    divisor: float
    sensitivity_coefficient: float = 1.0
    degrees_of_freedom: float | None = None
    equipment_id: str | None = None
    flow_point: float | None = None
    source_status: str = "Valid"
    evidence: str | None = None
    notes: str | None = None
    source_version: str | None = None
    calibration_record_id: int | None = None

    def __post_init__(self):
        if self.source_type not in {"A", "B"}:
            raise ValueError("Source type must be A or B.")
        if self.divisor <= 0:
            raise ValueError("Divisor must be greater than zero.")
        if self.source_status.lower() not in {"valid", "approved", "current"}:
            raise ValueError(f"Source '{self.source}' is not valid for calculation.")


@dataclass(frozen=True)
class CalculatedComponent:
    input: UncertaintyInput
    standard_uncertainty: float
    contribution: float
    contribution_percent: float


@dataclass(frozen=True)
class UncertaintyResult:
    components: tuple[CalculatedComponent, ...]
    rss_sum: float
    combined_standard_uncertainty: float
    coverage_factor: float
    expanded_uncertainty: float
    relative_expanded_uncertainty: float | None
    calculation_version: str
    calculated_at: str
    effective_degrees_of_freedom: float = inf
    coverage_probability: float = 95.0
    covariance_sum: float = 0.0

    def snapshot(self) -> dict:
        return asdict(self)


class Budget2Resolver:
    """Resolve laboratory-controlled conversions; never infer rules by label."""

    def __init__(self, rules: Iterable[Budget2Rule]):
        self.rules = {rule.input_type: rule for rule in rules}

    def resolve(self, input_type: str, coverage_factor: float | None = None) -> Budget2Rule:
        try:
            rule = self.rules[input_type]
        except KeyError as error:
            raise ValueError(f"Budget 2 rule is not configured for '{input_type}'.") from error
        if rule.requires_coverage_factor:
            if coverage_factor is None or coverage_factor <= 0:
                raise ValueError(f"'{input_type}' requires a valid coverage factor.")
            return Budget2Rule(rule.input_type, rule.distribution, coverage_factor, True, rule.version)
        return rule


class TypeAProcessor:
    @staticmethod
    def from_observations(source: str, observations: Iterable[float], unit: str,
                          flow_point: float | None = None, origin: str = "Manual",
                          evidence: str | None = None) -> tuple[UncertaintyInput, dict]:
        values = tuple(float(value) for value in observations)
        if len(values) < 2:
            raise ValueError("Type A evaluation requires at least two observations.")
        standard_deviation = stdev(values)
        standard_uncertainty = standard_deviation / sqrt(len(values))
        component = UncertaintyInput(
            source=source, source_type="A", source_origin=origin,
            input_value=standard_uncertainty, unit=unit,
            uncertainty_input_type="Standard Uncertainty", distribution="Normal",
            divisor=1.0, degrees_of_freedom=len(values) - 1,
            flow_point=flow_point, evidence=evidence,
            notes="Derived from retained repeated observations.",
        )
        statistics = {"observations": values, "n": len(values), "mean": mean(values),
                      "standard_deviation": standard_deviation,
                      "standard_uncertainty": standard_uncertainty}
        return component, statistics


class RSSEngine:
    @staticmethod
    def calculate(components: Iterable[UncertaintyInput], coverage_factor: float = 2.0,
                  measurand: float | None = None) -> UncertaintyResult:
        inputs = tuple(components)
        if not inputs:
            raise ValueError("At least one valid uncertainty source is required.")
        if coverage_factor <= 0:
            raise ValueError("Coverage factor must be greater than zero.")
        intermediates = []
        rss_sum = 0.0
        for component in inputs:
            standard = abs(float(component.input_value)) / float(component.divisor)
            contribution = standard * float(component.sensitivity_coefficient)
            square = contribution ** 2
            rss_sum += square
            intermediates.append((component, standard, contribution, square))
        combined = sqrt(rss_sum)
        expanded = combined * coverage_factor
        calculated = tuple(CalculatedComponent(item, standard, contribution,
            (square / rss_sum * 100.0) if rss_sum else 0.0)
            for item, standard, contribution, square in intermediates)
        relative = (expanded / abs(measurand) * 100.0) if measurand not in (None, 0) else None
        return UncertaintyResult(calculated, rss_sum, combined, coverage_factor,
            expanded, relative, CALCULATION_VERSION,
            datetime.now(timezone.utc).isoformat())


class GUMEngine:
    """Server-side GUM calculation including covariance and effective DOF."""

    @staticmethod
    def coverage_factor_95(degrees_of_freedom: float) -> float:
        if degrees_of_freedom == inf or degrees_of_freedom >= 200:
            return 1.96
        table = ((1, 12.706), (2, 4.303), (3, 3.182), (4, 2.776),
                 (5, 2.571), (6, 2.447), (7, 2.365), (8, 2.306),
                 (9, 2.262), (10, 2.228), (12, 2.179), (15, 2.131),
                 (20, 2.086), (25, 2.060), (30, 2.042), (40, 2.021),
                 (50, 2.009), (60, 2.000), (80, 1.990), (100, 1.984),
                 (120, 1.980), (200, 1.972))
        for limit, factor in table:
            if degrees_of_freedom <= limit:
                return factor
        return 1.96

    @classmethod
    def calculate(cls, components: Iterable[UncertaintyInput], correlations=(),
                  coverage_mode: str = "auto", coverage_factor: float | None = None,
                  coverage_probability: float = 95.0,
                  measurand: float | None = None) -> UncertaintyResult:
        inputs = tuple(components)
        if not inputs:
            raise ValueError("At least one valid uncertainty source is required.")
        rows, variance = [], 0.0
        by_name = {}
        for item in inputs:
            standard = abs(float(item.input_value)) / float(item.divisor)
            contribution = standard * float(item.sensitivity_coefficient)
            square = contribution ** 2
            variance += square
            rows.append((item, standard, contribution, square))
            by_name[item.source] = contribution
        covariance_sum = 0.0
        seen = set()
        for correlation in correlations:
            source_i = correlation.get("source_i") or correlation.get("a")
            source_j = correlation.get("source_j") or correlation.get("b")
            if not source_i or not source_j or source_i == source_j:
                raise ValueError("Correlation must identify two different uncertainty sources.")
            key = tuple(sorted((source_i, source_j)))
            if key in seen:
                raise ValueError(f"Correlation for '{source_i}' and '{source_j}' is duplicated.")
            seen.add(key)
            coefficient = float(correlation.get("coefficient", correlation.get("r")))
            if not -1 <= coefficient <= 1:
                raise ValueError("Correlation coefficient must be between -1 and +1.")
            if source_i not in by_name or source_j not in by_name:
                raise ValueError("Correlation refers to an excluded or unknown uncertainty source.")
            if not str(correlation.get("justification", "")).strip():
                raise ValueError(f"Correlation between '{source_i}' and '{source_j}' requires a justification.")
            term = 2 * by_name[source_i] * by_name[source_j] * coefficient
            covariance_sum += term
        total_variance = variance + covariance_sum
        if total_variance < -1e-15:
            raise ValueError("Correlation terms produce a negative combined variance.")
        total_variance = max(0.0, total_variance)
        combined = sqrt(total_variance)
        denominator = sum((contribution ** 4) / float(item.degrees_of_freedom)
                          for item, _, contribution, _ in rows
                          if item.degrees_of_freedom not in (None, 0, inf))
        effective_dof = combined ** 4 / denominator if denominator else inf
        if coverage_mode == "auto":
            factor = cls.coverage_factor_95(effective_dof)
        elif coverage_mode == "manual":
            if coverage_factor is None or float(coverage_factor) <= 0:
                raise ValueError("Manual coverage requires a coverage factor greater than zero.")
            factor = float(coverage_factor)
        else:
            raise ValueError("Coverage mode must be Auto or Manual.")
        expanded = combined * factor
        calculated = tuple(CalculatedComponent(item, standard, contribution,
            (square / total_variance * 100.0) if total_variance else 0.0)
            for item, standard, contribution, square in rows)
        relative = (expanded / abs(measurand) * 100.0) if measurand not in (None, 0) else None
        return UncertaintyResult(calculated, total_variance, combined, factor,
            expanded, relative, "flp-gum-2.0", datetime.now(timezone.utc).isoformat(),
            effective_dof, coverage_probability, covariance_sum)

    @staticmethod
    def gravimetric_run(collected_mass: float, collection_time: float,
                        mut_indication: float, quantity: str = "mass",
                        density: float | None = None,
                        density_unit: str = "kg/m³",
                        flow_unit: str | None = None) -> dict:
        mass, elapsed, indication = map(float, (collected_mass, collection_time, mut_indication))
        if mass <= 0 or elapsed <= 0:
            raise ValueError("Collected mass and collection time must be greater than zero.")
        if quantity == "volume":
            if density is None or float(density) <= 0:
                raise ValueError("Density or specific volume must be greater than zero for volume flow.")
            density_value = float(density)
            if density_unit == "m³/kg":
                cubic_metres_per_second = mass * density_value / elapsed
            elif density_unit == "kg/m³":
                cubic_metres_per_second = mass / density_value / elapsed
            else:
                raise ValueError("Density input unit must be kg/m³ or m³/kg.")
            factors = {"m³/s": 1.0, "m³/h": 3600.0, "L/s": 1000.0,
                       "L/min": 60000.0, "BPD": 86400.0 / 0.158987294928}
            selected_unit = flow_unit or "m³/s"
            if selected_unit not in factors:
                raise ValueError(f"Flow unit {selected_unit} is not valid for volume flow.")
            reference = cubic_metres_per_second * factors[selected_unit]
        elif quantity == "mass":
            kilograms_per_second = mass / elapsed
            factors = {"kg/s": 1.0, "kg/min": 60.0, "kg/h": 3600.0,
                       "g/s": 1000.0, "g/min": 60000.0}
            selected_unit = flow_unit or "kg/s"
            if selected_unit not in factors:
                raise ValueError(f"Flow unit {selected_unit} is not valid for mass flow.")
            reference = kilograms_per_second * factors[selected_unit]
        else:
            raise ValueError("Flow quantity must be mass or volume.")
        error = (indication - reference) / reference * 100.0
        return {"reference_flow": reference, "error_percent": error}

    @staticmethod
    def coriolis_run(master_indication: float, master_correction: float | None,
                     mut_indication: float) -> dict:
        if master_correction is None:
            raise ValueError("Master-meter correction is required and cannot be assumed to be zero.")
        reference = float(master_indication) * (1 + float(master_correction))
        if reference == 0:
            raise ValueError("Corrected master-meter reference must not be zero.")
        error = (float(mut_indication) - reference) / reference * 100.0
        return {"reference_flow": reference, "error_percent": error}


class CMCService:
    SUPPORTED_METHODS = {"Gravimetric Method", "Coriolis Comparison Method"}

    @classmethod
    def calculate(cls, method: str, components: Iterable[UncertaintyInput],
                  coverage_factor: float = 2.0) -> UncertaintyResult:
        if method not in cls.SUPPORTED_METHODS:
            raise ValueError("CMC method must be Gravimetric Method or Coriolis Comparison Method.")
        return RSSEngine.calculate(components, coverage_factor)
