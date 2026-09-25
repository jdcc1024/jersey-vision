"""Stage 1: sewing-template -> panel meshes (2D, pixel units == mm) with matched seam sampling.
Template: 1656 x 790 px. UV of any vertex = (px/1656, 1 - py/790).
"""
import json, numpy as np, cv2, triangle
from PIL import Image
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
TEMPLATE = REPO / 'assets' / 'template' / 'template.png'
BUILD = REPO / 'pipeline' / 'build'
BUILD.mkdir(parents=True, exist_ok=True)


EDGE = 12.0            # target edge length in px (1 px == 1 mm)
TW, TH = 1656, 790

im = np.array(Image.open(TEMPLATE)).astype(int)
bg = (np.abs(im - 141).sum(2) <= 12)
mask = (~bg).astype(np.uint8) * 255
n, lab, stats, cent = cv2.connectedComponentsWithStats(mask, 8)
comp = {}
for i in range(1, n):
    x, y, w, h, a = stats[i]
    if a < 300: continue
    if w > 500 and h > 700: nm = 'front' if x < 300 else 'back'
    elif h > 200: nm = 'sleeve_L' if y < 400 else 'sleeve_R'
    elif w > 450: nm = 'neck'
    elif w > 300: nm = 'inner_neck'
    else: nm = 'size_tag'
    comp[nm] = (i, (int(x), int(y), int(w), int(h)))

def contour(nm):
    m = (lab == comp[nm][0]).astype(np.uint8) * 255
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cs, key=cv2.contourArea)[:, 0, :].astype(float)
    # pixel centres -> pixel edges: push contour outward by 0.5px is negligible; keep centres
    return c

SL = 278  # sleeve_R is sleeve_L shifted down by 278 px
corners = {
    'front': dict(neckA=(197, 15), neckB=(379, 15), shA=(59, 55), shB=(517, 55),
                  uaA=(15, 315), uaB=(561, 315), hemA=(15, 771), hemB=(561, 771)),
    'back': dict(neckA=(751, 18), neckB=(943, 18), shA=(617, 55), shB=(1076, 55),
                 uaA=(573, 315), uaB=(1120, 315), hemA=(573, 774), hemB=(1120, 774)),
}
for s, dy in (('sleeve_L', 0), ('sleeve_R', SL)):
    corners[s] = dict(uaA=(1132, 356 + dy), peak=(1390.5, 229 + dy), uaB=(1649, 356 + dy),
                      foldA=(1187, 469 + dy), foldB=(1594, 469 + dy),
                      hemA=(1177, 494 + dy), hemB=(1604, 494 + dy))

def smooth_poly(p, iters=30):
    p = p.copy()
    for _ in range(iters):
        p[1:-1] = 0.5 * p[1:-1] + 0.25 * (p[:-2] + p[2:])
    return p

def resample(p, N):
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
    t = np.linspace(0, d[-1], N)
    return np.c_[np.interp(t, d, p[:, 0]), np.interp(t, d, p[:, 1])]

def plen(p): return float(np.sum(np.linalg.norm(np.diff(p, axis=0), axis=1)))

# --- raw segments along contours between corners -------------------------------------------
raw = {}
def path_between(c, a, b, avoid):
    """contour path from corner a to corner b that does not pass through any 'avoid' corner"""
    n = len(c)
    ia = int(np.argmin(np.linalg.norm(c - a, axis=1))); ib = int(np.argmin(np.linalg.norm(c - b, axis=1)))
    av = [int(np.argmin(np.linalg.norm(c - q, axis=1))) for q in avoid]
    fwd = [(ia + k) % n for k in range((ib - ia) % n + 1)]
    bwd = [(ia - k) % n for k in range((ia - ib) % n + 1)]
    fs, bs = set(fwd[1:-1]), set(bwd[1:-1])
    okf = not any(v in fs for v in av); okb = not any(v in bs for v in av)
    idx = fwd if (okf and (not okb or len(fwd) <= len(bwd))) else bwd
    p = c[idx].copy(); p[0] = a; p[-1] = b
    return p

def seg(panel, a, b, contour_name=None, straight=False):
    key = (panel, a, b)
    if key in raw: return raw[key]
    cn = contour_name or panel
    C = corners[panel]
    if straight:
        p = np.array([C[a], C[b]], float)
        p = resample(p, 200)
    else:
        c = contour(cn)
        avoid = [C[k] for k in C if k not in (a, b)]
        p = path_between(c, np.array(C[a], float), np.array(C[b], float), avoid)
        p = smooth_poly(p)
    raw[key] = p
    return p

# segment definitions per panel as closed loops of corner names
loops = {
    'front': ['neckA', 'neckB', 'shB', 'uaB', 'hemB', 'hemA', 'uaA', 'shA'],
    'back':  ['neckA', 'neckB', 'shB', 'uaB', 'hemB', 'hemA', 'uaA', 'shA'],
    'sleeve_L': ['peak', 'uaB', 'foldB', 'foldA', 'uaA'],
    'sleeve_R': ['peak', 'uaB', 'foldB', 'foldA', 'uaA'],
}
straight_segs = {('sleeve_L', 'foldB', 'foldA'), ('sleeve_R', 'foldB', 'foldA'),
                 ('front', 'hemB', 'hemA'), ('back', 'hemB', 'hemA')}

# seams: (panelA, a0, a1) <-> (panelB, b0, b1) ; point k of first == point k of second
# Wearer's left (+X) = front image-right (B side) = back image-left (A side) = sleeve_L.
# sleeve_L: image-left half -> front ; sleeve_R: image-right half -> front
seams = [
    (('front', 'uaB', 'hemB'), ('back', 'uaA', 'hemA')),      # side seam  +X
    (('front', 'uaA', 'hemA'), ('back', 'uaB', 'hemB')),      # side seam  -X
    (('front', 'neckB', 'shB'), ('back', 'neckA', 'shA')),    # shoulder   +X
    (('front', 'neckA', 'shA'), ('back', 'neckB', 'shB')),    # shoulder   -X
    (('front', 'shB', 'uaB'), ('sleeve_L', 'peak', 'uaA')),   # armhole +X front
    (('back', 'shA', 'uaA'), ('sleeve_L', 'peak', 'uaB')),    # armhole +X back
    (('front', 'shA', 'uaA'), ('sleeve_R', 'peak', 'uaB')),   # armhole -X front
    (('back', 'shB', 'uaB'), ('sleeve_R', 'peak', 'uaA')),    # armhole -X back
    (('sleeve_L', 'uaA', 'foldA'), ('sleeve_L', 'uaB', 'foldB')),  # underarm L
    (('sleeve_R', 'uaA', 'foldA'), ('sleeve_R', 'uaB', 'foldB')),  # underarm R
]

def getseg(panel, a, b):
    if (panel, a, b) in straight_segs or (panel, b, a) in straight_segs:
        return seg(panel, a, b, straight=True)
    rev = (panel, b, a) in raw
    if rev: return raw[(panel, b, a)][::-1]
    return seg(panel, a, b)

# decide sample counts
counts = {}
def setN(key, N):
    counts[key] = N; counts[(key[0], key[2], key[1])] = N
for A, B in seams:
    L = max(plen(getseg(*A)), plen(getseg(*B)))
    N = max(3, int(round(L / EDGE)) + 1)
    setN(A, N); setN(B, N)
for p, lp in loops.items():
    for i in range(len(lp)):
        key = (p, lp[i], lp[(i + 1) % len(lp)])
        if key not in counts:
            setN(key, max(3, int(round(plen(getseg(*key)) / EDGE)) + 1))

sampled = {}
def samp(panel, a, b):
    key = (panel, a, b)
    if key not in sampled:
        rk = (panel, b, a)
        if rk in sampled: return sampled[rk][::-1]
        sampled[key] = resample(getseg(panel, a, b), counts[key])
    return sampled[key]

# --- build panel meshes -----------------------------------------------------------------------
V = []; F = []; PANEL = []; corner_vid = {}; seg_vids = {}
panel_ids = {'front': 0, 'back': 1, 'sleeve_L': 2, 'sleeve_R': 3}

def build_panel(p, lp):
    bpts = []; bmap = []
    for i in range(len(lp)):
        a, b = lp[i], lp[(i + 1) % len(lp)]
        s = samp(p, a, b)
        bpts.extend(s[:-1].tolist())
    bpts = np.array(bpts)
    nb = len(bpts)
    segs = np.c_[np.arange(nb), (np.arange(nb) + 1) % nb]
    area = 0.433 * EDGE * EDGE * 1.05
    T = triangle.triangulate(dict(vertices=bpts, segments=segs), f'pq30a{area:.1f}Y')
    tv, tf = T['vertices'], T['triangles']
    assert np.allclose(tv[:nb], bpts), 'boundary moved'
    base = len(V)
    V.extend(tv.tolist()); PANEL.extend([panel_ids[p]] * len(tv))
    # orient faces CCW in (x, -y) i.e. front-facing when pattern viewed normally
    for f in tf:
        a_, b_, c_ = tv[f[0]], tv[f[1]], tv[f[2]]
        cr = (b_[0] - a_[0]) * (-(c_[1] - a_[1])) - (-(b_[1] - a_[1])) * (c_[0] - a_[0])
        F.append([base + f[0], base + f[1], base + f[2]] if cr > 0 else [base + f[0], base + f[2], base + f[1]])
    # record segment vertex ids
    k = 0
    for i in range(len(lp)):
        a, b = lp[i], lp[(i + 1) % len(lp)]
        N = counts[(p, a, b)]
        ids = [base + ((k + j) % nb) for j in range(N)]
        seg_vids[(p, a, b)] = ids; seg_vids[(p, b, a)] = ids[::-1]
        corner_vid[(p, a)] = base + k
        k += N - 1
    return len(tv), len(tf)

for p, lp in loops.items():
    print(p, build_panel(p, lp))

pairs = []
for A, B in seams:
    ia, ib = seg_vids[A], seg_vids[B]
    assert len(ia) == len(ib)
    pairs.extend(zip(ia, ib))

# --- sleeve hem-allowance (fold) regions: separate small meshes ------------------------------
fold = {}
for s in ('sleeve_L', 'sleeve_R'):
    C = corners[s]
    fl = sampled.get((s, 'foldB', 'foldA'))
    if fl is None: fl = sampled[(s, 'foldA', 'foldB')][::-1]
    fl = fl[::-1]  # foldA -> foldB
    c = contour(s)
    def cp(a, b):
        avoid = [C[k] for k in C if k not in (a, b)]
        pth = smooth_poly(path_between(c, np.array(C[a], float), np.array(C[b], float), avoid), 5)
        return resample(pth, max(3, int(round(plen(pth) / EDGE)) + 1))
    fa = cp('foldA', 'hemA'); fb = cp('foldB', 'hemB')
    Nf = min(len(fa), len(fb)); fa = resample(fa, Nf); fb = resample(fb, Nf)
    hem = resample(np.array([C['hemA'], C['hemB']], float), max(3, int(round((C['hemB'][0] - C['hemA'][0]) / EDGE)) + 1))
    loop = np.r_[fl, fb[1:], hem[::-1][1:], fa[::-1][1:-1]]
    nb = len(loop)
    segs = np.c_[np.arange(nb), (np.arange(nb) + 1) % nb]
    T = triangle.triangulate(dict(vertices=loop, segments=segs), f'pq30a{0.433*EDGE*EDGE:.1f}Y')
    tv, tf = T['vertices'], T['triangles']
    assert np.allclose(tv[:nb], loop)
    ff = []
    for f in tf:
        a_, b_, c_ = tv[f[0]], tv[f[1]], tv[f[2]]
        cr = (b_[0] - a_[0]) * (-(c_[1] - a_[1])) - (-(b_[1] - a_[1])) * (c_[0] - a_[0])
        ff.append([int(f[0]), int(f[1]), int(f[2])] if cr > 0 else [int(f[0]), int(f[2]), int(f[1])])
    nfl = len(fl)
    near = lambda q: int(np.argmin(np.linalg.norm(loop - q, axis=1)))
    ia = [near(q) for q in fa]; ib = [near(q) for q in fb]
    fold[s] = dict(v=tv.tolist(), f=ff, foldline_sim_ids=seg_vids[(s, 'foldA', 'foldB')],
                   n_foldline=nfl, flare_pairs=list(zip(ia, ib)), fold_y=C['foldA'][1])
    print(s, 'fold region', len(tv), len(ff), 'flare pairs', list(zip(ia, ib)))

out = dict(
    template_size=[TW, TH], px_to_m=0.001,
    V=V, F=[list(map(int, f)) for f in F], panel=PANEL,
    pairs=[list(map(int, p)) for p in pairs],
    corner={f'{k[0]}.{k[1]}': int(v) for k, v in corner_vid.items()},
    segs={f'{k[0]}.{k[1]}.{k[2]}': list(map(int, v)) for k, v in seg_vids.items()},
    corners={p: {k: list(v) for k, v in d.items()} for p, d in corners.items()},
    fold=fold,
    boxes={k: v[1] for k, v in comp.items()},
)
json.dump(out, open(BUILD / 'pattern.json', 'w'))
print('verts', len(V), 'faces', len(F), 'pairs', len(pairs))

# visualisation
viz = Image.open(TEMPLATE).convert('RGB').resize((TW * 2, TH * 2))
from PIL import ImageDraw
d = ImageDraw.Draw(viz)
Vn = np.array(V) * 2
for f in F:
    d.polygon([tuple(Vn[i]) for i in f], outline=(0, 200, 255))
for a, b in pairs[::3]:
    d.line([tuple(Vn[a]), tuple(Vn[b])], fill=(255, 0, 0), width=1)
for s in fold:
    fv = np.array(fold[s]['v']) * 2
    for f in fold[s]['f']:
        d.polygon([tuple(fv[i]) for i in f], outline=(255, 255, 0))
viz.save(BUILD / 'pattern_viz.png')
