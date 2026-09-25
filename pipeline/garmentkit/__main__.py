"""Command line for the Python half of the pipeline.

    python pipeline/gk.py new <slug> --template T.png|T.svg|T.pdf [--refs a.png b.png] [--name "..."]
    python pipeline/gk.py rasterize <garment> <file.svg|pdf> [--px-per-mm 2]
    python pipeline/gk.py inspect  <garment>      # pieces + corner candidates -> build/inspect*.png
    python pipeline/gk.py pattern  <garment>      # garment.json -> build/pattern.json (+ report)
    python pipeline/gk.py seammap  <garment>      # checkpoint image -> build/seam_map.png
    python pipeline/gk.py body     <garment>      # mannequin -> build/body.json
    python pipeline/gk.py texture  <garment>      # sample print with bleed -> out/texture.png
    python pipeline/gk.py prep     <garment>      # pattern + seammap + body + texture
    python pipeline/gk.py check    <garment> [--glb path]   # verify exported GLB -> build/uv_check.png
    python pipeline/gk.py compare  <garment>      # references vs renders -> build/compare.png
    python pipeline/gk.py register <garment>      # out/manifest.json + garments/index.json

<garment> is a folder (garments/crew-tee) or a slug (crew-tee).
"""
from __future__ import annotations

import argparse
import sys


def main(argv=None):
    ap = argparse.ArgumentParser(prog='gk', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('new'); p.add_argument('slug'); p.add_argument('--template', required=True)
    p.add_argument('--refs', nargs='*', default=[]); p.add_argument('--name', default='')
    p.add_argument('--mm-per-px', type=float, default=None)
    p = sub.add_parser('rasterize'); p.add_argument('garment'); p.add_argument('source'); p.add_argument('--px-per-mm', type=float, default=2.0)
    for c in ('inspect', 'pattern', 'seammap', 'body', 'texture', 'prep', 'compare', 'register'):
        sub.add_parser(c).add_argument('garment')
    p = sub.add_parser('check'); p.add_argument('garment'); p.add_argument('--glb', default=None)
    a = ap.parse_args(argv)

    from .common import garment_dir
    if a.cmd == 'new':
        from .new import run
        gdir = run(a.slug, a.template, a.refs, a.name, a.mm_per_px)
        from .inspect_template import run as inspect
        inspect(gdir)
        return
    gdir = garment_dir(a.garment)
    if a.cmd == 'rasterize':
        from .rasterize import run
        run(gdir, a.source, a.px_per_mm)
    elif a.cmd == 'inspect':
        from .inspect_template import run
        run(gdir)
    elif a.cmd in ('pattern', 'prep'):
        from .pattern import build, PatternError
        try:
            build(gdir)
        except PatternError as e:
            sys.exit(f'pattern error: {e}')
        if a.cmd == 'prep':
            from . import seammap, body, texture
            seammap.run(gdir); body.build(gdir); texture.build(gdir)
    elif a.cmd == 'seammap':
        from .seammap import run
        run(gdir)
    elif a.cmd == 'body':
        from .body import build
        build(gdir)
    elif a.cmd == 'texture':
        from .texture import build
        build(gdir)
    elif a.cmd == 'check':
        from .check import run
        rep = run(gdir, a.glb)
        if rep['problems']:
            sys.exit('problems: ' + '; '.join(rep['problems']))
    elif a.cmd == 'compare':
        from .check import compare
        compare(gdir)
    elif a.cmd == 'register':
        from .register import run
        run(gdir)


if __name__ == '__main__':
    main()
