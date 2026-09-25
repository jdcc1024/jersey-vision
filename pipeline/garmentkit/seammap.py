"""Checkpoint image: build/seam_map.png

Shows every panel, its named corners, and every seam drawn in its own colour on BOTH edges that
sew together, with a numbered dot at each edge's start and an arrow for direction. Two edges of
one seam must run the same way (dot to arrow) or the seam will twist. Open edges, hem turn-ups,
bands and inside patches are marked too. This is the image to show the user before simulating.
"""
from __future__ import annotations

import json

import numpy as np

from .common import build_dir, load_spec, load_template

COLORS = [(230, 25, 75), (60, 160, 60), (0, 110, 200), (245, 130, 48), (145, 30, 180), (0, 170, 170),
          (220, 40, 200), (140, 170, 20), (170, 110, 40), (128, 0, 0), (0, 0, 128), (100, 100, 100),
          (255, 90, 90), (40, 200, 120), (90, 90, 255), (200, 160, 0)]


def run(gdir, verbose=True):
    from PIL import Image, ImageDraw, ImageFont
    spec = load_spec(gdir)
    B = build_dir(gdir)
    P = json.loads((B / 'pattern.json').read_text())
    im = load_template(gdir, spec)
    H, W = im.shape[:2]
    S = 2 if max(W, H) < 2500 else 1
    V = np.array(P['V']) * S
    segs = P['segments']
    try:
        font = ImageFont.truetype('DejaVuSans.ttf', 13)
        fontb = ImageFont.truetype('DejaVuSans-Bold.ttf', 14)
    except OSError:
        font = fontb = ImageFont.load_default()
    base = Image.fromarray(im.astype(np.uint8)).convert('RGB').resize((W * S, H * S))
    img = Image.blend(base, Image.new('RGB', base.size, (255, 255, 255)), 0.6)
    d = ImageDraw.Draw(img)

    def poly(key):
        return V[segs[key]]

    def dashed(pts, col, w=2, dash=8):
        acc = 0
        for a, b in zip(pts[:-1], pts[1:]):
            L = np.linalg.norm(b - a)
            n = max(1, int(L / dash))
            for k in range(n):
                if (acc + k) % 2 == 0:
                    p0 = a + (b - a) * k / n; p1 = a + (b - a) * (k + 1) / n
                    d.line([tuple(p0), tuple(p1)], fill=col, width=w)
            acc += n

    def arrow(pts, col):
        L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))]
        t = 0.6 * L[-1]
        k = min(max(1, int(np.searchsorted(L, t))), len(pts) - 1)
        p, q = pts[k - 1], pts[k]
        dirv = (q - p) / (np.linalg.norm(q - p) + 1e-9)
        nrm = np.array([-dirv[1], dirv[0]])
        tip = p + dirv * 1
        s = 9
        d.polygon([tuple(tip + dirv * s), tuple(tip - dirv * s * 0.4 + nrm * s * 0.7), tuple(tip - dirv * s * 0.4 - nrm * s * 0.7)], fill=col)

    # panel outlines (thin) for everything first
    for key, ids in segs.items():
        d.line([tuple(p) for p in V[ids]], fill=(40, 40, 40), width=1)

    legend = []
    for i, s in enumerate(spec.get('seams', [])):
        col = COLORS[i % len(COLORS)]
        for side in ('a', 'b'):
            pts = poly('.'.join(s[side]))
            d.line([tuple(p) for p in pts], fill=col, width=4)
            arrow(pts, col)
            p0 = pts[0]
            d.ellipse([p0[0] - 8, p0[1] - 8, p0[0] + 8, p0[1] + 8], fill=col, outline=(255, 255, 255))
            d.text((p0[0] - 4, p0[1] - 8), str(i + 1), fill=(255, 255, 255), font=fontb)
        r = P['report']['seams'][i]
        legend.append((col, f"{i + 1}. {s.get('name', '')}:  {'.'.join(s['a'])}  <->  {'.'.join(s['b'])}"
                            f"   ({r['len_a_mm']:.0f} / {r['len_b_mm']:.0f} mm, x{r['ratio']:.2f}{'  CHECK' if r['ratio'] > 1.12 else ''})"))

    for e in P['report']['open_edges']:
        key = f"{e['piece']}.{e['seg'][0]}.{e['seg'][1]}"
        col = (0, 140, 255) if e['finished_by'] == 'band' else (150, 150, 150)
        dashed(poly(key), col, 3)

    for t in spec.get('turnups', []):
        dashed(poly(f"{t['piece']}.{t['fold'][0]}.{t['fold'][1]}"), (230, 180, 0), 4, 5)
    for tu in P['turnups']:
        fv = np.array(tu['v']) * S
        for f in tu['f']:
            d.polygon([tuple(fv[k]) for k in f], outline=(230, 180, 0))
    if P['turnups']:
        legend.append(((230, 180, 0), 'yellow: hem turn-up (fold line dashed, region folds inside)'))

    for bi, (bd, bs) in enumerate(zip(spec.get('bands', []), P['bands'])):
        col = (0, 140, 255)
        x, y, w, h = [v * S for v in bd['rect']]
        d.rectangle([x, y, x + w, y + h], outline=col, width=3)
        for k, u in enumerate(bs['u_breaks']):
            d.line([(u * S, y - 6), (u * S, y + h + 6)], fill=col, width=2)
            d.text((u * S + 3, y + h + 4), f'B{bi + 1}.{k}', fill=col, font=fontb)
        d.line([(x, bs['seam_y'] * S), (x + w, bs['seam_y'] * S)], fill=(255, 0, 0), width=2)
        for k, s in enumerate(bd['loop']):
            pts = poly('.'.join(s))
            p0 = pts[0]
            d.text((p0[0] + 4, p0[1] + 4), f'B{bi + 1}.{k}', fill=col, font=fontb)
            arrow(pts, col)
        legend.append((col, f"band B{bi + 1} '{bd.get('name', '')}': blue dashed edges sew to the band; B{bi + 1}.k ticks match"
                            f" loop segment starts; red line = edge sewn to the garment{'; folded' if bs['fold'] else ''}"))

    for pa in spec.get('patches', []):
        col = (200, 0, 160)
        x, y, w, h = [v * S for v in pa['rect']]
        d.rectangle([x, y, x + w, y + h], outline=col, width=3)
        d.text((x, y - 16), f"{pa.get('name', '')} -> inside {pa['host']}", fill=col, font=fontb)
    for pp in P['patches']:
        col = (200, 0, 160)
        if pp['type'] == 'strip':
            path = np.array(pp['path']) * S
            d.line([tuple(p) for p in path], fill=col, width=3)
        else:
            cx, cy = pp['center']; _, _, w, h = pp['rect']
            d.rectangle([(cx - w / 2) * S, (cy - h / 2) * S, (cx + w / 2) * S, (cy + h / 2) * S], outline=col, width=3)
    if P['patches']:
        legend.append(((200, 0, 160), 'magenta: inside patches (template rect -> where it sits on the host panel)'))
    legend.append(((150, 150, 150), 'grey dashed: raw open edge (hem / opening, not sewn)'))

    for n, C in P['corners'].items():
        for k, (cx, cy) in C.items():
            d.ellipse([cx * S - 4, cy * S - 4, cx * S + 4, cy * S + 4], fill=(0, 0, 0))
            d.text((cx * S + 6, cy * S - 6), k, fill=(0, 0, 0), font=font)
    for pc in P['pieces']:
        x, y, w, h = pc['bbox']
        pl = pc['place']
        tag = pl['type'] + (f" arc {np.degrees(pl['arc'][0]):.0f}..{np.degrees(pl['arc'][1]):.0f} deg" if pl['type'] == 'torso' else '')
        if pl['type'] == 'arm':
            tag += f" {'L' if pl['side'] > 0 else 'R'}, front half = {'image-left' if pl['front_sign'] > 0 else 'image-right'}"
        d.text((x * S + 6, (y + h) * S - 20), f"{pc['label']} [{tag}]", fill=(20, 20, 20), font=fontb)

    lh = 22
    out = Image.new('RGB', (img.width, img.height + lh * (len(legend) + 2)), (255, 255, 255))
    out.paste(img, (0, 0))
    dl = ImageDraw.Draw(out)
    yy = img.height + 10
    dl.text((10, yy), f"{P['name']}  -  {P['report']['verts']} verts, {P['report']['tris']} tris, {P['report']['pairs']} sewing pairs."
                      f"  Numbered dots = seam start; both edges of a seam must run dot -> arrow in the same direction.",
            fill=(0, 0, 0), font=fontb)
    for col, txt in legend:
        yy += lh
        dl.rectangle([10, yy + 4, 34, yy + 16], fill=col)
        dl.text((42, yy + 2), txt, fill=(0, 0, 0), font=font)
    path = B / 'seam_map.png'
    out.save(path)
    if verbose:
        print(f'  seam map -> {path}')
    return path
