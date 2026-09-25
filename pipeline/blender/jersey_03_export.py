"""Jersey build - step 3: clean up the scene, export GLB (three.js) and save the .blend."""
import bpy, os
def _repo_root():
    r = globals().get('JERSEY_ROOT')
    if r:
        return r
    f = globals().get('__file__')
    if f and os.path.exists(f):
        return os.path.abspath(os.path.join(os.path.dirname(f), '..', '..'))
    raise RuntimeError("Run with __file__ set (blender --python <script>) or define JERSEY_ROOT")


ROOT = _repo_root()
BUILD = os.path.join(ROOT, 'pipeline', 'build')
MODEL = os.path.join(ROOT, 'assets', 'model')
TEMPLATE_DIR = os.path.join(ROOT, 'assets', 'template')
os.makedirs(BUILD, exist_ok=True)
os.makedirs(MODEL, exist_ok=True)
scene = bpy.context.scene

# drop the simulation helper (re-creatable with jersey_01) and the preview camera
for name in ('JerseySim', 'PreviewCam'):
    o = bpy.data.objects.get(name)
    if o: bpy.data.objects.remove(o, do_unlink=True)
for coll in (bpy.data.meshes, bpy.data.cameras, bpy.data.shape_keys):
    for d in list(coll):
        if d.users == 0:
            try: coll.remove(d)
            except Exception: pass
scene.frame_set(1)

jersey = bpy.data.objects['Jersey']
body = bpy.data.objects.get('Mannequin')
if body:
    for m in list(body.modifiers): body.modifiers.remove(m)
    body.animation_data_clear(); body.scale = (1, 1, 1)
    body.hide_viewport = False; body.hide_set(True)

# display camera + light for convenience inside Blender
cam = bpy.data.objects.get('Camera') or bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
if cam.name not in scene.collection.objects: scene.collection.objects.link(cam)
cam.data.lens = 70
cam.location = (0.0, -2.9, 0.1); cam.rotation_euler = (1.5708 - 0.035, 0, 0)
scene.camera = cam
if not bpy.data.objects.get('KeyLight'):
    L = bpy.data.objects.new('KeyLight', bpy.data.lights.new('KeyLight', 'AREA'))
    L.data.energy = 150; L.data.size = 1.5
    L.location = (-1.2, -1.8, 1.2); L.rotation_euler = (0.9, 0, -0.6)
    scene.collection.objects.link(L)
if not bpy.data.objects.get('RimLight'):
    L = bpy.data.objects.new('RimLight', bpy.data.lights.new('RimLight', 'AREA'))
    L.data.energy = 120; L.data.size = 1.5
    L.location = (1.4, 1.6, 1.0); L.rotation_euler = (-0.9, 0, 2.4)
    scene.collection.objects.link(L)

for o in bpy.context.view_layer.objects: o.select_set(False)
jersey.hide_set(False); jersey.select_set(True)
bpy.context.view_layer.objects.active = jersey

common = dict(export_format='GLB', use_selection=True, export_apply=True, export_yup=True,
              export_texcoords=True, export_normals=True, export_materials='EXPORT',
              export_animations=False, export_vertex_color='NONE')
p_tex = os.path.join(MODEL, 'jersey.glb')
p_notex = os.path.join(MODEL, 'jersey_untextured.glb')
bpy.ops.export_scene.gltf(filepath=p_tex, export_image_format='AUTO', **common)
bpy.ops.export_scene.gltf(filepath=p_notex, export_image_format='NONE', **common)

img = bpy.data.images.get('jersey_texture.png')
if img and not img.packed_file: img.pack()
p_blend = os.path.join(MODEL, 'jersey.blend')
bpy.ops.wm.save_as_mainfile(filepath=p_blend, copy=True)
result = dict(glb=p_tex, glb_bytes=os.path.getsize(p_tex), glb_notex_bytes=os.path.getsize(p_notex),
              blend=p_blend, blend_bytes=os.path.getsize(p_blend))
