"""Diagnostic: what does Blender actually write for a byte image pixel?

Two 8x8 images are filled with 0.5 and saved, one declared sRGB and one
declared Non-Color. `pixels` is documented as scene-linear, so the question is
whether the file gets 128 (written raw) or 188 (sRGB-encoded on save). The
answer decides whether the painter should pre-encode the ColorMap itself.

    blender -b --factory-startup -P tools/diag_colorspace.py
"""
import os

import bpy

out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "out")

for name, space in (("test_srgb", "sRGB"), ("test_noncolor", "Non-Color")):
    img = bpy.data.images.new(name, 8, 8, alpha=False)
    img.colorspace_settings.name = space
    img.pixels = [0.5, 0.5, 0.5, 1.0] * 64
    path = os.path.join(out_dir, name + ".png")
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    print("DIAGCS %s space=%s file=%s bytes=%d"
          % (name, space, path, os.path.getsize(path)))

    # And what comes back if we load it again?
    loaded = bpy.data.images.load(path)
    px = list(loaded.pixels)
    print("DIAGCS %s reloaded first pixel = %s (space %s)"
          % (name, [round(v, 4) for v in px[:4]],
             loaded.colorspace_settings.name))
    bpy.data.images.remove(loaded)
