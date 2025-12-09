# Night Sky Viewer — v0.3

This is an offline desktop planetarium with 2D/3D sky visualization and constellation support.

Features in v0.3:
- **3D OpenGL dome**: Immersive hemispherical 3D sky view (when GPU available)
- **Automatic fallback**: If 3D fails, app gracefully falls back to 2D mode
- **2D modes**: Rectangular (Az/Alt grid) and Dome (polar projection)
- **City search**: Select observing location by city name or enter lat/lon manually
- **Earth tab**: 2D world map with click-to-select location (3D globe if OpenGL available)
- **Constellation lines**: Display faint lines connecting stars (from offline CSV)
- **Date/time control**: Pick observation date/time (UTC) with "Now" button
- **High-resolution export**: Save current view as PNG (2D or 3D) at ≥2000×2000 px

Requirements:
- Python 3.8+
- See `requirements.txt` (PyQt5, pyqtgraph, astropy, numpy)

Quick start (Linux/macOS/Windows, using bash):

```bash
python3 -m pip install -r requirements.txt
python3 -m night_sky.app
```

## v0.2 Features

- **Location selector**: Type city name (e.g., "London") to auto-fill latitude/longitude.
  Data from `data/cities.csv`.
- **Projection modes**: Toggle between Rectangular (Az/Alt grid) and Dome (polar)
  projections via menu or toolbar. Stars and constellations redraw in the new mode.
- **Constellation lines**: Load constellation definitions from `data/constellations_lines.csv`.
  Faint lines connect stars (when both are visible). Toggle on/off via constellation loader.

Data files (v0.2):

- `data/cities.csv`: City locations (name, country, lat, lon)
- `data/constellations_lines.csv`: Constellation line definitions
  (constellation name, star_id_1, star_id_2)

## Smoke test (headless)

To run a quick headless smoke test that verifies imports and basic astronomy logic:

```bash
# from the parent directory of the package (one level up from the `night_sky` folder)
python3 - <<'PY'
import sys
sys.path.insert(0, '.')
from night_sky.data_manager import load_bright_stars
print('stars:', len(load_bright_stars()))
from datetime import datetime, timezone
from night_sky.sky_model import SkyModel
sm = SkyModel()
print('catalog size:', len(sm.stars))
print('snapshot visible:', len(sm.compute_snapshot(0.0, 0.0, datetime.now(timezone.utc))))
PY
```

Run the GUI app (interactive):

```bash
python3 -m night_sky
```

## v0.3 Implementation

v0.3 adds:

- **3D OpenGL dome**: Full hemispherical 3D rendering using pyqtgraph.opengl
- **View switching**: Toggle between 2D and 3D via menu/toolbar (3D only if GPU available)
- **Graceful fallback**: If OpenGL context fails to initialize, app automatically uses 2D
- **Constellation support in 3D**: Faint lines drawn between visible star pairs in 3D mode
- **Unified export**: PNG export works for both 2D and 3D views
- **Earth tab**: Interactive world map for location selection
  - **2D map** (always available): Cylindrical projection with click-to-lat/lon support
  - **3D globe** (if OpenGL available): Textured sphere with click-to-ray-cast location selection
  - **Bidirectional sync**: Selecting location on Earth tab updates Sky view and vice versa

Running the app:

```bash
python3 -m night_sky
```

The main window has two tabs:

- **Sky**: Observe the night sky from your selected location
  - Toggle 2D modes (Rectangular / Dome) or switch to 3D (if available)
  - Adjust date/time and see stars move
- **Earth**: Select your observing location
  - 2D map: Click anywhere to select a location (converts screen coords to lat/lon)
  - 3D globe: Click to ray-cast and select location on the sphere (if OpenGL available)
  - City search is still available in the Location Selector above both tabs

## Data Files

Sample data provided (v0.1–v0.3):

- `data/stars_bright.csv`: 10 bright stars with RA/Dec/magnitude
- `data/cities.csv`: 10 sample cities worldwide
- `data/constellations_lines.csv`: 6 sample constellation line segments

To expand, replace these CSVs with larger catalogs (Yale Bright Star Catalog, etc.).

## v0.4+ Roadmap

Potential future features:

- **Planet support**: Add major planets (Sun, Moon, Mercury–Neptune) with accurate ephemeris positions
- **Improved Earth globe**: Use actual satellite imagery or better procedural textures for land/ocean
- **Improved labels**: Hover-over star/constellation names, adjustable magnitude threshold
- **Larger star catalogs**: Import full Yale BSC or Gaia DR3
- **Performance optimizations**: Culling, level-of-detail rendering for 3D
- **Time-lapse**: Animate sky/Earth position over hours or days

