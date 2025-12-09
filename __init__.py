"""Top-level package for Night Sky Viewer.

Expose a small public surface for consumers and tooling. Access the
package version via ``night_sky.__version__``. Submodules such as
``night_sky.app`` and ``night_sky.sky_model`` can be imported using
``import night_sky.app`` or ``from night_sky import sky_model``.
"""

__all__ = ["__version__", "app", "sky_model"]

# Keep version in one place; update here when releasing.
__version__ = "0.3.0"
