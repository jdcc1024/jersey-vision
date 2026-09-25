# CLAUDE.md

Working notes for AI assistants (and humans) on this repo. See README.md for the overview.
**To create or edit a garment model, use the `garment-model` skill** (`.claude/skills/garment-model/`).

## Invariants: do not break these
- **UV space = the garment's sewing template** (`garments/<slug>/template.png`). Every UV is a template pixel:
  Blender `((px+.5)/W, 1-(py+.5)/H)`, glTF/three.js `v = (py+.5)/H` (textures use `flipY = false`).
  Anything that touches geometry must keep this 1:1 mapping.
- **glTF axes:** Y-up, metres, **front faces +Z**, wearer's left = +X, model centred on the origin.
  (Blender side: front = −Y, Z-up, neck point at z = 0 during the build.)
- **Pieces are drawn as seen from outside** (front from the front, back from behind); otherwise `"flip": true`.
- **One mesh, one material per garment.** Consumers swap `material.map` and nothing else.
- **The cloth rest shape is the flat pattern** (shape key `Flat`) so the model matches the template's real size.
- **`out/` is generated.** Change `garment.json` and re-run; never hand-edit models or manifests.

## Pipeline
- Python half: `python pipeline/gk.py <cmd> <garment>` (`new, rasterize, inspect, pattern, seammap, body,
  texture, prep, check, compare, register`). Plain Python, deps in `pipeline/requirements.txt`. Writes
  `garments/<g>/build/` (git-ignored) and `out/texture.png`, `out/manifest.json`.
- Blender half: `pipeline/blender/run.py` (or `sim.py`, `finish.py`, `export.py` separately).
  `blender -b --python pipeline/blender/run.py -- <garment>`, or exec in a live Blender with
  `{'__file__': path, 'GARMENT': slug}`. `sim.py` clears the scene. The cloth cache resets if `GarmentSim`
  is modified between frame steps.
- Everything the Blender half needs is resolved into `build/pattern.json` by `pattern.py`, so the Blender
  scripts stay generic. New garment behaviour goes into the spec → pattern.py → sim.py/finish.py.
- After engine changes: `python pipeline/tests/run_engine_tests.py` (crew-tee + fixtures), and rebuild
  crew-tee to check it still matches `docs/images/compare_to_mockup.png`.
- glTF exporter kwargs differ between Blender 4.x and 5.x; use `gk_blender.gltf_kwargs()`.

## Web (web/index.html)
- Single file, no bundler. three.js from jsDelivr via an import map pinned to `three@0.170.0`; keep it in
  sync with `package.json` (the test serves three from `node_modules`).
- Reads `garments/index.json` → `<garment>/out/manifest.json` (template size, pieces, model file, sample
  graphic). `#<slug>` in the URL selects a garment. `npm run build:artifact` inlines index, manifests and
  GLBs into `dist/jersey-proof.html` (artifact fragment; the artifact CSP allows only cdnjs/jsDelivr/unpkg
  scripts, Google Fonts, no downloads started by the page).
- Print compositing: 2D canvas (`TEX_SCALE` px per template px) as a `CanvasTexture`; layers are
  `{x, y, w, h, rot, flip}` in template px (x, y = centre); the UI shows mm (`MMPP`).
- Test hooks `window.__jersey()`, `window.__layers()`; run `npm test` after UI changes (headless Chromium
  needs `--use-angle=swiftshader`; `PW_CHROMIUM` points at a browser binary). Must work at 400 px and in
  both themes (CSS tokens).

## Commits
- Commit `garments/<slug>/` (spec, template, references, out/) but not `build/`, `dist/`, `web/tests/output/`.
- Re-export all of a garment's `out/` files together.
