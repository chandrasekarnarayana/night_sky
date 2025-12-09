import unittest
from datetime import datetime, timezone

from night_sky.data_manager import load_bright_stars
from night_sky.sky_model import SkyModel


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
        self.assertIsInstance(snap, list)
        # If there are visible stars, assert basic ranges
        if len(snap) > 0:
            st = snap[0]
            self.assertTrue(hasattr(st, 'alt_deg'))
            self.assertTrue(hasattr(st, 'az_deg'))
            self.assertGreaterEqual(st.alt_deg, -90.0)
            self.assertLessEqual(st.alt_deg, 90.0)
            # azimuth normalized
            az_norm = st.az_deg % 360.0
            self.assertGreaterEqual(az_norm, 0.0)
            self.assertLess(az_norm, 360.0)


if __name__ == '__main__':
    unittest.main()
