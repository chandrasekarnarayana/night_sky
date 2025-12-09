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
