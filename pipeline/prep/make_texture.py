import numpy as np, cv2
from PIL import Image
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
TEMPLATE = REPO / 'assets' / 'template' / 'template.png'
BUILD = REPO / 'pipeline' / 'build'
BUILD.mkdir(parents=True, exist_ok=True)

im = np.array(Image.open(TEMPLATE).convert('RGB'))
bg = (np.abs(im.astype(int) - 141).sum(2) <= 12)
mask = (~bg).astype(np.uint8)
n, lab, st, _ = cv2.connectedComponentsWithStats(mask, 8)
keep = np.zeros_like(mask)
for i in range(1, n):
    x, y, w, h, a = st[i]
    if a >= 300 and not (1340 < x < 1440 and y < 60):  # panels (not size-tag text)
        keep[lab == i] = 1
keep = cv2.erode(keep, np.ones((5, 5), np.uint8))
# size tag: white label background with its artwork
tx0, ty0, tx1, ty1 = 1350, 10, 1433, 49
lab_img = im.copy()
tag = lab_img[ty0:ty1, tx0:tx1]
tb = (np.abs(tag.astype(int) - 141).sum(2) <= 40)
tag[tb] = 255
keep[ty0:ty1, tx0:tx1] = 1
# dilate: each background pixel takes the colour of the nearest kept pixel
dist, idx = cv2.distanceTransformWithLabels((1 - keep).astype(np.uint8), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
ys, xs = np.nonzero(keep)
lut = np.zeros((idx.max() + 1, 3), np.uint8)
lut[idx[keep == 1]] = lab_img[keep == 1]
out = lut[idx]
out[keep == 1] = lab_img[keep == 1]
Image.fromarray(out).save(REPO / 'assets' / 'template' / 'jersey_texture.png')
print(out.shape)
