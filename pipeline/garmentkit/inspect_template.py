"""Find the pattern pieces on a template and propose corner candidates, to help write garment.json.

Writes build/inspect.json and build/inspect.png (every component with its id and bbox, numbered
corner candidates with pixel coordinates) plus build/inspect_<id>.png zoomed crops per piece.
"""
from __future__ import annotations

import json

import numpy as np

from .common import build_dir, contour_of, load_spec, load_template, segment

PALETTE = [(230, 25, 75), (60, 180, 75), (0, 130, 200), (245, 130, 48), (145, 30, 180), (70, 240, 240),
           (240, 50, 230), (210, 245, 60), (250, 190, 212), (0, 128, 128), (170, 110, 40), (128, 0, 0)]


def corner_candidates(c, eps_frac=0.004, angle_deg=28):
    """Polygon-simplification vertices whose turning angle is sharp enough to be a pattern corner."""
    import cv2
    per = cv2.arcLength(c.astype(np.float32).reshape(-1, 1, 2), True)
    ap = cv2.approxPolyDP(c.astype(np.float32).reshape(-1, 1, 2), eps_frac * per, True)[:, 0, :]
    out = []
    n = len(ap)
    for i in range(n):
        p0, p1, p2 = ap[i - 1], ap[i], ap[(i + 1) % n]
        v1, v2 = p1 - p0, p2 - p1
        cosang = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-9)
        turn = np.degrees(np.arccos(np.clip(cosang, -1, 1)))
        if turn >= angle_deg:
            out.append([float(p1[0]), float(p1[1]), round(float(turn), 1)])
    return out


def run(gdir, verbose=True):
    from PIL import Image, ImageDraw, ImageFont
    import cv2
    spec = load_spec(gdir)
    B = build_dir(gdir)
    im = load_template(gdir, spec)
    lab, stats, bgc = segment(im, spec)
    H, W = im.shape[:2]
    min_area = spec['template']['min_piece_area_px']
    comps = []
    for i in range(1, len(stats)):
        x, y, w, h, a = map(int, stats[i])
        if a < min_area:
            continue
        c = contour_of(lab, i)
        solid = a / float(w * h)
        # a point guaranteed inside the component (distance-transform maximum)
        m = (lab == i).astype(np.uint8)
        dt = cv2.distanceTransform(m, cv2.DIST_L2, 5)
        yy, xx = np.unravel_index(np.argmax(dt), dt.shape)
        ext = dict(top=c[np.argmin(c[:, 1])], bottom=c[np.argmax(c[:, 1])], left=c[np.argmin(c[:, 0])], right=c[np.argmax(c[:, 0])])
        top_row = c[np.abs(c[:, 1] - c[:, 1].min()) < 1.5]          # centre of a flat top (e.g. a sleeve-cap peak)
        ext['top_center'] = np.array([top_row[:, 0].mean(), c[:, 1].min()])
        comps.append(dict(id=i, bbox=[x, y, w, h], area=a, fill_ratio=round(solid, 3), inside=[int(xx), int(yy)],
                          extremes={k: [round(float(v[0]), 1), round(float(v[1]), 1)] for k, v in ext.items()},
                          contour_len=len(c), corners=corner_candidates(c)))
    comps.sort(key=lambda d: (d['bbox'][1] // 50, d['bbox'][0]))
    for k, cdef in enumerate(comps):
        cdef['n'] = k
    (B / 'inspect.json').write_text(json.dumps(dict(template=[W, H], background=[int(v) for v in bgc], components=comps), indent=1))

    S = 2 if max(W, H) < 3000 else 1
    base = Image.fromarray(im.astype(np.uint8)).convert('RGB').resize((W * S, H * S))
    viz = Image.blend(base, Image.new('RGB', base.size, (255, 255, 255)), 0.45)
    d = ImageDraw.Draw(viz)
    try:
        font = ImageFont.truetype('DejaVuSans.ttf', 11 * S // 2 + 5)
    except OSError:
        font = ImageFont.load_default()
    for cdef in comps:
        col = PALETTE[cdef['n'] % len(PALETTE)]
        x, y, w, h = cdef['bbox']
        d.rectangle([x * S, y * S, (x + w) * S, (y + h) * S], outline=col, width=2)
        d.text((x * S + 4, y * S + 4), f"#{cdef['n']} bbox {x},{y} {w}x{h}", fill=col, font=font)
        for j, (cx, cy, turn) in enumerate(cdef['corners']):
            d.ellipse([cx * S - 4, cy * S - 4, cx * S + 4, cy * S + 4], fill=col)
            d.text((cx * S + 5, cy * S - 14), f'{j}:({int(cx)},{int(cy)})', fill=(0, 0, 0), font=font)
    viz.save(B / 'inspect.png')
    for cdef in comps:
        x, y, w, h = cdef['bbox']
        pad = 12
        crop = base.crop((max(0, x - pad) * S, max(0, y - pad) * S, min(W, x + w + pad) * S, min(H, y + h + pad) * S))
        sc = max(1, int(900 / max(crop.size)))
        crop = crop.resize((crop.size[0] * sc, crop.size[1] * sc))
        dc = ImageDraw.Draw(crop)
        ox, oy = max(0, x - pad), max(0, y - pad)
        for j, (cx, cy, turn) in enumerate(cdef['corners']):
            px, py = (cx - ox) * S * sc, (cy - oy) * S * sc
            dc.ellipse([px - 5, py - 5, px + 5, py + 5], outline=(255, 0, 0), width=2)
            dc.text((px + 6, py - 16), f'{j}:({int(cx)},{int(cy)}) {turn:.0f}deg', fill=(255, 0, 0), font=font)
        crop.save(B / f"inspect_{cdef['n']}.png")
    if verbose:
        print(f'  template {W}x{H}, background {tuple(int(v) for v in bgc)}, {len(comps)} components')
        for cdef in comps:
            x, y, w, h = cdef['bbox']
            print(f"  #{cdef['n']:2d} bbox=({x},{y},{w},{h}) area={cdef['area']} fill={cdef['fill_ratio']} inside={cdef['inside']} "
                  f"corners={[(int(a), int(b)) for a, b, _ in cdef['corners']]} extremes={cdef['extremes']}")
        print(f'  -> {B / "inspect.png"} and inspect_<n>.png crops')
    return comps
