"""garment.json + template -> build/pattern.json

Everything the Blender stage needs is resolved here into numbers:
  * triangulated panel meshes in template pixels (UV = template position), with seam vertex
    counts matched on both sides of every seam so seams weld vertex-for-vertex
  * sewing pairs, hem turn-up regions, band (rib/binding) loops, inside patches
  * initial placement parameters for every panel
"""
from __future__ import annotations

import math

import numpy as np

from .common import (build_dir, component_at, contour_of, cut_poly, fit_summary, load_spec,
                     load_template, path_between, plen, resample, segment, smooth_poly, write_json)


class PatternError(Exception):
    pass


def build(gdir, verbose=True):
    spec = load_spec(gdir)
    B = build_dir(gdir)
    im = load_template(gdir, spec)
    TH, TW = im.shape[:2]
    lab, stats, bgc = segment(im, spec)
    mmpp = float(spec['template']['mm_per_px'])
    m_per_px = mmpp / 1000.0
    EDGE = float(spec['mesh']['edge_mm']) / mmpp
    min_area = spec['template']['min_piece_area_px']
    pieces = spec['pieces']
    names = list(pieces.keys())
    pid = {n: i for i, n in enumerate(names)}
    log = print if verbose else (lambda *a, **k: None)

    # ------------------------------------------------ contours + corners
    contours, comp, corners = {}, {}, {}
    for n, pd in pieces.items():
        cid = component_at(lab, stats, pd['at'], min_area)
        if cid is None:
            raise PatternError(f'piece {n}: no component near {pd["at"]}')
        comp[n] = cid
        contours[n] = contour_of(lab, cid)
        corners[n] = {k: np.array(v, float) for k, v in pd['corners'].items()}
    straight = {}
    for n, pd in pieces.items():
        straight[n] = {frozenset(s) for s in pd.get('straight', [])}
    for t in spec.get('turnups', []):
        straight[t['piece']] |= {frozenset(s) for s in t.get('straight', [])}
        straight[t['piece']].add(frozenset(t['fold']))

    raw = {}

    def get_raw(p, a, b):
        if (p, a, b) in raw:
            return raw[(p, a, b)]
        if (p, b, a) in raw:
            return raw[(p, b, a)][::-1]
        C = corners[p]
        for k in (a, b):
            if k not in C:
                raise PatternError(f'piece {p}: unknown corner {k!r}')
        if frozenset((a, b)) in straight[p]:
            seg = resample(np.array([C[a], C[b]]), 200)
        else:
            avoid = [C[k] for k in C if k not in (a, b)]
            seg = smooth_poly(path_between(contours[p], C[a], C[b], avoid), spec['mesh']['smooth_iters'])
        raw[(p, a, b)] = seg
        return seg

    counts = {}

    def set_count(key, N):
        rk = (key[0], key[2], key[1])
        old = counts.get(key) or counts.get(rk)
        if old and old != N:
            raise PatternError(f'segment {key} is used by two seams with different lengths')
        counts[key] = counts[rk] = N

    def n_for(L):
        return max(3, int(round(L / EDGE)) + 1)

    seam_report = []
    for s in spec.get('seams', []):
        A, Bs = tuple(s['a']), tuple(s['b'])
        la, lb = plen(get_raw(*A)), plen(get_raw(*Bs))
        N = n_for(max(la, lb))
        set_count(A, N); set_count(Bs, N)
        seam_report.append(dict(name=s.get('name', ''), a=list(A), b=list(Bs), len_a_mm=la * mmpp, len_b_mm=lb * mmpp,
                                ratio=max(la, lb) / max(min(la, lb), 1e-9), n=N))
    for t in spec.get('turnups', []):
        for w in t.get('weld', []):
            A, Bs = (t['piece'], *w[0]), (t['piece'], *w[1])
            N = n_for(max(plen(get_raw(*A)), plen(get_raw(*Bs))))
            set_count(A, N); set_count(Bs, N)

    def loop_segments(outline):
        return [(outline[i], outline[(i + 1) % len(outline)]) for i in range(len(outline))]

    for n, pd in pieces.items():
        for a, b in loop_segments(pd['outline']):
            if (n, a, b) not in counts:
                set_count((n, a, b), n_for(plen(get_raw(n, a, b))))
    for t in spec.get('turnups', []):
        for a, b in loop_segments(t['outline']):
            if (t['piece'], a, b) not in counts:
                set_count((t['piece'], a, b), n_for(plen(get_raw(t['piece'], a, b))))

    sampled = {}

    def samp(p, a, b):
        if (p, a, b) in sampled:
            return sampled[(p, a, b)]
        if (p, b, a) in sampled:
            return sampled[(p, b, a)][::-1]
        sampled[(p, a, b)] = resample(get_raw(p, a, b), counts[(p, a, b)])
        return sampled[(p, a, b)]

    # ------------------------------------------------ triangulate panels
    import triangle
    V, F, PANEL, seg_vids, corner_vid = [], [], [], {}, {}
    area = 0.433 * EDGE * EDGE * 1.05

    def orient(tv, tf, flip):
        out = []
        for f in tf:
            a_, b_, c_ = tv[f[0]], tv[f[1]], tv[f[2]]
            cr = (b_[0] - a_[0]) * (-(c_[1] - a_[1])) - (-(b_[1] - a_[1])) * (c_[0] - a_[0])
            ccw = cr > 0
            out.append([int(f[0]), int(f[1]), int(f[2])] if ccw != flip else [int(f[0]), int(f[2]), int(f[1])])
        return out

    piece_info = []
    for n, pd in pieces.items():
        segs = loop_segments(pd['outline'])
        bpts = []
        for a, b in segs:
            bpts.extend(samp(n, a, b)[:-1].tolist())
        bpts = np.array(bpts)
        nb = len(bpts)
        T = triangle.triangulate(dict(vertices=bpts, segments=np.c_[np.arange(nb), (np.arange(nb) + 1) % nb]),
                                 f'pq30a{area:.1f}Y')
        tv, tf = T['vertices'], T['triangles']
        if not np.allclose(tv[:nb], bpts):
            raise PatternError(f'piece {n}: triangulation moved boundary points (self-intersecting outline?)')
        base = len(V)
        V.extend(tv.tolist())
        PANEL.extend([pid[n]] * len(tv))
        F.extend([[base + i for i in f] for f in orient(tv, tf, pd.get('flip', False))])
        k = 0
        for a, b in segs:
            N = counts[(n, a, b)]
            ids = [base + ((k + j) % nb) for j in range(N)]
            seg_vids[(n, a, b)] = ids
            seg_vids[(n, b, a)] = ids[::-1]
            corner_vid[(n, a)] = base + k
            k += N - 1
        x, y, w, h, _ = stats[comp[n]]
        piece_info.append(dict(name=n, label=pd.get('label', n), role=pd.get('role', ''), bbox=[int(x), int(y), int(w), int(h)],
                               verts=len(tv), faces=len(tf)))
        log(f'  piece {n:12s} {len(tv):6d} verts {len(tf):6d} tris')

    def sv(p, a, b):
        key = (p, a, b)
        if key not in seg_vids:
            raise PatternError(f'{key} is not a segment of piece {p}\'s outline')
        return seg_vids[key]

    pairs = []
    for s in spec.get('seams', []):
        ia, ib = sv(*s['a']), sv(*s['b'])
        pairs.extend(zip(ia, ib))

    # ------------------------------------------------ turn-ups (hem allowances folded inside)
    turnups = []
    for t in spec.get('turnups', []):
        p = t['piece']
        f0, f1 = t['fold']
        fold_ids = sv(p, f0, f1)
        segs = loop_segments(t['outline'])
        if segs[0] != (f0, f1):
            raise PatternError(f'turnup on {p}: outline must start with the fold {f0}->{f1}')
        loop = [samp(p, f0, f1)]
        for a, b in segs[1:]:
            loop.append(samp(p, a, b)[1:])
        loop = np.concatenate(loop)[:-1]
        nb = len(loop)
        T = triangle.triangulate(dict(vertices=loop, segments=np.c_[np.arange(nb), (np.arange(nb) + 1) % nb]),
                                 f'pq30a{0.433 * EDGE * EDGE:.1f}Y')
        tv, tf = T['vertices'], T['triangles']
        near = lambda q: int(np.argmin(np.linalg.norm(loop - q, axis=1)))
        weld = []
        for w in t.get('weld', []):
            pa, pb = samp(p, *w[0]), samp(p, *w[1])
            weld.extend((near(qa), near(qb)) for qa, qb in zip(pa, pb))
        turnups.append(dict(piece=pid[p], v=tv.tolist(), f=orient(tv, tf, pieces[p].get('flip', False)),
                            fold_ids=fold_ids, n_fold=len(fold_ids), weld=weld,
                            fold_line=[corners[p][f0].tolist(), corners[p][f1].tolist()],
                            depth_m=t.get('depth_mm', 3.5) / 1000.0))

    # ------------------------------------------------ bands (rib collars, bindings, cuffs)
    bands = []
    for bd in spec.get('bands', []):
        loop = [sv(*s) for s in bd['loop']]
        for i in range(len(loop)):
            nxt = loop[(i + 1) % len(loop)]
            if not _welded(loop[i][-1], nxt[0], pairs):
                log(f'  WARNING band {bd.get("name")}: loop segments {i} and {(i + 1) % len(loop)} do not meet at a seam')
        breaks = bd.get('u_breaks_px') or _proportional_breaks(bd['rect'], [len(s) for s in loop])
        seam_y, far_y = bd['seam_edge_y_px'], bd['far_edge_y_px']
        fold = bd.get('fold', True)
        fold_y = (seam_y + far_y) / 2 if fold else far_y
        bands.append(dict(name=bd.get('name', 'band'), loop=loop, u_breaks=breaks, seam_y=seam_y, fold_y=fold_y, far_y=far_y,
                          fold=fold, height_m=abs(seam_y - fold_y) * m_per_px, lean_deg=bd.get('lean_deg', 25),
                          thickness_m=bd.get('thickness_mm', 3.0) / 1000.0, rows=bd.get('rows', 7),
                          axis=bd.get('axis', 'auto')))

    # ------------------------------------------------ patches on the inside (tapes, labels)
    import cv2
    patches = []
    for pa in spec.get('patches', []):
        host = pa['host']
        hc = contours[host].astype(np.float32).reshape(-1, 1, 2)
        V2 = np.array(V)
        if pa['type'] == 'strip':
            rx, ry, rw, rh = pa['rect']
            path = _concat([V2[sv(*s)] for s in pa['path']])
            L = plen(path)
            ext = max(0.0, (rw - L) / 2)
            if pa.get('extend') and ext > 1:
                e0 = cut_poly(V2[sv(*pa['extend'][0])], ext)[::-1]
                e1 = cut_poly(V2[sv(*pa['extend'][1])], ext)
                path = _concat([e0, path, e1])
            path = resample(path, max(8, int(round(plen(path) / EDGE * 2))))
            tang = np.gradient(path, axis=0)
            tang /= np.linalg.norm(tang, axis=1, keepdims=True)
            nrm = np.c_[-tang[:, 1], tang[:, 0]]
            mid = len(path) // 2
            probe = path[mid] + nrm[mid] * 3
            if cv2.pointPolygonTest(hc, (float(probe[0]), float(probe[1])), False) < 0:
                nrm = -nrm
            patches.append(dict(type='strip', name=pa.get('name', 'strip'), host=pid[host], path=path.tolist(), normals=nrm.tolist(),
                                rect=pa['rect'], mirror_u=pa.get('mirror_u', False), inset_px=pa.get('inset_px', 1.0),
                                offset_m=pa.get('offset_mm', 1.5) / 1000.0, rows=pa.get('rows', 5)))
        elif pa['type'] == 'label':
            patches.append(dict(type='label', name=pa.get('name', 'label'), host=pid[host], center=pa['center_px'], rect=pa['rect'],
                                mirror_u=pa.get('mirror_u', True), offset_m=pa.get('offset_mm', 2.2) / 1000.0,
                                grid=pa.get('grid', [8, 4])))
        else:
            raise PatternError(f'unknown patch type {pa["type"]}')

    # ------------------------------------------------ placement parameters
    out = dict(template_size=[TW, TH], mm_per_px=mmpp, m_per_px=m_per_px, V=V, F=F, panel=PANEL,
               pairs=[list(map(int, p)) for p in pairs], turnups=turnups, bands=bands, patches=patches)
    placed = []
    for n, pd in pieces.items():
        pl = dict(pd.get('place') or {})
        C = corners[n]
        if pl.get('type') == 'torso':
            xr = pl['x_range']
            top = np.concatenate([samp(n, a, b) for a, b in pl.get('top_edges', [])]) if pl.get('top_edges') else None
            ys = [C[k][1] for k in C]
            res = dict(type='torso', x0=float(C[xr[0]][0]), x1=float(C[xr[1]][0]),
                       arc=[math.radians(pl['arc_deg'][0]), math.radians(pl['arc_deg'][1])],
                       hps_y=float(C[pl['hps']][1]), hem_y=float(pl.get('hem_y', max(ys))))
            if top is not None:
                o = np.argsort(top[:, 0])
                res['top_x'] = top[o, 0].tolist(); res['top_y'] = top[o, 1].tolist()
            placed.append(res)
        elif pl.get('type') == 'arm':
            h0, h1 = C[pl['hem'][0]], C[pl['hem'][1]]
            u0, u1 = C[pl['underarm'][0]], C[pl['underarm'][1]]
            pk = C[pl['peak']]
            hem_y = (h0[1] + h1[1]) / 2
            placed.append(dict(type='arm', side=1 if pl['side'] in ('left', 'L', 1) else -1,
                               front_sign=1 if pl['front_half'] == 'image_left' else -1,
                               cx=float(pk[0]), hem_y=float(hem_y), w_hem=float(np.linalg.norm(h1 - h0)) * m_per_px,
                               w_ua=float(np.linalg.norm(u1 - u0)) * m_per_px, h_ua=float(hem_y - (u0[1] + u1[1]) / 2) * m_per_px,
                               h_peak=float(hem_y - pk[1]) * m_per_px, anchor=pl['anchor']))
        elif pl.get('type') == 'flat':
            placed.append(dict(type='flat', origin=pl['origin_m'], right=pl.get('right', [1, 0, 0]), down=pl.get('down', [0, 0, -1]),
                               anchor=pl.get('anchor_px', [float(np.mean([c[0] for c in C.values()])), float(np.mean([c[1] for c in C.values()]))])))
        else:
            raise PatternError(f'piece {n}: place.type must be torso, arm or flat')
    for i, n in enumerate(names):
        piece_info[i]['place'] = placed[i]
    out['pieces'] = piece_info
    fit = fit_summary(out, spec)
    # resolve arm anchors against their torso piece
    for pc in out['pieces']:
        pl = pc['place']
        if pl['type'] != 'arm':
            continue
        tp, corner = pl['anchor']
        tpl = out['pieces'][pid[tp]]['place']
        cxm = (tpl['x0'] + tpl['x1']) / 2
        q = corners[tp][corner]
        s = abs(q[0] - cxm) * m_per_px
        pl['anchor_m'] = [pl['side'] * min(s, 0.97 * fit['wrap_a']), 0.0, -((q[1] - tpl['hps_y']) * m_per_px + 0.005)]
    out['fit'] = fit
    out['body'] = _body_params(out, spec, fit)
    out['sim'] = spec['sim']
    out['finish'] = spec['finish']
    out['export'] = spec['export']
    out['name'] = spec.get('name', gdir.name)
    out['slug'] = spec.get('slug', gdir.name)

    # ------------------------------------------------ report
    seamed = set()
    for s in spec.get('seams', []):
        seamed |= {tuple(s['a']), tuple(s['b']), (s['a'][0], s['a'][2], s['a'][1]), (s['b'][0], s['b'][2], s['b'][1])}
    for t in spec.get('turnups', []):
        seamed |= {(t['piece'], *t['fold']), (t['piece'], t['fold'][1], t['fold'][0])}
    banded = set()
    for bd in spec.get('bands', []):
        for s in bd['loop']:
            banded |= {tuple(s), (s[0], s[2], s[1])}
    open_edges = []
    for n, pd in pieces.items():
        for a, b in loop_segments(pd['outline']):
            if (n, a, b) not in seamed:
                open_edges.append(dict(piece=n, seg=[a, b], length_mm=plen(samp(n, a, b)) * mmpp,
                                       finished_by='band' if (n, a, b) in banded else 'raw edge'))
    report = dict(seams=seam_report, open_edges=open_edges, verts=len(V), tris=len(F), pairs=len(pairs), fit=fit)
    out['report'] = report
    out['manifest_pieces'] = _manifest_pieces(piece_info, spec)
    out['segments'] = {f'{k[0]}.{k[1]}.{k[2]}': v for k, v in seg_vids.items()}
    out['corners'] = {n: {k: v.tolist() for k, v in C.items()} for n, C in corners.items()}
    write_json(B / 'pattern.json', out)
    log(f'  {len(V)} verts, {len(F)} tris, {len(pairs)} sewing pairs -> {B / "pattern.json"}')
    for r in seam_report:
        flag = '  <-- check (length mismatch > 12%)' if r['ratio'] > 1.12 else ''
        log(f'  seam {r["name"]:22s} {r["len_a_mm"]:7.1f} / {r["len_b_mm"]:7.1f} mm  x{r["ratio"]:.3f}{flag}')
    for e in open_edges:
        log(f'  open edge {e["piece"]}.{e["seg"][0]}->{e["seg"][1]} ({e["length_mm"]:.0f} mm, {e["finished_by"]})')
    return out


def _welded(a, b, pairs):
    if a == b:
        return True
    adj = {}
    for x, y in pairs:
        adj.setdefault(x, set()).add(y); adj.setdefault(y, set()).add(x)
    seen, stack = {a}, [a]
    while stack:
        v = stack.pop()
        for w in adj.get(v, ()):
            if w == b:
                return True
            if w not in seen:
                seen.add(w); stack.append(w)
    return False


def _proportional_breaks(rect, sizes):
    x, _, w, _ = rect
    tot = sum(sizes)
    br, acc = [x], 0
    for s in sizes:
        acc += s
        br.append(x + w * acc / tot)
    return br


def _concat(polys):
    out = [np.asarray(polys[0], float)]
    for p in polys[1:]:
        p = np.asarray(p, float)
        out.append(p[1:] if np.linalg.norm(p[0] - out[-1][-1]) < 1e-6 else p)
    return np.concatenate(out)


def _body_params(P, spec, fit):
    """Mannequin parameters (metres) derived from the pattern unless overridden in spec.body."""
    body = spec['body']
    m = P['m_per_px']
    arms = [pc['place'] for pc in P['pieces'] if pc['place']['type'] == 'arm']
    if arms:
        sx = max(abs(a['anchor_m'][0]) for a in arms)
        drop = max(-a['anchor_m'][2] for a in arms)
        r_up = max(0.045, max(a['w_ua'] for a in arms) / (2 * math.pi) * 0.78)
        r_lo = max(0.035, max(a['w_hem'] for a in arms) / (2 * math.pi) * 0.80)
        arm_len = max(a['h_peak'] for a in arms) + 0.10
    else:
        sx, drop, r_up, r_lo, arm_len = 0.215, 0.045, 0.064, 0.052, 0.34
    sx = body.get('shoulder_half_width_mm', sx * 1000) / 1000
    params = dict(chest_a=fit['chest_a'], chest_b=fit['chest_b'], hps_to_hem=fit['hps_to_hem'],
                  below_hem=body['below_hem_mm'] / 1000, shoulder_x=sx, shoulder_drop=drop,
                  arm_angle_deg=body['arm_angle_deg'], arm_len=body.get('arm_length_mm', arm_len * 1000) / 1000,
                  arm_r_top=body.get('upper_arm_radius_mm', r_up * 1000) / 1000,
                  arm_r_end=body.get('lower_arm_radius_mm', r_lo * 1000) / 1000,
                  neck_r=body.get('neck_radius_mm', 66) / 1000, voxel=body['voxel_mm'] / 1000,
                  arms=body.get('arms', True), upper_back=body.get('upper_back_mm', 0) / 1000,
                  upper_back_z=body.get('upper_back_z_mm', -130) / 1000, upper_back_sigma=body.get('upper_back_sigma_mm', 50) / 1000)
    return params


def _manifest_pieces(piece_info, spec):
    out = [dict(name=p['name'], label=p['label'], bbox=p['bbox']) for p in piece_info]
    for bd in spec.get('bands', []):
        out.append(dict(name=bd.get('name', 'band'), label=bd.get('label', bd.get('name', 'Band')), bbox=bd['rect']))
    for pa in spec.get('patches', []):
        out.append(dict(name=pa.get('name', 'patch'), label=pa.get('label', pa.get('name', 'Patch')), bbox=pa['rect']))
    return out
