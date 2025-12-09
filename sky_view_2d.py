from PyQt5 import QtWidgets
import pyqtgraph as pg
import numpy as np
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt


class SkyView2D(QtWidgets.QWidget):
    """2D Alt/Az sky view using pyqtgraph.

    X axis: Azimuth [0,360]
    Y axis: Altitude [0,90]
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.plot = pg.PlotWidget()
        self.plot.setBackground('k')
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.plot.setLabel('bottom', 'Azimuth', units='deg')
        self.plot.setLabel('left', 'Altitude', units='deg')
        self.plot.setXRange(0, 360)
        self.plot.setYRange(0, 90)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(self.plot)
        self.setLayout(layout)

        self.star_scatter = pg.ScatterPlotItem()
        self.planet_scatter = pg.ScatterPlotItem()
        self.plot.addItem(self.star_scatter)
        self.plot.addItem(self.planet_scatter)
        # projection mode: 'rect' (Az/Alt) or 'dome' (polar dome projection)
        self.mode = 'rect'
        # stored constellation segments (list of (Star, Star))
        self.constellation_segments = []
        self.constellation_items = []
        # mapping star id -> plotted (x,y) coordinates in current projection
        self._star_pos_by_id = {}
        # caching last data for redraws and label toggles
        self._last_stars = []
        self._last_planets = []
        # label flags
        self.show_star_labels = False
        self.show_planet_labels = False
        # storage of label items (pyqtgraph TextItem)
        self._label_items = []

    def _mag_to_size(self, mag: float) -> float:
        # Brighter stars (smaller mag) should be larger.
        # Use a simple linear mapping with clipping.
        size = (6.0 - mag) * 3.5
        return float(np.clip(size, 2.0, 30.0))

    def update_sky(self, stars: list, planets: list = None):
        """Redraw the plot from lists of `Star` and `Planet` objects.

        Each `Star` should have attributes: `az_deg`, `alt_deg`, and `mag`, etc.
        Each `Planet` should have attributes: `az_deg`, `alt_deg`, and `name`.
        """
        if planets is None:
            planets = []

        # cache last data for toggles
        self._last_stars = list(stars) if stars is not None else []
        self._last_planets = list(planets) if planets is not None else []
            
        # Clear plot and reconfigure according to projection
        self.plot.clear()
        self.constellation_items = []
        self._star_pos_by_id = {}

        if not stars and not planets:
            return

        # Filter visible stars (alt > 0)
        visible_stars = [s for s in stars if s.alt_deg > 0.0]
        visible_planets = [p for p in planets if p.alt_deg > 0.0]

        # Project star positions according to mode
        star_spots = []
        planet_spots = []
        
        if self.mode == 'rect':
            # Rectangular Az/Alt: x=az(0..360), y=alt(0..90)
            self.plot.setBackground('k')
            self.plot.showGrid(x=True, y=True, alpha=0.3)
            self.plot.setLabel('bottom', 'Azimuth', units='deg')
            self.plot.setLabel('left', 'Altitude', units='deg')
            self.plot.setXRange(0, 360)
            self.plot.setYRange(0, 90)
            
            for s in visible_stars:
                x = float(s.az_deg % 360.0)
                y = float(s.alt_deg)
                star_spots.append({'pos': (x, y), 'size': self._mag_to_size(s.mag), 'brush': pg.mkBrush(255, 255, 255), 'pen': None})
                self._star_pos_by_id[s.id] = (x, y)
            
            # Planets: larger, colored markers (yellow)
            for p in visible_planets:
                x = float(p.az_deg % 360.0)
                y = float(p.alt_deg)
                planet_spots.append({'pos': (x, y), 'size': 12, 'brush': pg.mkBrush(255, 255, 0), 'pen': pg.mkPen((255, 200, 0), width=1)})
        else:
            # Dome projection: center=zenith, radius=(90-alt)/90, angle=az
            self.plot.setBackground('k')
            # For dome, use square aspect and hide numeric labels to look like a sky dome
            self.plot.hideAxis('bottom')
            self.plot.hideAxis('left')
            self.plot.setAspectLocked(True)
            self.plot.setXRange(-1.05, 1.05)
            self.plot.setYRange(-1.05, 1.05)
            
            for s in visible_stars:
                az_rad = np.radians(s.az_deg)
                r = float(np.clip((90.0 - s.alt_deg) / 90.0, 0.0, 1.0))
                x = r * np.sin(az_rad)
                y = r * np.cos(az_rad)
                star_spots.append({'pos': (x, y), 'size': self._mag_to_size(s.mag), 'brush': pg.mkBrush(255, 255, 255), 'pen': None})
                self._star_pos_by_id[s.id] = (x, y)
            
            # Planets in dome projection
            for p in visible_planets:
                az_rad = np.radians(p.az_deg)
                r = float(np.clip((90.0 - p.alt_deg) / 90.0, 0.0, 1.0))
                x = r * np.sin(az_rad)
                y = r * np.cos(az_rad)
                planet_spots.append({'pos': (x, y), 'size': 12, 'brush': pg.mkBrush(255, 255, 0), 'pen': pg.mkPen((255, 200, 0), width=1)})

        # Add star scatter
        if star_spots:
            self.star_scatter = pg.ScatterPlotItem()
            self.star_scatter.addPoints(star_spots)
            self.plot.addItem(self.star_scatter)
        
        # Add planet scatter
        if planet_spots:
            self.planet_scatter = pg.ScatterPlotItem()
            self.planet_scatter.addPoints(planet_spots)
            self.plot.addItem(self.planet_scatter)

        # Clear existing labels
        for it in self._label_items:
            try:
                self.plot.removeItem(it)
            except Exception:
                pass
        self._label_items = []

        # Draw labels if enabled
        placed = []  # list of placed label positions in data coords
        def _is_far(px, py, placed_list, min_dist):
            for (ox, oy) in placed_list:
                if ((px - ox) ** 2 + (py - oy) ** 2) ** 0.5 < min_dist:
                    return False
            return True

        if self.show_star_labels:
            # Label bright stars (mag < 2) with simple collision avoidance
            if self.mode == 'rect':
                min_dist = 2.0  # degrees
                offsets = [(0, 0), (1.0, 0), (-1.0, 0), (0, 1.0), (0, -1.0), (1.0, 1.0), (-1.0, -1.0)]
            else:
                min_dist = 0.03  # dome normalized units
                offsets = [(0, 0), (0.02, 0), (-0.02, 0), (0, 0.02), (0, -0.02), (0.02, 0.02)]

            for s in visible_stars:
                try:
                    if hasattr(s, 'mag') and s.mag < 2.0:
                        pos = self._star_pos_by_id.get(s.id)
                        if pos is None:
                            continue
                        base_x, base_y = pos[0], pos[1]
                        placed_pos = None
                        for dx, dy in offsets:
                            cand_x = base_x + dx
                            cand_y = base_y + dy
                            if _is_far(cand_x, cand_y, placed, min_dist):
                                placed_pos = (cand_x, cand_y)
                                placed.append(placed_pos)
                                break
                        if placed_pos is None:
                            # fallback: use base pos
                            placed_pos = (base_x, base_y)
                            placed.append(placed_pos)

                        txt = pg.TextItem(text=s.name, color=(220, 220, 255), anchor=(0, 0))
                        txt.setFont(QtWidgets.QApplication.font())
                        txt.setPos(placed_pos[0], placed_pos[1])
                        self.plot.addItem(txt)
                        self._label_items.append(txt)
                except Exception:
                    continue

        if self.show_planet_labels:
            # Use same collision avoidance strategy as for stars
            for p in visible_planets:
                try:
                    if self.mode == 'rect':
                        base_x = float(p.az_deg % 360.0)
                        base_y = float(p.alt_deg)
                        min_dist = 2.0
                        offsets = [(0, 0), (1.5, 0), (-1.5, 0), (0, 1.5), (0, -1.5), (1.5, 1.5)]
                    else:
                        az_rad = np.radians(p.az_deg)
                        r = float(np.clip((90.0 - p.alt_deg) / 90.0, 0.0, 1.0))
                        base_x = r * np.sin(az_rad)
                        base_y = r * np.cos(az_rad)
                        min_dist = 0.04
                        offsets = [(0, 0), (0.03, 0), (-0.03, 0), (0, 0.03), (0, -0.03)]

                    placed_pos = None
                    for dx, dy in offsets:
                        cand_x = base_x + dx
                        cand_y = base_y + dy
                        if _is_far(cand_x, cand_y, placed, min_dist):
                            placed_pos = (cand_x, cand_y)
                            placed.append(placed_pos)
                            break
                    if placed_pos is None:
                        placed_pos = (base_x, base_y)
                        placed.append(placed_pos)

                    txt = pg.TextItem(text=p.name, color=(255, 220, 80), anchor=(0, 0))
                    txt.setFont(QtWidgets.QApplication.font())
                    txt.setPos(placed_pos[0], placed_pos[1])
                    self.plot.addItem(txt)
                    self._label_items.append(txt)
                except Exception:
                    continue
        # If constellation segments are present, draw them
        if self.constellation_segments:
            self.update_constellations(self.constellation_segments)

    def export_png(self, path, width: int = 2000, height: int = 2000):
        """Export the current widget view to a PNG at the requested resolution."""
        # Grab the plot widget as a pixmap and scale to desired size
        # Use devicePixelRatio scaling for HiDPI if available
        pm: QPixmap = self.plot.grab()
        # scale while keeping aspect ratio
        pm = pm.scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        pm.save(str(path), 'PNG')

    def set_show_star_labels(self, flag: bool):
        """Enable/disable star labels (bright stars only)."""
        self.show_star_labels = bool(flag)
        # redraw if we have cached data
        if self._last_stars or self._last_planets:
            self.update_sky(self._last_stars, self._last_planets)

    def set_show_planet_labels(self, flag: bool):
        """Enable/disable planet labels (all visible planets)."""
        self.show_planet_labels = bool(flag)
        if self._last_stars or self._last_planets:
            self.update_sky(self._last_stars, self._last_planets)

    def set_projection_mode(self, mode: str):
        """Set projection mode: 'rect' or 'dome' and redraw current sky.

        This method will update `self.mode` and trigger a redraw by
        calling `update_sky` with the last known stars (if any).
        """
        if mode not in ('rect', 'dome'):
            raise ValueError("mode must be 'rect' or 'dome'")
        self.mode = mode
        # Note: caller should call `update_sky` after switching to provide star list.

    def update_constellations(self, segments: list):
        """Draw faint lines between star pairs provided as segments.

        `segments` is a list of tuples `(star1, star2)` where each star has an `id`.
        Only segments where both star ids are present in the current projection
        will be drawn.
        """
        # store segments for redraws
        self.constellation_segments = segments
        # remove existing items
        for it in self.constellation_items:
            try:
                self.plot.removeItem(it)
            except Exception:
                pass
        self.constellation_items = []

        pen = pg.mkPen((180, 180, 255, 120), width=1)
        for s1, s2 in segments:
            p1 = self._star_pos_by_id.get(s1.id)
            p2 = self._star_pos_by_id.get(s2.id)
            if p1 is None or p2 is None:
                continue
            x = [p1[0], p2[0]]
            y = [p1[1], p2[1]]
            line = pg.PlotDataItem(x, y, pen=pen)
            self.plot.addItem(line)
            self.constellation_items.append(line)

