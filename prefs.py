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
        # Only write known keys
        out = {k: bool(prefs.get(k, DEFAULT_PREFS[k])) for k in DEFAULT_PREFS.keys()}
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(out, f, indent=2)
    except Exception:
        pass
