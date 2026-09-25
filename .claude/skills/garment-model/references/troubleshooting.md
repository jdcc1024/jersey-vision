# Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `pattern error: unknown corner` / "not a segment of piece X's outline" | typo, or a seam uses two corners that aren't neighbours in `outline` | add the missing corner to `outline` between them, or use neighbouring corners |
| "triangulation moved boundary points" | corners out of order in `outline`, or a corner off the contour making the loop self-intersect | check corner order against `inspect.png`; snap corners to candidates |
| A segment follows the wrong side of the piece | two corners with nothing between them the "short way" passes another corner | add an intermediate corner or check corner coordinates |
| Seam ratio > 1.12 flagged | wrong segment picked, or mismatched corners (e.g. armhole to underarm vs to side-hem) | compare lengths in the report; fix corners |
| Twisted seam, fabric crossing itself | seam `a` and `b` run in opposite directions | swap `b`'s two corners |
| Front and back swapped / design mirrored on the model | `arc_deg` wrong, or piece drawn from inside | front `[-90,90]`, back `[90,270]`; `"flip": true` for pieces shown from the inside |
| Sleeve colours on the wrong arms | `side` or `front_half` wrong | check the mockups; set-in sleeve drawn from outside: left → `image_left` |
| Panels explode / fly off at frame 1 | initial placement intersects the mannequin or other panels badly | preview right after `("sim",)` with `SHOW_BODY`; raise `sim.wrap_clearance` or `arm_wrap_scale`; lower `grow_from` |
| Seam gap > 5 mm after sim (`max_seam_gap_mm`) | seams didn't finish closing | more `sim.frames`, higher `sewing_force_max` |
| Fabric crumpled / wavy everywhere | low bending, or rest lengths not from the pattern | raise `sim.bending` (2–5); make sure `rest_shape_key` is set |
| Sleeves crumpled at the cap | cap ease, arm too thin, sleeve starts far from arm | normal up to a point; thicken arm (`upper_arm_radius_mm`), lower `arm_wrap_scale` |
| Shirt hangs too loose / too tight | mannequin size | `body.fit_ease_mm` (smaller = fuller) or `chest_circ_mm` |
| Back hem lower than front | shallower back neck makes the back hang lower, normal within ~2 cm | reduce `sim.gravity` or raise the mannequin's back depth |
| Collar flares outward / sits flat | band direction | `lean_deg` (20–30 standing, 85 binding), `axis: "up"` for crew necks |
| Band edge floats off the neckline | loop segments don't meet at seams (warning in `pattern`) | order/orientation of `loop` segments |
| Thin grey lines along seams in three.js | artwork has no bleed past the cut lines | bleed 3–5 mm; `gk texture` does it for the sample print |
| Texture upside down / shifted in three.js | `flipY` left true | `texture.flipY = false` for glTF |
| Finish step output looks unsimulated | cloth cache reset (GarmentSim touched between frame chunks) | rerun sim → frames → finish without touching the object |
| `gk check`: median edge ratio far from 1 | wrong `mm_per_px`, or rest shape not the flat pattern | fix scale; verify with a known measurement |
| Blender MCP "cannot connect" | Blender not running or MCP server not started | ask the user to open Blender and start the add-on's server |
