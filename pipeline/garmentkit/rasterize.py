"""Vector template (SVG / PDF) -> template.png at a known scale.

The raster becomes the UV space, so its artboard must be the full template artboard. Pick a
resolution high enough for accurate contours (default 2 px/mm); UVs are normalised so any export of
the same artboard at the same aspect ratio maps identically.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

MM_PER_PT = 25.4 / 72.0


def _svg_mm_size(path: Path):
    """(width_mm, height_mm) if the SVG root declares physical units, else None."""
    head = path.read_text(errors='ignore')[:4000]
    m = re.search(r'<svg[^>]*>', head, re.S)
    if not m:
        return None
    tag = m.group(0)
    units = {'mm': 1.0, 'cm': 10.0, 'in': 25.4, 'pt': MM_PER_PT, 'px': 25.4 / 96}
    out = []
    for attr in ('width', 'height'):
        a = re.search(rf'\s{attr}="([\d.]+)\s*(mm|cm|in|pt|px)?"', tag)
        if not a:
            return None
        out.append(float(a.group(1)) * units.get(a.group(2) or 'px', 25.4 / 96))
    return tuple(out)


def run(gdir: Path, src: Path, px_per_mm: float = 2.0, background=(141, 141, 141), verbose=True):
    import pymupdf
    src = Path(src)
    doc = pymupdf.open(str(src))
    page = doc[0]
    w_pt, h_pt = page.rect.width, page.rect.height
    size_mm = (w_pt * MM_PER_PT, h_pt * MM_PER_PT)
    if src.suffix.lower() == '.svg':
        svg_mm = _svg_mm_size(src)
        if svg_mm:
            size_mm = svg_mm
    zoom_x = px_per_mm * size_mm[0] / w_pt
    zoom_y = px_per_mm * size_mm[1] / h_pt
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom_x, zoom_y), alpha=True)
    from PIL import Image
    im = Image.frombytes('RGBA', (pix.width, pix.height), pix.samples)
    bg = Image.new('RGBA', im.size, tuple(background) + (255,))
    bg.alpha_composite(im)
    out = gdir / 'template.png'
    bg.convert('RGB').save(out)
    spec_path = gdir / 'garment.json'
    spec = json.loads(spec_path.read_text())
    spec.setdefault('template', {})
    spec['template'].update(file='template.png', mm_per_px=round(1.0 / px_per_mm, 6), source=src.name,
                            background=list(background))
    spec_path.write_text(json.dumps(spec, indent=2))
    if verbose:
        print(f'  {src.name}: artboard {size_mm[0]:.1f} x {size_mm[1]:.1f} mm -> {pix.width}x{pix.height} px '
              f'({px_per_mm} px/mm) -> {out}')
        print('  CHECK the scale against a known garment measurement (e.g. body width) before continuing.')
    return out
