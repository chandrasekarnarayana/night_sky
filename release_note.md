# Night Sky 0.4.0 — First Public Release

## Highlights
- Rich catalogs: default bright set plus rich (~108k stars to mag ≤10), Messier + NGC/IC deep-sky data, and custom catalog support.
- Scientific accuracy: optional high-accuracy ephemerides (JPL DE421) for Sun/Moon/planets; refraction, light-pollution, time-scale (UTC/TT) controls; twilight filtering.
- Immersive visuals: 2D Rect/Dome and 3D OpenGL dome (auto-fallback), horizon gradient/compass, optional Milky Way/panorama textures, theme presets (Night, Astro Red, High Contrast), label density and limiting magnitude controls.
- Interactivity: click-to-pick objects with info pane, search/go-to, time scrubber and time-lapse, presets (incl. “Titanic Night”), settings import/export/reset, plugin loader, offline help.
- Exports: high-DPI PNG with labels-as-seen, N/E markers, scale bar, legend, and optional metadata.
- CI/QA: cross-OS CI (Linux/macOS/Windows) with wheel build/install smoke tests; release workflow auto-publishes to PyPI when `PYPI_API_TOKEN` is set.

## Known placeholders / TODO
- Replace Milky Way placeholder with a real texture; add visual regression fixtures and installers (MSI/DMG/AppImage/Flatpak).
- Improve 3D picking precision and smooth search/go-to animation.
- Expand user import UI (catalog/constellation/horizon), document plugin API, add i18n/accessibility (font scaling, colorblind themes, translations).
- High-accuracy ephemeris defaults to off to avoid automatic downloads; consider bundling/prompting for kernels.
