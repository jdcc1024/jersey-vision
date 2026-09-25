"""Write out/manifest.json for a garment and list it in garments/index.json (read by the web viewer)."""
from __future__ import annotations

import json
import os

from .common import GARMENTS, build_dir, load_spec, out_dir


def run(gdir, verbose=True):
    spec = load_spec(gdir)
    P = json.loads((build_dir(gdir) / 'pattern.json').read_text())
    out = out_dir(gdir)
    tw, th = P['template_size']
    viewer = spec.get('viewer', {})
    manifest = {
        'name': spec.get('name', gdir.name),
        'slug': spec.get('slug', gdir.name),
        'type': spec.get('type', ''),
        'template': {'file': '../' + spec['template']['file'], 'width_px': tw, 'height_px': th,
                     'mm_per_px': spec['template']['mm_per_px']},
        'model': 'model.glb',
        'model_untextured': 'model_untextured.glb',
        'texture': 'texture.png',
        'object_name': spec['export']['object_name'],
        'axes': 'glTF Y-up, metres, front faces +Z, wearer\'s left +X, centred on origin',
        'uv': 'u = (px + 0.5) / width_px, v = (py + 0.5) / height_px (glTF, top-down); textures use flipY = false',
        'pieces': [dict(p, label=viewer.get('labels', {}).get(p['name'], p['label'])) for p in P['manifest_pieces']],
        'piece_notes': viewer.get('notes', {}),
        'sample_graphic': viewer.get('sample_graphic'),
    }
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=1))
    idx_path = GARMENTS / 'index.json'
    idx = json.loads(idx_path.read_text()) if idx_path.exists() else {'default': manifest['slug'], 'garments': []}
    idx['garments'] = [g for g in idx['garments'] if g['slug'] != manifest['slug']]
    idx['garments'].append({'slug': manifest['slug'], 'name': manifest['name'], 'type': manifest['type'],
                            'path': os.path.relpath(out / 'manifest.json', GARMENTS).replace(os.sep, '/')})
    idx['garments'].sort(key=lambda g: g['name'])
    idx_path.write_text(json.dumps(idx, indent=1))
    if verbose:
        print(f'  manifest -> {out / "manifest.json"}; registered in {idx_path}')
    return manifest
