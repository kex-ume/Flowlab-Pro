"""Helpers for calibration procedures."""
import re


def parse_range(range_str):
    """Parse a human range string into (min, max) floats.

    Accepts forms like '0–10 bar', '0-10 bar', '-5 to 25 °C', '100'
    (treated as 0..100). Returns None when no numeric bounds can be extracted.

    An ASCII hyphen is ambiguous: '0-10 bar' splits into the pair (0, -10),
    which would wrongly read as -10..0. When exactly two numbers are found and
    the second is negative while the first is not AND there is no explicit
    'to', the hyphen is treated as a range separator (0..10), matching the
    en-dash form. Forms like '-5 to 25' keep their negative low bound.
    """
    if not range_str:
        return None
    nums = re.findall(r'-?\d+(?:\.\d+)?', str(range_str))
    if not nums:
        return None
    a = float(nums[0])
    b = float(nums[1]) if len(nums) > 1 else 0.0
    if len(nums) == 2 and a >= 0 and b < 0 and 'to' not in str(range_str).lower():
        a, b = a, -b
    return (min(a, b), max(a, b))


def test_point_values(procedure, range_str):
    """Resolve a procedure's % test points against an equipment range string.

    Returns a list of absolute values, or [] when unresolvable.
    """
    rng = parse_range(range_str)
    if rng is None:
        return []
    lo, hi = rng
    values = []
    for pct in (procedure.test_points_percent or []):
        try:
            values.append(lo + (hi - lo) * (float(pct) / 100))
        except (TypeError, ValueError):
            continue
    return values
