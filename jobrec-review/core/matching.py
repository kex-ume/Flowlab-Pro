"""Matching helpers: map a pre-calibration (scopes, units, range) onto the
company's available reference standards (Primary) so calibration techs get
smarter unit + standard suggestions."""

from django.db.models import Q

from .procedures import parse_range


def _equipment_bounds(range_str):
    """Return (lo, hi) floats for a human range string, or (None, None)."""
    if range_str:
        rng = parse_range(range_str)
        if rng is not None:
            return rng
    return (None, None)


def _unit_standards(unit):
    """Deduplicated, active reference standards serving `unit` — via the legacy
    single `unit` FK, the new `units` M2M, or both (FK is mirror of M2M first)."""
    seen = set()
    out = []
    for p in list(unit.primaries.all()) + list(unit.primaries_m2m.all()):
        if p.status == 'active' and p.pk not in seen:
            seen.add(p.pk)
            out.append(p)
    return out


def units_with_standards(scopes, range_str=None, require_containment=True):
    """Unit ids (within the given scope ids) that have at least one active
    reference standard, optionally one whose range contains the equipment range.

    A standard with no numeric bounds qualifies ("allow" policy); when
    require_containment is False any active standard in the unit qualifies.
    """
    from .models import Unit

    candidates = Unit.objects.filter(
        Q(primaries__status='active') | Q(primaries_m2m__status='active')
    ).distinct()
    if scopes:
        candidates = candidates.filter(scope_id__in=scopes)
    lo, hi = _equipment_bounds(range_str)
    units = []
    for unit in candidates.prefetch_related('primaries', 'primaries_m2m'):
        standards = _unit_standards(unit)
        if not standards:
            continue
        if not require_containment or lo is None:
            units.append(unit)
            continue
        if any(p.contains_range(lo, hi) for p in standards):
            units.append(unit)
    return units


def available_unit_ids(scopes, range_str=None, require_containment=True):
    return [u.pk for u in units_with_standards(scopes, range_str, require_containment)]


def suggested_primaries(scopes, unit_ids, range_str=None, each=None):
    """Active reference standards for the requested scopes/units, ordered by
    tightest-range fit (smallest standard range that still fully contains the
    equipment range). Standards without numeric bounds sort last."""
    from .models import Primary

    qs = Primary.objects.filter(status='active').filter(
        Q(unit_id__in=unit_ids) | Q(units__id__in=unit_ids)
    ).distinct()
    if scopes:
        qs = qs.filter(scope_id__in=scopes)
    lo, hi = _equipment_bounds(range_str)
    standards = list(qs)
    hit = []
    loose = []
    for p in standards:
        if p.range_bounds is None:
            loose.append(p)
            continue
        if lo is None:
            hit.append(p)
            continue
        if p.contains_range(lo, hi):
            hit.append(p)
    hit.sort(key=lambda p: (p.range_bounds[1] - p.range_bounds[0], p.name.lower()))
    ordered = hit + loose
    if each:
        from itertools import groupby
        out = []
        for _unit_id, group in groupby(ordered, key=lambda p: p.unit_id or 0):
            out.extend(list(group)[:each])
        return out
    return ordered