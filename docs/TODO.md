# Night Sky TODO / Roadmap (prioritized)

## P1 — Shipping polish & scientific authenticity
- Installers/bundles: Windows (MSI/EXE via PyInstaller/cx_Freeze), macOS (.app/.dmg), Linux (AppImage/Flatpak); ensure data files packaged; signing/notarization hooks.
- Visual regression harness: reference PNGs for 2D/3D key scenes; CI diff with tolerance; render benchmark.
- Milky Way & horizon: replace placeholder band with real texture; gradient/twilight hues; optional panorama/landscape import.
- 3D picking: use camera projection math for accurate hit-testing.
- Ephemeris: prompt/download DE kernels; toggle accuracy; document scientific assumptions; add basic aberration/precession toggles surfaced in UI.
- Supply real Milky Way/panorama assets for users or bundle defaults, and consider mirroring overlays in 3D once textures are available.

## P2 — Interaction & planning depth
- Search/go-to: fuzzy search + smooth center in 2D/3D; autocomplete; hotkey.
- Time controls: scrubber/time-lapse with rate control; events pane (rise/set/culmination) visible by default; keyboard shortcuts (←/→, space, +/-).
- FOV overlays & grids: telescope/eyepiece/camera presets; RA/Dec, Alt/Az, ecliptic, meridian toggles; snap FOV to selected object.
- Event framework: conjunction detector (Moon–planet/planet–planet), eclipse announcements (coarse), meteor shower radiants overlay; optional satellite/ISS passes via TLE ingest and ground tracks.

## P3 — Data & accuracy
- Offer Gaia-derived optional catalog download (LOD aware); cull by mag/FOV; cache projections.
- Expand NGC/IC attributes (size/type/surface-brightness); add constellation names/labels and optional constellation artwork overlays.
- Light pollution/refraction model refinement; extinction/airmass coloring; twilight limiting-mag estimator tied to Bortle slider.

## P4 — Accessibility & i18n
- Font scaling slider; keyboard navigation audit; colorblind-friendly theme preset.
- Translation framework (Qt .ts/.qm or gettext) with at least one additional locale (e.g., fr/ES/de).

## P5 — Extensibility UX
- UI flows for importing user catalogs/constellations/horizons; texture pack support with folder convention.
- Document plugin API and ship sample plugins (custom overlay, custom catalog loader).

## P6 — Docs/help
- Expand offline help with screenshots/tutorials; “How to use your own catalogs” step-by-step; “Best practices for exports/printing”.

## Release readiness checklist
- Bump version, update README (PyPI install) / release notes.
- CI green on Linux/macOS/Windows with wheel build/install smoke tests and visual regression.
- Packages include data assets; optional DE kernel download prompt documented.
- Prepare PyPI release (sdist+wheel) and GitHub release notes; tag and upload when ready.
