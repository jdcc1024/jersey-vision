"""Jersey build - step 1: build mannequin collider + garment panels (UV = sewing template) and set up
a cloth simulation with sewing springs. Run inside Blender (tested 5.2).
Units: metres. Template pixel == 1 mm. Front = -Y, wearer's left = +X, neck point (HPS) at z = 0.
"""
import bpy, bmesh, json, math, os
import numpy as np

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
P = json.load(open(os.path.join(BUILD, 'pattern.json')))
TW, TH = P['template_size']
PX = P['px_to_m']
SELF_COLL = globals().get('SELF_COLL', True)

# ---------------------------------------------------------------- clean scene
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.curves, bpy.data.cameras, bpy.data.lights):
    for d in list(coll):
        if d.users == 0:
            coll.remove(d)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.frame_start = 1
scene.frame_end = 90
scene.render.fps = 24

# ---------------------------------------------------------------- mannequin collider
bd = json.load(open(os.path.join(BUILD, 'body.json')))
me = bpy.data.meshes.new('Mannequin')
me.from_pydata([tuple(v) for v in bd['v']], [], [tuple(f) for f in bd['f']])
bm = bmesh.new(); bm.from_mesh(me)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
bm.to_mesh(me); bm.free()
body = bpy.data.objects.new('Mannequin', me)
scene.collection.objects.link(body)
dec = body.modifiers.new('Decimate', 'DECIMATE'); dec.ratio = 0.25
bpy.context.view_layer.objects.active = body
body.select_set(True)
bpy.ops.object.modifier_apply(modifier='Decimate')
for p in body.data.polygons: p.use_smooth = True
body.modifiers.new('Collision', 'COLLISION')
body.collision.thickness_outer = 0.004
body.collision.cloth_friction = 5.0
body.collision.damping = 0.5
# grow the mannequin at the start so panels are guaranteed to start outside it
body.scale = (0.84, 0.84, 1.0); body.keyframe_insert('scale', frame=1)
body.scale = (0.84, 0.84, 1.0); body.keyframe_insert('scale', frame=4)
body.scale = (1.0, 1.0, 1.0);   body.keyframe_insert('scale', frame=26)

# ---------------------------------------------------------------- garment initial placement
V2 = np.array(P['V'], float)            # template pixels
panel = np.array(P['panel'])
F = P['F']
N = len(V2)
V3 = np.zeros((N, 3))

def ellipse_table(a, b, n=2000):
    ph = np.linspace(0, math.pi / 2, n)
    dx = a * np.cos(ph); dy = b * np.sin(ph)
    ds = np.sqrt(dx ** 2 + dy ** 2) * (ph[1] - ph[0])
    arc = np.r_[0, np.cumsum(ds[:-1])]
    return ph, arc / arc[-1]

A0, B0 = 0.222, 0.155
ph_tab, arc_tab = ellipse_table(A0, B0)
C_CURL = 0.12
torso_def = {0: dict(cx=288.0, top=15.0, xs=+1, ys=-1),     # front
             1: dict(cx=846.5, top=18.0, xs=-1, ys=+1)}     # back
HALF_W = 273.0
for pid, d in torso_def.items():
    idx = np.where(panel == pid)[0]
    px, py = V2[idx, 0], V2[idx, 1]
    s = px - d['cx']
    a_s = np.abs(s)
    phi = np.interp(np.clip(a_s / HALF_W, 0, 1), arc_tab, ph_tab) * np.sign(s)
    # distance below shoulder line (neck point |s|=91 -> shoulder point |s|=229 drops 40 px)
    ysh = d['top'] + np.clip((a_s - 91.0) / 138.0, 0, None) * 40.0
    dtop = np.clip((py - ysh) * PX, 0, None)
    g = np.where(dtop < C_CURL, 0.25 + 0.75 * np.sin(0.5 * math.pi * dtop / C_CURL), 1.0)
    X = d['xs'] * A0 * np.sin(phi)
    Y = d['ys'] * B0 * g * np.cos(phi)
    Z = -(py - d['top']) * PX
    V3[idx] = np.c_[X, Y, Z]

ANG = math.radians(50)
for pid, sgn, dy, side_y in ((2, +1, 0, +1), (3, -1, 278, -1)):
    idx = np.where(panel == pid)[0]
    px, py = V2[idx, 0], V2[idx, 1]
    cx, fold_y = 1390.5, 469.0 + dy
    s = (px - cx) * PX
    h = (fold_y - py) * PX
    w = np.interp(h, [0.0, 0.112], [0.407, 0.517])        # seam-to-seam width (m)
    rr = w / (2 * math.pi)
    theta = s / rr
    r_place = rr * 1.06
    dirv = np.array([sgn * math.cos(ANG), 0, -math.sin(ANG)])
    upv = np.array([sgn * math.sin(ANG), 0, math.cos(ANG)])
    sidev = np.array([0, side_y, 0.0])
    SP = np.array([sgn * 0.215, 0.0, -0.045])
    h_peak = 0.240
    r_cap = 0.517 / (2 * math.pi) * 1.06
    hem_c = SP + dirv * h_peak - upv * r_cap
    V3[idx] = hem_c[None] - np.outer(h, dirv) + (r_place * np.cos(theta))[:, None] * upv[None] \
        + (r_place * np.sin(theta))[:, None] * sidev[None]

pairs = sorted({tuple(sorted(p)) for p in P["pairs"] if p[0] != p[1]})
gm = bpy.data.meshes.new('JerseyPanels')
gm.from_pydata(V3.tolist(), pairs, F)
gm.update()
uv = gm.uv_layers.new(name='UVMap')
loop_v = np.zeros(len(gm.loops), int); gm.loops.foreach_get('vertex_index', loop_v)
uvs = np.c_[V2[loop_v, 0] / TW, 1.0 - V2[loop_v, 1] / TH]
uv.data.foreach_set('uv', uvs.ravel())
for p in gm.polygons: p.use_smooth = True
gar = bpy.data.objects.new('JerseySim', gm)
scene.collection.objects.link(gar)
# panel id attribute (useful later)
at = gm.attributes.new('panel', 'INT', 'POINT'); at.data.foreach_set('value', panel.tolist())

# rest shape = flat pattern
gar.shape_key_add(name='Basis')
flat = gar.shape_key_add(name='Flat')
flat_co = np.c_[V2[:, 0] * PX, np.zeros(N), -V2[:, 1] * PX]
flat.data.foreach_set('co', flat_co.ravel())
flat.value = 0.0

cl = gar.modifiers.new('Cloth', 'CLOTH')
cs = cl.settings
cs.rest_shape_key = flat
cs.quality = 10
cs.mass = 0.15
cs.air_damping = 1.0
cs.tension_stiffness = 15; cs.compression_stiffness = 30
cs.shear_stiffness = 5
cs.bending_stiffness = 2.0
cs.tension_damping = 5; cs.compression_damping = 5; cs.shear_damping = 5; cs.bending_damping = 0.5
cs.use_sewing_springs = True
cs.sewing_force_max = 10.0
cs.effector_weights.gravity = 0.0
cs.effector_weights.keyframe_insert('gravity', frame=1)
cs.effector_weights.keyframe_insert('gravity', frame=30)
cs.effector_weights.gravity = globals().get('GRAVITY', 0.6)
cs.effector_weights.keyframe_insert('gravity', frame=50)
cc = cl.collision_settings
cc.collision_quality = 3
cc.distance_min = 0.003
cc.use_self_collision = SELF_COLL
cc.self_distance_min = 0.002
cl.point_cache.frame_start = 1
cl.point_cache.frame_end = 90

scene.frame_set(1)
result = dict(garment_verts=N, faces=len(F), sew_edges=len(pairs), body_faces=len(body.data.polygons))
