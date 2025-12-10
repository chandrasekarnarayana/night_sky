"""Simple preferences persistence for Night Sky Viewer v0.3.

Stores a small JSON file under the user's home directory `~/.night_sky/prefs.json`.
Provides `load_prefs()` and `save_prefs()` helpers.
"""
from pathlib import Path
import json

CONFIG_DIR = Path.home() / '.night_sky'
CONFIG_PATH = CONFIG_DIR / 'prefs.json'

DEFAULT_PREFS = {
    'show_star_labels': True,
    'show_planet_labels': True,
    'show_constellations': True,
    'show_dso': True,
    'projection_mode': 'rect',
    'view_mode': '2d',
    'lat_deg': 0.0,
    'lon_deg': 0.0,
    'export_default_size': 2000,
    'limiting_magnitude': 6.0,
    'catalog_mode': 'default',
    'custom_catalog_path': '',
    'label_density': 1,
    'theme': 'night',
    'time_scale': 'utc',
    'apply_refraction': True,
    'temperature_c': 10.0,
    'pressure_hpa': 1013.0,
    'twilight_sun_alt': 90.0,
    'light_pollution_bortle': 4,
    'high_accuracy_ephem': False,
    'precession_nutation': True,
    'apply_aberration': True,
    'milky_way_texture': '',
    'panorama_image': '',
}


def load_prefs():
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # merge defaults
            prefs = DEFAULT_PREFS.copy()
            prefs.update({k: data.get(k, prefs[k]) for k in prefs.keys()})
            return prefs
    except Exception:
        pass
    return DEFAULT_PREFS.copy()


def save_prefs(prefs: dict):
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        # Only write known keys, preserving types
        out = {}
        for key, default_val in DEFAULT_PREFS.items():
            val = prefs.get(key, default_val)
            if isinstance(default_val, bool):
                val = bool(val)
            elif isinstance(default_val, float):
                val = float(val)
            elif isinstance(default_val, int):
                val = int(val)
            out[key] = val
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(out, f, indent=2)
    except Exception:
        pass


def export_prefs(path: str):
    """Export current prefs to a JSON file."""
    try:
        prefs = load_prefs()
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(prefs, f, indent=2)
        return True
    except Exception:
        return False


def import_prefs(path: str):
    """Import prefs from a JSON file, merging with defaults."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        prefs = DEFAULT_PREFS.copy()
        prefs.update(data)
        save_prefs(prefs)
        return prefs
    except Exception:
        return load_prefs()


def reset_prefs():
    """Reset preferences to defaults."""
    try:
        save_prefs(DEFAULT_PREFS.copy())
    except Exception:
        pass
