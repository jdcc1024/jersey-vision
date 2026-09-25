"""Whole Blender half of the pipeline for one garment: sim -> frames -> finish -> export.

    blender --background --python pipeline/blender/run.py -- crew-tee

or in a live Blender (e.g. via Blender MCP):

    p = r"<repo>/pipeline/blender/run.py"
    exec(compile(open(p).read(), p, "exec"), {"__file__": p, "GARMENT": "crew-tee"})

Needs garments/<g>/build/pattern.json and body.json and out/texture.png
(`python pipeline/gk.py prep <g>`).

Optional globals: STEPS (subset of 'sim','frames','finish','export'), FRAMES=(first, last) to step
the simulation in chunks across several calls, RENDER=False, SELF_COLL, SMOOTH_ITERS.
Frames must be stepped in order without touching GarmentSim in between (that resets the cache).
"""
import importlib
import os
import sys
import time

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(globals().get('__file__') or __file__)))
import gk_blender as gk  # noqa: E402
importlib.reload(gk)

GARMENT = gk.garment_arg(globals())
extra = {'GARMENT': GARMENT}
for k in ('SELF_COLL', 'SMOOTH_ITERS', 'RENDER'):   # optional overrides passed through
    if k in globals():
        extra[k] = globals()[k]
STEPS = globals().get('STEPS', ('sim', 'frames', 'finish', 'export'))

t0 = time.time()
log = []
if 'sim' in STEPS:
    log.append(('sim', gk.run_script('sim.py', extra)))
if 'frames' in STEPS:
    scene = bpy.context.scene
    f0, f1 = globals().get('FRAMES', (scene.frame_start, scene.frame_end))   # chunk long sims: FRAMES=(1, 40) ...
    for f in range(f0, min(f1, scene.frame_end) + 1):
        scene.frame_set(f)
    log.append(('frames', f'{f0}-{min(f1, scene.frame_end)} of {scene.frame_end}, {time.time() - t0:.1f}s'))
if 'finish' in STEPS:
    log.append(('finish', gk.run_script('finish.py', extra)))
if 'export' in STEPS:
    log.append(('export', gk.run_script('export.py', extra)))
for k, v in log:
    print(f'[{k}] {v}')
print(f'done in {time.time() - t0:.1f}s')
result = dict(log, seconds=round(time.time() - t0, 1))
