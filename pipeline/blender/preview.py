"""Quick workbench preview renders (front / back / side / 3-4) into build/preview_<tag>_<view>.png"""
import bpy, math, os
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
OUT = os.path.join(BUILD, 'previews')
os.makedirs(OUT, exist_ok=True)
TAG = globals().get('TAG', 'x')
VIEWS = globals().get('VIEWS', ['front', 'back', 'side', 'q34'])
SHOW_BODY = globals().get('SHOW_BODY', False)
TEXTURED = globals().get('TEXTURED', False)
CENTER = globals().get('CENTER', (0, 0, -0.38))
RES = globals().get('RES', 700)

scene = bpy.context.scene
cam = bpy.data.objects.get('PreviewCam')
if cam is None:
    cam = bpy.data.objects.new('PreviewCam', bpy.data.cameras.new('PreviewCam'))
    scene.collection.objects.link(cam)
cam.data.type = 'ORTHO'
cam.data.ortho_scale = globals().get('ORTHO', 1.05)
scene.camera = cam
scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.light = 'STUDIO'
scene.display.shading.color_type = 'TEXTURE' if TEXTURED else 'OBJECT'
scene.display.shading.show_cavity = False
scene.render.resolution_x = RES; scene.render.resolution_y = RES
scene.render.film_transparent = False
body = bpy.data.objects.get('Mannequin')
if body: body.hide_render = not SHOW_BODY
cx, cy, cz = CENTER
dirs = {'front': (0, -1, 0), 'back': (0, 1, 0), 'side': (1, 0, 0), 'q34': (0.7, -0.7, 0.15), 'top': (0, -0.2, 1)}
paths = []
for v in VIEWS:
    d = dirs[v]
    n = math.sqrt(sum(c * c for c in d)); d = [c / n for c in d]
    cam.location = (cx + d[0] * 3, cy + d[1] * 3, cz + d[2] * 3)
    import mathutils
    cam.rotation_euler = (mathutils.Vector((-d[0], -d[1], -d[2]))).to_track_quat('-Z', 'Y').to_euler()
    p = os.path.join(OUT, f'preview_{TAG}_{v}.png')
    scene.render.filepath = p
    bpy.ops.render.render(write_still=True)
    paths.append(p)
result = dict(paths=paths)
