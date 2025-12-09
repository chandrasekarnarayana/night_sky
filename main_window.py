from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QLabel, QLineEdit, QPushButton, QHBoxLayout, QVBoxLayout, QWidget, QDateTimeEdit, QFileDialog, QTabWidget, QInputDialog
from datetime import datetime, timezone

from .sky_model import SkyModel
from .sky_view_2d import SkyView2D
from .earth_view_2d import EarthView2D
from .export import export_view_to_png
from .settings import DEFAULTS
from .location_selector import LocationSelector
from .constellations import load_constellation_lines, build_constellation_segments
from .opengl_utils import explain_failure, opengl_available
from .prefs import load_prefs, save_prefs

# Try to import 3D views (only available if OpenGL is present)
HAS_3D = opengl_available()
HAS_3D_EARTH = False

# Import 3D view classes only if OpenGL is available to avoid import-time errors
if HAS_3D:
    try:
        from .sky_view_3d import SkyView3D
    except Exception:
        HAS_3D = False

try:
    from .earth_view_3d import EarthView3D, OPENGL_AVAILABLE as EARTH_3D_AVAILABLE
    if EARTH_3D_AVAILABLE:
        HAS_3D_EARTH = True
except Exception:
    HAS_3D_EARTH = False


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Night Sky Viewer (v0.2)')
        self.resize(900, 700)

        self.sky_model = SkyModel()
        
        # Load constellation lines at startup (may be empty if file missing)
        self.constellation_lines = []
        try:
            self.constellation_lines = load_constellation_lines()
        except FileNotFoundError:
            pass  # No constellation file yet
        
        self.current_lat = 0.0
        self.current_lon = 0.0
        self.current_stars = []  # Cache for projection mode switching
        self.current_planets = []  # Cache for projection mode switching

        # Try to create 3D view; fall back to 2D-only if OpenGL unavailable
        self.sky_view_3d = None
        self.sky_view = SkyView2D()
        self.current_view = '2d'  # Track which view is active ('2d' or '3d')

        if HAS_3D:
            try:
                self.sky_view_3d = SkyView3D()
            except Exception:
                # 3D creation failed; use 2D only
                QtWidgets.QMessageBox.warning(
                    self, 'OpenGL Error',
                    'Failed to initialize 3D view. Using 2D mode.\n\n' + explain_failure()
                )
        
        # Create Earth views (2D always available, 3D only if OpenGL available)
        self.earth_view_2d = EarthView2D()
        self.earth_view_3d = None
        
        if HAS_3D_EARTH:
            try:
                self.earth_view_3d = EarthView3D()
            except Exception:
                # 3D Earth creation failed; use 2D only
                pass
        
        # Load cities into Earth views
        cities = []
        try:
            from .data_manager import load_cities
            cities = load_cities()
        except Exception:
            pass
        self.earth_view_2d.add_cities(cities)
        
        # Connect Earth view signals
        self.earth_view_2d.location_changed.connect(self._on_earth_location_changed)
        if self.earth_view_3d:
            self.earth_view_3d.location_changed.connect(self._on_earth_location_changed)

        # Location selector widget
        self.location_selector = LocationSelector()

        # Use UTC for datetime edit (v0.2 uses UTC assumption)
        self.datetime_edit = QDateTimeEdit(QtCore.QDateTime.currentDateTimeUtc())
        self.datetime_edit.setCalendarPopup(True)
        self.now_btn = QPushButton('Now (UTC)')
        self.update_btn = QPushButton('Update Sky')

        # Label toggles: stars (bright only) and planets
        prefs = load_prefs()
        self.star_label_chk = QtWidgets.QCheckBox('Show star labels (mag < 2)')
        self.star_label_chk.setChecked(bool(prefs.get('show_star_labels', True)))
        self.planet_label_chk = QtWidgets.QCheckBox('Show planet labels')
        self.planet_label_chk.setChecked(bool(prefs.get('show_planet_labels', True)))

        self.export_btn = QPushButton('Export PNG')

        controls = QWidget()
        h = QHBoxLayout()
        h.addWidget(self.datetime_edit)
        h.addWidget(self.now_btn)
        h.addWidget(self.update_btn)
        h.addWidget(self.star_label_chk)
        h.addWidget(self.planet_label_chk)
        h.addWidget(self.export_btn)
        controls.setLayout(h)

        # Sky view container (swappable between 2D and 3D)
        self.view_container = QWidget()
        self.view_layout = QVBoxLayout()
        self.view_layout.setContentsMargins(0, 0, 0, 0)
        self.view_layout.addWidget(self.sky_view)
        self.view_container.setLayout(self.view_layout)
        
        # Tabs for Sky and Earth
        self.tabs = QTabWidget()
        self.tabs.addTab(self.view_container, "Sky")
        
        # Earth tab container (swappable between 2D and 3D Earth)
        self.earth_tab_container = QWidget()
        self.earth_tab_layout = QVBoxLayout()
        self.earth_tab_layout.setContentsMargins(0, 0, 0, 0)
        self.earth_tab_layout.addWidget(self.earth_view_2d)
        self.earth_tab_container.setLayout(self.earth_tab_layout)
        self.current_earth_view = '2d'  # Track which Earth view is active
        
        self.tabs.addTab(self.earth_tab_container, "Earth")

        # Menu and toolbar
        self._create_actions()
        self._create_menu_toolbar()

        central = QWidget()
        v = QVBoxLayout()
        v.addWidget(self.location_selector)
        v.addWidget(controls)
        v.addWidget(self.tabs)
        central.setLayout(v)
        self.setCentralWidget(central)

        # Connections
        self.now_btn.clicked.connect(self.set_now)
        self.update_btn.clicked.connect(self.update_sky)
        self.export_btn.clicked.connect(self.export_png)
        self.location_selector.location_changed.connect(self._on_location_changed)
        # Label toggle connections
        self.star_label_chk.toggled.connect(self._on_star_label_toggled)
        self.planet_label_chk.toggled.connect(self._on_planet_label_toggled)

        # initial render
        self.update_sky()
        # Apply initial label settings to views
        self._on_star_label_toggled(self.star_label_chk.isChecked())
        self._on_planet_label_toggled(self.planet_label_chk.isChecked())

    def _on_star_label_toggled(self, checked: bool):
        """Toggle star labels in the active view(s)."""
        self.show_star_labels = bool(checked)
        # Apply to both 2D and 3D views if present
        try:
            if hasattr(self, 'sky_view') and self.sky_view is not None:
                self.sky_view.set_show_star_labels(self.show_star_labels)
        except Exception:
            pass
        try:
            if hasattr(self, 'sky_view_3d') and self.sky_view_3d is not None:
                self.sky_view_3d.set_show_star_labels(self.show_star_labels)
        except Exception:
            pass
        # keep menu/toolbar actions in sync
        try:
            if hasattr(self, 'action_show_star_labels'):
                self.action_show_star_labels.setChecked(self.show_star_labels)
        except Exception:
            pass
        # persist preference
        try:
            prefs = load_prefs()
            prefs['show_star_labels'] = self.show_star_labels
            save_prefs(prefs)
        except Exception:
            pass

    def _on_planet_label_toggled(self, checked: bool):
        """Toggle planet labels in the active view(s)."""
        self.show_planet_labels = bool(checked)
        try:
            if hasattr(self, 'sky_view') and self.sky_view is not None:
                self.sky_view.set_show_planet_labels(self.show_planet_labels)
        except Exception:
            pass
        try:
            if hasattr(self, 'sky_view_3d') and self.sky_view_3d is not None:
                self.sky_view_3d.set_show_planet_labels(self.show_planet_labels)
        except Exception:
            pass
        # keep menu/toolbar actions in sync
        try:
            if hasattr(self, 'action_show_planet_labels'):
                self.action_show_planet_labels.setChecked(self.show_planet_labels)
        except Exception:
            pass
        # persist
        try:
            prefs = load_prefs()
            prefs['show_planet_labels'] = self.show_planet_labels
            save_prefs(prefs)
        except Exception:
            pass

    def _on_constellation_toggled(self, checked: bool):
        """Toggle drawing of constellation lines in the active view(s)."""
        try:
            if checked and self.constellation_lines and self.current_stars:
                star_map = {s.id: s for s in self.current_stars}
                segments = build_constellation_segments(star_map, self.constellation_lines)
                if self.current_view == '3d' and self.sky_view_3d:
                    self.sky_view_3d.update_constellations(segments)
                else:
                    self.sky_view.update_constellations(segments)
            else:
                # Clear constellation lines
                if self.current_view == '3d' and self.sky_view_3d:
                    self.sky_view_3d.update_constellations([])
                else:
                    self.sky_view.update_constellations([])
        except Exception:
            pass
        # sync menu action -> checkbox if exists
        try:
            if hasattr(self, 'action_show_constellations'):
                self.action_show_constellations.setChecked(checked)
        except Exception:
            pass
        # persist
        try:
            prefs = load_prefs()
            prefs['show_constellations'] = bool(checked)
            save_prefs(prefs)
        except Exception:
            pass

    def closeEvent(self, event):
        """Persist preferences on application close and continue closing."""
        try:
            prefs = load_prefs()
            # Prefer QAction state if available, otherwise fall back to checkboxes
            prefs['show_star_labels'] = bool(getattr(self, 'action_show_star_labels', None) and self.action_show_star_labels.isChecked()) if hasattr(self, 'action_show_star_labels') else bool(self.star_label_chk.isChecked())
            prefs['show_planet_labels'] = bool(getattr(self, 'action_show_planet_labels', None) and self.action_show_planet_labels.isChecked()) if hasattr(self, 'action_show_planet_labels') else bool(self.planet_label_chk.isChecked())
            prefs['show_constellations'] = bool(getattr(self, 'action_show_constellations', None) and self.action_show_constellations.isChecked()) if hasattr(self, 'action_show_constellations') else prefs.get('show_constellations', True)
            save_prefs(prefs)
        except Exception:
            pass
        super().closeEvent(event)

    def _create_actions(self):
        self.action_update = QtWidgets.QAction('Update Sky', self)
        self.action_update.triggered.connect(self.update_sky)

        self.action_export = QtWidgets.QAction('Export PNG...', self)
        self.action_export.triggered.connect(self.export_png)
        
        self.action_proj_rect = QtWidgets.QAction('Rectangular (Az/Alt)', self, checkable=True)
        self.action_proj_rect.setChecked(True)
        self.action_proj_rect.triggered.connect(lambda: self._set_projection('rect'))
        
        self.action_proj_dome = QtWidgets.QAction('Dome (Polar)', self, checkable=True)
        self.action_proj_dome.triggered.connect(lambda: self._set_projection('dome'))
        
        # Group projection actions
        proj_group = QtWidgets.QActionGroup(self)
        proj_group.addAction(self.action_proj_rect)
        proj_group.addAction(self.action_proj_dome)
        
        # 3D view toggle (only available if OpenGL is supported)
        self.action_view_2d = QtWidgets.QAction('2D View', self, checkable=True)
        self.action_view_2d.setChecked(True)
        self.action_view_2d.triggered.connect(lambda: self._switch_view('2d'))
        
        self.action_view_3d = QtWidgets.QAction('3D View', self, checkable=True, enabled=HAS_3D)
        self.action_view_3d.triggered.connect(lambda: self._switch_view('3d'))
        
        view_group = QtWidgets.QActionGroup(self)
        view_group.addAction(self.action_view_2d)
        view_group.addAction(self.action_view_3d)
        
        # Earth view toggle (only available if OpenGL is supported)
        self.action_earth_2d = QtWidgets.QAction('2D Map', self, checkable=True)
        self.action_earth_2d.setChecked(True)
        self.action_earth_2d.triggered.connect(lambda: self._switch_earth_view('2d'))
        
        self.action_earth_3d = QtWidgets.QAction('3D Globe', self, checkable=True, enabled=HAS_3D_EARTH)
        self.action_earth_3d.triggered.connect(lambda: self._switch_earth_view('3d'))
        
        earth_group = QtWidgets.QActionGroup(self)
        earth_group.addAction(self.action_earth_2d)
        earth_group.addAction(self.action_earth_3d)

        # Label and overlay actions
        self.action_show_star_labels = QtWidgets.QAction('Show Star Labels', self, checkable=True)
        self.action_show_star_labels.setChecked(self.star_label_chk.isChecked())
        self.action_show_star_labels.toggled.connect(self._on_star_label_toggled)
        # keep checkboxes in sync
        self.action_show_star_labels.toggled.connect(self.star_label_chk.setChecked)
        self.star_label_chk.toggled.connect(self.action_show_star_labels.setChecked)

        self.action_show_planet_labels = QtWidgets.QAction('Show Planet Labels', self, checkable=True)
        self.action_show_planet_labels.setChecked(self.planet_label_chk.isChecked())
        self.action_show_planet_labels.toggled.connect(self._on_planet_label_toggled)
        self.action_show_planet_labels.toggled.connect(self.planet_label_chk.setChecked)
        self.planet_label_chk.toggled.connect(self.action_show_planet_labels.setChecked)

        self.action_show_constellations = QtWidgets.QAction('Show Constellation Lines', self, checkable=True)
        # default: show if we have constellation lines
        self.action_show_constellations.setChecked(bool(self.constellation_lines))
        self.action_show_constellations.toggled.connect(self._on_constellation_toggled)
        # sync with checkbox (none currently exists in control bar) - leave for future

    def _create_menu_toolbar(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu('File')
        file_menu.addAction(self.action_export)

        sky_menu = menubar.addMenu('Sky')
        sky_menu.addAction(self.action_update)
        sky_menu.addSeparator()
        sky_menu.addAction(self.action_view_2d)
        sky_menu.addAction(self.action_view_3d)
        sky_menu.addSeparator()
        sky_menu.addAction(self.action_show_star_labels)
        sky_menu.addAction(self.action_show_planet_labels)
        sky_menu.addAction(self.action_show_constellations)
        sky_menu.addSeparator()
        sky_menu.addAction(self.action_proj_rect)
        sky_menu.addAction(self.action_proj_dome)
        
        earth_menu = menubar.addMenu('Earth')
        earth_menu.addAction(self.action_earth_2d)
        earth_menu.addAction(self.action_earth_3d)

        toolbar = self.addToolBar('Main')
        toolbar.addAction(self.action_update)
        toolbar.addAction(self.action_export)
        toolbar.addSeparator()
        toolbar.addAction(self.action_view_2d)
        toolbar.addAction(self.action_view_3d)
        toolbar.addSeparator()
        toolbar.addAction(self.action_show_star_labels)
        toolbar.addAction(self.action_show_planet_labels)
        toolbar.addAction(self.action_show_constellations)
        toolbar.addSeparator()
        toolbar.addAction(self.action_proj_rect)
        toolbar.addAction(self.action_proj_dome)

    def set_now(self):
        # Set to current UTC time
        self.datetime_edit.setDateTime(QtCore.QDateTime.currentDateTimeUtc())

    def _on_location_changed(self, lat: float, lon: float):
        """Called when location selector emits a new location."""
        self.current_lat = lat
        self.current_lon = lon
        # Update Earth view markers
        self.earth_view_2d.set_marker(lat, lon)
        if self.earth_view_3d:
            self.earth_view_3d.set_marker(lat, lon)
        # Trigger sky update with the new location
        self.update_sky()
    
    def _on_earth_location_changed(self, lat: float, lon: float):
        """Called when Earth view emits a location change."""
        self.current_lat = lat
        self.current_lon = lon
        # Update location selector (will trigger _on_location_changed if needed)
        self.location_selector._update_lat_lon_fields(lat, lon)
        # Trigger sky update
        self.update_sky()

    def _set_projection(self, mode: str):
        """Switch to 'rect' or 'dome' projection and redraw."""
        self.sky_view.set_projection_mode(mode)
        # Redraw with cached stars and planets in the new projection
        if self.current_stars:
            self.sky_view.update_sky(self.current_stars, self.current_planets)
            # Reapply constellations if present
            if self.constellation_lines and self.current_stars:
                star_map = {s.id: s for s in self.current_stars}
                segments = build_constellation_segments(star_map, self.constellation_lines)
                self.sky_view.update_constellations(segments)

    def update_sky(self):
        lat = self.current_lat
        lon = self.current_lon

        qdt = self.datetime_edit.dateTime().toPyDateTime()
        # Treat the QDateTime as UTC: make timezone-aware UTC
        try:
            when = qdt.replace(tzinfo=timezone.utc)
        except Exception:
            when = qdt

        snapshot = self.sky_model.compute_snapshot(lat, lon, when)
        self.current_stars = snapshot.visible_stars  # Cache for projection switching
        self.current_planets = snapshot.visible_planets  # Cache for projection switching
        
        # Pass the stars and planets to the active view
        if self.current_view == '3d' and self.sky_view_3d:
            self.sky_view_3d.update_sky(snapshot.visible_stars, snapshot.visible_planets)
            # Compute and draw constellation segments if available
            if self.constellation_lines and snapshot.visible_stars:
                star_map = {s.id: s for s in snapshot.visible_stars}
                segments = build_constellation_segments(star_map, self.constellation_lines)
                self.sky_view_3d.update_constellations(segments)
        else:
            # 2D view
            self.sky_view.update_sky(snapshot.visible_stars, snapshot.visible_planets)
            # Compute and draw constellation segments if available
            if self.constellation_lines and snapshot.visible_stars:
                star_map = {s.id: s for s in snapshot.visible_stars}
                segments = build_constellation_segments(star_map, self.constellation_lines)
                self.sky_view.update_constellations(segments)

    def export_png(self):
        fileName, _ = QFileDialog.getSaveFileName(self, 'Export PNG', '', 'PNG Files (*.png)')
        if not fileName:
            return
        # Ask for export size (px), default to prefs or DEFAULTS
        try:
            prefs = load_prefs()
        except Exception:
            prefs = {}
        default_size = int(prefs.get('export_default_size', DEFAULTS.get('export_default_size', 2000)))
        size, ok = QInputDialog.getInt(self, 'Export size', 'PNG size (px):', value=default_size, min=100, max=10000, step=100)
        if not ok:
            return

        # Persist chosen size
        try:
            prefs['export_default_size'] = int(size)
            save_prefs(prefs)
        except Exception:
            pass

        # Delegate to the active view's exporter
        try:
            if self.current_view == '3d' and self.sky_view_3d:
                export_view_to_png(self.sky_view_3d, fileName, size=size)
            else:
                export_view_to_png(self.sky_view, fileName, size=size)
            QtWidgets.QMessageBox.information(self, 'Export', f'Wrote {fileName}')
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Export failed', str(e))

    def _switch_view(self, mode: str):
        """Switch between 2D and 3D views."""
        if mode == '3d' and not self.sky_view_3d:
            QtWidgets.QMessageBox.warning(self, 'OpenGL Error',
                'OpenGL 3D view is not available.\n\n' + explain_failure())
            self.action_view_2d.setChecked(True)
            return

        self.current_view = mode
        # Clear the view container
        while self.view_layout.count():
            self.view_layout.takeAt(0).widget().hide()

        # Add the appropriate view
        if mode == '3d':
            self.view_layout.addWidget(self.sky_view_3d)
            self.sky_view_3d.show()
        else:
            self.view_layout.addWidget(self.sky_view)
            self.sky_view.show()

        # Redraw current stars in the new view
        if self.current_stars:
            self.update_sky()
    
    def _switch_earth_view(self, mode: str):
        """Switch between 2D and 3D Earth views."""
        if mode == '3d' and not self.earth_view_3d:
            QtWidgets.QMessageBox.warning(self, 'OpenGL Error',
                'OpenGL 3D Earth view is not available.')
            self.action_earth_2d.setChecked(True)
            return

        self.current_earth_view = mode
        # Clear the Earth tab container
        while self.earth_tab_layout.count():
            self.earth_tab_layout.takeAt(0).widget().hide()

        # Add the appropriate view
        if mode == '3d':
            self.earth_tab_layout.addWidget(self.earth_view_3d.view)
            self.earth_view_3d.view.show()
        else:
            self.earth_tab_layout.addWidget(self.earth_view_2d)
            self.earth_view_2d.show()
        
        # Set marker at current location
        self.earth_view_2d.set_marker(self.current_lat, self.current_lon)
        if self.earth_view_3d:
            self.earth_view_3d.set_marker(self.current_lat, self.current_lon)
