from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QLabel, QLineEdit, QPushButton, QHBoxLayout, QVBoxLayout, QWidget, QDateTimeEdit, QFileDialog, QTabWidget, QInputDialog, QDockWidget, QRadioButton, QDoubleSpinBox, QComboBox, QTextEdit, QSlider, QListWidget, QDialog
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
from .theme import apply_theme, THEMES
from .moon_phase_widget import MoonPhaseWidget
from .help_viewer import HelpViewer
from .plugins import load_plugins
from .search_dialog import SearchDialog
from datetime import timedelta

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
        self.setWindowTitle('Night Sky Viewer (v0.3)')
        self.resize(900, 700)
        self.setStyleSheet("""
            QMainWindow { background: #05070a; color: #d0d0d0; }
            QWidget { background: #0a0d12; color: #d0d0d0; }
            QPushButton, QLineEdit, QDateTimeEdit, QDoubleSpinBox {
                background: #101218; color: #d0d0d0; border: 1px solid #1c2028; padding: 4px;
            }
            QTabWidget::pane { border: 1px solid #1c2028; }
            QToolBar { background: #0a0d12; border: 0px; spacing: 4px; }
            QDockWidget { titlebar-close-icon: none; titlebar-normal-icon: none; }
        """)

        self.prefs = load_prefs()
        # Apply theme early
        apply_theme(QtWidgets.QApplication.instance() or QtWidgets.QApplication([]), self.prefs.get('theme', 'night'))

        self.sky_model = SkyModel(
            limiting_magnitude=float(self.prefs.get('limiting_magnitude', 6.0)),
            apply_refraction=bool(self.prefs.get('apply_refraction', True)),
            catalog_mode=self.prefs.get('catalog_mode', 'default'),
            custom_catalog=self.prefs.get('custom_catalog_path', ''),
            time_scale=self.prefs.get('time_scale', 'utc'),
            twilight_sun_alt=float(self.prefs.get('twilight_sun_alt', 90.0)),
            light_pollution_bortle=int(self.prefs.get('light_pollution_bortle', 4)),
            high_accuracy_ephem=bool(self.prefs.get('high_accuracy_ephem', True)),
            precession_nutation=bool(self.prefs.get('precession_nutation', True)),
        )
        preferred_view = self.prefs.get('view_mode', '2d')
        
        # Load constellation lines at startup (may be empty if file missing)
        self.constellation_lines = []
        try:
            self.constellation_lines = load_constellation_lines()
        except FileNotFoundError:
            pass  # No constellation file yet
        
        self.current_lat = float(self.prefs.get('lat_deg', 0.0))
        self.current_lon = float(self.prefs.get('lon_deg', 0.0))
        self.current_stars = []  # Cache for projection mode switching
        self.current_planets = []  # Cache for projection mode switching

        # Try to create 3D view; fall back to 2D-only if OpenGL unavailable
        self.sky_view_3d = None
        self.sky_view = SkyView2D()
        self.sky_view.set_projection_mode(self.prefs.get('projection_mode', 'rect'))
        self.sky_view.show_dso = bool(self.prefs.get('show_dso', True))
        try:
            self.sky_view.set_label_density(int(self.prefs.get('label_density', 1)))
        except Exception:
            pass
        try:
            self.sky_view.set_milky_way_texture(self.prefs.get('milky_way_texture', ''))
            self.sky_view.set_panorama_image(self.prefs.get('panorama_image', ''))
        except Exception:
            pass
        self.current_view = preferred_view if preferred_view in ('2d', '3d') else '2d'
        if self.current_view == '3d' and not HAS_3D:
            self.current_view = '2d'

        if HAS_3D:
            try:
                self.sky_view_3d = SkyView3D()
                self.sky_view_3d.show_dso = bool(self.prefs.get('show_dso', True))
                try:
                    self.sky_view_3d.set_label_density(int(self.prefs.get('label_density', 1)))
                except Exception:
                    pass
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
        # Info pane
        self.info_panel = QTextEdit()
        self.info_panel.setReadOnly(True)
        self.search_dialog = SearchDialog(self)

        # Use UTC for datetime edit (v0.2 uses UTC assumption)
        self.datetime_edit = QDateTimeEdit(QtCore.QDateTime.currentDateTimeUtc())
        self.datetime_edit.setCalendarPopup(True)
        self.now_btn = QPushButton('Now (UTC)')
        self.now_btn.setToolTip('Set time to current system UTC')
        self.update_btn = QPushButton('Update Sky')
        self.update_btn.setToolTip('Recompute sky for current settings')
        self.moon_label = QLabel('Moon: --')
        self.moon_label.setStyleSheet('color: rgb(210, 210, 255);')
        self.moon_icon = MoonPhaseWidget()
        # Time scrubbing / animation
        self.time_slider = QSlider(QtCore.Qt.Horizontal)
        self.time_slider.setRange(-720, 720)  # +/-12h in minutes
        self.time_slider.setValue(0)
        self.time_step_minutes = 10
        self.play_timer = QtCore.QTimer(self)
        self.play_timer.timeout.connect(self._on_time_tick)
        self.playing = False
        self.time_step_spin = QtWidgets.QSpinBox()
        self.time_step_spin.setRange(1, 180)
        self.time_step_spin.setValue(self.time_step_minutes)
        self.time_step_spin.setSuffix(" min/frame")
        self.time_step_spin.setToolTip("Time-lapse step per frame")
        self.mag_limit = QDoubleSpinBox()
        self.mag_limit.setRange(-1.0, 12.0)
        self.mag_limit.setSingleStep(0.1)
        self.mag_limit.setDecimals(1)
        self.mag_limit.setValue(float(self.prefs.get('limiting_magnitude', 6.0)))
        self.mag_limit.setToolTip('Limiting magnitude (dimmer stars hidden)')
        self.catalog_combo = QComboBox()
        self.catalog_combo.addItems(['Default', 'Rich', 'Custom'])
        mode_map = {'default': 0, 'rich': 1, 'custom': 2}
        self.catalog_combo.setCurrentIndex(mode_map.get(self.prefs.get('catalog_mode', 'default'), 0))
        self.custom_catalog_edit = QLineEdit(self.prefs.get('custom_catalog_path', ''))
        self.custom_catalog_browse = QPushButton('Browse')
        self.label_density = QComboBox()
        self.label_density.addItems(['Sparse', 'Balanced', 'Rich'])
        try:
            idx = int(self.prefs.get('label_density', 1))
            self.label_density.setCurrentIndex(max(0, min(idx, 2)))
        except Exception:
            self.label_density.setCurrentIndex(1)
        self.theme_combo = QComboBox()
        for key in THEMES.keys():
            self.theme_combo.addItem(THEMES[key].name, key)
        if self.prefs.get('theme', 'night') in THEMES:
            self.theme_combo.setCurrentIndex(list(THEMES.keys()).index(self.prefs.get('theme', 'night')))
        self.milky_path_edit = QLineEdit(self.prefs.get('milky_way_texture', ''))
        self.milky_browse_btn = QPushButton('Milky Way Texture')
        self.milky_clear_btn = QPushButton('Clear')
        self.panorama_path_edit = QLineEdit(self.prefs.get('panorama_image', ''))
        self.panorama_browse_btn = QPushButton('Panorama')
        self.panorama_clear_btn = QPushButton('Clear')
        self.time_scale_combo = QComboBox()
        self.time_scale_combo.addItems(['UTC', 'TT'])
        self.time_scale_combo.setCurrentIndex(0 if self.prefs.get('time_scale', 'utc').lower() == 'utc' else 1)
        self.refraction_chk = QtWidgets.QCheckBox('Atmospheric refraction')
        self.refraction_chk.setChecked(bool(self.prefs.get('apply_refraction', True)))
        self.high_acc_ephem_chk = QtWidgets.QCheckBox('High-accuracy ephemerides')
        self.high_acc_ephem_chk.setChecked(bool(self.prefs.get('high_accuracy_ephem', True)))
        self.precession_chk = QtWidgets.QCheckBox('Precession/Nutation')
        self.precession_chk.setChecked(bool(self.prefs.get('precession_nutation', True)))
        self.aberration_chk = QtWidgets.QCheckBox('Apply aberration')
        self.aberration_chk.setChecked(bool(self.prefs.get('apply_aberration', True)))
        self.light_pollution_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.light_pollution_slider.setRange(1, 9)
        self.light_pollution_slider.setValue(int(self.prefs.get('light_pollution_bortle', 4)))
        self.fov_presets = QComboBox()
        self.fov_presets.addItems([
            "None",
            "Wide 60°",
            "Binocular 7°",
            "Telescope 1°",
            "Planetary 0.3°",
            "DSLR 5°",
        ])
        self.fov_apply_btn = QPushButton("Apply FOV")

        # Label toggles: stars (bright only) and planets
        prefs = load_prefs()
        self.star_label_chk = QtWidgets.QCheckBox('Show star labels (mag < 2)')
        self.star_label_chk.setChecked(bool(prefs.get('show_star_labels', True)))
        self.planet_label_chk = QtWidgets.QCheckBox('Show planet labels')
        self.planet_label_chk.setChecked(bool(prefs.get('show_planet_labels', True)))
        self.dso_label_chk = QtWidgets.QCheckBox('Show deep-sky objects')
        self.dso_label_chk.setChecked(bool(prefs.get('show_dso', True)))

        self.export_btn = QPushButton('Export PNG')
        self.selected_target = None

        # Side control panel (dock)
        controls = QWidget()
        vctrl = QVBoxLayout()
        vctrl.setContentsMargins(6, 6, 6, 6)
        vctrl.addWidget(self.location_selector)
        vctrl.addWidget(QLabel('Time (UTC):'))
        vctrl.addWidget(self.datetime_edit)
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.now_btn)
        btn_row.addWidget(self.update_btn)
        vctrl.addLayout(btn_row)
        vctrl.addWidget(QLabel('Time scrubber (+/-12h):'))
        vctrl.addWidget(self.time_slider)
        vctrl.addWidget(QLabel('Time-lapse step (min):'))
        vctrl.addWidget(self.time_step_spin)
        vctrl.addWidget(QLabel('Projection:'))
        self.proj_rect_radio = QRadioButton('Rectangular')
        self.proj_dome_radio = QRadioButton('Dome')
        self.proj_rect_radio.setChecked(self.prefs.get('projection_mode', 'rect') == 'rect')
        self.proj_dome_radio.setChecked(self.prefs.get('projection_mode', 'rect') == 'dome')
        self.proj_rect_radio.toggled.connect(lambda checked: checked and self._set_projection('rect'))
        self.proj_dome_radio.toggled.connect(lambda checked: checked and self._set_projection('dome'))
        vctrl.addWidget(self.proj_rect_radio)
        vctrl.addWidget(self.proj_dome_radio)
        vctrl.addWidget(QLabel('Limiting magnitude:'))
        vctrl.addWidget(self.mag_limit)
        vctrl.addWidget(QLabel('Catalog:'))
        vctrl.addWidget(self.catalog_combo)
        cat_row = QHBoxLayout()
        cat_row.addWidget(self.custom_catalog_edit)
        cat_row.addWidget(self.custom_catalog_browse)
        vctrl.addLayout(cat_row)
        vctrl.addWidget(QLabel('Label density:'))
        vctrl.addWidget(self.label_density)
        moon_row = QHBoxLayout()
        moon_row.addWidget(self.moon_icon)
        moon_row.addWidget(self.moon_label)
        vctrl.addLayout(moon_row)
        vctrl.addSpacing(8)
        vctrl.addWidget(self.star_label_chk)
        vctrl.addWidget(self.planet_label_chk)
        vctrl.addWidget(self.dso_label_chk)
        vctrl.addWidget(QLabel('Theme:'))
        vctrl.addWidget(self.theme_combo)
        vctrl.addWidget(QLabel('Milky Way texture (optional):'))
        milky_row = QHBoxLayout()
        milky_row.addWidget(self.milky_path_edit)
        milky_row.addWidget(self.milky_browse_btn)
        milky_row.addWidget(self.milky_clear_btn)
        vctrl.addLayout(milky_row)
        vctrl.addWidget(QLabel('Panorama/landscape (optional):'))
        pano_row = QHBoxLayout()
        pano_row.addWidget(self.panorama_path_edit)
        pano_row.addWidget(self.panorama_browse_btn)
        pano_row.addWidget(self.panorama_clear_btn)
        vctrl.addLayout(pano_row)
        vctrl.addWidget(QLabel('Time scale:'))
        vctrl.addWidget(self.time_scale_combo)
        vctrl.addWidget(self.refraction_chk)
        vctrl.addWidget(self.high_acc_ephem_chk)
        vctrl.addWidget(self.precession_chk)
        vctrl.addWidget(self.aberration_chk)
        vctrl.addWidget(QLabel('Light pollution (Bortle 1-9):'))
        vctrl.addWidget(self.light_pollution_slider)
        play_row = QHBoxLayout()
        self.play_btn = QPushButton('Play/Pause (Space)')
        self.step_minus = QPushButton('← Step')
        self.step_plus = QPushButton('Step →')
        play_row.addWidget(self.step_minus)
        play_row.addWidget(self.play_btn)
        play_row.addWidget(self.step_plus)
        vctrl.addLayout(play_row)
        # Overlays
        overlay_row = QHBoxLayout()
        self.grid_ra_dec = QtWidgets.QCheckBox('RA/Dec grid')
        self.grid_alt_az = QtWidgets.QCheckBox('Alt/Az grid')
        self.grid_alt_az.setChecked(True)
        self.grid_ecliptic = QtWidgets.QCheckBox('Ecliptic')
        self.grid_meridian = QtWidgets.QCheckBox('Meridian')
        overlay_row.addWidget(self.grid_ra_dec)
        overlay_row.addWidget(self.grid_alt_az)
        overlay_row.addWidget(self.grid_ecliptic)
        overlay_row.addWidget(self.grid_meridian)
        vctrl.addLayout(overlay_row)
        self.fov_spin = QDoubleSpinBox()
        self.fov_spin.setRange(0.0, 90.0)
        self.fov_spin.setSingleStep(0.5)
        self.fov_spin.setPrefix('FOV ')
        self.fov_spin.setSuffix(' deg')
        self.fov_spin.setValue(0.0)
        vctrl.addWidget(self.fov_spin)
        fov_row = QHBoxLayout()
        fov_row.addWidget(self.fov_presets)
        fov_row.addWidget(self.fov_apply_btn)
        vctrl.addLayout(fov_row)
        # Preset skies
        vctrl.addWidget(QLabel('Presets:'))
        self.preset_combo = QComboBox()
        self.presets = [
            {"name": "Select preset...", "lat": None, "lon": None, "hours_offset": None},
            {"name": "Paris Midnight", "lat": 48.8566, "lon": 2.3522, "hours_offset": 0},
            {"name": "Mauna Kea Dark", "lat": 19.8206, "lon": -155.4681, "hours_offset": -10},
            {"name": "Sydney Evening", "lat": -33.8688, "lon": 151.2093, "hours_offset": 10},
            {"name": "Sahara Zenith", "lat": 23.4162, "lon": 25.6628, "hours_offset": 2},
            {"name": "Atacama Night", "lat": -23.2917, "lon": -67.9194, "hours_offset": -4},
            {"name": "Titanic Night", "lat": 41.7325, "lon": -49.9469, "hours_offset": 0},
        ]
        for p in self.presets:
            self.preset_combo.addItem(p["name"])
        vctrl.addWidget(self.preset_combo)
        self.preset_apply = QPushButton("Load preset")
        vctrl.addWidget(self.preset_apply)
        # Settings import/export/reset
        self.btn_export_settings = QPushButton("Export Settings")
        self.btn_import_settings = QPushButton("Import Settings")
        self.btn_reset_settings = QPushButton("Reset Settings")
        vctrl.addWidget(self.btn_export_settings)
        vctrl.addWidget(self.btn_import_settings)
        vctrl.addWidget(self.btn_reset_settings)
        controls.setLayout(vctrl)

        dock = QDockWidget("Controls", self)
        dock.setWidget(controls)
        dock.setFeatures(QDockWidget.NoDockWidgetFeatures)
        dock.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dock)

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
        v.addWidget(self.tabs)
        v.addWidget(QLabel("Info"))
        v.addWidget(self.info_panel)
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
        self.mag_limit.valueChanged.connect(self._on_mag_limit_changed)
        self.dso_label_chk.toggled.connect(self._on_dso_toggled)
        self.label_density.currentIndexChanged.connect(self._on_label_density_changed)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        self.time_scale_combo.currentIndexChanged.connect(self._on_time_scale_changed)
        self.refraction_chk.toggled.connect(self._on_refraction_toggled)
        self.light_pollution_slider.valueChanged.connect(self._on_light_pollution_changed)
        self.catalog_combo.currentIndexChanged.connect(self._on_catalog_mode_changed)
        self.custom_catalog_browse.clicked.connect(self._on_browse_custom_catalog)
        self.custom_catalog_edit.editingFinished.connect(self._on_custom_catalog_changed)
        self.high_acc_ephem_chk.toggled.connect(self._on_high_acc_ephem_toggled)
        self.precession_chk.toggled.connect(self._on_precession_toggled)
        self.aberration_chk.toggled.connect(self._on_aberration_toggled)
        # Picking connections (2D)
        try:
            self.sky_view.plot.scene().sigMouseClicked.connect(self._on_plot_clicked)
        except Exception:
            pass
        self.btn_export_settings.clicked.connect(self._on_export_settings)
        self.btn_import_settings.clicked.connect(self._on_import_settings)
        self.btn_reset_settings.clicked.connect(self._on_reset_settings)
        self.preset_apply.clicked.connect(self._on_apply_preset)
        self.play_btn.clicked.connect(self._toggle_play)
        self.step_minus.clicked.connect(lambda: self._step_time(-self.time_step_minutes))
        self.step_plus.clicked.connect(lambda: self._step_time(self.time_step_minutes))
        self.time_slider.valueChanged.connect(self._on_time_slider)
        self.time_step_spin.valueChanged.connect(self._on_time_step_changed)
        self.grid_ra_dec.toggled.connect(self._on_overlay_changed)
        self.grid_alt_az.toggled.connect(self._on_overlay_changed)
        self.grid_ecliptic.toggled.connect(self._on_overlay_changed)
        self.grid_meridian.toggled.connect(self._on_overlay_changed)
        self.fov_spin.valueChanged.connect(self._on_fov_changed)
        self.fov_apply_btn.clicked.connect(self._on_fov_preset)
        self.milky_browse_btn.clicked.connect(self._on_browse_milky)
        self.milky_clear_btn.clicked.connect(self._on_clear_milky)
        self.panorama_browse_btn.clicked.connect(self._on_browse_panorama)
        self.panorama_clear_btn.clicked.connect(self._on_clear_panorama)

        # Seed UI with persisted location/markers
        try:
            self.location_selector._update_lat_lon_fields(self.current_lat, self.current_lon)
            self.earth_view_2d.set_marker(self.current_lat, self.current_lon)
            if self.earth_view_3d:
                self.earth_view_3d.set_marker(self.current_lat, self.current_lon)
        except Exception:
            pass

        # Honor persisted view preference if 3D available
        if self.current_view == '3d' and self.sky_view_3d:
            self._switch_view('3d')

        try:
            self.loaded_plugins = load_plugins(self)
        except Exception:
            self.loaded_plugins = []

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

    def _on_dso_toggled(self, checked: bool):
        """Toggle deep-sky object visibility."""
        flag = bool(checked)
        try:
            self.sky_view.show_dso = flag
            if self.sky_view_3d:
                self.sky_view_3d.show_dso = flag
        except Exception:
            pass
        try:
            self.prefs['show_dso'] = flag
            save_prefs(self.prefs)
        except Exception:
            pass
        self.update_sky()

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
            prefs['show_dso'] = bool(getattr(self, 'action_show_dso', None) and self.action_show_dso.isChecked()) if hasattr(self, 'action_show_dso') else prefs.get('show_dso', True)
            prefs['projection_mode'] = 'dome' if getattr(self, 'action_proj_dome', None) and self.action_proj_dome.isChecked() else 'rect'
            prefs['view_mode'] = '3d' if getattr(self, 'action_view_3d', None) and self.action_view_3d.isChecked() else '2d'
            prefs['lat_deg'] = float(self.current_lat)
            prefs['lon_deg'] = float(self.current_lon)
            prefs['limiting_magnitude'] = float(self.mag_limit.value())
            prefs['label_density'] = int(self.label_density.currentIndex())
            prefs['catalog_mode'] = ['default', 'rich', 'custom'][self.catalog_combo.currentIndex()]
            prefs['custom_catalog_path'] = self.custom_catalog_edit.text().strip()
            prefs['theme'] = self.prefs.get('theme', 'night')
            prefs['time_scale'] = self.prefs.get('time_scale', 'utc')
            prefs['apply_refraction'] = bool(self.refraction_chk.isChecked())
            prefs['light_pollution_bortle'] = int(self.light_pollution_slider.value())
            prefs['high_accuracy_ephem'] = bool(self.high_acc_ephem_chk.isChecked())
            prefs['precession_nutation'] = bool(self.precession_chk.isChecked())
            prefs['milky_way_texture'] = self.milky_path_edit.text().strip()
            prefs['panorama_image'] = self.panorama_path_edit.text().strip()
            save_prefs(prefs)
        except Exception:
            pass
        super().closeEvent(event)

    def _create_actions(self):
        self.action_update = QtWidgets.QAction('Update Sky', self)
        self.action_update.setToolTip('Recompute sky for current time/location')
        self.action_update.setShortcut('Ctrl+R')
        self.action_update.triggered.connect(self.update_sky)

        self.action_now = QtWidgets.QAction('Now', self)
        self.action_now.setToolTip('Jump to current system time (UTC)')
        self.action_now.setShortcut('Ctrl+N')
        self.action_now.triggered.connect(self.set_now)

        self.action_export = QtWidgets.QAction('Export PNG...', self)
        self.action_export.setToolTip('Export current view as high-res PNG')
        self.action_export.setShortcut('Ctrl+E')
        self.action_export.triggered.connect(self.export_png)
        
        self.action_proj_rect = QtWidgets.QAction('Rectangular (Az/Alt)', self, checkable=True)
        self.action_proj_rect.setChecked(self.prefs.get('projection_mode', 'rect') == 'rect')
        self.action_proj_rect.setToolTip('Rectangular Alt/Az projection')
        self.action_proj_rect.setShortcut('Ctrl+1')
        self.action_proj_rect.triggered.connect(lambda: self._set_projection('rect'))
        
        self.action_proj_dome = QtWidgets.QAction('Dome (Polar)', self, checkable=True)
        self.action_proj_dome.setChecked(self.prefs.get('projection_mode', 'rect') == 'dome')
        self.action_proj_dome.setToolTip('Dome (fisheye) projection')
        self.action_proj_dome.setShortcut('Ctrl+Shift+1')
        self.action_proj_dome.triggered.connect(lambda: self._set_projection('dome'))
        
        # Group projection actions
        proj_group = QtWidgets.QActionGroup(self)
        proj_group.addAction(self.action_proj_rect)
        proj_group.addAction(self.action_proj_dome)
        
        # 3D view toggle (only available if OpenGL is supported)
        self.action_view_2d = QtWidgets.QAction('2D View', self, checkable=True)
        self.action_view_2d.setChecked(self.current_view == '2d')
        self.action_view_2d.setToolTip('Switch to 2D sky view')
        self.action_view_2d.setShortcut('Ctrl+2')
        self.action_view_2d.triggered.connect(lambda: self._switch_view('2d'))
        
        self.action_view_3d = QtWidgets.QAction('3D View', self, checkable=True, enabled=HAS_3D)
        self.action_view_3d.setToolTip('Switch to 3D dome view (if OpenGL available)')
        self.action_view_3d.setShortcut('Ctrl+3')
        self.action_view_3d.setChecked(HAS_3D and self.current_view == '3d')
        self.action_view_3d.triggered.connect(lambda: self._switch_view('3d'))
        
        view_group = QtWidgets.QActionGroup(self)
        view_group.addAction(self.action_view_2d)
        view_group.addAction(self.action_view_3d)
        
        # Earth view toggle (only available if OpenGL is supported)
        self.action_earth_2d = QtWidgets.QAction('2D Map', self, checkable=True)
        self.action_earth_2d.setChecked(True)
        self.action_earth_2d.setToolTip('Earth tab: 2D map')
        self.action_earth_2d.triggered.connect(lambda: self._switch_earth_view('2d'))
        
        self.action_earth_3d = QtWidgets.QAction('3D Globe', self, checkable=True, enabled=HAS_3D_EARTH)
        self.action_earth_3d.setToolTip('Earth tab: 3D globe (if OpenGL available)')
        self.action_earth_3d.triggered.connect(lambda: self._switch_earth_view('3d'))
        
        earth_group = QtWidgets.QActionGroup(self)
        earth_group.addAction(self.action_earth_2d)
        earth_group.addAction(self.action_earth_3d)

        # Label and overlay actions
        self.action_show_star_labels = QtWidgets.QAction('Show Star Labels', self, checkable=True)
        self.action_show_star_labels.setChecked(self.star_label_chk.isChecked())
        self.action_show_star_labels.setToolTip('Toggle bright star labels')
        self.action_show_star_labels.setShortcut('Ctrl+L')
        self.action_show_star_labels.toggled.connect(self._on_star_label_toggled)
        # keep checkboxes in sync
        self.action_show_star_labels.toggled.connect(self.star_label_chk.setChecked)
        self.star_label_chk.toggled.connect(self.action_show_star_labels.setChecked)

        self.action_show_planet_labels = QtWidgets.QAction('Show Planet Labels', self, checkable=True)
        self.action_show_planet_labels.setChecked(self.planet_label_chk.isChecked())
        self.action_show_planet_labels.setToolTip('Toggle planet labels')
        self.action_show_planet_labels.setShortcut('Ctrl+P')
        self.action_show_planet_labels.toggled.connect(self._on_planet_label_toggled)
        self.action_show_planet_labels.toggled.connect(self.planet_label_chk.setChecked)
        self.planet_label_chk.toggled.connect(self.action_show_planet_labels.setChecked)

        self.action_show_dso = QtWidgets.QAction('Show Deep-Sky Objects', self, checkable=True)
        self.action_show_dso.setChecked(self.dso_label_chk.isChecked())
        self.action_show_dso.setToolTip('Toggle Messier/DSO markers')
        self.action_show_dso.setShortcut('Ctrl+D')
        self.action_show_dso.toggled.connect(self._on_dso_toggled)
        self.action_show_dso.toggled.connect(self.dso_label_chk.setChecked)
        self.dso_label_chk.toggled.connect(self.action_show_dso.setChecked)

        self.action_show_constellations = QtWidgets.QAction('Show Constellation Lines', self, checkable=True)
        # default: show if we have constellation lines
        self.action_show_constellations.setChecked(bool(self.constellation_lines))
        self.action_show_constellations.setToolTip('Toggle constellation line overlay')
        self.action_show_constellations.setShortcut('Ctrl+C')
        self.action_show_constellations.toggled.connect(self._on_constellation_toggled)
        # sync with checkbox (none currently exists in control bar) - leave for future

        # label density quick actions (not in menu; only via control panel)

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

        help_menu = menubar.addMenu('Help')
        help_action = QtWidgets.QAction('Help / Tutorial', self)
        help_action.triggered.connect(self._show_help)
        help_menu.addAction(help_action)
        search_action = QtWidgets.QAction('Search / Go To', self)
        search_action.setShortcut('Ctrl+F')
        search_action.triggered.connect(self._show_search)
        help_menu.addAction(search_action)

        toolbar = self.addToolBar('Main')
        toolbar.addAction(self.action_now)
        toolbar.addAction(self.action_update)
        toolbar.addSeparator()
        toolbar.addAction(self.action_view_2d)
        toolbar.addAction(self.action_view_3d)
        toolbar.addSeparator()
        toolbar.addAction(self.action_show_star_labels)
        toolbar.addAction(self.action_show_planet_labels)
        toolbar.addAction(self.action_show_dso)
        toolbar.addAction(self.action_show_constellations)
        toolbar.addSeparator()
        toolbar.addAction(self.action_proj_rect)
        toolbar.addAction(self.action_proj_dome)
        toolbar.addSeparator()
        toolbar.addAction(self.action_export)

    def set_now(self):
        # Set to current UTC time
        self.datetime_edit.setDateTime(QtCore.QDateTime.currentDateTimeUtc())

    def _on_location_changed(self, lat: float, lon: float):
        """Called when location selector emits a new location."""
        self.current_lat = lat
        self.current_lon = lon
        try:
            self.prefs['lat_deg'] = float(lat)
            self.prefs['lon_deg'] = float(lon)
            save_prefs(self.prefs)
        except Exception:
            pass
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
        try:
            self.prefs['lat_deg'] = float(lat)
            self.prefs['lon_deg'] = float(lon)
            save_prefs(self.prefs)
        except Exception:
            pass
        # Update location selector (will trigger _on_location_changed if needed)
        self.location_selector._update_lat_lon_fields(lat, lon)
        # Trigger sky update
        self.update_sky()

    def _set_projection(self, mode: str):
        """Switch to 'rect' or 'dome' projection and redraw."""
        self.sky_view.set_projection_mode(mode)
        try:
            if mode == 'dome' and hasattr(self, 'action_proj_dome'):
                self.action_proj_dome.setChecked(True)
                self.action_proj_rect.setChecked(False)
            elif mode == 'rect' and hasattr(self, 'action_proj_rect'):
                self.action_proj_rect.setChecked(True)
                if hasattr(self, 'action_proj_dome'):
                    self.action_proj_dome.setChecked(False)
        except Exception:
            pass
        try:
            self.prefs['projection_mode'] = mode
            save_prefs(self.prefs)
        except Exception:
            pass
        try:
            if mode == 'rect':
                self.proj_rect_radio.setChecked(True)
            else:
                self.proj_dome_radio.setChecked(True)
        except Exception:
            pass
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
        self._update_moon_label(snapshot.moon)
        self.current_stars = snapshot.visible_stars  # Cache for projection switching
        self.current_planets = snapshot.visible_planets  # Cache for projection switching
        try:
            self.sky_view.limiting_magnitude = self.sky_model.limiting_magnitude
        except Exception:
            pass
        try:
            self.current_dso = snapshot.deep_sky_objects or []
        except Exception:
            self.current_dso = []
        # Show events summary if available
        try:
            if snapshot.events:
                lines = ["Events:"]
                for ev in snapshot.events:
                    r = ev.get('rise')
                    s = ev.get('set')
                    c = ev.get('culmination_alt')
                    def fmt(t):
                        return t.strftime('%H:%M') if t else '--'
                    lines.append(f"{ev.get('name')}: rise {fmt(r)}, set {fmt(s)}, max alt {c:.1f}°" if c is not None else f"{ev.get('name')}")
                self.info_panel.setPlainText("\n".join(lines))
        except Exception:
            pass
        
        # Pass the stars and planets to the active view
        if self.current_view == '3d' and self.sky_view_3d:
            self.sky_view_3d.update_sky(snapshot.visible_stars, snapshot.visible_planets, snapshot.deep_sky_objects)
            # Compute and draw constellation segments if available
            if self.constellation_lines and snapshot.visible_stars:
                star_map = {s.id: s for s in snapshot.visible_stars}
                segments = build_constellation_segments(star_map, self.constellation_lines)
                self.sky_view_3d.update_constellations(segments)
        else:
            # 2D view
            self.sky_view.update_sky(snapshot.visible_stars, snapshot.visible_planets, snapshot.deep_sky_objects)
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
            self.prefs['export_default_size'] = int(size)
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
        try:
            if mode == '3d':
                self.action_view_3d.setChecked(True)
                self.action_view_2d.setChecked(False)
            else:
                self.action_view_2d.setChecked(True)
                if hasattr(self, 'action_view_3d'):
                    self.action_view_3d.setChecked(False)
        except Exception:
            pass
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
        try:
            self.prefs['view_mode'] = mode
            save_prefs(self.prefs)
        except Exception:
            pass
    
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

    def _update_moon_label(self, moon):
        """Display moon phase and altitude information."""
        if not moon:
            self.moon_label.setText('Moon: —')
            self.moon_icon.set_phase(0.0, True)
            return
        frac = moon.phase_fraction or 0.0
        name = moon.phase_name or 'Moon'
        alt = moon.alt_deg
        self.moon_label.setText(f"Moon: {name} ({frac*100:.0f}%), alt {alt:.1f}°")
        waxing = moon.waxing if hasattr(moon, 'waxing') else ('Wax' in name or 'First' in name or 'New' in name or 'Full' in name)
        self.moon_icon.set_phase(frac, waxing=bool(waxing))

    def _on_mag_limit_changed(self, value: float):
        """Update limiting magnitude preference and redraw."""
        try:
            self.sky_model.set_limiting_magnitude(float(value))
            self.prefs['limiting_magnitude'] = float(value)
            save_prefs(self.prefs)
        except Exception:
            pass
        self.update_sky()

    def _on_label_density_changed(self, idx: int):
        self.prefs['label_density'] = int(idx)
        save_prefs(self.prefs)
        self.update_sky()

    def _on_theme_changed(self, idx: int):
        key = self.theme_combo.itemData(idx)
        if not key:
            key = list(THEMES.keys())[idx]
        self.prefs['theme'] = key
        save_prefs(self.prefs)
        apply_theme(QtWidgets.QApplication.instance(), key)
        # reapply background colors to views
        try:
            self.sky_view.plot.setBackground(THEMES[key].bg_color)
        except Exception:
            pass
        try:
            if self.sky_view_3d:
                self.sky_view_3d.setStyleSheet("")
        except Exception:
            pass

    def _on_browse_milky(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Select Milky Way texture', '', 'Images (*.png *.jpg *.jpeg *.webp)')
        if path:
            self.milky_path_edit.setText(path)
            self.sky_view.set_milky_way_texture(path)
            self.prefs['milky_way_texture'] = path
            save_prefs(self.prefs)

    def _on_clear_milky(self):
        self.milky_path_edit.setText('')
        self.sky_view.set_milky_way_texture('')
        self.prefs['milky_way_texture'] = ''
        save_prefs(self.prefs)

    def _on_browse_panorama(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Select panorama/landscape', '', 'Images (*.png *.jpg *.jpeg *.webp)')
        if path:
            self.panorama_path_edit.setText(path)
            self.sky_view.set_panorama_image(path)
            self.prefs['panorama_image'] = path
            save_prefs(self.prefs)

    def _on_clear_panorama(self):
        self.panorama_path_edit.setText('')
        self.sky_view.set_panorama_image('')
        self.prefs['panorama_image'] = ''
        save_prefs(self.prefs)

    def _on_time_scale_changed(self, idx: int):
        scale = 'utc' if idx == 0 else 'tt'
        self.prefs['time_scale'] = scale
        save_prefs(self.prefs)
        self.sky_model.time_scale = scale
        self.update_sky()

    def _on_refraction_toggled(self, checked: bool):
        self.prefs['apply_refraction'] = bool(checked)
        save_prefs(self.prefs)
        self.sky_model.apply_refraction = bool(checked)
        self.update_sky()

    def _on_light_pollution_changed(self, value: int):
        self.prefs['light_pollution_bortle'] = int(value)
        save_prefs(self.prefs)
        self.sky_model.light_pollution_bortle = int(value)
        self.update_sky()

    def _on_catalog_mode_changed(self, idx: int):
        mode = ['default', 'rich', 'custom'][idx] if idx < 3 else 'default'
        self.prefs['catalog_mode'] = mode
        save_prefs(self.prefs)
        self.sky_model.catalog_mode = mode
        self.sky_model.custom_catalog = self.custom_catalog_edit.text().strip()
        self.sky_model.load_stars()
        self.update_sky()

    def _on_browse_custom_catalog(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Select custom catalog CSV', '', 'CSV Files (*.csv)')
        if path:
            self.custom_catalog_edit.setText(path)
            self._on_custom_catalog_changed()

    def _on_custom_catalog_changed(self):
        path = self.custom_catalog_edit.text().strip()
        self.prefs['custom_catalog_path'] = path
        save_prefs(self.prefs)
        if self.catalog_combo.currentIndex() == 2:
            self.sky_model.custom_catalog = path
            self.sky_model.load_stars()
            self.update_sky()

    def _on_high_acc_ephem_toggled(self, checked: bool):
        self.prefs['high_accuracy_ephem'] = bool(checked)
        save_prefs(self.prefs)
        self.sky_model.high_accuracy_ephem = bool(checked)
        if checked:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Download ephemeris?",
                "High-accuracy mode requires downloading a JPL DE ephemeris kernel (a few MB). Download now?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            )
            if reply == QtWidgets.QMessageBox.Yes:
                path = self.sky_model._ensure_ephem_kernel()
                if not path:
                    QtWidgets.QMessageBox.warning(self, "Download failed", "Could not download ephemeris kernel.")

    def _on_precession_toggled(self, checked: bool):
        self.prefs['precession_nutation'] = bool(checked)
        save_prefs(self.prefs)
        # hook for future precession/nutation toggles
        self.sky_model.precession_nutation = bool(checked)

    def _on_aberration_toggled(self, checked: bool):
        self.prefs['apply_aberration'] = bool(checked)
        save_prefs(self.prefs)
        self.sky_model.apply_aberration = bool(checked)

    def _on_export_settings(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Export Settings', '', 'JSON Files (*.json)')
        if not path:
            return
        from .prefs import export_prefs
        ok = export_prefs(path)
        if not ok:
            QtWidgets.QMessageBox.warning(self, 'Export failed', 'Could not write settings file.')

    def _on_import_settings(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Import Settings', '', 'JSON Files (*.json)')
        if not path:
            return
        from .prefs import import_prefs
        prefs = import_prefs(path)
        self.prefs.update(prefs)
        QtWidgets.QMessageBox.information(self, 'Settings imported', 'Restart the app to apply imported settings.')

    def _on_reset_settings(self):
        from .prefs import reset_prefs
        reset_prefs()
        QtWidgets.QMessageBox.information(self, 'Settings reset', 'Settings reset to defaults. Restart to apply.')

    def _on_plot_clicked(self, event):
        if event.button() != QtCore.Qt.LeftButton:
            return
        pos = event.scenePos()
        picked = None
        if self.current_view == '2d':
            try:
                picked = self.sky_view.pick_object(pos)
            except Exception:
                picked = None
        else:
            try:
                picked = self.sky_view_3d.pick_object(pos)
            except Exception:
                picked = None
        if not picked:
            return
        kind, obj = picked
        if obj is None:
            return
        try:
            self._center_on_object(obj)
        except Exception:
            pass
        info_lines = []
        if kind == 'star':
            info_lines.append(f"Star: {obj.name} (id {obj.id})")
            info_lines.append(f"Mag: {getattr(obj, 'mag', ''):.2f}")
            info_lines.append(f"Alt/Az: {obj.alt_deg:.1f} / {obj.az_deg:.1f}")
            info_lines.append(f"RA/Dec: {obj.ra_deg:.2f} / {obj.dec_deg:.2f}")
        elif kind == 'planet':
            info_lines.append(f"Planet: {obj.name}")
            info_lines.append(f"Alt/Az: {obj.alt_deg:.1f} / {obj.az_deg:.1f}")
            info_lines.append(f"RA/Dec: {obj.ra_deg:.2f} / {obj.dec_deg:.2f}")
        elif kind == 'dso':
            info_lines.append(f"DSO: {obj.name} ({getattr(obj, 'obj_type', 'DSO')})")
            info_lines.append(f"Alt/Az: {obj.alt_deg:.1f} / {obj.az_deg:.1f}")
            info_lines.append(f"RA/Dec: {obj.ra_deg:.2f} / {obj.dec_deg:.2f}")
        self.info_panel.setPlainText("\n".join(info_lines))

    def _show_help(self):
        dlg = HelpViewer(self)
        dlg.exec_()

    def keyPressEvent(self, event):
        key = event.key()
        if key == QtCore.Qt.Key_Left:
            self._step_time(-self.time_step_minutes)
            event.accept()
            return
        if key == QtCore.Qt.Key_Right:
            self._step_time(self.time_step_minutes)
            event.accept()
            return
        if key in (QtCore.Qt.Key_Space,):
            self._toggle_play()
            event.accept()
            return
        if key in (QtCore.Qt.Key_Plus, QtCore.Qt.Key_Equal):
            self.time_step_minutes = min(180, self.time_step_minutes + 1)
            self.time_step_spin.setValue(self.time_step_minutes)
            event.accept()
            return
        if key == QtCore.Qt.Key_Minus:
            self.time_step_minutes = max(1, self.time_step_minutes - 1)
            self.time_step_spin.setValue(self.time_step_minutes)
            event.accept()
            return
        super().keyPressEvent(event)

    def _show_search(self):
        # Build object list from current snapshot caches
        objects = []
        for s in getattr(self, 'current_stars', []):
            objects.append({'name': s.name or f"Star {s.id}", 'type': 'star', 'data': s})
        for p in getattr(self, 'current_planets', []):
            t = 'planet' if getattr(p, 'name', '').lower() != 'moon' else 'moon'
            objects.append({'name': p.name, 'type': t, 'data': p})
        try:
            for d in getattr(self, 'current_dso', []):
                objects.append({'name': d.name, 'type': 'dso', 'data': d})
        except Exception:
            pass
        self.search_dialog.set_objects(objects)
        self.search_dialog.object_selected.connect(self._on_search_selected)
        self.search_dialog.show()

    def _on_search_selected(self, obj: dict):
        data = obj.get('data')
        if data is None:
            return
        # Focus info panel
        info_lines = []
        if obj.get('type') == 'star':
            info_lines.append(f"Star: {data.name} (id {data.id})")
            info_lines.append(f"Mag: {getattr(data, 'mag', ''):.2f}")
            info_lines.append(f"Alt/Az: {data.alt_deg:.1f} / {data.az_deg:.1f}")
            info_lines.append(f"RA/Dec: {data.ra_deg:.2f} / {data.dec_deg:.2f}")
        elif obj.get('type') in ('planet', 'moon'):
            info_lines.append(f"{data.name}")
            info_lines.append(f"Alt/Az: {data.alt_deg:.1f} / {data.az_deg:.1f}")
            info_lines.append(f"RA/Dec: {data.ra_deg:.2f} / {data.dec_deg:.2f}")
        elif obj.get('type') == 'dso':
            info_lines.append(f"DSO: {data.name} ({getattr(data, 'obj_type', 'DSO')})")
            info_lines.append(f"Alt/Az: {data.alt_deg:.1f} / {data.az_deg:.1f}")
            info_lines.append(f"RA/Dec: {data.ra_deg:.2f} / {data.dec_deg:.2f}")
        self.info_panel.setPlainText("\n".join(info_lines))
        self._center_on_object(data)

    def _on_apply_preset(self):
        idx = self.preset_combo.currentIndex()
        if idx <= 0 or idx >= len(self.presets):
            return
        preset = self.presets[idx]
        lat = preset.get('lat')
        lon = preset.get('lon')
        if lat is not None and lon is not None:
            self.current_lat = lat
            self.current_lon = lon
            self.location_selector._update_lat_lon_fields(lat, lon)
            self.earth_view_2d.set_marker(lat, lon)
            if self.earth_view_3d:
                self.earth_view_3d.set_marker(lat, lon)
        # Set time: now adjusted by hours_offset if provided
        now = datetime.utcnow()
        offset = preset.get('hours_offset')
        if offset is not None:
            now = now + timedelta(hours=offset)
        qt_now = QtCore.QDateTime(now.year, now.month, now.day, now.hour, now.minute, now.second, QtCore.Qt.UTC)
        self.datetime_edit.setDateTime(qt_now)
        self.update_sky()

    def _center_on_object(self, obj):
        """Center/pan views toward the selected object."""
        if obj is None:
            return
        try:
            az_sel = float(getattr(obj, 'az_deg', 0.0))
            alt_sel = float(getattr(obj, 'alt_deg', 0.0))
            self.selected_target = (az_sel, alt_sel)
            if hasattr(self.sky_view, 'set_fov_center'):
                self.sky_view.set_fov_center(az_sel, alt_sel)
        except Exception:
            pass
        if self.current_view == '2d':
            try:
                if self.sky_view.mode == 'rect':
                    az = float(getattr(obj, 'az_deg', 0.0)) % 360.0
                    alt = float(getattr(obj, 'alt_deg', 0.0))
                    span_az = 60.0
                    span_alt = 60.0
                    self.sky_view.plot.setXRange(max(0, az - span_az / 2), min(360, az + span_az / 2))
                    self.sky_view.plot.setYRange(max(0, alt - span_alt / 2), min(90, alt + span_alt / 2))
                else:
                    # dome: no pan, rely on redraw
                    pass
            except Exception:
                pass
        elif self.current_view == '3d' and self.sky_view_3d:
            try:
                az = float(getattr(obj, 'az_deg', 0.0))
                alt = float(getattr(obj, 'alt_deg', 0.0))
                self.sky_view_3d.glview.setCameraPosition(azimuth=az - 90, elevation=alt, distance=2.0)
            except Exception:
                pass

    def _on_time_slider(self, val: int):
        """Slider is minutes offset from current base time."""
        base = datetime.utcnow().replace(tzinfo=timezone.utc)
        dt = base + timedelta(minutes=val)
        qt_dt = QtCore.QDateTime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, QtCore.Qt.UTC)
        self.datetime_edit.setDateTime(qt_dt)
        self.update_sky()

    def _on_time_tick(self):
        self._step_time(self.time_step_minutes)

    def _on_time_step_changed(self, val: int):
        self.time_step_minutes = max(1, int(val))

    def _step_time(self, minutes: int):
        qdt = self.datetime_edit.dateTime().toUTC()
        dt = qdt.addSecs(minutes * 60)
        self.datetime_edit.setDateTime(dt)
        self.update_sky()

    def _toggle_play(self):
        self.playing = not self.playing
        if self.playing:
            self.play_timer.start(200)
        else:
            self.play_timer.stop()

    def _on_overlay_changed(self, checked: bool):
        try:
            self.sky_view.set_overlays(self.grid_ra_dec.isChecked(), self.grid_alt_az.isChecked(), self.grid_ecliptic.isChecked(), self.grid_meridian.isChecked())
        except Exception:
            pass
        try:
            if self.sky_view_3d:
                self.sky_view_3d.set_overlays(self.grid_ra_dec.isChecked(), self.grid_alt_az.isChecked(), self.grid_ecliptic.isChecked(), self.grid_meridian.isChecked())
        except Exception:
            pass

    def _on_fov_changed(self, val: float):
        radius = float(val)
        if radius <= 0:
            radius = None
        try:
            self.sky_view.set_fov_radius(radius)
            if radius and self.selected_target:
                az, alt = self.selected_target
                self.sky_view.set_fov_center(az, alt)
            if radius is None:
                try:
                    self.sky_view.clear_fov_center()
                except Exception:
                    pass
        except Exception:
            pass

    def _on_fov_preset(self):
        preset = self.fov_presets.currentText()
        mapping = {
            "None": 0.0,
            "Wide 60°": 30.0,
            "Binocular 7°": 3.5,
            "Telescope 1°": 0.5,
            "Planetary 0.3°": 0.15,
            "DSLR 5°": 2.5,
        }
        val = mapping.get(preset, 0.0)
        self.fov_spin.setValue(val)
