---
name: garment-model
description: Build or edit a 3D garment model (jersey, tee, long sleeve, raglan, tank, hockey, baseball, etc.) whose UV map is the customer's sewing template, from a template image/SVG/PDF plus mockup references, using the jersey-vision garmentkit pipeline and Blender. Exports a three.js-ready GLB and registers it in the Jersey 3D Proof viewer.
---

# Garment model from a sewing template

Turn a sublimation sewing template (the flat cut pieces a print shop uses) plus a few mockup
images into a 3D garment whose **UV map is the template itself**: any artwork exported on the
template artboard maps onto the model 1:1. The output is a GLB that three.js loads directly. It
is also registered in the Jersey 3D Proof editor (`web/index.html`).

The pipeline is a spec-driven engine in the jersey-vision repo:

- `garments/<slug>/garment.json` describes the garment:
  - the pieces and their named corners;
  - which edge sews to which;
  - how each piece wraps around the body;
  - hem turn-ups, bands (collars, bindings, cuffs) and inside patches (tapes, labels);
  - fit and cloth settings.
- `pipeline/gk.py` (plain Python) turns the spec into meshes and checks.
- `pipeline/blender/*.py` (Blender 5.x) runs a cloth simulation with sewing springs around an invisible mannequin, finishes the mesh and exports it.

Worked examples:

- **`garments/crew-tee/garment.json`**: set-in short sleeves, crew neck rib, hem turn-ups, neck tape and size tag.
- **`pipeline/tests/fixtures/tank-top/garment.json`**: sleeveless, with armhole bindings.

Read the one closest to the new garment before writing a spec.

## Where things are

The repo root is the folder containing `pipeline/gk.py`. On JCC's machine it is `C:\jdcc\jersey-vision`. If you can't reach it, ask the user to connect that folder.

**Read these before starting:**

- `CLAUDE.md`: the invariants.
- `references/spec-reference.md`: every garment.json field.
- `references/garment-types.md`: how to spec each garment family, and the engine's limits.

**Read when needed:**

- `references/blender.md`: running the Blender half through Blender MCP or on the command line, plus version gotchas.
- `references/troubleshooting.md`: symptom → cause → fix.

## Inputs to collect (ask only for what's missing)

1. **The sewing template.** PNG/JPG with pieces on a flat background colour, or SVG/PDF. Also its scale: mm per pixel, or one known measurement to derive it from, such as body width at the chest.
2. **Mockup references**, front and back at least. These are used for the shape, the arm angle and checking which side is which.
3. **The garment type**, and anything unusual: how collars or bands fold, which half of a strip faces out, hem allowances.
4. **The slug**, e.g. `raglan-ls`. When **editing**, which garment and what should change.

## Workflow

Track these as tasks. Run commands from the repo root.

### 1. Set up
```
python pipeline/gk.py new <slug> --template <file> --refs <front.png> <back.png> --name "<Name>" [--mm-per-px 1]
```
This creates `garments/<slug>/` (template.png, references/, a skeleton garment.json) and runs `inspect`. For SVG/PDF it rasterizes at 2 px/mm and records `mm_per_px`. **Verify the scale** against a known measurement before going further.

### 2. Inspect and understand the pieces
`python pipeline/gk.py inspect <slug>` writes the following to `build/`:

- `inspect.png`, plus zoomed crops `inspect_<n>.png`;
- `inspect.json`: component bboxes, an inside point, corner candidates and extremes (`top_center` is the sleeve-cap peak).

Look at the images. For each piece decide:

- **What it is.** Front, back, sleeve, yoke, gusset, band strip, tape or label.
- **Which way it is drawn.** Panels must be drawn *as seen from outside*: the front as seen from the front, the back as seen from behind. Set `"flip": true` for a piece drawn from the inside.
- **Which side is the wearer's left.**
  - On the front piece, the wearer's left is image-right.
  - On the back piece, the wearer's left is image-left.
  - For sleeves, check the mockups (for example, which colour sits on which arm) and decide which half of each sleeve faces the front.
- **Where the corners are.** Name every point where an edge changes meaning: neck point, shoulder point, underarm, hem corners, fold line ends, sleeve-cap peak. A corner can sit mid-curve (the cap peak); it only needs to divide seams.
- **Allowances.** Hem allowances (a flared strip mirroring the taper, like the tee's sleeve hem) become `turnups`. Strips become `bands`. Printed-inside rectangles (tapes, size tags) become `patches`.

### 3. Write garment.json
- **Sim pieces:** `at`, `corners`, `outline` (corner loop), `straight` edges and `place`.
- **`seams`:** pairs of `[piece, from_corner, to_corner]`. Point k of `a` sews to point k of `b`, so **both must run in the same physical direction** (e.g. both from underarm to hem).
- **Band loops:** ordered, closed, and each segment joined to the next by a seam.
- Copy the patterns from the examples and the spec reference.

Then run:
```
python pipeline/gk.py pattern <slug>     # prints seam lengths (ratio > 1.12 is flagged) and open edges
python pipeline/gk.py seammap <slug>     # build/seam_map.png
```
Before the checkpoint, fix everything the report flags:

- **Seam length mismatch.** A sleeve cap is normally 3–6% longer than its armhole, which is ease. Beyond about 12% the wrong segment was probably picked.
- **Open edges that should be sewn.** The opposite, a seam that should stay open, is also possible.
- **Band loops that don't meet.**

### 4. CHECKPOINT: show the seam map and wait for approval
Show the user `build/seam_map.png`, for example with SendUserFile or by viewing it. Then summarise in a short list:

- which piece is which, and how it wraps (torso front/back arcs, which sleeve is the wearer's left and which half faces front);
- each seam (the numbered legend) and any length mismatches;
- open edges (hems, openings) and what finishes them;
- turn-ups, bands (fold, which half faces out) and patches;
- every **assumption** you made.

**Stop and wait for the user to approve or correct.** This is the one checkpoint. Wrong seams or sides waste a simulation and produce a subtly wrong model.

### 5. Build
```
python pipeline/gk.py body <slug>       # mannequin sized from the pattern (fit/arm pose from spec.body)
python pipeline/gk.py texture <slug>    # sample print with bleed -> out/texture.png
```
(`gk.py prep` runs pattern + seammap + body + texture in one go.)

Then run the Blender half:

- **Blender MCP**, with the user's live Blender: `exec` `pipeline/blender/run.py` with globals `{'__file__': <path>, 'GARMENT': '<slug>'}`. Split long sims across calls: run `STEPS=('sim',)`, then step frames in chunks of about 40, then `STEPS=('finish','export')`. See `references/blender.md`.
- **Command line:** `blender -b --python pipeline/blender/run.py -- <slug>`.

The run writes `out/model.glb`, `out/model_untextured.glb`, `out/model.blend`, `out/render_front.png` and `out/render_back.png`. `sim.py` clears the Blender scene, so tell the user before running it in their live session if they have other work open.

### 6. Verify (don't skip)
```
python pipeline/gk.py check <slug>      # UVs in 0..1, one mesh, double-sided, scale ratio ~1.0 -> build/uv_check.png
python pipeline/gk.py compare <slug>    # references next to renders -> build/compare.png
```
Look at both images:

- **`uv_check.png`:** the mesh must cover each piece exactly.
- **`distortion.png`:** the colours should be even, mostly green, with no speckle. Speckle means text will look wavy. `check` fails when `neighbour_jump_p50` is above 0.05; it should be under 0.02.
- **`compare.png`:** designs land in the same places as the mockups, the sides are right (e.g. left sleeve colour), and the silhouette and arm angle are plausible.

Also check `finish` output: `max_seam_gap_mm` should be under about 5.

**If the result is off,** adjust the spec and re-run from the step that changed:

- fit (`body.fit_ease_mm`, `chest_circ_mm`);
- pose (`body.arm_angle_deg`);
- cloth (`sim.bending`, `sim.gravity`);
- collar (`lean_deg`).

`references/troubleshooting.md` maps symptoms to fixes.

### 7. Register, test, commit
```
python pipeline/gk.py register <slug>   # out/manifest.json + garments/index.json (viewer garment picker)
npm test                                # Playwright smoke test of the viewer
python pipeline/tests/run_engine_tests.py
```
Optionally add `viewer.sample_graphic` and `viewer.notes` to the spec, then re-register. Commit:

- **Include:** `garments/<slug>/` (garment.json, template, references, out/).
- **Leave out:** `build/`, which is ignored.

Rebuild the published page with `npm run build:artifact` if the artifact should include the new garment.

## Editing an existing garment
- **Fit, pose, drape, collar:** change `body` / `sim` / `bands[].lean_deg` in its garment.json. Re-run body (if body changed), then the Blender run, then check / compare / register.
- **Corrected template (same layout):** replace template.png, re-run `inspect`, update any corner that moved, then run the full workflow including the checkpoint.
- **New piece, band or patch:** edit the spec, then pattern → seammap → **checkpoint** → build.
- Never hand-edit files in `out/`. They are regenerated.

## Invariants (see CLAUDE.md)
- **UV = template pixel.** Blender `((px+.5)/W, 1-(py+.5)/H)`; glTF v is top-down, so three.js textures use `flipY = false`. Never move UVs off the template.
- **glTF axes:** Y-up, metres, front faces +Z, wearer's left +X, centred on the origin. Blender side: front = −Y.
- **One mesh, one material** (double-sided), UV set `TEXCOORD_0`, object name from `export.object_name`.
- **The cloth rest shape is the flat pattern** (shape key `Flat`), so fabric keeps the template's real size. `check` flags a scale mismatch.

## When the engine can't express a garment
The three placement types are `torso` (arc of an ellipse), `arm` (cone around an arm) and `flat` (a plane anywhere). Finishing covers turn-ups, bands and patches. Some construction is not covered yet:

- collars that stand as a separate shaped piece (polo, baseball collar band);
- button plackets with an overlap;
- hoods;
- pieces on the lower body.

Say so, propose the smallest engine extension (new placement type, new band mode), and ask before implementing it. When you implement one:

- add a fixture under `pipeline/tests/fixtures/`;
- run `run_engine_tests.py`;
- document the new field in `references/spec-reference.md`.
