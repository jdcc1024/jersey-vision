# Running the Blender half

Tested with Blender 5.2 (the pipeline also runs in the Python `bpy` 4.2 module). One tee build is
~1 minute on a 20-thread desktop, ~2 minutes on 2 cloud cores.

## Command line (simplest)
```
blender --background --python pipeline/blender/run.py -- crew-tee
```
`run.py` = `sim.py` (clears the scene, builds mannequin + panels + cloth) → step all frames →
`finish.py` (weld, smooth, turn-ups, bands, patches, material) → `export.py` (GLBs, renders,
.blend). Each script can also be run alone with the same `-- <garment>` argument.

## Live Blender through Blender MCP
Blender must be running with the MCP add-on server started (the add-on panel's "Start MCP
server"); if `execute_blender_code` can't connect, ask the user to start it. Background/CLI MCP
tools need `BLENDER_PATH` set; prefer the live session.

Blender reads files from the user's disk, so the garment folder (with `build/pattern.json`,
`build/body.json`, `out/texture.png`) must exist **on that machine** under the repo. Then:
```python
p = r"C:\jdcc\jersey-vision\pipeline\blender\run.py"
exec(compile(open(p).read(), p, "exec"), {"__file__": p, "GARMENT": "crew-tee", "STEPS": ("sim",)})
```
then in follow-up calls (keeps each call short; the cloth cache persists between calls):
```python
... {"__file__": p, "GARMENT": "crew-tee", "STEPS": ("frames",), "FRAMES": (1, 45)}
... {"__file__": p, "GARMENT": "crew-tee", "STEPS": ("frames",), "FRAMES": (46, 90)}
... {"__file__": p, "GARMENT": "crew-tee", "STEPS": ("finish", "export")}
```
Frames must be stepped in order. Anything that moves or edits `GarmentSim` between chunks resets
the cloth cache (you'll see the finish step produce the *initial* unsimulated shape). If that
happens, rerun from `("sim",)`.

`sim.py` deletes every object in the open scene. Warn the user first if their session has other
work; the finished model is always saved to `out/model.blend` by `export.py`.

Quick visual checks while iterating (Workbench, fast):
```python
q = r"C:\jdcc\jersey-vision\pipeline\blender\preview.py"
exec(compile(open(q).read(), q, "exec"), {"__file__": q, "GARMENT": "crew-tee", "TAG": "try1",
     "VIEWS": ["front", "back", "side", "q34"], "SHOW_BODY": False})
```
→ `garments/<g>/build/previews/try1_<view>.png`. Right after `("sim",)` this shows the initial
placement; check nothing starts inside the mannequin (`SHOW_BODY: True`).

## "Permission denied" when Blender writes into out/
Files created on the user's disk by another tool (e.g. extracted or copied from a Cowork shell /
cloud workspace) can be read-only to the Windows Blender process. If `export.py` fails with
`PermissionError` on `out/model.glb` (or similar), delete those specific files from the shell that
created them, then re-run `STEPS=("export",)`; Blender then creates fresh files it owns.

## Moving files between a cloud workspace and the user's machine
If the Python half runs in a cloud container and Blender on the user's machine:
- Copy with the device commit tool, then **verify with `md5sum` on the device**. Files copied into
  the outputs folder by a shell command can take ~20 s to sync; committing too early writes the
  previous version. Wait, re-check the checksum, re-commit if needed.
- Or run the Python half on the user's machine if `pip install -r pipeline/requirements.txt`
  works there.

## Version gotchas
- glTF exporter keyword names differ between 4.x and 5.x (`export_texcoord` vs `export_texcoords`);
  `gk_blender.gltf_kwargs()` picks the right one.
- EEVEE engine id: `BLENDER_EEVEE` (5.x) vs `BLENDER_EEVEE_NEXT` (4.2); see `gk_blender.eevee_engine()`.
- `Material.use_nodes` prints a deprecation warning in 5.x; harmless.
- Cloth `rest_shape_key` must point at the `Flat` shape key; without it the fabric's rest lengths
  come from the wrapped (stretched) placement and the model ends up the wrong size (`gk check`
  catches this through the 3D/pattern edge ratio).
