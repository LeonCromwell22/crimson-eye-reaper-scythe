# Crimson Eye Reaper Scythe

A game-ready two-handed scythe for Roblox Studio, built in Blender 4.5 from
`scene/params.py` alone, plus the Luau that turns the import into a working Tool.

Every number below is measured by a stage and written to `out/<stage>_response.json`.
Nothing here is quoted from a plan.

| | |
|---|---|
| Height | **1.8008 m** = **6.43 studs** (Roblox 25:7) |
| Triangles | **8,906** total, target 12,000, hard per-mesh cap 20,000 |
| Body | **1 mesh, 1 material, 1 UV set**, one 1024 × 1024 atlas |
| Parts | shaft 1,848 / crown 2,708 / blade 2,104 / claw 944 / pommel 392 / tendril 334 |
| Separate meshes | 2 eyes (224 each) + 2 slit pupils (64 each), single material each |
| Atlas | 1024², 15.5 % covered, **469 texels per metre** (≈ 2.1 mm per texel) |
| High-poly source | **199,920** triangles, hidden, never exported |
| Textures | 5 for Studio + AO + curvature, all 1024² |
| FBX / .blend | 377 KB / 5.1 MB |
| Pivot | **the grip point, 1.1 m up the shaft** |

## What is in here

| Path | What it is |
|---|---|
| `scene/params.py` | every dimension, spike, vein, colour and budget. Pure data, never imports bpy |
| `scene/lib.py` | bpy helpers: lofts, wedge sections, spikes, ridge tubes, dents, cleaning, UVs, the UV-space painter, bakes, export |
| `scene/build.py` | one builder per stage, each ending in a `STAGE_JSON=` report with its own gate |
| `tools/run_stage.ps1` | run one stage through the live Blender bridge |
| `tools/build_headless.ps1` | run one stage headless (`blender -b`) |
| `tools/diag_nonmanifold.py` | where a non-manifold edge actually is |
| `tools/diag_colorspace.py` | what Blender really writes for a byte-image pixel |
| `luau/scythe_tool_setup.lua` | the Studio setup: Handle, SurfaceAppearance, Neon eyes, PointLight, Trail |
| `ROBLOX_SETUP.md` | the short handoff note |
| `out/` | per-stage JSON evidence, `previews/*.png`, the FBX and the .blend |

The transport is the same bridge as the dragon project's
(`overgrown-observatory/tools/live/bridge.ps1`); nothing here re-implements it.

## Running it

```powershell
# everything, from an empty scene, headless (~4 minutes)
powershell -File tools/build_headless.ps1 -Stage all

# one stage, cumulative: asking for s16 runs s0..s16
powershell -File tools/build_headless.ps1 -Stage s16_export

# the gate summary
$j = Get-ChildItem out/s*_response.json | ForEach-Object { Get-Content $_ -Raw | ConvertFrom-Json }
$j | Where-Object gate_ok -ne $true | Select-Object stage, checks
```

Stages are cumulative and each one is idempotent. A `.blend` snapshot is written
after every stage unless you pass `--no-snapshot`.

## Stages and what each gate proves

| Stage | Gate |
|---|---|
| `s0_setup` | metric scene, four collections, spec self-check: budgets sum to exactly 12,000 |
| `s1_scale_spike` | a 1 m cube exported **both** ways and re-imported: **1.0 units, either way** |
| `s2_shaft` | 1,848 ≤ 2,000 tris; S-curve **0.126 m wide where a straight shaft would be 0.056** |
| `s3_claw` | 4 talons, all tips on the blade side, 944 ≤ 1,500 tris |
| `s4_tendril` | the hook closes **264°** of its own centre, 334 ≤ 400 tris |
| `s5_crown` | 13 spikes 0.061–0.189 m (varied), 6 gems, eye recess **0.010 m deep**, tops out at **1.800 m** |
| `s6_blade` | edge **1.84 mm** vs spine **8.79 mm** (measured, not assumed), tip gap 0.0, 2,104 ≤ 3,000 tris |
| `s7_pommel` | points down at z 0.000, 88 mm wide above the point, recess 7 mm |
| `s8_eyes` | 4 separate parts, ≤ budget each, one material each, out of the body collection |
| `s9_cleanup` | 0 n-gons, 0 loose, 0 degenerate, 0 non-manifold, every shell outward, transforms applied, **geometry unmoved** |
| `s10_verify` | every budget, 12,000 total, height 1.8008, sits on 0, pivots on the grip |
| `s11_uv` | one 1024 atlas: no overlapping tiles, no UV outside its tile, 8 px padding |
| `s12_highpoly` | 6 hidden copies, 199,920 tris, in `HP_HighPoly`, out of the export set |
| `s13_bake` | normal **std 0.018**, AO **std 0.25**, curvature **std 0.25** — flatness is what fails, not absence |
| `s14_paint` | 7 maps written, density 469 texels/m, vein AO **preserved** (luma identical before/after), emissive a minority (11.7 %) |
| `s15_join` | 1 object, 1 material slot, 1 UV layer, **join moved nothing** (shift 0.0) |
| `s16_export` | FBX re-imports with the same 8,906 triangles, same names, **same place** |
| `s17_previews` | 7 views rendered, none blank |
| `s18_luau_check` | every mesh, every map file and the grip height named in the Luau |

## How the model is built

Orientation is fixed in `params.py` and never re-derived: **Z up, the blade
sweeping to −X, the weapon one thin plate in Y**, so the reference image's side
view is Blender's front view. Exported `-Z forward, Y up`, the flat of the blade
faces the camera in Studio.

**One definition, three consumers.** Each vein is a world-space polyline in
`params.py`. The same list builds the raised crack ridge (so the normal map
carries a real crack), paints the hot crimson into the ColorMap, and lights the
emissive mask. Geometry and glow therefore cannot drift apart, and a crack runs
across three UV islands without a seam because the paint is driven by where a
texel sits *on the model*, not on the atlas.

**Materials** are painted in UV space from per-part recipes (base and second
colour, roughness, metalness, and ordered rules: `polyline`, `near_point`,
`z_band`). Wear comes from the baked normal map's gradient, so highlights land on
sculpted keels rather than anywhere random. Ambient occlusion is folded into the
colour everywhere **except the veins**, which keep their full brightness - and
that is a measured property (`vein_luma_before_ao` equals `vein_luma_after_ao`),
not a claim.

## Deviations from the brief, and why

| Brief | Built | Why |
|---|---|---|
| Head 3,500 tris | **3,308** | the brief's own table (11,400 + 600 for the eyes) already sums to exactly 12,000, and the two slit pupils need 192 triangles. Taking them out of the crown's slack keeps the total honest instead of letting it drift |
| Two eye gems | 2 eyes **+ 2 pupils** | the gems have to show a vertical slit pupil, and there is no way to paint one on a Neon part - Neon ignores maps - so the pupil is its own tiny mesh, single-material like everything else |
| "Glowing veins in the head mount" | emissive mask on the body, **not** Neon | confirmed against Roblox's docs: `SurfaceAppearance` has `EmissiveMaskContent` / `EmissiveTint` / `EmissiveStrength`, which is the right tool and keeps the body at one mesh, one material, one atlas. The eyes stay Neon because a mask cannot make a surface read as lit from inside |
| "sculpt, retopo, hand-paint" | procedural high-poly, procedural paint | see the limitations above: the workflow is the same shape, the tools are code |

## What the gates actually caught

These are the reason the gates exist, in the order they fired:

1. **The join dropped the grip offset.** `bmesh.from_mesh` ignores an object's
   transform, and every part keeps its origin on the grip. The assembled body sat
   1.1 m too low while the separate eyes stayed put, so the exported FBX was
   2.747 m tall instead of 1.8. Every *difference*-based check was happy with it.
   Fixed in `lib.join`; `s15` and `s16` now assert absolute position, not size.
2. **The curvature bake came back flat** (std 0.0) because the high-poly was made
   the active object - in a selected-to-active bake the active object is the
   target. Caught by measuring std deviation instead of checking that a file
   appeared.
3. **A four-face pinch in the pommel's vein**: a closed loop whose last point
   repeated its first, welded into a non-manifold edge by `remove_doubles`. Found
   with `tools/diag_nonmanifold.py`, which prints the coordinates.
4. **Blender clears a bake target to black** even with `use_clear = False`. A
   black tangent-space normal is a fully bent surface, so every UV seam would
   have shown a dark outline; a black AO is full occlusion. The painter now
   stamps the fill back and bleeds baked values 8 px into the gaps.
5. **The vein AO exclusion was only partial** - it reached zero AO at a weight of
   1.0 but leaked at 0.9. The core is now excluded exactly, the shoulder fades
   smoothly, and the gate compares vein luminance before and after.
6. **Degenerate triangles at the blade's tip**, where the loft's rings collapsed
   to a point. The tip now keeps a 0.8 mm section, which still reads as a point.
7. **The first previews were washed out and the veins glowed white.** Two causes:
   Blender 4.x's AgX view transform grading a near-black weapon into pale beige
   under a 900 W key light, and the emissive mask wired straight into Emission
   Color. Previews now use the Standard transform and a modest rig, and the mask
   drives Emission Strength against a constant crimson tint - the way Studio does.

- **The high-poly is procedural, not sculpted.** Subdivision plus an outward
  displacement (199,920 tris, 22x the low-poly) is the bake source. It gives
  surface grain and edge curvature; it does not give a hand-modelled crack
  channel. The vein ridges are *raised*, not carved in.
- **"Hand-paint" is procedural.** Colour, roughness, metalness and the emissive
  mask are rasterised in UV space from the recipes; the normal and AO maps are
  genuine Cycles bakes. Nothing here was painted with a brush.
- **AO has nowhere to go in Studio.** `SurfaceAppearance` has no AO slot, so AO
  is multiplied into the ColorMap. `Scythe_AO.png` ships anyway, for Blender and
  for a MaterialVariant workflow later.
- **Metalness is derived, not baked.** Blender has no metalness bake; the map is
  written from the recipe and the normal-map wear term.
- **Curvature uses Cycles pointiness** through an EMIT bake, validated by std
  deviation (0.25). Pointiness is a geometry heuristic, not a true solver.
- **The body is one mesh holding many shells** (crown 32, blade 18, shaft 12,
  claw 11, pommel 4, tendril 3). Roblox renders that without complaint; what
  cares is collision, which is why the Handle is set to `CollisionFidelity =
  Hull`.
- **The atlas is 15.5 % used.** Each part gets a square tile sized by surface
  area, and a part's projection rarely fills its square. Density is the number
  that matters and it is 469 texels/m; a global island packer would do better.
- **The claw is a stylised mass**, not an anatomical hand: a palm, four curved
  talons and three knuckles. In a front view it reads as a grip.
- **The setup Luau has been run against Studio 4.5** — it built the Tool, the
  weld, the Neon eyes, the PointLight and the Trail in a live place, and the
  result was re-checked claim by claim (`out/studio/verify_tool_*.json`,
  `out/previews/studio_held_*.jpg`). Two Studio behaviours it corrected are noted
  in `ROBLOX_SETUP.md`: `Tool.Handle` is engine-managed and must never be
  assigned, and an FBX imported at Stud scale needs the 25/7 correction. The
  texture *asset ids* in `UPLOAD` are real, so the maps are already wired.
- **The R6 grip and the two-handed hold were solved against a purpose-built R6
  rig**, not against this place's Play session, which spawns an R15 avatar and
  offers no scriptable avatar-type setting. The rig was assembled from the
  documented R6 sizes and Motor6D values, and the engine itself did the
  equipping, so the grip it applied is the real one. Every R6 claim in
  `ROBLOX_SETUP.md` is a measurement in `out/studio/r6_*_response.json`; the one
  thing not tested is the `TwoHandedHold` LocalScript's event wiring on a real
  R6 player character, since this place cannot spawn one.
