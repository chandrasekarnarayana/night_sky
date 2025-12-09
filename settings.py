from pathlib import Path

# Project root is directory containing this file
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / 'data'

# Default settings
DEFAULTS = {
    'mag_label_threshold': 2.0,
    'export_default_size': 2000,
}

def data_path(filename: str) -> Path:
    return DATA_DIR / filename
