"""OpenGL detection and diagnostic utilities for v0.3.

Provides runtime checks for OpenGL availability and helpful error messages
when 3D rendering is not available.
"""

import os
from typing import Tuple


def opengl_available() -> bool:
    """Detect whether OpenGL 3D rendering is available and usable.

    Attempts to:
    1. Import pyqtgraph.opengl
    2. Create a QOpenGLContext and QSurfaceFormat to test GPU binding

    Returns True if successful, False otherwise.
    """
    if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        # Avoid heavy GL probing in headless test environments
        return False
    try:
        # Try importing pyqtgraph.opengl
        import pyqtgraph.opengl as gl  # noqa: F401
        
        # Try creating an OpenGL context
        from PyQt5.QtGui import QOpenGLContext, QSurfaceFormat
        
        fmt = QSurfaceFormat()
        fmt.setVersion(2, 0)
        ctx = QOpenGLContext()
        ctx.setFormat(fmt)
        if not ctx.create():
            return False
        return True
    except Exception:
        return False


def explain_failure() -> str:
    """Return a user-friendly explanation of why OpenGL is not available.

    If opengl_available() returns False, this provides likely reasons and
    troubleshooting suggestions.
    """
    return (
        "OpenGL 3D rendering is not available on this system.\n\n"
        "Common causes:\n"
        "  • Missing or outdated GPU drivers (NVIDIA, AMD, Intel)\n"
        "  • Running over SSH without X11 GL forwarding\n"
        "  • Conflicting libraries in conda/virtualenv\n"
        "    (Try: conda install -c conda-forge libstdcxx-ng mesa-libgl)\n"
        "  • Running in a container without GPU passthrough\n\n"
        "The app will use 2D-only mode. If you need 3D, check your drivers."
    )
