"""Application entrypoint for Night Sky Viewer.

Provides a `run()` function used by the console script and `python -m`.
This function creates a QApplication and shows the main window.
"""
from __future__ import annotations

import sys
from typing import Optional

from PyQt5 import QtWidgets

from .main_window import MainWindow


def _apply_dark_theme_if_available(app: QtWidgets.QApplication) -> None:
    """Apply a dark theme if ``qdarkstyle`` is installed.

    This is optional — if the package is not available the function is
    a no-op.
    """
    try:
        import qdarkstyle  # type: ignore

        # qdarkstyle provides load_stylesheet_pyqt5() for PyQt5
        sheet = qdarkstyle.load_stylesheet_pyqt5()
        app.setStyleSheet(sheet)
    except Exception:
        # No-op if qdarkstyle is not installed or applying fails
        pass


def run(argv: Optional[list[str]] = None) -> None:
    """Start the Night Sky GUI application and enter the Qt event loop.

    This function is the canonical entrypoint for the package and is used
    by the console script entry point (``night-sky``) as well as
    ``python -m night_sky`` (the package-level ``__main__`` delegates to
    this function). The function does not return; it calls ``sys.exit``
    with the Qt application's exit code.

    Parameters
    - argv: Optional list of command-line arguments. Defaults to
      ``sys.argv`` when not provided. The QApplication is created only if
      one does not already exist.
    """
    if argv is None:
        argv = sys.argv

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(argv)

    # Apply optional dark theme if available
    _apply_dark_theme_if_available(app)

    win = MainWindow()
    win.show()

    # Enter the Qt main loop and exit the process with the returned code
    rc = app.exec_()
    sys.exit(int(rc))
import sys
from typing import Sequence
from PyQt5 import QtWidgets

from .main_window import MainWindow


def run(argv: Sequence[str] | None = None) -> int:
    """Run the Night Sky Qt application.

    If `argv` is None, `sys.argv` will be used. Returns the process exit code.
    """
    args = sys.argv if argv is None else list(argv)
    # Create QApplication if not already present
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(args)

    w = MainWindow()
    w.show()
    return app.exec_()


if __name__ == '__main__':
    raise SystemExit(run())
