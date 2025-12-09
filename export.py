from PyQt5.QtGui import QPixmap, QPainter, QColor, QFont
from PyQt5.QtWidgets import QWidget
from typing import Any

from .settings import DEFAULTS


def export_view_to_png(view: Any, filename: str, size: int = None) -> None:
    """Export a supported view to a PNG file.

    Supported view interfaces (in priority order):
    - view.export_png(path, width=..., height=...): call directly
    - view.plot (pyqtgraph PlotWidget): grab `view.plot.grab()`
    - view.glview (pyqtgraph GLViewWidget): grab framebuffer via `glview.grabFramebuffer()`

    If labels/overlays are present and the view does not composite them itself,
    this function will attempt to draw simple text labels on top of the captured
    image using the view's `_stars_cache` and `_planets_cache` when available and
    `view.show_star_labels` / `view.show_planet_labels` flags.

    Parameters
    - view: object representing a view widget
    - filename: output PNG path
    - size: desired pixel size (square). If None, uses DEFAULTS['export_default_size']
    """
    if size is None:
        size = int(DEFAULTS.get('export_default_size', 2000))

    # 1) If the view can export itself, prefer that
    try:
        if hasattr(view, 'export_png'):
            # call with width/height keywords if supported
            try:
                view.export_png(filename, width=size, height=size)
            except TypeError:
                # fallback: positional
                view.export_png(filename, size, size)
            return
    except Exception:
        # If view.export_png raised, fall back to manual capture
        pass

    pm: QPixmap = None

    # 2) Plot-based capture (2D)
    if hasattr(view, 'plot') and isinstance(view.plot, QWidget):
        try:
            pm = view.plot.grab()
        except Exception:
            pm = None

    # 3) GLView capture
    if pm is None and hasattr(view, 'glview'):
        try:
            # glview.grabFramebuffer() returns a QImage/QPixmap
            img = view.glview.grabFramebuffer()
            # If QImage, convert to QPixmap
            if hasattr(img, 'toImage'):
                pm = QPixmap.fromImage(img)
            else:
                pm = img
        except Exception:
            pm = None

    if pm is None:
        raise RuntimeError('Unable to capture view for export')

    # Scale to requested size while keeping aspect ratio
    pm = pm.scaled(size, size)

    # Composite simple labels if available and not already handled
    try:
        need_labels = False
        if hasattr(view, 'show_star_labels') and getattr(view, 'show_star_labels'):
            need_labels = True
        if hasattr(view, 'show_planet_labels') and getattr(view, 'show_planet_labels'):
            need_labels = True

        if need_labels:
            painter = QPainter(pm)
            painter.setPen(QColor(255, 255, 255))
            font = QFont()
            font.setPointSize(max(8, int(size / 250)))
            painter.setFont(font)

            w = pm.width()
            h = pm.height()
            # Simple dome projection fallback: map alt/az to image coordinates
            def project(alt, az):
                import math
                az_rad = math.radians(az)
                r = max(0.0, min(1.0, (90.0 - alt) / 90.0))
                x = r * math.sin(az_rad)
                y = r * math.cos(az_rad)
                cx = w / 2.0
                cy = h / 2.0
                scale = 0.45 * min(w, h)
                px = int(cx + scale * x)
                py = int(cy - scale * y)
                return px, py

            # Draw planet labels first (higher priority)
            if hasattr(view, '_planets_cache') and getattr(view, '_planets_cache'):
                for p in view._planets_cache:
                    try:
                        px, py = project(p.alt_deg, p.az_deg)
                        painter.setPen(QColor(255, 220, 80))
                        painter.drawText(px + 6, py - 6, str(p.name))
                    except Exception:
                        continue

            # Then bright stars
            if hasattr(view, '_stars_cache') and getattr(view, '_stars_cache'):
                for s in view._stars_cache:
                    try:
                        if getattr(s, 'mag', 99.0) < float(DEFAULTS.get('mag_label_threshold', 2.0)):
                            px, py = project(s.alt_deg, s.az_deg)
                            painter.setPen(QColor(220, 220, 255))
                            painter.drawText(px + 6, py - 6, str(s.name))
                    except Exception:
                        continue

            painter.end()
    except Exception:
        # Non-fatal: proceed without compositing labels
        pass

    pm.save(filename, 'PNG')
