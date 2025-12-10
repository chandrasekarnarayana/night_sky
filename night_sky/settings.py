from pathlib import Path

# Project root is directory containing this file
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / 'data'

# Default settings
DEFAULTS = {
    'mag_label_threshold': 2.0,
    'export_default_size': 2000,
    'limiting_magnitude': 6.0,
    'catalog_mode': 'default',  # default | rich | custom
    'custom_catalog_path': '',
    'label_density': 1,  # 0=planets only,1=sparse,2=rich
    'theme': 'night',  # night | astro_red | high_contrast
    'time_scale': 'utc',  # utc | tt
    'apply_refraction': True,
    'temperature_c': 10.0,
    'pressure_hpa': 1013.0,
    'twilight_sun_alt': 90.0,  # deg; set high to disable filtering by default
    'light_pollution_bortle': 4,  # 1..9
    'high_accuracy_ephem': False,
    'precession_nutation': True,
}

def data_path(filename: str) -> Path:
    return DATA_DIR / filename
