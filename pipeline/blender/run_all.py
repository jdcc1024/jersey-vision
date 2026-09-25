"""Run the whole Blender half of the pipeline: setup + cloth sim + finish + export.

    blender --background --python pipeline/blender/run_all.py

or, from a live Blender (e.g. via Blender MCP):

    exec(open(r"<repo>/pipeline/blender/run_all.py").read(), {"__file__": r"<repo>/pipeline/blender/run_all.py"})

Needs pipeline/build/pattern.json and body.json (run pipeline/prep/pattern.py and body.py first).
"""
import os
import time
import bpy

HERE = os.path.dirname(os.path.abspath(globals().get('__file__') or __file__))


def run(name, **extra):
    path = os.path.join(HERE, name)
    g = {'__name__': '__main__', '__file__': path}
    g.update(extra)
    exec(compile(open(path).read(), path, 'exec'), g)
    return g.get('result')


t0 = time.time()
print('setup:', run('jersey_01_setup_sim.py'))
scene = bpy.context.scene
for f in range(scene.frame_start, scene.frame_end + 1):
    scene.frame_set(f)
print(f'cloth sim: {scene.frame_end} frames in {time.time() - t0:.1f}s')
print('finish:', run('jersey_02_finish.py'))
print('export:', run('jersey_03_export.py'))
print(f'done in {time.time() - t0:.1f}s')
