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

        # Moon info should be present
        self.assertIsNotNone(snap.moon)
        if snap.moon:
            self.assertTrue(hasattr(snap.moon, 'phase_fraction'))
            self.assertGreaterEqual(snap.moon.alt_deg, -90.0)
            self.assertLessEqual(snap.moon.alt_deg, 90.0)
            self.assertGreaterEqual(snap.moon.phase_fraction, 0.0)
            self.assertLessEqual(snap.moon.phase_fraction, 1.0)

    def test_limiting_magnitude_filters_catalog(self):
        sm = SkyModel(limiting_magnitude=-5.0)
        snap = sm.compute_snapshot(0.0, 0.0, datetime.now(timezone.utc))
        self.assertLessEqual(len(snap.visible_stars), 5)
        # refraction toggle should not raise
        sm = SkyModel(limiting_magnitude=6.0, apply_refraction=True)
        snap = sm.compute_snapshot(0.0, 0.0, datetime.now(timezone.utc))
        self.assertIsInstance(snap.visible_stars, list)

    def test_filter_helper(self):
        catalog = [
            {'id': 1, 'name': 'A', 'ra_deg': 0, 'dec_deg': 0, 'mag': 1.0},
            {'id': 2, 'name': 'B', 'ra_deg': 0, 'dec_deg': 0, 'mag': 7.0},
        ]
        filtered = SkyModel._filter_catalog_by_mag(catalog, 2.0)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]['id'], 1)


if __name__ == '__main__':
    unittest.main()
