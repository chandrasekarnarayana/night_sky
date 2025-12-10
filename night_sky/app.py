"""Application entrypoint for Night Sky Viewer.

Expose a single ``run`` function so both ``python -m night_sky`` and the
console script entry point can start the GUI consistently.
"""
from __future__ import annotations

import sys
from typing import Sequence

from PyQt5 import QtWidgets, QtCore

from .main_window import MainWindow


def _apply_dark_theme_if_available(app: QtWidgets.QApplication) -> None:
    """Apply a dark theme if ``qdarkstyle`` is installed."""
    try:
        import qdarkstyle  # type: ignore

        app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
    except Exception:
        # No-op if qdarkstyle is not installed or applying fails
        pass


def run(argv: Sequence[str] | None = None) -> int:
    """Start the Qt application and return its exit code."""
    args = sys.argv if argv is None else list(argv)
    # Prefer software OpenGL to avoid driver crashes/segfaults on systems without stable GL.
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseSoftwareOpenGL, on=True)
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(args)
    _apply_dark_theme_if_available(app)

    window = MainWindow()
    window.show()
    return int(app.exec_())


if __name__ == "__main__":
    raise SystemExit(run())
