import os
import subprocess
import sys


def test_export_view_to_png(tmp_path):
    """Run export in a fresh process to isolate Qt state."""
    out_file = tmp_path / "export.png"
    script = f"""
from PyQt5 import QtWidgets
from night_sky.sky_view_2d import SkyView2D
from night_sky.sky_model import Star
from night_sky.export import export_view_to_png
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
view = SkyView2D()
view.update_sky([Star(id=1, name='Test', ra_deg=0.0, dec_deg=0.0, mag=1.5, alt_deg=45.0, az_deg=180.0)], [])
export_view_to_png(view, r\"\"\"{out_file}\"\"\", size=300)
"""
    env = os.environ.copy()
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    result = subprocess.run([sys.executable, "-c", script], env=env)
    assert result.returncode == 0
    assert out_file.exists()
    assert out_file.stat().st_size > 0
