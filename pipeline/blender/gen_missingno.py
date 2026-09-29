"""MISSINGNO. (upstream src/game/glitches.js 'block' look): the famous backwards-L of
decompressed garbage, as a slab of 8px glitch tiles.  The front/back faces are textured
with upstream's own glitchSprite() output (baked through pipeline/scripts/bake_monsprites.js),
tile depths jitter like corrupted data.  Called by gen_pokemon.py --all; standalone:

  UPSTREAM=/path/to/pokemon-claude-red python3 pipeline/blender/gen_missingno.py
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
import bpy  # noqa: E402,F401  (must precede bmesh)
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402
import common as C  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
HEIGHT_M = 1.6
UP = 8   # texture upscale (nearest) so linear filtering keeps the pixels crisp


def bake_sprites(tmp):
    script = os.path.join(ROOT, 'pipeline', 'scripts', 'bake_monsprites.js')
    subprocess.run(['node', script, tmp, '64', 'MISSINGNO'], check=True, stdout=subprocess.DEVNULL)
    from PIL import Image
    f = np.asarray(Image.open(os.path.join(tmp, 'MISSINGNO_front.png')).convert('RGBA'))
    b = np.asarray(Image.open(os.path.join(tmp, 'MISSINGNO_back.png')).convert('RGBA'))
    return f, b


def build(out_dir):
    import gen_pokemon as GP
    with tempfile.TemporaryDirectory() as tmp:
        front, back = bake_sprites(tmp)
        from PIL import Image
        atlas = np.zeros((64, 128, 4), dtype=np.uint8)
        atlas[:, :64] = front
        atlas[:, 64:] = back
        atlas[..., 3] = 255
        img = Image.fromarray(atlas).resize((128 * UP, 64 * UP), Image.NEAREST).convert('RGB')
        png = os.path.join(tmp, 'MISSINGNO.png')
        img.save(png, optimize=True)

        C.reset_scene()
        mb = C.MeshBuilder()
        uv = mb.bm.loops.layers.uv.new('UVMap')
        rng = np.random.RandomState(0x1F)
        gi = mb.group_index('body')
        T = 8.0
        for ty in range(7):
            for tx in range(7):
                if tx < 4 and ty < 4:
                    continue  # the empty upper-left corner
                x0, y0 = 8 + tx * T, 8 + ty * T
                depth = 10.0 + rng.randint(0, 4) * 2.0
                res = bmesh.ops.create_cube(mb.bm, size=1.0)
                for v in res['verts']:
                    v.co = Vector((x0 - 32 + (v.co.x + 0.5) * T, (v.co.y) * depth, 60 - y0 - (v.co.z + 0.5) * T))
                    v[mb.grp] = gi
                faces = {f for v in res['verts'] for f in v.link_faces}
                for f in faces:
                    f.normal_update()
                    n = f.normal
                    c = f.calc_center_median()
                    for loop in f.loops:
                        co = loop.vert.co
                        sx, sy = co.x + 32.0, 60.0 - co.z
                        if n.y > 0.5:        # back: seen from behind, mirrored
                            u, vv = 64 + (64 - sx), sy
                        elif n.y < -0.5:     # front
                            u, vv = sx, sy
                        else:                # sides: smear the tile's edge pixels
                            cx, cy = c.x + 32.0, 60.0 - c.z
                            if abs(n.x) > 0.5:
                                u = min(max(cx - 0.5 * np.sign(n.x), x0 + 0.5), x0 + T - 0.5)
                                vv = sy
                            else:
                                u = sx
                                vv = min(max(cy + 0.5 * np.sign(n.z), y0 + 0.5), y0 + T - 0.5)
                        loop[uv].uv = (u / 128.0, 1.0 - vv / 64.0)
                    f.smooth = False
        mat = GP.make_textured_material('mon_missingno', png)
        mat.node_tree.nodes['Image Texture'].interpolation = 'Closest'
        info = GP.finalize('MISSINGNO', mb, [mat], {'ht': [HEIGHT_M / 0.3048, 0]},
                           os.path.join(out_dir, 'MISSINGNO.glb'))
    info['file'] = 'MISSINGNO.glb'
    info['bytes'] = os.path.getsize(os.path.join(out_dir, 'MISSINGNO.glb'))
    info['status'] = 'generated'
    info['texture'] = '%dx%d' % (128 * UP, 64 * UP)
    print('MISSINGNO   h=%.2fm tris=%d' % (info['height_m'], info['tris']), flush=True)
    return {'MISSINGNO': info}


if __name__ == '__main__':
    build(os.path.join(ROOT, 'godot', 'assets', 'models', 'pokemon'))
