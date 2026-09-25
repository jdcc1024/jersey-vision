"""Jersey build - step 2: take the simulated panels (JerseySim @ last frame), weld seams, smooth,
add sleeve hem turn-ups, folded rib collar, inner neck tape and size tag, assign the template
texture and export a three.js-ready GLB.
UV convention: template pixel (px, py) -> Blender UV ((px+.5)/W, 1-(py+.5)/H)  (glTF: v = (py+.5)/H)
"""
import bpy, bmesh, json, math, os
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform

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
V2 = np.array(P['V'], float)
panel = np.array(P['panel'])
F = np.array(P['F'], int)
N = len(V2)
scene = bpy.context.scene

def uv_of(px, py):
    return ((px + 0.5) / TW, 1.0 - (py + 0.5) / TH)

# ------------------------------------------------------------- 1. simulated positions
sim = bpy.data.objects['JerseySim']
scene.frame_set(scene.frame_end)
dg = bpy.context.evaluated_depsgraph_get()
se = sim.evaluated_get(dg)
m = se.to_mesh()
co = np.zeros(len(m.vertices) * 3); m.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
se.to_mesh_clear()
co = co @ np.array(sim.matrix_world)[:3, :3].T + np.array(sim.matrix_world)[:3, 3]

# ------------------------------------------------------------- 2. weld seams (union-find)
par = list(range(N))
def find(i):
    while par[i] != i:
        par[i] = par[par[i]]; i = par[i]
    return i
for a, b in P['pairs']:
    ra, rb = find(a), find(b)
    if ra != rb: par[rb] = ra
roots = np.array([find(i) for i in range(N)])
uniq, inv = np.unique(roots, return_inverse=True)
M = len(uniq)
pos = np.zeros((M, 3)); cnt = np.zeros(M)
np.add.at(pos, inv, co); np.add.at(cnt, inv, 1); pos /= cnt[:, None]
faces = inv[F]

# ------------------------------------------------------------- 3. Taubin smoothing (no shrink)
def taubin(pos, faces, iters=10, lam=0.5, mu=-0.53, pinned=None):
    e = np.sort(np.r_[faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]], axis=1)
    ue, ec = np.unique(e, axis=0, return_counts=True)
    bnd_e = ue[ec == 1]
    isb = np.zeros(len(pos), bool); isb[bnd_e.ravel()] = True
    # interior verts use all edges, boundary verts use boundary edges only
    int_e = ue[~(isb[ue[:, 0]] | isb[ue[:, 1]])]
    mix_e = ue[(isb[ue[:, 0]] ^ isb[ue[:, 1]])]
    src, dst = [], []
    for ed in (int_e,):
        src += [ed[:, 0], ed[:, 1]]; dst += [ed[:, 1], ed[:, 0]]
    # mixed edges: only interior endpoint sees the boundary one
    ib = isb[mix_e[:, 0]]
    src += [np.where(ib, mix_e[:, 1], mix_e[:, 0])]; dst += [np.where(ib, mix_e[:, 0], mix_e[:, 1])]
    src += [bnd_e[:, 0], bnd_e[:, 1]]; dst += [bnd_e[:, 1], bnd_e[:, 0]]
    src = np.concatenate(src); dst = np.concatenate(dst)
    deg = np.bincount(src, minlength=len(pos)).astype(float); deg[deg == 0] = 1
    p = pos.copy()
    for _ in range(iters):
        for f in (lam, mu):
            acc = np.zeros_like(p); np.add.at(acc, src, p[dst])
            L = acc / deg[:, None] - p
            if pinned is not None: L[pinned] = 0
            p = p + f * L
    return p, isb

pos, isb = taubin(pos, faces, iters=int(globals().get('SMOOTH_ITERS', 12)))

def vnormals(pos, faces):
    fn = np.cross(pos[faces[:, 1]] - pos[faces[:, 0]], pos[faces[:, 2]] - pos[faces[:, 0]])
    vn = np.zeros_like(pos)
    for k in range(3): np.add.at(vn, faces[:, k], fn)
    return vn / np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-12)
vn = vnormals(pos, faces)

# ------------------------------------------------------------- geometry accumulators
G_pos = [pos]; G_faces = []; G_uv = []; nverts = [M]
def add_verts(p):
    base = nverts[0]; G_pos.append(np.asarray(p)); nverts[0] += len(p); return base
for f, fo in zip(faces, F):
    G_faces.append(tuple(f)); G_uv.append([uv_of(*V2[i]) for i in fo])

# pattern(2D) -> 3D lookup for one panel
def panel_mapper(pid):
    fp = F[panel[F[:, 0]] == pid]
    verts = [Vector((x, y, 0.0)) for x, y in V2]
    bvh = BVHTree.FromPolygons(verts, [tuple(f) for f in fp])
    def mapf(qx, qy):
        loc, _, idx, _ = bvh.find_nearest(Vector((qx, qy, 0.0)))
        a, b, c = fp[idx]
        A, B, C = verts[a], verts[b], verts[c]
        w = barycentric_transform(loc, A, B, C, Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))
        ia, ib, ic = inv[a], inv[b], inv[c]
        p3 = w[0] * pos[ia] + w[1] * pos[ib] + w[2] * pos[ic]
        n3 = w[0] * vn[ia] + w[1] * vn[ib] + w[2] * vn[ic]
        return p3, n3 / np.linalg.norm(n3)
    return mapf

# ------------------------------------------------------------- 4. sleeve hem turn-ups
for sname, pid in (('sleeve_L', 2), ('sleeve_R', 3)):
    fd = P['fold'][sname]
    fv = np.array(fd['v']); ff = np.array(fd['f'])
    fy = fd['fold_y']; nfl = fd['n_foldline']
    mapf = panel_mapper(pid)
    idx_map = np.zeros(len(fv), int)
    for k in range(nfl):
        idx_map[k] = inv[fd['foldline_sim_ids'][k]]
    newp = []
    for k in range(nfl, len(fv)):
        x, y = fv[k]
        d = max(0.0, y - fy)
        p3, n3 = mapf(x, 2 * fy - y)
        off = 0.0035 * min(1.0, d / 4.0) ** 0.5
        newp.append(p3 - n3 * off)
    base = add_verts(newp)
    idx_map[nfl:] = base + np.arange(len(fv) - nfl)
    for ia, ib in fd['flare_pairs']:      # weld the turn-up's underarm seam
        idx_map[ib] = idx_map[ia] if ia >= nfl or ib >= nfl else idx_map[ib]
    for f in ff:
        G_faces.append(tuple(idx_map[f])); G_uv.append([uv_of(*fv[i]) for i in f])

# ------------------------------------------------------------- 5. folded rib collar
bx, by, bw, bh = P['boxes']['neck']
fr = P['segs']['front.neckA.neckB']; bk = P['segs']['back.neckA.neckB']
loop_orig = fr[::-1] + bk[::-1][1:-1]          # +X -> front -> -X -> back
Lp = pos[inv[np.array(loop_orig)]]
nF = len(fr)
seglen = np.linalg.norm(np.diff(np.r_[Lp, Lp[:1]], axis=0), axis=1)
cum = np.r_[0, np.cumsum(seglen)]              # len = n+1 (closing point)
front_len = cum[nF - 1]; tot = cum[-1]
u_x = np.where(np.arange(len(cum)) <= nF - 1,
               bx + (cum / front_len) * (1392 - bx),
               1392 + (cum - front_len) / (tot - front_len) * (bx + bw - 1392))
ctr = Lp.mean(0)
H = 0.030; T = 0.003; RF = T / 2; BETA = math.radians(globals().get('COLLAR_LEAN_DEG', 28))
rows = [(h, 0.0, 193 - 30 * h / H) for h in np.linspace(0, H, 7)]
rows += [(H + RF * math.sin(a), -RF * (1 - math.cos(a)), 163.0) for a in np.radians([45, 90, 135])]
rows += [(h, -T, 133 + 30 * h / H) for h in np.linspace(H, 0, 7)]
cols = np.r_[Lp, Lp[:1]]
radial = cols - ctr; radial[:, 2] = 0; radial /= np.linalg.norm(radial, axis=1, keepdims=True)
up = np.array([0, 0, 1.0])
dirs = up[None] * math.cos(BETA) - radial * math.sin(BETA)
cp = []
for (h, ro, _) in rows:
    cp.append(cols + dirs * h + radial * ro)
cp = np.array(cp)                                 # rows x cols x 3
nr, nc = cp.shape[:2]
base = add_verts(cp.reshape(-1, 3))
vid = lambda r, c: base + r * nc + c
cf = []; cu = []
for r in range(nr - 1):
    for c in range(nc - 1):
        q = (vid(r, c), vid(r, c + 1), vid(r + 1, c + 1), vid(r + 1, c))
        uvq = [((u_x[c] + 0.5) / TW, 1 - (rows[r][2] + 0.5) / TH), ((u_x[c + 1] + 0.5) / TW, 1 - (rows[r][2] + 0.5) / TH),
               ((u_x[c + 1] + 0.5) / TW, 1 - (rows[r + 1][2] + 0.5) / TH), ((u_x[c] + 0.5) / TW, 1 - (rows[r + 1][2] + 0.5) / TH)]
        cf.append(q); cu.append(uvq)
# orient so the outer layer faces outwards
allp = np.concatenate(G_pos)
q = cf[0]; nrm = np.cross(allp[q[1]] - allp[q[0]], allp[q[3]] - allp[q[0]])
if np.dot(nrm, radial[0]) < 0:
    cf = [tuple(reversed(f)) for f in cf]; cu = [list(reversed(u)) for u in cu]
G_faces += cf; G_uv += cu

# ------------------------------------------------------------- 6. inner neck tape + size tag (inside back)
mapB = panel_mapper(1)
def cut_poly(p, length):
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
    k = np.searchsorted(d, length)
    t = (length - d[k - 1]) / (d[k] - d[k - 1])
    return np.r_[p[:k], [p[k - 1] + t * (p[k] - p[k - 1])]]
def resample(p, n):
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
    t = np.linspace(0, d[-1], n)
    return np.c_[np.interp(t, d, p[:, 0]), np.interp(t, d, p[:, 1])]
tx, ty, tw, th = P['boxes']['inner_neck']
neck = V2[P['segs']['back.neckA.neckB']]
nl = np.sum(np.linalg.norm(np.diff(neck, axis=0), axis=1))
ext = max(0.0, (tw - nl) / 2)
shA = V2[P['segs']['back.neckA.shA']]; shB = V2[P['segs']['back.neckB.shB']]
path = np.r_[cut_poly(shA, ext)[::-1][:-1], neck, cut_poly(shB, ext)[1:]] if ext > 1 else neck
path = resample(path, 48)
tang = np.gradient(path, axis=0); tang /= np.linalg.norm(tang, axis=1, keepdims=True)
nrm2 = np.c_[-tang[:, 1], tang[:, 0]]
nrm2 *= np.sign(nrm2[:, 1:2] + 1e-9)            # point into the panel (+py)
plen = np.r_[0, np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))]
TAPE_ROWS = 5
tp = []; tuv = []
for j in range(TAPE_ROWS):
    w = th * j / (TAPE_ROWS - 1)
    for i in range(len(path)):
        qx, qy = path[i] + nrm2[i] * (w + 1.0)
        p3, n3 = mapB(qx, qy)
        tp.append(p3 - n3 * 0.0015)
        tuv.append(uv_of(tx + tw - plen[i] / plen[-1] * tw, ty + w))
base = add_verts(tp)
ncol = len(path)
tf = []; tfu = []
for j in range(TAPE_ROWS - 1):
    for i in range(ncol - 1):
        q = (base + j * ncol + i, base + j * ncol + i + 1, base + (j + 1) * ncol + i + 1, base + (j + 1) * ncol + i)
        tf.append(q); tfu.append([tuv[k - base] for k in q])
allp = np.concatenate(G_pos)
_, n_in = mapB(*path[len(path) // 2])
q = tf[len(tf) // 2]
if np.dot(np.cross(allp[q[1]] - allp[q[0]], allp[q[3]] - allp[q[0]]), -n_in) < 0:
    tf = [tuple(reversed(f)) for f in tf]; tfu = [list(reversed(u)) for u in tfu]
G_faces += tf; G_uv += tfu

sx0, sy0, sx1, sy1 = 1350, 10, 1433, 49          # size-tag artwork box on the template
cxb = (V2[P['corner']['back.neckA'], 0] + V2[P['corner']['back.neckB'], 0]) / 2
neck_low = neck[:, 1].max()
tag_w, tag_h = sx1 - sx0, sy1 - sy0
x0, y0 = cxb - tag_w / 2, neck_low + th + 10
sp = []; suv = []
NX, NY = 8, 4
for j in range(NY + 1):
    for i in range(NX + 1):
        qx, qy = x0 + tag_w * i / NX, y0 + tag_h * j / NY
        p3, n3 = mapB(qx, qy)
        sp.append(p3 - n3 * 0.0022)
        suv.append(uv_of(sx1 - tag_w * i / NX, sy0 + tag_h * j / NY))   # mirrored: read from inside
base = add_verts(sp)
sf = []; sfu = []
for j in range(NY):
    for i in range(NX):
        q = (base + j * (NX + 1) + i, base + j * (NX + 1) + i + 1, base + (j + 1) * (NX + 1) + i + 1, base + (j + 1) * (NX + 1) + i)
        sf.append(q); sfu.append([suv[k - base] for k in q])
allp = np.concatenate(G_pos)
_, n_in = mapB(cxb, y0 + tag_h / 2)
q = sf[0]
if np.dot(np.cross(allp[q[1]] - allp[q[0]], allp[q[3]] - allp[q[0]]), -n_in) < 0:
    sf = [tuple(reversed(f)) for f in sf]; sfu = [list(reversed(u)) for u in sfu]
G_faces += sf; G_uv += sfu

# ------------------------------------------------------------- 7. build final mesh
allp = np.concatenate(G_pos)
ctr = (allp.min(0) + allp.max(0)) / 2
allp = allp - ctr                                  # centre bounding box on the origin
old = bpy.data.objects.get('Jersey')
if old: bpy.data.objects.remove(old, do_unlink=True)
if bpy.data.meshes.get('Jersey'): bpy.data.meshes.remove(bpy.data.meshes['Jersey'])
me = bpy.data.meshes.new('Jersey')
me.from_pydata(allp.tolist(), [], [tuple(int(i) for i in f) for f in G_faces])
me.update()
uvl = me.uv_layers.new(name='UVMap')
flat_uv = [uv for fu in G_uv for uv in fu]
uvl.data.foreach_set('uv', np.array(flat_uv, float).ravel())
me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
me.validate(clean_customdata=False)
bm = bmesh.new(); bm.from_mesh(me)
loose = [v for v in bm.verts if not v.link_faces]
bmesh.ops.delete(bm, geom=loose, context='VERTS')
bm.to_mesh(me); bm.free()
me.update()
ob = bpy.data.objects.new('Jersey', me)
scene.collection.objects.link(ob)

# material
tex_path = os.path.join(TEMPLATE_DIR, 'jersey_texture.png')
img = bpy.data.images.get('jersey_texture.png') or bpy.data.images.load(tex_path)
img.reload()
mat = bpy.data.materials.get('JerseyPrint') or bpy.data.materials.new('JerseyPrint')
mat.use_nodes = True
nt = mat.node_tree
for n_ in list(nt.nodes): nt.nodes.remove(n_)
out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (400, 0)
bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled'); bsdf.location = (100, 0)
texn = nt.nodes.new('ShaderNodeTexImage'); texn.location = (-300, 0); texn.image = img
texn.interpolation = 'Linear'
bsdf.inputs['Roughness'].default_value = 0.78
nt.links.new(texn.outputs['Color'], bsdf.inputs['Base Color'])
nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
mat.use_backface_culling = False                   # glTF doubleSided = true
ob.data.materials.append(mat)

# tidy: build helpers into a hidden collection
bc = bpy.data.collections.get('JerseyBuild') or bpy.data.collections.new('JerseyBuild')
if bc.name not in scene.collection.children: scene.collection.children.link(bc)
for o in (bpy.data.objects.get('Mannequin'), sim):
    if o is None: continue
    for c in list(o.users_collection): c.objects.unlink(o)
    bc.objects.link(o)
    o.hide_render = True; o.hide_viewport = True
bpy.data.objects['Mannequin'].location = tuple(-ctr)
sim.location = tuple(-ctr)

result = dict(verts=len(me.vertices), faces=len(me.polygons), tris=sum(len(p.vertices) - 2 for p in me.polygons),
              bbox=(allp.max(0) - allp.min(0)).round(4).tolist(), welded_from=N, main_verts=M,
              collar_rows=nr, collar_cols=nc)
