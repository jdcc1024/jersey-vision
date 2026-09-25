"""Quick Workbench previews (orthographic) -> garments/<g>/build/previews/<TAG>_<view>.png

Globals: GARMENT, TAG ('x'), VIEWS (['front','back','side','q34']), TEXTURED (True),
SHOW_BODY (False), RES (700). Frames whatever garment objects are visible.
"""
import importlib
import math
import os
import sys

import bpy
import mathutils

sys.path.insert(0, os.path.dirname(os.path.abspath(globals().get('__file__') or __file__)))
import gk_blender as gk  # noqa: E402
importlib.reload(gk)

C = gk.context(globals())
OUT = os.path.join(C.build, 'previews')
os.makedirs(OUT, exist_ok=True)
TAG = globals().get('TAG', 'x')
VIEWS = globals().get('VIEWS', ['front', 'back', 'side', 'q34'])
TEXTURED = globals().get('TEXTURED', True)
SHOW_BODY = globals().get('SHOW_BODY', False)
RES = globals().get('RES', 700)
scene = bpy.context.scene

body = bpy.data.objects.get('Mannequin')
if body:
    body.hide_render = not SHOW_BODY
targets = [o for o in scene.objects if o.type == 'MESH' and not o.hide_render]
pts = [o.matrix_world @ mathutils.Vector(c) for o in targets for c in o.bound_box]
lo = mathutils.Vector([min(p[i] for p in pts) for i in range(3)])
hi = mathutils.Vector([max(p[i] for p in pts) for i in range(3)])
ctr = (lo + hi) / 2
cam = bpy.data.objects.get('PreviewCam')
if cam is None:
    cam = bpy.data.objects.new('PreviewCam', bpy.data.cameras.new('PreviewCam'))
    scene.collection.objects.link(cam)
cam.data.type = 'ORTHO'
cam.data.ortho_scale = max(hi - lo) * 1.1
prev_cam = scene.camera
scene.camera = cam
scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.light = 'STUDIO'
scene.display.shading.color_type = 'TEXTURE' if TEXTURED else 'OBJECT'
scene.render.resolution_x = scene.render.resolution_y = RES
scene.render.film_transparent = False
dirs = {'front': (0, -1, 0), 'back': (0, 1, 0), 'side': (1, 0, 0), 'left': (1, 0, 0), 'right': (-1, 0, 0),
        'q34': (0.7, -0.7, 0.15), 'top': (0, -0.2, 1)}
paths = []
for v in VIEWS:
    d = mathutils.Vector(dirs[v]).normalized()
    cam.location = ctr + d * 3
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = os.path.join(OUT, f'{TAG}_{v}.png')
    bpy.ops.render.render(write_still=True)
    paths.append(scene.render.filepath)
scene.camera = prev_cam
result = dict(paths=paths)
