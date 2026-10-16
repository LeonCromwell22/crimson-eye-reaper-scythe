"""Crimson Eye Reaper Scythe - every dimension, name, budget and colour.

Pure data. This module must never import bpy, so tooling, gates and headless
checks can read the whole specification without a Blender session.

ORIENTATION (fixed here, gated in s10)
    Z up, the weapon stands vertically, the blade sweeps toward -X and the
    scythe is one thin plate in Y. The reference image is a side view, so the
    reference's left-to-right becomes this file's -X-to-+X. Exported with
    Forward = -Z and Up = Y (the workspace convention), Blender's -Y front
    becomes Roblox's -Z front, so the flat of the blade faces the camera.

SCALE
    1.800 m tall. Roblox's ratio is 25:7 studs per metre (1 stud = 28 cm), so
    1.800 m is 6.43 studs. s1_scale_spike measures that rather than trusting it
    - see SCALE_SPIKE below.
"""
import math

PROJECT = "Crimson Eye Reaper Scythe"
SLUG = "crimson_eye_reaper_scythe"
BLEND_NAME = "crimson_eye_reaper_scythe"
FBX_NAME = "crimson_eye_reaper_scythe"

UNIT_SYSTEM = "METRIC"
SCALE_LENGTH = 1.0
LENGTH_UNIT = "METERS"

# --------------------------------------------------------------- scaling ---
HEIGHT_M = 1.800                  # pommel tip to the top of the head crown
STUDS_PER_METRE = 25.0 / 7.0       # Roblox: 1 stud = 28 cm
GRIP = (0.000, 0.000, 1.100)       # the hand holds here; every origin lands here

# s1 exports a reference cube both ways and re-imports it, so the note in
# ROBLOX_SETUP.md quotes a measurement instead of a belief.
SCALE_SPIKE = {
    "cube_size": 1.0,
    "variants": (
        ("fbx_units", "FBX_SCALE_UNITS", False),
        ("units_baked", "FBX_SCALE_NONE", True),
    ),
}

# ------------------------------------------------------------ collections ---
COLLECTIONS = ("Scythe", "Eyes", "HP_HighPoly", "TEMP_Ref")
PARTS_COLLECTION = "Scythe"
EYES_COLLECTION = "Eyes"
HIGHPOLY_COLLECTION = "HP_HighPoly"
TEMP_COLLECTION = "TEMP_Ref"
ROOT_EMPTY = "Scythe_Root"

# The six body parts are built, measured and painted separately, then joined
# into exactly one mesh with one material and one atlas (s14_join).
BODY_PARTS = ("Scythe_Shaft", "Scythe_HeadCrown", "Scythe_Blade",
              "Scythe_ClawGuard", "Scythe_Pommel", "Scythe_TendrilHook")
BODY_JOINED = "Scythe_Body"
EYE_PARTS = ("Scythe_EyeHead", "Scythe_EyePommel")
PUPIL_PARTS = ("Scythe_PupilHead", "Scythe_PupilPommel")
EXPORT_OBJECTS = (ROOT_EMPTY, BODY_JOINED) + EYE_PARTS + PUPIL_PARTS

# ---------------------------------------------------------------- budgets ---
BUDGETS = {
    "Scythe_Blade": 3000,
    # 3,500 in the brief, less the 192 triangles the two pupil shells need: the
    # brief's own allowances (11,400 + 600 for the eyes) already sum to exactly
    # 12,000, so an extra pair of tiny meshes has to come out of somewhere or
    # the total stops meaning anything. s0 reports this number.
    "Scythe_HeadCrown": 3308,
    "Scythe_Shaft": 2000,
    "Scythe_ClawGuard": 1500,
    "Scythe_Pommel": 1000,
    "Scythe_TendrilHook": 400,
    "Scythe_EyeHead": 300,
    "Scythe_EyePommel": 300,
    "Scythe_PupilHead": 96,
    "Scythe_PupilPommel": 96,
}
BRIEF_BUDGETS = {                  # the brief's own table, for the s0 comparison
    "Scythe_Blade": 3000, "Scythe_HeadCrown": 3500, "Scythe_Shaft": 2000,
    "Scythe_ClawGuard": 1500, "Scythe_Pommel": 1000, "Scythe_TendrilHook": 400,
    "Scythe_EyeHead": 300, "Scythe_EyePommel": 300,
}
PUPIL_ALLOWANCE = 192              # 2 x 96, taken out of the crown's slack
TRI_TARGET_TOTAL = 12000           # the brief's soft total
CAP_PER_OBJECT = 20000             # the brief's hard per-mesh limit

# ------------------------------------------------------------------ shaft ---
SHAFT_Z0 = 0.105                   # sits on top of the pommel
SHAFT_Z1 = 1.520                   # disappears into the head crown
SHAFT_RINGS = 32                   # loft rings along the length
SHAFT_SEGMENTS = 12                # vertices around the section
SHAFT_R0 = 0.0215                  # radius at the bottom
SHAFT_R1 = 0.0192                  # radius at the top
SHAFT_LEAN = -0.010                # a slight overall lean, so it is not plumb
SHAFT_SWING = 0.032                # amplitude of the S
SHAFT_Y_SWING = 0.020              # the out-of-plane part of the S
SHAFT_TWIST = 2.35                 # radians of twist over the whole length
SHAFT_SQ = 0.93                    # a touch squared off, so it is not a sausage

# Knots and bulges: (t along the shaft, +radius, width of the bump in t).
SHAFT_KNOTS = (
    (0.075, 0.0055, 0.045),
    (0.205, 0.0072, 0.055),
    (0.385, 0.0044, 0.038),
    (0.545, 0.0081, 0.050),
    (0.690, 0.0038, 0.033),
    (0.845, 0.0060, 0.046),
)


def shaft_point(t):
    """S-curved centreline. Two out-of-phase sines, plus a lean."""
    t = max(0.0, min(1.0, t))
    z = SHAFT_Z0 + (SHAFT_Z1 - SHAFT_Z0) * t
    x = SHAFT_SWING * math.sin(2.0 * math.pi * t) + SHAFT_LEAN * t
    y = SHAFT_Y_SWING * math.sin(math.pi * t - 0.55)
    return (x, y, z)


def shaft_radius(t):
    """Base taper plus the Gaussian bulges at the knots."""
    t = max(0.0, min(1.0, t))
    r = SHAFT_R0 + (SHAFT_R1 - SHAFT_R0) * t
    for kt, amp, width in SHAFT_KNOTS:
        r += amp * math.exp(-((t - kt) / width) ** 2)
    return r


def shaft_twist(t):
    return SHAFT_TWIST * max(0.0, min(1.0, t))


def shaft_sq(t):
    """Slightly flatter between the knots, rounder on them."""
    t = max(0.0, min(1.0, t))
    wobble = 0.05 * math.sin(5.0 * math.pi * t)
    return SHAFT_SQ + wobble


def shaft_samples():
    """The loft samples for tube(): one dict per ring."""
    out = []
    for i in range(SHAFT_RINGS):
        t = i / float(SHAFT_RINGS - 1)
        r = shaft_radius(t)
        out.append({
            "centre": shaft_point(t),
            "w": r * (1.0 + 0.05 * math.sin(3.0 * math.pi * t)),
            "hu": r,
            "hd": r,
            "sq": shaft_sq(t),
            "rot": shaft_twist(t),
        })
    return out


def shaft_surface(t, angle, lift=0.0):
    """A point on (or just off) the shaft's skin, for veins and branch stubs."""
    cx, cy, cz = shaft_point(t)
    r = shaft_radius(t) + lift
    return (cx + r * math.cos(angle), cy + r * math.sin(angle), cz)

# ------------------------------------------------------------ claw guard ---
# A skeletal hand wrapping the shaft a third of the way down from the head,
# its talons curling toward the blade side (-X).
CLAW_T = 0.812                     # the palm's place along the shaft
CLAW_PALM_CENTRE = (0.004, 0.000, 1.253)
CLAW_PALM_RADII = (0.031, 0.025, 0.044)
CLAW_PALM_TILT_DEG = 12.0          # leaning with the shaft
CLAW_TALONS = (
    # name, base angle around the shaft (deg), base t, tip offset, bend offset, r0
    ("finger_a", 148.0, 0.845, (-0.086, -0.014, -0.034), (-0.056, -0.023, 0.006), 0.0125),
    ("finger_b", 188.0, 0.836, (-0.090, 0.010, -0.048), (-0.058, 0.018, -0.002), 0.0130),
    ("finger_c", 236.0, 0.812, (-0.078, 0.030, -0.064), (-0.050, 0.030, -0.014), 0.0122),
    ("thumb", 108.0, 0.866, (-0.050, -0.030, 0.014), (-0.036, -0.028, 0.026), 0.0104),
)
CLAW_TALON_SEGMENTS = 7
CLAW_TALON_RINGS = 6
CLAW_TALON_FLAT = 0.86             # a little flattened, so they read as bone
CLAW_KNUCKLES = (148.0, 188.0, 236.0)   # angles that get a joint bump
CLAW_KNUCKLE_R = 0.0165

# ---------------------------------------------------------- tendril hook ---
# A curled hook on the far side of the blade (`opposite side` in the brief).
TENDRIL_CENTRE = (0.130, 0.0, 1.470)
TENDRIL_START_DEG = 205.0
TENDRIL_SWEEP_DEG = 264.0
TENDRIL_POINTS = 13
TENDRIL_R_OUT = 0.055
TENDRIL_R_IN = 0.023
TENDRIL_TUBE_R0 = 0.0125
TENDRIL_TUBE_R1 = 0.0022
TENDRIL_SEGMENTS = 7


def tendril_points():
    """The hook's centreline: a planar spiral, curling in the blade plane."""
    pts = []
    for i in range(TENDRIL_POINTS):
        a = math.radians(TENDRIL_START_DEG
                         + TENDRIL_SWEEP_DEG * i / float(TENDRIL_POINTS - 1))
        r = TENDRIL_R_OUT + (TENDRIL_R_IN - TENDRIL_R_OUT) * i / float(TENDRIL_POINTS - 1)
        pts.append((TENDRIL_CENTRE[0] + r * math.cos(a),
                    0.0,
                    TENDRIL_CENTRE[2] + r * math.sin(a)))
    return pts


def tendril_radii():
    return [TENDRIL_TUBE_R0 + (TENDRIL_TUBE_R1 - TENDRIL_TUBE_R0)
            * (i / float(TENDRIL_POINTS - 1)) ** 0.85
            for i in range(TENDRIL_POINTS)]


# ------------------------------------------------------------- head crown ---
HUB_CENTRE = (-0.008, 0.0, 1.605)
HUB_SEGMENTS = 14
# (z, half width in X, half depth up, half depth down, x offset, squareness)
HUB_RINGS = (
    (1.470, 0.038, 0.028, 0.026, -0.004, 0.95),
    (1.512, 0.070, 0.044, 0.040, -0.008, 0.90),
    (1.556, 0.092, 0.052, 0.048, -0.010, 0.85),
    (1.606, 0.105, 0.056, 0.052, -0.012, 0.82),
    (1.656, 0.097, 0.054, 0.050, -0.014, 0.82),
    (1.700, 0.077, 0.046, 0.042, -0.012, 0.85),
    (1.741, 0.047, 0.032, 0.030, -0.008, 0.90),
    (1.772, 0.020, 0.015, 0.014, -0.004, 0.95),
)
# 13 jagged spikes of deliberately uneven length, radiating from the hub.
# The blade root occupies roughly 155-205 degrees, so no spike is placed there.
# (angle from +X in the XZ plane, base z, length, r0, tangential bend deg, out-of-plane tilt)
CROWN_SPIKES = (
    (92.0, 1.660, 0.140, 0.0165, 14.0, 0.000),
    (75.0, 1.640, 0.1605, 0.0175, 10.0, -0.004),
    (55.0, 1.660, 0.150, 0.0150, -8.0, -0.008),
    (35.0, 1.680, 0.110, 0.0135, -12.0, -0.010),
    (15.0, 1.690, 0.080, 0.0118, -16.0, -0.008),
    (110.0, 1.640, 0.1885, 0.0160, 12.0, 0.006),
    (128.0, 1.660, 0.140, 0.0146, 9.0, 0.010),
    (145.0, 1.690, 0.090, 0.0130, 6.0, 0.008),
    (-18.0, 1.660, 0.079, 0.0126, -14.0, -0.006),
    (-42.0, 1.620, 0.101, 0.0134, -10.0, -0.004),
    (-72.0, 1.570, 0.126, 0.0146, -6.0, 0.004),
    (-104.0, 1.530, 0.093, 0.0128, 4.0, 0.006),
    (-134.0, 1.560, 0.061, 0.0110, 10.0, 0.004),
)
# The three tallest spikes are tuned to land exactly on HEIGHT_M (1.800 m), so
# the crown - not the blade, at 1.790 - is what sets the weapon's height, and
# the brief's "1.8 m" is a measurement rather than a rounding of whatever the
# spikes happened to add up to.
CROWN_TOP_BASES = (1.660, 1.640, 1.640)
CROWN_SPIKE_SEGMENTS = 7
CROWN_SPIKE_RINGS = 5
# Which spikes carry one of the small grey oval gems, and how far along.
CROWN_GEMS = ((1, 0.55), (2, 0.62), (5, 0.58), (6, 0.66), (8, 0.60), (9, 0.64))
CROWN_GEM_RADII = (0.0150, 0.0045, 0.0100)
CROWN_EYE_SOCKET = (-0.048, -0.048, 1.615)
CROWN_EYE_SOCKET_RADII = (0.036, 0.032, 0.036)

# ------------------------------------------------------------------ blade ---
BLADE_ROOT = (-0.062, 0.000, 1.612)
# The control point and the tip sit low enough that the crescent's own spine
# crests at ~1.79 m: the crown's spikes, at exactly 1.800, stay the highest
# thing on the weapon. Without this the blade's belly rose to 1.85 and the
# brief's "1.8 m" quietly stopped being true.
BLADE_TIP = (-0.905, -0.004, 1.720)
BLADE_CTRL = (-0.320, 0.000, 1.820)
BLADE_RINGS = 56
BLADE_W_MAX = 0.088                # half width at the base, before the swell
BLADE_SWELL = 0.95                 # how much wider the base third gets
BLADE_SWELL_T = 0.16
BLADE_SWELL_W = 0.15
BLADE_SPINE_FRACTION = 0.58        # of the half width, which side is the spine
BLADE_THICK = 0.0110               # at the root; thins toward the tip
BLADE_THICK_TAPER = 0.72
# The black spiked spine: (t along the blade, length, r0, flatness, back tilt deg)
BLADE_SPINE_SPIKES = (
    (0.045, 0.040, 0.0080, 0.32, 34.0),
    (0.098, 0.048, 0.0082, 0.30, 30.0),
    (0.152, 0.042, 0.0076, 0.30, 27.0),
    (0.230, 0.034, 0.0068, 0.34, 24.0),
    (0.320, 0.028, 0.0060, 0.36, 22.0),
    (0.420, 0.022, 0.0052, 0.38, 20.0),
    (0.535, 0.017, 0.0044, 0.40, 18.0),
    (0.660, 0.012, 0.0036, 0.42, 16.0),
    (0.790, 0.008, 0.0028, 0.45, 14.0),
)
BLADE_FIN_T = (0.030, 0.075, 0.118)     # the small fins near the base
BLADE_FIN_LEN = (0.052, 0.058, 0.046)
BLADE_FIN_R = 0.0088
BLADE_SPIKE_SEGMENTS = 6
BLADE_SPIKE_RINGS = 4

# ----------------------------------------------------------------- pommel ---
# Pointed shield cap. (z, half width X, half depth up, half depth down, sq)
POMMEL_RINGS = (
    (0.118, 0.024, 0.0150, 0.0150, 0.95),
    (0.100, 0.036, 0.0210, 0.0210, 0.90),
    (0.078, 0.045, 0.0260, 0.0260, 0.85),
    (0.052, 0.042, 0.0240, 0.0240, 0.85),
    (0.028, 0.030, 0.0180, 0.0180, 0.88),
    (0.011, 0.014, 0.0090, 0.0090, 0.92),
    (0.000, 0.0018, 0.0014, 0.0014, 0.95),
)
POMMEL_SEGMENTS = 12
POMMEL_SOCKET = (0.000, -0.018, 0.062)
POMMEL_SOCKET_RADII = (0.019, 0.010, 0.019)

# ------------------------------------------------------------------- eyes ---
# Two separate small meshes so Studio can make them Neon, exactly as the brief
# asks. They are not part of the joined body and carry no atlas.
EYE_HEAD_CENTRE = CROWN_EYE_SOCKET
EYE_HEAD_R = 0.0320
EYE_POMMEL_CENTRE = POMMEL_SOCKET
EYE_POMMEL_R = 0.0170
EYE_SEGMENTS = 16
EYE_RING_BANDS = 8                 # bands, so 16 x 8 quads -> 288 triangles
EYE_COLOUR = (0.85, 0.045, 0.030, 1.0)
PUPIL_HEAD_CENTRE = (-0.048, -0.0780, 1.615)
PUPIL_HEAD_RADII = (0.0055, 0.0035, 0.0195)
PUPIL_POMMEL_CENTRE = (0.000, -0.0340, 0.062)
PUPIL_POMMEL_RADII = (0.0034, 0.0024, 0.0106)
PUPIL_SEGMENTS = 8
PUPIL_RING_BANDS = 5
PUPIL_COLOUR = (0.006, 0.005, 0.006, 1.0)

# ======================================================= blade maths (pure) ===
# The blade's centreline, in-plane normal and width, as plain functions, so the
# loft, the spine spikes, the veins and the painter all read the same curve.
def blade_point(t):
    """Quadratic Bezier from the root to the tip, bowing up and to the right."""
    u = 1.0 - t
    a, b, c = BLADE_ROOT, BLADE_CTRL, BLADE_TIP
    return tuple(a[i] * u * u + b[i] * 2.0 * u * t + c[i] * t * t for i in range(3))


def blade_tangent(t):
    u = 1.0 - t
    a, b, c = BLADE_ROOT, BLADE_CTRL, BLADE_TIP
    v = tuple(2.0 * u * (b[i] - a[i]) + 2.0 * t * (c[i] - b[i]) for i in range(3))
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return tuple(x / n for x in v)


def blade_normal(t):
    """The in-plane normal pointing to the spine side (always the upper one)."""
    tx, _ty, tz = blade_tangent(t)
    nx, nz = -tz, tx
    n = math.sqrt(nx * nx + nz * nz) or 1.0
    nx, nz = nx / n, nz / n
    if nz < 0.0:
        nx, nz = -nx, -nz
    return (nx, 0.0, nz)


def blade_half_width(t):
    """Half width from the cutting edge to the spine: swollen near the base."""
    base = BLADE_W_MAX * (1.0 - t) ** 0.85
    swell = 1.0 + BLADE_SWELL * math.exp(-((t - BLADE_SWELL_T) / BLADE_SWELL_W) ** 2)
    return base * swell


def blade_spine_point(t, lift=0.0):
    p, n = blade_point(t), blade_normal(t)
    off = blade_half_width(t) * BLADE_SPINE_FRACTION + lift
    return (p[0] + n[0] * off, p[1] + n[1] * off, p[2] + n[2] * off)


def blade_edge_point(t):
    p, n = blade_point(t), blade_normal(t)
    off = blade_half_width(t) * (1.0 - BLADE_SPINE_FRACTION)
    return (p[0] - n[0] * off, p[1] - n[1] * off, p[2] - n[2] * off)


def blade_samples():
    """Loft samples: a wedge section, sharp at the edge and blunt at the spine.

    The tip keeps a ~1 mm section instead of collapsing to a point: a collapsed
    ring triangulates into zero-area triangles at the very tip, and those show
    up as degenerate faces in the export. A millimetre still reads as a point at
    this scale - the tip's own vertex sits on BLADE_TIP - but the mesh stays
    clean all the way out.
    """
    out = []
    for i in range(BLADE_RINGS):
        t = i / float(BLADE_RINGS - 1)
        hw = max(blade_half_width(t), 0.0008)
        hw_up = max(hw * BLADE_SPINE_FRACTION, 0.0005)
        hw_dn = max(hw * (1.0 - BLADE_SPINE_FRACTION), 0.0004)
        out.append({
            "t": t,
            "centre": blade_point(t),
            "normal": blade_normal(t),
            "w_edge": hw_dn,
            "w_spine": hw_up,
            "thick": BLADE_THICK * (1.0 - BLADE_THICK_TAPER * t) + 0.0004,
        })
    return out


# ==================================================== part surface helpers ===
# Where each part's front face (-Y) sits, so veins, gems and sockets can be
# parked ON the surface instead of floating near it.
def _interp_rings(rings, z):
    if z <= rings[0][0]:
        r = rings[0]
    elif z >= rings[-1][0]:
        r = rings[-1]
    else:
        r = rings[0]
        for i in range(len(rings) - 1):
            z0, z1 = rings[i][0], rings[i + 1][0]
            if z0 <= z <= z1:
                f = (z - z0) / (z1 - z0)
                r = tuple(rings[i][k] + (rings[i + 1][k] - rings[i][k]) * f
                          for k in range(len(rings[i])))
                break
    return r


def hub_ring_at(z):
    r = _interp_rings(HUB_RINGS, z)
    return {"w": r[1], "hu": r[2], "hd": r[3], "x": r[4], "sq": r[5]}


def _front_y(w, hu, sq, x, x_off=0.0, lift=0.0):
    """The -Y surface of a super-ellipse section at a given in-plane x."""
    u = min(abs((x - x_off) / max(w, 1e-9)), 1.0)
    v = max(0.0, 1.0 - u ** (2.0 / sq)) ** (sq * 0.5)
    return -(hu * v + lift)


def hub_front_y(x, z, lift=0.0):
    r = hub_ring_at(z)
    return _front_y(r["w"], r["hu"], r["sq"], x, r["x"], lift)


def pommel_ring_at(z):
    r = _interp_rings(POMMEL_RINGS, z)
    return {"w": r[1], "hu": r[2], "sq": r[4]}


def pommel_front_y(x, z, lift=0.0):
    r = pommel_ring_at(z)
    return _front_y(r["w"], r["hu"], r["sq"], x, 0.0, lift)


# ================================================================== veins ===
# ONE definition per vein, in world space. The same polylines build the raised
# crack ridges (so the normal map carries a real crack) and drive the paint and
# the emissive mask (so geometry and mask cannot drift apart). All of them are
# pure math, so they can be read without bpy.
def _shaft_veins():
    """Six thin red cracks wandering down the wood, following its twist."""
    out = []
    specs = ((0.06, 0.36, 0.0028), (0.40, 0.68, 0.0038), (0.28, 0.50, 0.0022),
             (0.60, 0.90, 0.0034), (0.72, 0.98, 0.0026), (0.12, 0.42, 0.0019))
    for start, end, r in specs:
        pts = []
        n = 15
        for i in range(n):
            f = i / float(n - 1)
            t = start + (end - start) * f
            a = shaft_twist(t) + 3.3 * f + 0.7
            pts.append(shaft_surface(t, a, lift=0.0011))
        out.append({"t": pts, "r": r})
    return out


def _crown_veins():
    """Channels radiating through the thorny crown, plus two rings at the eye."""
    out = []
    for ang in (20.0, 58.0, 96.0, 134.0, -24.0, -62.0, -100.0, -138.0):
        a = math.radians(ang)
        pts = []
        for k in range(9):
            s = 0.20 + 0.80 * k / 8.0
            rr = 0.026 + s * 0.100
            x = HUB_CENTRE[0] + rr * math.cos(a)
            z = HUB_CENTRE[2] + rr * math.sin(a) * 0.94
            pts.append((x, hub_front_y(x, z, lift=0.0013), z))
        out.append({"t": pts, "r": 0.0024})
    for rad, rr in ((0.046, 0.0019), (0.059, 0.0016)):
        pts = []
        for k in range(13):
            a = math.radians(-62.0 + 196.0 * k / 12.0)
            x = EYE_HEAD_CENTRE[0] + rad * math.cos(a)
            z = EYE_HEAD_CENTRE[2] + rad * 0.86 * math.sin(a)
            pts.append((x, hub_front_y(x, z, lift=0.0012), z))
        out.append({"t": pts, "r": rr})
    for ang in (12.0, 168.0):
        a = math.radians(ang)
        pts = []
        for k in range(8):
            s = k / 7.0
            rr = 0.030 + s * 0.085
            x = HUB_CENTRE[0] + rr * math.cos(a)
            z = HUB_CENTRE[2] + rr * math.sin(a) * 0.94
            pts.append((x, -hub_front_y(x, z, lift=0.0012), z))
        out.append({"t": pts, "r": 0.0020})
    return out


def _blade_veins():
    """Cracks that run along the spine and bleed into the blade."""
    out = []
    specs = ((0.02, 0.66, 0.86, 0.0100, 0.0028), (0.05, 0.50, 0.62, -0.0080, 0.0024),
             (0.02, 0.36, 0.36, 0.0120, 0.0021), (0.10, 0.74, 1.06, -0.0120, 0.0018),
             (0.20, 0.58, 1.26, 0.0090, 0.0015))
    for t0, t1, frac, wob, r in specs:
        pts = []
        n = 15
        for i in range(n):
            f = i / float(n - 1)
            t = t0 + (t1 - t0) * f
            p, normal, hw = blade_point(t), blade_normal(t), blade_half_width(t)
            off = hw * (BLADE_SPINE_FRACTION - frac * 0.85) + wob * math.sin(5.4 * f)
            pts.append((p[0] + normal[0] * off,
                        p[1] + 0.0014 * math.sin(3.1 * f),
                        p[2] + normal[2] * off))
        out.append({"t": pts, "r": r})
    return out


def _pommel_veins():
    out = []
    for rad, z, rr in ((0.021, 0.076, 0.0021),):
        pts = []
        # 12 points, not 13: this one closes on itself, and repeating the first
        # point at the end makes the ridge tube fold back onto its own start -
        # which remove_doubles then welds into a four-face pinch.
        for k in range(12):
            a = math.radians(360.0 * k / 12.0)
            x = rad * math.cos(a)
            zz = z + rad * 0.62 * math.sin(a)
            pts.append((x, pommel_front_y(x, zz, lift=0.0012), zz))
        out.append({"t": pts, "r": rr})
    for ang in (72.0, 108.0):
        a = math.radians(ang)
        pts = []
        for k in range(8):
            s = k / 7.0
            rr = 0.014 + s * 0.030
            x = rr * math.cos(a)
            z = 0.080 + s * 0.036
            pts.append((x, pommel_front_y(x, z, lift=0.0011), z))
        out.append({"t": pts, "r": 0.0017})
    return out


def _claw_veins():
    """Short cracks at the knuckles, where the bone meets the shaft."""
    out = []
    for ang in CLAW_KNUCKLES:
        a = math.radians(ang)
        base = shaft_surface(0.836, a, lift=0.014)
        pts = [base]
        for k in range(1, 6):
            s = k / 5.0
            pts.append((base[0] - 0.030 * s, base[1] + 0.020 * s * math.sin(a),
                        base[2] + 0.034 * s))
        out.append({"t": pts, "r": 0.0015})
    return out


def _tendril_veins():
    pts = tendril_points()
    radii = tendril_radii()
    return [{"t": [(p[0], p[1] - radii[i] * 0.85, p[2]) for i, p in enumerate(pts)],
             "r": 0.0014}]


VEINS = {
    "Scythe_Shaft": _shaft_veins(),
    "Scythe_HeadCrown": _crown_veins(),
    "Scythe_Blade": _blade_veins(),
    "Scythe_Pommel": _pommel_veins(),
    "Scythe_ClawGuard": _claw_veins(),
    "Scythe_TendrilHook": _tendril_veins(),
}
VEIN_RIDGE_GAIN = 1.25             # ridge tube radius = vein radius x this
VEIN_PAINT_SOFT = 0.0013           # the soft shoulder around a crack, in metres
# The first pass had a gain of 1.55 and a 3.2 mm shoulder, which turned hairline
# cracks into red pipes as thick as a fifth of the shaft.


def crown_spike_frame(idx):
    """(base, bend, tip, r0) of one crown spike, in world space.

    Shared by the builder, the gem placement and the paint rules, so a gem can
    never end up hovering next to its spike.
    """
    ang, base_z, length, r0, bend_deg, tilt = CROWN_SPIKES[idx]
    r = hub_ring_at(base_z)
    a = math.radians(ang)
    base = (HUB_CENTRE[0] + r["w"] * math.cos(a) * 0.94, 0.0, base_z)
    d = math.radians(bend_deg)
    dx, dz = math.cos(a + d), math.sin(a + d)
    tip = (base[0] + dx * length, tilt, base[2] + dz * length)
    bend = (base[0] + dx * length * 0.52, tilt * 0.55,
            base[2] + dz * length * 0.52 + 0.10 * length)
    return base, bend, tip, r0


def _spike_point(idx, frac):
    base, bend, tip, _r0 = crown_spike_frame(idx)
    u = 1.0 - frac
    return tuple(base[i] * u * u + bend[i] * 2.0 * u * frac + tip[i] * frac * frac
                 for i in range(3))


def blade_spine_polyline(n=21):
    return [blade_spine_point(i / float(n - 1)) for i in range(n)]


# ================================================================ palette ===
# Blender works in linear values; the Luau table carries the same colours
# converted to sRGB, exactly as the dragon project did it.
PALETTE = {
    "wood_brown": (0.064, 0.033, 0.021),
    "wood_dark": (0.020, 0.012, 0.009),
    "charred": (0.038, 0.026, 0.019),
    "crimson": (0.240, 0.014, 0.022),
    "crimson_deep": (0.090, 0.006, 0.010),
    "crimson_hot": (0.780, 0.048, 0.042),
    "steel": (0.520, 0.540, 0.560),
    "steel_bright": (0.800, 0.820, 0.850),
    "black": (0.012, 0.012, 0.014),
    "bone": (0.520, 0.480, 0.395),
    "bone_dark": (0.140, 0.124, 0.098),
    "gem_grey": (0.235, 0.240, 0.245),
}
BLACK = PALETTE["black"] + (1.0,)
CRIMSON_HOT = PALETTE["crimson_hot"] + (1.0,)


def _vein_rules(part, rough=0.28, emissive=1.0, extra=0.0012):
    """One paint rule per vein on that part: hot crimson, and it glows."""
    rules = []
    for v in VEINS[part]:
        rules.append({"kind": "polyline", "poly": v["t"],
                      "radius": v["r"] + extra, "soft": VEIN_PAINT_SOFT,
                      "colour": CRIMSON_HOT, "rough": rough, "metal": None,
                      "emissive": emissive, "no_ao": True})
    return rules


def _shaft_charred_bands():
    """Dark charring either side of each knot."""
    bands = []
    for t, _amp, _w in SHAFT_KNOTS:
        z0 = shaft_point(max(0.0, t - 0.055))[2]
        z1 = shaft_point(min(1.0, t + 0.055))[2]
        bands.append({"kind": "z_band", "z0": z0, "z1": z1, "soft": 0.012,
                      "colour": PALETTE["charred"] + (1.0,), "rough": 0.80,
                      "metal": None, "emissive": 0.0, "no_ao": False})
    return bands

# ================================================================== paint ===
# One recipe per part: the base and second colour the noise mixes between, the
# roughness and metalness the whole part starts from, and the ordered rules that
# override it. Rules apply in order, so a vein painted last wins over whatever
# was painted under it.
def _gem_rules():
    rules = []
    for idx, along in CROWN_GEMS:
        rules.append({"kind": "near_point", "point": _spike_point(idx, along),
                      "radius": CROWN_GEM_RADII[0] * 1.05, "soft": 0.0036,
                      "colour": PALETTE["gem_grey"] + (1.0,), "rough": 0.26,
                      "metal": 0.30, "emissive": 0.0, "no_ao": False})
    return rules


def _socket_rule(centre, radius):
    """The recess the eye sits in: dark, faintly lit, kept out of the AO."""
    return {"kind": "near_point", "point": tuple(centre), "radius": radius,
            "soft": 0.006, "colour": PALETTE["crimson_deep"] + (1.0,),
            "rough": 0.35, "metal": None, "emissive": 0.35, "no_ao": True}


_SPINE_RULE = {"kind": "polyline", "poly": blade_spine_polyline(), "radius": 0.018,
               "soft": 0.008, "colour": BLACK, "rough": 0.55, "metal": 0.22,
               "emissive": 0.0, "no_ao": False}

PAINT = {
    "Scythe_Shaft": {
        "base": PALETTE["wood_brown"] + (1.0,), "second": PALETTE["wood_dark"] + (1.0,),
        "rough": 0.74, "metal": 0.02, "wear": 0.30, "noise": 26.0,
        "rules": _shaft_charred_bands() + _vein_rules("Scythe_Shaft"),
    },
    "Scythe_HeadCrown": {
        "base": BLACK, "second": PALETTE["wood_dark"] + (1.0,),
        "rough": 0.52, "metal": 0.10, "wear": 0.35, "noise": 22.0,
        "rules": (_gem_rules()
                  + [_socket_rule(CROWN_EYE_SOCKET, 0.046)]
                  + _vein_rules("Scythe_HeadCrown")),
    },
    "Scythe_Blade": {
        "base": PALETTE["steel"] + (1.0,), "second": PALETTE["steel_bright"] + (1.0,),
        "rough": 0.34, "metal": 0.75, "wear": 0.85, "noise": 14.0,
        "rules": [_SPINE_RULE] + _vein_rules("Scythe_Blade", rough=0.26),
    },
    "Scythe_ClawGuard": {
        "base": PALETTE["bone"] + (1.0,), "second": PALETTE["bone_dark"] + (1.0,),
        "rough": 0.58, "metal": 0.0, "wear": 0.45, "noise": 20.0,
        "rules": _vein_rules("Scythe_ClawGuard", emissive=0.65),
    },
    "Scythe_Pommel": {
        "base": BLACK, "second": PALETTE["wood_dark"] + (1.0,),
        "rough": 0.52, "metal": 0.14, "wear": 0.40, "noise": 24.0,
        "rules": [_socket_rule(POMMEL_SOCKET, 0.026)] + _vein_rules("Scythe_Pommel"),
    },
    "Scythe_TendrilHook": {
        "base": BLACK, "second": PALETTE["crimson_deep"] + (1.0,),
        "rough": 0.50, "metal": 0.10, "wear": 0.30, "noise": 18.0,
        "rules": _vein_rules("Scythe_TendrilHook", emissive=0.8),
    },
}
ANCHOR_COLOUR = PALETTE["wood_dark"] + (1.0,)   # unpainted atlas background

# ================================================================ textures ===
TEXTURE_SET_NAME = "Scythe"
TEXTURE_SIZE = 1024
TEXTURE_FOLDER = "ScytheTextures_1024"
TEXTURE_PAD_PX = 8
# The five maps Studio reads, then the two support maps that only the .blend and
# the painter use. Roblox has no ambient-occlusion slot, so AO is multiplied
# into the ColorMap instead - and never over the glowing veins.
TEXTURE_ROLES = ("ColorMap", "NormalMap", "RoughnessMap", "MetalnessMap",
                 "EmissiveMask")
SUPPORT_ROLES = ("AO", "Curvature")
MAP_FILES = {role: "%s_%s.png" % (TEXTURE_SET_NAME, role)
             for role in TEXTURE_ROLES + SUPPORT_ROLES}

# ================================================================== export ===
EXPORT = {
    "name": FBX_NAME,
    "axis_forward": "-Z",
    "axis_up": "Y",
    "apply_unit_scale": True,
    "apply_scale_options": "FBX_SCALE_UNITS",   # the cottage's measured setting
    "global_scale": 1.0,
    "bake_space_transform": False,
    "object_types": {"MESH", "EMPTY"},
    "mesh_smooth_type": "FACE",
}

# ================================================================ previews ===
PREVIEW_RESOLUTION = (720, 1080)
PREVIEW_SAMPLES = 48
VIEWS = {
    "front": {"loc": (0.10, -3.10, 0.95), "target": (-0.17, 0.0, 0.92), "lens": 50.0},
    "side": {"loc": (-3.10, 0.05, 0.95), "target": (-0.17, 0.0, 0.92), "lens": 50.0},
    "three_quarter": {"loc": (-2.15, -2.25, 1.30), "target": (-0.17, 0.0, 0.95),
                      "lens": 55.0},
    "head": {"loc": (-0.55, -0.82, 1.72), "target": (-0.16, 0.0, 1.62), "lens": 60.0},
    "blade": {"loc": (-0.72, -1.05, 2.02), "target": (-0.48, 0.0, 1.72), "lens": 55.0},
    "pommel": {"loc": (0.05, -0.62, 0.16), "target": (0.0, 0.0, 0.06), "lens": 55.0},
    "eye": {"loc": (-0.10, -0.36, 1.64), "target": (-0.048, -0.04, 1.614), "lens": 90.0},
}
# A small three-point rig. Kept modest on purpose: point lights at 900 W blew
# the charred wood out to pale beige in the first preview pass.
LIGHTS = (
    ("key", (1.6, -2.4, 2.6), 220.0, (1.0, 0.95, 0.90)),
    ("fill", (-2.4, -1.5, 1.2), 90.0, (0.86, 0.90, 1.0)),
    ("rim", (0.4, 2.6, 2.2), 140.0, (1.0, 0.82, 0.80)),
)

# What Studio is told to start from, so the preview, the Luau and the README all
# quote the same two numbers.
EMISSIVE_TINT_SRGB = (190, 20, 32)
EMISSIVE_TINT_LINEAR = (0.512, 0.0075, 0.0144, 1.0)
EMISSIVE_STRENGTH = 4.0

# ================================================================== sanity ===
def sanity():
    """Cross-checks that must hold before a single triangle is built."""
    problems = []
    if len(set(BODY_PARTS)) != len(BODY_PARTS):
        problems.append("duplicate body part name")
    for part in BODY_PARTS + EYE_PARTS + PUPIL_PARTS:
        if part not in BUDGETS:
            problems.append("no budget for %s" % part)
    for part in BODY_PARTS:
        if part not in PAINT:
            problems.append("no paint recipe for %s" % part)
        if not VEINS.get(part):
            problems.append("no veins for %s" % part)
    if budget_total() > TRI_TARGET_TOTAL:
        problems.append("budgets sum to %d, over the %d target"
                        % (budget_total(), TRI_TARGET_TOTAL))
    if not (0.0 < GRIP[2] < HEIGHT_M):
        problems.append("grip point outside the weapon")
    if blade_half_width(1.0) > 1e-6:
        problems.append("blade tip is not a point")
    if blade_half_width(0.16) <= blade_half_width(0.60):
        problems.append("blade does not swell near its base")
    if not (10 <= len(CROWN_SPIKES) <= 14):
        problems.append("crown spike count %d outside 10-14" % len(CROWN_SPIKES))
    if len({s[2] for s in CROWN_SPIKES}) < 6:
        problems.append("crown spike lengths are not varied")
    for part, veins in VEINS.items():
        for v in veins:
            if len(v["t"]) < 2:
                problems.append("%s has a degenerate vein" % part)
    return problems


def budget_total():
    return sum(BUDGETS[p] for p in BODY_PARTS + EYE_PARTS + PUPIL_PARTS)
# CHUNK_END
