"""Paint eye decals into a Pokemon's own base-colour atlas (headless Blender).

Why paint instead of adding eye quads: the cel shader ignores alpha, so an alpha-cut quad would show as a box, and a
quad hovering over the skin z-fights or floats when the rig moves the head.  Painting through the mesh's existing UVs
puts the eye exactly on the surface, at any depth, with zero extra geometry.  The decal texture is an existing game
texture from pipeline/data/eye_tex (see SOURCES.md).

An override entry looks like (fractions are of the model height H, x = to the model's left, z = up):

    "eye_decals": [{"tex": "pm0143_00_Face.png", "uv": [0.0, 0.75, 0.5, 1.0],   # cell of the atlas, v up
                    "x": 0.05, "z": 0.62, "w": 0.06, "h": 0.03, "rot": 0, "mirror": true}]
"""
import os

import numpy as np

import pokemon_eye_bake as EB

HERE = os.path.dirname(os.path.abspath(__file__))
EYE_TEX = os.path.abspath(os.path.join(HERE, '..', 'data', 'eye_tex'))


def _load_decal(name, key=None):
    import bpy
    tag = 'decal:' + name
    img = bpy.data.images.get(tag)
    if img is None:
        img = bpy.data.images.load(os.path.join(EYE_TEX, name), check_existing=False)
        img.name = tag
    w, h = img.size
    a = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(a)
    a = a.reshape(h, w, 4).copy()
    if key == 'dark':
        # opaque atlas with dark strokes on a plain background (Snorlax's Face sheet): alpha = how far a texel is
        # from the background colour, taken from the atlas corner
        bg = a[-1, 0, :3]
        a[..., 3] = np.clip(np.abs(a[..., :3] - bg).max(-1) * 3.0, 0, 1)
    return a


def _bilinear(tex, u, v):
    h, w = tex.shape[:2]
    x = np.clip(u * w - 0.5, 0, w - 1.001)
    y = np.clip(v * h - 0.5, 0, h - 1.001)
    x0, y0 = x.astype(int), y.astype(int)
    fx, fy = (x - x0)[..., None], (y - y0)[..., None]
    return (tex[y0, x0] * (1 - fx) * (1 - fy) + tex[y0, x0 + 1] * fx * (1 - fy)
            + tex[y0 + 1, x0] * (1 - fx) * fy + tex[y0 + 1, x0 + 1] * fx * fy)


def paint(me, spec, H, cache):
    """Paint one decal spec (and its mirror) into the atlases of `me`.  `cache` maps image name -> pixel array and
    is flushed by `flush`.  Returns the number of triangles painted."""
    decal = _load_decal(spec['tex'], spec.get('key'))
    u0, v0, u1, v1 = spec.get('uv', [0, 0, 1, 1])
    V = EB.verts(me)
    UV = EB.uv_array(me)
    tmat, tv, tl, _ = EB.loop_tris(me)
    P0, P1, P2 = V[tv[:, 0]], V[tv[:, 1]], V[tv[:, 2]]
    nrm = np.cross(P1 - P0, P2 - P0)
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-12)
    front = nrm[:, 1] < -0.05           # facing -Y (the model's front)
    cen = (P0 + P1 + P2) / 3
    painted = 0
    sides = [1.0, -1.0] if spec.get('mirror', True) else [1.0]
    for side in sides:
        cx, cz = spec['x'] * H * side, spec['z'] * H
        w, h = spec['w'] * H, spec['h'] * H
        rot = np.radians(spec.get('rot', 0.0)) * side
        rad = 0.75 * np.hypot(w, h)
        cand = np.nonzero(front & (np.hypot(cen[:, 0] - cx, cen[:, 2] - cz) < rad + 0.02 * H))[0]
        for t in cand:
            mat = me.materials[int(tmat[t])] if int(tmat[t]) < len(me.materials) else None
            img = EB.mat_image(mat)
            if img is None or img.size[0] == 0:
                continue
            if img.name not in cache:
                cache[img.name] = (img, EB.read_px(img))
            dst = cache[img.name][1]
            ih, iw = dst.shape[:2]
            px = UV[tl[t]] * np.array([iw, ih])
            x0, x1 = max(int(np.floor(px[:, 0].min())), 0), min(int(np.ceil(px[:, 0].max())), iw - 1)
            y0, y1 = max(int(np.floor(px[:, 1].min())), 0), min(int(np.ceil(px[:, 1].max())), ih - 1)
            if x1 < x0 or y1 < y0:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            a, b, c = px
            den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
            if abs(den) < 1e-9:
                continue
            l1 = ((b[1] - c[1]) * (gx - c[0]) + (c[0] - b[0]) * (gy - c[1])) / den
            l2 = ((c[1] - a[1]) * (gx - c[0]) + (a[0] - c[0]) * (gy - c[1])) / den
            l3 = 1 - l1 - l2
            inside = (l1 >= -0.01) & (l2 >= -0.01) & (l3 >= -0.01)
            if not inside.any():
                continue
            pos = l1[..., None] * P0[t] + l2[..., None] * P1[t] + l3[..., None] * P2[t]
            dx, dz = pos[..., 0] - cx, pos[..., 2] - cz
            rx = dx * np.cos(rot) + dz * np.sin(rot)
            rz = -dx * np.sin(rot) + dz * np.cos(rot)
            du = rx / w * side + 0.5      # left eye reads left-to-right, the right eye is its mirror image
            dv = rz / h + 0.5
            ok = inside & (du >= 0) & (du <= 1) & (dv >= 0) & (dv <= 1)
            if not ok.any():
                continue
            s = _bilinear(decal, u0 + du * (u1 - u0), v0 + dv * (v1 - v0))
            al = (s[..., 3:4] * ok[..., None]) * float(spec.get('opacity', 1.0))
            reg = dst[y0:y1 + 1, x0:x1 + 1]
            reg[..., :3] = reg[..., :3] * (1 - al) + s[..., :3] * al
            painted += 1
    return painted


def flush(cache):
    for img, arr in cache.values():
        EB.write_px(img, arr)


def apply(me, specs, H):
    cache = {}
    n = 0
    for sp in specs:
        n += paint(me, sp, H, cache)
    flush(cache)
    return n


# ------------------------------------------------------------------------------------------ flat-colour geometry patches
def _bvh(me):
    from mathutils.bvhtree import BVHTree
    me.calc_loop_triangles()
    verts = [tuple(v.co) for v in me.vertices]
    tris = [tuple(t.vertices) for t in me.loop_triangles]
    return BVHTree.FromPolygons(verts, tris)


def add_patches(me, specs, H):
    """Flat-colour ellipse discs laid on the surface (for models whose faces cannot be painted into a shared palette
    atlas, e.g. Gastly).  Each spec: {x, z, w, h, rot, color, lift, layer, cut} in fractions of H; `layer` orders
    overlapping discs (pupil over sclera), `cut` [dx, dz, sw, sh] makes a crescent by shifting the inner edge."""
    import math
    import bmesh
    import bpy
    from mathutils import Vector
    tree = _bvh(me)
    bm = bmesh.new()
    bm.from_mesh(me)
    mats = {}
    for sp in sorted(specs, key=lambda s: s.get('layer', 0)):
        col = tuple(sp['color']) + (1.0,)
        key = tuple(round(c, 3) for c in col)
        if key not in mats:
            m = bpy.data.materials.new('eye_%d' % len(mats))
            m.use_nodes = True
            bsdf = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
            bsdf.inputs['Base Color'].default_value = col
            bsdf.inputs['Metallic'].default_value = 0.0
            bsdf.inputs['Roughness'].default_value = 0.6
            me.materials.append(m)
            mats[key] = len(me.materials) - 1
        mi = mats[key]
        for side in ([1.0, -1.0] if sp.get('mirror', False) else [1.0]):
            cx, cz = sp['x'] * H * side, sp['z'] * H
            w, h = sp['w'] * H * 0.5, sp['h'] * H * 0.5
            rot = math.radians(sp.get('rot', 0.0)) * side
            lift = sp.get('lift', 0.004) * H * (1 + sp.get('layer', 0))
            centre = None
            ring = []
            for r_i, rr in enumerate((0.0, 0.5, 1.0)):
                pts = []
                n = 1 if r_i == 0 else 20
                for k in range(n):
                    a = 2 * math.pi * k / max(n, 1)
                    ex, ez = rr * w * math.cos(a), rr * h * math.sin(a)
                    x = cx + ex * math.cos(rot) - ez * math.sin(rot)
                    z = cz + ex * math.sin(rot) + ez * math.cos(rot)
                    hit, nrm, _, _ = tree.ray_cast(Vector((x, -4 * H, z)), Vector((0, 1, 0)))
                    if hit is None:
                        pts.append(None)
                    else:
                        pts.append(bm.verts.new(hit + nrm.normalized() * lift))
                ring.append(pts)
            c0 = ring[0][0]
            try:
                for r_i in range(2):
                    A, B = ring[r_i], ring[r_i + 1]
                    for k in range(len(B)):
                        k2 = (k + 1) % len(B)
                        if r_i == 0:
                            tri = [c0, B[k], B[k2]]
                        else:
                            a0 = A[k]; a1 = A[k2]
                            tri = None
                            quad = [a0, B[k], B[k2], a1]
                            if None in quad:
                                continue
                            f = bm.faces.new(quad)
                            f.material_index = mi
                            f.smooth = True
                            continue
                        if None in tri:
                            continue
                        f = bm.faces.new(tri)
                        f.material_index = mi
                        f.smooth = True
            except ValueError:
                pass
    bm.to_mesh(me)
    bm.free()
    me.update()
    return len(specs)
