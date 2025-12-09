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

        # Add a faint grid at the horizon
        grid = GLGridItem()
        grid.scale(2, 2, 1)
        self.glview.addItem(grid)

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
        # Label flags
        self.show_star_labels = False
        self.show_planet_labels = False

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

    def _mag_to_size(self, mag: float) -> float:
        """Map magnitude to marker size (brighter = larger)."""
        size = (6.0 - mag) * 0.5
        return float(np.clip(size, 0.02, 0.3))

    def update_sky(self, stars: list, planets: list = None):
        """Redraw stars and planets from lists of dataclass objects."""
        if planets is None:
            planets = []
            
        # Remove old scatter
        if self.star_scatter is not None:
            self.glview.removeItem(self.star_scatter)
            self.star_scatter = None
        if self.planet_scatter is not None:
            self.glview.removeItem(self.planet_scatter)
            self.planet_scatter = None

        if not stars and not planets:
            self._stars_cache = []
            self._planets_cache = []
            return

        # Filter visible stars (alt > 0)
        visible_stars = [s for s in stars if s.alt_deg > 0.0]
        visible_planets = [p for p in planets if p.alt_deg > 0.0]

        self._stars_cache = visible_stars
        self._planets_cache = visible_planets

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

            # Planets: larger, yellow
            sizes = np.ones(len(visible_planets)) * 0.15
            colors = np.ones((len(visible_planets), 4))
            colors[:, 0] = 1.0   # R: full
            colors[:, 1] = 1.0   # G: full
            colors[:, 2] = 0.0   # B: none (yellow)
            colors[:, 3] = 1.0   # Fully opaque

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

            if self.show_star_labels or self.show_planet_labels:
                # Ensure overlay fills the widget
                self._overlay.setGeometry(self.glview.geometry())
                w = max(10, self._overlay.width())
                h = max(10, self._overlay.height())
                cx = w / 2.0
                cy = h / 2.0
                scale = 0.45 * min(w, h)

                if self.show_star_labels:
                    for s in visible_stars:
                        try:
                            if hasattr(s, 'mag') and s.mag < 2.0:
                                az_rad = np.radians(s.az_deg)
                                r = float(np.clip((90.0 - s.alt_deg) / 90.0, 0.0, 1.0))
                                x = r * np.sin(az_rad)
                                y = r * np.cos(az_rad)
                                px = int(cx + scale * x)
                                py = int(cy - scale * y)
                                # collision avoidance in pixel space
                                min_px = 24
                                placed_ok = False
                                for ox, oy in [(0, 0), (12, 0), (-12, 0), (0, 12), (0, -12), (12, 12)]:
                                    cand_x = px + ox
                                    cand_y = py + oy
                                    ok = True
                                    for (ex, ey) in [(lbl.x(), lbl.y()) for lbl in self._overlay_labels]:
                                        if ((cand_x - ex) ** 2 + (cand_y - ey) ** 2) ** 0.5 < min_px:
                                            ok = False
                                            break
                                    if ok:
                                        lbl = QtWidgets.QLabel(self._overlay)
                                        lbl.setText(s.name)
                                        lbl.setStyleSheet('color: rgb(220,220,255); background: rgba(0,0,0,0);')
                                        lbl.move(cand_x + 6, cand_y - 6)
                                        lbl.show()
                                        self._overlay_labels.append(lbl)
                                        placed_ok = True
                                        break
                                if not placed_ok:
                                    # fallback: place at original pixel
                                    lbl = QtWidgets.QLabel(self._overlay)
                                    lbl.setText(s.name)
                                    lbl.setStyleSheet('color: rgb(220,220,255); background: rgba(0,0,0,0);')
                                    lbl.move(px + 6, py - 6)
                                    lbl.show()
                                    self._overlay_labels.append(lbl)
                        except Exception:
                            continue

                if self.show_planet_labels:
                    for p in visible_planets:
                        try:
                            az_rad = np.radians(p.az_deg)
                            r = float(np.clip((90.0 - p.alt_deg) / 90.0, 0.0, 1.0))
                            x = r * np.sin(az_rad)
                            y = r * np.cos(az_rad)
                            px = int(cx + scale * x)
                            py = int(cy - scale * y)
                            # collision avoidance
                            min_px = 24
                            placed_ok = False
                            for ox, oy in [(0, 0), (12, 0), (-12, 0), (0, 12), (0, -12)]:
                                cand_x = px + ox
                                cand_y = py + oy
                                ok = True
                                for (ex, ey) in [(lbl.x(), lbl.y()) for lbl in self._overlay_labels]:
                                    if ((cand_x - ex) ** 2 + (cand_y - ey) ** 2) ** 0.5 < min_px:
                                        ok = False
                                        break
                                if ok:
                                    lbl = QtWidgets.QLabel(self._overlay)
                                    lbl.setText(p.name)
                                    lbl.setStyleSheet('color: rgb(255,220,80); background: rgba(0,0,0,0);')
                                    lbl.move(cand_x + 6, cand_y - 6)
                                    lbl.show()
                                    self._overlay_labels.append(lbl)
                                    placed_ok = True
                                    break
                            if not placed_ok:
                                lbl = QtWidgets.QLabel(self._overlay)
                                lbl.setText(p.name)
                                lbl.setStyleSheet('color: rgb(255,220,80); background: rgba(0,0,0,0);')
                                lbl.move(px + 6, py - 6)
                                lbl.show()
                                self._overlay_labels.append(lbl)
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
        if (self.show_star_labels or self.show_planet_labels) and self._stars_cache is not None:
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
                            painter.drawText(px + 6, py - 6, p.name)
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
