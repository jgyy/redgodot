"""3D battle stages for every upstream battle environment (src/art/battlebg.js THEMES),
generated with headless Blender.

    python3 pipeline/blender/gen_battlebg.py            # all envs
    python3 pipeline/blender/gen_battlebg.py -- grass   # one env

Output: godot/assets/models/battle/bg_<env>.glb, platform_<kind>.glb, layout.json

How the parity works: the battle camera is fixed (CAM below == BattleStage.gd reads
layout.json), so every prop is placed along the camera ray through the pixel where
upstream paints it in its 320x132 battle framebuffer, at a chosen depth. Clouds,
hills, tree lines, stalactites, icicles, pipes and pillars are real 3D meshes
(toon-shaded with upstream's own 3-tone palettes); the sky / walls / ground / sea
are real 3D planes whose UVs are the camera projection of upstream's own
procedural pixel painting (ported in upstream_px.py), so from the battle camera
they read exactly as the 2D game while still being lit 3D surfaces that receive
the Pokémon's shadows.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
import bpy  # noqa: E402
import bmesh  # noqa: E402
import upstream_px as U  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(ROOT, 'godot', 'assets', 'models', 'battle')

# ------------------------------------------------------------------ camera model (Godot coords: Y up, -Z forward)
CAM = {'pos': [0.0, 1.6, 0.0], 'pitch': -11.5, 'fov': 34.0, 'w': 960, 'h': 540}
_P = math.radians(CAM['pitch'])
_F = np.array([0.0, math.sin(_P), -math.cos(_P)])
_UP = np.array([0.0, math.cos(_P), math.sin(_P)])
_R = np.array([1.0, 0.0, 0.0])
_TH = math.tan(math.radians(CAM['fov']) / 2)
_C = np.array(CAM['pos'])


def ray(px, py):
    """Direction of the camera ray through upstream pixel (px, py) (320x180 space)."""
    u, v = px * 3.0, py * 3.0
    sx = (u - CAM['w'] / 2) / (CAM['h'] / 2) * _TH
    sy = (CAM['h'] / 2 - v) / (CAM['h'] / 2) * _TH
    d = _F + sx * _R + sy * _UP
    return d / np.linalg.norm(d)


def at_depth(px, py, depth):
    d = ray(px, py)
    return _C + d * (depth / float(np.dot(d, _F)))


def ground_hit(px, py, y=0.0):
    d = ray(px, py)
    if d[1] >= -1e-6:
        return None
    t = (y - _C[1]) / d[1]
    return _C + d * t


def to_px(p):
    v = np.array(p) - _C
    z = float(np.dot(v, _F))
    sx = float(np.dot(v, _R)) / z / _TH
    sy = float(np.dot(v, _UP)) / z / _TH
    return ((sx * CAM['h'] / 2 + CAM['w'] / 2) / 3.0, (CAM['h'] / 2 - sy * CAM['h'] / 2) / 3.0)


def px_scale(depth):
    """World metres per upstream pixel at a given depth."""
    return 3.0 * depth * _TH / (CAM['h'] / 2)


def B(p):
    """Godot (x, y, z) -> Blender (x, -z, y) (the glTF exporter converts back)."""
    return (float(p[0]), float(-p[2]), float(p[1]))


# ------------------------------------------------------------------ blender helpers
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


_mats = {}


def _principled(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m, m.node_tree.nodes.get('Principled BSDF')


def mat_color(name, hexcol, rough=0.9, alpha=1.0, emit=None):
    key = (name, hexcol, alpha)
    if key in _mats:
        return _mats[key]
    m, bsdf = _principled(name)
    c = U.hexc(hexcol) if isinstance(hexcol, str) else hexcol
    lin = [_lin(c[0]), _lin(c[1]), _lin(c[2]), 1.0]
    bsdf.inputs['Base Color'].default_value = lin
    bsdf.inputs['Roughness'].default_value = rough
    if 'Specular IOR Level' in bsdf.inputs:
        bsdf.inputs['Specular IOR Level'].default_value = 0.1
    if alpha < 1.0:
        bsdf.inputs['Alpha'].default_value = alpha
        try:
            m.surface_render_method = 'BLENDED'
        except Exception:
            pass
        m.blend_method = 'BLEND'
    if emit:
        bsdf.inputs['Emission Color'].default_value = lin
        bsdf.inputs['Emission Strength'].default_value = emit
    _mats[key] = m
    return m


def _lin(v):
    c = v / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def image_from_surf(name, s):
    img = bpy.data.images.new(name, s.w, s.h, alpha=True)
    a = s.a.astype(np.float32) / 255.0
    a = a[::-1, :, :]  # blender rows are bottom-up
    img.pixels.foreach_set(a.ravel())
    img.pack()
    return img


def mat_image(name, s, rough=0.9, alpha_blend=False):
    m, bsdf = _principled(name)
    tex = m.node_tree.nodes.new('ShaderNodeTexImage')
    tex.image = image_from_surf(name + '_tex', s)
    tex.interpolation = 'Closest'
    tex.extension = 'EXTEND'
    m.node_tree.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    if alpha_blend:
        m.node_tree.links.new(tex.outputs['Alpha'], bsdf.inputs['Alpha'])
        m.blend_method = 'CLIP'
    bsdf.inputs['Roughness'].default_value = rough
    if 'Specular IOR Level' in bsdf.inputs:
        bsdf.inputs['Specular IOR Level'].default_value = 0.1
    return m


def make_obj(name, verts, faces, mats, face_mat=None, uvs=None, smooth=False):
    """verts in Godot coords; uvs: per-vertex (u, v) with v up."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([B(v) for v in verts], [], faces)
    me.update()
    for m in mats:
        me.materials.append(m)
    if face_mat is not None:
        for i, p in enumerate(me.polygons):
            p.material_index = face_mat[i]
    for p in me.polygons:
        p.use_smooth = smooth
    if uvs is not None:
        uvl = me.uv_layers.new(name='UVMap')
        for li, loop in enumerate(me.loops):
            uvl.data[li].uv = uvs[loop.vertex_index]
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def screen_uv(p, sw=320.0, sh=180.0):
    x, y = to_px(p)
    return (x / sw, 1.0 - y / sh)


def projected_grid(name, corner_fn, nu, nv, mat, sw=320.0, sh=180.0):
    """A (nu x nv) grid mesh from corner_fn(i/nu, j/nv) -> Godot point, UV = camera projection."""
    verts, uvs, faces = [], [], []
    for j in range(nv + 1):
        for i in range(nu + 1):
            p = corner_fn(i / nu, j / nv)
            verts.append(p)
            uvs.append(screen_uv(p, sw, sh))
    for j in range(nv):
        for i in range(nu):
            a = j * (nu + 1) + i
            faces.append((a, a + 1, a + nu + 2, a + nu + 1))
    return make_obj(name, verts, faces, [mat], uvs=uvs)


def export(path):
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', export_apply=True, export_yup=True,
                              export_animations=False, export_materials='EXPORT')


# ------------------------------------------------------------------ layout
def layout():
    """Anchors for Godot: platform centres/radii from upstream's ellipses."""
    def plat(cx, cy, rx, ry, top):
        c = ground_hit(cx, cy, top)
        left = ground_hit(cx - rx, cy, top)
        front = ground_hit(cx, cy + ry, top)
        back = ground_hit(cx, cy - ry, top)
        return {'center': [float(c[0]), top, float((front[2] + back[2]) / 2)],
                'rx': float(abs(c[0] - left[0])), 'rz': float(abs(front[2] - back[2]) / 2)}
    e = plat(236, 78, 62, 14, 0.14)
    p = plat(84, 130, 76, 16, 0.14)
    # the 2D art's ellipse is deeper than a camera this low would see; keep the enemy
    # platform shallow enough that it stays in front of the tree line.
    e['rz'] = min(e['rz'], 1.55)
    p['rz'] = min(p['rz'], 1.0)
    return {'camera': CAM, 'enemy': e, 'player': p}


LAYOUT = None
# enclosed rooms put their back wall just behind the enemy platform's back edge
WALL_D = 12.4
TREE_D = 12.1


def wall_row():
    """Screen row where the ground meets a wall at WALL_D."""
    return to_px(np.array([0.0, 0.0, -WALL_D]))[1]


# ------------------------------------------------------------------ props
def cloud_props(y0, y1, seed, col, sh, depth=70.0):
    wm, sm = mat_color('cloud_white', col), mat_color('cloud_shadow', sh)
    verts, faces, fm = [], [], []
    for ci, blobs in enumerate(U.cloud_blobs(y0, y1, seed)):
        d = depth + ci * 3.0
        for bx, by, r in blobs:
            c = at_depth(bx, by, d)
            rad = r * px_scale(d)
            bm = bmesh.new()
            bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
            base = len(verts)
            for v in bm.verts:
                x, y, z = v.co.x, v.co.z, -v.co.y  # to godot-ish local
                verts.append((c[0] + x * rad, c[1] + y * rad * 0.92, c[2] + z * rad * 0.35))
            for f in bm.faces:
                idx = [base + v.index for v in f.verts]
                cy = sum(verts[i][1] for i in idx) / len(idx)
                faces.append(tuple(idx))
                fm.append(1 if cy < c[1] - rad * 0.25 else 0)
            bm.free()
    make_obj('clouds', verts, faces, [wm, sm], face_mat=fm)


def hill_prop(name, base, amp, freq, seed, col, col_hi, depth, painter_h=180):
    s = U.Surf(320, painter_h)
    hs = U.paint_hills(s, base, amp, freq, seed, U.hexc(col), U.hexc(col_hi))
    mat = mat_image('unlit_' + name, s)
    verts, uvs, faces = [], [], []
    xs = list(range(-8, 330, 3))
    rows = 4
    for x in xs:
        xi = min(319, max(0, x))
        top = hs[xi]
        for r in range(rows + 1):
            yy = top + (base + 30 - top) * r / rows
            bulge = math.sin(r / rows * math.pi * 0.5) * 3.0
            p = at_depth(x, yy, depth - bulge)
            verts.append(p)
            uvs.append(screen_uv(at_depth(x, yy, depth)))
    for i in range(len(xs) - 1):
        for r in range(rows):
            a = i * (rows + 1) + r
            faces.append((a, a + rows + 1, a + rows + 2, a + 1))
    make_obj(name, verts, faces, [mat], uvs=uvs)


def _toon_mats(prefix, cols):
    return [mat_color('unlit_%s%d' % (prefix, i), cols[i]) for i in range(3)]


def _lit_index(n):
    # upstream: lit = dx*-0.6 + dy*-0.8 (y down) -> light from the upper left (and a bit from the front)
    lit = n[0] * -0.6 + n[1] * 0.8 + n[2] * 0.15
    return 2 if lit > 0.35 else (1 if lit > -0.2 else 0)


def tree_line(name, base, seed, cols, depth, jitter=1.5, ground_y=0.0, crown_scale=1.0):
    mats = _toon_mats(name, cols)
    verts, faces, fm = [], [], []
    for k, (cx, cy, r) in enumerate(U.tree_specs(base, seed)):
        d = depth + U.hash2(k, 7, seed) * jitter
        c = at_depth(cx, cy, d)
        rad = r * px_scale(d) * crown_scale
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
        base_i = len(verts)
        for v in bm.verts:
            x, y, z = v.co.x, v.co.z, -v.co.y
            wob = 1.0 + 0.08 * math.sin(x * 5 + k) * math.cos(y * 4 + k * 0.7)
            verts.append((c[0] + x * rad * wob, c[1] + y * rad * wob, c[2] + z * rad * 0.8 * wob))
        for f in bm.faces:
            idx = [base_i + v.index for v in f.verts]
            faces.append(tuple(idx))
            n = f.normal
            fm.append(_lit_index((n.x, n.z, -n.y)))
        bm.free()
        # the solid lower mass (upstream fills the tree's width down to the ground)
        seg = 10
        top_y = c[1]
        bot_y = ground_y - 0.2
        ring_t, ring_b = [], []
        for i in range(seg):
            a = math.pi * 2 * i / seg
            nx, nz = math.cos(a), math.sin(a)
            ring_t.append(len(verts))
            verts.append((c[0] + nx * rad * 0.97, top_y, c[2] + nz * rad * 0.78))
            ring_b.append(len(verts))
            verts.append((c[0] + nx * rad * 0.97, bot_y, c[2] + nz * rad * 0.78))
        for i in range(seg):
            j = (i + 1) % seg
            faces.append((ring_t[i], ring_b[i], ring_b[j], ring_t[j]))
            a = math.pi * 2 * (i + 0.5) / seg
            fm.append(_lit_index((math.cos(a), 0.0, math.sin(a))))
    make_obj(name, verts, faces, mats, face_mat=fm)


def cones_hanging(name, count, seed, len_px, w_px, cols, depth, edge_col=None, y_top=-8):
    """Stalactites / icicles: upstream draws count triangles from the top edge."""
    mats = [mat_color('unlit_%s_l' % name, cols[0]), mat_color('unlit_%s_d' % name, cols[1])]
    if edge_col:
        mats.append(mat_color('unlit_%s_e' % name, edge_col))
    verts, faces, fm = [], [], []
    for k in range(count):
        x = U.hash2(k, 1, seed) * 320
        l = len_px[0] + U.hash2(k, 2, seed) * len_px[1]
        w = w_px[0] + U.hash2(k, 3, seed) * w_px[1]
        d = depth + U.hash2(k, 4, seed) * 2.0
        top = at_depth(x, y_top, d)
        tip = at_depth(x, l, d)
        rad = w * px_scale(d)
        seg = 7
        base_i = len(verts)
        for i in range(seg):
            a = math.pi * 2 * i / seg
            verts.append((top[0] + math.cos(a) * rad, top[1], top[2] + math.sin(a) * rad * 0.9))
        verts.append(tuple(tip))
        for i in range(seg):
            j = (i + 1) % seg
            faces.append((base_i + i, base_i + j, base_i + seg))
            a = math.pi * 2 * (i + 0.5) / seg
            nx = -math.cos(a)
            if edge_col and i == seg // 2:
                fm.append(2)
            else:
                fm.append(0 if nx > 0.1 else 1)
    make_obj(name, verts, faces, mats, face_mat=fm)


# ------------------------------------------------------------------ backdrop planes
def sky_plane(s, depth=90.0, name='sky'):
    mat = mat_image(name, s)

    def corner(u, v):
        return at_depth(-10 + u * 340, -10 + v * 200, depth)
    projected_grid(name, corner, 4, 4, mat)


def ground_plane(s, near=-0.5, far=None, name='ground', y=0.0, xw=40.0, lit=True, nu=48, nv=40):
    mat = mat_image(name if lit else 'unlit_' + name, s, rough=0.95)

    def corner(u, v):
        z = -(near + (far - near) * (v ** 1.6))
        x = (u - 0.5) * 2 * (xw * (0.35 + 0.65 * v))
        return np.array([x, y, z])
    projected_grid(name, corner, nu, nv, mat)


def wall_plane(s, depth, name='wall', y_bottom=-1.0, y_top=None, lit=False):
    mat = mat_image(name if lit else 'unlit_' + name, s)

    def corner(u, v):
        top = at_depth(0, -12, depth)[1] if y_top is None else y_top
        x = (u - 0.5) * 2 * depth * 1.2
        return np.array([x, top + (y_bottom - top) * v, -depth])
    projected_grid(name, corner, 24, 16, mat)


def horizon_depth(y_px):
    """Ground distance (along -Z) where the ground plane projects to screen row y_px."""
    g = ground_hit(160, y_px)
    return float(-g[2])


# ------------------------------------------------------------------ environments
def paint_full(fn, h=180):
    s = U.Surf(320, h)
    fn(s)
    return s


def env_grass():
    sky = paint_full(lambda s: U.vgrad(s, 0, 60, U.hexc('#6cb0f0'), U.hexc('#d8f0ff'), 6) or U.vgrad(s, 60, 180, U.hexc('#d8f0ff'), U.hexc('#d8f0ff'), 1))
    sky_plane(sky)
    cloud_props(8, 36, 3, '#ffffff', '#d8e4f4')
    hill_prop('unlit_hills_far', 56, 16, 0.02, 1, '#8cb8b8', '#a8d0c8', 48.0)
    hill_prop('unlit_hills_near', 64, 10, 0.035, 4, '#5a9a70', '#78b880', 34.0)
    tree_line('trees', 76, 9, ['#1f5a3a', '#2f7a44', '#4c9a4c'], TREE_D, jitter=1.2)
    g = paint_full(lambda s: U.paint_ground(s, 60, U.hexc('#7cc05a'), U.hexc('#6cb050'), U.hexc('#9ad870'), 7))
    ground_plane(g, far=TREE_D + 0.8)


def env_forest():
    sky = paint_full(lambda s: U.vgrad(s, 0, 180, U.hexc('#1c3a2e'), U.hexc('#2e5a3a'), 6))
    sky_plane(sky)
    tree_line('trees_far', 40, 2, ['#0f2a22', '#163a2a', '#1f4e32'], 26.0, jitter=1.0)
    tree_line('trees_mid', 62, 5, ['#15382a', '#1f5034', '#2c6a3e'], 17.0, jitter=1.0)
    tree_line('trees', 80, 7, ['#1a4830', '#27663c', '#3a8446'], TREE_D, jitter=0.8)
    g = paint_full(lambda s: U.paint_ground(s, 66, U.hexc('#3c7a3e'), U.hexc('#346e38'), U.hexc('#58964c'), 6))
    ground_plane(g, far=TREE_D + 0.6)
    # light shafts: slanted translucent quads (upstream blends #e8f8b0 at 25% in bayer-dithered bands)
    m = mat_color('unlit_shaft', '#e8f8b0', alpha=0.08)
    verts, faces = [], []
    for k in range(4):
        x0 = 40 + k * 80
        d = 9.0 + k * 0.7
        a, b = at_depth(x0, -5, d), at_depth(x0 + 10, -5, d)
        c, e = at_depth(x0 + 10 + 132 * 0.4, 132, d), at_depth(x0 + 132 * 0.4, 132, d)
        i = len(verts)
        verts += [a, b, c, e]
        faces.append((i, i + 1, i + 2, i + 3))
    make_obj('unlit_shafts', verts, faces, [m])


def _cave_wall(s):
    U.vgrad(s, 0, 180, U.hexc('#16121c'), U.hexc('#3a2e30'), 5)
    for y in range(132):
        for x in range(320):
            n = U.N('mid').at(x * 1.5, y * 2.5)
            m = U.N('big').at(x, y)
            if y < 70 and n > 0.55 - y / 300:
                s.pset(x, y, U.mix(U.hexc('#2a2230'), U.hexc('#4a3c3c'), m * 0.8))


def env_cave():
    wall = paint_full(_cave_wall)
    hd = WALL_D
    wall_plane(wall, hd, name='cave_wall')
    cones_hanging('stalactites', 18, 4, (8, 26), (3, 4), ['#5a4a44', '#3a302e'], hd - 1.0)
    g = paint_full(lambda s: U.paint_ground(s, int(wall_row()) - 2, U.hexc('#5a4a42'), U.hexc('#4e4038'), U.hexc('#6e5c50'), 5))
    ground_plane(g, far=hd)
    # boulders at the foot of the wall
    rock_m = [mat_color('rock_d', '#3a302e'), mat_color('rock_m', '#54443a'), mat_color('rock_l', '#6a5848')]
    verts, faces, fm = [], [], []
    for k in range(9):
        x = U.hash2(k, 1, 44) * 320
        d = hd - 0.3
        c = ground_hit(x, wall_row() + 1)
        if c is None:
            continue
        rad = (6 + U.hash2(k, 2, 44) * 10) * px_scale(d)
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
        bi = len(verts)
        for v in bm.verts:
            x2, y2, z2 = v.co.x, v.co.z, -v.co.y
            j = 1.0 + 0.25 * U.hash2(k, v.index, 45)
            verts.append((c[0] + x2 * rad * j, max(-0.1, y2 * rad * 0.7 * j), c[2] + z2 * rad * 0.8 * j))
        for f in bm.faces:
            faces.append(tuple(bi + v.index for v in f.verts))
            n = f.normal
            fm.append(_lit_index((n.x, n.z, -n.y)))
        bm.free()
    make_obj('boulders', verts, faces, rock_m, face_mat=fm)


def _ice_wall(s):
    U.vgrad(s, 0, 180, U.hexc('#0e2038'), U.hexc('#2e5e8e'), 6)
    for y in range(80):
        for x in range(320):
            n = U.N('mid').at(x * 1.4 + 17, y * 2.2)
            m = U.N('big').at(x * 0.8 + 30, y)
            if n > 0.5 - y / 260:
                s.pset(x, y, U.mix(U.hexc('#24507e'), U.hexc('#5e96c4'), math.floor(m * 4) / 4))
            if 0.5 - y / 260 < n < 0.53 - y / 260:
                s.pset(x, y, U.hexc('#9ccbe8'))


def env_ice():
    wall = paint_full(_ice_wall)
    hd = WALL_D
    wall_plane(wall, hd, name='ice_wall')
    cones_hanging('icicles', 22, 14, (10, 30), (2.5, 4), ['#a8d8f4', '#5a96c6'], hd - 1.0, edge_col='#f0fbff')
    g = paint_full(lambda s: U.paint_ground(s, int(wall_row()) - 2, U.hexc('#b4d8ee'), U.hexc('#a4cce6'), U.hexc('#eef9ff'), 5))
    ground_plane(g, far=hd)


def _sea(s, y0, c0='#3a78c8', c1='#1e4a98', hi='#8ac8f8', mid='#6aa8e8', span=74):
    for y in range(y0, 180):
        t = min(1.0, (y - y0) / span)
        for x in range(320):
            c = U.mix(U.hexc(c0), U.hexc(c1), t)
            w = math.sin(x * 0.08 + y * 0.9 + math.sin(y * 0.3) * 2)
            if w > 0.9 - t * 0.2:
                c = U.hexc(hi)
            elif w > 0.75:
                c = U.mix(c, U.hexc(mid), 0.6)
            s.pset(x, y, c)
    for x in range(320):
        s.pset(x, y0, U.hexc('#e8f8ff'))


def env_water(beach=False):
    sky = paint_full(lambda s: U.vgrad(s, 0, 58, U.hexc('#58a0e8'), U.hexc('#d0ecff'), 6) or U.vgrad(s, 58, 180, U.hexc('#d0ecff'), U.hexc('#d0ecff'), 1))
    sky_plane(sky)
    cloud_props(6, 34, 11, '#ffffff', '#d0dcf0')

    def sea(s):
        _sea(s, 58)
        if beach:
            U.paint_ground(s, 96, U.hexc('#f0dca0'), U.hexc('#e8d090'), U.hexc('#fff0c0'), 4)
    g = paint_full(sea)
    hd = horizon_depth(57.5)
    ground_plane(g, far=hd, name='sea' if not beach else 'beach', nu=64, nv=60)


def env_indoor(gym=False):
    def wall(s):
        for y in range(180):
            for x in range(320):
                c = U.hexc('#d8d0c0')
                if y > 60:
                    c = U.hexc('#b8ae9c')
                if x % 40 == 0:
                    c = U.hexc('#c4bca8')
                if y % 20 == 0 and y < 60:
                    c = U.hexc('#e4dccc')
                if gym and y < 60 and (x + y) % 32 < 2:
                    c = U.hexc('#c0a878')
                s.pset(x, y, c)

    def floor(s):
        y0 = int(wall_row()) - 1
        for y in range(y0, 180):
            t = (y - y0) / (132 - y0)
            for x in range(320):
                px = (x - 160) / (0.4 + t) + 160
                tile = (math.floor(px / 24) + math.floor((y - y0) / (6 + t * 10))) % 2
                s.pset(x, y, U.hexc('#a8b8c8') if tile else U.hexc('#98a8b8'))
    hd = WALL_D
    wall_plane(paint_full(wall), hd, name='indoor_wall')
    ground_plane(paint_full(floor), far=hd, name='indoor_floor')


def env_tower():
    def back(s):
        U.vgrad(s, 0, 180, U.hexc('#1e1630'), U.hexc('#4a3a5a'), 6)
        for y in range(132):
            for x in range(320):
                f = U.N('big').at(x * 0.6 + 40, y * 1.2)
                if f > 0.6:
                    s.pset(x, y, U.mix(s.get(x, y), U.hexc('#9a8ab8'), (f - 0.6) * 0.8))
    hd = WALL_D
    wall_plane(paint_full(back), hd, name='tower_wall')
    g = paint_full(lambda s: U.paint_ground(s, int(wall_row()) - 2, U.hexc('#4a3e5a'), U.hexc('#40364e'), U.hexc('#5e5070'), 5))
    ground_plane(g, far=hd)


def env_mountain():
    sky = paint_full(lambda s: U.vgrad(s, 0, 60, U.hexc('#78a8e0'), U.hexc('#e0eef8'), 6) or U.vgrad(s, 60, 180, U.hexc('#e0eef8'), U.hexc('#e0eef8'), 1))
    sky_plane(sky)
    hill_prop('unlit_mtn_far', 50, 30, 0.03, 7, '#8a7a70', '#b0a090', 44.0)
    hill_prop('unlit_mtn_near', 68, 18, 0.05, 2, '#a08a70', '#c8b090', 26.0)
    g = paint_full(lambda s: U.paint_ground(s, 60, U.hexc('#c0a882'), U.hexc('#b09a76'), U.hexc('#d8c4a0'), 6))
    ground_plane(g, far=TREE_D + 0.8)


def env_power():
    def wall(s):
        for y in range(180):
            for x in range(320):
                px, py = x % 40, y % 26
                c = U.hexc('#343c48')
                if px == 0 or py == 0:
                    c = U.hexc('#1c2029')
                elif px == 1 or py == 1:
                    c = U.hexc('#4c5664')
                elif px in (4, 35) and py in (4, 21):
                    c = U.hexc('#7a8494')
                elif U.N('fine').at(x * 2, y * 3) > 0.8:
                    c = U.hexc('#3a4250')
                s.pset(x, y, c)
        for y in range(74, 80):
            for x in range(320):
                s.pset(x, y, U.hexc('#e8c020') if ((x + y) >> 2) & 1 else U.hexc('#1a1a1c'))
    hd = WALL_D
    wall_plane(paint_full(wall), hd, name='power_wall')

    def floor(s):
        U.paint_ground(s, int(wall_row()) - 2, U.hexc('#4a525e'), U.hexc('#424954'), U.hexc('#6a7482'), 5)
        for y in range(80, 180):
            for x in range(320):
                if (x + (y - 80) * 3) % 64 == 0 or (y - 80) % 14 == 0:
                    s.pset(x, y, U.hexc('#363c46'))
    ground_plane(paint_full(floor), far=hd, name='power_floor')
    # conduits: real pipes along the wall (upstream paints two at y=18 and y=50)
    for y0, r, cols in [(18, 3, ['#d8a860', '#a87838']), (50, 2, ['#9aa8b8', '#6a7888'])]:
        d = hd
        a, b = at_depth(-20, y0, d), at_depth(340, y0, d)
        rad = r * px_scale(d)
        bm = bmesh.new()
        seg = 10
        verts, faces, fm = [], [], []
        for end in (a, b):
            for i in range(seg):
                ang = math.pi * 2 * i / seg
                verts.append((end[0], end[1] + math.cos(ang) * rad, end[2] + math.sin(ang) * rad))
        for i in range(seg):
            j = (i + 1) % seg
            faces.append((i, j, seg + j, seg + i))
            fm.append(0 if math.cos(math.pi * 2 * (i + 0.5) / seg) > 0 else 1)
        bm.free()
        make_obj('pipe%d' % y0, verts, faces, [mat_color('pipe_hi%d' % y0, cols[0]), mat_color('pipe_lo%d' % y0, cols[1])], face_mat=fm)


def env_mansion():
    def wall(s):
        for y in range(180):
            for x in range(320):
                c = U.hexc('#6a3a3c') if (x >> 3) & 1 else U.hexc('#5c3236')
                if x % 16 == 4 and y % 12 == 6:
                    c = U.hexc('#8a5a4a')
                if y >= 62:
                    c = U.hexc('#a07a52') if y == 62 else (U.hexc('#2a1c14') if y == 63 else (U.hexc('#3a281c') if x % 24 == 0 else U.hexc('#4e3624')))
                burn = U.N('big').at(x * 0.9 + 11, y * 1.4)
                if burn > 0.6:
                    c = U.mix(c, U.hexc('#1a1210'), min(1, math.floor((burn - 0.6) * 10) / 4))
                s.pset(x, y, c)
    hd = WALL_D
    wall_plane(paint_full(wall), hd, name='mansion_wall')

    def floor(s):
        U.paint_ground(s, int(wall_row()) - 2, U.hexc('#6a4e38'), U.hexc('#5e4430'), U.hexc('#8a6a4a'), 6)
        for y in range(84, 180):
            if (y - 84) % 9 == 0:
                for x in range(320):
                    s.pset(x, y, U.hexc('#46321f'))
    ground_plane(paint_full(floor), far=hd, name='mansion_floor')


def env_elite(tint='#6a4a9a'):
    c = U.hexc(tint)

    def back(s):
        U.vgrad(s, 0, 180, U.shade(c, -0.55), U.shade(c, -0.1), 6)
    hd = WALL_D
    wall_plane(paint_full(back), hd, name='elite_wall')
    g = paint_full(lambda s: U.paint_ground(s, int(wall_row()) - 2, U.shade(c, -0.35), U.shade(c, -0.42), U.shade(c, -0.15), 5))
    ground_plane(g, far=hd, name='elite_floor')
    mats = [mat_color('pillar_hi', U.shade(c, 0.35)), mat_color('pillar_mid', U.shade(c, 0.2)), mat_color('pillar_lo', U.shade(c, -0.3))]
    verts, faces, fm = [], [], []
    for k in range(8):
        x0 = k * 44 + 10
        d = hd
        base = at_depth(x0 + 1, 90, d)
        top = at_depth(x0 + 1, -10, d)
        rad = 2.5 * px_scale(d)
        seg = 8
        bi = len(verts)
        for i in range(seg):
            ang = math.pi * 2 * i / seg
            verts.append((base[0] + math.cos(ang) * rad, base[1], base[2] + math.sin(ang) * rad))
            verts.append((base[0] + math.cos(ang) * rad, top[1], base[2] + math.sin(ang) * rad))
        for i in range(seg):
            j = (i + 1) % seg
            faces.append((bi + 2 * i, bi + 2 * j, bi + 2 * j + 1, bi + 2 * i + 1))
            nx = math.cos(math.pi * 2 * (i + 0.5) / seg)
            fm.append(0 if nx < -0.3 else (1 if nx < 0.4 else 2))
        make_obj('pillars', verts, faces, mats, face_mat=fm) if k == 7 else None


def env_cavewater(ice=False):
    wall = paint_full(_ice_wall if ice else _cave_wall)
    hd = WALL_D
    wall_plane(wall, hd, name='cw_wall')
    if ice:
        cones_hanging('icicles', 22, 14, (10, 30), (2.5, 4), ['#a8d8f4', '#5a96c6'], hd - 1.0, edge_col='#f0fbff')
    else:
        cones_hanging('stalactites', 18, 4, (8, 26), (3, 4), ['#5a4a44', '#3a302e'], hd - 1.0)
    c0, c1, hl = ('#3a7ab0', '#143866', '#b0e4ff') if ice else ('#24485a', '#0c1c28', '#5a8ca0')
    g = paint_full(lambda s: _sea(s, int(wall_row()) - 1, c0, c1, hl, hl, 62))
    ground_plane(g, far=hd, name='cave_sea')


ENVS = {
    'grass': env_grass, 'forest': env_forest, 'cave': env_cave, 'ice': env_ice,
    'water': lambda: env_water(False), 'beach': lambda: env_water(True),
    'indoor': lambda: env_indoor(False), 'gym': lambda: env_indoor(True), 'tower': env_tower,
    'mountain': env_mountain, 'power': env_power, 'mansion': env_mansion, 'elite': env_elite,
    'cavewater': lambda: env_cavewater(False), 'cavewater_ice': lambda: env_cavewater(True),
}


# ------------------------------------------------------------------ platforms
def platform(kind):
    cols = [U.hexc(c) for c in U.PLATFORM_COLS[kind]]
    paint_kind = U.PLATFORM_KIND[kind]
    top = U.paint_platform_top(96, cols, paint_kind)
    # alpha outside the ellipse (for the water ripple disc)
    mt = mat_image('plat_top_' + kind, top, rough=0.95)
    side_col = cols[0] if paint_kind == 'water' else U.shade(cols[0], -0.25)
    ms = mat_color('plat_side_' + kind, side_col)
    seg = 48
    h_top = 0.14
    h_bot = -0.06 if paint_kind != 'water' else 0.10
    verts, uvs, faces, fm = [(0.0, h_top, 0.0)], [(0.5, 0.5)], [], []
    for i in range(seg):
        a = math.pi * 2 * i / seg
        x, z = math.cos(a), math.sin(a)
        verts.append((x, h_top, z))
        uvs.append((0.5 + x * 0.5, 0.5 - z * 0.5))
    for i in range(seg):
        j = (i + 1) % seg
        faces.append((0, 1 + j, 1 + i))
        fm.append(0)
    # side skirt (flares slightly)
    base = len(verts)
    for i in range(seg):
        a = math.pi * 2 * i / seg
        x, z = math.cos(a), math.sin(a)
        verts.append((x, h_top, z))
        uvs.append((0, 0))
        verts.append((x * 1.03, h_bot, z * 1.03))
        uvs.append((0, 0))
    for i in range(seg):
        j = (i + 1) % seg
        faces.append((base + 2 * i, base + 2 * j, base + 2 * j + 1, base + 2 * i + 1))
        fm.append(1)
    make_obj('platform_' + kind, verts, faces, [mt, ms], face_mat=fm, uvs=uvs)


def main():
    global LAYOUT
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    os.makedirs(OUT, exist_ok=True)
    LAYOUT = layout()
    with open(os.path.join(OUT, 'layout.json'), 'w') as fh:
        json.dump(LAYOUT, fh, indent=1)
    print('layout', json.dumps(LAYOUT))
    print('horizon depths: 58->%.1f 70->%.1f 74->%.1f 80->%.1f' % (horizon_depth(58), horizon_depth(70), horizon_depth(74), horizon_depth(80)))
    todo = args or list(ENVS.keys()) + ['platforms']
    for name in todo:
        if name == 'platforms':
            for kind in U.PLATFORM_COLS:
                reset()
                _mats.clear()
                platform(kind)
                export(os.path.join(OUT, 'platform_%s.glb' % kind))
                print('platform', kind)
            continue
        reset()
        _mats.clear()
        ENVS[name]()
        path = os.path.join(OUT, 'bg_%s.glb' % name)
        export(path)
        print('env', name, os.path.getsize(path))


if __name__ == '__main__':
    main()
