# Night Sky 0.4.0 — First Public Release

Highlights:
- Rich catalogs: default bright set plus rich (~108k stars to mag ≤10), Messier + NGC/IC deep-sky data, and custom catalog support.
- Scientific accuracy: optional high-accuracy ephemerides (JPL DE421) for Sun/Moon/planets; refraction, light-pollution, and time-scale (UTC/TT) controls; twilight filtering.
- Immersive visuals: 2D Rect/Dome and 3D OpenGL dome (auto-fallback), horizon gradient/compass, Milky Way placeholder band, theme presets (Night, Astro Red, High Contrast), label density and limiting magnitude controls.
- Interactivity: click-to-pick objects with info pane, popular sky presets (including “Titanic Night”), settings import/export/reset, plugin loader for extensions.
- Exports: high-DPI PNG with labels-as-seen, N/E markers, scale bar, legend, and optional metadata.
- CI/QA: cross-OS CI (Linux/macOS/Windows) with wheel build/install smoke tests.

Known placeholders / TODO:
- Replace Milky Way placeholder with a real texture; add visual regression tests and installers (MSI/DMG/AppImage).
- Improve 3D picking precision and add search/go-to animation smoothness.
- Expand user import UI (catalog/constellation/horizon), document plugin API, and add i18n/accessibility (font scaling, colorblind themes, translations).
- High-accuracy ephemeris defaults to off to avoid automatic downloads; consider bundling/prompting for kernels.
