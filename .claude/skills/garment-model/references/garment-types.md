# Speccing garment families

Start from the closest example, then change what differs. "✓ supported" means today's engine
handles it with spec changes only; "⚠ extension" means the engine needs a small addition first
(propose it and ask before building).

## Set-in short sleeve tee / jersey ✓ (`garments/crew-tee`)
Front + back torso (`torso` arcs `[-90,90]` and `[90,270]`), two sleeves (`arm`, anchored at the
front shoulder point corner), side/shoulder/armhole/underarm seams, sleeve hem `turnups`, neck
rib `band` (fold, `lean_deg` ~28, `axis: "up"`), inner neck tape + size tag `patches`.
Arm angle ~50 degrees from typical ghost-mannequin mockups.

## Long sleeve ✓
Same as the tee; the sleeve is just longer and narrower at the wrist. The arm capsule length is
derived from the sleeve (`h_peak + 100 mm`); check `body.arm_length_mm` ends past the cuff.
Arms usually hang lower in long-sleeve mockups: `arm_angle_deg` 60–70. Cuffs: either a
`turnup` (hemmed) or a `band` (rib cuff: loop = the sleeve's wrist edge, which is one segment
from `foldA`→`foldB`, closed by the underarm seam; `fold: true`, `lean_deg: 0`, `axis: "auto"`).
Consider `sim.frames` 110 for the longer sleeve to settle.

## Raglan sleeve ✓ (placement differs)
Front and back have diagonal raglan seams from underarm to neck instead of shoulder seams; the
sleeve's top edge runs to the neckline, and there is often a sleeve dart or a two-piece sleeve.
- Torso `top_edges` = the raglan edges (the curl then follows them).
- Sleeve `place.peak` = the corner at the middle of the sleeve's neck edge (or the dart point),
  `anchor` = `[front, neckB]`-style **neck** corner, not a shoulder point.
- Seams: front raglan ↔ sleeve front raglan, back raglan ↔ sleeve back raglan, underarm, side.
  With a shoulder dart or two-piece sleeve add that seam (dart edges sew to each other).
- The neck band loop runs front neck → sleeve neck → back neck → other sleeve neck.
- Expect the sleeve to need more settling: `sim.frames` 110, maybe `arm_wrap_scale` 1.1.

## Tank / sleeveless / singlet ✓ (`pipeline/tests/fixtures/tank-top`)
Front + back only; armholes and neck finished with bindings (`bands` with `lean_deg` ~85, `fold:
true`) or rib. Armhole band loop: `[front shB→uaB]` + `[back uaA→shA]` (wearer's left). Keep the
mannequin arms (they hold the shape of the armhole) but lower them: `arm_angle_deg` 60–65.
Racerbacks: the back's `top_edges` are the narrow straps; same approach.

## V-neck ✓
Neckline has a corner at the V point: add it as a corner so the band loop has segments on each
side. A binding (`lean_deg` ~80) follows the V naturally. A rib V with a mitred overlap is a
single band whose `u_breaks_px` put the mitre at the V; the overlap itself is not modelled.

## Hockey jersey ✓ with care
Very wide body and sleeves, often shoulder yokes, underarm gussets, and sometimes a lace-up
collar or V-neck insert.
- Baggy fit: set `body.chest_circ_mm` to a real chest (~1000–1050) instead of deriving it from
  the huge garment circumference, keep `sim.gravity` at 1.0 for drape, `arm_angle_deg` 35–45
  (hockey mockups hold the arms out).
- Shoulder yokes: separate pieces sewn between front/back and sleeves; place them with `torso`
  (they sit over the shoulders: arcs covering e.g. `[40, 140]` on the wearer's left side, with
  `top_edges`), or `flat` above the shoulder, and let the sewing pull them in.
- Underarm gussets (diamond pieces): `flat` near the armpit (`origin_m` ≈ `[±0.22, 0, -0.30]`,
  `right` = `[0, 1, 0]`); sew all four edges.
- Sleeve cuff stripes etc. are just print, no geometry.
- ⚠ extension: lace-up collars (holes, laces) are not modelled; treat as a band/insert.

## Baseball jersey (button front) ⚠ partly
Split front (left and right pieces), placket, collar band or piping; often raglan or set-in sleeves.
- ✓ Two front pieces as `torso` with arcs `[-90, 0]`-ish and `[0, 90]`-ish; sew the placket edges
  to each other as a seam (closed front). Buttons are print.
- ⚠ extension: a real placket overlap (one side over the other) needs an "overlap seam" mode
  (offset instead of weld). Collar stands/bands that are separate shaped pieces need a
  `collar` band mode (shaped strip). Propose these as engine additions when needed.
- Piping/soutache: print only.

## Polo ⚠ extension
Knit collar (a separate shaped piece standing and folding over) and a placket: needs the collar
band mode above. Body and sleeves as the tee.

## Things the engine does not cover yet ⚠
Hoods, pockets that open (a patch pocket can be a `label`-style patch on the outside with a small
extension), lower-body garments (shorts, pants: need a different mannequin: legs, and a
`leg` placement like `arm`), bonded tapes on seams (print), elastic hems (tighten with a band).

## Extending the engine: where to add things
- New placement: `pipeline/garmentkit/pattern.py` (resolve parameters into `pieces[i].place`) and
  `pipeline/blender/sim.py` (turn them into 3D positions). Keep placement rough; the sim finishes it.
- New finishing element: resolve in `pattern.py`, build geometry in `pipeline/blender/finish.py`
  with UVs = template pixels (`uv_of(px, py)`).
- Mannequin changes: `pipeline/garmentkit/body.py`.
- Always add or extend a fixture in `pipeline/tests/fixtures/` and run
  `python pipeline/tests/run_engine_tests.py`, and document new fields in `spec-reference.md`.
