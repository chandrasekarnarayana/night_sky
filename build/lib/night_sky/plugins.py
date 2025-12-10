"""Simple plugin loader for Night Sky.

Plugins are Python modules placed in either:
- ~/.night_sky/plugins/
- night_sky/plugins/ (packaged)

Each plugin module may define an `init_plugin(app_context)` function,
where `app_context` can expose hooks (currently the MainWindow instance).
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any, List

PLUGIN_DIRS = [
    Path.home() / '.night_sky' / 'plugins',
    Path(__file__).resolve().parent / 'plugins',
]


def discover_plugins() -> List[str]:
    names = []
    for base in PLUGIN_DIRS:
        if not base.exists():
            continue
        for py in base.glob('*.py'):
            if py.name.startswith('_'):
                continue
            names.append(f"{py.stem}")
    return names


def load_plugins(app_context: Any):
    loaded = []
    for base in PLUGIN_DIRS:
        if not base.exists():
            continue
        if str(base) not in sys.path:
            sys.path.insert(0, str(base))
        for py in base.glob('*.py'):
            if py.name.startswith('_'):
                continue
            mod_name = py.stem
            try:
                mod = importlib.import_module(mod_name)
                if hasattr(mod, 'init_plugin'):
                    mod.init_plugin(app_context)
                loaded.append(mod_name)
            except Exception:
                continue
    return loaded
