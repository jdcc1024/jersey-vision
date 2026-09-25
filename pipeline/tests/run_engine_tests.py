"""Engine regression checks (no Blender needed): build the pattern for every garment in
garments/ plus the synthetic fixtures and check the invariants the Blender stage relies on.
    python pipeline/tests/run_engine_tests.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from garmentkit.common import GARMENTS  # noqa: E402
from garmentkit.pattern import build  # noqa: E402


def check(gdir):
    P = build(gdir, verbose=False)
    n = len(P['V'])
    tw, th = P['template_size']
    assert n > 0 and len(P['F']) > 0, 'empty mesh'
    for a, b in P['pairs']:
        assert 0 <= a < n and 0 <= b < n
    for x, y in P['V']:
        assert -1 <= x <= tw and -1 <= y <= th, 'vertex outside the template'
    for s in P['report']['seams']:
        assert s['ratio'] < 1.25, f"seam {s['name']} length mismatch x{s['ratio']:.2f}"
    for bd in P['bands']:
        assert len(bd['u_breaks']) == len(bd['loop']) + 1
    kinds = {pc['place']['type'] for pc in P['pieces']}
    return f"{gdir.name}: {n} verts, {len(P['F'])} tris, {len(P['pairs'])} pairs, {len(P['bands'])} bands, placements {sorted(kinds)}"


dirs = sorted(p.parent for p in GARMENTS.glob('*/garment.json')) + sorted(p.parent for p in (HERE / 'fixtures').glob('*/garment.json'))
fails = 0
for d in dirs:
    try:
        print('ok  ', check(d))
    except Exception as e:  # noqa: BLE001
        fails += 1
        print('FAIL', d.name, '-', e)
sys.exit(1 if fails else 0)
