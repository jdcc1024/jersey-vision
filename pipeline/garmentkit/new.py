"""Scaffold garments/<slug>/ from a template file and reference mockups."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from .common import GARMENTS

SKELETON = {
    "name": "",
    "slug": "",
    "type": "",
    "template": {"file": "template.png", "mm_per_px": 1.0, "background": "auto", "bg_tolerance": 12},
    "mesh": {"edge_mm": 12},
    "pieces": {},
    "seams": [],
    "turnups": [],
    "bands": [],
    "patches": [],
    "body": {"arm_angle_deg": 50},
    "sim": {},
    "finish": {"smooth_iters": 12},
    "export": {"object_name": "Garment", "material_name": "GarmentPrint"},
    "viewer": {},
}


def run(slug: str, template: str, refs=(), name: str = '', mm_per_px: float | None = None, verbose=True):
    gdir = GARMENTS / slug
    if (gdir / 'garment.json').exists():
        raise SystemExit(f'{gdir} already exists; edit its garment.json instead')
    (gdir / 'references').mkdir(parents=True, exist_ok=True)
    spec = json.loads(json.dumps(SKELETON))
    spec['name'] = name or slug.replace('-', ' ').title()
    spec['slug'] = slug
    if mm_per_px:
        spec['template']['mm_per_px'] = mm_per_px
    (gdir / 'garment.json').write_text(json.dumps(spec, indent=2))
    src = Path(template)
    if src.suffix.lower() in ('.svg', '.pdf'):
        shutil.copy(src, gdir / ('template_source' + src.suffix.lower()))
        from .rasterize import run as rasterize
        rasterize(gdir, src, verbose=verbose)
    else:
        from PIL import Image
        Image.open(src).convert('RGB').save(gdir / 'template.png')
    for r in refs:
        r = Path(r)
        shutil.copy(r, gdir / 'references' / r.name)
    if verbose:
        print(f'  created {gdir}')
    return gdir
