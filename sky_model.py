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
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Union, Optional

import numpy as np
from astropy.time import Time
from astropy.coordinates import SkyCoord, EarthLocation, AltAz, get_body
import astropy.units as u

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
    """Represents a solar-system body (planet) at a specific observation time.

    Attributes
    - name: Capitalized planet name (e.g. "Mars").
    - ra_deg: Right ascension in degrees [deg].
    - dec_deg: Declination in degrees [deg].
    - alt_deg: Altitude above horizon in degrees ([-90, 90]).
    - az_deg: Azimuth in degrees [0, 360).
    - magnitude: Optional visual magnitude when available.
    """

    name: str
    ra_deg: float
    dec_deg: float
    alt_deg: float
    az_deg: float
    magnitude: Optional[float] = None  # Planet magnitude (if available)


@dataclass
class SkySnapshot:
    """Immutable snapshot of the visible sky for a given observer/time.

    This is the stable headless API returned by :meth:`SkyModel.compute_snapshot`.

    Attributes
    - visible_stars: List of :class:`Star` objects with ``alt_deg > 0``.
    - visible_planets: List of :class:`Planet` objects with ``alt_deg > 0``.
    """

    visible_stars: List[Star]
    visible_planets: List[Planet]


class SkyModel:
    # Major planets to track
    PLANETS = ['mercury', 'venus', 'mars', 'jupiter', 'saturn']
    
    def __init__(self, stars_csv: Union[str, Path] = 'stars_bright.csv') -> None:
        """Create a SkyModel and load the bright-star catalog.

        `stars_csv` may be a filename inside `data/` (default) or a path.
        """
        self.stars_source = stars_csv
        self.stars = []
        self.load_stars()

    def load_stars(self) -> None:
        """Load the bright star catalog into `self.stars`.

        Each entry is a dict with keys: id, name, ra_deg, dec_deg, mag
        """
        # `load_bright_stars` reads from package `data/` by default
        self.stars = load_bright_stars()

    def get_planet_positions(self, lat_deg: float, lon_deg: float, dt_utc: datetime) -> List[Planet]:
        """Compute positions of major planets at the given observer and time.

        Parameters
        - lat_deg, lon_deg: observer coordinates in degrees
        - dt_utc: a `datetime`. If naive, it is interpreted as local time and
          converted to UTC; otherwise it will be converted to UTC.

        Returns a list of `Planet` objects for planets with altitude > 0 deg.
        """
        # Normalize datetime to timezone-aware UTC
        if dt_utc.tzinfo is None:
            dt_local = dt_utc.astimezone()
            dt_utc = dt_local.astimezone(timezone.utc)
        else:
            dt_utc = dt_utc.astimezone(timezone.utc)

        times = Time(dt_utc)
        location = EarthLocation(lat=lat_deg * u.deg, lon=lon_deg * u.deg, height=0 * u.m)
        altaz_frame = AltAz(obstime=times, location=location)

        visible_planets = []
        for planet_name in self.PLANETS:
            try:
                # Get planet position using astropy
                planet_coord = get_body(planet_name, times, location)
                aa = planet_coord.transform_to(altaz_frame)
                
                # Only include if above horizon
                if aa.alt.degree > 0.0:
                    visible_planets.append(Planet(
                        name=planet_name.capitalize(),
                        ra_deg=float(planet_coord.ra.degree),
                        dec_deg=float(planet_coord.dec.degree),
                        alt_deg=float(aa.alt.degree),
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
        if dt_utc.tzinfo is None:
            # interpret naive as local time, make aware, then convert to UTC
            dt_local = dt_utc.astimezone()
            dt_utc = dt_local.astimezone(timezone.utc)
        else:
            dt_utc = dt_utc.astimezone(timezone.utc)

        times = Time(dt_utc)
        location = EarthLocation(lat=lat_deg * u.deg, lon=lon_deg * u.deg, height=0 * u.m)
        altaz_frame = AltAz(obstime=times, location=location)

        # Build arrays for stars
        ra = np.array([s['ra_deg'] for s in self.stars])
        dec = np.array([s['dec_deg'] for s in self.stars])
        mag = np.array([s['mag'] for s in self.stars])
        names = [s['name'] for s in self.stars]
        ids = [s['id'] for s in self.stars]

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
                    alt_deg=float(alt[i]),
                    az_deg=float(az[i]),
                ))

        # Get planets
        visible_planets = self.get_planet_positions(lat_deg, lon_deg, dt_utc)

        return SkySnapshot(visible_stars=visible_stars, visible_planets=visible_planets)

