"""Step 2: simulated panels -> final garment mesh.

Welds seams, smooths, then adds hem turn-ups, bands (rib collars / bindings / cuffs) and inside
patches (tapes, labels), assigns the print material and centres the model on the origin.
UV convention: template pixel (px, py) -> Blender UV ((px+.5)/W, 1-(py+.5)/H)   (glTF v = (py+.5)/H)
"""
import importlib
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform

sys.path.insert(0, os.path.dirname(os.path.abspath(globals().get('__file__') or __file__)))
import gk_blender as gk  # noqa: E402
importlib.reload(gk)

C = gk.context(globals())
P = C.P
TW, TH = P['template_size']
MPX = P['m_per_px']
EXP = P['export']
V2 = np.array(P['V'], float)
panel = np.array(P['panel'])
F = np.array(P['F'], int)
N = len(V2)
scene = bpy.context.scene


def uv_of(px, py):
    return ((px + 0.5) / TW, 1.0 - (py + 0.5) / TH)


# ------------------------------------------------------------- 1. simulated positions
sim = bpy.data.objects['GarmentSim']
scene.frame_set(scene.frame_end)
dg = bpy.context.evaluated_depsgraph_get()
se = sim.evaluated_get(dg)
m = se.to_mesh()
co = np.zeros(len(m.vertices) * 3); m.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
se.to_mesh_clear()
mw = np.array(sim.matrix_world)
co = co @ mw[:3, :3].T + mw[:3, 3]
pr = np.array(P['pairs'])
gap = float(np.linalg.norm(co[pr[:, 0]] - co[pr[:, 1]], axis=1).max()) if len(pr) else 0.0

# ------------------------------------------------------------- 2. weld seams (union-find)
par = list(range(N))


def find(i):
    while par[i] != i:
        par[i] = par[par[i]]; i = par[i]
    return i


for a, b in P['pairs']:
    ra, rb = find(a), find(b)
    if ra != rb:
        par[rb] = ra
roots = np.array([find(i) for i in range(N)])
uniq, inv = np.unique(roots, return_inverse=True)
Mv = len(uniq)
pos = np.zeros((Mv, 3)); cnt = np.zeros(Mv)
np.add.at(pos, inv, co); np.add.at(cnt, inv, 1); pos /= cnt[:, None]
faces = inv[F]


# ------------------------------------------------------------- 3. Taubin smoothing (no shrink)
def taubin(pos, faces, iters=10, lam=0.5, mu=-0.53):
    e = np.sort(np.r_[faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]], axis=1)
    ue, ec = np.unique(e, axis=0, return_counts=True)
    bnd = ue[ec == 1]
    isb = np.zeros(len(pos), bool); isb[bnd.ravel()] = True
    inner = ue[~(isb[ue[:, 0]] | isb[ue[:, 1]])]
    mix = ue[isb[ue[:, 0]] ^ isb[ue[:, 1]]]
    ib = isb[mix[:, 0]]
    src = np.concatenate([inner[:, 0], inner[:, 1], np.where(ib, mix[:, 1], mix[:, 0]), bnd[:, 0], bnd[:, 1]])
    dst = np.concatenate([inner[:, 1], inner[:, 0], np.where(ib, mix[:, 0], mix[:, 1]), bnd[:, 1], bnd[:, 0]])
    deg = np.bincount(src, minlength=len(pos)).astype(float); deg[deg == 0] = 1
    p = pos.copy()
    for _ in range(iters):
        for f in (lam, mu):
            acc = np.zeros_like(p); np.add.at(acc, src, p[dst])
            p = p + f * (acc / deg[:, None] - p)
    return p


pos = taubin(pos, faces, iters=int(globals().get('SMOOTH_ITERS', P['finish']['smooth_iters'])))


def vnormals(pos, faces):
    fn = np.cross(pos[faces[:, 1]] - pos[faces[:, 0]], pos[faces[:, 2]] - pos[faces[:, 0]])
    vn = np.zeros_like(pos)
    for k in range(3):
        np.add.at(vn, faces[:, k], fn)
    return vn / np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-12)


vn = vnormals(pos, faces)

# ------------------------------------------------------------- geometry accumulators
G_pos = [pos]; G_faces = []; G_uv = []; count = [Mv]


def add_verts(p):
    base = count[0]; G_pos.append(np.asarray(p, float).reshape(-1, 3)); count[0] += len(G_pos[-1]); return base


def allp():
    return np.concatenate(G_pos)


for f, fo in zip(faces, F):
    G_faces.append(tuple(f)); G_uv.append([uv_of(*V2[i]) for i in fo])

_mappers = {}


def mapper(pid):
    """pattern (px) -> (3D point, unit outward normal) on the finished panel pid"""
    if pid in _mappers:
        return _mappers[pid]
    fp = F[panel[F[:, 0]] == pid]
    verts = [Vector((x, y, 0.0)) for x, y in V2]
    bvh = BVHTree.FromPolygons(verts, [tuple(f) for f in fp])

    def mapf(qx, qy):
        loc, _, idx, _ = bvh.find_nearest(Vector((qx, qy, 0.0)))
        a, b, c = fp[idx]
        w = barycentric_transform(loc, verts[a], verts[b], verts[c], Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))
        ia, ib_, ic = inv[a], inv[b], inv[c]
        p3 = w[0] * pos[ia] + w[1] * pos[ib_] + w[2] * pos[ic]
        n3 = w[0] * vn[ia] + w[1] * vn[ib_] + w[2] * vn[ic]
        return p3, n3 / np.linalg.norm(n3)
    _mappers[pid] = mapf
    return mapf


def add_grid(pts, uvs, rows, cols, want_normal=None, ref_row=0):
    """quads over a rows x cols grid; flip so the face normal agrees with want_normal (a 3-vector)"""
    base = add_verts(pts)
    fl, ul = [], []
    for r in range(rows - 1):
        for c in range(cols - 1):
            q = (base + r * cols + c, base + r * cols + c + 1, base + (r + 1) * cols + c + 1, base + (r + 1) * cols + c)
            fl.append(q); ul.append([uvs[k - base] for k in q])
    if want_normal is not None:
        P3 = allp(); q = fl[ref_row * (cols - 1) + (cols - 1) // 2]
        if np.dot(np.cross(P3[q[1]] - P3[q[0]], P3[q[3]] - P3[q[0]]), want_normal) < 0:
            fl = [tuple(reversed(f)) for f in fl]; ul = [list(reversed(u)) for u in ul]
    G_faces.extend(fl); G_uv.extend(ul)


# ------------------------------------------------------------- 4. hem turn-ups
for tu in P['turnups']:
    fv = np.array(tu['v']); ff = np.array(tu['f']); nfl = tu['n_fold']
    a, b = np.array(tu['fold_line'][0], float), np.array(tu['fold_line'][1], float)
    t_hat = (b - a) / np.linalg.norm(b - a)
    mapf = mapper(tu['piece'])
    idx_map = np.zeros(len(fv), int)
    idx_map[:nfl] = inv[np.array(tu['fold_ids'])]
    newp = []
    for k in range(nfl, len(fv)):
        q = fv[k]
        rel = q - a
        foot = a + t_hat * np.dot(rel, t_hat)
        mirrored = 2 * foot - q                           # reflect across the fold line
        dist_mm = np.linalg.norm(q - foot) * P['mm_per_px']
        p3, n3 = mapf(*mirrored)
        newp.append(p3 - n3 * tu['depth_m'] * min(1.0, dist_mm / 4.0) ** 0.5)
    base = add_verts(newp)
    idx_map[nfl:] = base + np.arange(len(fv) - nfl)
    for ia, ib_ in tu['weld']:
        if ib_ < nfl:
            idx_map[ia] = idx_map[ib_]
        else:
            idx_map[ib_] = idx_map[ia]
    for f in ff:
        G_faces.append(tuple(int(i) for i in idx_map[f])); G_uv.append([uv_of(*fv[i]) for i in f])

# ------------------------------------------------------------- 5. bands (rib collars, bindings, cuffs)
g_ctr = pos.mean(0)
for bd in P['bands']:
    pts, us = [], []
    br = bd['u_breaks']
    for k, seg in enumerate(bd['loop']):
        ids = inv[np.array(seg)]
        sp = pos[ids]
        L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(sp, axis=0), axis=1))]
        u = br[k] + (br[k + 1] - br[k]) * L / L[-1]
        if pts and ids[0] == pts[-1]:                   # joint shared with the previous segment
            ids, u = ids[1:], u[1:]
        pts.extend(int(i) for i in ids); us.extend(u.tolist())
    closed = pts[-1] == pts[0]
    if closed:
        pts = pts[:-1]; us = us[:-1]
    Lp = pos[np.array(pts)]
    cols = np.r_[Lp, Lp[:1]]
    us = np.r_[us, br[-1]]
    ctr = Lp.mean(0)
    if bd['axis'] == 'up':
        axis = np.array([0, 0, 1.0])
    else:
        _, _, vt = np.linalg.svd(Lp - ctr)
        axis = vt[2] * (1 if np.dot(vt[2], ctr - g_ctr) > 0 else -1)
    radial = cols - ctr
    radial -= np.outer(radial @ axis, axis)
    radial /= np.linalg.norm(radial, axis=1, keepdims=True)
    beta = math.radians(bd['lean_deg'])
    dirs = axis[None] * math.cos(beta) - radial * math.sin(beta)
    Hh, T = bd['height_m'], bd['thickness_m']
    n = bd['rows']
    rows = [(h, 0.0, bd['seam_y'] + (bd['fold_y'] - bd['seam_y']) * h / Hh) for h in np.linspace(0, Hh, n)]
    if bd['fold']:
        rf = T / 2
        rows += [(Hh + rf * math.sin(a_), -rf * (1 - math.cos(a_)), bd['fold_y']) for a_ in np.radians([45, 90, 135])]
        rows += [(h, -T, bd['far_y'] + (bd['fold_y'] - bd['far_y']) * h / Hh) for h in np.linspace(Hh, 0, n)]
    gp, gu = [], []
    for (h, ro, vy) in rows:
        gp.append(cols + dirs * h + radial * ro)
        gu.extend([uv_of(u, vy) for u in us])
    add_grid(np.array(gp).reshape(-1, 3), gu, len(rows), len(cols), want_normal=radial[len(cols) // 2], ref_row=0)

# ------------------------------------------------------------- 6. inside patches (tapes, labels)
for pa in P['patches']:
    mapf = mapper(pa['host'])
    rx, ry, rw, rh = pa['rect']
    if pa['type'] == 'strip':
        path = np.array(pa['path']); nrm = np.array(pa['normals'])
        L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))]
        pts, uvs = [], []
        for j in range(pa['rows']):
            w = rh * j / (pa['rows'] - 1)
            for i in range(len(path)):
                q = path[i] + nrm[i] * (w + pa['inset_px'])
                p3, n3 = mapf(*q)
                pts.append(p3 - n3 * pa['offset_m'])
                fu = L[i] / L[-1]
                uvs.append(uv_of(rx + rw - fu * rw if pa['mirror_u'] else rx + fu * rw, ry + w))
        _, n_in = mapf(*path[len(path) // 2])
        add_grid(pts, uvs, pa['rows'], len(path), want_normal=-n_in)
    else:
        cx, cy = pa['center']; NX, NY = pa['grid']
        pts, uvs = [], []
        for j in range(NY + 1):
            for i in range(NX + 1):
                p3, n3 = mapf(cx - rw / 2 + rw * i / NX, cy - rh / 2 + rh * j / NY)
                pts.append(p3 - n3 * pa['offset_m'])
                uvs.append(uv_of(rx + rw - rw * i / NX if pa['mirror_u'] else rx + rw * i / NX, ry + rh * j / NY))
        _, n_in = mapf(cx, cy)
        add_grid(pts, uvs, NY + 1, NX + 1, want_normal=-n_in)

# ------------------------------------------------------------- 7. final mesh, material, tidy up
P3 = allp()
ctr = (P3.min(0) + P3.max(0)) / 2
P3 = P3 - ctr
name = EXP['object_name']
old = bpy.data.objects.get(name)
if old:
    bpy.data.objects.remove(old, do_unlink=True)
if bpy.data.meshes.get(name):
    bpy.data.meshes.remove(bpy.data.meshes[name])
me = bpy.data.meshes.new(name)
me.from_pydata(P3.tolist(), [], [tuple(int(i) for i in f) for f in G_faces])
me.update()
uvl = me.uv_layers.new(name='UVMap')
uvl.data.foreach_set('uv', np.array([uv for fu in G_uv for uv in fu], float).ravel())
me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
me.validate(clean_customdata=False)
bm = bmesh.new(); bm.from_mesh(me)
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
bm.to_mesh(me); bm.free()
me.update()
ob = bpy.data.objects.new(name, me)
scene.collection.objects.link(ob)

tex_path = os.path.join(C.out, 'texture.png')
img = bpy.data.images.get('texture.png')
if img is None or os.path.abspath(bpy.path.abspath(img.filepath)) != os.path.abspath(tex_path):
    img = bpy.data.images.load(tex_path)
img.reload()
mat = bpy.data.materials.get(EXP['material_name']) or bpy.data.materials.new(EXP['material_name'])
mat.use_nodes = True
nt = mat.node_tree
for n_ in list(nt.nodes):
    nt.nodes.remove(n_)
out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (400, 0)
bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled'); bsdf.location = (100, 0)
texn = nt.nodes.new('ShaderNodeTexImage'); texn.location = (-300, 0); texn.image = img
texn.interpolation = 'Linear'
bsdf.inputs['Roughness'].default_value = EXP['roughness']
nt.links.new(texn.outputs['Color'], bsdf.inputs['Base Color'])
nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
mat.use_backface_culling = False                       # glTF doubleSided = true
ob.data.materials.append(mat)

bc = bpy.data.collections.get('GarmentBuild') or bpy.data.collections.new('GarmentBuild')
if bc.name not in scene.collection.children:
    scene.collection.children.link(bc)
for o in (bpy.data.objects.get('Mannequin'), sim):
    if o is None:
        continue
    for c in list(o.users_collection):
        c.objects.unlink(o)
    bc.objects.link(o)
    o.hide_render = True; o.hide_viewport = True
bpy.data.objects['Mannequin'].location = tuple(-ctr)

result = dict(object=name, verts=len(me.vertices), faces=len(me.polygons), tris=sum(len(p.vertices) - 2 for p in me.polygons),
              size_m=(P3.max(0) - P3.min(0)).round(4).tolist(), max_seam_gap_mm=round(gap * 1000, 2),
              turnups=len(P['turnups']), bands=len(P['bands']), patches=len(P['patches']))
