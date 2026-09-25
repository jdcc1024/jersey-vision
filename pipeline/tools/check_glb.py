"""Read a GLB back, report mesh/UV/material facts and draw its UVs over the template.
Usage: python pipeline/tools/check_glb.py [path/to/model.glb]
"""
import numpy as np, struct, json, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
GLB = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / 'assets' / 'model' / 'jersey.glb'
OUT = REPO / 'pipeline' / 'build'; OUT.mkdir(parents=True, exist_ok=True)
from pygltflib import GLTF2
from PIL import Image, ImageDraw
g = GLTF2().load(str(GLB))
blob = g.binary_blob()
def acc(i):
    a = g.accessors[i]; bv = g.bufferViews[a.bufferView]
    dt = {5126: np.float32, 5125: np.uint32, 5123: np.uint16}[a.componentType]
    nc = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}[a.type]
    off = (bv.byteOffset or 0) + (a.byteOffset or 0)
    return np.frombuffer(blob, dt, a.count * nc, off).reshape(a.count, nc) if nc > 1 else np.frombuffer(blob, dt, a.count, off)
prim = g.meshes[0].primitives[0]
pos = acc(prim.attributes.POSITION); uv = acc(prim.attributes.TEXCOORD_0); nrm = acc(prim.attributes.NORMAL); idx = acc(prim.indices).reshape(-1, 3)
print('nodes', [n.name for n in g.nodes], 'meshes', len(g.meshes), 'prims', len(g.meshes[0].primitives))
print('verts', len(pos), 'tris', len(idx), 'bbox', pos.min(0).round(3), pos.max(0).round(3))
print('uv range', uv.min(0).round(4), uv.max(0).round(4))
m = g.materials[0]; print('material', m.name, 'doubleSided', m.doubleSided, 'baseColorTexture', m.pbrMetallicRoughness.baseColorTexture is not None, 'images', len(g.images))
# draw UV layout (glTF v is top-down => pixel y = v*H)
T = Image.open(REPO / 'assets' / 'template' / 'template.png').convert('RGB'); W, H = T.size
S = 2
T = T.resize((W * S, H * S)); d = ImageDraw.Draw(T)
for f in idx:
    pts = [(uv[i, 0] * W * S, uv[i, 1] * H * S) for i in f]
    d.polygon(pts, outline=(0, 255, 255))
T.save(OUT / 'uv_layout_check.png')
print('wrote', OUT / 'uv_layout_check.png')
# texel stretch: compare 3D edge length vs UV edge length (px==mm)
e3 = np.linalg.norm(pos[idx[:, 0]] - pos[idx[:, 1]], axis=1)
e2 = np.linalg.norm((uv[idx[:, 0]] - uv[idx[:, 1]]) * [W, H], axis=1) / 1000
r = e3 / np.maximum(e2, 1e-9)
print('3D/UV edge ratio percentiles (5,25,50,75,95):', np.percentile(r, [5, 25, 50, 75, 95]).round(3))
