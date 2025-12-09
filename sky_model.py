"""Astronomical model utilities for v0.3.

Provides `Star` and `Planet` dataclasses, and `SkyModel` which loads the
bright-star catalog and computes a snapshot of visible stars and planets
(alt/az) for a given observer location and time.
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
    id: int
    name: str
    ra_deg: float
    dec_deg: float
    mag: float
    alt_deg: float
    az_deg: float


@dataclass
class Planet:
    """Represents a planet's position in the sky."""
    name: str
    ra_deg: float
    dec_deg: float
    alt_deg: float
    az_deg: float
    magnitude: Optional[float] = None  # Planet magnitude (if available)


@dataclass
class SkySnapshot:
    """Complete snapshot of visible sky from a location and time."""
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
        """Compute a snapshot of visible stars and planets at the given observer and time.

        Parameters
        - lat_deg, lon_deg: observer coordinates in degrees
        - dt_utc: a `datetime`. If naive, it is interpreted as local time and
          converted to UTC; otherwise it will be converted to UTC.

        Returns a `SkySnapshot` containing:
        - visible_stars: list[Star] for stars with altitude > 0 deg
        - visible_planets: list[Planet] for planets with altitude > 0 deg
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

