"""Shared helpers for the Blender half of the garment pipeline.

Scripts in this folder are run either with `blender --background --python <script> -- <garment>`
or exec'd inside a live Blender (e.g. via Blender MCP) with globals
{'__file__': <script path>, 'GARMENT': '<slug or folder>'}.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))


class Ctx:
    def __init__(self, gdir):
        self.gdir = gdir
        self.build = os.path.join(gdir, 'build')
        self.out = os.path.join(gdir, 'out')
        os.makedirs(self.build, exist_ok=True)
        os.makedirs(self.out, exist_ok=True)
        self.spec = json.load(open(os.path.join(gdir, 'garment.json')))
        pj = os.path.join(self.build, 'pattern.json')
        if not os.path.exists(pj):
            raise RuntimeError(f'{pj} missing: run `python pipeline/gk.py prep {os.path.basename(gdir)}` first')
        self.P = json.load(open(pj))


def garment_arg(g):
    """Garment from the exec globals, the command line (after `--`) or $GARMENT."""
    val = g.get('GARMENT')
    if not val and '--' in sys.argv:
        rest = sys.argv[sys.argv.index('--') + 1:]
        val = rest[0] if rest else None
    val = val or os.environ.get('GARMENT')
    if not val:
        raise RuntimeError('Say which garment: GARMENT global, `-- <garment>` on the command line, or $GARMENT')
    if os.path.isdir(val):
        return os.path.abspath(val)
    cand = os.path.join(REPO, 'garments', val)
    if os.path.isdir(cand):
        return cand
    raise RuntimeError(f'garment {val!r} not found')


def context(g):
    return Ctx(garment_arg(g))


def run_script(name, g_extra=None):
    """exec another script of this folder with the same garment."""
    path = os.path.join(HERE, name)
    g = {'__name__': '__main__', '__file__': path}
    g.update(g_extra or {})
    exec(compile(open(path).read(), path, 'exec'), g)
    return g.get('result')


def gltf_kwargs():
    """glTF exporter keyword names changed between Blender 4.x and 5.x."""
    import bpy
    props = {p.identifier for p in bpy.ops.export_scene.gltf.get_rna_type().properties}
    kw = dict(export_format='GLB', use_selection=True, export_apply=True, export_yup=True, export_normals=True,
              export_materials='EXPORT', export_animations=False)
    kw['export_texcoords' if 'export_texcoords' in props else 'export_texcoord'] = True
    if 'export_vertex_color' in props:
        kw['export_vertex_color'] = 'NONE'
    return kw, props


def eevee_engine():
    import bpy
    ids = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
    return 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in ids else 'BLENDER_EEVEE_NEXT'
