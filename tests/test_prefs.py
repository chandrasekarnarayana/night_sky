import unittest
import os
from pathlib import Path

from night_sky import prefs


class TestPrefs(unittest.TestCase):
    def setUp(self):
        # Use the real config path but back it up if exists
        self.config_path = prefs.CONFIG_PATH
        self.backup_path = None
        if self.config_path.exists():
            self.backup_path = self.config_path.with_suffix('.bak')
            self.config_path.replace(self.backup_path)

    def tearDown(self):
        # Remove config created during test
        try:
            if self.config_path.exists():
                self.config_path.unlink()
        except Exception:
            pass
        # Restore backup
        if self.backup_path and self.backup_path.exists():
            self.backup_path.replace(self.config_path)

    def test_save_and_load_prefs_roundtrip(self):
        test_prefs = {
            'show_star_labels': False,
            'show_planet_labels': True,
            'show_constellations': False,
        }
        prefs.save_prefs(test_prefs)
        loaded = prefs.load_prefs()
        self.assertIsInstance(loaded, dict)
        self.assertEqual(bool(loaded.get('show_star_labels')), False)
        self.assertEqual(bool(loaded.get('show_planet_labels')), True)
        self.assertEqual(bool(loaded.get('show_constellations')), False)


if __name__ == '__main__':
    unittest.main()
