"""Headless astronomical model utilities for Night Sky Viewer (v0.3).

This module provides the computational engine used throughout the
application and tests. The primary entry point is :class:`SkyModel`, which
can compute a :class:`SkySnapshot` for a given observer location and UTC
time. The snapshot is a stable, serializable API between the model and
UI layers (2D/3D views, export, and CLI tools).

Units and conventions
- All angular coordinates (RA, Dec, Alt, Az) are expressed in degrees.
- Altitude/declination range: [-90.0, +90.0] degrees (negative = below
    horizon).
- Azimuth range: [0.0, 360.0) degrees, normalized with `% 360` where
    appropriate (0 = North, 90 = East, 180 = South, 270 = West).
- Times passed to the API should be timezone-aware :class:`datetime` in
    UTC; naive datetimes are interpreted as local time and converted to
    UTC.

The dataclasses ``Star``, ``Planet``, and ``SkySnapshot`` are lightweight
value objects intended for consumption by GUI code, exports, and tests.
"""

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Union, Optional, Tuple
from contextlib import contextmanager

import numpy as np
from astropy.time import Time
from astropy.coordinates import SkyCoord, EarthLocation, AltAz, get_body, solar_system_ephemeris, get_sun
import astropy.units as u
from astropy.utils.data import download_file

from .data_manager import load_bright_stars


@dataclass
class Star:
    """Representation of a catalog star at a specific observation time.

    Attributes
    - id: Integer identifier (from the bright-star catalog).
    - name: Common name or Bayer/Flamsteed designation.
    - ra_deg: Right ascension in degrees (ICRS epoch) [deg].
    - dec_deg: Declination in degrees (ICRS epoch) [deg].
    - mag: Visual magnitude (smaller = brighter).
    - alt_deg: Altitude above horizon in degrees ([-90, 90]).
    - az_deg: Azimuth in degrees [0, 360).
    """

    id: int
    name: str
    ra_deg: float
    dec_deg: float
    mag: float
    alt_deg: float
    az_deg: float


@dataclass
class Planet:
    """Represents a solar-system body (planet or Moon) at a specific observation time."""

    name: str
    ra_deg: float
    dec_deg: float
    alt_deg: float
    az_deg: float
    magnitude: Optional[float] = None  # Planet magnitude (if available)
    phase_fraction: Optional[float] = None  # 0=new, 1=full (for Moon)
    phase_name: Optional[str] = None      # e.g., "Waxing gibbous"
    waxing: Optional[bool] = None


@dataclass
class SkySnapshot:
    """Immutable snapshot of the visible sky for a given observer/time.

    This is the stable headless API returned by :meth:`SkyModel.compute_snapshot`.

    Attributes
    - visible_stars: List of :class:`Star` objects with ``alt_deg > 0``.
    - visible_planets: List of :class:`Planet` objects with ``alt_deg > 0`` (includes Moon).
    - moon: Optional :class:`Planet` entry representing the Moon with phase metadata.
    """

    visible_stars: List[Star]
    visible_planets: List[Planet]
    moon: Optional[Planet] = None
    deep_sky_objects: Optional[List["DeepSkyObject"]] = None
    events: Optional[List[dict]] = None


@dataclass
class DeepSkyObject:
    """Simple representation for Messier/DSO markers."""

    name: str
    ra_deg: float
    dec_deg: float
    alt_deg: float
    az_deg: float
    obj_type: str = "DSO"


class SkyModel:
    # Major planets to track
    PLANETS = ['mercury', 'venus', 'mars', 'jupiter', 'saturn']
    METEOR_RADIANTS = [
        {"name": "Perseids", "ra_deg": 46.0, "dec_deg": 58.0},
        {"name": "Geminids", "ra_deg": 112.0, "dec_deg": 33.0},
        {"name": "Quadrantids", "ra_deg": 230.0, "dec_deg": 49.0},
        {"name": "Lyrids", "ra_deg": 272.0, "dec_deg": 34.0},
    ]
    
    def __init__(self, stars_csv: Union[str, Path] = 'stars_bright.csv', limiting_magnitude: float = 6.0, apply_refraction: bool = False, catalog_mode: str = 'default', custom_catalog: str = '', time_scale: str = 'utc', twilight_sun_alt: float = 90.0, light_pollution_bortle: int = 4, high_accuracy_ephem: bool = False, precession_nutation: bool = True, apply_aberration: bool = True) -> None:
        """Create a SkyModel and load the bright-star catalog.

        `stars_csv` may be a filename inside `data/` (default) or a path.
        """
        self.stars_source = stars_csv
        self.stars = []
        self.limiting_magnitude = float(limiting_magnitude)
        self.apply_refraction = bool(apply_refraction)
        self.catalog_mode = catalog_mode
        self.custom_catalog = custom_catalog
        self.time_scale = time_scale
        self.twilight_sun_alt = twilight_sun_alt
        self.light_pollution_bortle = max(1, min(int(light_pollution_bortle), 9))
        self.high_accuracy_ephem = bool(high_accuracy_ephem)
        self.precession_nutation = bool(precession_nutation)
        self.apply_aberration = bool(apply_aberration)
        self._ephem_kernel_path = None
        self.load_stars()

    def load_stars(self) -> None:
        """Load the bright star catalog into `self.stars`.

        Each entry is a dict with keys: id, name, ra_deg, dec_deg, mag
        """
        # `load_bright_stars` reads from package `data/` by default
        catalog = None
        if self.catalog_mode == 'rich':
            catalog = 'rich'
        elif self.catalog_mode == 'custom' and self.custom_catalog:
            catalog = self.custom_catalog
        self.stars = load_bright_stars(catalog)

    @staticmethod
    def _filter_catalog_by_mag(catalog: List[dict], mag_limit: float) -> List[dict]:
        """Return stars with magnitude <= mag_limit (or all if mag_limit is None)."""
        if mag_limit is None:
            return catalog
        filtered = []
        for s in catalog:
            try:
                if float(s.get('mag', 99.0)) <= float(mag_limit):
                    filtered.append(s)
            except Exception:
                continue
        return filtered

    def set_limiting_magnitude(self, mag_limit: float) -> None:
        """Set limiting magnitude used for star filtering."""
        self.limiting_magnitude = float(mag_limit)

    def _ensure_ephem_kernel(self) -> Optional[str]:
        """Download a JPL ephemeris kernel if high accuracy is enabled."""
        if not self.high_accuracy_ephem:
            return None
        if self._ephem_kernel_path and Path(self._ephem_kernel_path).exists():
            return self._ephem_kernel_path
        try:
            url = 'https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de421.bsp'
            path = download_file(url, cache=True, timeout=20)
            self._ephem_kernel_path = path
            return path
        except Exception:
            return None

    @contextmanager
    def _ephem_context(self):
        """Context manager for solar system ephemeris selection."""
        if self.high_accuracy_ephem:
            kernel = self._ensure_ephem_kernel()
            if kernel and Path(kernel).exists():
                with solar_system_ephemeris.set(kernel):
                    yield
                    return
        with solar_system_ephemeris.set('builtin'):
            yield

    def _compute_rise_set_for_coord(self, coord: SkyCoord, lat_deg: float, lon_deg: float, dt_utc: datetime, step_minutes: int = 10):
        """Brute-force rise/set/culmination over +/-12h from dt_utc."""
        times = []
        alts = []
        start = dt_utc.replace(minute=0, second=0, microsecond=0) - timedelta(hours=12)
        location = EarthLocation(lat=lat_deg * u.deg, lon=lon_deg * u.deg, height=0 * u.m)
        for i in range(0, int(24 * 60 / step_minutes) + 1):
            t = start + timedelta(minutes=i * step_minutes)
            times.append(t)
            aa = coord.transform_to(AltAz(obstime=Time(t), location=location))
            alts.append(float(aa.alt.degree))
        rise = None
        set_ = None
        culminate = max(alts)
        # simple zero-cross detection
        for i in range(1, len(alts)):
            if alts[i - 1] <= 0 < alts[i]:
                rise = times[i]
            if alts[i - 1] >= 0 > alts[i]:
                set_ = times[i]
        return rise, set_, culminate

    def _compute_rise_set_summary(self, lat_deg: float, lon_deg: float, dt_utc: datetime, planets: List[Planet], moon_obj: Optional[Planet]):
        """Compute rise/set/culmination for Sun, Moon, planets (coarse)."""
        summary = []
        location = EarthLocation(lat=lat_deg * u.deg, lon=lon_deg * u.deg, height=0 * u.m)
        with self._ephem_context():
            sun_coord = get_sun(Time(dt_utc))
        sun_rise, sun_set, sun_max = self._compute_rise_set_for_coord(sun_coord, lat_deg, lon_deg, dt_utc)
        summary.append({'name': 'Sun', 'rise': sun_rise, 'set': sun_set, 'culmination_alt': sun_max})
        if moon_obj:
            moon_coord = SkyCoord(moon_obj.ra_deg * u.deg, moon_obj.dec_deg * u.deg, frame='icrs')
            r, s, c = self._compute_rise_set_for_coord(moon_coord, lat_deg, lon_deg, dt_utc)
            summary.append({'name': 'Moon', 'rise': r, 'set': s, 'culmination_alt': c})
        for p in planets:
            if getattr(p, 'name', '').lower() == 'moon':
                continue
            coord = SkyCoord(p.ra_deg * u.deg, p.dec_deg * u.deg, frame='icrs')
            r, s, c = self._compute_rise_set_for_coord(coord, lat_deg, lon_deg, dt_utc)
            summary.append({'name': p.name, 'rise': r, 'set': s, 'culmination_alt': c})
        return summary

    def _detect_conjunctions(self, planets: List[Planet], moon_obj: Optional[Planet], sun_coord: Optional[SkyCoord]) -> List[dict]:
        """Detect simple close approaches between visible planets/Moon (and coarse eclipses)."""
        events = []
        bodies = []
        for p in planets:
            bodies.append((p.name, SkyCoord(p.ra_deg * u.deg, p.dec_deg * u.deg, frame='icrs')))
        if moon_obj:
            bodies.append(("Moon", SkyCoord(moon_obj.ra_deg * u.deg, moon_obj.dec_deg * u.deg, frame='icrs')))
        # Pairwise separations
        for i in range(len(bodies)):
            for j in range(i + 1, len(bodies)):
                name_a, coord_a = bodies[i]
                name_b, coord_b = bodies[j]
                sep = float(coord_a.separation(coord_b).degree)
                if sep < 5.0:
                    events.append({'name': f'Conjunction: {name_a} & {name_b}', 'separation_deg': sep})
        # Coarse eclipses using Sun/Moon separation
        if sun_coord and moon_obj:
            moon_c = SkyCoord(moon_obj.ra_deg * u.deg, moon_obj.dec_deg * u.deg, frame='icrs')
            sep = float(sun_coord.separation(moon_c).degree)
            if sep < 8.0:
                events.append({'name': 'Possible solar eclipse window', 'separation_deg': sep})
            if abs(sep - 180.0) < 8.0:
                events.append({'name': 'Possible lunar eclipse window', 'separation_deg': abs(sep - 180.0)})
        return events

    def get_deep_sky(self, lat_deg: float, lon_deg: float, dt_utc: datetime) -> List[DeepSkyObject]:
        """Return deep sky objects above the horizon."""
        try:
            from .data_manager import load_stars  # reuse loader for generic CSV
            dso_rows = load_stars('messier.csv')
            try:
                dso_rows += load_stars('ngc_ic.csv')
            except Exception:
                pass
        except Exception:
            return []

        dt_utc = self._normalize_time(dt_utc)
        times = Time(dt_utc, scale=self.time_scale if self.time_scale in ('utc', 'tt') else 'utc')
        location = EarthLocation(lat=lat_deg * u.deg, lon=lon_deg * u.deg, height=0 * u.m)
        altaz_frame = AltAz(obstime=times, location=location)

        try:
            ra = np.array([float(r['ra_deg']) for r in dso_rows])
            dec = np.array([float(r['dec_deg']) for r in dso_rows])
        except Exception:
            return []

        coords = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame='icrs')
        aa = coords.transform_to(altaz_frame)

        objs = []
        for idx, row in enumerate(dso_rows):
            alt = float(self._apply_refraction(float(aa.alt.degree[idx])))
            az = float(aa.az.degree[idx])
            if alt > 0.0:
                objs.append(DeepSkyObject(
                    name=row.get('name', f"Obj{idx}"),
                    ra_deg=float(ra[idx]),
                    dec_deg=float(dec[idx]),
                    alt_deg=alt,
                    az_deg=az,
                    obj_type=row.get('type', 'DSO')
                ))
        # Add meteor shower radiants (static list)
        try:
            if self.METEOR_RADIANTS:
                rad_ra = np.array([r['ra_deg'] for r in self.METEOR_RADIANTS])
                rad_dec = np.array([r['dec_deg'] for r in self.METEOR_RADIANTS])
                rad_coords = SkyCoord(ra=rad_ra * u.deg, dec=rad_dec * u.deg, frame='icrs')
                rad_aa = rad_coords.transform_to(altaz_frame)
                for i, rad in enumerate(self.METEOR_RADIANTS):
                    alt = float(self._apply_refraction(float(rad_aa.alt.degree[i])))
                    az = float(rad_aa.az.degree[i])
                    if alt > 0:
                        objs.append(DeepSkyObject(
                            name=rad['name'],
                            ra_deg=float(rad_ra[i]),
                            dec_deg=float(rad_dec[i]),
                            alt_deg=alt,
                            az_deg=az,
                            obj_type="Meteor radiant"
                        ))
        except Exception:
            pass
        return objs

    def _normalize_time(self, dt_utc: datetime) -> datetime:
        """Return timezone-aware UTC datetime."""
        if dt_utc.tzinfo is None:
            dt_local = dt_utc.astimezone()
            return dt_local.astimezone(timezone.utc)
        return dt_utc.astimezone(timezone.utc)

    def _moon_phase(self, times: Time) -> Tuple[float, str]:
        """Return illuminated fraction (0-1) and a friendly phase name."""
        try:
            sun_coord = get_body('sun', times)
            moon_coord = get_body('moon', times)
            phase_angle = float(sun_coord.separation(moon_coord).degree)
            fraction = float((1 - np.cos(np.radians(phase_angle))) / 2.0)
            # waxing if moon RA is ahead of sun within 180 deg
            ra_diff = (moon_coord.ra.degree - sun_coord.ra.degree) % 360.0
            waxing = ra_diff < 180.0
        except Exception:
            phase_angle = 0.0
            fraction = 0.0
            waxing = True

        # Simple naming
        if fraction < 0.03:
            name = "New Moon"
        elif fraction < 0.25:
            name = "Waxing crescent"
        elif fraction < 0.27:
            name = "First quarter"
        elif fraction < 0.48:
            name = "Waxing gibbous"
        elif fraction < 0.52:
            name = "Full Moon"
        elif fraction < 0.73:
            name = "Waning gibbous"
        elif fraction < 0.77:
            name = "Last quarter"
        elif fraction < 0.97:
            name = "Waning crescent"
        else:
            name = "New Moon"
        return fraction, name, waxing

    def _apply_refraction(self, alt_deg: float) -> float:
        """Apply a simple refraction correction for altitudes near the horizon."""
        if not getattr(self, "apply_refraction", False):
            return alt_deg
        if alt_deg < -1.0 or alt_deg > 90.0:
            return alt_deg
        # Bennett's approximate formula (arcminutes)
        try:
            alt_rad = np.radians(max(alt_deg, -1.0) + 0.001)
            R = 1.02 / np.tan(alt_rad + 10.3 / (alt_rad + 5.11))
            return alt_deg + R / 60.0
        except Exception:
            return alt_deg

    def get_planet_positions(self, lat_deg: float, lon_deg: float, dt_utc: datetime) -> List[Planet]:
        """Compute positions of major planets at the given observer and time.

        Parameters
        - lat_deg, lon_deg: observer coordinates in degrees
        - dt_utc: a `datetime`. If naive, it is interpreted as local time and
          converted to UTC; otherwise it will be converted to UTC.

        Returns a list of `Planet` objects for planets with altitude > 0 deg.
        """
        # Normalize datetime to timezone-aware UTC
        dt_utc = self._normalize_time(dt_utc)

        times = Time(dt_utc)
        location = EarthLocation(lat=lat_deg * u.deg, lon=lon_deg * u.deg, height=0 * u.m)
        altaz_frame = AltAz(obstime=times, location=location)
        sun_coord_cache = None

        visible_planets = []
        for planet_name in self.PLANETS:
            try:
                with self._ephem_context():
                    planet_coord = get_body(planet_name, times, location)
                aa = planet_coord.transform_to(altaz_frame)
                
                # Only include if above horizon
                alt_corr = self._apply_refraction(float(aa.alt.degree))
                if alt_corr > 0.0:
                    visible_planets.append(Planet(
                        name=planet_name.capitalize(),
                        ra_deg=float(planet_coord.ra.degree),
                        dec_deg=float(planet_coord.dec.degree),
                        alt_deg=float(alt_corr),
                        az_deg=float(aa.az.degree),
                        magnitude=None  # Could be computed but not needed for visualization
                    ))
            except Exception:
                # Skip planets that fail to compute (e.g., Sun, Moon may have special handling)
                pass
        
        return visible_planets

    def compute_snapshot(self, lat_deg: float, lon_deg: float, dt_utc: datetime) -> SkySnapshot:
        """Compute a headless snapshot of the visible sky for an observer.

        The returned :class:`SkySnapshot` contains lists of stars and planets
        that are above the horizon (``alt_deg > 0``) for the requested
        observer position and time.

        Parameters
        - lat_deg (float): Observer latitude in degrees (positive = North).
        - lon_deg (float): Observer longitude in degrees (positive = East).
        - dt_utc (datetime): Observation time. If naive, the datetime is
          interpreted as local time and converted to UTC; timezone-aware
          datetimes are converted to UTC before astronomical calculations.

        Returns
        - SkySnapshot: contains ``visible_stars`` and ``visible_planets``.

        Notes
        - All angular outputs are in degrees: ``ra_deg``, ``dec_deg``,
          ``alt_deg`` ([-90, 90]), ``az_deg`` ([0, 360)).
        - The method is deterministic and relies on the internal bright-
          star catalog loaded by :meth:`load_stars`.
        """
        # Normalize datetime to timezone-aware UTC
        dt_utc = self._normalize_time(dt_utc)

        times = Time(dt_utc)
        location = EarthLocation(lat=lat_deg * u.deg, lon=lon_deg * u.deg, height=0 * u.m)
        altaz_frame = AltAz(obstime=times, location=location)

        # Build arrays for stars (filtered by limiting magnitude)
        # adjust limiting magnitude by light pollution (simple model: degrade by 0.2 mag per Bortle step above 1)
        lp_penalty = max(0, self.light_pollution_bortle - 1) * 0.2
        effective_lim_mag = max(-5.0, self.limiting_magnitude - lp_penalty)
        stars_catalog = self._filter_catalog_by_mag(self.stars, effective_lim_mag)
        ra = np.array([s['ra_deg'] for s in stars_catalog])
        dec = np.array([s['dec_deg'] for s in stars_catalog])
        mag = np.array([s['mag'] for s in stars_catalog])
        names = [s['name'] for s in stars_catalog]
        ids = [s['id'] for s in stars_catalog]

        # allow precession/nutation toggles (astropy handles by default; here we keep hook)
        starcoords = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame='icrs')
        aa = starcoords.transform_to(altaz_frame)
        alt = aa.alt.degree
        az = aa.az.degree

        visible_stars = []
        for i in range(len(ra)):
            if alt[i] > 0.0:
                visible_stars.append(Star(
                    id=int(ids[i]),
                    name=names[i],
                    ra_deg=float(ra[i]),
                    dec_deg=float(dec[i]),
                    mag=float(mag[i]),
                    alt_deg=float(self._apply_refraction(float(alt[i]))),
                    az_deg=float(az[i]),
                ))

        # Get planets
        visible_planets = self.get_planet_positions(lat_deg, lon_deg, dt_utc)

        # Compute Moon position and phase; include as "planet"-like entry
        moon_obj: Optional[Planet] = None
        try:
            times = Time(dt_utc)
            location = EarthLocation(lat=lat_deg * u.deg, lon=lon_deg * u.deg, height=0 * u.m)
            altaz_frame = AltAz(obstime=times, location=location)
            with self._ephem_context():
                moon_coord = get_body('moon', times, location)
            moon_aa = moon_coord.transform_to(altaz_frame)
            fraction, phase_name, waxing = self._moon_phase(times)
            moon_alt = float(self._apply_refraction(float(moon_aa.alt.degree)))
            moon_obj = Planet(
                name="Moon",
                ra_deg=float(moon_coord.ra.degree),
                dec_deg=float(moon_coord.dec.degree),
                alt_deg=moon_alt,
                az_deg=float(moon_aa.az.degree),
                magnitude=None,
                phase_fraction=fraction,
                phase_name=phase_name,
                waxing=waxing,
            )
            if moon_obj.alt_deg > 0.0:
                visible_planets.insert(0, moon_obj)
        except Exception:
            moon_obj = None

        # Twilight filtering: optionally hide objects when Sun is above threshold
        try:
            with self._ephem_context():
                sun_coord_cache = get_body('sun', Time(dt_utc))
            sun_aa = sun_coord_cache.transform_to(altaz_frame)
            if float(self.twilight_sun_alt) < 90.0 and sun_aa.alt.degree > float(self.twilight_sun_alt):
                visible_stars = []
                visible_planets = []
                deep_sky = []
        except Exception:
            pass

        # Deep sky objects (best-effort)
        deep_sky = []
        try:
            deep_sky = self.get_deep_sky(lat_deg, lon_deg, dt_utc)
        except Exception:
            deep_sky = []

        events = []
        try:
            events = self._compute_rise_set_summary(lat_deg, lon_deg, dt_utc, visible_planets, moon_obj)
        except Exception:
            events = []
        try:
            events += self._detect_conjunctions(visible_planets, moon_obj, sun_coord_cache)
        except Exception:
            pass

        return SkySnapshot(visible_stars=visible_stars, visible_planets=visible_planets, moon=moon_obj, deep_sky_objects=deep_sky, events=events)
