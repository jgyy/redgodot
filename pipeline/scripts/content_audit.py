#!/usr/bin/env python3
"""Numbers behind docs/CONTENT_AUDIT.md: compares the game's data files with the pret disassemblies
(pokered = RED/BLUE, pokeyellow = YELLOW) and prints one line per checklist row.

  python3 pipeline/scripts/content_audit.py [--cache DIR]      (needs the pret cache written by extract_versions.py)
"""
import argparse, json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import extract_versions as ev

ROOT = ev.ROOT


def obj_stats(repo, m):
    try:
        t = ev.fetch(repo, f'data/maps/objects/{m}.asm')
    except Exception:
        return None
    warps = len(re.findall(r'^\s*warp_event\b', t, re.M))
    bgs = re.findall(r'^\s*bg_event\s+([^;\n]*)', t, re.M)
    bg_all = len(bgs)
    objs = ev.parse_objects(repo, m) or []
    return {
        'warps': warps,
        'signs': bg_all,
        'objects': len(objs),
        'trainers': sum(1 for o in objs if 'trainer' in o),
        'items': sum(1 for o in objs if 'item' in o),
        'tms': sum(1 for o in objs if str(o.get('item', '')).startswith('TM_') or str(o.get('item', '')).startswith('HM_')),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cache', default=ev.CACHE)
    args = ap.parse_args()
    ev.CACHE = args.cache
    md = json.load(open(os.path.join(ROOT, 'godot/data/mapdata.json')))
    pd = json.load(open(os.path.join(ROOT, 'godot/data/pokedata.json')))
    vs = json.load(open(os.path.join(ROOT, 'godot/data/versions.json')))
    maps = md['maps']
    ev.ITEMS = set(pd['items'].keys())
    ev.prefetch([(r, f'data/maps/objects/{m}.asm') for m in maps for r in ('pokered', 'pokeyellow')])
    tot = {'game': dict(warps=0, objects=0, trainers=0, items=0, tms=0, signs=0)}
    for r in ('pokered', 'pokeyellow'):
        tot[r] = dict(warps=0, objects=0, trainers=0, items=0, tms=0, signs=0)
    per_map_diff = []
    for name, m in maps.items():
        tot['game']['warps'] += len(m.get('warps', []))
        tot['game']['signs'] += len(m.get('signs', [])) + len(m.get('hidden', []))
        tot['game']['objects'] += len(m.get('objs', []))
        tot['game']['trainers'] += sum(1 for o in m.get('objs', []) if 'trainer' in o)
        tot['game']['items'] += sum(1 for o in m.get('objs', []) if 'item' in o)
        tot['game']['tms'] += sum(1 for o in m.get('objs', []) if str(o.get('item', '')).startswith(('TM_', 'HM_')))
        for r in ('pokered', 'pokeyellow'):
            s = obj_stats(r, name)
            if not s:
                continue
            for k in ('warps', 'objects', 'trainers', 'items', 'tms', 'signs'):
                tot[r][k] += s[k]
        s = obj_stats('pokered', name)
        if s and (s['warps'] != len(m.get('warps', [])) or s['trainers'] != sum(1 for o in m.get('objs', []) if 'trainer' in o)):
            per_map_diff.append(name)
    print('maps in mapdata.json:', len(maps))
    print('totals (game RED data | pokered | pokeyellow):')
    for k in ('warps', 'objects', 'trainers', 'items', 'tms', 'signs'):
        print(f'  {k:9s} {tot["game"][k]:5d} | {tot["pokered"][k]:5d} | {tot["pokeyellow"][k]:5d}')
    print('maps whose warp/trainer count differs from pokered:', per_map_diff)
    print('species', len(pd['species']), 'moves', len(pd['moves']), 'items', len(pd['items']), 'tm moves', len(pd['tmMoves']), 'hm', pd['hmMoves'])
    print('trainer classes', len(pd['trainerClasses']), 'parties', sum(len(v) for v in pd['parties'].values()),
          'yellow parties', sum(len(v) for v in vs['parties']['YELLOW'].values()))
    print('wild tables (RED/BLUE/YELLOW):', {v: len(vs['wild'][v]) for v in vs['versions']})
    # Yellow overlay coverage
    ov = vs['objects']['YELLOW']
    patched = sum(len(x['patch']) for x in ov.values())
    added = sum(len(x['add']) for x in ov.values())
    removed = sum(len(x['remove']) for x in ov.values())
    print(f'YELLOW overlay: {len(ov)} maps, {patched} patched objects, {added} added, {removed} removed; {len(vs["text"]["YELLOW"])} text labels; {len(vs["species"]["YELLOW"])} species changed')


if __name__ == '__main__':
    main()
