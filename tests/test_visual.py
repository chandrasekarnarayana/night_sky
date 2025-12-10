import hashlib
from pathlib import Path

from PyQt5 import QtWidgets
from PIL import Image, ImageChops
from datetime import datetime, timezone

import sys

from night_sky.sky_model import SkyModel
from night_sky.sky_view_2d import SkyView2D


def rms_diff(img1: Image.Image, img2: Image.Image) -> float:
    diff = ImageChops.difference(img1, img2)
    h = diff.histogram()
    squares = (value * ((idx % 256) ** 2) for idx, value in enumerate(h))
    sum_of_squares = sum(squares)
    rms = (sum_of_squares / float(img1.size[0] * img1.size[1])) ** 0.5
    return rms


def test_visual_regression_2d(tmp_path):
    if sys.platform.startswith("win") or sys.platform.startswith("darwin"):
        # Qt offscreen differs on Windows/macOS; limit visual regression to Linux for now.
        import pytest
        pytest.skip("Visual regression checked on Linux only")
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    sm = SkyModel(limiting_magnitude=6.0)
    snap = sm.compute_snapshot(0.0, 0.0, datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc))
    view = SkyView2D()
    view.update_sky(snap.visible_stars, snap.visible_planets, snap.deep_sky_objects)
    out = tmp_path / "current.png"
    view.export_png(out, width=300, height=300)

    ref_path = Path("tests/fixtures/ref_2d.png")
    assert ref_path.exists(), "Reference image missing"
    cur = Image.open(out).convert("RGB")
    ref = Image.open(ref_path).convert("RGB")
    if cur.size != ref.size:
        # normalize sizes across platforms/render backends
        cur = cur.resize(ref.size)
    rms = rms_diff(cur, ref)
    # allow small differences (fonts/platform)
    assert rms < 15.0, f"Visual regression detected (rms={rms})"
