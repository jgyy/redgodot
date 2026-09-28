"""Generic rigged humanoid (voxel-extruded from the 16x24 region-code sprite grids).

  blender --background --python pipeline/blender/gen_characters.py -- [--head short] [--body normal]

Front half of each voxel column comes from the `down` grid, the back half from the `up`
grid (mirrored), so the face is only on the front and the back of the head is hair.
Each contiguous run of cells in a row gets an elliptical depth profile -> rounded solid.
Output: godot/assets/models/characters/humanoid.glb + manifest.json
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402,F401
from mathutils import Vector  # noqa: E402
import common as C  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
EXTRACTED = os.path.join(ROOT, 'pipeline', 'extracted')
OUT_DIR = os.path.join(ROOT, 'godot', 'assets', 'models', 'characters')

TARGET_HEIGHT = 1.5  # metres, head-to-toe

ROLE_OF = {}
for ch in 'SsWM':
    ROLE_OF[ch] = 'skin'
ROLE_OF['E'] = 'eye'
for ch in 'HhL':
    ROLE_OF[ch] = 'hair'
for ch in 'CcKB':
    ROLE_OF[ch] = 'hat'
for ch in 'TtUAXxGg':
    ROLE_OF[ch] = 'top'
for ch in 'Pp':
    ROLE_OF[ch] = 'pants'
for ch in 'Ff':
    ROLE_OF[ch] = 'shoes'

MATERIALS = [  # (slot name, placeholder colour, cast.json field that tints it at runtime)
    ('mat_skin', '#e8c4a0', 'skin'),
    ('mat_hair', '#6a5a50', 'hair'),
    ('mat_top', '#b0b0b8', 'shirt (coat for body=coat)'),
    ('mat_pants', '#80808a', 'pants'),
    ('mat_shoes', '#606068', 'shoes'),
]
EXTRA_MATERIALS = [('mat_eye', '#1b1a2e', None), ('mat_hat', '#a0a0a8', 'hat')]


def resolve_grid(rows):
    """Region-code rows -> role grid; outline cells 'O' take their most common neighbour role."""
    H, W = len(rows), 16
    g = [[ROLE_OF.get(rows[r][c]) if c < len(rows[r]) and rows[r][c] not in '.O' else None
          for c in range(W)] for r in range(H)]
    out = [row[:] for row in g]
    for r in range(H):
        for c in range(W):
            if c < len(rows[r]) and rows[r][c] == 'O':
                cnt = {}
                for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                    rr, cc = r + dr, c + dc
                    if 0 <= rr < H and 0 <= cc < W and g[rr][cc] and g[rr][cc] != 'eye':
                        w = 2 if dr == 0 or dc == 0 else 1
                        cnt[g[rr][cc]] = cnt.get(g[rr][cc], 0) + w
                out[r][c] = max(cnt, key=cnt.get) if cnt else None
    return out


def main():
    args = C.parse_args()
    head_style = args[args.index('--head') + 1] if '--head' in args else 'short'
    body_style = args[args.index('--body') + 1] if '--body' in args else 'normal'
    chars = json.load(open(os.path.join(EXTRACTED, 'chars.json')))
    head, body = chars['HEADS'][head_style], chars['BODY'][body_style]
    down = resolve_grid(head['down'] + body['down'][0])
    up = resolve_grid(head['up'] + body['up'][0])
    NR = len(down)
    filled = [r for r in range(NR) if any(down[r])]
    top_r, bot_r = min(filled), max(filled)
    s = TARGET_HEIGHT / (bot_r - top_r + 1)

    C.reset_scene()
    mats = C.MaterialCache()
    for name, col, _ in MATERIALS + EXTRA_MATERIALS:
        mats.add_named(name, col, roughness=0.6)
    mi = {n: mats.index['named:' + n] for n, _, _ in MATERIALS + EXTRA_MATERIALS}
    role_mat = {'skin': 'mat_skin', 'hair': 'mat_hair', 'top': 'mat_top', 'pants': 'mat_pants',
                'shoes': 'mat_shoes', 'eye': 'mat_eye', 'hat': 'mat_hat'}
    used_roles = set()

    def bone_for(r, c):
        if r < 12:
            return 'head'
        br = r - 12
        if br <= 5 and (c <= 4 or c >= 11):
            return 'arm_L' if c >= 8 else 'arm_R'   # +X is the character's left (front = -Y)
        if br >= 7:
            return 'leg_L' if c >= 8 else 'leg_R'
        if br >= 5:
            return 'hips'
        return 'spine'

    mb = C.MeshBuilder()
    for r in range(NR):
        row = down[r]
        c = 0
        while c < 16:
            if not row[c]:
                c += 1
                continue
            a = c
            while c < 16 and row[c]:
                c += 1
            run = (a, c)  # [a, c)
            half_w = (run[1] - run[0]) * 0.5
            mid = (run[0] + run[1]) * 0.5
            depth_k = 0.95 if r < 12 else 0.75
            for cc in range(run[0], run[1]):
                u = (cc + 0.5 - mid) / max(half_w, 0.5)
                d = max(0.6, half_w * depth_k * math.sqrt(max(0.0, 1 - u * u * 0.85)))
                x0, x1 = (cc - 8) * s, (cc - 7) * s
                z0 = (bot_r - r) * s
                z1 = z0 + s
                bone = bone_for(r, cc)
                fr = row[cc]
                br_ = up[r][15 - cc] or fr
                if br_ == 'eye':
                    br_ = fr
                used_roles.update((fr, br_))
                mb.box((x0, -d * s, z0), (x1, 0.0, z1), mi[role_mat[fr]], bone)
                mb.box((x0, 0.0, z0), (x1, d * s, z1), mi[role_mat[br_]], bone)
    mb.finish()
    # bone pivots from group bounds
    stats = {}
    for v in mb.bm.verts:
        g = mb.groups[v[mb.grp]]
        st = stats.setdefault(g, [Vector((1e9, 1e9, 1e9)), Vector((-1e9, -1e9, -1e9))])
        for i in range(3):
            st[0][i] = min(st[0][i], v.co[i])
            st[1][i] = max(st[1][i], v.co[i])

    def top_center(g):
        lo, hi = stats[g]
        return Vector(((lo.x + hi.x) / 2, 0, hi.z))

    def bottom_center(g):
        lo, hi = stats[g]
        return Vector(((lo.x + hi.x) / 2, 0, lo.z))
    bl = 0.12
    bones = [
        {'name': 'hips', 'head': bottom_center('hips') + Vector((0, 0, 0)), 'parent': None, 'length': bl},
        {'name': 'spine', 'head': bottom_center('spine'), 'parent': 'hips', 'length': bl},
        {'name': 'head', 'head': bottom_center('head'), 'parent': 'spine', 'length': bl * 2},
        {'name': 'arm_L', 'head': top_center('arm_L') - Vector((0, 0, s * 0.5)), 'parent': 'spine', 'length': bl},
        {'name': 'arm_R', 'head': top_center('arm_R') - Vector((0, 0, s * 0.5)), 'parent': 'spine', 'length': bl},
        {'name': 'leg_L', 'head': top_center('leg_L'), 'parent': 'hips', 'length': bl},
        {'name': 'leg_R', 'head': top_center('leg_R'), 'parent': 'hips', 'length': bl},
    ]
    obj = mb.to_object('humanoid', mats.mats)
    arm = C.build_armature('humanoid', bones, root_len=0.2)
    C.skin_to_armature(obj, arm)
    tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)

    X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))
    all_bones = ['root'] + [b['name'] for b in bones]
    idle = C.ActionWriter(arm, 'Idle', 60)
    for f in range(0, 61, 2):
        t = f / 60.0
        sn = math.sin(2 * math.pi * t)
        idle.key('hips', f, loc=(0, 0, -0.008 * (0.5 - 0.5 * math.cos(2 * math.pi * t))))
        idle.key('spine', f, scl=(1 + 0.015 * sn, 1 + 0.015 * sn, 1 + 0.01 * sn))
        idle.key('head', f, rot=(X, math.radians(2.0) * sn))
        idle.key('arm_L', f, rot=(Y, -math.radians(2.5) * sn))
        idle.key('arm_R', f, rot=(Y, math.radians(2.5) * sn))
    walk = C.ActionWriter(arm, 'Walk', 24)
    for f in range(0, 25):
        w = 2 * math.pi * f / 24.0
        walk.key('hips', f, loc=(0, 0, 0.03 * (0.5 - 0.5 * math.cos(2 * w))))
        walk.key('leg_L', f, rot=(X, math.radians(30) * math.sin(w)))
        walk.key('leg_R', f, rot=(X, -math.radians(30) * math.sin(w)))
        walk.key('arm_L', f, rot=(X, -math.radians(25) * math.sin(w)))
        walk.key('arm_R', f, rot=(X, math.radians(25) * math.sin(w)))
        walk.key('spine', f, rot=(Z, math.radians(4) * math.sin(w)))
        walk.key('head', f, rot=(Z, -math.radians(3) * math.sin(w)))
    C.stash_actions(arm, [idle.write(all_bones), walk.write(all_bones)])
    # drop the unused hat material slot if the base head has no hat cells
    if 'hat' not in used_roles:
        idx = obj.data.materials.find('mat_hat')
        if idx >= 0:
            obj.data.materials.pop(index=idx)
    C.ensure_dir(OUT_DIR)
    path = os.path.join(OUT_DIR, 'humanoid.glb')
    C.export_glb(path)
    manifest = {
        'file': 'humanoid.glb',
        'base_style': {'head': head_style, 'body': body_style, 'source': 'chars.json HEADS/BODY, down frame 0 (front) + up frame 0 (back)'},
        'height_m': TARGET_HEIGHT,
        'tris': tris,
        'material_slots': {n: {'placeholder': col, 'tint_from_cast_json': src} for n, col, src in MATERIALS},
        'fixed_materials': {'mat_eye': 'dark eye colour, not tinted'} if 'eye' in used_roles else {},
        'optional_materials': {'mat_hat': 'present only when the base head style has hat cells (C/c/K/B); tint from cast.json "hat"'},
        'region_code_roles': {'skin': 'S s W M', 'eye': 'E', 'hair': 'H h L', 'top': 'T t U A X x G g',
                              'pants': 'P p', 'shoes': 'F f', 'hat': 'C c K B', 'outline O': 'takes neighbouring role'},
        'bones': all_bones,
        'animations': {'Idle': {'seconds': 2.0, 'loop': True}, 'Walk': {'seconds': 0.8, 'loop': True}},
        'conventions': {'front': 'Blender -Y == glTF/Godot +Z', 'origin': 'bottom centre (feet at y=0)'},
        'notes': ('v1 approach: ONE base mesh for every humanoid in cast.json, recoloured at runtime by '
                  'setting the mat_* slots from each cast entry\'s hex fields (skin/hair/shirt/pants/shoes). '
                  'Per-style mesh variants (hats/caps, hairstyles, coats, dresses, backpacks, glasses) are a '
                  'documented future extension and out of scope for this pass; gen_characters.py already takes '
                  '--head/--body to voxelize any other HEADS/BODY style.'),
    }
    with open(os.path.join(OUT_DIR, 'manifest.json'), 'w') as fh:
        json.dump(manifest, fh, indent=1)
    print('DONE humanoid tris=%d bytes=%d' % (tris, os.path.getsize(path)))


if __name__ == '__main__':
    main()
