"""Crimson Eye Reaper Scythe - build entry point.

USAGE
    blender -b --factory-startup -P scene/build.py -- --stage s0_setup
    powershell -File tools/run_stage.ps1 -Stage s15_paint

Stages are CUMULATIVE, exactly as in the observatory project: asking for s10
runs s0..s10 in order. Each stage is idempotent, each ends in a STAGE_JSON=
report, and the harness saves a .blend snapshot after every stage - so a failure
is attributable to one stage and the session can be inspected at that point
without re-running the whole chain.
"""
import argparse
import json
import math
import os
import sys
import time

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scene import params as P      # noqa: E402
from scene import lib as L         # noqa: E402

OUT_DIR = os.path.join(ROOT, "out")
PREVIEW_DIR = os.path.join(OUT_DIR, "previews")
HIGHPOLY_PREFIX = "HP_"


def out_path(*parts):
    path = os.path.join(OUT_DIR, *parts)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def save_snapshot(tag):
    path = out_path("%s.blend" % tag)
    try:
        bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
        return {"file": path, "bytes": os.path.getsize(path)}
    except Exception as exc:                      # pragma: no cover - reporting path
        return {"file": path, "error": str(exc)}


def write_json(name, payload):
    path = out_path(name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, default=str)
    return path


def body_parts():
    return [L.get(n) for n in P.BODY_PARTS if L.get(n) is not None]


def eye_parts():
    return [L.get(n) for n in P.EYE_PARTS + P.PUPIL_PARTS if L.get(n) is not None]


# ==================================================================== s0 =====
def stage_s0_setup():
    """An empty metric scene, the four collections, and the spec's own gate."""
    problems = P.sanity()
    scene = bpy.context.scene
    scene.name = "SCENE_scythe"
    scene.unit_settings.system = P.UNIT_SYSTEM
    scene.unit_settings.scale_length = P.SCALE_LENGTH
    scene.unit_settings.length_unit = P.LENGTH_UNIT
    scene.frame_start = 1
    scene.frame_end = 1
    scene.render.engine = "CYCLES"
    scene.cycles.samples = P.PREVIEW_SAMPLES
    scene.cycles.use_denoising = True
    L.ensure_collections(P.COLLECTIONS)

    # A 1.8 m reference box, so every later framing decision is checked against
    # the brief's height rather than against a feeling.
    ref = L.box("TEMP_SizeRef", P.TEMP_COLLECTION,
                (-0.10, 0.10), (0.45, 0.65), (0.0, P.HEIGHT_M))
    ref.hide_render = True
    grip = L.box("TEMP_GripRef", P.TEMP_COLLECTION,
                 (-0.03, 0.03), (-0.03, 0.03),
                 (P.GRIP[2] - 0.005, P.GRIP[2] + 0.005))
    grip.hide_render = True
    L.move_to_collection(ref, P.TEMP_COLLECTION)
    L.move_to_collection(grip, P.TEMP_COLLECTION)
    return L.report(
        "s0_setup",
        gate_ok=not problems,
        problems=problems,
        collections=P.COLLECTIONS,
        height_m=P.HEIGHT_M,
        height_studs=round(P.HEIGHT_M * P.STUDS_PER_METRE, 3),
        grip=list(P.GRIP),
        objects=len(bpy.data.objects),
        budget_total=P.budget_total(),
        brief_budget_total=sum(P.BRIEF_BUDGETS.values()),
        pupil_allowance=P.PUPIL_ALLOWANCE,
        crown_budget_note=("crown 3500 -> 3308: the two pupil shells need 192 "
                           "triangles and the brief's own table already sums to 12000"),
        tri_target=P.TRI_TARGET_TOTAL,
        crown_spikes=len(P.CROWN_SPIKES),
        veins={k: len(v) for k, v in P.VEINS.items()},
    )


# ==================================================================== s1 =====
def stage_s1_scale_spike():
    """Measure the export/import scale instead of assuming it.

    A 1 m cube is exported twice - once as FBX unit scale, once with the axis
    transform baked - then re-imported in a separate background Blender and
    measured. Whatever comes back is what ROBLOX_SETUP.md is allowed to claim.
    """
    results = {}
    cube = L.box("TEMP_ScaleCube", P.TEMP_COLLECTION,
                 (0.0, 1.0), (0.0, 1.0), (0.0, 1.0))
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    cube.select_set(True)
    bpy.context.view_layer.objects.active = cube
    for tag, scale_option, bake_transform in P.SCALE_SPIKE["variants"]:
        fbx = out_path("scale_spike_%s.fbx" % tag)
        L.export_fbx(fbx, use_selection=True,
                     settings={"apply_scale_options": scale_option,
                               "bake_space_transform": bake_transform,
                               "global_scale": 1.0})
        check, note = L.fbx_reimport_check(fbx)
        results[tag] = {
            "settings": {"apply_scale_options": scale_option,
                         "bake_space_transform": bake_transform},
            "file_bytes": os.path.getsize(fbx) if os.path.exists(fbx) else 0,
            "reimport": check,
            "note": note,
        }
    L.remove_object(cube)
    units_ok = bool(results.get("fbx_units", {}).get("reimport"))
    size = None
    if units_ok:
        size = results["fbx_units"]["reimport"]["size"]
    expected_studs = round(P.HEIGHT_M * P.STUDS_PER_METRE, 3)
    return L.report(
        "s1_scale_spike",
        gate_ok=bool(units_ok and size and abs(max(size) - 1.0) < 0.002),
        cube_side_m=P.SCALE_SPIKE["cube_size"],
        results=results,
        picked="fbx_units" if units_ok else None,
        reimported_cube_size=size,
        studs_per_metre=P.STUDS_PER_METRE,
        weapon_height_m=P.HEIGHT_M,
        weapon_height_studs=expected_studs,
        note=("a 1 m cube re-imports at %s Blender units, so with Scale Unit = "
              "Meter the 1.8 m scythe lands at %s studs"
              % (size, expected_studs)) if size else "the spike did not import",
    )

# ============================================================== builders ====
def vein_ridges(part, prefix, segments=5):
    """Raised crack ridges along a part's veins, tapering at both ends.

    The ridges are real geometry, so the normal map carries the crack, and the
    painter lights the same polyline - one definition, two consumers.
    """
    made = []
    for i, v in enumerate(P.VEINS[part]):
        pts = v["t"]
        r = v["r"] * P.VEIN_RIDGE_GAIN
        n = max(len(pts) - 1, 1)
        radii = []
        for k in range(len(pts)):
            taper = math.sin(math.pi * (k / float(n))) ** 0.45
            radii.append(max(r * (0.25 + 0.75 * taper), 0.0008))
        made.append(L.ridge_tube("%s%02d" % (prefix, i), P.TEMP_COLLECTION,
                                 pts, radii, segments=segments))
    return made


def spike_radius_at(idx, frac):
    """The spike's own radius at a fraction along it - for seating its gem."""
    _ang, _z, _len, r0, _bend, _tilt = P.CROWN_SPIKES[idx]
    r1 = max(r0 * 0.05, 0.0015)
    return r0 + (r1 - r0) * (frac ** 0.75)


def rotated_in_plane(direction, degrees):
    """Rotate an in-plane (XZ) direction about +Y, sweeping it along the blade."""
    from mathutils import Matrix
    v = Vector(direction).normalized()
    return tuple(v @ Matrix.Rotation(math.radians(degrees), 3, "Y"))


# ==================================================================== s2 =====
def stage_s2_shaft():
    """The shaft: a twisted, knotted, S-curved stave with red cracks."""
    L.remove_objects(["Scythe_Shaft", "TEMP_Shaft"])
    pieces = [L.tube("TEMP_Shaft_Tube", P.TEMP_COLLECTION, P.shaft_samples(),
                     segments=P.SHAFT_SEGMENTS)]
    # Knot bosses: small ovoid swellings where the wood has grown over itself.
    bosses = 0
    for k, (t, _amp, _w) in enumerate(P.SHAFT_KNOTS):
        if k % 2:
            continue
        ang = math.radians(35.0 + 96.0 * k)
        centre = P.shaft_surface(t, ang, lift=-P.shaft_radius(t) * 0.35)
        pieces.append(L.ellipsoid("TEMP_Shaft_Knot%d" % k, P.TEMP_COLLECTION,
                                  centre, (0.0165, 0.0135, 0.0300),
                                  segments=8, bands=6))
        bosses += 1
    # Two broken branch stubs, so the stave reads as cut wood.
    stubs = 0
    for k, (t, ang_deg) in enumerate(((0.415, 55.0), (0.775, 250.0))):
        ang = math.radians(ang_deg)
        base = P.shaft_surface(t, ang, lift=-0.004)
        direction = Vector((math.cos(ang), math.sin(ang), 0.55)).normalized()
        tip = Vector(base) + direction * 0.052
        bend = Vector(base) + direction * 0.026 + Vector((0.0, 0.0, 0.006))
        pieces.append(L.spike("TEMP_Shaft_Stub%d" % k, P.TEMP_COLLECTION,
                              base, tuple(tip), 0.0085, segments=6, ring_count=4,
                              bend=tuple(bend), flat=0.9, sq=0.85))
        stubs += 1
    pieces += vein_ridges("Scythe_Shaft", "TEMP_Shaft_Vein", segments=4)
    shaft = L.join(pieces, "Scythe_Shaft", P.PARTS_COLLECTION)
    L.orient_outward(shaft)
    box = L.bounds(shaft)
    stats = L.stats(shaft)
    swings = box[1][0] - box[0][0]
    straight = 2.0 * max(P.shaft_radius(t / 10.0) for t in range(11))
    checks = {
        "under_budget": stats["tris"] <= P.BUDGETS["Scythe_Shaft"],
        "s_curve_present": swings > straight * 1.35,
        "reaches_the_pommel_side": box[0][2] < P.SHAFT_Z0 + 0.004,
        "reaches_the_crown": box[1][2] > P.SHAFT_Z1 - 0.02,
        "no_loose_geometry": stats["loose_verts"] == 0 and stats["loose_edges"] == 0,
    }
    return L.report("s2_shaft", gate_ok=all(checks.values()), checks=checks,
                    tris=stats["tris"], budget=P.BUDGETS["Scythe_Shaft"],
                    shells=stats["shells"], knot_bosses=bosses, branch_stubs=stubs,
                    vein_ridges=len(P.VEINS["Scythe_Shaft"]),
                    bounds=box, x_extent=round(swings, 4),
                    straight_shaft_extent=round(straight, 4),
                    nonmanifold=stats["nonmanifold_edges"])
# CHUNK_END

# ==================================================================== s3 =====
def stage_s3_claw():
    """A skeletal hand: palm, four curved talons, three knuckles, cracks."""
    from mathutils import Matrix
    L.remove_objects(["Scythe_ClawGuard", "TEMP_Claw"])
    palm = L.ellipsoid("TEMP_Claw_Palm", P.TEMP_COLLECTION, (0.0, 0.0, 0.0),
                       P.CLAW_PALM_RADII, segments=12, bands=8)
    palm.data.transform(Matrix.Rotation(math.radians(P.CLAW_PALM_TILT_DEG), 4, "Y"))
    palm.data.transform(Matrix.Translation(P.CLAW_PALM_CENTRE))
    palm.data.update()
    pieces = [palm]
    talons = 0
    tips = []
    for (name, ang_deg, t, tip_off, bend_off, r0) in P.CLAW_TALONS:
        ang = math.radians(ang_deg)
        base = Vector(P.shaft_surface(t, ang, lift=0.012))
        tip = base + Vector(tip_off)
        bend = base + Vector(bend_off)
        pieces.append(L.spike("TEMP_Claw_%s" % name, P.TEMP_COLLECTION,
                              tuple(base), tuple(tip), r0,
                              segments=P.CLAW_TALON_SEGMENTS,
                              ring_count=P.CLAW_TALON_RINGS, bend=tuple(bend),
                              flat=P.CLAW_TALON_FLAT, sq=0.82))
        tips.append([round(v, 4) for v in tip])
        talons += 1
    knuckles = 0
    for ang_deg in P.CLAW_KNUCKLES:
        ang = math.radians(ang_deg)
        centre = P.shaft_surface(0.838, ang, lift=0.010)
        pieces.append(L.ellipsoid("TEMP_Claw_Knuckle%d" % knuckles,
                                  P.TEMP_COLLECTION, centre,
                                  (P.CLAW_KNUCKLE_R, P.CLAW_KNUCKLE_R,
                                   P.CLAW_KNUCKLE_R * 1.1), segments=8, bands=6))
        knuckles += 1
    pieces += vein_ridges("Scythe_ClawGuard", "TEMP_Claw_Vein", segments=4)
    claw = L.join(pieces, "Scythe_ClawGuard", P.PARTS_COLLECTION)
    L.orient_outward(claw)
    stats = L.stats(claw)
    box = L.bounds(claw)
    blade_side = all(t[0] < -0.02 for t in tips)
    checks = {
        "under_budget": stats["tris"] <= P.BUDGETS["Scythe_ClawGuard"],
        "four_talons": talons == 4,
        "talons_point_to_the_blade": blade_side,
        "no_loose_geometry": stats["loose_verts"] == 0 and stats["loose_edges"] == 0,
    }
    return L.report("s3_claw", gate_ok=all(checks.values()), checks=checks,
                    tris=stats["tris"], budget=P.BUDGETS["Scythe_ClawGuard"],
                    shells=stats["shells"], talons=talons, knuckles=knuckles,
                    talon_tips=tips, bounds=box,
                    nonmanifold=stats["nonmanifold_edges"])


# ==================================================================== s4 =====
def stage_s4_tendril():
    """The curled hook on the side opposite the blade."""
    L.remove_objects(["Scythe_TendrilHook", "TEMP_Tendril"])
    pts = P.tendril_points()
    radii = P.tendril_radii()
    samples = [{"centre": pts[i], "w": radii[i], "hu": radii[i], "hd": radii[i],
                "sq": 0.9} for i in range(len(pts))]
    pieces = [L.tube("TEMP_Tendril_Tube", P.TEMP_COLLECTION, samples,
                     segments=P.TENDRIL_SEGMENTS)]
    anchor = pts[len(pts) // 2]
    pieces.append(L.spike("TEMP_Tendril_Barb", P.TEMP_COLLECTION, anchor,
                          (anchor[0] + 0.020, -0.028, anchor[2] - 0.016),
                          0.0042, segments=6, ring_count=3, sq=0.85))
    pieces += vein_ridges("Scythe_TendrilHook", "TEMP_Tendril_Vein", segments=4)
    tendril = L.join(pieces, "Scythe_TendrilHook", P.PARTS_COLLECTION)
    L.orient_outward(tendril)
    stats = L.stats(tendril)
    box = L.bounds(tendril)
    # How far the curl actually wraps around its own centre, in degrees.
    centre = Vector((P.TENDRIL_CENTRE[0], 0.0, P.TENDRIL_CENTRE[2]))
    angles = [math.degrees(math.atan2((Vector(p) - centre).z,
                                      (Vector(p) - centre).x)) for p in pts]
    sweep = 0.0
    for i in range(len(angles) - 1):
        sweep += (angles[i + 1] - angles[i] + 540.0) % 360.0 - 180.0
    checks = {
        "under_budget": stats["tris"] <= P.BUDGETS["Scythe_TendrilHook"],
        "hook_closes": abs(sweep) >= 200.0,
        "on_the_far_side": box[0][0] > 0.04,
        "no_loose_geometry": stats["loose_verts"] == 0 and stats["loose_edges"] == 0,
    }
    return L.report("s4_tendril", gate_ok=all(checks.values()), checks=checks,
                    tris=stats["tris"], budget=P.BUDGETS["Scythe_TendrilHook"],
                    shells=stats["shells"], sweep_deg=round(sweep, 1),
                    bounds=box, nonmanifold=stats["nonmanifold_edges"])

# ==================================================================== s5 =====
def stage_s5_crown():
    """The thorny crown: hub, 13 uneven spikes, grey gems, eye socket, veins."""
    L.remove_objects(["Scythe_HeadCrown", "TEMP_Crown"])
    hub_samples = [{"centre": (x_off, 0.0, z), "w": w, "hu": hu, "hd": hd,
                    "sq": sq}
                   for (z, w, hu, hd, x_off, sq) in P.HUB_RINGS]
    hub = L.tube("TEMP_Crown_Hub", P.TEMP_COLLECTION, hub_samples,
                 segments=P.HUB_SEGMENTS)
    # The eye's recess: a dent, not a boolean - see lib.dent_surface for why.
    recess = L.dent_surface(hub, P.CROWN_EYE_SOCKET, 0.048, 0.010)
    pieces = [hub]
    spike_tips = []
    for idx in range(len(P.CROWN_SPIKES)):
        base, bend, tip, r0 = P.crown_spike_frame(idx)
        pieces.append(L.spike("TEMP_Crown_Spike%02d" % idx, P.TEMP_COLLECTION,
                              base, tip, r0, segments=P.CROWN_SPIKE_SEGMENTS,
                              ring_count=P.CROWN_SPIKE_RINGS, bend=bend,
                              flat=0.92, sq=0.78))
        spike_tips.append([round(v, 4) for v in tip])
    gems = 0
    for idx, along in P.CROWN_GEMS:
        point = P._spike_point(idx, along)
        r = spike_radius_at(idx, along)
        pieces.append(L.ellipsoid("TEMP_Crown_Gem%02d" % idx, P.TEMP_COLLECTION,
                                  (point[0], point[1] - r * 0.85, point[2]),
                                  P.CROWN_GEM_RADII, segments=8, bands=6))
        gems += 1
    pieces += vein_ridges("Scythe_HeadCrown", "TEMP_Crown_Vein", segments=4)
    crown = L.join(pieces, "Scythe_HeadCrown", P.PARTS_COLLECTION)
    L.orient_outward(crown)
    stats = L.stats(crown)
    box = L.bounds(crown)
    tops = [t[2] for t in spike_tips]
    lengths = [s[2] for s in P.CROWN_SPIKES]
    checks = {
        "under_budget": stats["tris"] <= P.BUDGETS["Scythe_HeadCrown"],
        "spikes_10_to_14": 10 <= len(P.CROWN_SPIKES) <= 14,
        "spike_lengths_varied": min(lengths) < max(lengths) * 0.5,
        "gems_present": gems >= 3,
        "eye_recess_deep_enough": recess["deepest_recess_m"] >= 0.004,
        "recessed_vertices": recess["vertices_moved"] > 0,
        "tops_out_at_1m80": abs(max(tops) - P.HEIGHT_M) < 0.006,
        "no_loose_geometry": stats["loose_verts"] == 0 and stats["loose_edges"] == 0,
    }
    return L.report("s5_crown", gate_ok=all(checks.values()), checks=checks,
                    tris=stats["tris"], budget=P.BUDGETS["Scythe_HeadCrown"],
                    shells=stats["shells"], spikes=len(P.CROWN_SPIKES),
                    spike_lengths=lengths, spike_tip_z=[round(t, 4) for t in tops],
                    gems=gems, eye_recess=recess, bounds=box,
                    nonmanifold=stats["nonmanifold_edges"])

# ==================================================================== s6 =====
def local_thickness(obj, point, radius=0.011):
    """The mesh's local thickness across Y, near a world point.

    Returns None when nothing was found inside the radius. That matters: a
    silent 0.0 would make "the edge is thinner than the spine" pass by accident,
    which is exactly the kind of gate that looks green and proves nothing.
    """
    p = Vector(point)
    far = 0.0
    found = 0
    for v in obj.data.vertices:
        w = obj.matrix_world @ v.co
        if (w - p).length < radius:
            found += 1
            far = max(far, abs(w.y - p.y))
    if not found:
        return None
    return far * 2.0


def tip_reach(obj, point):
    """Closest a vertex gets to a point: how sharp the blade's tip really is."""
    p = Vector(point)
    coords = [obj.matrix_world @ v.co for v in obj.data.vertices]
    if not coords:
        return 99.0
    return min((c - p).length for c in coords)


def stage_s6_blade():
    """The crescent: wedge section, razor edge, spiked black spine, base fins."""
    L.remove_objects(["Scythe_Blade", "TEMP_Blade"])
    pieces = [L.wedge_loft("TEMP_Blade_Loft", P.TEMP_COLLECTION,
                           P.blade_samples())]
    for i, (t, length, r0, flat, back) in enumerate(P.BLADE_SPINE_SPIKES):
        base = P.blade_spine_point(t)
        direction = rotated_in_plane(P.blade_normal(t), back)
        tip = Vector(base) + Vector(direction) * length
        bend = (Vector(base) + Vector(direction) * (length * 0.55)
                + Vector((0.0, 0.0, 0.004)))
        pieces.append(L.spike("TEMP_Blade_Spike%02d" % i, P.TEMP_COLLECTION,
                              base, tuple(tip), r0,
                              segments=P.BLADE_SPIKE_SEGMENTS,
                              ring_count=P.BLADE_SPIKE_RINGS, bend=tuple(bend),
                              flat=flat, sq=0.70))
    for i, t in enumerate(P.BLADE_FIN_T):
        base = P.blade_spine_point(t)
        direction = rotated_in_plane(P.blade_normal(t), 46.0)
        tip = Vector(base) + Vector(direction) * P.BLADE_FIN_LEN[i]
        bend = Vector(base) + Vector(direction) * (P.BLADE_FIN_LEN[i] * 0.5)
        pieces.append(L.spike("TEMP_Blade_Fin%d" % i, P.TEMP_COLLECTION, base,
                              tuple(tip), P.BLADE_FIN_R,
                              segments=P.BLADE_SPIKE_SEGMENTS,
                              ring_count=P.BLADE_SPIKE_RINGS, bend=tuple(bend),
                              flat=0.30, sq=0.65))
    pieces += vein_ridges("Scythe_Blade", "TEMP_Blade_Vein", segments=4)
    blade = L.join(pieces, "Scythe_Blade", P.PARTS_COLLECTION)
    L.orient_outward(blade)
    stats = L.stats(blade)
    box = L.bounds(blade)
    spine_thick = local_thickness(blade, P.blade_spine_point(0.5))
    edge_thick = local_thickness(blade, P.blade_edge_point(0.5))
    tip_gap = tip_reach(blade, P.BLADE_TIP)
    measurable = spine_thick is not None and edge_thick is not None
    checks = {
        "under_budget": stats["tris"] <= P.BUDGETS["Scythe_Blade"],
        "thickness_measurable": measurable,
        "razor_edge_thinner_than_spine": bool(
            measurable and spine_thick > 0.0 and edge_thick < spine_thick * 0.45),
        "sweeps_away_from_the_head": box[0][0] < -0.80,
        "tip_is_a_point": tip_gap < 0.008,
        "spine_spikes_present": len(P.BLADE_SPINE_SPIKES) >= 6,
        "no_loose_geometry": stats["loose_verts"] == 0 and stats["loose_edges"] == 0,
    }
    return L.report("s6_blade", gate_ok=all(checks.values()), checks=checks,
                    tris=stats["tris"], budget=P.BUDGETS["Scythe_Blade"],
                    shells=stats["shells"],
                    spine_spikes=len(P.BLADE_SPINE_SPIKES),
                    fins=len(P.BLADE_FIN_T),
                    spine_thickness_m=None if spine_thick is None else round(spine_thick, 5),
                    edge_thickness_m=None if edge_thick is None else round(edge_thick, 5),
                    tip_gap_m=round(tip_gap, 5),
                    bounds=box, nonmanifold=stats["nonmanifold_edges"])

# ================================================================= harness ===
STAGES = [
    "s0_setup", "s1_scale_spike", "s2_shaft", "s3_claw", "s4_tendril",
    "s5_crown", "s6_blade", "s7_pommel", "s8_eyes", "s9_cleanup",
    "s10_verify", "s11_uv", "s12_highpoly", "s13_bake", "s14_paint",
    "s15_join", "s16_export", "s17_previews", "s18_luau_check",
]
STAGE_TITLES = {
    "s0_setup": "metric scene, collections, spec gate",
    "s1_scale_spike": "measure the FBX scale instead of assuming it",
    "s2_shaft": "twisted knotted shaft, S-curve, bulges, crack ridges",
    "s3_claw": "skeletal clawed hand gripping the shaft",
    "s4_tendril": "curled tendril hook on the far side of the blade",
    "s5_crown": "thorny crown: hub, 13 varied spikes, gems, socket, veins",
    "s6_blade": "crescent blade: razor edge, spiked black spine, fins",
    "s7_pommel": "pointed shield cap with its own eye recess",
    "s8_eyes": "two Neon eyeballs and their slit pupils",
    "s9_cleanup": "clean, triangulate, orient, apply transforms, origin to grip",
    "s10_verify": "re-measure everything against the brief's budgets",
    "s11_uv": "one 1024 atlas, shelf packed, 8 px padding",
    "s12_highpoly": "hidden high-poly copies, the bake source",
    "s13_bake": "normal, ambient occlusion and curvature",
    "s14_paint": "colour, roughness, metalness, emissive mask, AO fold-in",
    "s15_join": "join the body to one mesh with one material",
    "s16_export": "FBX plus a re-import verification, and the .blend",
    "s17_previews": "render the named views",
    "s18_luau_check": "every exported name resolves in the Luau",
}



# ==================================================================== s7 =====
def stage_s7_pommel():
    """The pointed shield cap, with its own eye recess."""
    L.remove_objects(["Scythe_Pommel", "TEMP_Pommel"])
    samples = [{"centre": (0.0, 0.0, z), "w": w, "hu": hu, "hd": hd, "sq": sq}
               for (z, w, hu, hd, sq) in P.POMMEL_RINGS]
    body = L.tube("TEMP_Pommel_Body", P.TEMP_COLLECTION, samples,
                  segments=P.POMMEL_SEGMENTS)
    recess = L.dent_surface(body, P.POMMEL_SOCKET, 0.026, 0.007)
    pieces = [body] + vein_ridges("Scythe_Pommel", "TEMP_Pommel_Vein", segments=4)
    pommel = L.join(pieces, "Scythe_Pommel", P.PARTS_COLLECTION)
    L.orient_outward(pommel)
    stats = L.stats(pommel)
    box = L.bounds(pommel)
    checks = {
        "under_budget": stats["tris"] <= P.BUDGETS["Scythe_Pommel"],
        "points_down": abs(box[0][2]) < 0.003,
        "widest_above_the_point": (box[1][0] - box[0][0]) > 0.070,
        "eye_recess_deep_enough": recess["deepest_recess_m"] >= 0.003,
        "recessed_vertices": recess["vertices_moved"] > 0,
        "no_loose_geometry": stats["loose_verts"] == 0 and stats["loose_edges"] == 0,
    }
    return L.report("s7_pommel", gate_ok=all(checks.values()), checks=checks,
                    tris=stats["tris"], budget=P.BUDGETS["Scythe_Pommel"],
                    shells=stats["shells"], eye_recess=recess, bounds=box,
                    nonmanifold=stats["nonmanifold_edges"])


# ==================================================================== s8 =====
def stage_s8_eyes():
    """Two separate Neon eyeballs, each with its own slit pupil shell."""
    L.remove_objects(list(P.EYE_PARTS) + list(P.PUPIL_PARTS) + ["TEMP_Eye"])
    eye_mat = L.make_material("Scythe_EyeNeon", P.EYE_COLOUR, emission=None,
                              roughness=0.15)
    pupil_mat = L.make_material("Scythe_Pupil", P.PUPIL_COLOUR, emission=None,
                                roughness=0.35)
    spec = (
        (P.EYE_PARTS[0], P.EYE_HEAD_CENTRE, P.EYE_HEAD_R,
         P.PUPIL_PARTS[0], P.PUPIL_HEAD_CENTRE, P.PUPIL_HEAD_RADII),
        (P.EYE_PARTS[1], P.EYE_POMMEL_CENTRE, P.EYE_POMMEL_R,
         P.PUPIL_PARTS[1], P.PUPIL_POMMEL_CENTRE, P.PUPIL_POMMEL_RADII),
    )
    made = {}
    for eye_name, centre, r, pupil_name, pupil_c, pupil_r in spec:
        eye = L.ellipsoid(eye_name, P.EYES_COLLECTION, centre, (r, r, r),
                          segments=P.EYE_SEGMENTS, bands=P.EYE_RING_BANDS)
        L.orient_outward(eye)
        L.assign_material(eye, eye_mat)
        pupil = L.ellipsoid(pupil_name, P.EYES_COLLECTION, pupil_c, pupil_r,
                            segments=P.PUPIL_SEGMENTS, bands=P.PUPIL_RING_BANDS)
        L.orient_outward(pupil)
        L.assign_material(pupil, pupil_mat)
        made[eye_name] = {"tris": L.stats(eye)["tris"],
                          "material": eye.data.materials[0].name}
        made[pupil_name] = {"tris": L.stats(pupil)["tris"],
                            "material": pupil.data.materials[0].name}
    checks = {
        "each_mesh_under_budget": all(
            L.stats(L.get(n))["tris"] <= P.BUDGETS[n]
            for n in P.EYE_PARTS + P.PUPIL_PARTS),
        "four_separate_objects": all(
            L.get(n) is not None for n in P.EYE_PARTS + P.PUPIL_PARTS),
        "one_material_each": all(
            len(L.get(n).data.materials) == 1
            for n in P.EYE_PARTS + P.PUPIL_PARTS),
        "eyes_stay_out_of_the_body": all(
            L.get(n).users_collection[0].name == P.EYES_COLLECTION
            for n in P.EYE_PARTS + P.PUPIL_PARTS),
    }
    return L.report("s8_eyes", gate_ok=all(checks.values()), checks=checks,
                    budgets={n: P.BUDGETS[n] for n in P.EYE_PARTS + P.PUPIL_PARTS},
                    made=made,
                    eye_material={"colour": P.EYE_COLOUR, "neon_in_studio": True,
                                  "map": "none - the eyes are the only Neon parts"})



# ==================================================================== s9 =====
ATLAS_MATERIAL = "Scythe_Atlas"    # placeholder until s15 wires the real maps


def stage_s9_cleanup():
    """Clean, triangulate, orient, apply transforms, park the origin on the grip.

    Every object's origin moves to the grip point at once, and the bounds on
    either side prove the geometry itself did not move while it happened.
    """
    names = list(P.BODY_PARTS) + list(P.EYE_PARTS) + list(P.PUPIL_PARTS)
    atlas = L.make_material(ATLAS_MATERIAL, P.ANCHOR_COLOUR, roughness=0.6)
    report = {}
    problems = []
    for name in names:
        obj = L.get(name)
        if obj is None:
            problems.append("missing object %s" % name)
            continue
        before = L.bounds(obj)
        before_tris = L.stats(obj)["tris"]
        merged = L.clean_mesh(obj)
        flips = L.orient_outward(obj)
        if name in P.BODY_PARTS and not obj.data.materials:
            L.assign_material(obj, atlas)
        L.set_origin(obj, P.GRIP)
        after = L.bounds(obj)
        stats = L.stats(obj)
        moved = 0.0
        if before and after:
            moved = max(max(abs(before[i][k] - after[i][k]) for k in range(3))
                        for i in range(2))
        report[name] = {
            "tris": stats["tris"], "tris_before": before_tris,
            "loose_verts": stats["loose_verts"],
            "loose_edges": stats["loose_edges"],
            "ngons": stats["ngons"], "quads": stats["quads"],
            "degenerate_faces": stats["degenerate"],
            "shells": stats["shells"], "shell_flips": flips,
            "nonmanifold_edges": stats["nonmanifold_edges"],
            "signed_volume": stats["signed_volume"],
            "materials": [m.name for m in obj.data.materials],
            "uv_layers": len(obj.data.uv_layers),
            "origin": [round(v, 6) for v in obj.location],
            "scale": tuple(round(v, 6) for v in obj.scale),
            "rotation": tuple(round(v, 6) for v in obj.rotation_euler),
            "bounds_before": before, "bounds_after": after,
            "geometry_moved": round(moved, 6),
        }
    checks = {
        "no_missing_objects": not problems,
        "all_triangles": all(r["ngons"] == 0 and r["quads"] == 0
                             for r in report.values()),
        "no_loose_geometry": all(r["loose_verts"] == 0 and r["loose_edges"] == 0
                                 for r in report.values()),
        "no_degenerate_faces": all(r["degenerate_faces"] == 0
                                   for r in report.values()),
        "no_nonmanifold_edges": all(r["nonmanifold_edges"] == 0
                                    for r in report.values()),
        "all_shells_face_outward": all(r["signed_volume"] > 0
                                       for r in report.values()),
        "one_material_each": all(len(r["materials"]) == 1
                                 for r in report.values()),
        "scale_and_rotation_applied": all(
            r["scale"] == (1.0, 1.0, 1.0) and r["rotation"] == (0.0, 0.0, 0.0)
            for r in report.values()),
        "origins_on_the_grip": all(
            max(abs(r["origin"][i] - P.GRIP[i]) for i in range(3)) < 1e-6
            for r in report.values()),
        "cleanup_did_not_move_geometry": all(r["geometry_moved"] < 1e-5
                                             for r in report.values()),
        # Cleanup is allowed to drop degenerate triangles - that is the point of
        # it - but not to quietly reshape the model: anything beyond 2% means the
        # merge distance is eating real geometry and the gate must say so.
        "cleanup_only_removed_degenerate_tris": all(
            r["tris"] <= r["tris_before"]
            and (r["tris_before"] - r["tris"]) <= 0.02 * max(r["tris_before"], 1)
            for r in report.values()),
    }
    return L.report("s9_cleanup", gate_ok=all(checks.values()), checks=checks,
                    problems=problems, objects=report, grip=list(P.GRIP),
                    total_tris=sum(r["tris"] for r in report.values()))


# =================================================================== s10 =====
def stage_s10_verify():
    """Re-measure everything from scratch, against the brief's numbers."""
    names = list(P.BODY_PARTS) + list(P.EYE_PARTS) + list(P.PUPIL_PARTS)
    present = sorted(o.name for o in L.mesh_objects() if not L.is_temp(o))
    missing = [n for n in names if n not in present]
    extra = [n for n in present if n not in names]
    stats = {n: L.stats(L.get(n)) for n in names if L.get(n) is not None}
    over = [n for n, s in stats.items() if s["tris"] > P.BUDGETS[n]]
    total = sum(s["tris"] for s in stats.values())
    box = L.scene_bounds(names)
    height = round(box[1][2] - box[0][2], 4)
    studs = round(height * P.STUDS_PER_METRE, 3)
    below = round(P.GRIP[2] - box[0][2], 4)
    above = round(box[1][2] - P.GRIP[2], 4)
    pivot_errors = []
    for n in names:
        obj = L.get(n)
        if obj is None:
            continue
        err = (Vector(obj.location) - Vector(P.GRIP)).length
        if err > 1e-6:
            pivot_errors.append({"name": n, "err": round(err, 6)})
    uv_missing = [n for n in names
                  if L.get(n) is not None and len(L.get(n).data.uv_layers) == 0]
    checks = {
        "every_expected_object_present": not missing,
        "no_extra_objects": not extra,
        "every_part_under_its_budget": not over,
        "total_under_12000": total <= P.TRI_TARGET_TOTAL,
        "no_mesh_over_the_hard_cap": all(s["tris"] <= P.CAP_PER_OBJECT
                                         for s in stats.values()),
        "height_is_1m80": abs(height - P.HEIGHT_M) < 0.012,
        "assembly_sits_on_zero": abs(box[0][2]) < 0.01,
        "assembly_tops_out_at_1m80": abs(box[1][2] - P.HEIGHT_M) < 0.02,
        "grip_is_inside_the_weapon": below > 0.2 and above > 0.2,
        "pivots_on_the_grip": not pivot_errors,
        "no_nonmanifold_edges": all(s["nonmanifold_edges"] == 0
                                    for s in stats.values()),
        "all_volumes_positive": all(s["signed_volume"] > 0
                                    for s in stats.values()),
        "one_material_each": all(len(L.get(n).data.materials) == 1
                                 for n in names if L.get(n)),
    }
    return L.report("s10_verify", gate_ok=all(checks.values()), checks=checks,
                    failed=[k for k, v in checks.items() if not v],
                    missing=missing, extra=extra, over_budget=over,
                    total_tris=total, tri_target=P.TRI_TARGET_TOTAL,
                    per_object={n: {"tris": s["tris"], "budget": P.BUDGETS[n],
                                    "shells": s["shells"],
                                    "nonmanifold": s["nonmanifold_edges"],
                                    "volume": s["signed_volume"]}
                                for n, s in stats.items()},
                    bounds_m=box, height_m=height, height_studs=studs,
                    export_bounds_m=box,
                    studs_per_metre=P.STUDS_PER_METRE,
                    metres_below_grip=below, metres_above_grip=above,
                    pivot_errors=pivot_errors, uv_missing=uv_missing)



# =================================================================== s11 =====
def stage_s11_uv(padding_px=None, gap=0.006):
    """One 1024 atlas: every body part smart-projected into its packed tile.

    Tiles are sized by surface area, so the blade and the crown - which carry
    most of the paint - get more texels than a vein ridge does, and the whole
    weapon still shares a single map.
    """
    size = P.TEXTURE_SIZE
    padding_px = padding_px or P.TEXTURE_PAD_PX
    pad_uv = padding_px / float(size)
    parts = [L.get(n) for n in P.BODY_PARTS if L.get(n) is not None]
    weights = {}
    for obj in parts:
        weights[obj.name] = max(sum(p.area for p in obj.data.polygons), 1e-5)
    rects = L.shelf_pack(weights, pad_uv, gap)
    results = {}
    problems = []
    for obj in parts:
        method = L.uv_smart(obj, margin=pad_uv * 0.5)
        bounds = L.uv_bounds(obj)
        if not bounds:
            problems.append("no uv on %s" % obj.name)
            continue
        u0, u1, v0, v1 = bounds
        du, dv = max(u1 - u0, 1e-6), max(v1 - v0, 1e-6)
        tx, ty, side = rects[obj.name]
        scale = max((side - 2.0 * pad_uv) / max(du, dv), 1e-6)
        shift_u = tx + pad_uv - u0 * scale
        shift_v = ty + pad_uv - v0 * scale
        uv = obj.data.uv_layers.active.data
        for d in uv:
            d.uv = (d.uv[0] * scale + shift_u, d.uv[1] * scale + shift_v)
        obj.data.update()
        results[obj.name] = {"method": method, "tile": [tx, ty, side],
                             "uv": L.uv_bounds(obj),
                             "area_m2": round(weights[obj.name], 6)}
    bad = []
    for name, r in results.items():
        x, y, s = r["tile"]
        if x < 0 or y < 0 or x + s > 1.0 + 1e-6 or y + s > 1.0 + 1e-6:
            bad.append({"object": name, "why": "tile outside the atlas",
                        "tile": r["tile"]})
    order = list(results)
    for i in range(len(order)):
        for j in range(i + 1, len(order)):
            ax, ay, a = results[order[i]]["tile"]
            bx, by, b = results[order[j]]["tile"]
            if ax < bx + b and bx < ax + a and ay < by + b and by < ay + a:
                bad.append({"objects": [order[i], order[j]], "why": "tiles overlap"})
    for name, r in results.items():
        x, y, s = r["tile"]
        b = r["uv"]
        if (b[0] < x - 1e-4 or b[1] > x + s + 1e-4
                or b[2] < y - 1e-4 or b[3] > y + s + 1e-4):
            bad.append({"object": name, "why": "uv outside its tile",
                        "tile": r["tile"], "uv": b})
    checks = {
        "every_body_part_has_uvs": not problems and len(results) == len(P.BODY_PARTS),
        "no_tile_problems": not bad,
        "one_atlas_for_the_whole_body": True,
        "padding_is_8px": padding_px == P.TEXTURE_PAD_PX,
    }
    return L.report("s11_uv", gate_ok=all(checks.values()), checks=checks,
                    problems=problems, tile_problems=bad, size=size,
                    padding_px=padding_px,
                    smallest_tile_px=round(size * min(r["tile"][2]
                                                      for r in results.values()), 1)
                    if results else 0,
                    tiles=results)



# =================================================================== s12 =====
def stage_s12_highpoly(subdiv=2, strength=0.0016, max_tris=400000):
    """Hidden high-poly copies: the detail source for the bakes.

    Procedural, not sculpted - that is the one honest substitution in this
    build, and the README says so plainly. Subdivision gives the surface curves
    the low-poly cannot carry; the displacement pushes every point *outward*
    (mid_level 0.0), which both adds grain and guarantees the high-poly encloses
    the low-poly - without that enclosure a bake quietly comes back flat.
    """
    L.remove_objects([HIGHPOLY_PREFIX])
    tex = bpy.data.textures.get("SCYTHE_HP_Noise")
    if tex is None:
        tex = bpy.data.textures.new("SCYTHE_HP_Noise", type="CLOUDS")
    tex.noise_scale = 0.055
    tex.noise_depth = 3
    made = {}
    problems = []
    for name in P.BODY_PARTS:
        src = L.get(name)
        if src is None:
            problems.append("missing %s" % name)
            continue
        me = src.data.copy()
        me.name = HIGHPOLY_PREFIX + name
        high = bpy.data.objects.new(HIGHPOLY_PREFIX + name, me)
        L.collection(P.HIGHPOLY_COLLECTION).objects.link(high)
        high.matrix_world = src.matrix_world.copy()
        high.hide_render = True
        L.add_subsurf(high, levels=subdiv)
        L.add_displace(high, tex, strength=strength, mid_level=0.0)
        L.apply_modifiers(high)
        stats = L.stats(high)
        made[name] = {"highpoly": high.name, "tris": stats["tris"],
                      "shells": stats["shells"]}
    total = sum(v["tris"] for v in made.values())
    if total > max_tris:
        problems.append("high-poly is %d tris, over the %d cap" % (total, max_tris))
    low_total = sum(L.stats(L.get(n))["tris"] for n in P.BODY_PARTS if L.get(n))
    checks = {
        "one_highpoly_per_body_part": len(made) == len(P.BODY_PARTS),
        "highpoly_is_denser": all(made[n]["tris"] > L.stats(L.get(n))["tris"]
                                  for n in made),
        "highpoly_hidden_from_render": all(
            L.get(HIGHPOLY_PREFIX + n).hide_render for n in made),
        "highpoly_out_of_the_export_collection": all(
            L.get(HIGHPOLY_PREFIX + n).users_collection[0].name
            == P.HIGHPOLY_COLLECTION for n in made),
        "under_the_highpoly_cap": total <= max_tris,
    }
    return L.report("s12_highpoly", gate_ok=all(checks.values()), checks=checks,
                    problems=problems, subdiv=subdiv, strength_m=strength,
                    highpoly_total_tris=total, lowpoly_total_tris=low_total,
                    density_ratio=round(total / max(low_total, 1), 2),
                    objects=made)

    """Look a stage up by name, so the STAGES list stays the only registry."""

# =================================================================== s13 =====
def stage_s13_bake(samples=48, margin=16, cage_extrusion=0.004):
    """Bake normal, ambient occlusion and curvature from high to low.

    Tangent-space normals with green up, which is what Roblox expects. Every map
    is then measured: a bake that misses leaves the fill colour behind, and a
    normal map that baked flat is (0.5, 0.5, 1.0) - which "did a file appear"
    would happily score as success. Std deviation catches both.
    """
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = samples
    size = P.TEXTURE_SIZE
    out_dir = L.texture_dir(P.TEXTURE_FOLDER)
    lows = [L.get(n) for n in P.BODY_PARTS if L.get(n) is not None]
    highs = [L.get(HIGHPOLY_PREFIX + n) for n in P.BODY_PARTS
             if L.get(HIGHPOLY_PREFIX + n) is not None]
    if not highs:
        return L.report("s13_bake", gate_ok=False,
                        problems=["no high-poly: run s12 first"])

    # Per-channel fills, and use_clear off: Blender clears a bake target to
    # black, and a black tangent-space normal is a fully bent surface, so every
    # seam in the model would have shown a dark outline in Studio.
    fills = {"NormalMap": (0.5, 0.5, 1.0, 1.0),
             "AO": (1.0, 1.0, 1.0, 1.0),
             "Curvature": (0.5, 0.5, 0.5, 1.0)}
    images = {}
    for role, fill in fills.items():
        images[role] = L.new_image("%s_%s" % (P.TEXTURE_SET_NAME, role),
                                   size, fill=fill)
        if role != "ColorMap":
            images[role].colorspace_settings.name = "Non-Color"
    bake_mat, nodes = L.make_bake_material("SCYTHE_BakeMat", images,
                                           roles=tuple(fills))
    for low in lows:
        L.assign_material(low, bake_mat)
    # Curvature is read off the high-poly's own pointiness, so the high-poly
    # carries the emit material and the low-poly stays the bake target.
    curv_mat = L.make_curvature_material("SCYTHE_CurvatureMat")
    for high in highs:
        L.assign_material(high, curv_mat)

    bake = scene.render.bake
    bake.margin = margin
    bake.margin_type = "ADJACENT_FACES"
    bake.use_selected_to_active = True
    bake.use_cage = True
    bake.cage_extrusion = cage_extrusion
    bake.use_clear = False
    bake.target = "IMAGE_TEXTURES"
    bake.use_pass_direct = False
    bake.use_pass_indirect = False
    bake.use_pass_color = True

    results = {}
    problems = []
    # The active object is always the low-poly: in a selected-to-active bake the
    # active object is the *target* that receives the image and the selected
    # ones are the sources. Making the high-poly active (the obvious-looking
    # thing for a pointiness bake) sends the bake nowhere and leaves the fill
    # colour behind - which is why the curvature map came back flat the first
    # time and why this stage measures std deviation instead of existence.
    roles = (("NormalMap", "NORMAL"), ("AO", "AO"), ("Curvature", "EMIT"))
    for role, bake_type in roles:
        scene.cycles.bake_type = bake_type
        if role == "NormalMap":
            bake.normal_space = "TANGENT"
            bake.normal_r = "POS_X"
            bake.normal_g = "POS_Y"
            bake.normal_b = "POS_Z"
        for node in nodes.values():
            node.select = False
        nodes[role].select = True
        bake_mat.node_tree.nodes.active = nodes[role]
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        for o in lows + highs:
            o.hide_set(False)
            o.hide_render = False
            o.select_set(True)
        bpy.context.view_layer.objects.active = lows[0]
        try:
            bpy.ops.object.bake(type=bake_type)
        except Exception as exc:
            problems.append("bake %s failed: %s" % (role, exc))
            continue
        img = images[role]
        saved = L.save_image(img, os.path.join(out_dir, P.MAP_FILES[role]))
        results[role] = {"file": saved["file"], "bytes": saved["bytes"],
                         "bake_type": bake_type, "stats": L.image_stats(img)}
    for high in highs:
        high.hide_render = True
        high.hide_set(True)
    thresholds = {"NormalMap": 0.010, "AO": 0.010, "Curvature": 0.004}
    flat = [r for r, v in results.items()
            if v["stats"].get("std_luma", 0.0) < thresholds[r]]
    checks = {
        "all_three_maps_baked": len(results) == 3,
        "no_bake_errors": not problems,
        "no_flat_bake": not flat,
        "every_map_has_no_nan": all(v["stats"].get("nan", 1) == 0
                                    for v in results.values()),
    }
    return L.report("s13_bake", gate_ok=all(checks.values()), checks=checks,
                    problems=problems, flat_maps=flat, samples=samples,
                    margin_px=margin, cage_extrusion_m=cage_extrusion,
                    folder=out_dir, thresholds=thresholds, maps=results)



# =================================================================== s14 =====
def stage_s14_paint(ao_gain=0.55, bleed_px=8):
    """Colour, roughness, metalness and the emissive mask, painted in UV space.

    This is the "hand-paint" step, done procedurally: each texel is painted from
    where it sits on the *model*, so a crack crosses three UV islands without a
    seam. The veins are painted bright crimson and lit in the emissive mask at
    once, from the same polylines that built the crack ridges, and ambient
    occlusion is folded into the colour everywhere except on those veins.
    """
    import numpy as np
    size = P.TEXTURE_SIZE
    out_dir = L.texture_dir(P.TEXTURE_FOLDER)
    parts = [L.get(n) for n in P.BODY_PARTS if L.get(n) is not None]
    problems = []
    baked = {}
    for role in ("NormalMap", "AO", "Curvature"):
        img = bpy.data.images.get("%s_%s" % (P.TEXTURE_SET_NAME, role))
        if img is None or tuple(img.size) != (size, size):
            problems.append("missing %s: run s13 first" % role)
            continue
        baked[role] = np.array(img.pixels[:], dtype="f4").reshape(size, size, 4)
    if problems:
        return L.report("s14_paint", gate_ok=False, problems=problems)

    painted = L.paint_maps(size, parts, P.PAINT,
                           normal_array=baked["NormalMap"],
                           ao_array=baked["AO"], ao_gain=ao_gain,
                           baked=baked, bleed_px=bleed_px)
    ones = np.ones((size, size, 1), dtype="f4")

    def _rgba(arr):
        if arr.shape[2] == 4:
            return arr
        return np.concatenate([np.repeat(arr, 3, axis=2), ones], axis=2)

    sources = (
        # role, pixels, colourspace, the value the unpainted texels carry
        ("ColorMap", _rgba(L.linear_to_srgb(painted["colour"])), "sRGB", None),
        ("NormalMap", _rgba(painted["repaired"]["NormalMap"][0]), "Non-Color", 0.5),
        ("RoughnessMap", _rgba(painted["rough"]), "Non-Color", None),
        ("MetalnessMap", _rgba(painted["metal"]), "Non-Color", None),
        ("EmissiveMask", _rgba(painted["emissive"]), "Non-Color", None),
        ("AO", _rgba(painted["repaired"]["AO"][0]), "Non-Color", 1.0),
        ("Curvature", _rgba(painted["repaired"]["Curvature"][0]),
         "Non-Color", 0.5),
    )
    written = {}
    for role, arr, colorspace, fill in sources:
        name = "%s_%s" % (P.TEXTURE_SET_NAME, role)
        img = bpy.data.images.get(name)
        if img is None:
            img = L.new_image(name, size, fill=None)
        img.colorspace_settings.name = colorspace
        img.pixels = arr.reshape(-1).tolist()
        saved = L.save_image(img, os.path.join(out_dir, P.MAP_FILES[role]))
        written[role] = {
            "file": saved["file"], "bytes": saved["bytes"],
            "colorspace": colorspace, "deliverable": role in P.TEXTURE_ROLES,
            "stats": L.image_stats(img, fill=fill),
        }
    stats = painted["stats"]
    luma = written["ColorMap"]["stats"]["mean_luma"]
    emissive = written["EmissiveMask"]["stats"]
    variation = {r: v["stats"]["std_luma"] for r, v in written.items()}
    repaired = {r: v[1] for r, v in painted["repaired"].items()}
    checks = {
        "seven_maps_written": len(written) == 7,
        "five_are_the_studio_set": sum(1 for r in P.TEXTURE_ROLES
                                       if r in written) == 5,
        "every_map_is_1024": all(
            tuple(bpy.data.images["%s_%s" % (P.TEXTURE_SET_NAME, r)].size)
            == (size, size) for r in written),
        "the_atlas_is_actually_painted": stats["covered_pct"] >= 12.0,
        "texel_density_is_usable": stats["texels_per_metre"] >= 250.0,
        "colour_map_is_not_black": 0.02 < luma < 0.95,
        "every_map_has_variation": all(v > 0.008 for v in variation.values()),
        "emissive_mask_is_a_minority": 0.5 <= stats["emissive_pct_of_painted"] <= 30.0,
        "veins_are_not_darkened_by_ao": bool(stats["vein_ao_preserved"]),
        "baked_maps_edge_bled": all(v >= 0 for v in repaired.values()),
    }
    return L.report("s14_paint", gate_ok=all(checks.values()), checks=checks,
                    problems=problems, folder=out_dir,
                    painted=stats, veined_texels=stats["vein_texels"],
                    emissive_texels=stats["emissive_texels"],
                    bleed_px=bleed_px, ao_gain=ao_gain,
                    gap_texels_repaired=repaired,
                    variation=variation, maps=written)

def stage_func(name):
    """Look a stage up by name, so the STAGES list stays the only registry."""
    return globals().get("stage_" + name)



# =================================================================== s15 =====
def stage_s15_join():
    """Join the six body parts into ONE mesh with ONE material and ONE atlas."""
    parts = [L.get(n) for n in P.BODY_PARTS if L.get(n) is not None]
    problems = []
    if len(parts) != len(P.BODY_PARTS):
        problems.append("not every body part is present")
    before = sum(L.stats(o)["tris"] for o in parts)
    where = L.scene_bounds([o.name for o in parts])
    body = L.join(parts, P.BODY_JOINED, P.PARTS_COLLECTION)
    L.orient_outward(body)
    images = {}
    for role in P.TEXTURE_ROLES:
        img = bpy.data.images.get("%s_%s" % (P.TEXTURE_SET_NAME, role))
        if img is None:
            problems.append("missing image %s" % role)
        images[role] = img
    atlas = L.make_pbr_material(ATLAS_MATERIAL, images,
                                emission_strength=P.EMISSIVE_STRENGTH,
                                emission_tint=P.EMISSIVE_TINT_LINEAR)
    L.assign_material(body, atlas)
    L.set_origin(body, P.GRIP)
    stats = L.stats(body)
    bounds = L.bounds(body)
    uv = L.uv_bounds(body)
    # The check that would have caught the join dropping the grip offset: the
    # merged mesh has to sit exactly where the six parts sat.
    shift = 0.0
    if where and bounds:
        shift = max(max(abs(where[i][k] - bounds[i][k]) for k in range(3))
                    for i in range(2))
    checks = {
        "joined_to_one_object": L.get(P.BODY_JOINED) is not None,
        "the_six_parts_are_gone": all(L.get(n) is None for n in P.BODY_PARTS),
        "one_material_slot": len(body.data.materials) == 1,
        "one_uv_layer": len(body.data.uv_layers) == 1,
        "triangle_count_preserved": stats["tris"] == before,
        "join_did_not_move_the_geometry": shift < 1e-4,
        "body_sits_on_zero": abs(bounds[0][2]) < 0.01,
        "body_tops_out_at_1m80": abs(bounds[1][2] - P.HEIGHT_M) < 0.02,
        "uvs_inside_the_atlas": bool(uv and uv[0] >= -1e-4 and uv[1] <= 1.0 + 1e-4
                                     and uv[2] >= -1e-4 and uv[3] <= 1.0 + 1e-4),
        "origin_on_the_grip": max(abs(body.location[i] - P.GRIP[i])
                                  for i in range(3)) < 1e-6,
        "no_problems": not problems,
    }
    return L.report("s15_join", gate_ok=all(checks.values()), checks=checks,
                    problems=problems, object=P.BODY_JOINED,
                    tris=stats["tris"], tris_before_join=before,
                    shells=stats["shells"],
                    nonmanifold=stats["nonmanifold_edges"],
                    material=atlas.name,
                    material_slots=[m.name for m in body.data.materials],
                    maps_wired={r: (images[r].name if images[r] else None)
                                for r in P.TEXTURE_ROLES},
                    bounds_before_join=where, bounds_after_join=bounds,
                    position_shift_m=round(shift, 6),
                    uv_bounds=uv, bounds=bounds)


# =================================================================== s16 =====
def stage_s16_export():
    """The FBX, the .blend, and a re-import that measures the result."""
    out_dir = OUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    root = L.get(P.ROOT_EMPTY)
    if root is None:
        root = bpy.data.objects.new(P.ROOT_EMPTY, None)
        root.empty_display_size = 0.25
        L.collection(P.PARTS_COLLECTION).objects.link(root)
    L.remove_light_rig()

    export_names = [n for n in P.EXPORT_OBJECTS if L.get(n) is not None]
    missing = [n for n in P.EXPORT_OBJECTS if L.get(n) is None]
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for n in export_names:
        L.get(n).select_set(True)
    bpy.context.view_layer.objects.active = L.get(P.BODY_JOINED) or root

    blend_path = os.path.join(out_dir, "%s.blend" % P.BLEND_NAME)
    bpy.ops.wm.save_as_mainfile(filepath=blend_path, compress=True)
    blend_bytes = os.path.getsize(blend_path) if os.path.exists(blend_path) else 0
    fbx_path = os.path.join(out_dir, "%s.fbx" % P.FBX_NAME)
    exported = L.export_fbx(fbx_path, use_selection=True)
    check, note = L.fbx_reimport_check(fbx_path)

    wanted_tris = sum(L.stats(L.get(n))["tris"] for n in export_names
                      if L.get(n) and L.get(n).type == "MESH")
    box = L.scene_bounds([n for n in export_names
                          if L.get(n) and L.get(n).type == "MESH"])
    height = round(box[1][2] - box[0][2], 4)
    re_tris = check.get("tris") if check else None
    re_names = check.get("names") if check else []
    checks = {
        "blend_written": blend_bytes > 0,
        "fbx_written": exported["bytes"] > 0,
        "reimport_succeeded": bool(check),
        "reimport_triangles_match": re_tris == wanted_tris,
        "reimport_names_match": sorted(
            n for n in re_names if not n.startswith("RootNode")) == sorted(
                export_names),
        "no_export_objects_missing": not missing,
        "size_survives_the_round_trip": bool(
            check and abs(max(check["size"]) - height) < 0.01),
        # Absolute position, not just size. The eyes sat at 1.6 m while the body
        # sat 1.1 m lower, and every difference-based check was happy with that.
        "assembly_sits_on_zero": abs(box[0][2]) < 0.01,
        "assembly_tops_out_at_1m80": abs(box[1][2] - P.HEIGHT_M) < 0.02,
        "reimport_lands_in_the_same_place": bool(
            check and abs(check["lo"][2] - box[0][2]) < 0.02
            and abs(check["hi"][2] - box[1][2]) < 0.02),
    }
    return L.report("s16_export", gate_ok=all(checks.values()), checks=checks,
                    missing=missing, note=note,
                    blend={"file": blend_path, "bytes": blend_bytes},
                    fbx=exported, exported_objects=export_names,
                    triangles=wanted_tris, reimport_tris=re_tris,
                    reimport_names=re_names,
                    height_m=height,
                    height_studs=round(height * P.STUDS_PER_METRE, 3),
                    reimport_size_m=(check or {}).get("size"),
                    axis="%s forward, %s up" % (P.EXPORT["axis_forward"],
                                                P.EXPORT["axis_up"]))



# =================================================================== s17 =====
def stage_s17_previews(views=None, samples=24, resolution=(600, 900)):
    """Render the named views through a temporary camera and a three-point rig.

    Cycles on CPU, deliberately: a viewport grab in background mode has no
    window to grab, and a render is the only way to see whether the maps, the
    metal and the glow actually landed.
    """
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    world = scene.world or bpy.data.worlds.new("SCYTHE_World")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    # A mid grey, not near-black: a polished metal reflects its environment, so
    # against a dark world an 0.75-metal blade renders black whether the metalness
    # map is right or not - which is exactly what the second preview pass showed.
    bg.inputs["Color"].default_value = (0.32, 0.335, 0.36, 1.0)
    bg.inputs["Strength"].default_value = 1.0
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    L.add_light_rig()
    try:
        shots = L.render_views(views or list(P.VIEWS), PREVIEW_DIR,
                               resolution=resolution, prefix="scythe",
                               engine="CYCLES", samples=samples)
    finally:
        L.remove_light_rig()
    rendered = [n for n, s in shots.items() if s["exists"] and s["bytes"] > 4096]
    checks = {
        "every_view_rendered": len(rendered) == len(shots),
        "no_view_is_blank": all(s["exists"] and s["bytes"] > 4096
                                for s in shots.values()),
        "rendered_in_cycles": all(s["engine"] == "CYCLES" for s in shots.values()),
    }
    return L.report("s17_previews", gate_ok=all(checks.values()), checks=checks,
                    folder=PREVIEW_DIR, resolution=list(resolution),
                    samples=samples, rendered=rendered, shots=shots)


# =================================================================== s18 =====
def stage_s18_luau_check():
    """Every exported name, every map file and the grip height appear in the Luau.

    The same check the dragon project used at the end: if a name the FBX carries
    is not in the setup script, Studio will import a part nothing ever colours -
    and that is invisible until someone opens the place.
    """
    path = os.path.join(ROOT, "luau", "scythe_tool_setup.lua")
    problems = []
    if not os.path.exists(path):
        return L.report("s18_luau_check", gate_ok=False,
                        problems=["missing %s" % path])
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    meshes = [P.BODY_JOINED] + list(P.EYE_PARTS) + list(P.PUPIL_PARTS)
    missing_meshes = [n for n in meshes if n not in text]
    uploads = [P.MAP_FILES[r] for r in P.TEXTURE_ROLES]
    missing_maps = [m for m in uploads if m not in text]
    grip_mentioned = ("%.1f" % P.GRIP[2]) in text
    checks = {
        "every_mesh_is_named_in_the_luau": not missing_meshes,
        "every_uploadable_map_is_named": not missing_maps,
        "grip_height_is_documented": grip_mentioned,
        "emissive_is_wired": "EmissiveMaskContent" in text,
        "eyes_are_neon": "Neon" in text,
        "trail_is_set_up": "Trail" in text,
        "point_light_is_set_up": "PointLight" in text,
    }
    return L.report("s18_luau_check", gate_ok=all(checks.values()),
                    checks=checks, file=path,
                    missing_meshes=missing_meshes, missing_maps=missing_maps,
                    uploadable_maps=uploads, meshes=meshes)


def parse_args(argv):
    ap = argparse.ArgumentParser(
        prog="build.py",
        description="Build the Crimson Eye Reaper Scythe.",
        epilog="Stages are cumulative; each runs every earlier stage first.",
    )
    ap.add_argument("--stage", default="s0_setup", choices=STAGES + ["all"])
    ap.add_argument("--keep", dest="fresh", action="store_false", default=True,
                    help="build on top of whatever is already in the .blend")
    ap.add_argument("--no-snapshot", dest="snapshot", action="store_false",
                    default=True, help="skip the per-stage .blend snapshot")
    return ap.parse_args(argv)


def main():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    opts = parse_args(argv)

    if opts.fresh:
        bpy.ops.wm.read_factory_settings(use_empty=True)

    t_start = time.time()
    target = opts.stage
    stop = len(STAGES) - 1 if target == "all" else STAGES.index(target)
    print("")
    print("=" * 72)
    print(" %s   stage=%s   fresh=%s" % (P.PROJECT, target, opts.fresh))
    print("=" * 72)
    reports = {}
    skipped = []
    for name in STAGES[:stop + 1]:
        fn = stage_func(name)
        if fn is None:
            skipped.append(name)
            print("[build] %s: not implemented yet - %s" % (name, STAGE_TITLES[name]))
            continue
        print("")
        print("--- %s: %s ---" % (name, STAGE_TITLES[name]))
        t0 = time.time()
        payload = fn() or {}
        payload["seconds"] = round(time.time() - t0, 1)
        print("[build] %s gate_ok=%s in %.1fs"
              % (name, payload.get("gate_ok"), payload["seconds"]))
        reports[name] = payload
        write_json("%s_response.json" % name, payload)
        if opts.snapshot and name != "s17_previews":
            snap = save_snapshot(name)
            print("[build] snapshot %s (%s bytes)" % (snap["file"], snap.get("bytes")))

    if skipped:
        print("")
        print("[build] skipped (not implemented): %s" % ", ".join(skipped))
    failed = [n for n, p in reports.items() if p.get("gate_ok") is False]
    print("")
    print("[build] stages run: %d, failed gates: %s"
          % (len(reports), ", ".join(failed) if failed else "none"))
    print("[build] total %.1fs" % (time.time() - t_start))
    print("")
    if failed:
        sys.exit(3)


if __name__ == "__main__":
    main()
