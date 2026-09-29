"""Checks on the committed Pokemon .glb files (numpy only, no Blender, no Godot).

    python3 -m unittest discover -s pipeline/tests -v          # all species (~3 min)
    POKEMON_FAST=1 python3 -m unittest discover -s pipeline/tests   # a sample of 24 species

What is asserted (numbers are printed so the CI log doubles as the report):
  * every species has its own skeleton: bone counts vary and the (bone names) signatures are near-unique;
  * >= 24 clips each, the 18 game clip names + idle variants + >= 6 signature clips;
  * no species is in a T/A pose in the Idle rest frame (limb-to-body angle measured on the skinned mesh);
  * every clip of a species differs meaningfully from every other clip (time-aligned skinned-vertex distance);
  * the same clip differs between species of the same body plan;
  * no clip explodes the mesh (edge stretch stays bounded in every clip).
"""
import itertools
import json
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'pipeline', 'blender'))
import pokemon_check as PC   # noqa: E402

MODELS = os.path.join(ROOT, 'godot', 'assets', 'models', 'pokemon')
BASE = ['Idle', 'Walk', 'Run', 'Attack', 'Special', 'Hurt', 'Faint', 'Victory', 'Sleep', 'Roar',
        'Dodge', 'Spin', 'Hop', 'Charge', 'Taunt', 'Spawn', 'Hover', 'Talk']
VARIANTS = ['IdleLook', 'IdleStretch', 'IdleFidget']
FAST = os.environ.get('POKEMON_FAST') == '1'

MIN_CLIP_DISTANCE = 0.006       # of body height: two clips of one species closer than this are "the same animation"
MIN_SAME_CLIP_DISTANCE = 0.001  # same-named clip of two species of one plan (feature distance, see feat())
MAX_STRETCH = 15.0


def species():
    ids = sorted(f[:-4] for f in os.listdir(MODELS) if f.endswith('.glb'))
    if FAST:
        ids = ids[::6]
    return ids


_cache = {}


def glb(sid):
    if sid not in _cache:
        _cache[sid] = PC.Glb(os.path.join(MODELS, sid + '.glb'))
    return _cache[sid]


def plans():
    with open(os.path.join(ROOT, 'pipeline', 'data', 'pokemon_species_rig.json')) as fh:
        return {k: v['plan'] for k, v in json.load(fh)['species'].items()}


class PokemonRigTests(unittest.TestCase):
    def test_all_species_present(self):
        ids = set(f[:-4] for f in os.listdir(MODELS) if f.endswith('.glb'))
        with open(os.path.join(ROOT, 'godot', 'data', 'pokedata.json')) as fh:
            want = set(json.load(fh)['species']) | {'MISSINGNO'}
        self.assertEqual(want - ids, set())

    def test_clip_counts_and_names(self):
        low = {}
        for sid in species():
            names = set(glb(sid).anims)
            self.assertTrue(set(BASE) <= names, '%s lacks base clips %s' % (sid, set(BASE) - names))
            self.assertTrue(set(VARIANTS) <= names, '%s lacks idle variants' % sid)
            sig = names - set(BASE) - set(VARIANTS)
            self.assertGreaterEqual(len(sig), 6, '%s has %d signature clips' % (sid, len(sig)))
            self.assertGreaterEqual(len(names), 24, sid)
            low[sid] = len(names)
        print('\nclips per species: min %d max %d' % (min(low.values()), max(low.values())))

    def test_skeletons_are_species_specific(self):
        counts, sigs = {}, {}
        for sid in species():
            g = glb(sid)
            counts[sid] = len(g.joints)
            sigs[sid] = tuple(sorted(g.jnames))
        distinct_counts = len(set(counts.values()))
        distinct_sigs = len(set(sigs.values()))
        print('\nbone counts: min %d max %d mean %.1f, %d distinct counts, %d distinct (names) signatures over %d species' % (
            min(counts.values()), max(counts.values()), float(np.mean(list(counts.values()))), distinct_counts, distinct_sigs, len(sigs)))
        n = len(sigs)
        self.assertGreaterEqual(distinct_counts, min(20, n // 3))
        self.assertGreaterEqual(distinct_sigs, int(0.9 * n))

    def test_no_tpose_in_idle_rest_frame(self):
        bad, worst = [], 0.0
        for sid in species():
            rep = PC.tpose_report(glb(sid), 'Idle', 0.0, plan=plans().get(sid))
            for k, r in rep.items():
                if r['role'] == 'Arm':
                    worst = max(worst, r['down'])
                if r['violation']:
                    bad.append((sid, k, round(r['down']), round(r['spread'])))
        print('\nT-pose violations: %d (worst arm angle from straight down: %.1f deg)' % (len(bad), worst))
        self.assertEqual(bad, [])

    def test_clips_of_a_species_are_distinct(self):
        worst = (9.0, '')
        weak = []
        for sid in species():
            g = glb(sid)
            feats, rest = PC.clip_features(g, samples=10)
            H = g.H
            names = list(feats)
            for n in names:            # every clip actually moves the body
                act = float(np.linalg.norm(feats[n], axis=2).mean()) / H
                if act < 0.002:
                    weak.append((sid, n, act))
            for a, b in itertools.combinations(names, 2):
                d = float(np.linalg.norm(feats[a] - feats[b], axis=2).mean()) / H
                if d < worst[0]:
                    worst = (d, '%s %s/%s' % (sid, a, b))
                if d < MIN_CLIP_DISTANCE:
                    weak.append((sid, a, b, round(d, 4)))
        print('\nclosest pair of clips within a species: %.4f H (%s)' % worst)
        self.assertEqual(weak, [])

    def test_same_clip_differs_between_species_of_one_plan(self):
        pl = plans()
        by = {}
        for sid in species():
            by.setdefault(pl.get(sid, '?'), []).append(sid)

        def feat(sid, clip):
            g = glb(sid)
            f, _ = PC.clip_features(g, samples=8, nv=200)
            x = f[clip] / g.H                                  # (8, n, 3)
            mag = np.linalg.norm(x, axis=2)
            return np.concatenate([mag.mean(1), mag.max(1), np.abs(x[:, :, 1]).mean(1), np.abs(x[:, :, 0]).mean(1)])
        same, checked = [], 0
        for plan, ids in by.items():
            if len(ids) < 2:
                continue
            for clip in ('Idle', 'Walk', 'Attack', 'Victory'):
                fs = {sid: feat(sid, clip) for sid in ids[:8]}
                for a, b in itertools.combinations(fs, 2):
                    checked += 1
                    d = float(np.abs(fs[a] - fs[b]).mean())
                    if d < MIN_SAME_CLIP_DISTANCE:
                        same.append((plan, clip, a, b, round(d, 5)))
        print('\nsame-named clips compared across same-plan species: %d pairs, %d too similar' % (checked, len(same)))
        self.assertEqual(same, [])

    def test_no_mesh_explosions(self):
        worst = (1.0, '')
        bad = []
        for sid in species():
            g = glb(sid)
            for clip in g.anims:
                s = PC.stretch(g, clip, frames=5)
                if s > worst[0]:
                    worst = (s, '%s/%s' % (sid, clip))
                if s > MAX_STRETCH:
                    bad.append((sid, clip, round(s, 1)))
        print('\nworst edge stretch: %.2fx (%s)' % worst)
        self.assertEqual(bad, [])

    def test_looping_clips_close_seamlessly(self):
        bad = []
        for sid in species():
            g = glb(sid)
            for clip in ('Idle', 'Walk', 'Run', 'Sleep', 'Charge', 'Taunt', 'Hover', 'Talk'):
                dur = g.duration(clip)
                a, b = g.skin(clip, 0.0, np.arange(0, len(g.P), 40)), g.skin(clip, dur, np.arange(0, len(g.P), 40))
                d = float(np.linalg.norm(a - b, axis=1).max()) / g.H
                if d > 0.01:
                    bad.append((sid, clip, round(d, 4)))
        self.assertEqual(bad, [])


if __name__ == '__main__':
    unittest.main()
