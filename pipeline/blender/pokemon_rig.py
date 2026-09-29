"""Per-species skeleton fitting, skinning and rest-pose correction for the Pokemon pipeline (numpy only).

`fit(V, T, spec)` -> Skeleton: a bone tree fitted to the mesh's own protrusions (limbs, ears, tails, wings, tentacles ...):
  * the trunk (Hips -> Spine* -> Neck* -> Head -> Jaw) follows the body axis, its segment counts scale with real length;
  * every persistent geodesic extremity of the surface (pokemon_geom.find_tips) becomes a chain of 1-4 bones whose
    role (Arm / Leg / Tail / Ear / Wing / Fin / Leaf / Tentacle ...) comes from where it sits on the body and the
    species' entry in pipeline/data/pokemon_species_rig.json;
  * bone count and names therefore differ from species to species.
`skin(V, T, sk)` gives smooth, radius-aware, Laplacian-relaxed weights; `natural_pose(...)` computes the corrective
rest pose (arms hang, legs stand under the body, wings fold) that gets baked into the mesh so no clip starts in a T-pose.
"""
import math

import numpy as np

import pokemon_geom as PG

EXTRA_NAME = {'plant': 'Leaf', 'multileg': 'Tentacle', 'floating': 'Wisp', 'sphere': 'Spike', 'blob': 'Lobe', 'rock': 'Boulder',
              'shell': 'Tentacle', 'radial': 'Point', 'winged': 'Feeler', 'bird': 'Crest', 'quadruped': 'Mane',
              'quadruped_small': 'Whisker', 'biped_tail': 'Spike', 'biped_humanoid': 'Trim', 'fish': 'Fringe', 'serpent': 'Frill'}
UP = np.array([0.0, 0.0, 1.0])
FWD = np.array([0.0, -1.0, 0.0])     # Blender space: creatures face -Y
LAT = np.array([1.0, 0.0, 0.0])


def unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else np.array([0.0, 0.0, 1.0])


class Bone:
    __slots__ = ('name', 'head', 'tail', 'parent', 'role', 'side', 'group', 'index')

    def __init__(self, name, head, tail, parent, role, side='', group='', index=0):
        self.name, self.parent, self.role, self.side, self.group, self.index = name, parent, role, side, group, index
        self.head = np.asarray(head, dtype=float)
        self.tail = np.asarray(tail, dtype=float)

    @property
    def dir(self):
        return unit(self.tail - self.head)

    @property
    def length(self):
        return float(np.linalg.norm(self.tail - self.head))


class Skeleton:
    def __init__(self, H):
        self.H = H
        self.bones = {}          # name -> Bone, insertion order == hierarchy order (parents first)
        self.chains = {}         # chain id (e.g. 'Arm_L') -> [bone names]
        self.info = {}

    def add(self, b):
        self.bones[b.name] = b
        self.chains.setdefault(b.group or b.name, []).append(b.name)
        return b

    def chain(self, gid):
        return self.chains.get(gid, [])

    def groups(self, role):
        return [g for g, names in self.chains.items() if self.bones[names[0]].role == role]

    def names(self):
        return list(self.bones)

    def signature(self):
        return tuple(sorted(self.bones))


# ------------------------------------------------------------------------------------------------ helpers
def _pctl(a, q):
    return float(np.percentile(a, q)) if len(a) else 0.0


def _seg_bones(sk, gid, role, pts, parent, side='', pattern=None, index=0):
    """chain of bones through `pts` (len n+1); names <gid>_1.._n unless `pattern` supplies them."""
    prev = parent
    for i in range(len(pts) - 1):
        nm = (pattern[i] if pattern else '%s_%d' % (gid, i + 1))
        sk.add(Bone(nm, pts[i], pts[i + 1], prev, role, side, gid, i))
        prev = nm
    return prev


def _slab_center(V, mask, fallback):
    return np.median(V[mask], axis=0) if mask.sum() >= 5 else np.asarray(fallback, dtype=float)


# ------------------------------------------------------------------------------------------------ analysis
class Tip:
    def __init__(self, v, pos, base, d, pers, chain):
        self.v, self.pos, self.base, self.d, self.pers, self.chain = v, pos, base, d, pers, chain
        self.role = None
        self.side = ''


def analyse(V, T, spec):
    H = float(V[:, 2].max())
    f = -V[:, 1]
    g = PG.Graph(V, T, H)
    return H, f, g


def fit(V, T, spec):
    """Build the species skeleton. `spec` is the entry of pokemon_species_rig.json."""
    H = float(V[:, 2].max())
    plan = spec.get('plan', 'quadruped')
    sk = Skeleton(H)
    posture = spec.get('posture')
    x, y, z = V[:, 0], V[:, 1], V[:, 2]
    f = -y
    fmin, fmax = float(f.min()), float(f.max())
    L = max(fmax - fmin, 1e-4)
    if posture is None:
        posture = 'chain' if plan == 'serpent' else 'core' if plan in ('blob', 'sphere', 'radial') else ('horizontal' if L > 1.1 * H else 'upright')
    sk.info.update(plan=plan, posture=posture, H=H, L=L)
    g = PG.Graph(V, T, H)
    sk.info['graph'] = g
    c = np.array([np.median(x), np.median(y), np.median(z)])
    core = (z > 0.25 * H) & (z < 0.65 * H)
    xcore = max(_pctl(np.abs(x[core]), 75) if core.sum() > 10 else 0.2 * H, 0.05 * H)
    if posture == 'horizontal':
        # torso = the f-range where the body is wide (tails and necks are thin), so the hips sit at its rear
        bins = np.linspace(fmin, fmax, 21)
        wid = np.array([_pctl(np.abs(x[(f >= bins[i]) & (f < bins[i + 1] + 1e-9)]), 90) if ((f >= bins[i]) & (f < bins[i + 1] + 1e-9)).sum() > 3 else 0.0 for i in range(20)])
        ok = np.nonzero(wid >= 0.5 * wid.max())[0]
        t0, t1 = bins[ok.min()], bins[ok.max() + 1]
        cf = 0.5 * (t0 + t1)
        sk.info['torso'] = (float(t0), float(t1))
    else:
        band = (z > 0.4 * H) & (z < 0.7 * H) & (np.abs(x) > 0.45 * xcore)
        cf = float(np.median(f[band])) if band.sum() > 10 else (float(np.median(f[core])) if core.sum() > 10 else float(np.median(f)))
        sk.info['torso'] = (cf - 0.2 * H, cf + 0.2 * H)

    root_v, pred, d_root, tips_raw = PG.find_tips(g, c, H, max_tips=40, min_len=float(spec.get('min_tip', 0.07)))
    tips = []
    for (tv, dd, pers, mv) in tips_raw:
        pth = g.path(pred, tv)
        # walk the surface path up to where this protrusion joins the rest of the body
        keep = [p for p in pth if d_root[p] >= d_root[mv] - 1e-9]
        pts = g.P[keep] if len(keep) >= 2 else g.P[pth[-2:]]
        tips.append(Tip(tv, g.P[tv], g.P[mv], dd, pers, pts[::-1]))   # chain: tip -> base

    if posture == 'chain':
        _fit_chain_body(sk, V, g, tips, spec, H, L, xcore, c)
    elif posture == 'core':
        _fit_core_body(sk, V, g, tips, spec, H, L, xcore, c)
    else:
        _fit_trunk_body(sk, V, g, tips, spec, H, L, xcore, cf, posture)
    return sk


# ------------------------------------------------------------------------------------------------ trunk bodies
def _trunk_landmarks(V, spec, H, L, xcore, cf, posture, sk):
    x, y, z = V[:, 0], V[:, 1], V[:, 2]
    f = -y
    fmax = float(f.max())
    core_mask = (z > 0.25 * H) & (z < 0.65 * H) if posture == 'upright' else (np.abs(f - cf) < 0.3 * L)
    if posture == 'upright':
        slab = z > 0.76 * H
        hc = _slab_center(V, slab & (np.abs(x) < 0.8 * max(xcore, 0.1 * H)), [0, -cf, 0.9 * H])
        hips = np.array([0.0, -cf, 0.36 * H])
        hr = float(np.clip(_pctl(np.abs(x[slab] - hc[0]), 75) if slab.sum() > 8 else 0.12 * H, 0.06 * H, 0.24 * H))
    else:
        slab = f > fmax - 0.20 * L
        cz = float(np.median(z[core_mask])) if core_mask.sum() > 5 else 0.5 * H
        hc = _slab_center(V, slab, [0, -(fmax - 0.08 * L), cz])
        t0, t1 = sk.info['torso']
        hips = np.array([0.0, -(t0 + 0.2 * (t1 - t0)), cz])
        hr = float(np.clip(_pctl(np.abs(x[slab]), 75) if slab.sum() > 8 else 0.12 * H, 0.04 * H, 0.3 * H))
    hc = hc.copy()
    hc[0] = 0.0
    return hc, hips, hr


def _classify(tips, spec, V, H, L, xcore, cf, hc, hr, hips, posture):
    """assign a role to each tip (mutates tip.role/side); returns leftover tips."""
    cap = {k: int(spec.get(k, d)) for k, d in (('arms', 2), ('legs', 2), ('wings', 0), ('ears', 2), ('tails', 1), ('fins', 0),
                                              ('extras', 4), ('feet', 0))}
    plan = spec.get('plan')
    horizontal = posture == 'horizontal'
    ref = H if not horizontal else max(H, 0.6 * L)

    def feat(t):
        p = t.pos
        return dict(lat=abs(p[0]) / xcore, z=p[2] / H, f=-p[1] - cf, len=t.pers / H, bz=t.base[2] / H,
                    dh=float(np.linalg.norm(p - hc)) / hr, bh=float(np.linalg.norm(t.base - hc)) / hr)
    F = {id(t): feat(t) for t in tips}
    pool = list(tips)

    chosen_all = []

    def take(pred, key, n, role, reverse=True, sep=0.09):
        cs = [t for t in pool if pred(F[id(t)], t)]
        cs.sort(key=lambda t: key(F[id(t)], t), reverse=reverse)
        out = []
        for t in cs:
            if len(out) >= n:
                break
            # fingers / toes / feathers of one limb are separate persistence peaks: one limb = one pick
            if any(np.linalg.norm(t.pos - o.pos) < sep * H for o in out):
                continue
            out.append(t)
        for t in out:
            t.role = role
            t.side = '' if abs(t.pos[0]) < 0.06 * H else ('L' if t.pos[0] > 0 else 'R')
            pool.remove(t)
            chosen_all.append(t)
        return out

    # the head itself (snout / crown of a head that pokes out): not a chain
    for t in list(pool):
        if F[id(t)]['dh'] < 1.25 and np.linalg.norm(t.base - hc) < 1.6 * hr:
            pool.remove(t)
    if cap['wings']:
        take(lambda a, t: a['lat'] > 0.9 and a['z'] > 0.3 and a['len'] > 0.12, lambda a, t: t.pers, cap['wings'], 'Wing')
    if cap['ears']:
        take(lambda a, t: a['bh'] < 2.2 and a['dh'] < 3.6 and t.pos[2] > hc[2] - 0.2 * hr and a['len'] > 0.05 and a['dh'] > 1.0,
             lambda a, t: t.pers, cap['ears'], 'Ear')
    tailn = cap['tails']
    if tailn:
        rear = (lambda a, t: a['f'] < -0.16 * ref and a['z'] < 0.75) if not horizontal else (lambda a, t: a['f'] < -0.22 * L)
        take(rear, lambda a, t: t.pers, tailn, 'Tail')
    if cap['fins']:
        take(lambda a, t: a['len'] > 0.06, lambda a, t: t.pers, cap['fins'], 'Fin')
    legz = 0.34 if not horizontal else 0.42
    take(lambda a, t: a['z'] < legz and t.pers > 0.05 * H, lambda a, t: (t.pers, -t.pos[2]), cap['legs'], 'Leg')
    take(lambda a, t: 0.16 < a['z'] < (0.9 if plan != 'multileg' else 1.1) and a['lat'] > 0.55 and t.pers > 0.05 * H, lambda a, t: (t.pers * a['lat']), cap['arms'], 'Arm')
    def near_limb(t):
        """fingers, claws and hand-held props peak on their own: fold them into the limb they sit on (its bones will skin them)."""
        for o in chosen_all:
            if o.role == 'Extra':
                continue
            ln = float(np.linalg.norm(o.pos - o.base))
            if float(_seg_dist(t.pos, o.base, o.pos)) < max(0.12 * H, 0.45 * ln):
                return True
        return False
    rest = [t for t in pool if t.pers > 0.08 * H and not near_limb(t)]
    rest.sort(key=lambda t: -t.pers)
    for t in rest[:cap['extras']]:
        t.role = 'Extra'
        t.side = '' if abs(t.pos[0]) < 0.06 * H else ('L' if t.pos[0] > 0 else 'R')
    return [t for t in tips if t.role]


def _seg_dist(P, a, b):
    ab = b - a
    t = np.clip(((P - a) @ ab) / max(float(ab @ ab), 1e-12), 0.0, 1.0)
    return np.linalg.norm(P - (a + t[..., None] * ab), axis=-1)


def _trim_chain(t, sk, role):
    """cut the surface path where it enters the body volume: torso capsule (limbs, tail) or head sphere (ears ...)."""
    info = sk.info
    pts = t.chain            # tip -> base
    if role in ('Ear', 'Extra') and np.linalg.norm(t.base - info['hc']) < 2.0 * info['hr']:
        d = np.linalg.norm(pts - info['hc'], axis=1) - 0.85 * info['hr']
    else:
        d = _seg_dist(pts, info['hips'], info['chest']) - 0.9 * info['xcore']
    inside = np.nonzero(d < 0)[0]
    cut = int(inside[0]) if len(inside) else len(pts) - 1
    cut = max(cut, 1)
    return pts[:cut + 1]


def _fill_slots(used, spec, V, H, L, xcore, cf, hips, chest, posture):
    """limbs the tip search could not separate (fused feet, arms hugging the body) are rebuilt from regional extremes so
    every two-/four-legged body gets its full set of limbs."""
    plan = spec.get('plan')
    if plan in ('multileg', 'plant', 'rock', 'radial', 'sphere', 'blob', 'floating', 'serpent', 'fish', 'shell') and plan != 'shell':
        return []
    x, y, z = V[:, 0], V[:, 1], V[:, 2]
    f = -y
    horizontal = posture == 'horizontal'
    out = []
    nleg, narm = int(spec.get('legs', 2)), int(spec.get('arms', 2))

    def mk(role, side, pos, base):
        t = Tip(-1, np.asarray(pos, float), np.asarray(base, float), float(np.linalg.norm(pos - base)), float(np.linalg.norm(pos - base)),
                np.array([pos, base], dtype=float))
        t.role, t.side = role, side
        return t
    if nleg in (2, 4):
        slots = [('', 'L'), ('', 'R')] if not (nleg == 4 and horizontal) else [(a, b) for a in 'FH' for b in 'LR']
        for fh, sd in slots:
            sg = 1.0 if sd == 'L' else -1.0
            have = any(t.role == 'Leg' and t.side == sd and (not fh or fh == ('F' if (-t.pos[1] - cf) > 0 else 'H')) for t in used)
            if have:
                continue
            m = (np.sign(x) == sg) & (z < 0.14 * H)
            if horizontal and fh:
                m &= (f > cf) if fh == 'F' else (f <= cf)
            if m.sum() >= 3:
                foot = np.array([x[m].mean(), -f[m].mean(), 0.03 * H])
            else:
                foot = np.array([sg * 0.3 * xcore, -(cf + (0.2 if fh == 'F' else -0.2 if fh == 'H' else 0.0) * L), 0.03 * H])
            hy = chest[1] if fh == 'F' else hips[1]
            hip = np.array([sg * 0.5 * abs(foot[0]), hy, hips[2]])
            out.append(mk('Leg', sd, foot, hip))
    if narm == 2 and plan not in ('quadruped', 'quadruped_small', 'bird', 'fish', 'serpent'):
        for sd in 'LR':
            sg = 1.0 if sd == 'L' else -1.0
            if any(t.role == 'Arm' and t.side == sd for t in used):
                continue
            m = (np.sign(x) == sg) & (z > 0.25 * H) & (z < 0.8 * H)
            if m.sum() < 8:
                continue
            ax = np.abs(x[m])
            sel = m & (np.abs(x) >= np.quantile(ax, 0.96))
            hand = V[sel].mean(0)
            sh = np.array([sg * 0.2 * xcore, chest[1], 0.66 * H])
            if np.linalg.norm(hand - sh) < 0.1 * H:
                hand = sh + np.array([sg * 0.1 * H, 0.0, -0.16 * H])
            out.append(mk('Arm', sd, hand, sh))
    return out


def _polyline_from_tip(t, n, V, H, sk=None, role=None, radius=0.06):
    """n+1 points from the base of the protrusion to its tip, pulled to the local section centres."""
    chain = _trim_chain(t, sk, role) if sk is not None else t.chain
    pts = PG.resample(chain[::-1], max(n * 3, 6))
    out = []
    for i, p in enumerate(pts):
        a = pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]
        out.append(PG.section_center(V, p, a, radius * H, 0.035 * H))
    out[-1] = 0.5 * out[-1] + 0.5 * t.pos
    return PG.resample(np.array(out), n)


def _fit_trunk_body(sk, V, g, tips, spec, H, L, xcore, cf, posture):
    hc, hips, hr = _trunk_landmarks(V, spec, H, L, xcore, cf, posture, sk)
    horizontal = posture == 'horizontal'
    ref = max(H, 0.6 * L)
    up_axis = hc - hips
    trunk_len = float(np.linalg.norm(up_axis))
    ax = unit(up_axis)
    n_spine = int(spec.get('spine', np.clip(round(trunk_len / (0.17 * ref)), 2, 4)))
    n_neck = int(spec.get('neck', 1))
    head_len = 2.0 * hr
    head_base = hc - ax * hr
    neck_frac = 0.20 + 0.06 * (n_neck - 1)
    chest = hips + (head_base - hips) * (1 - neck_frac)
    # rest bones: Hips is the first trunk segment, Spine1..n follow up to the chest
    sk.add(Bone('Root', [0, hips[1], 0.0], [0, hips[1], 0.06 * H], None, 'Root', '', 'Root'))
    pts = [hips + (chest - hips) * (i / (n_spine + 1)) for i in range(n_spine + 2)]
    sk.add(Bone('Hips', pts[0], pts[1], 'Root', 'Hips', '', 'Hips'))
    prev = 'Hips'
    for i in range(n_spine):
        nm = 'Spine%d' % (i + 1)
        sk.add(Bone(nm, pts[i + 1], pts[i + 2], prev, 'Spine', '', 'Spine', i))
        prev = nm
    npts = [chest + (head_base - chest) * (i / n_neck) for i in range(n_neck + 1)]
    for i in range(n_neck):
        nm = 'Neck%d' % (i + 1) if n_neck > 1 else 'Neck'
        sk.add(Bone(nm, npts[i], npts[i + 1], prev, 'Neck', '', 'Neck', i))
        prev = nm
    head_top = hc + ax * hr * 1.05
    head_top[2] = min(head_top[2], 0.995 * H)
    sk.add(Bone('Head', head_base, head_top, prev, 'Head', '', 'Head'))
    if spec.get('jaw', True):
        jd = FWD if True else FWD
        jh = hc + np.array([0, 0.0, -0.32 * hr]) + jd * 0.25 * hr
        sk.add(Bone('Jaw', jh, jh + jd * 0.85 * hr + np.array([0, 0, -0.1 * hr]), 'Head', 'Jaw', '', 'Jaw'))
    sk.info.update(hips=hips, hc=hc, hr=hr, chest=chest, ax=ax, xcore=xcore, cf=cf, head_base=head_base)
    top_spine = 'Spine%d' % n_spine
    used = _classify(tips, spec, V, H, L, xcore, cf, hc, hr, hips, posture)
    used += _fill_slots(used, spec, V, H, L, xcore, cf, hips, chest, posture)
    _attach_limbs(sk, used, spec, V, H, L, xcore, cf, hc, hr, hips, chest, top_spine, horizontal)


def _toward_axis(p, sk, k):
    a, b = sk.info['hips'], sk.info['chest']
    ab = b - a
    t = float(np.clip(((p - a) @ ab) / max(float(ab @ ab), 1e-12), 0.0, 1.0))
    return p + (a + t * ab - p) * k


def _nearest_on_polyline(pts, p):
    best, bi = 1e9, 0
    for i, q in enumerate(pts):
        d = np.linalg.norm(q - p)
        if d < best:
            best, bi = d, i
    return bi


def _attach_limbs(sk, used, spec, V, H, L, xcore, cf, hc, hr, hips, chest, top_spine, horizontal, nearest=False):
    counts = {}
    ref = max(H, 0.6 * L)
    nm_hips, nm_head = sk.info.get('names', {}).get('hips', 'Hips'), sk.info.get('names', {}).get('head', 'Head')

    def P(default, p):
        return _nearest_trunk(sk, p) if nearest else default

    def take_name(role, side):
        k = (role, side)
        counts[k] = counts.get(k, 0) + 1
        return counts[k]

    # front/hind for horizontal legs
    for t in sorted(used, key=lambda t: (t.role, -t.pers)):
        role, side = t.role, t.side
        span = float(np.linalg.norm(t.pos - t.base))
        ln = max(t.pers, span)
        if role == 'Leg':
            fh = ''
            if horizontal:
                fh = 'F' if (-t.pos[1] - cf) > 0 else 'H'
            k = take_name('Leg', fh + side)
            gid = 'Leg_%s%s' % (fh, side) + ('' if k == 1 else str(k))
            n = 3 if (ln > 0.15 * ref or horizontal) else 2
            pts = _polyline_from_tip(t, n, V, H, sk, role)
            pts[0] = _toward_axis(pts[0], sk, 0.45)
            parent = nm_hips if fh != 'F' else top_spine
            _seg_bones(sk, gid, 'Leg', PG.resample(pts, n), P(parent, pts[0]), side)
        elif role == 'Arm':
            k = take_name('Arm', side)
            gid = 'Arm_%s' % side + ('' if k == 1 else str(k))
            n = 3 if ln > 0.2 * H else 2
            pts = _polyline_from_tip(t, n, V, H, sk, role)
            pts[0] = _toward_axis(pts[0], sk, 0.4)
            _seg_bones(sk, gid, 'Arm', PG.resample(pts, n), P(top_spine, pts[0]), side)
        elif role == 'Tail':
            k = take_name('Tail', '')
            gid = 'Tail' if k == 1 else 'Tail%d' % k
            n = int(np.clip(round(ln / (0.11 * ref)), 2, 8))
            n = int(spec.get('tail_bones', n)) if k == 1 else min(n, 3)
            pts = _polyline_from_tip(t, n, V, H, sk, role, radius=0.05)
            pts[0] = _toward_axis(pts[0], sk, 0.5)
            names = ['Tail%d' % (i + 1) if k == 1 else 'Tail%d_%d' % (k, i + 1) for i in range(n)]
            _seg_bones(sk, gid, 'Tail', pts, P(nm_hips, pts[0]), side, pattern=names)
        elif role == 'Ear':
            k = take_name('Ear', side)
            gid = 'Ear_%s' % (side or 'C') + ('' if k == 1 else str(k))
            n = 2 if ln > 0.16 * H else 1
            pts = _polyline_from_tip(t, n, V, H, sk, role, radius=0.04)
            pts[0] = hc + (pts[0] - hc) * 0.6
            _seg_bones(sk, gid, 'Ear', pts, P(nm_head, pts[0]), side)
        elif role == 'Wing':
            k = take_name('Wing', side)
            gid = 'Wing_%s' % (side or 'C') + ('' if k == 1 else str(k))
            n = 3 if ln > 0.3 * H else 2
            pts = _polyline_from_tip(t, n, V, H, sk, role, radius=0.08)
            pts[0] = _toward_axis(pts[0], sk, 0.6)
            _seg_bones(sk, gid, 'Wing', pts, P(top_spine, pts[0]), side)
        elif role == 'Fin':
            k = take_name('Fin', side)
            gid = 'Fin_%s' % (side or 'C') + ('' if k == 1 else str(k))
            n = 2 if ln > 0.2 * ref else 1
            pts = _polyline_from_tip(t, n, V, H, sk, role, radius=0.05)
            _seg_bones(sk, gid, 'Fin', pts, P(top_spine, pts[0]), side)
        else:
            k = take_name('Extra', side)
            gid = '%s_%s%d' % (EXTRA_NAME.get(spec.get('plan'), 'Spike'), side or 'C', k)
            n = 2 if ln > 0.15 * ref else 1
            pts = _polyline_from_tip(t, n, V, H, sk, role, radius=0.05)
            par = nm_head if np.linalg.norm(t.base - hc) < 2.0 * hr else top_spine
            par = P(par, pts[0])
            _seg_bones(sk, gid, 'Extra', pts, par, side)


def _nearest_trunk(sk, p):
    best, bn = 1e9, None
    for n in sk.info['trunk']:
        b = sk.bones[n]
        d = float(_seg_dist(p, b.head, b.tail))
        if d < best:
            best, bn = d, n
    return bn


def _fit_chain_body(sk, V, g, tips, spec, H, L, xcore, c):
    """serpents: one long body chain (tail -> head) found as the geodesic between the two biggest extremities."""
    tips = sorted(tips, key=lambda t: -t.pers)
    A = tips[0]
    if len(tips) > 1:
        B = tips[1]
    else:
        far = int(np.argmax(np.linalg.norm(g.P - A.pos, axis=1)))
        B = Tip(far, g.P[far], g.P[far], 0, 0, g.P[[far]])
    _d, pred = g.dijkstra(A.v)
    pth = g.P[g.path(pred, B.v)]
    plen = float(np.linalg.norm(np.diff(pth, axis=0), axis=1).sum())
    pts = PG.resample(pth, 40)
    rad = 0.035 * plen
    cen = []
    for i, p in enumerate(pts):
        a = pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]
        cen.append(PG.section_center(V, p, a, rad, 0.02 * plen))
    cen = np.array(cen)
    cen[0], cen[-1] = 0.5 * (cen[0] + A.pos), 0.5 * (cen[-1] + B.pos)
    sample = V[:: max(1, len(V) // 3000)]
    dmin = np.min(np.linalg.norm(sample[:, None, :] - cen[None, ::2, :], axis=2), axis=1)
    thick = float(np.clip(np.median(dmin), 0.02 * plen, 0.2 * plen))
    n = int(spec.get('body_bones', np.clip(round(plen / (3.0 * thick)), 8, 14)))
    pts = PG.resample(cen, n)

    def mass(p):
        return int((np.linalg.norm(V - p, axis=1) < 0.09 * plen).sum())
    head_first = mass(pts[0]) > mass(pts[-1])
    if spec.get('head_end') == 'A':
        head_first = True
    if head_first:
        pts = pts[::-1]           # now pts[0] = tail, pts[-1] = head
    m = n // 2
    sk.add(Bone('Root', [pts[m][0], pts[m][1], 0.0], [pts[m][0], pts[m][1], 0.05 * H], None, 'Root', '', 'Root'))
    names = ['Body%d' % (i + 1) for i in range(n)]
    names[-1] = 'Head'
    trunk = []
    order = [m] + list(range(m + 1, n)) + list(range(m - 1, -1, -1))
    for i in order:
        par = 'Root' if i == m else names[i - 1] if i > m else names[i + 1]
        head = i == n - 1
        sk.add(Bone(names[i], pts[i], pts[i + 1], par, 'Head' if head else 'Spine', '', 'Head' if head else 'Spine', i))
        trunk.append(names[i])
    hd = sk.bones['Head']
    jh = hd.head + (hd.tail - hd.head) * 0.55 - np.array([0, 0, 0.25 * thick])
    sk.add(Bone('Jaw', jh, jh + hd.dir * 0.55 * hd.length, 'Head', 'Jaw', '', 'Jaw'))
    hc = hd.tail.copy()
    hr = max(thick, 0.02 * H)
    sk.info.update(hips=pts[m], hc=hc, hr=hr, chest=pts[-2], xcore=thick, cf=0.0, trunk=trunk + ['Jaw'],
                   names={'hips': names[m], 'head': 'Head'}, body_len=plen, thick=thick)
    rest = [t for t in tips if t is not A and t is not B and np.min(np.linalg.norm(pts - t.pos, axis=1)) > 1.6 * thick]
    sp = dict(spec)
    sp.update(arms=0, legs=0, tails=0, wings=0)
    used = _classify(rest, sp, V, H, L, thick, 0.0, hc, hr, pts[m], 'chain')
    _attach_limbs(sk, used, sp, V, H, L, thick, 0.0, hc, hr, pts[m], pts[-2], names[m], False, nearest=True)


def _fit_core_body(sk, V, g, tips, spec, H, L, xcore, c):
    """blobs, balls, stars, shells, floaters: a small core rig (Body/Crown/Side/Face) plus whatever sticks out."""
    plan = spec.get('plan')
    x, y, z = V[:, 0], V[:, 1], V[:, 2]
    zc = float(np.clip(np.median(z), 0.3 * H, 0.6 * H))
    cy = float(0.5 * (y.min() + y.max()))
    cen = np.array([0.0, cy, zc])
    sk.add(Bone('Root', [0, cy, 0.0], [0, cy, 0.05 * H], None, 'Root', '', 'Root'))
    sk.add(Bone('Body', [0, cy, 0.06 * H], cen, 'Root', 'Hips', '', 'Hips'))
    sk.add(Bone('Crown', cen, [0, cy, 0.97 * H], 'Body', 'Head', '', 'Head'))
    trunk = ['Body', 'Crown']
    xr = float(np.percentile(np.abs(x), 88))
    if plan in ('blob', 'sphere', 'floating', 'shell'):
        for sd, sg in (('L', 1), ('R', -1)):
            sk.add(Bone('Side_' + sd, cen, cen + np.array([sg * 0.8 * xr, 0, 0]), 'Body', 'Side', sd, 'Side_' + sd))
            trunk.append('Side_' + sd)
    if plan in ('sphere', 'blob', 'floating'):
        fr = float(np.percentile(-y, 90))
        sk.add(Bone('Face', cen, [0, -0.85 * fr, zc], 'Body', 'Face', '', 'Face'))
        trunk.append('Face')
    hc = np.array([0, cy, 0.9 * H])
    xc = max(xr * 0.8, 0.08 * H)
    hips = np.array([0, cy, 0.3 * H])
    sk.info.update(hips=hips, hc=hc, hr=0.25 * H, chest=cen, xcore=xc, cf=-cy, trunk=trunk,
                   names={'hips': 'Body', 'head': 'Crown'}, torso=(-cy - 0.2 * H, -cy + 0.2 * H))
    used = _classify(tips, spec, V, H, L, xc, -cy, hc, 0.2 * H, hips, 'upright')
    _attach_limbs(sk, used, spec, V, H, L, xc, -cy, hc, 0.2 * H, hips, cen, 'Crown', False, nearest=True)


