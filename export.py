from PyQt5.QtGui import QPixmap


def export_widget_to_png(widget, filename: str, size: int = 2000):
    """Export the given widget to a PNG file at approximately `size` pixels square.

    This uses QWidget.grab() and scales to the requested size.
    """
    pm: QPixmap = widget.export_pixmap()
    # scale while preserving aspect
    pm = pm.scaled(size, size)
    pm.save(filename, 'PNG')
