"""Simple data loading helpers for offline CSV files in `data/`.

v0.1: provides `get_data_path` and `load_bright_stars` for the
`stars_bright.csv` offline catalog.
"""

import csv
from pathlib import Path
from typing import List, Dict, Optional
import importlib.resources as pkg_resources


def get_data_path(*parts: str) -> Path:
    """Return a `Path` inside the package `data/` directory.

    Usage: `get_data_path('stars_bright.csv')` or `get_data_path('subdir', 'file.json')`.
    Paths are resolved relative to this file's parent directory.
    """
    try:
        data_dir = pkg_resources.files(__package__).joinpath('data')
    except Exception:
        data_dir = Path(__file__).resolve().parent / 'data'
    return Path(data_dir).joinpath(*parts)


def load_bright_stars(catalog: Optional[str] = None) -> List[Dict]:
    """Load star catalog.

    Catalog options:
    - None: auto-select (stars_extended.csv if present else stars_bright.csv)
    - "default": prefer stars_extended.csv
    - "rich": use stars_rich.csv if present (mag~10), else extended
    - path: absolute/relative path to user CSV

    Each dict contains the keys: `id` (int), `name` (str), `ra_deg` (float),
    `dec_deg` (float), and `mag` (float). Extended catalogs may include
    additional fields (spectral type, etc.) which are preserved.

    Raises FileNotFoundError if the CSV is missing.
    """
    base = get_data_path('')
    if catalog is None or catalog == 'default':
        path = get_data_path('stars_extended.csv')
        if not path.exists():
            path = get_data_path('stars_bright.csv')
    elif catalog == 'rich':
        path = get_data_path('stars_rich.csv')
        if not path.exists():
            path = get_data_path('stars_extended.csv')
    else:
        p = Path(catalog)
        path = p if p.is_absolute() else (base / p)
    if not Path(path).exists():
        raise FileNotFoundError(f"Stars file not found: {path}")

    stars: List[Dict] = []
    with open(path, newline='', encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            # Basic conversion; skip rows that fail conversion
            try:
                star = {
                    'id': int(row['id']),
                    'name': row.get('name', '').strip(),
                    'ra_deg': float(row['ra_deg']),
                    'dec_deg': float(row['dec_deg']),
                    'mag': float(row['mag']),
                }
            except Exception:
                continue
            stars.append(star)
    return stars


def load_stars(csv_filename: str = 'stars_bright.csv') -> List[Dict]:
    """Backward-compatible helper. Delegates to `load_bright_stars` when appropriate."""
    if csv_filename == 'stars_bright.csv':
        return load_bright_stars()
    if csv_filename == 'stars_extended.csv':
        return load_bright_stars('default')
    if csv_filename == 'stars_rich.csv':
        return load_bright_stars('rich')
    # Generic loader for other CSVs in `data/`
    path = get_data_path(csv_filename)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    rows: List[Dict] = []
    with open(path, newline='', encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(row)
    return rows


def load_cities(csv_filename: str = 'cities.csv') -> List[Dict]:
    """Load `data/cities.csv` returning list of dicts with keys:
    `name`, `country`, `lat_deg`, `lon_deg`.

    Raises FileNotFoundError if missing.
    """
    path = get_data_path(csv_filename)
    if not path.exists():
        raise FileNotFoundError(f"Cities file not found: {path}")
    cities: List[Dict] = []
    with open(path, newline='', encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            try:
                city = {
                    'name': row.get('name', '').strip(),
                    'country': row.get('country', '').strip(),
                    'lat_deg': float(row['lat_deg']),
                    'lon_deg': float(row['lon_deg']),
                }
            except Exception:
                continue
            cities.append(city)
    return cities
