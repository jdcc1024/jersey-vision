"""Sample print -> out/texture.png: the template with each piece's colours bled outward past its
cut line, so texture filtering never pulls the artboard background into the seams."""
from __future__ import annotations

import numpy as np

from .common import load_spec, load_template, out_dir, segment


def build(gdir, verbose=True):
    import cv2
    from PIL import Image
    spec = load_spec(gdir)
    im = load_template(gdir, spec).astype(np.uint8)
    lab, stats, bgc = segment(im.astype(int), spec)
    keep = np.zeros(lab.shape, np.uint8)
    min_area = spec['template']['min_piece_area_px']
    for i in range(1, len(stats)):
        if stats[i][4] >= min_area:
            keep[lab == i] = 1
    keep = cv2.erode(keep, np.ones((5, 5), np.uint8))     # drop anti-aliased edge pixels
    img = im.copy()
    for rect in spec.get('texture', {}).get('label_rects', []):   # labels printed on a white ground
        x, y, w, h = rect
        tile = img[y:y + h, x:x + w]
        tb = np.abs(tile.astype(int) - bgc).sum(2) <= 40
        tile[tb] = 255
        keep[y:y + h, x:x + w] = 1
    _, idx = cv2.distanceTransformWithLabels((1 - keep).astype(np.uint8), cv2.DIST_L2, 5,
                                             labelType=cv2.DIST_LABEL_PIXEL)
    lut = np.zeros((idx.max() + 1, 3), np.uint8)
    lut[idx[keep == 1]] = img[keep == 1]
    out = lut[idx]
    out[keep == 1] = img[keep == 1]
    path = out_dir(gdir) / 'texture.png'
    Image.fromarray(out).save(path)
    if verbose:
        print(f'  sample print {out.shape[1]}x{out.shape[0]} -> {path}')
    return path
