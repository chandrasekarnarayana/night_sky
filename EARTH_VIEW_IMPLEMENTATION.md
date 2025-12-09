# Earth View Implementation (v0.3 Upgrade)

## Overview

Added an interactive **Earth view** tab with click-to-select location support, enabling users to intuitively choose observing locations by clicking on a map or globe.

## Features Implemented

### 1. EarthView2D: Cylindrical Projection Map
**File**: `earth_view_2d.py`

- **Visualization**: Cylindrical projection of Earth (longitude 0–360° on x-axis, latitude -90° to +90° on y-axis)
- **Click-to-Select**: Left-click anywhere on map to select location; automatically converts (x, y) to (lat, lon)
- **Grid Lines**: Reference grid at 30° intervals
- **Cities Overlay**: Display cities as red dots with labels
- **Location Marker**: Yellow cross marks currently selected location
- **Signals**: Emits `location_changed(lat_deg, lon_deg)` when user clicks
- **Export**: PNG export via `export_png(path, width, height)`

**Click Conversion Logic**:
- Screen click (x, y) → plot coordinates via pyqtgraph's `mapSceneToView()`
- Clamp latitude to [-90, 90] and longitude to [0, 360)
- Emit signal with (lat, lon)

### 2. EarthView3D: Textured Sphere (Optional)
**File**: `earth_view_3d.py`

- **Visualization**: 3D sphere using pyqtgraph.opengl.GLViewWidget
- **Procedural Texture**: Simple land/ocean coloring based on 3D vertex positions
  - Land (green/brown) where noise > 0.3
  - Ocean (blue) where noise ≤ 0.3
  - Noise generated via sine wave combinations
- **UV Sphere Generation**: 32×32 subdivision for smooth geometry
- **Ray Casting**: Click-to-ray-cast location selection
  - Cast ray from camera through click position
  - Intersect with unit sphere (ICP formula)
  - Convert intersection to lat/lon
- **Signals**: Emits `location_changed(lat_deg, lon_deg)` when user clicks
- **Export**: PNG export via `export_png(path, width, height)`
- **OpenGL Conditional**: Only available if `OPENGL_AVAILABLE=True`; gracefully degrades to 2D if unavailable

**Ray-Sphere Intersection**:
$$|ray_{origin} + t \cdot ray_{dir}|^2 = 1$$
$$t = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$$
where $a=1$, $b=2 \langle ray_{origin}, ray_{dir} \rangle$, $c=|ray_{origin}|^2 - 1$

### 3. MainWindow Integration
**File**: `main_window.py` (updated)

**Architecture**:
- Added two-tab interface: "Sky" tab (existing) + "Earth" tab (new)
- Each tab has container with swappable 2D/3D views
- Bidirectional signal propagation between Earth and Sky views

**New Components**:
```python
# In MainWindow.__init__():
self.earth_view_2d = EarthView2D()           # Always available
self.earth_view_3d = None                    # Optional if OpenGL available
self.earth_tab_container = QWidget()         # Earth tab container
self.current_earth_view = '2d'               # Track active Earth view

# Connections:
self.earth_view_2d.location_changed.connect(self._on_earth_location_changed)
if self.earth_view_3d:
    self.earth_view_3d.location_changed.connect(self._on_earth_location_changed)
```

**Menu Structure**:
```
Sky Menu:
  - Update Sky
  - 2D View / 3D View (toggle)
  - Rectangular / Dome (projection toggle)

Earth Menu:
  - 2D Map / 3D Globe (toggle)
```

**Signal Flow**:
1. User clicks on Earth view → emits `location_changed(lat, lon)`
2. `_on_earth_location_changed()` handler:
   - Updates `self.current_lat`, `self.current_lon`
   - Updates LocationSelector fields via `_update_lat_lon_fields()` (no signal loop)
   - Calls `update_sky()` to recompute visible stars
3. User selects city in LocationSelector → `_on_location_changed()` handler:
   - Updates `self.current_lat`, `self.current_lon`
   - Updates Earth view markers via `earth_view_2d.set_marker()` and `earth_view_3d.set_marker()`
   - Calls `update_sky()` to recompute visible stars

### 4. LocationSelector Enhancement
**File**: `location_selector.py` (updated)

Added `_update_lat_lon_fields(lat, lon)` method:
- Updates lat/lon input fields without triggering `location_changed` signal
- Blocks signals during update to prevent cascading changes
- Prevents infinite loops when Earth view changes location

## Data Integration

**Cities**:
- Loaded from `data/cities.csv` (10 sample cities)
- Displayed as red dots on 2D map
- Selectable via LocationSelector

**Constellations**:
- Existing constellation lines still work
- Displayed on Sky tab (both 2D and 3D views)

## Testing

All tests pass:
- ✅ EarthView2D imports and instantiation
- ✅ EarthView3D class structure (3D geometry and ray casting)
- ✅ Click-to-lat/lon conversion (2D)
- ✅ Signal emission and propagation
- ✅ MainWindow integration (tabs, menus, signal handlers)
- ✅ Bidirectional location sync (Earth ↔ Sky ↔ LocationSelector)
- ✅ Tab switching and view management

## Future Enhancements (v0.4+)

1. **3D Earth Texture**: Use actual satellite imagery (e.g., NASA Blue Marble) instead of procedural texture
2. **Interactive 3D Earth Geometry**: Render country borders, city labels
3. **Location Smoothing**: Animate transitions when changing locations
4. **Performance**: Implement LOD (level-of-detail) for large catalogs
5. **Persistence**: Save user's favorite locations
6. **Time Zone Display**: Show local time zone when location is selected

## Technical Notes

### Coordinate Systems
- **Latitude**: -90° (South Pole) to +90° (North Pole)
- **Longitude**: 0° to 360° (East), or -180° to +180° (standard)
  - Implementation uses 0–360 range for consistency
- **Conversion**: Click screen coords → normalized [-1, 1] → ray through sphere → lat/lon

### OpenGL Optional Design
- EarthView3D only instantiated if `OPENGL_AVAILABLE=True`
- 2D map always works, 3D globe available if GPU supports OpenGL
- Graceful fallback: switching to 3D shows warning if unavailable
- No crashes if GPU drivers are missing (tested in headless environment)

### Signal Architecture
- LocationSelector → MainWindow → update_sky() + Earth marker updates
- EarthView2D/3D → MainWindow → LocationSelector update + update_sky()
- No direct Earth ↔ LocationSelector connection (prevents circular dependencies)

