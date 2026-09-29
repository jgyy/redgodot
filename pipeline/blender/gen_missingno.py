"""MISSINGNO. (upstream src/game/glitches.js 'block' look): the famous backwards-L of
decompressed garbage, as a slab of 8px glitch tiles.  The front/back faces are textured
with upstream's own glitchSprite() output, tile depths jitter like corrupted data.
Called by gen_pokemon.py --all; standalone:

  python3 pipeline/blender/gen_missingno.py

The 64x64 front/back glitch sprites come from pipeline/scripts/bake_monsprites.js when
UPSTREAM=/path/to/pokemon-claude-red is available (needs node); otherwise the copies that
were baked from it once are used (pipeline/data/missingno_front.png / _back.png), so the model
regenerates without the upstream checkout.

Rig: 'body' with one bone per tile column ('col0'..'col6').  Animations are deliberately glitchy:
stepped (low frame rate) column jitter, tearing offsets, columns collapsing on faint.
"""
import math
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
import bpy  # noqa: E402,F401  (must precede bmesh)
from mathutils import Vector  # noqa: E402
import common as C  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
DATA = os.path.join(ROOT, 'pipeline', 'data')
HEIGHT_M = 1.6
UP = 8   # texture upscale (nearest) so linear filtering keeps the pixels crisp
T = 8.0


def load_sprites(tmp):
    """(front[64,64,4], back[64,64,4]) glitch sprites."""
    from PIL import Image
    script = os.path.join(ROOT, 'pipeline', 'scripts', 'bake_monsprites.js')
    if os.environ.get('UPSTREAM'):
        try:
            subprocess.run(['node', script, tmp, '64', 'MISSINGNO'], check=True, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            f = np.asarray(Image.open(os.path.join(tmp, 'MISSINGNO_front.png')).convert('RGBA'))
            b = np.asarray(Image.open(os.path.join(tmp, 'MISSINGNO_back.png')).convert('RGBA'))
            return f, b
        except Exception:  # noqa: BLE001
            pass
    f = np.asarray(Image.open(os.path.join(DATA, 'missingno_front.png')).convert('RGBA'))
    b = np.asarray(Image.open(os.path.join(DATA, 'missingno_back.png')).convert('RGBA'))
    return f, b


def make_geometry():
    rng = np.random.RandomState(0x1F)
    P, Nn, UV, tris = [], [], [], []      # per-face-vertex data
    col_of = []
    for ty in range(7):
        for tx in range(7):
            if tx < 4 and ty < 4:
                continue          # the empty upper-left corner
            x0, y0 = 8 + tx * T, 8 + ty * T
            depth = 10.0 + rng.randint(0, 4) * 2.0
            hx0, hx1 = x0 - 32.0, x0 - 32.0 + T
            z1, z0 = 60.0 - y0, 60.0 - y0 - T
            yf, yb = -depth * 0.5, depth * 0.5
            faces = [
                ((0, -1, 0), [(hx0, yf, z0), (hx1, yf, z0), (hx1, yf, z1), (hx0, yf, z1)]),
                ((0, 1, 0), [(hx1, yb, z0), (hx0, yb, z0), (hx0, yb, z1), (hx1, yb, z1)]),
                ((-1, 0, 0), [(hx0, yb, z0), (hx0, yf, z0), (hx0, yf, z1), (hx0, yb, z1)]),
                ((1, 0, 0), [(hx1, yf, z0), (hx1, yb, z0), (hx1, yb, z1), (hx1, yf, z1)]),
                ((0, 0, 1), [(hx0, yf, z1), (hx1, yf, z1), (hx1, yb, z1), (hx0, yb, z1)]),
                ((0, 0, -1), [(hx0, yb, z0), (hx1, yb, z0), (hx1, yf, z0), (hx0, yf, z0)]),
            ]
            for n, corners in faces:
                base = len(P)
                cx = sum(c[0] for c in corners) / 4.0 + 32.0
                cy = 60.0 - sum(c[2] for c in corners) / 4.0
                for (px, py, pz) in corners:
                    sx, sy = px + 32.0, 60.0 - pz
                    if n[1] > 0:           # back: seen from behind, mirrored
                        u, v = 64 + (64 - sx), sy
                    elif n[1] < 0:         # front
                        u, v = sx, sy
                    elif abs(n[0]) > 0:    # sides: smear the tile's edge pixels
                        u = min(max(cx - 0.5 * n[0], x0 + 0.5), x0 + T - 0.5)
                        v = sy
                    else:
                        u = sx
                        v = min(max(cy + 0.5 * n[2], y0 + 0.5), y0 + T - 0.5)
                    P.append((px, py, pz))
                    Nn.append(n)
                    UV.append((u / 128.0, 1.0 - v / 64.0))
                    col_of.append(tx)
                tris += [(base, base + 1, base + 2), (base, base + 2, base + 3)]
    return (np.array(P, float), np.array(Nn, float), np.array(UV, float), np.array(tris, np.int64),
            np.array(col_of, np.int64))


class _Rig:
    pass


def stepped(u, steps):
    return math.floor(u * steps) / float(steps)


def hash01(a, b):
    v = math.sin(a * 127.1 + b * 311.7) * 43758.5453
    return v - math.floor(v)


def animate(arm, cols, target):
    import monanim as MA
    names = set(cols) | {'root', 'body'}
    all_bones = ['root', 'body'] + cols
    h = target
    TAU = 2 * math.pi

    def jit(c, q, k=1.0):
        return (hash01(c + 1, q * 17 + k) - 0.5) * 2.0

    def idle(P, u):
        q = int(math.floor(u * 10)) % 10
        P.move('body', (0, 0, 0.01 * h * math.sin(TAU * u)))
        for i, c in enumerate(cols):
            P.move(c, (0.01 * h * jit(i, q, 2) * (1 if q % 3 == 0 else 0.2), 0,
                       0.02 * h * math.sin(TAU * stepped(u, 12) * 2 + i * 1.3)))
            if q in (3, 7) and i % 3 == q % 3:
                P.move(c, (0.05 * h * jit(i, q, 5), 0, 0))
                P.scale(c, 1.0, 1.0 + 0.06 * jit(i, q, 7), 1.0)

    def walk(P, u):
        q = int(math.floor(u * 8)) % 8
        P.move('body', (0, 0, 0.03 * h * abs(math.sin(TAU * stepped(u, 8)))))
        P.rot('body', Vector((0, 1, 0)), math.radians(4) * math.sin(TAU * stepped(u, 8)))
        for i, c in enumerate(cols):
            P.move(c, (0.03 * h * jit(i, q, 3), 0, 0.02 * h * jit(i, q, 4)))

    def attack(P, u):
        env = MA.spline(u, [(0, 0), (0.25, -0.4), (0.45, 1.0), (0.65, 0.7), (1.0, 0)])
        q = int(math.floor(u * 12))
        P.move('body', (0, -0.3 * h * env, 0))
        for i, c in enumerate(cols):
            P.move(c, ((0.06 * h * jit(i, q, 9)) * abs(env), 0, 0))
            if 0.35 < u < 0.7:
                P.scale(c, 1.0 + 0.1 * jit(i, q, 6), 1.0, 1.0 + 0.08 * jit(i, q, 8))

    def hurt(P, u):
        env = math.exp(-4 * u)
        q = int(math.floor(u * 14))
        P.move('body', (0, 0.1 * h * env, 0))
        for i, c in enumerate(cols):
            P.move(c, (0.09 * h * jit(i, q, 1) * env, 0, 0.05 * h * jit(i, q, 2) * env))

    def faint(P, u):
        for i, c in enumerate(cols):
            d = MA.sstep((u - 0.12 - 0.07 * (i % 4)) / 0.5)
            P.scale(c, 1.0 + 0.2 * d, 1.0, max(0.03, 1.0 - 0.97 * d))
        P.move('body', (0, 0, -0.02 * h * MA.sstep(u * 1.5)))

    def special(P, u):
        q = int(math.floor(u * 15))
        env = MA.bump(u, 0.0, 1.0)
        P.move('body', (0, 0, 0.12 * h * math.sin(math.pi * u)))
        for i, c in enumerate(cols):
            P.scale(c, 1.0 + 0.25 * jit(i, q, 3) * env, 1.0, 1.0 + 0.3 * jit(i, q, 4) * env)
            P.move(c, (0.08 * h * jit(i, q, 5) * env, 0, 0))

    acts = []
    for clip, n, fn, loop in (('Idle', MA.DUR['Idle'], idle, True), ('Walk', MA.DUR['Walk'], walk, True),
                              ('Attack', MA.DUR['Attack'], attack, False), ('Hurt', MA.DUR['Hurt'], hurt, False),
                              ('Faint', MA.DUR['Faint'], faint, False), ('Special', MA.DUR['Special'], special, False)):
        W = MA.Writer(arm, clip, n)
        for f in range(n + 1):
            P = MA.Pose(names)
            fn(P, ((f % n) if loop else f) / float(n))
            W.key_pose(f, P)
        W.finalize()
        acts.append(W.write(all_bones))
    C.stash_actions(arm, acts)


def build(out_dir):
    import gen_pokemon as GP
    with tempfile.TemporaryDirectory() as tmp:
        front, back = load_sprites(tmp)
        from PIL import Image
        atlas = np.zeros((64, 128, 4), dtype=np.uint8)
        atlas[:, :64] = front
        atlas[:, 64:] = back
        atlas[..., 3] = 255
        img = Image.fromarray(atlas).resize((128 * UP, 64 * UP), Image.NEAREST).convert('RGB')
        png = os.path.join(tmp, 'MISSINGNO.png')
        img.save(png, optimize=True)

        C.reset_scene()
        P, Nn, UV, tris, colid = make_geometry()
        lo, hi = P.min(0), P.max(0)
        target = HEIGHT_M
        k = target / (hi[2] - lo[2])
        cx, cy = (lo[0] + hi[0]) * 0.5, (lo[1] + hi[1]) * 0.5
        Pm = (P - np.array([cx, cy, lo[2]])) * k
        ncol = int(colid.max()) + 1
        cols = ['col%d' % i for i in range(ncol)]
        bones = [{'name': 'body', 'head': Vector((0, 0, 0.3)), 'parent': None, 'length': 0.16}]
        for i in range(ncol):
            xs = Pm[colid == i, 0]
            bones.append({'name': cols[i], 'head': Vector((float(xs.mean()), 0, 0.0)), 'parent': 'body',
                          'length': 0.16})
        n = len(Pm)
        rig = _Rig()
        rig.influence_idx = (colid + 1)[:, None] * np.ones((1, 4), dtype=np.int64)
        rig.influence_idx[:, 1:] = 0
        rig.influence_w = np.zeros((n, 4))
        rig.influence_w[:, 0] = 1.0
        bone_names = [b['name'] for b in bones]
        mat = GP.make_textured_material('mon_missingno', png)
        mat.node_tree.nodes['Image Texture'].interpolation = 'Closest'
        uv = UV[tris]                                   # (m, 3, 2)
        obj = GP.make_object('MISSINGNO', Pm, Nn, tris, uv, np.ones(n), rig, mat, bone_names, smooth=False)
        arm = C.build_armature('MISSINGNO', bones, root_len=target * 0.25)
        C.skin_to_armature(obj, arm)
        animate(arm, cols, target)
        out_path = os.path.join(out_dir, 'MISSINGNO.glb')
        C.export_glb(out_path, animations=True)
        import glbtools as GT
        GT.externalize_images(out_path, lambda i, mime: 'MISSINGNO_tex')
        GT.quantize_attributes(out_path)
        for stale in ('MISSINGNO_MISSINGNO.png', 'MISSINGNO_MISSINGNO.png.import'):
            sp_ = os.path.join(out_dir, stale)
            if os.path.exists(sp_):
                os.remove(sp_)
        info = {'height_m': round(target, 3), 'px_height': round(float(hi[2] - lo[2]), 2), 'groups': ncol + 1,
                'tris': int(len(tris)), 'bones': len(bones), 'materials': 1, 'file': 'MISSINGNO.glb',
                'bytes': os.path.getsize(out_path), 'status': 'generated',
                'texture': '%dx%d' % (128 * UP, 64 * UP)}
    print('MISSINGNO   h=%.2fm tris=%d bones=%d' % (info['height_m'], info['tris'], info['bones']), flush=True)
    return {'MISSINGNO': info}


if __name__ == '__main__':
    build(os.path.join(ROOT, 'godot', 'assets', 'models', 'pokemon'))
