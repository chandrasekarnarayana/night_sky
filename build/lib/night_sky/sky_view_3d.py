"""3D sky dome visualization using pyqtgraph.opengl (v0.3).

Provides a SkyView3D widget that renders visible stars on a hemisphere
and draws constellation lines. This module is only imported when
opengl_utils.opengl_available() returns True.
"""

import numpy as np
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt

OPENGL_AVAILABLE = False

try:
    import pyqtgraph.opengl as gl
    from pyqtgraph.opengl import GLViewWidget, GLLinePlotItem, GLScatterPlotItem, GLGridItem
    OPENGL_AVAILABLE = True
except ImportError:
    pass


class SkyView3D(QtWidgets.QWidget):
    """3D hemispherical sky dome viewer using OpenGL.

    Renders visible stars and constellation lines on a unit hemisphere.
    Camera is positioned to look at the origin from above the dome.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        if not OPENGL_AVAILABLE:
            raise RuntimeError("OpenGL not available; cannot create SkyView3D")

        self.glview = GLViewWidget()
        self.glview.opts['distance'] = 2.0
        self.glview.setCameraPosition(distance=2.0, elevation=30, azimuth=-90)
        self.glview.setBackgroundColor((5, 7, 10, 255))

        # Add a faint grid at the horizon
        grid = GLGridItem()
        grid.scale(2, 2, 1)
        self.glview.addItem(grid)
        # Horizon ring
        try:
            theta = np.linspace(0, 2 * np.pi, 200)
            pts = np.column_stack([np.sin(theta), np.cos(theta), np.zeros_like(theta)])
            self.horizon_ring = GLLinePlotItem(pos=pts, color=(0.4, 0.5, 0.65, 0.5), width=1, antialias=True, mode='line_strip')
            self.glview.addItem(self.horizon_ring)
        except Exception:
            self.horizon_ring = None

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(self.glview)
        self.setLayout(layout)

        # Current star and planet scatter plots and constellation lines
        self.star_scatter = None
        self.planet_scatter = None
        self.constellation_lines = []
        self._stars_cache = []
        self._planets_cache = []
        self._dso_cache = []
        # Label flags
        self.show_star_labels = False
        self.show_planet_labels = False
        self.show_dso = True
        self.horizon_ring = None
        self._label_density_index = 1
        self.show_ra_dec_grid = False
        self.show_ecliptic = False
        self.show_meridian = False

        # Overlay widget for 2D labels (transparent)
        self._overlay = QtWidgets.QWidget(self)
        self._overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._overlay.setAttribute(Qt.WA_NoSystemBackground)
        self._overlay.setStyleSheet('background: transparent;')
        self._overlay.raise_()
        self._overlay_labels = []

    def _altaz_to_xyz(self, alt_deg: np.ndarray, az_deg: np.ndarray) -> tuple:
        """Convert Alt/Az (deg) to 3D Cartesian on unit hemisphere.

        Zenith = (0, 0, 1), Horizon = z=0.
        Azimuth 0 = North (+y), 90 = East (+x), 180 = South (-y), 270 = West (-x).
        """
        alt_rad = np.radians(alt_deg)
        az_rad = np.radians(az_deg)

        # Spherical coords: r=1, theta=az, phi=(90-alt)
        r = np.cos(alt_rad)
        z = np.sin(alt_rad)
        x = r * np.sin(az_rad)
        y = r * np.cos(az_rad)
        return x, y, z

    def _compute_screen_coords_for_altaz(self, alt_deg: float, az_deg: float, width: int, height: int):
        """Map a single Alt/Az point to overlay pixel coordinates.

        Uses the same dome projection as the 2D dome view: radial distance r=(90-alt)/90,
        then maps to pixel coordinates centered in the overlay with a scale factor.
        Returns (px, py) as integers.
        """
        az_rad = np.radians(az_deg)
        r = float(np.clip((90.0 - alt_deg) / 90.0, 0.0, 1.0))
        x = r * np.sin(az_rad)
        y = r * np.cos(az_rad)
        cx = width / 2.0
        cy = height / 2.0
        scale = 0.45 * min(width, height)
        px = int(cx + scale * x)
        py = int(cy - scale * y)
        return px, py

    def _place_labels_greedy_pixels(self, candidates, width, height, font: QtGui.QFont):
        """Place labels (pixel coords) using a greedy bounding-box avoidance.

        candidates: list of dicts with keys: 'id','px','py','text','priority'
        Returns list of placed dicts with keys 'x','y','text','src' where x,y are
        the top-left pixel coordinates to place the QLabel / drawText.
        """
        fm = QtGui.QFontMetrics(font)
        def _rect_for_text(cand_x, cand_y, text, offx=0, offy=0):
            left = cand_x + 6 + offx
            top = cand_y - 6 + offy
            w = fm.horizontalAdvance(text)
            h = fm.height()
            return (left, top, left + w, top + h)

        def _intersect(a, b):
            return not (a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3])

        placed = []
        occupied = []
        # sort by priority then (for stars) magnitude if provided
        candidates.sort(key=lambda c: (c.get('priority', 10), c.get('mag', 0)))

        offsets = [(0, 0), (12, 0), (-12, 0), (0, 12), (0, -12), (12, 12), (-12, 12), (12, -12), (-12, -12)]
        for c in candidates:
            cand_x = int(c['px'])
            cand_y = int(c['py'])
            text = c['text']
            placed_ok = False
            for offx, offy in offsets:
                rect = _rect_for_text(cand_x, cand_y, text, offx, offy)
                # skip if out of bounds
                if rect[0] < 0 or rect[1] < 0 or rect[2] > width or rect[3] > height:
                    continue
                collision = False
                for occ in occupied:
                    if _intersect(rect, occ):
                        collision = True
                        break
                if not collision:
                    occupied.append(rect)
                    placed.append({'x': rect[0], 'y': rect[1], 'text': text, 'src': c})
                    placed_ok = True
                    break
            # if not placed and high priority, force at base position
            if not placed_ok and c.get('priority', 10) <= 1:
                rect = _rect_for_text(cand_x, cand_y, text, 0, 0)
                occupied.append(rect)
                placed.append({'x': rect[0], 'y': rect[1], 'text': text, 'src': c})

        return placed

    def _mag_to_size(self, mag: float) -> float:
        """Map magnitude to marker size (brighter = larger)."""
        size = (6.0 - mag) * 0.5
        return float(np.clip(size, 0.02, 0.3))

    def update_sky(self, stars: list, planets: list = None, deep_sky: list = None):
        """Redraw stars and planets from lists of dataclass objects."""
        if planets is None:
            planets = []
        if deep_sky is None:
            deep_sky = []
            
        # Remove old scatter
        if self.star_scatter is not None:
            self.glview.removeItem(self.star_scatter)
            self.star_scatter = None
        if self.planet_scatter is not None:
            self.glview.removeItem(self.planet_scatter)
            self.planet_scatter = None

        if not stars and not planets and not deep_sky:
            self._stars_cache = []
            self._planets_cache = []
            self._dso_cache = []
            return

        # Filter visible stars (alt > 0)
        visible_stars = [s for s in stars if s.alt_deg > 0.0]
        visible_planets = [p for p in planets if p.alt_deg > 0.0]
        visible_dso = [d for d in deep_sky if getattr(d, 'alt_deg', -1) > 0.0] if self.show_dso else []

        self._stars_cache = visible_stars
        self._planets_cache = visible_planets
        self._dso_cache = visible_dso

        # Render stars
        if visible_stars:
            # Convert to 3D
            alt = np.array([s.alt_deg for s in visible_stars], dtype=float)
            az = np.array([s.az_deg for s in visible_stars], dtype=float)
            mag = np.array([s.mag for s in visible_stars], dtype=float)

            x, y, z = self._altaz_to_xyz(alt, az)
            pos = np.column_stack([x, y, z])

            # Map magnitude to size and color
            sizes = np.array([self._mag_to_size(m) for m in mag])
            colors = np.ones((len(visible_stars), 4))
            colors[:, :3] = 1.0  # White
            colors[:, 3] = 1.0   # Fully opaque

            # Create and add scatter
            self.star_scatter = GLScatterPlotItem(
                pos=pos,
                size=sizes,
                color=colors,
                pxMode=False
            )
            self.glview.addItem(self.star_scatter)
        
        # Render planets
        if visible_planets:
            # Convert to 3D
            alt = np.array([p.alt_deg for p in visible_planets], dtype=float)
            az = np.array([p.az_deg for p in visible_planets], dtype=float)

            x, y, z = self._altaz_to_xyz(alt, az)
            pos = np.column_stack([x, y, z])

            # Planets: larger, yellow; Moon slightly larger and bluish
            sizes = np.ones(len(visible_planets)) * 0.15
            colors = np.ones((len(visible_planets), 4))
            colors[:, 0] = 1.0   # R: full
            colors[:, 1] = 1.0   # G: full
            colors[:, 2] = 0.0   # B: none (yellow)
            colors[:, 3] = 1.0   # Fully opaque
            for idx, p in enumerate(visible_planets):
                if getattr(p, 'name', '').lower() == 'moon':
                    sizes[idx] = 0.2
                    colors[idx] = (0.8, 0.8, 1.0, 1.0)

            # Create and add scatter
            self.planet_scatter = GLScatterPlotItem(
                pos=pos,
                size=sizes,
                color=colors,
                pxMode=False
            )
            self.glview.addItem(self.planet_scatter)

        # Update overlay labels (use dome-like projection onto overlay)
        try:
            # Clear existing overlay labels
            for lab in self._overlay_labels:
                try:
                    lab.setParent(None)
                except Exception:
                    pass
            self._overlay_labels = []
            self._overlay_label_positions = []

            if self.show_star_labels or self.show_planet_labels:
                # Ensure overlay fills the widget
                self._overlay.setGeometry(self.glview.geometry())
                w = max(10, self._overlay.width())
                h = max(10, self._overlay.height())

                # Build candidates in pixel coords
                candidates = []
                if self.show_star_labels:
                    max_star_labels = [5, 15, 40][self._label_density_index if hasattr(self, '_label_density_index') else 1]
                    bright = []
                    for s in visible_stars:
                        try:
                            if hasattr(s, 'mag') and s.mag < 6.0:
                                px, py = self._compute_screen_coords_for_altaz(s.alt_deg, s.az_deg, w, h)
                                priority = 1 if s.mag < 2.0 else 2
                                bright.append({'id': s.id, 'px': px, 'py': py, 'text': s.name, 'priority': priority, 'mag': s.mag})
                        except Exception:
                            continue
                    bright.sort(key=lambda c: c.get('mag', 99.0))
                    candidates.extend(bright[:max_star_labels])
                if self.show_planet_labels:
                    for p in visible_planets:
                        try:
                            px, py = self._compute_screen_coords_for_altaz(p.alt_deg, p.az_deg, w, h)
                            text = p.name
                            if getattr(p, 'name', '').lower() == 'moon' and getattr(p, 'phase_fraction', None) is not None:
                                text = f"{p.name} ({int(p.phase_fraction*100)}%)"
                            candidates.append({'id': getattr(p, 'name', None), 'px': px, 'py': py, 'text': text, 'priority': 0})
                        except Exception:
                            continue
                if self.show_dso:
                    max_dso_labels = [0, 5, 15][self._label_density_index if hasattr(self, '_label_density_index') else 1]
                    for d in visible_dso[:max_dso_labels]:
                        try:
                            px, py = self._compute_screen_coords_for_altaz(d.alt_deg, d.az_deg, w, h)
                            candidates.append({'id': d.name, 'px': px, 'py': py, 'text': d.name, 'priority': 3})
                        except Exception:
                            continue
                # Compass labels at horizon (low priority but always placed)
                compass = [('N', 0), ('E', 90), ('S', 180), ('W', 270)]
                for lbl, az in compass:
                    px, py = self._compute_screen_coords_for_altaz(0.0, az, w, h)
                    candidates.append({'id': f'compass_{lbl}', 'px': px, 'py': py, 'text': lbl, 'priority': 4})

                # Font used both for overlay QLabel sizing and export consistency
                font = QtGui.QFont()
                font.setPointSize(max(8, int(min(w, h) / 200)))

                placed = self._place_labels_greedy_pixels(candidates, w, h, font)

                # Create QLabel overlays and record positions for export
                for pl in placed:
                    try:
                        lbl = QtWidgets.QLabel(self._overlay)
                        lbl.setText(pl['text'])
                        # color planets differently if source indicates priority 0
                        if pl['src'].get('priority', 10) == 0:
                            lbl.setStyleSheet('color: rgb(255,220,80); background: rgba(0,0,0,0);')
                        elif pl['src'].get('priority', 10) == 3:
                            lbl.setStyleSheet('color: rgb(120,180,255); background: rgba(0,0,0,0);')
                        else:
                            lbl.setStyleSheet('color: rgb(220,220,255); background: rgba(0,0,0,0);')
                        lbl.setFont(font)
                        lbl.move(int(pl['x']), int(pl['y']))
                        lbl.show()
                        self._overlay_labels.append(lbl)
                        # Save exact draw positions for export (top-left)
                        self._overlay_label_positions.append({'x': int(pl['x']), 'y': int(pl['y']), 'text': pl['text'], 'priority': pl['src'].get('priority', 10)})
                    except Exception:
                        continue
        except Exception:
            # Non-critical: overlay labels are best-effort
            pass

    def update_constellations(self, segments: list):
        """Draw constellation lines between visible star pairs.

        `segments` is a list of (star1, star2) tuples.
        """
        # Remove old constellation lines
        for line in self.constellation_lines:
            try:
                self.glview.removeItem(line)
            except Exception:
                pass
        self.constellation_lines = []

        if not self._stars_cache or not segments:
            return

        # Build star position map
        star_pos = {}
        for s in self._stars_cache:
            x, y, z = self._altaz_to_xyz(np.array([s.alt_deg]), np.array([s.az_deg]))
            star_pos[s.id] = np.array([x[0], y[0], z[0]])

        # Draw lines for available segments
        for s1, s2 in segments:
            p1 = star_pos.get(s1.id)
            p2 = star_pos.get(s2.id)
            if p1 is None or p2 is None:
                continue

            # Create a line connecting the two stars
            pts = np.array([p1, p2])
            line = GLLinePlotItem(
                pos=pts,
                color=(0.7, 0.7, 1.0, 0.3),  # Faint blue
                width=1,
                antialias=True
            )
            self.glview.addItem(line)
            self.constellation_lines.append(line)

    def export_png(self, path, width: int = 2000, height: int = 2000):
        """Export the current 3D view to a high-resolution PNG.

        Renders the GLViewWidget to an image at the requested size.
        """
        # Resize the widget temporarily for high-res rendering
        old_size = self.glview.size()
        self.glview.resize(width, height)

        # Grab the framebuffer
        pm = self.glview.grabFramebuffer()

        # Restore size
        self.glview.resize(old_size)

        # Composite labels onto pixmap if enabled
        if (self.show_star_labels or self.show_planet_labels or self.show_dso) and self._stars_cache is not None:
            try:
                painter = QtGui.QPainter(pm)
                painter.setRenderHint(QtGui.QPainter.Antialiasing)
                w = pm.width()
                h = pm.height()
                cx = w / 2.0
                cy = h / 2.0
                scale = 0.45 * min(w, h)
                font = QtGui.QFont()
                font.setPointSize(max(8, int(min(w, h) / 200)))
                painter.setFont(font)

                # If we have cached overlay positions (from update_sky), use them to
                # draw text so exports match on-screen overlay.
                if getattr(self, '_overlay_label_positions', None):
                    for lbl in self._overlay_label_positions:
                        try:
                            if lbl.get('priority', 10) == 0:
                                painter.setPen(QtGui.QColor(255, 220, 80))
                            elif lbl.get('priority', 10) == 3:
                                painter.setPen(QtGui.QColor(120, 180, 255))
                            else:
                                painter.setPen(QtGui.QColor(220, 220, 255))
                            painter.drawText(int(lbl['x']), int(lbl['y']), lbl['text'])
                        except Exception:
                            continue
                else:
                    # Fallback: approximate positions directly from alt/az
                    if self.show_star_labels:
                        painter.setPen(QtGui.QColor(220, 220, 255))
                        for s in self._stars_cache:
                            try:
                                if hasattr(s, 'mag') and s.mag < 2.0:
                                    az_rad = np.radians(s.az_deg)
                                    r = float(np.clip((90.0 - s.alt_deg) / 90.0, 0.0, 1.0))
                                    x = r * np.sin(az_rad)
                                    y = r * np.cos(az_rad)
                                    px = int(cx + scale * x)
                                    py = int(cy - scale * y)
                                    painter.drawText(px + 6, py - 6, s.name)
                            except Exception:
                                continue

                    if self.show_planet_labels:
                        painter.setPen(QtGui.QColor(255, 220, 80))
                        for p in self._planets_cache:
                            try:
                                az_rad = np.radians(p.az_deg)
                                r = float(np.clip((90.0 - p.alt_deg) / 90.0, 0.0, 1.0))
                                x = r * np.sin(az_rad)
                                y = r * np.cos(az_rad)
                                px = int(cx + scale * x)
                                py = int(cy - scale * y)
                                label = p.name
                                if getattr(p, 'name', '').lower() == 'moon' and getattr(p, 'phase_fraction', None) is not None:
                                    label = f"{p.name} ({int(p.phase_fraction*100)}%)"
                                painter.drawText(px + 6, py - 6, label)
                            except Exception:
                                continue

                painter.end()
            except Exception:
                pass

        # Save
        pm.save(str(path), 'PNG')

    def set_show_star_labels(self, flag: bool):
        self.show_star_labels = bool(flag)
        # Trigger label overlay update if we have data cached
        if self._stars_cache or self._planets_cache:
            self.update_sky(self._stars_cache, self._planets_cache)

    def set_show_planet_labels(self, flag: bool):
        self.show_planet_labels = bool(flag)
        if self._stars_cache or self._planets_cache:
            self.update_sky(self._stars_cache, self._planets_cache)

    def set_label_density(self, idx: int):
        self._label_density_index = max(0, min(int(idx), 2))
        if self._stars_cache or self._planets_cache:
            self.update_sky(self._stars_cache, self._planets_cache, self._dso_cache)

    def set_overlays(self, ra_dec: bool, alt_az: bool, ecliptic: bool, meridian: bool):
        self.show_ra_dec_grid = bool(ra_dec)
        self.show_ecliptic = bool(ecliptic)
        self.show_meridian = bool(meridian)
        # TODO: draw grid lines in 3D (placeholder)
    def resizeEvent(self, event: QtGui.QResizeEvent):
        # Ensure overlay geometry and recompute label placement on resize
        try:
            super().resizeEvent(event)
        except Exception:
            pass
        try:
            self._overlay.setGeometry(self.glview.geometry())
            if getattr(self, '_stars_cache', None) or getattr(self, '_planets_cache', None):
                # Recompute placements using cached data
                self.update_sky(self._stars_cache, self._planets_cache)
        except Exception:
            pass

    def pick_object(self, screen_pos, tol_px: int = 12):
        """Picking using projected Alt/Az -> overlay pixel coordinates.

        Looks at stars, planets, and DSOs and returns nearest within tolerance.
        """
        w = max(10, self._overlay.width())
        h = max(10, self._overlay.height())
        best = None
        best_dist = tol_px

        def check(px, py, kind, obj):
            nonlocal best, best_dist
            dx = screen_pos.x() - px
            dy = screen_pos.y() - py
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best = (kind, obj)

        # Stars
        for s in self._stars_cache:
            px, py = self._compute_screen_coords_for_altaz(s.alt_deg, s.az_deg, w, h)
            check(px, py, 'star', s)
        # Planets
        for p in self._planets_cache:
            px, py = self._compute_screen_coords_for_altaz(p.alt_deg, p.az_deg, w, h)
            kind = 'moon' if getattr(p, 'name', '').lower() == 'moon' else 'planet'
            check(px, py, kind, p)
        # Deep sky
        for d in self._dso_cache:
            px, py = self._compute_screen_coords_for_altaz(d.alt_deg, d.az_deg, w, h)
            check(px, py, 'dso', d)
        return best
