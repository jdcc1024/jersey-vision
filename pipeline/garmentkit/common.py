"""Shared helpers: paths, spec loading, template segmentation, polyline geometry, fit maths."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
GARMENTS = REPO / 'garments'

SPEC_DEFAULTS = {
    'template': {'mm_per_px': 1.0, 'background': 'auto', 'bg_tolerance': 12, 'min_piece_area_px': 300},
    'mesh': {'edge_mm': 12.0, 'smooth_iters': 30},
    'body': {'fit_ease_mm': 13.0, 'depth_ratio': 0.66, 'arm_angle_deg': 50.0, 'below_hem_mm': 200.0,
             'voxel_mm': 6.0},
    'sim': {'frames': 90, 'gravity': 0.6, 'gravity_on_frame': 30, 'gravity_full_frame': 50,
            'grow_from': 0.84, 'grow_until_frame': 26, 'quality': 10, 'mass': 0.15,
            'tension': 15.0, 'compression': 30.0, 'shear': 5.0, 'bending': 2.0,
            'sewing_force_max': 10.0, 'self_collision': True, 'collision_distance_mm': 3.0,
            'self_collision_distance_mm': 2.0, 'body_thickness_mm': 4.0, 'friction': 5.0,
            'wrap_clearance': [1.08, 1.15], 'arm_wrap_scale': 1.06, 'curl_mm': 120.0},
    'finish': {'smooth_iters': 12},
    'export': {'object_name': 'Garment', 'material_name': 'GarmentPrint', 'roughness': 0.78},
}


def garment_dir(arg: str | Path) -> Path:
    p = Path(arg)
    if not p.exists() and (GARMENTS / str(arg)).exists():
        p = GARMENTS / str(arg)
    p = p.resolve()
    if not (p / 'garment.json').exists():
        raise SystemExit(f'No garment.json in {p}')
    return p


def deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load_spec(gdir: Path) -> dict:
    spec = json.loads((gdir / 'garment.json').read_text())
    return deep_merge(SPEC_DEFAULTS, spec)


def build_dir(gdir: Path) -> Path:
    d = gdir / 'build'
    d.mkdir(parents=True, exist_ok=True)
    return d


def out_dir(gdir: Path) -> Path:
    d = gdir / 'out'
    d.mkdir(parents=True, exist_ok=True)
    return d


# ------------------------------------------------------------------ template segmentation
def load_template(gdir: Path, spec: dict):
    from PIL import Image
    im = np.array(Image.open(gdir / spec['template']['file']).convert('RGB')).astype(int)
    return im


def background_color(im: np.ndarray, spec: dict) -> np.ndarray:
    bg = spec['template']['background']
    if bg != 'auto':
        return np.array(bg, int)
    border = np.concatenate([im[0], im[-1], im[:, 0], im[:, -1]])
    vals, counts = np.unique(border, axis=0, return_counts=True)
    return vals[np.argmax(counts)]


def segment(im: np.ndarray, spec: dict):
    """Connected components of non-background pixels. Returns (labels, stats, bg_color)."""
    import cv2
    bgc = background_color(im, spec)
    bg = np.abs(im - bgc).sum(2) <= spec['template']['bg_tolerance']
    mask = (~bg).astype(np.uint8) * 255
    n, lab, stats, cent = cv2.connectedComponentsWithStats(mask, 8)
    return lab, stats, bgc


def component_at(lab, stats, pt, min_area):
    x, y = int(round(pt[0])), int(round(pt[1]))
    i = lab[y, x]
    if i > 0 and stats[i][4] >= min_area:
        return int(i)
    # nearest large component
    best, bd = None, 1e18
    for k in range(1, len(stats)):
        if stats[k][4] < min_area:
            continue
        bx, by, bw, bh, _ = stats[k]
        dx = max(bx - x, 0, x - (bx + bw)); dy = max(by - y, 0, y - (by + bh))
        if dx * dx + dy * dy < bd:
            best, bd = k, dx * dx + dy * dy
    return int(best)


def contour_of(lab, comp_id):
    import cv2
    m = (lab == comp_id).astype(np.uint8) * 255
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    return max(cs, key=cv2.contourArea)[:, 0, :].astype(float)


# ------------------------------------------------------------------ polylines
def plen(p) -> float:
    p = np.asarray(p, float)
    return float(np.sum(np.linalg.norm(np.diff(p, axis=0), axis=1))) if len(p) > 1 else 0.0


def resample(p, n):
    p = np.asarray(p, float)
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
    t = np.linspace(0, d[-1], n)
    return np.c_[np.interp(t, d, p[:, 0]), np.interp(t, d, p[:, 1])]


def smooth_poly(p, iters=30):
    p = np.asarray(p, float).copy()
    for _ in range(iters):
        p[1:-1] = 0.5 * p[1:-1] + 0.25 * (p[:-2] + p[2:])
    return p


def cut_poly(p, length):
    """First `length` of polyline p (from its start)."""
    p = np.asarray(p, float)
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
    if length >= d[-1]:
        return p.copy()
    k = int(np.searchsorted(d, length))
    t = (length - d[k - 1]) / (d[k] - d[k - 1])
    return np.r_[p[:k], [p[k - 1] + t * (p[k] - p[k - 1])]]


def path_between(c, a, b, avoid):
    """Contour path from point a to point b (both snapped to the contour) that avoids the
    other corners. The first/last points are replaced by the exact corner coordinates."""
    c = np.asarray(c, float)
    n = len(c)
    ia = int(np.argmin(np.linalg.norm(c - a, axis=1)))
    ib = int(np.argmin(np.linalg.norm(c - b, axis=1)))
    av = [int(np.argmin(np.linalg.norm(c - q, axis=1))) for q in avoid]
    fwd = [(ia + k) % n for k in range((ib - ia) % n + 1)]
    bwd = [(ia - k) % n for k in range((ia - ib) % n + 1)]
    fs, bs = set(fwd[1:-1]), set(bwd[1:-1])
    okf = not any(v in fs for v in av)
    okb = not any(v in bs for v in av)
    idx = fwd if (okf and (not okb or len(fwd) <= len(bwd))) else bwd
    p = c[idx].copy()
    p[0] = a; p[-1] = b
    return p


# ------------------------------------------------------------------ fit maths (shared by pattern + body)
def ellipse_perimeter(a, b):
    return math.pi * (3 * (a + b) - math.sqrt((3 * a + b) * (a + 3 * b)))


def ellipse_for_perimeter(perim, depth_ratio):
    """semi-axes (a, b=a*ratio) with the given perimeter"""
    unit = ellipse_perimeter(1.0, depth_ratio)
    a = perim / unit
    return a, a * depth_ratio


def fit_summary(P: dict, spec: dict) -> dict:
    """Torso circumference and derived mannequin chest/placement ellipse, all in metres."""
    m = P['m_per_px']
    circ = 0.0
    length = 0.0
    for pc in P['pieces']:
        pl = pc.get('place') or {}
        if pl.get('type') == 'torso':
            circ += abs(pl['x1'] - pl['x0']) * m
            length = max(length, (pl['hem_y'] - pl['hps_y']) * m)
    body = spec['body']
    chest = body.get('chest_circ_mm')
    chest = chest / 1000.0 if chest else circ - body['fit_ease_mm'] / 1000.0
    a, b = ellipse_for_perimeter(chest, body['depth_ratio'])
    cl = spec['sim']['wrap_clearance']
    ga, gb = ellipse_for_perimeter(circ * 1.02, body['depth_ratio']) if circ else (a, b)
    # panels start on an ellipse outside both the mannequin and the garment's own circumference
    return dict(torso_circ=circ, chest_circ=chest, chest_a=a, chest_b=b, hps_to_hem=length or 0.75,
                wrap_a=max(a * cl[0], ga), wrap_b=max(b * cl[1], gb))


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, separators=(',', ':')))
