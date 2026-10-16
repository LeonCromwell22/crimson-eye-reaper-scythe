"""Diagnostic: where exactly are the pommel's two non-manifold edges?

Run against a saved snapshot:
    blender -b out/s9_cleanup.blend -P tools/diag_nonmanifold.py
"""
import bmesh
import bpy

for name in ("Scythe_Pommel", "Scythe_HeadCrown", "Scythe_Blade"):
    obj = bpy.data.objects.get(name)
    if obj is None:
        continue
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    edges = [e for e in bm.edges if len(e.link_faces) != 2]
    print("DIAG %s verts=%d faces=%d nonmanifold=%d"
          % (name, len(bm.verts), len(bm.faces), len(edges)))
    for e in edges:
        v0, v1 = e.verts
        print("   edge faces=%d  v0=%s  v1=%s  len=%.6f"
              % (len(e.link_faces),
                 [round(c, 5) for c in v0.co], [round(c, 5) for c in v1.co],
                 (v1.co - v0.co).length))
        for f in e.link_faces:
            print("      face area=%.9f verts=%s"
                  % (f.calc_area(), [round(c, 5) for c in f.calc_center_median()]))
    # Degenerate faces are the usual cause once a weld has happened.
    tiny = [f for f in bm.faces if f.calc_area() < 1e-9]
    print("DIAG %s degenerate_faces=%d" % (name, len(tiny)))
    bm.free()
