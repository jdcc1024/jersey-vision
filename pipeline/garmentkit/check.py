"""Verification of an exported model.

check:   read out/model.glb back, report mesh/UV/material facts and texture distortion, fail on
         out-of-range UVs or noisy distortion, draw the UVs over the template -> build/uv_check.png
         and a distortion heat map -> build/distortion.png
compare: put the reference mockups next to the Blender renders -> build/compare.png
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .common import build_dir, load_spec, out_dir


def _read_glb(path: Path):
    from pygltflib import GLTF2
    g = GLTF2().load(str(path))
    blob = g.binary_blob()

    def acc(i):
        a = g.accessors[i]; bv = g.bufferViews[a.bufferView]
        dt = {5126: np.float32, 5125: np.uint32, 5123: np.uint16, 5121: np.uint8}[a.componentType]
        nc = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}[a.type]
        off = (bv.byteOffset or 0) + (a.byteOffset or 0)
        arr = np.frombuffer(blob, dt, a.count * nc, off)
        return arr.reshape(a.count, nc) if nc > 1 else arr
    prim = g.meshes[0].primitives[0]
    return g, acc(prim.attributes.POSITION), acc(prim.attributes.TEXCOORD_0), acc(prim.indices).reshape(-1, 3)


def run(gdir, glb=None, verbose=True):
    from PIL import Image, ImageDraw
    spec = load_spec(gdir)
    glb = Path(glb) if glb else out_dir(gdir) / 'model.glb'
    g, pos, uv, idx = _read_glb(glb)
    T = Image.open(gdir / spec['template']['file']).convert('RGB')
    W, H = T.size
    mmpp = spec['template']['mm_per_px']
    problems = []
    if uv.min() < -1e-4 or uv.max() > 1 + 1e-4:
        problems.append(f'UVs outside 0..1: {uv.min(0)} {uv.max(0)}')
    if len(g.meshes) != 1 or len(g.meshes[0].primitives) != 1:
        problems.append('expected exactly one mesh with one primitive')
    mat = g.materials[0] if g.materials else None
    if not mat or not mat.doubleSided:
        problems.append('material should be doubleSided')
    e3 = np.linalg.norm(pos[idx[:, 0]] - pos[idx[:, 1]], axis=1)
    e2 = np.linalg.norm((uv[idx[:, 0]] - uv[idx[:, 1]]) * [W, H], axis=1) * mmpp / 1000
    ratio = e3 / np.maximum(e2, 1e-9)
    ok = e2 > 1e-4
    pct = np.percentile(ratio[ok], [5, 25, 50, 75, 95])
    if abs(pct[2] - 1) > 0.12:
        problems.append(f'median 3D/pattern edge ratio {pct[2]:.3f}: model scale does not match the template scale')
    # texture distortion: singular values of the UV->3D map per triangle (1.0 = print exactly as drawn)
    Pm = pos[idx] * 1000.0
    Um = uv[idx] * [W, H] * mmpp
    dP = np.stack([Pm[:, 1] - Pm[:, 0], Pm[:, 2] - Pm[:, 0]], 2)
    dU = np.stack([Um[:, 1] - Um[:, 0], Um[:, 2] - Um[:, 0]], 2)
    good = np.abs(np.linalg.det(dU)) > 1e-3
    sv = np.linalg.svd(np.einsum('nij,njk->nik', dP[good], np.linalg.inv(dU[good])), compute_uv=False)
    aniso = sv[:, 0] / sv[:, 1]
    tri = idx[good]
    e2t = {}
    for t, (a, b, c) in enumerate(tri):
        for x, y in ((a, b), (b, c), (c, a)):
            e2t.setdefault((min(x, y), max(x, y)), []).append(t)
    prs = np.array([v for v in e2t.values() if len(v) == 2])
    ls = np.log(sv)
    nbr = np.abs(ls[prs[:, 0]] - ls[prs[:, 1]]).max(1)
    if np.median(nbr) > 0.05:
        problems.append(f'texture distortion changes sharply between neighbouring triangles (median {np.median(nbr):.3f}); '
                        'printed text will look wavy. Smoothing is probably sliding vertices (finish.smooth_mode should be "normal")')
    heat = Image.new('RGB', (W, H), (70, 70, 70)); dh = ImageDraw.Draw(heat)
    Ug = uv[tri] * [W, H]
    for t in range(len(tri)):
        v = float(np.clip((aniso[t] - 1) / 0.35, 0, 1))
        a_ = float(np.clip(np.log(sv[t, 0] * sv[t, 1]) / 0.3, -1, 1))
        dh.polygon([tuple(q) for q in Ug[t]], fill=(int(40 + 215 * v), int(200 * (1 - v)), int(140 + 110 * a_)))
    S = 2 if max(W, H) < 3000 else 1
    img = T.resize((W * S, H * S)); d = ImageDraw.Draw(img)
    for f in idx:
        d.polygon([(uv[i, 0] * W * S, uv[i, 1] * H * S) for i in f], outline=(0, 255, 255))
    B = build_dir(gdir)
    img.save(B / 'uv_check.png')
    heat.save(B / 'distortion.png')
    ext = pos.max(0) - pos.min(0)
    rep = dict(file=str(glb), bytes=glb.stat().st_size, nodes=[n.name for n in g.nodes], verts=int(len(pos)), tris=int(len(idx)),
               size_m=ext.round(4).tolist(), uv_min=uv.min(0).round(4).tolist(), uv_max=uv.max(0).round(4).tolist(),
               material=mat.name if mat else None, double_sided=bool(mat and mat.doubleSided),
               has_texture=bool(mat and mat.pbrMetallicRoughness and mat.pbrMetallicRoughness.baseColorTexture),
               edge_ratio_p5_25_50_75_95=pct.round(3).tolist(),
               distortion=dict(anisotropy_p50=round(float(np.median(aniso)), 3), anisotropy_p90=round(float(np.percentile(aniso, 90)), 3),
                               neighbour_jump_p50=round(float(np.median(nbr)), 4), neighbour_jump_p90=round(float(np.percentile(nbr, 90)), 4)),
               problems=problems)
    (B / 'check.json').write_text(json.dumps(rep, indent=1))
    if verbose:
        for k, v in rep.items():
            print(f'  {k}: {v}')
        print(f'  UV overlay -> {B / "uv_check.png"}; distortion heat map (green = true to the print, red = stretched one way) -> {B / "distortion.png"}')
    return rep


def compare(gdir, verbose=True):
    from PIL import Image
    refs = sorted((gdir / 'references').glob('*.*'))
    rends = sorted(out_dir(gdir).glob('render_*.png'))
    H = 700

    def fit(p):
        im = Image.open(p).convert('RGBA')
        bb = im.getbbox() or (0, 0, im.width, im.height)
        im = im.crop(bb)
        s = H * 0.92 / im.height
        im = im.resize((max(1, int(im.width * s)), int(im.height * s)))
        c = Image.new('RGBA', (int(H * 0.95), H), (40, 44, 48, 255))
        c.alpha_composite(im, ((c.width - im.width) // 2, (H - im.height) // 2))
        return c
    order = []
    for view in ('front', 'back', 'left', 'right', 'side'):
        order += [r for r in refs if view in r.stem.lower()] + [r for r in rends if view in r.stem.lower()]
    order += [p for p in refs + rends if p not in order]
    tiles = [fit(p) for p in order]
    if not tiles:
        raise SystemExit('no references/ or out/render_*.png to compare')
    W = sum(t.width for t in tiles) + 10 * (len(tiles) - 1)
    m = Image.new('RGBA', (W, H), (20, 22, 25, 255))
    x = 0
    for t in tiles:
        m.alpha_composite(t, (x, 0)); x += t.width + 10
    path = build_dir(gdir) / 'compare.png'
    m.convert('RGB').save(path)
    if verbose:
        print('  ' + ' | '.join(p.name for p in order) + f' -> {path}')
    return path
