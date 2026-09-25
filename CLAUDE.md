# CLAUDE.md

Working notes for AI assistants (and humans) on this repo. See README.md for the overview.

## Invariants — do not break these
- **UV space = the sewing template.** `assets/template/template.png` is 1656 × 790 px and 1 px = 1 mm. Every UV is a template pixel: Blender `((px+.5)/1656, 1-(py+.5)/790)`, glTF/three.js `v = (py+.5)/790` (so textures use `flipY = false`). Anything that moves UVs must keep this 1:1 mapping.
- **glTF axes:** Y-up, **front faces +Z**, wearer's left = +X, model centred on the origin, metres. (Blender side: front = −Y, Z-up.)
- **Orientation of pieces on the template:**
  - The front piece is drawn as seen from the front, and the back piece as seen from behind.
  - Sleeve L (top sleeve on the template, pink) is the wearer's left. Its image-left half joins the front armhole.
  - Sleeve R is the wearer's right. Its image-right half joins the front armhole.
- **Single mesh, single material.** Consumers swap `material.map` and nothing else, so keep it that way unless there is a strong reason.

## Web (web/index.html)
- A single file with no bundler. three.js comes from jsDelivr via an import map pinned to `three@0.170.0`. Keep that pin in sync with `package.json` (the test serves three from `node_modules`).
- The same file is published as a Claude artifact: `npm run build:artifact` inlines the GLB as base64 into `dist/jersey-proof.html` and strips the html/head/body wrapper.
  - Artifact CSP: scripts only from cdnjs, jsDelivr or unpkg, fonts only from Google Fonts, no downloads started by the page.
- Print compositing is a 2D canvas at `TEX_SCALE` px/mm, used as a `CanvasTexture`.
  - The base print is drawn first, then graphic layers `{x, y, w, h, rot, flip}` in template mm (x, y = centre).
- Test hooks: `window.__jersey()` and `window.__layers()`, used by `web/tests/smoke.mjs`.
- Always run `npm test` after UI changes. Headless Chromium needs `--use-angle=swiftshader`. Set `PW_CHROMIUM` to point at a local browser binary.
- The page must work at 400 px width and in both light and dark themes. Colours come from CSS tokens.

## Pipeline
- `pipeline/prep/*` runs in normal Python (see `pipeline/requirements.txt`) and writes `pipeline/build/`, which is git-ignored and regenerable. It is deterministic: re-running reproduces the same `pattern.json`.
- `pipeline/blender/*` runs in Blender 5.2+. Scripts find the repo root from `__file__`, or from `JERSEY_ROOT` if set.
  - From a live Blender (e.g. Blender MCP), exec a script with `{'__file__': <path>}` in its globals.
  - The cloth cache is only valid while the `JerseySim` object is untouched. Step 02 moves it, so re-run step 01 plus the sim before re-running step 02.
- The glTF exporter's keyword names changed in Blender 5 (e.g. `export_texcoords`). Check `bpy.ops.export_scene.gltf.get_rna_type().properties` when upgrading.

## Commits
- Keep generated files out of git (`dist/`, `pipeline/build/`, `web/tests/output/`).
- Committed binaries: `assets/model/*.glb`, `assets/model/jersey.blend`, and images in `assets/` and `docs/`. When you regenerate the model, re-export all three model files together.
