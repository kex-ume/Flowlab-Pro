import json
import urllib.request

from django.conf import settings

from core.models import CalibrationType, Unit

# Bundled fallback catalog (used when the online source is unreachable).
# Keys are CalibrationType names; values are (name, symbol) pairs.
BUNDLED_CATALOG = {
    'General Calibration': [
        ('gram', 'g'), ('kilogram', 'kg'), ('milligram', 'mg'),
        ('millilitre', 'mL'), ('litre', 'L'), ('microlitre', '\u00b5L'),
        ('newton', 'N'), ('volt', 'V'), ('milliamp', 'mA'), ('amp', 'A'),
        ('ohm', '\u03a9'), ('kilohertz', 'kHz'), ('megahertz', 'MHz'), ('gigahertz', 'GHz'),
        ('hertz', 'Hz'), ('metre', 'm'), ('millimetre', 'mm'), ('micrometre', '\u00b5m'),
        ('newton-metre', 'N\u00b7m'), ('second', 's'), ('minute', 'min'),
    ],
    'Pressure Calibration': [
        ('pascal', 'Pa'), ('kilopascal', 'kPa'), ('megapascal', 'MPa'),
        ('bar', 'bar'), ('millibar', 'mbar'), ('pounds per square inch', 'psi'),
        ('kilogram-force per square centimetre', 'kgf/cm\u00b2'), ('millimetre of mercury', 'mmHg'),
        ('inch of water', 'inH\u2082O'), ('torr', 'Torr'), ('atmosphere', 'atm'),
    ],
    'Temperature Calibration': [
        ('degree Celsius', '\u00b0C'), ('degree Fahrenheit', '\u00b0F'),
        ('kelvin', 'K'), ('degree Rankine', '\u00b0R'),
    ],
}


def _fetch_online():
    """Fetch the unit catalog JSON from the configured URL.

    Expected shape: a JSON object mapping scope names to a list of
    {"name": ..., "symbol": ...} entries. Returns the raw parsed dict or
    None when the URL is unset / fetch fails.
    """
    url = getattr(settings, 'UNITS_CATALOG_URL', '')
    if not url:
        return None
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        return None


def units_for_scope(scope, refresh=False):
    """Return the unit list for a scope, populating the Unit cache on demand.

    Online-first (when the catalog URL is configured and reachable), bundled
    catalog as the offline fallback. Existing rows are preserved; new entries
    are upserted by (symbol, scope). Never raises.
    """
    if not scope:
        return []
    existing = list(Unit.objects.filter(scope_id=scope.pk).order_by('name'))
    if existing and not refresh:
        return existing

    catalog = _fetch_online()
    if catalog:
        raw = catalog.get(scope.name) or []
    else:
        raw = [{'name': n, 'symbol': s} for n, s in BUNDLED_CATALOG.get(scope.name, [])]

    symbols = {u.symbol for u in existing}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        name = (entry.get('name') or '').strip()
        symbol = (entry.get('symbol') or '').strip()
        if not name or not symbol or symbol in symbols:
            continue
        Unit.objects.get_or_create(scope_id=scope.pk, symbol=symbol, defaults={'name': name})
        symbols.add(symbol)

    return list(Unit.objects.filter(scope_id=scope.pk).order_by('name'))


def refresh_all_units():
    """Populate / refresh units for every scope. Returns a dict of
    scope name -> unit count after the refresh."""
    result = {}
    for scope in CalibrationType.objects.all():
        result[scope.name] = len(units_for_scope(scope, refresh=True))
    return result