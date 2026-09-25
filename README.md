# Jersey Vision

A 3D model of a sublimated jersey whose **UV map is the sewing template** used to cut and print the real shirts, plus **Jersey 3D Proof**, a three.js tool for placing artwork on the template and checking it on the 3D model.

![Mockups vs. model](docs/images/compare_to_mockup.png)

*Reference mockups (1st, 3rd) next to renders of the model (2nd, 4th).*

## Quick start

```bash
npm install
npm run serve            # http://localhost:5173/web/
```

- **Try the tool:**
  - Open the page and drag the sample graphic on the print layout.
  - Add your own PNG with **Add graphic**.
  - Turn on **Place on model** and drag on the jersey itself.
- **Test:** `npm test` runs a headless end-to-end smoke test with Playwright. Run `npx playwright install chromium` once before the first test.
- **Build the single-file page:** `npm run build:artifact` writes `dist/jersey-proof.html`, the version published as the Claude artifact, with the model inlined.

## Repository layout

| Path | What it is |
|---|---|
| `assets/template/template.png` | The sewing template, 1656 × 790 px, 1 px = 1 mm. **This is the UV space.** |
| `assets/template/jersey_texture.png` | Sample print: the template with its colours bled past the cut lines |
| `assets/model/jersey.glb` | three.js-ready model with the sample print embedded (12.6k verts, 24.4k tris) |
| `assets/model/jersey_untextured.glb` | Same mesh and material, with no image |
| `assets/model/jersey.blend` | Blender scene: final `Jersey` mesh, hidden `Mannequin`, camera and lights |
| `web/index.html` | Jersey 3D Proof, a single page with no build step (three.js from jsDelivr via an import map) |
| `web/tools/` | `serve.mjs` (dev server), `build-artifact.mjs` (single-file build) |
| `web/tests/` | Playwright smoke test and its fixtures |
| `pipeline/prep/` | Plain-Python steps: template → panel meshes, mannequin, sample texture |
| `pipeline/blender/` | Blender steps: cloth sim with sewing, finishing, export (`run_all.py` does all three) |
| `pipeline/tools/check_glb.py` | Reads a GLB back, reports mesh and UV facts, draws its UVs over the template |
| `docs/` | Renders, the UV check image, and the reference mockups |

## The model

- Units are metres and glTF is Y-up. **The front faces +Z**, the back faces −Z, and the wearer's left is +X. The bounding box is centred on the origin, about 76 × 76 × 31 cm.
- One mesh (`Jersey`), one material (`JerseyPrint`, double-sided), one UV set (`TEXCOORD_0`).
- Pieces:
  - front and back;
  - sleeve L (wearer's left) and sleeve R;
  - folded neck rib;
  - inner neck tape (inside the back neck);
  - size tag (inside, reads correctly from inside).
- Seams are welded for smooth shading. UV seams stay split, as glTF requires.
- **Sleeve hem allowance:** the flared bottom 25 mm of each sleeve piece is turned up inside the sleeve.
- **Neck rib:**
  - The 60 mm strip folds in half to a 30 mm collar.
  - The lower half of the strip (the edge with the LEFT / FRONT / RIGHT labels) is the outside face.
  - The strip runs LEFT → FRONT → RIGHT → BACK → LEFT around the neckline.

### UV convention

A template pixel `(px, py)` maps to Blender UV `((px + 0.5) / 1656, 1 − (py + 0.5) / 790)`. In glTF and three.js, `v` runs top-down, so a texture made from the template must use `flipY = false`:

```js
const gltf = await new GLTFLoader().loadAsync('jersey.glb');
const jersey = gltf.scene.getObjectByName('Jersey');
const tex = await new THREE.TextureLoader().loadAsync('design.png');   // full template artboard
tex.flipY = false;
tex.colorSpace = THREE.SRGBColorSpace;
jersey.material.map = tex;
jersey.material.needsUpdate = true;
```

- **Artboard:** export artwork on the full template artboard, at any resolution with the 1656 : 790 ratio.
- **Bleed:** extend the artwork 3–5 mm past every cut line. Otherwise texture filtering pulls in the grey artboard background as thin lines along the seams.

## Rebuilding the model

```bash
pip install -r pipeline/requirements.txt
python pipeline/prep/pattern.py        # template -> pipeline/build/pattern.json (panel meshes, matched seam samples)
python pipeline/prep/body.py           # mannequin collider -> pipeline/build/body.json
python pipeline/prep/make_texture.py   # sample print -> assets/template/jersey_texture.png
blender --background --python pipeline/blender/run_all.py   # sim + finish + export -> assets/model/
python pipeline/tools/check_glb.py     # verify; writes pipeline/build/uv_layout_check.png
```

**What each Blender step does:**
- The pattern pieces are wrapped around the mannequin.
- The cloth rest shape is the flat pattern (shape key `Flat`), so the fabric keeps the template's true dimensions.
- Sewing springs close the seams during a 90-frame sim.
- Step 02 welds the seams, applies Taubin smoothing, then adds the hem turn-ups, collar, neck tape and size tag.
- Step 03 exports both GLBs and the `.blend`.

The pipeline was built with Blender 5.2.2 (through Blender MCP). One full run takes about a minute.

**Settings you can change:**
- **Fit and arm angle:** the `ak` / `bk` cross-sections and `ang` in `pipeline/prep/body.py`.
- **Cloth:** bending 2.0, gravity 0.6 and sewing force 10 in `jersey_01_setup_sim.py`.
- **Finishing:** `COLLAR_LEAN_DEG` (28°) and `SMOOTH_ITERS` (12) in `jersey_02_finish.py`.
- **Mesh density:** `EDGE` in `pattern.py` (12 mm; 9 mm roughly doubles the triangle count).
- **Seam allowance:** none is removed. If the cut lines include allowance, the outer 6–10 mm of each piece is really hidden in the seam.

## Open questions

- Does the template include seam allowance?
- Which half of the neck strip faces out?
- The inner neck tape (367 mm) is longer than the back neckline. It is currently modelled running about 80 mm along each shoulder seam.
- A size range (S–3XL) needs one template per size. `pattern.py` has per-template corner coordinates.
