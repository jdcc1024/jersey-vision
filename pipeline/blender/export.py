"""Step 3: export out/model.glb (+ untextured), render front/back views, save out/model.blend.

The simulation object is removed from the scene first (it is rebuilt by sim.py when needed).
"""
import importlib
import math
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(globals().get('__file__') or __file__)))
import gk_blender as gk  # noqa: E402
importlib.reload(gk)

C = gk.context(globals())
EXP = C.P['export']
RENDER = globals().get('RENDER', True)
scene = bpy.context.scene

for name in ('GarmentSim', 'PreviewCam'):
    o = bpy.data.objects.get(name)
    if o:
        bpy.data.objects.remove(o, do_unlink=True)
for coll in (bpy.data.meshes, bpy.data.cameras, bpy.data.shape_keys):
    for d in list(coll):
        if d.users == 0:
            try:
                coll.remove(d)
            except Exception:
                pass
scene.frame_set(1)

garment = bpy.data.objects[EXP['object_name']]
body = bpy.data.objects.get('Mannequin')
if body:
    for mo in list(body.modifiers):
        body.modifiers.remove(mo)
    body.animation_data_clear(); body.scale = (1, 1, 1)
    body.hide_viewport = False; body.hide_set(True)

cam = bpy.data.objects.get('Camera') or bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
if cam.name not in scene.collection.objects:
    scene.collection.objects.link(cam)
cam.data.lens = 60
scene.camera = cam
for lname, loc, rot, energy in (('KeyLight', (-1.2, -1.8, 1.2), (0.9, 0, -0.6), 150),
                                ('RimLight', (1.4, 1.6, 1.0), (-0.9, 0, 2.4), 120)):
    if not bpy.data.objects.get(lname):
        L = bpy.data.objects.new(lname, bpy.data.lights.new(lname, 'AREA'))
        L.data.energy = energy; L.data.size = 1.5
        L.location = loc; L.rotation_euler = rot
        scene.collection.objects.link(L)

for o in bpy.context.view_layer.objects:
    o.select_set(False)
garment.hide_set(False); garment.select_set(True)
bpy.context.view_layer.objects.active = garment

kw, _ = gk.gltf_kwargs()
p_tex = os.path.join(C.out, 'model.glb')
p_notex = os.path.join(C.out, 'model_untextured.glb')
bpy.ops.export_scene.gltf(filepath=p_tex, export_image_format='AUTO', **kw)
bpy.ops.export_scene.gltf(filepath=p_notex, export_image_format='NONE', **kw)

renders = []
if RENDER:
    scene.render.engine = gk.eevee_engine()
    scene.render.resolution_x, scene.render.resolution_y = 900, 1000
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.view_settings.view_transform = 'Standard'
    w = scene.world or bpy.data.worlds.new('World'); scene.world = w
    w.use_nodes = True
    bgn = w.node_tree.nodes.get('Background')
    if bgn:
        bgn.inputs[0].default_value = (0.8, 0.82, 0.85, 1); bgn.inputs[1].default_value = 0.35
    size = max(garment.dimensions)
    dist = size / (2 * math.tan(math.atan(18 / 60))) * 1.12 + 0.2    # fit the garment in a 60 mm lens frame
    for view, loc, rot in (('front', (0, -dist, 0.02), (math.radians(90), 0, 0)),
                           ('back', (0, dist, 0.02), (math.radians(90), 0, math.radians(180)))):
        cam.location = loc; cam.rotation_euler = rot
        scene.render.filepath = os.path.join(C.out, f'render_{view}.png')
        bpy.ops.render.render(write_still=True)
        renders.append(scene.render.filepath)
    cam.location = (0, -dist, 0.02); cam.rotation_euler = (math.radians(90), 0, 0)

img = bpy.data.images.get('texture.png')
if img and not img.packed_file:
    img.pack()
p_blend = os.path.join(C.out, 'model.blend')
bpy.ops.wm.save_as_mainfile(filepath=p_blend, copy=True)
result = dict(glb=p_tex, glb_bytes=os.path.getsize(p_tex), glb_untextured_bytes=os.path.getsize(p_notex),
              blend=p_blend, renders=renders)
