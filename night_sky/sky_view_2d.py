from PyQt5 import QtWidgets, QtGui, QtCore
import pyqtgraph as pg
import numpy as np
from PyQt5.QtGui import QPixmap, QFontMetrics, QLinearGradient, QColor
from PyQt5.QtCore import Qt


class SkyView2D(QtWidgets.QWidget):
    """2D Alt/Az sky view using pyqtgraph.

    X axis: Azimuth [0,360]
    Y axis: Altitude [0,90]
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.plot = pg.PlotWidget()
        self.plot.setBackground('#05070a')
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
        self._last_dso = []
        # label flags
        self.show_star_labels = False
        self.show_planet_labels = False
        self.limiting_magnitude = 6.0
        self.show_dso = True
        self._placed_labels = []
        self.horizon_items = []
        self.ambient_items = []
        self._label_density_index = 1
        self.show_ra_dec_grid = False
        self.show_alt_az_grid = True
        self.show_ecliptic = False
        self.show_meridian = False
        self.fov_radius_deg: float | None = None
        self._fov_center = None  # (az, alt) center for FOV snap
        self.milky_way_texture_path: str = ''
        self.panorama_image_path: str = ''
        self._milky_way_item = None
        self._panorama_item = None
        self._apply_background()
        self._last_screen_map = {}  # id -> screen QPointF cache
        # storage of label items (pyqtgraph TextItem)
        self._label_items = []

    def _mag_to_size(self, mag: float) -> float:
        # Brighter stars (smaller mag) should be larger.
        # Use a simple linear mapping with clipping.
        size = (6.0 - mag) * 3.5
        return float(np.clip(size, 2.0, 30.0))

    def _apply_background(self):
        """Apply a subtle horizon gradient."""
        grad = QLinearGradient(0, 1, 0, 0)
        grad.setCoordinateMode(QLinearGradient.ObjectBoundingMode)
        grad.setColorAt(0.0, QColor(10, 12, 18))
        grad.setColorAt(0.2, QColor(12, 16, 24))
        grad.setColorAt(1.0, QColor(5, 7, 10))
        try:
            self.plot.setBackground(grad)
        except Exception:
            self.plot.setBackground('#05070a')

    def _load_image_item(self, path: str, rect: QtCore.QRectF, opacity: float = 0.4):
        """Load an image file as a pg.ImageItem scaled into the provided rect."""
        if not path:
            return None
        image = QtGui.QImage(path)
        if image.isNull():
            return None
        try:
            image = image.convertToFormat(QtGui.QImage.Format_RGBA8888)
            ptr = image.bits()
            ptr.setsize(image.byteCount())
            arr = np.frombuffer(ptr, np.uint8).reshape((image.height(), image.width(), 4))
            arr = arr.astype(np.float32) / 255.0
            item = pg.ImageItem(arr)
            item.setRect(rect)
            item.setOpacity(opacity)
            return item
        except Exception:
            return None

    def set_milky_way_texture(self, path: str):
        """Set optional Milky Way texture overlay."""
        self.milky_way_texture_path = path or ''
        if self._last_stars:
            self.update_sky(self._last_stars, self._last_planets, self._last_dso)

    def set_panorama_image(self, path: str):
        """Set optional panorama/landscape near the horizon."""
        self.panorama_image_path = path or ''
        if self._last_stars:
            self.update_sky(self._last_stars, self._last_planets, self._last_dso)

    def update_sky(self, stars: list, planets: list = None, deep_sky: list = None):
        """Redraw the plot from lists of `Star` and `Planet` objects.

        Each `Star` should have attributes: `az_deg`, `alt_deg`, and `mag`, etc.
        Each `Planet` should have attributes: `az_deg`, `alt_deg`, and `name`.
        """
        if planets is None:
            planets = []
        if deep_sky is None:
            deep_sky = []

        # cache last data for toggles
        self._last_stars = list(stars) if stars is not None else []
        self._last_planets = list(planets) if planets is not None else []
        self._last_dso = list(deep_sky) if deep_sky is not None else []
            
        # Clear plot and reconfigure according to projection
        self.plot.clear()
        self.constellation_items = []
        self._star_pos_by_id = {}
        self._placed_labels = []
        # remove horizon items
        for it in self.horizon_items:
            try:
                self.plot.removeItem(it)
            except Exception:
                pass
        self.horizon_items = []
        for it in self.ambient_items:
            try:
                self.plot.removeItem(it)
            except Exception:
                pass
        self.ambient_items = []
        self._milky_way_item = None
        self._panorama_item = None
        self._apply_background()

        if not stars and not planets:
            return

        # Filter visible stars (alt > 0) and mag <= limit
        visible_stars = [s for s in stars if s.alt_deg > 0.0 and getattr(s, 'mag', 99.0) <= self.limiting_magnitude]
        visible_planets = [p for p in planets if p.alt_deg > 0.0]
        visible_dso = [d for d in deep_sky if getattr(d, 'alt_deg', -1) > 0.0] if self.show_dso else []
        self._last_screen_map = {}

        # Project star positions according to mode
        star_spots = []
        planet_spots = []
        
        if self.mode == 'rect':
            # Rectangular Az/Alt: x=az(0..360), y=alt(0..90)
            self._apply_background()
            self.plot.showGrid(x=True, y=True, alpha=0.3)
            self.plot.setLabel('bottom', 'Azimuth', units='deg')
            self.plot.setLabel('left', 'Altitude', units='deg')
            self.plot.setXRange(0, 360)
            self.plot.setYRange(0, 90)
            
            for s in visible_stars:
                x = float(s.az_deg % 360.0)
                y = float(s.alt_deg)
                star_spots.append({'pos': (x, y), 'size': self._mag_to_size(s.mag), 'brush': pg.mkBrush(220, 230, 255), 'pen': None})
                self._star_pos_by_id[s.id] = (x, y)
            
            # Planets: larger, colored markers (yellow)
            for p in visible_planets:
                x = float(p.az_deg % 360.0)
                y = float(p.alt_deg)
                if getattr(p, 'name', '').lower() == 'moon':
                    planet_spots.append({'pos': (x, y), 'size': 16, 'brush': pg.mkBrush(200, 200, 255), 'pen': pg.mkPen((180, 180, 220), width=1)})
                else:
                    planet_spots.append({'pos': (x, y), 'size': 12, 'brush': pg.mkBrush(255, 255, 0), 'pen': pg.mkPen((255, 200, 0), width=1)})
        else:
            # Dome projection: center=zenith, radius=(90-alt)/90, angle=az
            self._apply_background()
            # For dome, use square aspect and hide numeric labels to look like a sky dome
            self.plot.hideAxis('bottom')
            self.plot.hideAxis('left')
            self.plot.setAspectLocked(True)
            self.plot.setXRange(-1.05, 1.05)
            self.plot.setYRange(-1.05, 1.05)
            # horizon circle and compass
            thetas = np.linspace(0, 2 * np.pi, 256)
            xh = np.sin(thetas)
            yh = np.cos(thetas)
            horizon = pg.PlotDataItem(xh, yh, pen=pg.mkPen((80, 100, 130, 160), width=1))
            self.plot.addItem(horizon)
            self.horizon_items.append(horizon)
            # compass labels
            compass = [('N', 0), ('E', 90), ('S', 180), ('W', 270)]
            for label, az in compass:
                az_rad = np.radians(az)
                r = 1.02
                lx = r * np.sin(az_rad)
                ly = r * np.cos(az_rad)
                t = pg.TextItem(text=label, color=(150, 170, 200))
                t.setPos(lx, ly)
                self.plot.addItem(t)
                self.horizon_items.append(t)
            # optional Milky Way texture (full dome) and panorama near the horizon
            milky_rect = QtCore.QRectF(-1.1, -1.1, 2.2, 2.2)
            pano_rect = QtCore.QRectF(-1.1, -1.1, 2.2, 0.55)
            if self.milky_way_texture_path:
                self._milky_way_item = self._load_image_item(self.milky_way_texture_path, milky_rect, opacity=0.42)
                if self._milky_way_item:
                    self.plot.addItem(self._milky_way_item)
                    self.ambient_items.append(self._milky_way_item)
            if self.panorama_image_path:
                self._panorama_item = self._load_image_item(self.panorama_image_path, pano_rect, opacity=0.8)
                if self._panorama_item:
                    self.plot.addItem(self._panorama_item)
                    self.ambient_items.append(self._panorama_item)
            
            for s in visible_stars:
                az_rad = np.radians(s.az_deg)
                r = float(np.clip((90.0 - s.alt_deg) / 90.0, 0.0, 1.0))
                x = r * np.sin(az_rad)
                y = r * np.cos(az_rad)
                star_spots.append({'pos': (x, y), 'size': self._mag_to_size(s.mag), 'brush': pg.mkBrush(220, 230, 255), 'pen': None})
                self._star_pos_by_id[s.id] = (x, y)
            
            # Planets in dome projection
            for p in visible_planets:
                az_rad = np.radians(p.az_deg)
                r = float(np.clip((90.0 - p.alt_deg) / 90.0, 0.0, 1.0))
                x = r * np.sin(az_rad)
                y = r * np.cos(az_rad)
                if getattr(p, 'name', '').lower() == 'moon':
                    planet_spots.append({'pos': (x, y), 'size': 16, 'brush': pg.mkBrush(200, 200, 255), 'pen': pg.mkPen((180, 180, 220), width=1)})
                else:
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

        # Build label candidates and place them using greedy bounding-box avoidance
        candidates = []
        # planets/Moon: highest priority (0)
        if self.show_planet_labels:
            for p in visible_planets:
                if self.mode == 'rect':
                    x = float(p.az_deg % 360.0)
                    y = float(p.alt_deg)
                else:
                    az_rad = np.radians(p.az_deg)
                    r = float(np.clip((90.0 - p.alt_deg) / 90.0, 0.0, 1.0))
                    x = r * np.sin(az_rad)
                    y = r * np.cos(az_rad)
                label = p.name
                if getattr(p, 'name', '').lower() == 'moon' and getattr(p, 'phase_fraction', None) is not None:
                    label = f"{p.name} ({int(p.phase_fraction*100)}%)"
                candidates.append({'id': getattr(p, 'name', None), 'x': x, 'y': y, 'text': label, 'priority': 0})

        # stars: bright stars next (priority 1), optionally include others with lower priority
        if self.show_star_labels:
            max_star_labels = [5, 15, 40][self._label_density_index if hasattr(self, '_label_density_index') else 1]
            bright = []
            for s in visible_stars:
                try:
                    mag = getattr(s, 'mag', 99.0)
                    if mag < min(self.limiting_magnitude, 6.0):
                        pos = self._star_pos_by_id.get(s.id)
                        if pos is None:
                            continue
                        priority = 1 if mag < 2.0 else 2
                        bright.append({'id': s.id, 'x': pos[0], 'y': pos[1], 'text': s.name, 'priority': priority, 'mag': mag})
                except Exception:
                    continue
            bright.sort(key=lambda c: c.get('mag', 99.0))
            candidates.extend(bright[:max_star_labels])
        # Deep sky objects (low priority)
        if self.show_dso:
            max_dso_labels = [0, 5, 15][self._label_density_index if hasattr(self, '_label_density_index') else 1]
            for d in visible_dso[:max_dso_labels]:
                try:
                    if self.mode == 'rect':
                        x = float(d.az_deg % 360.0)
                        y = float(d.alt_deg)
                    else:
                        az_rad = np.radians(d.az_deg)
                        r = float(np.clip((90.0 - d.alt_deg) / 90.0, 0.0, 1.0))
                        x = r * np.sin(az_rad)
                        y = r * np.cos(az_rad)
                    candidates.append({'id': d.name, 'x': x, 'y': y, 'text': d.name, 'priority': 3, 'mag': 10.0})
                except Exception:
                    continue

        # Occupied rects start empty; we could seed with star/planet marker boxes if desired
        occupied = []

        def _font_metrics():
            return QFontMetrics(QtWidgets.QApplication.font())

        def _estimate_label_rect(xc, yc, text, offset_x=0.0, offset_y=0.0):
            # Estimate label size in data coordinates using font metrics and plot view range
            fm = _font_metrics()
            pixel_w = fm.horizontalAdvance(text)
            pixel_h = fm.height()
            # view ranges
            try:
                vr = self.plot.getViewBox().viewRange()
                x_min, x_max = vr[0][0], vr[0][1]
                y_min, y_max = vr[1][0], vr[1][1]
            except Exception:
                # fallback ranges used earlier
                if self.mode == 'rect':
                    x_min, x_max = 0.0, 360.0
                    y_min, y_max = 0.0, 90.0
                else:
                    x_min, x_max = -1.05, 1.05
                    y_min, y_max = -1.05, 1.05
            data_w = x_max - x_min
            data_h = y_max - y_min
            widget_w = max(1, self.plot.width())
            widget_h = max(1, self.plot.height())
            scale_x = data_w / widget_w
            scale_y = data_h / widget_h
            lab_w = pixel_w * scale_x
            lab_h = pixel_h * scale_y
            # Anchor label top-left at (xc + offset_x, yc + offset_y)
            left = xc + offset_x
            top = yc + offset_y
            right = left + lab_w
            bottom = top + lab_h
            # normalize rect so top < bottom
            if top > bottom:
                top, bottom = bottom, top
            if left > right:
                left, right = right, left
            return (left, top, right, bottom)

        def _rects_intersect(a, b):
            # rect: (l,t,r,b)
            return not (a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3])

        def _place_labels_greedy(candidates_list):
            placed_labels = []
            # sort by priority (low number = higher priority) and optional magnitude for stars
            candidates_list.sort(key=lambda c: (c.get('priority', 10), c.get('mag', 0)))
            # offsets in data units
            if self.mode == 'rect':
                dx = 2.0
                dy = 1.2
            else:
                dx = 0.04
                dy = 0.03
            offsets = [(0, dy), (dx, 0), (-dx, 0), (dx, dy), (-dx, dy), (0, -dy), (dx, -dy), (-dx, -dy), (0, 0)]

            for c in candidates_list:
                base_x = c['x']
                base_y = c['y']
                placed = False
                for offx, offy in offsets:
                    rect = _estimate_label_rect(base_x, base_y, c['text'], offset_x=offx, offset_y=offy)
                    collision = False
                    for occ in occupied:
                        if _rects_intersect(rect, occ):
                            collision = True
                            break
                    if not collision:
                        occupied.append(rect)
                        placed_labels.append({'x': rect[0], 'y': rect[1], 'text': c['text'], 'src': c})
                        placed = True
                        break
                # If not placed and low priority (e.g., priority >=2), skip
                if not placed and c.get('priority', 10) <= 1:
                    # try to force at base location even if overlapping for high priority
                    rect = _estimate_label_rect(base_x, base_y, c['text'], offset_x=0.0, offset_y=0.0)
                    occupied.append(rect)
                    placed_labels.append({'x': rect[0], 'y': rect[1], 'text': c['text'], 'src': c})
            return placed_labels

        placed = _place_labels_greedy(candidates)
        self._placed_labels = placed
        # Create TextItems for placed labels
        for pl in placed:
            try:
                txt = pg.TextItem(text=pl['text'], color=(255, 220, 220), anchor=(0, 0))
                txt.setFont(QtWidgets.QApplication.font())
                txt.setPos(pl['x'], pl['y'])
                self.plot.addItem(txt)
                self._label_items.append(txt)
            except Exception:
                continue
        # If constellation segments are present, draw them
        if self.constellation_segments:
            self.update_constellations(self.constellation_segments)
        # Grids and overlays
        self._draw_overlays()

    def export_png(self, path, width: int = 2000, height: int = 2000):
        """Export the current widget view to a PNG at the requested resolution."""
        # Grab the plot widget as a pixmap and scale to desired size
        # Use devicePixelRatio scaling for HiDPI if available
        pm: QPixmap = self.plot.grab()
        # scale while keeping aspect ratio stable
        pm = pm.scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        # composite labels if we have placed positions
        if self._placed_labels:
            painter = QtGui.QPainter(pm)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            painter.setPen(QtGui.QColor(220, 220, 255))
            painter.setFont(QtWidgets.QApplication.font())
            # Derive scaling between current view range and export size
            try:
                vr = self.plot.getViewBox().viewRange()
                x_min, x_max = vr[0][0], vr[0][1]
                y_min, y_max = vr[1][0], vr[1][1]
            except Exception:
                x_min, x_max = 0.0, 360.0
                y_min, y_max = 0.0, 90.0
            data_w = x_max - x_min
            data_h = y_max - y_min
            for pl in self._placed_labels:
                dx = (pl['x'] - x_min) / data_w if data_w else 0
                dy = (pl['y'] - y_min) / data_h if data_h else 0
                px = int(dx * pm.width())
                py = int((1 - dy) * pm.height())
                if pl['src'].get('priority', 10) == 0:
                    painter.setPen(QtGui.QColor(255, 220, 80))
                elif pl['src'].get('priority', 10) == 3:
                    painter.setPen(QtGui.QColor(120, 180, 255))
                else:
                    painter.setPen(QtGui.QColor(220, 220, 255))
                painter.drawText(px, py, pl['text'])
            painter.end()
        # add simple export markers
        painter = QtGui.QPainter(pm)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtGui.QColor(180, 180, 200))
        painter.drawText(10, 20, "N")
        painter.drawText(pm.width() - 20, pm.height() // 2, "E")
        # scale bar
        painter.drawLine(10, pm.height() - 20, 110, pm.height() - 20)
        painter.drawText(10, pm.height() - 25, "Scale")
        painter.end()
        pm.save(str(path), 'PNG')

    def pick_object(self, scene_pos, tol_px: int = 10):
        """Return nearest object info at scene_pos within tolerance in pixels."""
        vb = self.plot.getViewBox()
        if vb is None:
            return None
        try:
            data_pos = vb.mapSceneToView(scene_pos)
        except Exception:
            return None
        x = data_pos.x()
        y = data_pos.y()
        best = None
        best_dist = tol_px
        # Build screen positions if not cached
        if not self._last_screen_map and self._last_stars:
            for s in self._last_stars:
                pos = self._star_pos_by_id.get(s.id)
                if pos is None:
                    continue
                sp = vb.mapViewToScene(pg.Point(pos[0], pos[1]))
                self._last_screen_map[s.id] = sp
        # stars
        for s in self._last_stars:
            sp = self._star_pos_by_id.get(s.id)
            if sp is None:
                continue
            scene_pt = self._last_screen_map.get(s.id)
            if scene_pt is None:
                scene_pt = vb.mapViewToScene(pg.Point(sp[0], sp[1]))
            dx = scene_pos.x() - scene_pt.x()
            dy = scene_pos.y() - scene_pt.y()
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best = ('star', s)
        # planets
        for p in self._last_planets:
            if p.alt_deg <= 0:
                continue
            if self.mode == 'rect':
                vx = float(p.az_deg % 360.0)
                vy = float(p.alt_deg)
            else:
                az_rad = np.radians(p.az_deg)
                r = float(np.clip((90.0 - p.alt_deg) / 90.0, 0.0, 1.0))
                vx = r * np.sin(az_rad)
                vy = r * np.cos(az_rad)
            scene_pt = vb.mapViewToScene(pg.Point(vx, vy))
            dx = scene_pos.x() - scene_pt.x()
            dy = scene_pos.y() - scene_pt.y()
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best = ('planet', p)
        # dso
        for d in self._last_dso:
            if getattr(d, 'alt_deg', -1) <= 0 or not self.show_dso:
                continue
            if self.mode == 'rect':
                vx = float(d.az_deg % 360.0)
                vy = float(d.alt_deg)
            else:
                az_rad = np.radians(d.az_deg)
                r = float(np.clip((90.0 - d.alt_deg) / 90.0, 0.0, 1.0))
                vx = r * np.sin(az_rad)
                vy = r * np.cos(az_rad)
            scene_pt = vb.mapViewToScene(pg.Point(vx, vy))
            dx = scene_pos.x() - scene_pt.x()
            dy = scene_pos.y() - scene_pt.y()
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best = ('dso', d)
        return best

    def _draw_overlays(self):
        """Draw grids, ecliptic/meridian, and FOV circle if enabled."""
        if self.mode != 'rect':
            return
        # Alt/Az grid
        if self.show_alt_az_grid:
            pen = pg.mkPen((70, 90, 120, 120))
            for az in range(0, 361, 30):
                x = [az, az]
                y = [0, 90]
                self.plot.addItem(pg.PlotDataItem(x, y, pen=pen))
            for alt in range(10, 90, 10):
                x = [0, 360]
                y = [alt, alt]
                self.plot.addItem(pg.PlotDataItem(x, y, pen=pen))
        # RA/Dec grid (approx by treating az as RA proxy for visualization)
        if self.show_ra_dec_grid:
            pen = pg.mkPen((100, 120, 160, 100))
            for ra in range(0, 361, 30):
                self.plot.addItem(pg.PlotDataItem([ra, ra], [0, 90], pen=pen))
            for dec in range(10, 90, 20):
                self.plot.addItem(pg.PlotDataItem([0, 360], [dec, dec], pen=pen))
        # Meridian line (Az=180)
        if self.show_meridian:
            pen = pg.mkPen((200, 120, 120, 150), width=2)
            self.plot.addItem(pg.PlotDataItem([180, 180], [0, 90], pen=pen))
        # Ecliptic (simple sinusoid placeholder)
        if self.show_ecliptic:
            az = np.linspace(0, 360, 200)
            alt = 30 * np.sin(np.radians(az))
            pen = pg.mkPen((200, 200, 120, 140), width=2)
            self.plot.addItem(pg.PlotDataItem(az, alt, pen=pen))
        # FOV circle
        if self.fov_radius_deg is not None:
            pen = pg.mkPen((120, 200, 200, 180), width=2, style=Qt.DashLine)
            # center at selected target (defaults to zenith proxy)
            if self._fov_center:
                az_center, alt_center = self._fov_center
            else:
                alt_center = 45.0
                az_center = 180.0
            az = np.linspace(0, 360, 200)
            x = (az_center + self.fov_radius_deg * np.sin(np.radians(az))) % 360
            y = alt_center + self.fov_radius_deg * np.cos(np.radians(az))
            self.plot.addItem(pg.PlotDataItem(x, y, pen=pen))

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

    def set_label_density(self, idx: int):
        """Set label density tier (0,1,2)."""
        self._label_density_index = max(0, min(int(idx), 2))
        if self._last_stars or self._last_planets:
            self.update_sky(self._last_stars, self._last_planets, self._last_dso)

    def set_overlays(self, ra_dec: bool, alt_az: bool, ecliptic: bool, meridian: bool):
        """Configure grid/line overlays."""
        self.show_ra_dec_grid = bool(ra_dec)
        self.show_alt_az_grid = bool(alt_az)
        self.show_ecliptic = bool(ecliptic)
        self.show_meridian = bool(meridian)
        if self._last_stars or self._last_planets:
            self.update_sky(self._last_stars, self._last_planets, self._last_dso)

    def set_fov_radius(self, radius_deg: float | None):
        """Set FOV radius overlay (deg). None disables."""
        self.fov_radius_deg = radius_deg
        if self._last_stars or self._last_planets:
            self.update_sky(self._last_stars, self._last_planets, self._last_dso)

    def set_fov_center(self, az_deg: float, alt_deg: float):
        """Set the FOV overlay center (Az/Alt)."""
        self._fov_center = (az_deg, alt_deg)
        if self._last_stars or self._last_planets:
            self.update_sky(self._last_stars, self._last_planets, self._last_dso)

    def clear_fov_center(self):
        self._fov_center = None

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
