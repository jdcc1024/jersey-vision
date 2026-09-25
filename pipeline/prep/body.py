"""Simple invisible-mannequin collider (SDF + marching cubes). Metres. HPS (neck point) at z=0.
Front = -Y, wearer's left = +X."""
import numpy as np, json
from skimage import measure
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
TEMPLATE = REPO / 'assets' / 'template' / 'template.png'
BUILD = REPO / 'pipeline' / 'build'
BUILD.mkdir(parents=True, exist_ok=True)


VOX = 0.006
xs = np.arange(-0.46, 0.46, VOX); ys = np.arange(-0.2, 0.2, VOX); zs = np.arange(-0.96, 0.18, VOX)
X, Y, Z = np.meshgrid(xs, ys, zs, indexing='ij')

def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)

def capsule(P, a, b, ra, rb):
    a = np.array(a); b = np.array(b); ba = b - a
    pa = np.stack([P[0] - a[0], P[1] - a[1], P[2] - a[2]], -1)
    h = np.clip((pa @ ba) / (ba @ ba), 0, 1)
    d = np.linalg.norm(pa - h[..., None] * ba, axis=-1)
    return d - (ra + (rb - ra) * h)

P = (X, Y, Z)
# torso: elliptic cross-sections varying with z
zk = np.array([-0.96, -0.80, -0.66, -0.52, -0.40, -0.28, -0.18, -0.10, -0.06])
ak = np.array([0.198, 0.198, 0.192, 0.188, 0.196, 0.205, 0.198, 0.172, 0.130])
bk = np.array([0.130, 0.130, 0.126, 0.124, 0.128, 0.135, 0.130, 0.112, 0.082])
yk = np.array([0.0, 0.0, 0.0, 0.0, -0.004, -0.008, -0.006, 0.0, 0.004])
A = np.interp(Z, zk, ak); B = np.interp(Z, zk, bk); YC = np.interp(Z, zk, yk)
r = np.sqrt((X / A) ** 2 + ((Y - YC) / B) ** 2)
torso = (r - 1) * np.minimum(A, B)
torso = np.maximum(torso, Z - (-0.06))      # cap top
torso = np.maximum(torso, -0.96 - Z + 0.0)  # cap bottom (open-ish)

neck = capsule(P, (0, 0.012, -0.10), (0, 0.02, 0.16), 0.066, 0.058)
shoulders = capsule(P, (-0.165, 0.008, -0.105), (0.165, 0.008, -0.105), 0.056, 0.056)
ang = np.radians(50)
body = smin(torso, shoulders, 0.05)
body = smin(body, neck, 0.035)
for sgn in (1, -1):
    j = np.array([sgn * 0.180, 0.006, -0.112])
    d = np.array([sgn * np.cos(ang), 0, -np.sin(ang)])
    arm = capsule(P, j, j + d * 0.34, 0.064, 0.052)
    body = smin(body, arm, 0.03)

verts, faces, normals, _ = measure.marching_cubes(body, 0.0, spacing=(VOX, VOX, VOX))
verts += np.array([xs[0], ys[0], zs[0]])
print('body verts', len(verts), 'faces', len(faces), verts.min(0), verts.max(0))
np.savez(BUILD / 'body.npz', v=verts.astype(np.float32), f=faces.astype(np.int32))
json.dump(dict(v=np.round(verts, 5).tolist(), f=faces.tolist()), open(BUILD / 'body.json', 'w'))
