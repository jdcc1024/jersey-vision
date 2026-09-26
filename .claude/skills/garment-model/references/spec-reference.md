# garment.json reference

All coordinates are **template pixels** (x right, y down, origin top-left of the template image).
Lengths ending in `_mm` are millimetres; `mm_per_px` converts between the two. Defaults live in
`pipeline/garmentkit/common.py` (`SPEC_DEFAULTS`); anything omitted uses them.

## Top level
| key | meaning |
|---|---|
| `name`, `slug`, `type` | display name, folder name, free-text garment type (shown in the viewer picker) |
| `template` | `{file, mm_per_px, background: "auto" or [r,g,b], bg_tolerance, min_piece_area_px}` |
| `mesh` | `{edge_mm: 12, smooth_iters: 30}`: target triangle edge length (12 mm gives about 25k tris for a tee), and how much the pixel-stepped contours are smoothed |
| `pieces` | the **simulated panels** (fabric that wraps the body) keyed by name |
| `seams` | which panel edges sew together |
| `turnups` | hem allowances folded inside |
| `bands` | strips sewn along a closed edge loop: collars/ribs, bindings, cuffs, waistbands |
| `patches` | printed pieces that sit on the inside of a panel: neck tape, size tag |
| `body` | mannequin fit and pose |
| `sim` | cloth simulation settings |
| `finish` | `{smooth_iters: 12, smooth_mode: "normal"}`: Taubin smoothing after welding. `normal` moves vertices only along the surface normal (and across boundary edges) so triangles keep their shape relative to the UVs; `full` also slides vertices along the surface, which makes printed text look wavy, so don't use it for print proofs |
| `texture` | `{label_rects: [[x,y,w,h], ...]}`: rects whose background becomes white in the sample print |
| `export` | `{object_name, material_name, roughness}` |
| `viewer` | `{notes: {piece: "text"}, labels: {piece: "Label"}, sample_graphic: {name, rect:[x,y,w,h], knockout:"dark", place:[cx, cy, width_px]}}` |

## pieces.<name>
```json
"sleeve_L": {
  "label": "Sleeve L",
  "at": [1375, 362],
  "corners": {"uaA": [1132, 356], "peak": [1390.5, 229], ...},
  "outline": ["peak", "uaB", "foldB", "foldA", "uaA"],
  "straight": [["foldB", "foldA"]],
  "flip": false,
  "place": { ... }
}
```
- `at`: any point inside the piece (use `inspect.json` → `inside`); selects the connected component.
- `corners`: named points on (or within ~2 px of) the outline. Corners divide the outline into
  **segments**; a segment is referenced as `[piece, fromCorner, toCorner]` and may be used in either
  direction. Add a corner wherever a seam starts/ends, even mid-curve (sleeve-cap peak, notches).
  Corners must be unique points; the path between two corners follows the contour the short way
  that doesn't pass another corner.
- `outline`: the corners in order around the piece (either winding). Every consecutive pair is a
  segment; the last joins back to the first.
- `straight`: segments to treat as exact straight lines (hems, fold lines, straight shoulder seams).
- `flip`: `true` if the template shows this piece from the inside (its face normals are reversed).

### place: how the flat piece is wrapped before simulation
The sim fixes the details (sewing springs pull edges together; the mannequin pushes fabric
outward), so placement only has to be roughly right and **outside the body**.

**`torso`**: wraps the piece around an ellipse around the body.
```json
{"type": "torso", "arc_deg": [-90, 90], "x_range": ["uaA", "uaB"], "hps": "neckA",
 "top_edges": [["shA", "neckA"], ["neckB", "shB"]], "hem_y": 771}
```
- angle convention: `0` = front centre, `+90` = wearer's left side (+X), `180` = back centre,
  `270` (= −90) = wearer's right side.
- `arc_deg: [a0, a1]` = angle at the piece's `x_range[0]` corner's x and at `x_range[1]`'s x;
  linear in arc length in between. Front drawn from outside: `[-90, 90]`. Back drawn from outside
  (wearer's left is image-left): `[90, 270]`. Split pieces: e.g. baseball left front `[0, 90]`,
  right front `[-90, 0]`; a side panel `[60, 120]`.
- `hps`: corner at the high point shoulder (neck point); defines z = 0.
- `top_edges`: shoulder (or raglan) seams. Near them the panel curls over the shoulder so front
  and back start close together. Omit for pieces that don't reach the shoulder.
- `hem_y` (optional): hem level, default = lowest corner.

**`arm`**: rolls the piece into a cone around an arm.
```json
{"type": "arm", "side": "left", "front_half": "image_left", "peak": "peak",
 "underarm": ["uaA", "uaB"], "hem": ["foldA", "foldB"], "anchor": ["front", "shB"]}
```
- The sleeve must be drawn **cap up, hem down** with its centre line vertical.
- `side`: `left` = wearer's left (+X).
- `front_half`: which half of the drawing faces the wearer's front: `image_left` or
  `image_right`. For a symmetric set-in sleeve drawn from outside: left sleeve → `image_left`,
  right sleeve → `image_right`. Verify with the mockups.
- `peak`: the corner that meets the `anchor` (sleeve-cap top for set-in; the neck edge for raglan).
- `underarm`: the two ends of the cap/armhole seam at the underarm; `hem`: the two ends of the hem
  (or fold line). Widths and lengths are measured from these.
- `anchor`: `[torsoPiece, corner]` where the peak attaches: shoulder point for set-in sleeves,
  neck point for raglan sleeves.

**`flat`**: a plane anywhere (gussets, yokes, pockets, odd pieces).
```json
{"type": "flat", "origin_m": [0.19, 0, -0.30], "right": [0, 1, 0], "down": [0, 0, -1], "anchor_px": [900, 400]}
```
`anchor_px` (default: centroid of the corners) is placed at `origin_m` (Blender metres: front = −Y,
+X = wearer's left, z = 0 at neck point); template +x goes along `right`, +y along `down`.

## seams
```json
{"name": "side seam L", "a": ["front", "uaB", "hemB"], "b": ["back", "uaA", "hemA"]}
```
Both segments are resampled to the same number of points and **point k of a sews to point k of b**.
Write both segments running the **same physical direction** (both underarm → hem). A reversed
pair twists the seam (visible in the seam map: numbered dots should both be at the same end).
A corner can appear in several seams (underarm point = side seam + armhole + sleeve seam); the
engine welds them into one vertex. Length ratio > 1.12 is flagged; set-in caps are usually
3–6% longer than the armhole (ease).

## turnups
```json
{"piece": "sleeve_L", "fold": ["foldA", "foldB"], "outline": ["foldA", "foldB", "hemB", "hemA"],
 "straight": [["hemB", "hemA"]], "weld": [[["foldA", "hemA"], ["foldB", "hemB"]]], "depth_mm": 3.5}
```
The region beyond a fold line (hem allowance) is reflected across the fold and tucked inside by
`depth_mm`. `fold` must be a segment of the piece's `outline`; `outline` lists the region, starting
with the fold. `weld` pairs the region's side edges that sew together (the allowance's continuation
of the underarm seam). The piece's sim `outline` must stop at the fold.

## bands
```json
{"name": "neck", "label": "Neck rib", "rect": [1144, 133, 494, 61],
 "loop": [["front", "neckB", "neckA"], ["back", "neckB", "neckA"]],
 "u_breaks_px": [1144, 1392, 1637], "seam_edge_y_px": 193, "far_edge_y_px": 133,
 "fold": true, "lean_deg": 28, "thickness_mm": 3, "axis": "auto", "rows": 7}
```
- `rect`: the strip's box on the template (drawn horizontally).
- `loop`: garment edge segments in order around the opening; each segment's end must be welded
  to the next one's start (they meet at seams) and the loop closes. The strip's x runs along the loop.
- `u_breaks_px`: template x of the strip at each loop joint (len = segments + 1), e.g. the
  LEFT / RIGHT / LEFT notches. Omit for proportional.
- `seam_edge_y_px`: the strip edge sewn to the garment; `far_edge_y_px`: the other edge.
- `fold: true`: strip folds in half lengthwise: the seam-edge half is the **outside**, the fold is
  the top, the far half lies inside. `false`: single layer from seam edge to far edge.
- `lean_deg`: direction the band extends from the edge, tilted from the opening's axis toward its
  centre. `~20–30` = standing collar/rib; `~85–90` = binding lying in the surface (armholes of tanks,
  V-neck binding); `0` = straight out (cuffs, waistbands extend along the axis).
- `axis`: `auto` (normal of the loop's best-fit plane, pointing away from the garment) or `up`
  (world up; crew collars that should stand vertically).

## patches
Strip (tape following an edge, on the inside):
```json
{"name": "inner_neck", "type": "strip", "host": "back", "path": [["back", "neckA", "neckB"]],
 "extend": [["back", "neckA", "shA"], ["back", "neckB", "shB"]], "rect": [1207, 67, 368, 39],
 "mirror_u": true, "offset_mm": 1.5, "inset_px": 1, "rows": 5}
```
`path` segments are concatenated; if the rect is longer than the path it is extended equally
along the `extend` segments (start-side first). The strip's top edge (rect y) lies along the path,
the rest extends into the host panel. `mirror_u: true` when the print should read correctly from
the inside.

Label (rectangle on the inside, e.g. printed size tag):
```json
{"name": "size_tag", "type": "label", "host": "back", "rect": [1350, 10, 83, 39],
 "center_px": [847, 112.5], "mirror_u": true, "offset_mm": 2.2, "grid": [8, 4]}
```
`center_px` is in the host panel's template coordinates; rect top faces toward decreasing host y
(up the garment).

## body (mannequin), all derived from the pattern unless set
| key | default | meaning |
|---|---|---|
| `fit_ease_mm` | 13 | torso circumference minus chest circumference (bigger = looser drape) |
| `chest_circ_mm` | derived | override the mannequin chest directly (baggy hockey jerseys) |
| `depth_ratio` | 0.66 | chest depth / width |
| `arm_angle_deg` | 50 | arms below horizontal (tee mockups ≈ 50; tanks 60–65; hockey 35–45) |
| `arm_length_mm`, `upper_arm_radius_mm`, `lower_arm_radius_mm` | from sleeves | arm capsule |
| `shoulder_half_width_mm` | from sleeve anchors (else 215) | |
| `neck_radius_mm` | 66 | |
| `upper_back_mm` (+ `upper_back_z_mm` -130, `upper_back_sigma_mm` 50) | 18 | extra mannequin depth over the shoulder blades, back side only. Without it the back panel's extra length above the shoulder blades buckles into a ridge/bump across the upper back |
| `arms` | true | false removes the arms (vests without armholes, etc.) |
| `below_hem_mm`, `voxel_mm` | 200, 6 | torso extends below the hem; SDF resolution |

## sim (Blender cloth)
`frames 90, gravity 1.0 (0 until frame 30, full by 50), bending 2.0, tension 15, compression 30,
shear 5, mass 0.15, sewing_force_max 10, quality 10, self_collision true, collision_distance_mm 3,
body_thickness_mm 4, friction 5, grow_from 0.84 (mannequin scales up from 84% by frame 26),
wrap_clearance [1.08, 1.15], arm_wrap_scale 1.06, curl_mm 120`.
Stiffer fabric / fewer wrinkles: raise `bending`. Less sag: lower `gravity`. Seams not closing:
raise `frames` or `sewing_force_max`.
