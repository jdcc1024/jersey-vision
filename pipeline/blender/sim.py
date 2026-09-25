"""Step 1: mannequin collider + garment panels placed around it + cloth sim with sewing springs.

Clears the scene. After this, step frames 1..sim.frames (run.py does it) before finish.py.
Units: metres. Front = -Y, wearer's left = +X, neck point (HPS) at z = 0.
"""
import importlib
import json
import math
import os
import sys

import bmesh
import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(globals().get('__file__') or __file__)))
import gk_blender as gk  # noqa: E402
importlib.reload(gk)

C = gk.context(globals())
P, S = C.P, C.P['sim']
TW, TH = P['template_size']
M = P['m_per_px']
SELF_COLL = globals().get('SELF_COLL', S['self_collision'])

# ---------------------------------------------------------------- clean scene
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights, bpy.data.images):
    for d in list(coll):
        if d.users == 0:
            coll.remove(d)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.frame_start = 1
scene.frame_end = S['frames']
scene.render.fps = 24

# ---------------------------------------------------------------- mannequin collider
bd = json.load(open(os.path.join(C.build, 'body.json')))
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
for p in body.data.polygons:
    p.use_smooth = True
body.modifiers.new('Collision', 'COLLISION')
body.collision.thickness_outer = S['body_thickness_mm'] / 1000
body.collision.cloth_friction = S['friction']
body.collision.damping = 0.5
g0 = S['grow_from']          # grow the mannequin at the start so panels begin outside it
body.scale = (g0, g0, 1.0); body.keyframe_insert('scale', frame=1)
body.scale = (g0, g0, 1.0); body.keyframe_insert('scale', frame=4)
body.scale = (1.0, 1.0, 1.0); body.keyframe_insert('scale', frame=S['grow_until_frame'])

# ---------------------------------------------------------------- initial placement of every panel
V2 = np.array(P['V'], float)
panel = np.array(P['panel'])
N = len(V2)
V3 = np.zeros((N, 3))
fit = P['fit']
A0, B0 = fit['wrap_a'], fit['wrap_b']

# arc-length table around the whole ellipse; angle 0 = front centre, +90 deg = wearer's left (+X)
_ph = np.linspace(-2 * math.pi, 2 * math.pi, 16001)
_ds = np.sqrt((A0 * np.cos(_ph)) ** 2 + (B0 * np.sin(_ph)) ** 2) * (_ph[1] - _ph[0])
_arc = np.r_[0, np.cumsum(_ds[:-1])]
arc_of = lambda phi: np.interp(phi, _ph, _arc)
phi_of = lambda s: np.interp(s, _arc, _ph)
ANG = math.radians(P['body']['arm_angle_deg'])
CURL = S['curl_mm'] / 1000

for pi, pc in enumerate(P['pieces']):
    pl = pc['place']
    idx = np.where(panel == pi)[0]
    px, py = V2[idx, 0], V2[idx, 1]
    if pl['type'] == 'torso':
        t = (px - pl['x0']) / (pl['x1'] - pl['x0'])
        s0, s1 = arc_of(pl['arc'][0]), arc_of(pl['arc'][1])
        phi = phi_of(s0 + t * (s1 - s0))
        if 'top_x' in pl:
            ytop = np.interp(px, pl['top_x'], pl['top_y'])
            dtop = np.clip((py - ytop) * M, 0, None)
            g = np.where(dtop < CURL, 0.25 + 0.75 * np.sin(0.5 * math.pi * dtop / CURL), 1.0)
        else:
            g = 1.0
        V3[idx] = np.c_[A0 * np.sin(phi), -B0 * g * np.cos(phi), -(py - pl['hps_y']) * M]
    elif pl['type'] == 'arm':
        sgn = pl['side']
        s = (px - pl['cx']) * M
        h = (pl['hem_y'] - py) * M
        w = np.interp(h, [0.0, pl['h_ua']], [pl['w_hem'], pl['w_ua']])
        rr = w / (2 * math.pi)
        theta = s / rr
        r_place = rr * S['arm_wrap_scale']
        dirv = np.array([sgn * math.cos(ANG), 0, -math.sin(ANG)])
        upv = np.array([sgn * math.sin(ANG), 0, math.cos(ANG)])
        sidev = np.array([0, pl['front_sign'], 0.0])
        r_cap = pl['w_ua'] / (2 * math.pi) * S['arm_wrap_scale']
        hem_c = np.array(pl['anchor_m']) + dirv * pl['h_peak'] - upv * r_cap
        V3[idx] = hem_c[None] - np.outer(h, dirv) + (r_place * np.cos(theta))[:, None] * upv[None] \
            + (r_place * np.sin(theta))[:, None] * sidev[None]
    elif pl['type'] == 'flat':
        o, r, d = (np.array(pl[k], float) for k in ('origin', 'right', 'down'))
        V3[idx] = o[None] + np.outer((px - pl['anchor'][0]) * M, r) + np.outer((py - pl['anchor'][1]) * M, d)

pairs = sorted({tuple(sorted(p)) for p in P['pairs'] if p[0] != p[1]})
gm = bpy.data.meshes.new('GarmentPanels')
gm.from_pydata(V3.tolist(), pairs, P['F'])
gm.update()
uv = gm.uv_layers.new(name='UVMap')
loop_v = np.zeros(len(gm.loops), int); gm.loops.foreach_get('vertex_index', loop_v)
uv.data.foreach_set('uv', np.c_[(V2[loop_v, 0] + 0.5) / TW, 1.0 - (V2[loop_v, 1] + 0.5) / TH].ravel())
for p in gm.polygons:
    p.use_smooth = True
sim = bpy.data.objects.new('GarmentSim', gm)
scene.collection.objects.link(sim)
at = gm.attributes.new('panel', 'INT', 'POINT'); at.data.foreach_set('value', panel.tolist())

# rest shape = the flat pattern, so the cloth keeps the template's true dimensions
sim.shape_key_add(name='Basis')
flat = sim.shape_key_add(name='Flat')
flat.data.foreach_set('co', np.c_[V2[:, 0] * M, np.zeros(N), -V2[:, 1] * M].ravel())
flat.value = 0.0

cl = sim.modifiers.new('Cloth', 'CLOTH')
cs = cl.settings
cs.rest_shape_key = flat
cs.quality = S['quality']
cs.mass = S['mass']
cs.air_damping = 1.0
cs.tension_stiffness = S['tension']; cs.compression_stiffness = S['compression']
cs.shear_stiffness = S['shear']; cs.bending_stiffness = S['bending']
cs.tension_damping = 5; cs.compression_damping = 5; cs.shear_damping = 5; cs.bending_damping = 0.5
cs.use_sewing_springs = True
cs.sewing_force_max = S['sewing_force_max']
cs.effector_weights.gravity = 0.0
cs.effector_weights.keyframe_insert('gravity', frame=1)
cs.effector_weights.keyframe_insert('gravity', frame=S['gravity_on_frame'])
cs.effector_weights.gravity = S['gravity']
cs.effector_weights.keyframe_insert('gravity', frame=S['gravity_full_frame'])
cc = cl.collision_settings
cc.collision_quality = 3
cc.distance_min = S['collision_distance_mm'] / 1000
cc.use_self_collision = SELF_COLL
cc.self_distance_min = S['self_collision_distance_mm'] / 1000
cl.point_cache.frame_start = 1
cl.point_cache.frame_end = S['frames']

scene.frame_set(1)
result = dict(garment=os.path.basename(C.gdir), verts=N, tris=len(P['F']), sew_edges=len(pairs),
              body_faces=len(body.data.polygons), frames=S['frames'])
