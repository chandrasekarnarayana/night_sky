import unittest
from datetime import datetime, timezone

from night_sky.data_manager import load_bright_stars
from night_sky.sky_model import SkyModel, SkySnapshot, Planet


class TestDataAndModel(unittest.TestCase):
    def test_load_bright_stars(self):
        stars = load_bright_stars()
        self.assertIsInstance(stars, list)
        self.assertGreaterEqual(len(stars), 1)
        s = stars[0]
        for k in ('id', 'name', 'ra_deg', 'dec_deg', 'mag'):
            self.assertIn(k, s)

    def test_compute_snapshot(self):
        sm = SkyModel()
        snap = sm.compute_snapshot(0.0, 0.0, datetime.now(timezone.utc))
        # Expect a SkySnapshot with visible_stars and visible_planets
        self.assertIsInstance(snap, SkySnapshot)
        self.assertIsInstance(snap.visible_stars, list)
        self.assertIsInstance(snap.visible_planets, list)

        # If there are visible stars, assert basic ranges and attributes
        if len(snap.visible_stars) > 0:
            st = snap.visible_stars[0]
            for attr in ('id', 'name', 'ra_deg', 'dec_deg', 'mag', 'alt_deg', 'az_deg'):
                self.assertTrue(hasattr(st, attr))
            self.assertGreaterEqual(st.alt_deg, -90.0)
            self.assertLessEqual(st.alt_deg, 90.0)
            az_norm = st.az_deg % 360.0
            self.assertGreaterEqual(az_norm, 0.0)
            self.assertLess(az_norm, 360.0)

        # If there are planets, assert Planet shape
        if len(snap.visible_planets) > 0:
            p = snap.visible_planets[0]
            for attr in ('name', 'ra_deg', 'dec_deg', 'alt_deg', 'az_deg'):
                self.assertTrue(hasattr(p, attr))


if __name__ == '__main__':
    unittest.main()
