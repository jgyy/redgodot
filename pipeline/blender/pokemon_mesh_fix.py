"""Mesh / material / eye clean-up for the rigged Pokemon (called from gen_rigged_pokemon.build_one).

Pure function of (joined+normalised mesh object, species id, overrides): idempotent, so the lead can regenerate
every glb after merging.  Runs after normalise (feet on ground, facing -Y in Blender = +Z in glTF) and before the
rig, so it only edits vertices/faces/materials and never touches bones or animation.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
EYE_TEX = os.path.join(ROOT, 'pipeline', 'data', 'eye_tex')


def _verts(me):
    import numpy as np
    n = len(me.vertices)
    co = np.empty(n * 3, dtype=np.float64)
    me.vertices.foreach_get('co', co)
    return co.reshape(-1, 3)


def head_focus(V, head_z=None, head_r=None):
    """(centre, radius) of the head in Blender space.  With `head_z` (fraction of the height, from the overrides) the
    centre sits on the front surface of that height band; otherwise: upright = top slab, horizontal = front slab."""
    import numpy as np
    f, z = -V[:, 1], V[:, 2]
    H = float(z.max())
    fmin, fmax = float(f.min()), float(f.max())
    L = max(fmax - fmin, 1e-4)
    if head_z is not None:
        band = np.abs(z - head_z * H) < 0.08 * H
        if not band.any():
            band = np.ones_like(z, dtype=bool)
        front = float(f[band].max())
        tip = band & (f > front - 0.06 * H)          # whatever pokes out furthest at that height is the face
        x0 = float(np.median(V[tip, 0])) if abs(float(np.median(V[tip, 0]))) < 0.5 * H else 0.0
        return np.array([x0, -(front - 0.03 * H), head_z * H]), (head_r or 0.16) * H
    if L > 1.1 * H:
        m = f > fmax - 0.14 * L
        return np.array([0.0, -float(f[m].mean()), float(z[m].mean())]), 0.25 * H
    m = z > 0.85 * H
    return np.array([0.0, -float(f[m].mean()), 0.9 * H]), 0.2 * H


import pokemon_eye_bake as EB   # noqa: E402

EYE_WORDS = EB.EYE_WORDS


def eye_material_ids(me):
    """Indices of material slots that look like eyes (by material or texture name)."""
    return [i for i, m in enumerate(me.materials) if EB.is_eye(m)]


def eye_faces_centres(me, idx):
    """(x, y, z) centroid of each connected eye-material patch, Blender space."""
    import numpy as np
    V = _verts(me)
    polys = [p for p in me.polygons if p.material_index in idx]
    if not polys:
        return []
    cen = np.array([V[list(p.vertices)].mean(0) for p in polys])
    # cluster by proximity (eye patches are compact): greedy, radius = 4% of height
    rad = 0.04 * V[:, 2].max()
    groups = []
    for c in cen:
        for g in groups:
            if np.linalg.norm(g[0] / g[1] - c) < rad:
                g[0] += c
                g[1] += 1
                break
        else:
            groups.append([c.copy(), 1])
    return [(g[0] / g[1], g[1]) for g in groups]


def cleanup(sid, obj, ov):
    """Mesh/material clean-up on the raw joined mesh, BEFORE normalisation so that scale and centring are computed on
    the mesh that ships (a floating prop or a gas shell would otherwise shrink the model).  Returns a record dict."""
    me = obj.data
    rec = {}
    for nm in ov.get('drop_materials', []):   # translucent shells the alpha-less cel shader cannot draw (Gastly's gas)
        EB.delete_slots(me, [i for i, m in enumerate(me.materials) if m and m.name == nm])
    for nm, col in ov.get('alpha_fill', {}).items():   # transparent texels that stand for a dark face (Farfetch'd)
        EB.fill_transparent(me, nm, col)
    n = EB.bake_iris_layers(me, tuple(ov.get('overlay_layers', ())), skip=bool(ov.get('keep_iris_layers')))
    if n:
        rec['iris_baked_tris'] = n
    cut = EB.resolve_alpha(me)
    if cut:
        rec['alpha_cut'] = cut
    if ov.get('strays'):   # small islands far from the body (Alakazam's two spoons drift a body-length away)
        k = EB.remove_strays(me, far=float(ov['strays'].get('far', 2.4)), small=float(ov['strays'].get('small', 0.04)))
        if k:
            rec['strays_removed_verts'] = k
    return rec


def prepare(sid, obj, ov, rec=None):
    """Entry point after normalisation, before the rig.  Returns the record written to eyes.json."""
    me = obj.data
    rec = dict(rec or {})
    EB.matte(me)
    if ov.get('eye_patches'):   # flat-colour discs for models with palette atlases (Gastly)
        import pokemon_eyes
        rec['eye_patches'] = pokemon_eyes.add_patches(me, ov['eye_patches'], float(_verts(me)[:, 2].max()))
    if ov.get('eye_decals'):   # eyes painted from pipeline/data/eye_tex into the body atlas (see pokemon_eyes.py)
        import pokemon_eyes
        rec['eye_decal_tris'] = pokemon_eyes.apply(me, ov['eye_decals'], float(_verts(me)[:, 2].max()))
    for nm, hexcol in ov.get('retint', {}).items():   # atlas colour vs the upstream sprite palette
        EB.retint(me, nm, [int(hexcol[i:i + 2], 16) / 255.0 for i in (1, 3, 5)])
    if ov.get('smooth_normals'):
        EB.smooth_normals(me)
    if ov.get('relax_normals'):
        EB.relaxed_normals(me, int(ov['relax_normals']))
    V = _verts(me)
    c, r = head_focus(V, ov.get('head_z'), ov.get('head_r'))
    rec['src'] = 'heuristic'
    idx = eye_material_ids(me)
    rec['eye_mats'] = [me.materials[i].name for i in idx]
    pts = [] if ov.get('head_z') is not None else eye_faces_centres(me, idx)
    pts = [p for p, n in pts if n >= 1]
    if pts:
        import numpy as np
        P = np.array(pts)
        c = np.median(P, axis=0)   # median: one stray eye patch (mouth, second head) must not drag the close-up
        spread = float(np.linalg.norm(P.max(0) - P.min(0)))
        Hh = float(V[:, 2].max())
        r = min(0.3 * Hh, max(0.07 * Hh, 1.25 * spread + 0.03 * Hh))
        rec['src'] = 'eye-material'
        rec['eyes'] = [[round(float(q[0]), 4), round(float(q[2]), 4), round(float(-q[1]), 4)] for q in P]
    rec['focus'] = [round(float(c[0]), 4), round(float(c[2]), 4), round(float(-c[1]), 4)]
    rec['focus_r'] = round(float(r), 4)
    return rec


def dump_record(out_dir, sid, rec):
    """Sidecar for eyes.json.  Also drops the textures Godot extracted from the previous glb: its importer
    (gltf/embedded_image_handling=Extract) never overwrites an existing SID_<image>.jpg, so stale ones would
    shadow the freshly baked eye atlases."""
    import glob
    imp = os.path.join(out_dir, sid + '.glb.import')
    if os.path.exists(imp):   # force Godot to re-import (and re-extract) even if the glb bytes did not change
        os.remove(imp)
    for ext in ('jpg', 'png', 'webp'):
        for f in glob.glob(os.path.join(out_dir, '%s_*.%s' % (sid, ext))):
            os.remove(f)
        for f in glob.glob(os.path.join(out_dir, '%s_*.%s.import' % (sid, ext))):
            os.remove(f)
    with open(os.path.join(out_dir, '_%s.eyes.json' % sid), 'w') as fh:
        json.dump(rec, fh)


def write_index(out_dir, ids):
    """Merge the per-species sidecars into eyes.json (what ModelSheet.gd and the eye check read)."""
    p = os.path.join(out_dir, 'eyes.json')
    old = json.load(open(p)).get('species', {}) if os.path.exists(p) else {}
    for sid in ids:
        q = os.path.join(out_dir, '_%s.eyes.json' % sid)
        if os.path.exists(q):
            old[sid] = json.load(open(q))
            os.remove(q)
    with open(p, 'w') as fh:
        json.dump({'species': dict(sorted(old.items()))}, fh, separators=(',', ':'))
