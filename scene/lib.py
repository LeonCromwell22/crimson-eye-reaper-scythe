"""bpy-side helpers for the scythe build.

House rules, so the stages stay small and the failure surface stays obvious:

* Every mesh is built in WORLD coordinates with an identity object transform,
  then set_origin() moves each object's origin onto its joint while the world
  geometry stays put. Nothing is authored in local space.
* bpy.ops is used only where there is no data-level alternative (Smart UV
  Project, curve conversion, bake). Modifier application goes through the
  depsgraph, which cannot fail on context.
* Anything that can be measured is measured and printed, never assumed.
"""
import bmesh
import bpy
import json
import math
import os
from mathutils import Matrix, Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # project root


# ------------------------------------------------------------ collections ---
def collection(name):
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(coll)
    return coll


def ensure_collections(names):
    return [collection(n).name for n in names]


def move_to_collection(obj, coll_name):
    """Unlink from wherever it is and put it in exactly one collection."""
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    collection(coll_name).objects.link(obj)
    return obj


def drop_collection(name, delete_objects=True):
    coll = bpy.data.collections.get(name)
    if coll is None:
        return 0
    n = len(coll.objects)
    if delete_objects:
        for obj in list(coll.objects):
            remove_object(obj)
    bpy.data.collections.remove(coll)
    return n


# ---------------------------------------------------------------- objects ---
def new_object(name, coll_name, verts, faces):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.validate(verbose=False)
    me.update()
    obj = bpy.data.objects.new(name, me)
    collection(coll_name).objects.link(obj)
    return obj


def remove_object(obj):
    """Delete an object, and its mesh datablock if nothing else uses it."""
    data = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if isinstance(data, bpy.types.Mesh) and data.users == 0:
        bpy.data.meshes.remove(data)


def remove_objects(names_or_prefixes):
    gone = []
    for obj in list(bpy.data.objects):
        for key in names_or_prefixes:
            if obj.name == key or obj.name.startswith(key):
                gone.append(obj.name)
                remove_object(obj)
                break
    return gone


def get(name):
    return bpy.data.objects.get(name)


def join(objs, name, coll):
    """Merge meshes into one object, baking each source's transform in.

    bmesh has no matrix argument for from_mesh, and every part in this build
    keeps its origin parked on the grip with the geometry shifted to match.
    Joining the raw mesh data therefore drops that shift and lands the whole
    weapon a grip-point lower - which is exactly what happened, and exactly the
    kind of error that a size-only gate cannot see.
    """
    bm = bmesh.new()
    for obj in objs:
        me = obj.data.copy()
        me.transform(obj.matrix_world)
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for obj in list(objs):
        remove_object(obj)
    new = bpy.data.objects.new(name, me)
    collection(coll).objects.link(new)
    return new

# ------------------------------------------------------------- primitives ---
def box(name, coll, xr, yr, zr):
    """Axis-aligned box from three (min, max) ranges; windings face outward."""
    x0, x1 = xr
    y0, y1 = yr
    z0, z1 = zr
    verts = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
             (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return new_object(name, coll, verts, faces)


def slab(name, coll, centre, size, ax=(1.0, 0.0, 0.0), ay=(0.0, 1.0, 0.0),
         az=(0.0, 0.0, 1.0)):
    """Box in an arbitrary orthonormal frame (plates, fins, barbs)."""
    ax = Vector(ax).normalized()
    ay = Vector(ay).normalized()
    az = Vector(az).normalized()
    c = Vector(centre)
    hx, hy, hz = size[0] / 2.0, size[1] / 2.0, size[2] / 2.0
    signs = ((-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
             (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1))
    verts = [tuple(c + ax * (sx * hx) + ay * (sy * hy) + az * (sz * hz))
             for (sx, sy, sz) in signs]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return new_object(name, coll, verts, faces)


def profile_ring(segments, w, hu, hd, sq=1.0, rot=0.0):
    """Unit ring in (u, v): a super-ellipse with independent up/down radii.

    sq < 1 squares the section off, which is what keeps a twisted wooden shaft
    from reading as a smooth sausage.
    """
    pts = []
    for k in range(segments):
        a = rot + 2.0 * math.pi * k / segments
        c, s = math.cos(a), math.sin(a)
        u = math.copysign(abs(c) ** sq, c) if c else 0.0
        v = math.copysign(abs(s) ** sq, s) if s else 0.0
        pts.append((w * u, hu * v if v >= 0 else hd * v))
    return pts


def _frames(points, up=(0.0, 0.0, 1.0)):
    """Tangent/side/up frame per point, from neighbouring points."""
    pts = [Vector(p) for p in points]
    n = len(pts)
    u0 = Vector(up)
    frames = []
    for i in range(n):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == n - 1:
            t = pts[-1] - pts[-2]
        else:
            t = pts[i + 1] - pts[i - 1]
        if t.length < 1e-9:
            t = Vector((0.0, 0.0, 1.0))
        t = t.normalized()
        u = u0 if abs(t.dot(u0)) <= 0.999 else Vector((0.0, 1.0, 0.0))
        if abs(t.dot(u)) > 0.999:
            u = Vector((1.0, 0.0, 0.0))
        side = t.cross(u).normalized()
        real_up = side.cross(t).normalized()
        frames.append((side, real_up, t))
    return frames


def tube(name, coll, samples, segments=8, up=(0.0, 0.0, 1.0), caps=True):
    """Loft closed rings along a path. samples are dicts:
    {centre, w, hu, hd, sq, rot}. Produces quads plus triangle-fan caps."""
    pts = [s["centre"] for s in samples]
    frames = _frames(pts, up)
    verts = []
    rings = []
    for i, s in enumerate(samples):
        side, real_up, _t = frames[i]
        centre = Vector(s["centre"])
        profile = profile_ring(segments, s.get("w", 0.1), s.get("hu", 0.1),
                               s.get("hd", s.get("hu", 0.1)), s.get("sq", 1.0),
                               s.get("rot", 0.0))
        idx = []
        for (u, v) in profile:
            verts.append(tuple(centre + side * u + real_up * v))
            idx.append(len(verts) - 1)
        rings.append(idx)
    faces = []
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        for k in range(segments):
            k2 = (k + 1) % segments
            faces.append((a[k], a[k2], b[k2], b[k]))
    if caps:
        for ring, centre in ((rings[0], pts[0]), (rings[-1], pts[-1])):
            verts.append(tuple(Vector(centre)))
            c = len(verts) - 1
            for k in range(segments):
                k2 = (k + 1) % segments
                faces.append((c, ring[k], ring[k2]))
    return new_object(name, coll, verts, faces)

def spike(name, coll, base, tip, r0, r1=None, segments=6, ring_count=4,
          bend=None, flat=1.0, sq=0.9, up=(0.0, 0.0, 1.0)):
    """Curved tapered cone: crown thorns, talons, spine barbs, blade fins.

    `bend` is an optional quadratic control point, so a thorn curls instead of
    being a straight cone. `flat` squashes the section sideways, which is what
    turns the same helper into a flat fin.
    """
    if r1 is None:
        r1 = max(r0 * 0.05, 0.0015)
    base, tip = Vector(base), Vector(tip)
    samples = []
    for i in range(ring_count + 1):
        t = i / float(ring_count)
        if bend is None:
            p = base.lerp(tip, t)
        else:
            u = 1.0 - t
            p = base * (u * u) + Vector(bend) * (2.0 * u * t) + tip * (t * t)
        r = r0 + (r1 - r0) * (t ** 0.75)
        samples.append({"centre": tuple(p), "w": r * flat, "hu": r,
                        "hd": r, "sq": sq})
    return tube(name, coll, samples, segments=segments, up=up, caps=True)


def ellipsoid(name, coll, centre, radii, segments=12, bands=8, axis="z"):
    """UV sphere with per-axis radii; poles on the named axis."""
    cx, cy, cz = centre
    rx, ry, rz = radii
    verts = []
    faces = []
    rings = []
    for j in range(1, bands):
        phi = math.pi * j / bands
        sin_p, cos_p = math.sin(phi), math.cos(phi)
        idx = []
        for k in range(segments):
            theta = 2.0 * math.pi * k / segments
            src = (sin_p * math.cos(theta), sin_p * math.sin(theta), cos_p)
            if axis == "z":
                p = (cx + rx * src[0], cy + ry * src[1], cz + rz * src[2])
            elif axis == "y":
                p = (cx + rx * src[0], cy + ry * src[2], cz + rz * src[1])
            else:
                p = (cx + rx * src[2], cy + ry * src[0], cz + rz * src[1])
            verts.append(p)
            idx.append(len(verts) - 1)
        rings.append(idx)
    for j in range(len(rings) - 1):
        a, b = rings[j], rings[j + 1]
        for k in range(segments):
            k2 = (k + 1) % segments
            faces.append((a[k], a[k2], b[k2], b[k]))
    ends = ((0.0, 0.0, 1.0), (0.0, 0.0, -1.0))
    for which, src in ((0, ends[0]), (1, ends[1])):
        if axis == "z":
            pole = (cx + rx * src[0], cy + ry * src[1], cz + rz * src[2])
        elif axis == "y":
            pole = (cx + rx * src[0], cy + ry * src[2], cz + rz * src[1])
        else:
            pole = (cx + rx * src[2], cy + ry * src[0], cz + rz * src[1])
        verts.append(pole)
        c = len(verts) - 1
        ring = rings[0] if which == 0 else rings[-1]
        for k in range(segments):
            k2 = (k + 1) % segments
            if which == 0:
                faces.append((c, ring[k2], ring[k]))
            else:
                faces.append((c, ring[k], ring[k2]))
    return new_object(name, coll, verts, faces)

# The blade section, as (u, v): u = -1 is the razor edge, u = +1 the blunt
# spine, v = +/-1 the two faces. Asymmetric on purpose - that asymmetry is what
# makes a blade read as a blade rather than as a flattened tube.
BLADE_SECTION = (
    (-1.00, 0.00),
    (-0.34, 0.80),
    (0.30, 1.00),
    (1.00, 0.58),
    (1.00, -0.58),
    (0.30, -1.00),
    (-0.34, -0.80),
)


def wedge_loft(name, coll, samples, section=BLADE_SECTION):
    """Loft a wedge section along samples carrying centre, normal, w_edge,
    w_spine and thick.

    `normal` is the in-plane spine direction; the section's other axis comes out
    of that plane, forced to the +Y side so the blade stays consistently
    orientated the whole way along its sweep.
    """
    pts = [s["centre"] for s in samples]
    frames = _frames(pts, (0.0, 1.0, 0.0))
    n = len(section)
    verts = []
    rings = []
    for i, s in enumerate(samples):
        centre = Vector(s["centre"])
        up = Vector(s["normal"]).normalized()
        tangent = frames[i][2]
        out = tangent.cross(up).normalized()
        if out.y < 0.0:
            out = -out
        ring = []
        for (u, v) in section:
            w = s["w_edge"] if u < 0.0 else s["w_spine"]
            p = centre + up * (u * w) + out * (v * s["thick"])
            verts.append(tuple(p))
            ring.append(len(verts) - 1)
        rings.append(ring)
    faces = []
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        for k in range(n):
            k2 = (k + 1) % n
            faces.append((a[k], a[k2], b[k2], b[k]))
    for ring, centre in ((rings[0], pts[0]), (rings[-1], pts[-1])):
        verts.append(tuple(Vector(centre)))
        c = len(verts) - 1
        for k in range(n):
            k2 = (k + 1) % n
            faces.append((c, ring[k], ring[k2]))
    return new_object(name, coll, verts, faces)


def ridge_tube(name, coll, points, radius, segments=5, up=(0.0, 0.0, 1.0)):
    """A thin tube following a polyline: the raised crack ridges.

    Accepts one radius or one per point, so a crack can taper away to nothing.
    """
    radii = radius if isinstance(radius, (list, tuple)) else [radius] * len(points)
    samples = [{"centre": tuple(points[i]), "w": radii[i], "hu": radii[i],
                "hd": radii[i], "sq": 0.85} for i in range(len(points))]
    return tube(name, coll, samples, segments=segments, up=up, caps=True)


def curve_tube(name, coll, points, radii, bevel_resolution=2, resolution=6):
    """Bezier curve with a bevel and per-point radii, converted to a mesh."""
    cu = bpy.data.curves.new(name + "_curve", type="CURVE")
    cu.dimensions = "3D"
    cu.resolution_u = resolution
    cu.bevel_depth = max(radii)
    cu.bevel_resolution = bevel_resolution
    cu.use_fill_caps = True
    spline = cu.splines.new("BEZIER")
    spline.bezier_points.add(len(points) - 1)
    for i, (p, r) in enumerate(zip(points, radii)):
        bp = spline.bezier_points[i]
        bp.co = Vector(p)
        bp.handle_left_type = "AUTO"
        bp.handle_right_type = "AUTO"
        bp.radius = r / max(radii)
    holder = bpy.data.objects.new(name + "_CURVE", cu)
    collection(coll).objects.link(holder)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(holder.evaluated_get(dg))
    me.name = name
    obj = bpy.data.objects.new(name, me)
    collection(coll).objects.link(obj)
    remove_object(holder)
    bpy.data.curves.remove(cu)
    return obj

# ----------------------------------------------------------- geometry ops ---
def recalc_normals(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return len(obj.data.polygons)


def clean_mesh(obj, merge=0.0001, triangulate=True):
    """Merge doubles, drop degenerate/loose geometry, fix normals, triangulate."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    before = (len(bm.verts), len(bm.faces))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=bm.edges)
    loose_e = [e for e in bm.edges if not e.link_faces]
    if loose_e:
        bmesh.ops.delete(bm, geom=loose_e, context="EDGES")
    loose_v = [v for v in bm.verts if not v.link_faces]
    if loose_v:
        bmesh.ops.delete(bm, geom=loose_v, context="VERTS")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if triangulate:
        bmesh.ops.triangulate(bm, faces=bm.faces,
                              quad_method="BEAUTY", ngon_method="BEAUTY")
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return before


def _shells(bm):
    """Connected face islands. Used to orient each shell on its own volume."""
    seen = set()
    out = []
    for face in bm.faces:
        if face in seen:
            continue
        stack = [face]
        comp = []
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            comp.append(cur)
            for edge in cur.edges:
                for nxt in edge.link_faces:
                    if nxt not in seen:
                        stack.append(nxt)
        out.append(comp)
    return out


def _signed_volume(faces):
    """Divergence theorem: r.n integrated over a closed surface is 3V."""
    vol = 0.0
    for f in faces:
        area = f.calc_area()
        if area > 1e-12 and f.normal.length_squared > 1e-12:
            vol += area * f.normal.dot(f.calc_center_median())
    return vol / 3.0


def orient_outward(obj):
    """Flip any shell whose own signed volume is negative.

    recalc_face_normals is consistent *per shell* but not guaranteed outward on
    geometry that self-intersects, so each shell is measured and corrected
    separately rather than trusting one recalc for the whole object.
    """
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    flipped = 0
    for comp in _shells(bm):
        if _signed_volume(comp) < 0.0:
            bmesh.ops.reverse_faces(bm, faces=comp)
            flipped += 1
    bm.normal_update()
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return flipped

def dent_surface(obj, centre, radius, depth, plane=("x", "z"), axis="y"):
    """Press a smooth recess into a surface, without touching the topology.

    This replaced a boolean cutter for the two eye sockets. A boolean is the
    obvious tool, but both solvers left a non-manifold edge where the rim met
    the shell - and a sliver that only becomes non-manifold once remove_doubles
    welds it is precisely the kind of defect that hides from a spot check. A
    dent cannot do that: the vertex count, the shells and the winding are all
    untouched, and the depth is measurable against the surface it came from.
    """
    a, b = plane
    idx = {"x": 0, "y": 1, "z": 2}
    ca, cb = centre[idx[a]], centre[idx[b]]
    axis_i = idx[axis]
    sign = -1.0 if centre[axis_i] < 0.0 else 1.0   # push back the way it came
    moved = 0
    deepest = 0.0
    for v in obj.data.vertices:
        da = v.co[idx[a]] - ca
        db = v.co[idx[b]] - cb
        d = math.sqrt(da * da + db * db)
        if d >= radius:
            continue
        falloff = (1.0 - (d / radius) ** 2) ** 2
        v.co[axis_i] += sign * depth * falloff
        deepest = max(deepest, depth * falloff)
        moved += 1
    obj.data.update()
    return {"vertices_moved": moved, "deepest_recess_m": round(deepest, 6)}


def apply_modifiers(obj):
    """Bake every modifier into the mesh through the depsgraph.

    Avoids bpy.ops.object.modifier_apply, which needs a very specific context
    and fails silently in some session states.
    """
    if not obj.modifiers:
        return 0
    n = len(obj.modifiers)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
    old = obj.data
    obj.modifiers.clear()
    obj.data = me
    me.name = old.name
    if old.users == 0:
        bpy.data.meshes.remove(old)
    bpy.context.view_layer.update()
    return n


def add_subsurf(obj, levels=1):
    mod = obj.modifiers.new("subdiv", "SUBSURF")
    mod.levels = levels
    mod.render_levels = levels
    return mod


def add_bevel(obj, width=0.02, segments=2, limit_angle=40.0):
    mod = obj.modifiers.new("bevel", "BEVEL")
    mod.width = width
    mod.segments = segments
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(limit_angle)
    return mod


def add_decimate(obj, ratio):
    mod = obj.modifiers.new("decimate", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = max(0.01, min(1.0, ratio))
    return mod


def add_displace(obj, texture, strength=0.01, mid_level=0.5):
    mod = obj.modifiers.new("displace", "DISPLACE")
    mod.texture = texture
    mod.strength = strength
    mod.mid_level = mid_level
    return mod


def decimate_to(obj, target_tris, max_passes=4, floor=0.05):
    """Apply collapse decimates until the object is under target_tris.

    Decimate's ratio is a ratio of faces, not of triangles, so this measures and
    corrects rather than assuming one pass lands on the number.
    """
    applied = 0
    for _ in range(max_passes):
        cur = stats(obj)["tris"]
        if cur <= target_tris:
            break
        ratio = max(floor, (target_tris / float(cur)) * 0.98) if cur else 1.0
        add_decimate(obj, ratio)
        apply_modifiers(obj)
        applied += 1
    return {"passes": applied, "tris": stats(obj)["tris"], "target": target_tris}


def purge_orphans():
    """Drop unused datablocks left behind by deletions."""
    n = 0
    for bucket in (bpy.data.meshes, bpy.data.materials, bpy.data.curves,
                   bpy.data.cameras, bpy.data.lights, bpy.data.images,
                   bpy.data.textures):
        for block in list(bucket):
            if block.users == 0 and not block.use_fake_user:
                bucket.remove(block)
                n += 1
    return n

# ---------------------------------------------------- origins / measuring ---
def set_origin(obj, joint):
    """Move the object's origin onto `joint` without moving the geometry.

    This is the one deliberate deviation from "apply all transforms": rotation
    and scale are baked to identity, but the translation is kept, because the
    origin is what Roblox rotates the part about - and here it is the grip.
    """
    j = Vector(joint)
    obj.data.transform(Matrix.Translation(-j))
    obj.data.update()
    obj.location = j
    return [round(v, 4) for v in obj.location]


def stats(obj):
    """Measure one object: tris, face mix, loose and non-manifold geometry."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    me.calc_loop_triangles()
    out = {
        "tris": len(me.loop_triangles),
        "verts": len(me.vertices),
        "faces": len(me.polygons),
        "quads": sum(1 for p in me.polygons if len(p.vertices) == 4),
        "tris_faces": sum(1 for p in me.polygons if len(p.vertices) == 3),
        "ngons": sum(1 for p in me.polygons if len(p.vertices) > 4),
        "degenerate": sum(1 for p in me.polygons if p.area < 1e-9),
    }
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.normal_update()
    out["loose_verts"] = sum(1 for v in bm.verts if not v.link_faces)
    out["loose_edges"] = sum(1 for e in bm.edges if not e.link_faces)
    out["nonmanifold_edges"] = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    out["shells"] = len(_shells(bm))
    # 9 decimals, not 6: the two pupil shells are a few hundred cubic
    # micrometres, and a value that rounds to 0.0 would fail "every shell faces
    # outward" for a mesh that is in fact perfectly fine.
    out["signed_volume"] = round(sum(_signed_volume(c) for c in _shells(bm)), 9)
    bm.free()
    ev.to_mesh_clear()
    return out


def bounds(obj):
    """World-space (min, max) bounding box of the evaluated mesh."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    if not len(me.vertices):
        ev.to_mesh_clear()
        return None
    pts = [obj.matrix_world @ v.co for v in me.vertices]
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    ev.to_mesh_clear()
    return ([round(v, 4) for v in lo], [round(v, 4) for v in hi])


def mesh_objects():
    return sorted((o for o in bpy.data.objects if o.type == "MESH"),
                  key=lambda o: o.name)


def is_temp(obj):
    """True for build scaffolding, which never counts towards anything."""
    return any(c.name.startswith("TEMP_") for c in obj.users_collection)


def scene_bounds(names=None, include_temp=False):
    pool = [o for o in mesh_objects() if names is None or o.name in names]
    if not include_temp:
        pool = [o for o in pool if not is_temp(o)]
    boxes = [b for b in (bounds(o) for o in pool) if b]
    if not boxes:
        return None
    lo = [min(b[0][i] for b in boxes) for i in range(3)]
    hi = [max(b[1][i] for b in boxes) for i in range(3)]
    return ([round(v, 4) for v in lo], [round(v, 4) for v in hi])


def extremes(names):
    """Which object owns each axis extreme - so a bad number has a name."""
    table = {}
    for name in names:
        o = get(name)
        if o is None:
            continue
        b = bounds(o)
        if b:
            table[name] = b
    out = {}
    for axis, tag in ((0, "x"), (1, "y"), (2, "z")):
        if not table:
            continue
        lo_name = min(table, key=lambda n: table[n][0][axis])
        hi_name = max(table, key=lambda n: table[n][1][axis])
        out["min_" + tag] = [lo_name, table[lo_name][0][axis]]
        out["max_" + tag] = [hi_name, table[hi_name][1][axis]]
    return out


def max_vertex_distance(obj, point):
    """Furthest a vertex sits from a point, in world space."""
    p = Vector(point)
    return max(((obj.matrix_world @ v.co) - p).length for v in obj.data.vertices)


def nearest_surface_distance(obj, point):
    """Closest distance from a point to the object's vertices."""
    p = Vector(point)
    return min(((obj.matrix_world @ v.co) - p).length for v in obj.data.vertices)

# ------------------------------------------------------------------- uv -----
def uv_smart(obj, margin=0.02):
    """Smart UV Project for one object; falls back to a planar projection."""
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    try:
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(66.0),
                                 island_margin=margin)
        bpy.ops.object.mode_set(mode="OBJECT")
        obj.select_set(False)
        return "smart_project"
    except Exception as exc:
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
            pass
        obj.select_set(False)
        _uv_planar(obj)
        return "planar_fallback:%s" % exc.__class__.__name__


def _uv_planar(obj):
    """Per-face projection on each face's dominant axis, normalised to 0..1."""
    me = obj.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uv = me.uv_layers.active.data
    verts = [v.co for v in me.vertices]
    groups = {}
    for poly in me.polygons:
        axis = max(range(3), key=lambda i: abs(poly.normal[i]))
        groups.setdefault(axis, []).append(poly)
    for axis, polys in groups.items():
        axes = [i for i in range(3) if i != axis]
        pts = [verts[i] for p in polys for i in p.vertices]
        if not pts:
            continue
        us = [p[axes[0]] for p in pts]
        vs = [p[axes[1]] for p in pts]
        du = (max(us) - min(us)) or 1.0
        dv = (max(vs) - min(vs)) or 1.0
        for p in polys:
            for li in p.loop_indices:
                co = verts[me.loops[li].vertex_index]
                uv[li].uv = ((co[axes[0]] - min(us)) / du,
                             (co[axes[1]] - min(vs)) / dv)


def uv_bounds(obj):
    me = obj.data
    if not me.uv_layers or not len(me.uv_layers.active.data):
        return None
    us = [d.uv[0] for d in me.uv_layers.active.data]
    vs = [d.uv[1] for d in me.uv_layers.active.data]
    return [round(min(us), 4), round(max(us), 4),
            round(min(vs), 4), round(max(vs), 4)]


# ------------------------------------------------------------ tile packing ---
def _pack_once(weights, padding, gap, factor):
    """One shelf packing pass at a given size factor. Returns (rects, fits)."""
    total = sum(weights.values()) or 1.0
    usable = (1.0 - 2.0 * padding) * factor
    rects, x, y, shelf_h, fits = {}, padding, padding, 0.0, True
    for name, weight in sorted(weights.items(), key=lambda kv: -kv[1]):
        side = max(math.sqrt(max(weight / total, 1e-9)) * usable, 0.02)
        if x + side > 1.0 - padding + 1e-9:
            x = padding
            y += shelf_h + gap
            shelf_h = 0.0
        if y + side > 1.0 - padding + 1e-9:
            fits = False
        rects[name] = (round(x, 6), round(y, 6), round(side, 6))
        x += side + gap
        shelf_h = max(shelf_h, side)
    return rects, fits


def shelf_pack(weights, padding, gap, tries=40):
    """Allocate every part a rectangle inside the 0..1 atlas, fitted.

    A shelf packer, biggest first, with a binary search on the global size
    factor: shelves waste space (a row is as tall as its tallest tile), so one
    area-proportional pass overflows the atlas. The search finds the largest
    scale at which every tile still lands inside - which is what makes "one
    atlas for the whole weapon" fit without silently dropping detail.
    """
    lo, hi, best = 0.02, 1.0, None
    for _ in range(tries):
        mid = (lo + hi) * 0.5
        rects, fits = _pack_once(weights, padding, gap, mid)
        if fits:
            best, lo = rects, mid
        else:
            hi = mid
    if best is None:
        best, _fits = _pack_once(weights, padding, gap, 0.02)
    return best

# -------------------------------------------------------------- materials ---
def make_material(name, rgba, emission=None, roughness=0.75):
    """A flat Principled material, for the Neon eyes and for previews."""
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = rgba
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = roughness
        if emission is not None:
            if "Emission Color" in bsdf.inputs:
                bsdf.inputs["Emission Color"].default_value = rgba
            if "Emission Strength" in bsdf.inputs:
                bsdf.inputs["Emission Strength"].default_value = emission
    mat.diffuse_color = rgba          # what MATERIAL viewport shading shows
    return mat


def assign_material(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return mat


def make_pbr_material(name, images, emission_strength=1.0,
                      emission_tint=(1.0, 0.09, 0.07, 1.0)):
    """The deliverable material: the five maps wired into one Principled BSDF.

    Roblox reads the maps through SurfaceAppearance; inside Blender this is the
    same five textures, so a preview render and Studio agree about what is on
    the model instead of nearly agreeing.
    """
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    def _tex(role):
        img = images.get(role)
        if img is None:
            return None
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = img
        node.interpolation = "Smart"
        return node

    col = _tex("ColorMap")
    if col is not None:
        nt.links.new(col.outputs["Color"], bsdf.inputs["Base Color"])
        nt.links.new(col.outputs["Alpha"], bsdf.inputs["Alpha"])
    nrm = _tex("NormalMap")
    if nrm is not None:
        nrm.image.colorspace_settings.name = "Non-Color"
        nmap = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(nrm.outputs["Color"], nmap.inputs["Color"])
        nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    rgh = _tex("RoughnessMap")
    if rgh is not None:
        rgh.image.colorspace_settings.name = "Non-Color"
        nt.links.new(rgh.outputs["Color"], bsdf.inputs["Roughness"])
    met = _tex("MetalnessMap")
    if met is not None:
        met.image.colorspace_settings.name = "Non-Color"
        nt.links.new(met.outputs["Color"], bsdf.inputs["Metallic"])
    emi = _tex("EmissiveMask")
    if emi is not None:
        emi.image.colorspace_settings.name = "Non-Color"
        if "Emission Color" in bsdf.inputs:
            # Studio's model: EmissiveTint is a constant colour and the mask
            # scales the *strength*. Wiring the mask straight into Emission
            # Color instead makes every vein emit white in a preview - which is
            # what happened, and it hid the crimson the map actually carries.
            bsdf.inputs["Emission Color"].default_value = emission_tint
        if "Emission Strength" in bsdf.inputs:
            math_node = nt.nodes.new("ShaderNodeMath")
            math_node.operation = "MULTIPLY"
            math_node.inputs[1].default_value = emission_strength
            nt.links.new(emi.outputs["Color"], math_node.inputs[0])
            nt.links.new(math_node.outputs["Value"], bsdf.inputs["Emission Strength"])
    return mat


def make_bake_material(name, images, roles=("Color", "Normal", "Roughness")):
    """A material holding one image node per role, so a bake has a target.

    Returns (material, {role: image node}); the caller selects exactly one node
    as active, which is how Cycles decides where a bake lands.
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    nodes = {}
    for role in roles:
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = images[role]
        node.location = (-420, 300 - 320 * len(nodes))
        nodes[role] = node
    return mat, nodes


def make_curvature_material(name, start=(0.0, 0.0, 0.0, 1.0),
                            end=(1.0, 1.0, 1.0, 1.0)):
    """An EMIT material driven by Geometry > Pointiness, for the curvature bake.

    An EMIT bake cannot pick up light, a pass filter or a stray ambient term,
    which is the whole reason the curvature bake uses it rather than a diffuse
    bake that would come back tinted by the lighting rig.
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.inputs["Strength"].default_value = 1.0
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.44
    ramp.color_ramp.elements[0].color = start
    ramp.color_ramp.elements[1].position = 0.56
    ramp.color_ramp.elements[1].color = end
    nt.links.new(geo.outputs["Pointiness"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], emit.inputs["Color"])
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    return mat

# ----------------------------------------------------------------- images ---
def texture_dir(folder_name):
    """The real Documents folder; falls back to the OneDrive mirror."""
    home = os.path.expanduser("~")
    for folder in (os.path.join(home, "Documents"),
                   os.path.join(home, "OneDrive", "Documents")):
        if os.path.isdir(folder):
            d = os.path.join(folder, folder_name)
            os.makedirs(d, exist_ok=True)
            return d
    raise RuntimeError("no Documents folder for the texture output")


def new_image(name, size, fill=0.0, alpha=1.0, float_buffer=False):
    """Create or resize an image and fill it.

    `fill` may be a single value or one per channel: a tangent-space normal
    map's neutral colour is (0.5, 0.5, 1.0), and filling it with 0.5 everywhere
    leaves ordinary un-baked texels looking like a fully bent surface.
    """
    img = bpy.data.images.get(name)
    if img is not None and tuple(img.size) != (size, size):
        bpy.data.images.remove(img)
        img = None
    if img is None:
        img = bpy.data.images.new(name, size, size, alpha=False,
                                  float_buffer=float_buffer)
    if fill is not None:
        if isinstance(fill, (list, tuple)):
            rgba = [fill[0], fill[1], fill[2],
                    fill[3] if len(fill) > 3 else alpha]
        else:
            rgba = [fill, fill, fill, alpha]
        img.pixels = rgba * (size * size)
    return img


def save_image(img, path):
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    return {"file": path,
            "bytes": os.path.getsize(path) if os.path.exists(path) else 0}


def image_stats(img, fill=None):
    """Artifact probe on a baked map: coverage, variation and NaN count.

    `std_luma` is the load-bearing number. A bake that misses leaves the image
    at its fill colour, and a normal map that baked *flat* is (0.5, 0.5, 1.0) -
    which a "painted vs fill" test would score as 100% painted. Standard
    deviation catches both.
    """
    w, h = img.size
    px = list(img.pixels)
    n = w * h
    if not px:
        return {}
    if fill is None:
        fill = 0.5 if img.name.lower().endswith("normal") else 0.0
    off = flat = bad = 0
    lum_sum = lum_sq = 0.0
    for i in range(0, len(px), 4):
        r, g, b = px[i], px[i + 1], px[i + 2]
        if any(v != v for v in (r, g, b)):      # NaN
            bad += 1
            continue
        if (abs(r - fill) > 0.02 or abs(g - fill) > 0.02 or abs(b - fill) > 0.02):
            off += 1
        else:
            flat += 1
        lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
        lum_sum += lum
        lum_sq += lum * lum
    mean = lum_sum / max(n, 1)
    var = max(lum_sq / max(n, 1) - mean * mean, 0.0)
    return {"px": n, "painted_pct": round(100.0 * off / max(n, 1), 2),
            "flat_pct": round(100.0 * flat / max(n, 1), 2),
            "nan": bad, "mean_luma": round(mean, 4),
            "std_luma": round(math.sqrt(var), 4)}


def report(stage, **fields):
    payload = {"stage": stage}
    payload.update(fields)
    print("STAGE_JSON=" + json.dumps(payload, default=str))
    return payload

# ----------------------------------------------------------------- render ---
def render_view(loc, target, path, resolution=(720, 1080), lens=50.0,
                engine="CYCLES", samples=48):
    """Render one view through a temporary camera.

    Cycles by default rather than a viewport grab: `region_3d.view_matrix` only
    refreshes on a real window redraw, so an offscreen viewport capture can
    silently shoot the session's startup framing instead of the view asked for.
    """
    scene = bpy.context.scene
    cam_data = bpy.data.cameras.new("TEMP_Cam_Data")
    cam = bpy.data.objects.new("TEMP_Cam", cam_data)
    holder = bpy.data.collections.get("TEMP_Ref") or scene.collection
    holder.objects.link(cam)
    ok = False
    size = 0
    used = engine
    note = None
    prev = None
    try:
        cam_data.lens = lens
        cam.location = Vector(loc)
        direction = Vector(target) - Vector(loc)
        cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        prev = (scene.camera, scene.render.engine,
                scene.render.resolution_x, scene.render.resolution_y,
                scene.render.resolution_percentage, scene.render.filepath,
                scene.view_settings.view_transform, scene.view_settings.look)
        # Standard, not AgX: a preview is there to show whether the *maps* are
        # right. AgX is a cinematic grade, and under a bright key light it turned
        # near-black charred wood into pale beige.
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"
        scene.camera = cam
        scene.render.engine = engine
        if engine == "CYCLES":
            scene.cycles.samples = samples
        scene.render.resolution_x, scene.render.resolution_y = resolution
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = path
        try:
            bpy.ops.render.render(write_still=True)
        except Exception as exc:
            note = "render failed (%s); retried in CYCLES" % exc.__class__.__name__
            scene.render.engine = "CYCLES"
            scene.cycles.samples = max(16, samples // 2)
            bpy.ops.render.render(write_still=True)
            used = "CYCLES"
        ok = os.path.exists(path)
        size = os.path.getsize(path) if ok else 0
    finally:
        if prev:
            scene.camera, scene.render.engine = prev[0], prev[1]
            scene.render.resolution_x, scene.render.resolution_y = prev[2], prev[3]
            scene.render.resolution_percentage, scene.render.filepath = prev[4], prev[5]
            scene.view_settings.view_transform = prev[6]
            scene.view_settings.look = prev[7]
        remove_object(cam)
        bpy.data.cameras.remove(cam_data)
    return {"file": path, "exists": bool(ok), "bytes": size,
            "engine": used, "note": note, "lens": lens,
            "cam_loc": [round(v, 3) for v in loc],
            "cam_look_at": [round(v, 3) for v in target]}


def render_views(names, out_dir, resolution=None, prefix="check",
                 engine="CYCLES", samples=None):
    """Render several named views from params.VIEWS in one call."""
    import scene.params as P
    os.makedirs(out_dir, exist_ok=True)
    resolution = resolution or P.PREVIEW_RESOLUTION
    samples = samples or P.PREVIEW_SAMPLES
    shots = {}
    for name in names:
        v = P.VIEWS[name]
        path = os.path.join(out_dir, "%s_%s.png" % (prefix, name))
        shots[name] = render_view(v["loc"], v["target"], path,
                                  resolution=resolution, lens=v["lens"],
                                  engine=engine, samples=samples)
    return shots


def add_light_rig(lights=None, collection_name="TEMP_Ref"):
    """Three points of light, so metal and glow read in a preview."""
    import scene.params as P
    made = []
    holder = collection(collection_name)
    for name, loc, power, colour in (lights or P.LIGHTS):
        data = bpy.data.lights.new("TEMP_L_" + name, type="POINT")
        data.energy = power
        data.color = colour[:3]
        data.shadow_soft_size = 0.25
        obj = bpy.data.objects.new("TEMP_L_" + name, data)
        obj.location = loc
        holder.objects.link(obj)
        made.append(obj.name)
    return made


def remove_light_rig():
    return remove_objects(["TEMP_L_"])

# ------------------------------------------------------------------ export ---
def export_fbx(filepath, use_selection=True, settings=None):
    import scene.params as P
    s = dict(P.EXPORT)
    if settings:
        s.update(settings)
    bpy.ops.export_scene.fbx(
        filepath=filepath,
        use_selection=use_selection,
        apply_unit_scale=s["apply_unit_scale"],
        apply_scale_options=s["apply_scale_options"],
        bake_space_transform=s["bake_space_transform"],
        global_scale=s["global_scale"],
        object_types=s["object_types"],
        use_mesh_modifiers=False,
        mesh_smooth_type=s["mesh_smooth_type"],
        use_tspace=False,
        add_leaf_bones=False,
        bake_anim=False,
        path_mode="AUTO",
        embed_textures=False,
        batch_mode="OFF",
        use_custom_props=False,
        axis_forward=s["axis_forward"],
        axis_up=s["axis_up"],
    )
    return {"file": filepath,
            "bytes": os.path.getsize(filepath) if os.path.exists(filepath) else 0,
            "settings": {k: str(v) for k, v in s.items()}}


def fbx_reimport_check(filepath, timeout=900):
    """Re-import the FBX in a separate background Blender and measure it.

    So "the file is fine" is a measurement rather than a hope.
    """
    import subprocess
    exe = bpy.app.binary_path
    expr = (
        "import bpy, json, mathutils;"
        "bpy.ops.wm.read_factory_settings(use_empty=True);"
        "r = bpy.ops.import_scene.fbx(filepath=r'%s');"
        "objs = [o for o in bpy.data.objects if o.type == 'MESH'];"
        "[o.data.calc_loop_triangles() for o in objs];"
        "tris = sum(len(o.data.loop_triangles) for o in objs);"
        "lo = [round(min((o.matrix_world @ mathutils.Vector(c))[i]"
        " for o in objs for c in o.bound_box), 4) for i in range(3)];"
        "hi = [round(max((o.matrix_world @ mathutils.Vector(c))[i]"
        " for o in objs for c in o.bound_box), 4) for i in range(3)];"
        "names = sorted(o.name for o in bpy.data.objects);"
        "print('FBXCHECK', json.dumps({'objects': len(objs), 'tris': tris,"
        " 'lo': lo, 'hi': hi, 'names': names}))" % filepath
    )
    check, note = None, None
    try:
        proc = subprocess.run([exe, "--background", "--factory-startup",
                               "--python-expr", expr],
                              capture_output=True, text=True, timeout=timeout)
        for line in (proc.stdout or "").splitlines():
            if line.startswith("FBXCHECK"):
                check = json.loads(line[len("FBXCHECK"):].strip())
        if check is None:
            note = (proc.stderr or proc.stdout or "")[-500:]
    except Exception as exc:
        note = str(exc)
    if check:
        check["size"] = [round(check["hi"][i] - check["lo"][i], 4) for i in range(3)]
    return check, note

# ===================================================== the UV-space painter ===
# The maps are painted in UV space, and the paint is driven by where a texel is
# in the MODEL, not by which island it landed on. That is what lets a crack
# follow the blade's spine across three UV islands without a seam, and it is why
# the veins, the geometry and the emissive mask cannot drift apart: all three
# read the same polylines from params.py.
def _hash01(ix, iy, iz, seed=0):
    """Deterministic integer hash -> [0, 1). No RNG state, so maps reproduce."""
    import numpy as np
    n = (ix.astype("int64") * 374761393
         + iy.astype("int64") * 668265263
         + iz.astype("int64") * 1442695041
         + np.int64(seed) * 1013904223) & np.int64(0xFFFFFFFF)
    n = ((n ^ (n >> np.int64(13))) * np.int64(1274126177)) & np.int64(0xFFFFFFFF)
    return ((n ^ (n >> np.int64(16))) & np.int64(0xFFFF)).astype("f4") / 65535.0


def value_noise(x, y, z, freq, seed=0):
    """Trilinear value noise on the model's own coordinates."""
    import numpy as np
    fx, fy, fz = x * freq, y * freq, z * freq
    ix, iy, iz = np.floor(fx), np.floor(fy), np.floor(fz)
    tx, ty, tz = fx - ix, fy - iy, fz - iz
    sx = tx * tx * (3.0 - 2.0 * tx)
    sy = ty * ty * (3.0 - 2.0 * ty)
    sz = tz * tz * (3.0 - 2.0 * tz)
    ix, iy, iz = ix.astype("int64"), iy.astype("int64"), iz.astype("int64")
    c000 = _hash01(ix, iy, iz, seed)
    c100 = _hash01(ix + 1, iy, iz, seed)
    c010 = _hash01(ix, iy + 1, iz, seed)
    c110 = _hash01(ix + 1, iy + 1, iz, seed)
    c001 = _hash01(ix, iy, iz + 1, seed)
    c101 = _hash01(ix + 1, iy, iz + 1, seed)
    c011 = _hash01(ix, iy + 1, iz + 1, seed)
    c111 = _hash01(ix + 1, iy + 1, iz + 1, seed)
    x00 = c000 + (c100 - c000) * sx
    x10 = c010 + (c110 - c010) * sx
    x01 = c001 + (c101 - c001) * sx
    x11 = c011 + (c111 - c011) * sx
    y0 = x00 + (x10 - x00) * sy
    y1 = x01 + (x11 - x01) * sy
    return y0 + (y1 - y0) * sz


def rasterise_positions(size, objects):
    """Where each texel of the atlas sits in the model, and which part owns it.

    One pass per triangle, writing into a position buffer and a part-id buffer.
    Everything else in the painter then works on whole-image numpy arrays, which
    is both far simpler and far faster than evaluating rules per triangle.
    """
    import numpy as np
    pos = np.zeros((size, size, 3), dtype="f4")
    pid = np.zeros((size, size), dtype="i2")
    covered = np.zeros((size, size), dtype=bool)
    verts_all = []
    for obj_index, obj in enumerate(objects, start=1):
        me = obj.data
        if not me.uv_layers or not len(me.uv_layers.active.data):
            continue
        uv = me.uv_layers.active.data
        mw = obj.matrix_world
        coords = [mw @ v.co for v in me.vertices]
        for poly in me.polygons:
            loops = list(poly.loop_indices)
            if len(loops) < 3:
                continue
            vi = [me.loops[li].vertex_index for li in loops]
            uvp = [(uv[li].uv[0] * size, uv[li].uv[1] * size) for li in loops]
            tris = [(0, 1, 2)] if len(loops) == 3 else [(0, 1, 2), (0, 2, 3)]
            for (a, b, c) in tris:
                px = np.array([uvp[a][0], uvp[b][0], uvp[c][0]], dtype="f4")
                py = np.array([uvp[a][1], uvp[b][1], uvp[c][1]], dtype="f4")
                x0 = max(int(np.floor(px.min())) - 1, 0)
                x1 = min(int(np.ceil(px.max())) + 1, size - 1)
                y0 = max(int(np.floor(py.min())) - 1, 0)
                y1 = min(int(np.ceil(py.max())) + 1, size - 1)
                if x1 < x0 or y1 < y0:
                    continue
                xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5,
                                     np.arange(y0, y1 + 1) + 0.5)
                d = ((px[1] - px[0]) * (py[2] - py[0])
                     - (px[2] - px[0]) * (py[1] - py[0]))
                if abs(d) < 1e-12:
                    continue
                w0 = ((px[1] - xs) * (py[2] - ys)
                      - (px[2] - xs) * (py[1] - ys)) / d
                w1 = ((px[2] - xs) * (py[0] - ys)
                      - (px[0] - xs) * (py[2] - ys)) / d
                w2 = 1.0 - w0 - w1
                inside = (w0 >= -0.002) & (w1 >= -0.002) & (w2 >= -0.002)
                if not inside.any():
                    continue
                tri = np.array([coords[vi[a]], coords[vi[b]], coords[vi[c]]],
                               dtype="f4")
                wx = w0 * tri[0, 0] + w1 * tri[1, 0] + w2 * tri[2, 0]
                wy = w0 * tri[0, 1] + w1 * tri[1, 1] + w2 * tri[2, 1]
                wz = w0 * tri[0, 2] + w1 * tri[1, 2] + w2 * tri[2, 2]
                sel = (slice(y0, y1 + 1), slice(x0, x1 + 1))
                m = inside
                pos[sel[0], sel[1], 0] = np.where(m, wx, pos[sel][:, :, 0])
                pos[sel[0], sel[1], 1] = np.where(m, wy, pos[sel][:, :, 1])
                pos[sel[0], sel[1], 2] = np.where(m, wz, pos[sel][:, :, 2])
                pid[sel[0], sel[1]] = np.where(m, obj_index,
                                               pid[sel[0], sel[1]]).astype("i2")
                covered[sel[0], sel[1]] |= m
    return pos, pid, covered


def _dilate(mask, radius):
    """Cheap square dilation, used to give the map an 8 px bleed at its edges."""
    import numpy as np
    out = mask.copy()
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx == 0 and dy == 0:
                continue
            out |= np.roll(np.roll(mask, dy, axis=0), dx, axis=1)
    return out

def linear_to_srgb(a):
    """Linear -> sRGB, because a PNG ColorMap is read as sRGB by Studio.

    Blender's byte images store raw values, so writing sRGB here gives a map
    that decodes back to the intended linear colour in Blender *and* in Studio
    (where the ColorMap is sRGB and multiplies the part's white Color).
    """
    import numpy as np
    a = np.clip(a, 0.0, 1.0)
    return np.where(a <= 0.0031308, a * 12.92,
                    1.055 * np.power(a, 1.0 / 2.4) - 0.055).astype("f4")


def rule_weight(points, rule):
    """Weight in [0, 1] for one paint rule over an (N, 3) array of positions."""
    import numpy as np
    kind = rule["kind"]
    soft = max(float(rule.get("soft", 0.002)), 1e-6)
    radius = float(rule.get("radius", 0.01))
    if kind == "polyline":
        poly = np.array(rule["poly"], dtype="f4")
        best = None
        for i in range(len(poly) - 1):
            a, b = poly[i], poly[i + 1]
            ab = b - a
            denom = float(ab.dot(ab)) or 1e-9
            t = np.clip(((points - a[None, :]) @ ab) / denom, 0.0, 1.0)
            proj = a[None, :] + t[:, None] * ab[None, :]
            d = np.sqrt(((points - proj) ** 2).sum(axis=1))
            best = d if best is None else np.minimum(best, d)
        dist = best
    elif kind == "near_point":
        p = np.array(rule["point"], dtype="f4")
        dist = np.sqrt(((points - p[None, :]) ** 2).sum(axis=1))
    elif kind == "z_band":
        z0, z1 = float(rule["z0"]), float(rule["z1"])
        mid, half = 0.5 * (z0 + z1), 0.5 * abs(z1 - z0)
        dist = np.abs(np.abs(points[:, 2] - mid) - half)
    else:
        return np.zeros(points.shape[0], dtype="f4")
    return np.clip(1.0 - np.clip((dist - radius) / soft, 0.0, 1.0),
                   0.0, 1.0).astype("f4")

# The value an un-baked texel must carry, per map. A black tangent-space normal
# is a fully bent surface and a black AO is full occlusion, so these are not
# cosmetic defaults - they are what stops every UV seam showing an outline.
BAKED_FILLS = {
    "NormalMap": (0.5, 0.5, 1.0, 1.0),
    "AO": (1.0, 1.0, 1.0, 1.0),
    "Curvature": (0.5, 0.5, 0.5, 1.0),
}


def dilate_into_gaps(array, covered, radius=8, fill=None):
    """Bleed baked values outward into the gaps around each island.

    A bake only writes the texels its islands project onto. Everything between
    the islands keeps whatever was there, and a renderer sampling across an
    island edge reads that - so without this the model gets a visible outline of
    the atlas around every UV seam.

    `fill` is stamped back over the uncovered texels first. Blender's
    `use_clear = False` was not enough to preserve the fill through a bake, and
    relying on it would have left a black background under the bleeds. Returns
    the repaired copy and how many texels were filled in.
    """
    import numpy as np
    out = array.copy()
    if fill is not None:
        out[~covered] = np.asarray(fill, dtype="f4")
    cov = covered.copy()
    h, w = cov.shape
    repaired = 0
    for _ in range(radius):
        grew = cov.copy()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ys = slice(max(dy, 0), h + min(dy, 0))
            xs = slice(max(dx, 0), w + min(dx, 0))
            ys_src = slice(max(-dy, 0), h + min(-dy, 0))
            xs_src = slice(max(-dx, 0), w + min(-dx, 0))
            take = (~cov)[ys, xs] & cov[ys_src, xs_src]
            if not take.any():
                continue
            out[ys, xs][take] = out[ys_src, xs_src][take]
            grew[ys, xs] |= take
            repaired += int(take.sum())
        cov = grew
    return out, repaired


def paint_maps(size, objects, recipes, normal_array=None, ao_array=None,
               ao_gain=0.55, baked=None, bleed_px=8):
    """Paint colour, roughness, metalness and the emissive mask in UV space.

    Returns the arrays plus the statistics a gate can check: painted texels, vein
    texels, emissive texels, and the mean luminance of the veins before and after
    ambient occlusion - so "the veins really are kept out of the AO" is measured
    rather than asserted. Any `baked` maps handed in come back edge-bled, so the
    gap between UV islands carries a real value instead of the fill.
    """
    import numpy as np
    pos, pid, covered = rasterise_positions(size, objects)
    area_m2 = sum(p.area for obj in objects for p in obj.data.polygons)
    repaired = {}
    for role, arr in (baked or {}).items():
        out, filled = dilate_into_gaps(arr, covered, radius=bleed_px,
                                       fill=BAKED_FILLS.get(role))
        repaired[role] = (out, filled)
    if "NormalMap" in repaired:
        normal_array = repaired["NormalMap"][0]
    if "AO" in repaired:
        ao_array = repaired["AO"][0]
    colour = np.zeros((size, size, 4), dtype="f4")
    colour[..., 3] = 1.0
    rough = np.zeros((size, size, 1), dtype="f4")
    metal = np.zeros((size, size, 1), dtype="f4")
    emissive = np.zeros((size, size, 1), dtype="f4")
    vein_w = np.zeros((size, size), dtype="f4")
    wear = np.zeros((size, size), dtype="f4")
    if normal_array is not None:
        gx = np.gradient(normal_array[..., 0].astype("f4"), axis=1)
        gy = np.gradient(normal_array[..., 1].astype("f4"), axis=0)
        wear = np.clip(np.sqrt(gx * gx + gy * gy) * 16.0, 0.0, 1.0).astype("f4")
    per_part = {}
    for obj_index, obj in enumerate(objects, start=1):
        recipe = recipes.get(obj.name)
        if recipe is None:
            continue
        mask = pid == obj_index
        if not mask.any():
            continue
        idx = np.nonzero(mask)
        pts = pos[idx]
        noise = value_noise(pts[:, 0], pts[:, 1], pts[:, 2],
                            float(recipe.get("noise", 20.0)))
        fac = noise * 0.65 + noise * noise * 0.35
        base = np.array(recipe["base"][:3], dtype="f4")
        second = np.array(recipe["second"][:3], dtype="f4")
        col = base[None, :] * (1.0 - fac[:, None]) + second[None, :] * fac[:, None]
        w = wear[idx] * float(recipe.get("wear", 0.5))
        col = col + w[:, None] * np.array([0.30, 0.26, 0.20], dtype="f4")[None, :]
        r = float(recipe["rough"]) + (noise - 0.5) * 0.36 - w * 0.25
        m = np.full(noise.shape, float(recipe.get("metal", 0.0)), dtype="f4")
        e = np.zeros(noise.shape, dtype="f4")
        vw = np.zeros(noise.shape, dtype="f4")
        for rule in recipe.get("rules", []):
            rw = rule_weight(pts, rule)
            hit = rw > 0.001
            if not hit.any():
                continue
            blend = rw[hit]
            rc = np.array(rule["colour"][:3], dtype="f4")
            col[hit] = (col[hit] * (1.0 - blend[:, None])
                        + rc[None, :] * blend[:, None])
            if rule.get("rough") is not None:
                r[hit] = r[hit] * (1.0 - blend) + float(rule["rough"]) * blend
            if rule.get("metal") is not None:
                m[hit] = m[hit] * (1.0 - blend) + float(rule["metal"]) * blend
            if rule.get("emissive"):
                e[hit] = np.maximum(e[hit], float(rule["emissive"]) * rw[hit])
            if rule.get("no_ao"):
                vw = np.maximum(vw, rw)
        colour[idx[0], idx[1], :3] = np.clip(col, 0.0, 1.0)
        rough[idx[0], idx[1], 0] = np.clip(r, 0.02, 1.0)
        metal[idx[0], idx[1], 0] = np.clip(m, 0.0, 1.0)
        emissive[idx[0], idx[1], 0] = np.clip(e, 0.0, 1.0)
        vein_w[idx] = vw
        per_part[obj.name] = {
            "texels": int(mask.sum()),
            "vein_texels": int((vw > 0.5).sum()),
            "emissive_texels": int((e > 0.5).sum()),
            "noise": float(recipe.get("noise", 20.0)),
            "rules": len(recipe.get("rules", [])),
        }
    ao_factor = np.ones((size, size), dtype="f4")
    if ao_array is not None:
        ao = np.clip(ao_array[..., 0].astype("f4"), 0.0, 1.0)
        ao_factor = 1.0 - (1.0 - ao) * ao_gain
    # The vein core is taken out of the AO *completely*: ao_soft reaches 1.0 at
    # vein_w 0.5, so the moment a texel counts as vein its full brightness is
    # preserved, and the crack's soft shoulder still fades in and out smoothly.
    ao_soft = np.clip(vein_w * 2.0, 0.0, 1.0)
    ao_factor = ao_factor * (1.0 - ao_soft) + ao_soft
    vein_core = covered & (vein_w > 0.5)
    before = (float(colour[..., :3].sum(axis=2)[vein_core].mean())
              if vein_core.any() else 0.0)
    colour[..., :3] = colour[..., :3] * ao_factor[..., None]
    after = (float(colour[..., :3].sum(axis=2)[vein_core].mean())
             if vein_core.any() else 0.0)
    stats = {
        "painted_texels": int(covered.sum()),
        "covered_pct": round(100.0 * float(covered.sum()) / float(size * size), 2),
        # Texel density is the number that decides whether a 1024 atlas is enough:
        # what fraction of the *atlas* is used says more about the packer than
        # about the model, whereas texels per metre says what a player sees.
        "surface_area_m2": round(area_m2, 4),
        "texels_per_metre": (round(math.sqrt(float(covered.sum()) / area_m2), 1)
                             if area_m2 > 0 else 0.0),
        "vein_texels": int((vein_w > 0.5).sum()),
        "emissive_texels": int((emissive[..., 0] > 0.5).sum()),
        "emissive_pct_of_painted": round(
            100.0 * float((emissive[..., 0] > 0.5).sum())
            / max(int(covered.sum()), 1), 2),
        "vein_luma_before_ao": round(before, 5),
        "vein_luma_after_ao": round(after, 5),
        "vein_ao_preserved": bool(abs(before - after) < 1e-5),
        "per_part": per_part,
    }
    return {"colour": colour, "rough": rough, "metal": metal,
            "emissive": emissive, "vein": vein_w, "covered": covered,
            "pos": pos, "pid": pid, "stats": stats, "repaired": repaired}


def write_support_maps(out_dir, size, arrays, names, images):
    """Save the extra maps (AO, curvature) that Blender shows but Studio ignores."""
    written = {}
    for role in names:
        arr = arrays.get(role)
        if arr is None:
            continue
        img = images.get(role)
        if img is None:
            continue
        img.colorspace_settings.name = "Non-Color"
        img.pixels = arr.reshape(-1).tolist()
        written[role] = save_image(img, os.path.join(out_dir, "%s.png" % role))
    return written
# CHUNK_END
