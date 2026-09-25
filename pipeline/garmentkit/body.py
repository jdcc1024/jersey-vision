"""Invisible-mannequin collider for the cloth sim (SDF + marching cubes) -> build/body.json

Metres, neck point (HPS) at z = 0, front = -Y, wearer's left = +X (Blender axes).
All dimensions come from build/pattern.json['body'] (derived from the pattern, overridable in
garment.json -> body).
"""
from __future__ import annotations

import json

import numpy as np

from .common import build_dir, write_json

# torso cross-section profile of the reference mannequin, relative to the chest ellipse
_Z_REF = np.array([-0.96, -0.80, -0.66, -0.52, -0.40, -0.28, -0.18, -0.10, -0.06])
_A_REL = np.array([0.966, 0.966, 0.937, 0.917, 0.956, 1.000, 0.966, 0.839, 0.634])
_B_REL = np.array([0.963, 0.963, 0.933, 0.919, 0.948, 1.000, 0.963, 0.830, 0.607])
_Y_OFF = np.array([0.0, 0.0, 0.0, 0.0, -0.004, -0.008, -0.006, 0.0, 0.004])
_L_REF = 0.756


def _smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)


def _capsule(P, a, b, ra, rb):
    a = np.asarray(a, float); b = np.asarray(b, float); ba = b - a
    pa = np.stack([P[0] - a[0], P[1] - a[1], P[2] - a[2]], -1)
    h = np.clip((pa @ ba) / (ba @ ba), 0, 1)
    d = np.linalg.norm(pa - h[..., None] * ba, axis=-1)
    return d - (ra + (rb - ra) * h)


def build(gdir, verbose=True):
    from skimage import measure
    B = build_dir(gdir)
    P = json.loads((B / 'pattern.json').read_text())
    bp = P['body']
    L = bp['hps_to_hem']
    bottom = -(L + bp['below_hem'])
    zk = np.where(_Z_REF <= -0.28, _Z_REF * (L / _L_REF), _Z_REF)
    zk[0] = bottom
    ak = _A_REL * bp['chest_a']
    bk = _B_REL * bp['chest_b']
    sx, drop = bp['shoulder_x'], bp['shoulder_drop']
    ang = np.radians(bp['arm_angle_deg'])
    reach = sx + bp['arm_len'] * np.cos(ang) + bp['arm_r_top'] + 0.02 if bp.get('arms', True) else sx + 0.1
    vox = bp['voxel']
    xs = np.arange(-max(reach, bp['chest_a'] + 0.05), max(reach, bp['chest_a'] + 0.05), vox)
    ys = np.arange(-bp['chest_b'] - 0.07, bp['chest_b'] + 0.07, vox)
    zs = np.arange(bottom, 0.18, vox)
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing='ij')
    Pg = (X, Y, Z)
    A = np.interp(Z, zk, ak); Bv = np.interp(Z, zk, bk); YC = np.interp(Z, zk, _Y_OFF)
    r = np.sqrt((X / A) ** 2 + ((Y - YC) / Bv) ** 2)
    torso = (r - 1) * np.minimum(A, Bv)
    torso = np.maximum(torso, Z - (-0.06))
    torso = np.maximum(torso, bottom - Z)
    neck = _capsule(Pg, (0, 0.012, -0.10), (0, 0.02, 0.16), bp['neck_r'], bp['neck_r'] - 0.008)
    shoulders = _capsule(Pg, (-(sx - 0.05), 0.008, -(drop + 0.06)), (sx - 0.05, 0.008, -(drop + 0.06)), 0.056, 0.056)
    body = _smin(torso, shoulders, 0.05)
    body = _smin(body, neck, 0.035)
    if bp.get('arms', True):
        for sgn in (1, -1):
            j = np.array([sgn * (sx - 0.035), 0.006, -(drop + 0.067)])
            d = np.array([sgn * np.cos(ang), 0, -np.sin(ang)])
            body = _smin(body, _capsule(Pg, j, j + d * bp['arm_len'], bp['arm_r_top'], bp['arm_r_end']), 0.03)
    verts, faces, _, _ = measure.marching_cubes(body, 0.0, spacing=(vox, vox, vox))
    verts += np.array([xs[0], ys[0], zs[0]])
    write_json(B / 'body.json', dict(v=np.round(verts, 5).tolist(), f=faces.tolist()))
    if verbose:
        print(f'  mannequin {len(verts)} verts, chest {bp["chest_a"] * 2 * 100:.1f} x {bp["chest_b"] * 2 * 100:.1f} cm, '
              f'arms {"on" if bp.get("arms", True) else "off"} at {bp["arm_angle_deg"]:.0f} deg -> {B / "body.json"}')
    return verts, faces
