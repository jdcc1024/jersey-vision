"""Generate the synthetic sleeveless (tank top) test template used to exercise the engine on a
second garment shape: no sleeves, deep armholes finished with bindings, a scoop neck rib.
Not a production pattern. 1 px = 1 mm.
    python pipeline/tests/make_tank_fixture.py
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / 'fixtures' / 'tank-top'
W, H = 2050, 800
BG = (141, 141, 141)


def catmull(pts, n=24):
    pts = np.asarray(pts, float)
    P = np.r_[[pts[0]], pts, [pts[-1]]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for t in np.linspace(0, 1, n, endpoint=False):
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(pts[-1])
    return np.array(out)


def torso(x0, neck_depth):
    cx = x0 + 255
    neck = catmull([(cx - 85, 20), (cx - 70, 20 + neck_depth * 0.55), (cx, 20 + neck_depth), (cx + 70, 20 + neck_depth * 0.55), (cx + 85, 20)])
    arm_r = catmull([(cx + 155, 40), (cx + 142, 150), (cx + 150, 260), (cx + 190, 340), (cx + 255, 380)])
    arm_l = arm_r.copy(); arm_l[:, 0] = 2 * cx - arm_l[:, 0]
    poly = np.r_[neck, arm_r, [(cx + 255, 760), (cx - 255, 760)], arm_l[::-1]]
    corners = dict(neckA=[cx - 85, 20], neckB=[cx + 85, 20], shA=[cx - 155, 40], shB=[cx + 155, 40],
                   uaA=[cx - 255, 380], uaB=[cx + 255, 380], hemA=[cx - 255, 760], hemB=[cx + 255, 760])
    return poly, corners, cx


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    im = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(im)
    try:
        big = ImageFont.truetype('DejaVuSans-Bold.ttf', 260); mid = ImageFont.truetype('DejaVuSans-Bold.ttf', 70)
        small = ImageFont.truetype('DejaVuSans-Bold.ttf', 26)
    except OSError:
        big = mid = small = ImageFont.load_default()
    fpoly, fc, fcx = torso(20, 120)
    bpoly, bc, bcx = torso(600, 30)
    for poly in (fpoly, bpoly):
        d.polygon([tuple(p) for p in poly], fill=(22, 34, 78))
    mask = Image.new('L', (W, H), 0); dm = ImageDraw.Draw(mask)
    for poly in (fpoly, bpoly):
        dm.polygon([tuple(p) for p in poly], fill=255)
    art = Image.new('RGB', (W, H), (22, 34, 78)); da = ImageDraw.Draw(art)
    da.rectangle([0, 430, W, 470], fill=(250, 190, 40))                 # chest stripe runs across both panels
    da.text((fcx, 300), 'TANK', font=mid, fill=(255, 255, 255), anchor='mm')
    da.text((bcx, 330), '10', font=big, fill=(255, 255, 255), anchor='mm')
    da.text((fcx + 150, 700), 'L', font=small, fill=(250, 190, 40), anchor='mm')   # wearer's left hem
    da.text((bcx - 150, 700), 'L', font=small, fill=(250, 190, 40), anchor='mm')
    im.paste(art, (0, 0), mask)
    # bands: neck rib and two armhole bindings (folded strips)
    d.rectangle([1200, 20, 1720, 70], fill=(250, 190, 40))
    d.rectangle([1200, 110, 1980, 140], fill=(250, 190, 40))
    d.rectangle([1200, 170, 1980, 200], fill=(250, 190, 40))
    im.save(OUT / 'template.png')
    return fc, bc


if __name__ == '__main__':
    fc, bc = main()
    print('front corners', fc)
    print('back corners', bc)
