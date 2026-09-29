#!/usr/bin/env python3
"""Builds godot/data/versions.json: everything that differs between POKeMON RED, BLUE and YELLOW.

The base game data (godot/data/pokedata.json, ported from the upstream Pokemon Claude Red remake) is RED.
This script reads the pret disassemblies (https://github.com/pret/pokered and https://github.com/pret/pokeyellow)
and extracts, per version:

  wild        map constant -> {grass:{rate,mons:[[lvl,SPECIES]x10]}, water:{...}}   (pokered has IF DEF(_RED)/(_BLUE) blocks)
  goodRod     [[lvl,SPECIES]...]            superRod  map constant -> [[lvl,SPECIES]...]
  trades      the 10 in-game trades (index = TRADE_FOR_* order)
  prizes      Game Corner prize windows (species/TM, coin cost, level)
  marts       {ClerkTextLabel: [items]} for the marts whose stock differs
  parties     (YELLOW only) trainer class -> [party -> [[lvl,SPECIES]...]]  same shape as pokedata.json "parties"
  specialMoves(YELLOW only) class -> {party number -> [[mon 1..6, slot 1..4, MOVE]...]} custom movesets
  species     (YELLOW only) SPECIES -> the fields that differ from RED (base stats, start moves, learnset, evolutions, ...)
  objects     (YELLOW only) map name -> {patch:{TEXT_CONST:{...}}, add:[obj...], remove:[TEXT_CONST...]} on top of the RED maps

Usage:  python3 pipeline/scripts/extract_versions.py [--cache DIR] [--out godot/data/versions.json]
The pret sources are downloaded from raw.githubusercontent.com into --cache (default $PRET_CACHE or /tmp/pret-cache).
Everything is deterministic, so re-running produces an identical file.
"""
import argparse, json, os, re, sys, urllib.request, concurrent.futures as cf

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CACHE = os.environ.get('PRET_CACHE', '/tmp/pret-cache')


def fetch(repo, path):
    dst = os.path.join(CACHE, repo, path)
    if not os.path.exists(dst):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        data = urllib.request.urlopen(f'https://raw.githubusercontent.com/pret/{repo}/master/{path}', timeout=60).read()
        open(dst, 'wb').write(data)
    return open(dst, encoding='utf-8').read()


def prefetch(jobs):
    def one(j):
        try:
            fetch(*j)
        except Exception as e:  # a missing optional file is reported when it is actually needed
            return (j, str(e))
    with cf.ThreadPoolExecutor(16) as ex:
        for r in ex.map(one, jobs):
            if r:
                print('  (not available)', r[0][1], r[1][:40], file=sys.stderr)


def preprocess(text, flag):
    """Resolves IF DEF(_RED) / IF DEF(_BLUE) / ELSE / ENDC for the given flag ('_RED', '_BLUE', '_YELLOW')."""
    out, stack = [], []  # stack of (active, taken)
    for line in text.split('\n'):
        s = line.split(';')[0].strip()
        m = re.match(r'IF DEF\((\w+)\)', s)
        if m:
            on = m.group(1) == flag
            stack.append([on, on])
            continue
        if s == 'ELSE' and stack:
            stack[-1][0] = not stack[-1][1]
            continue
        if s == 'ENDC' and stack:
            stack.pop()
            continue
        if all(a for a, _ in stack):
            out.append(line)
    return '\n'.join(out)


def clean(line):
    return line.split(';')[0].strip()


def norm(name):
    """pret constant -> the id used by pokedata.json."""
    return {'NIDORAN_M': 'NIDORAN_M', 'NIDORAN_F': 'NIDORAN_F', 'MR_MIME': 'MR_MIME', 'FARFETCH_D': 'FARFETCHD',
            'PSYCHIC_M': 'PSYCHIC_M', 'PSYCHIC': 'PSYCHIC_TYPE'}.get(name, name)


# ---------------------------------------------------------------- maps
def map_constants(repo):
    t = fetch(repo, 'constants/map_constants.asm')
    ids = {}
    for m in re.finditer(r'map_const (\w+),\s*\d+,\s*\d+\s*;\s*\$([0-9A-Fa-f]+)', t):
        ids[int(m.group(2), 16)] = m.group(1)
    return ids


# ---------------------------------------------------------------- wild
def parse_wild(repo, flag):
    ids = map_constants(repo)
    gw = fetch(repo, 'data/wild/grass_water.asm')
    incs = sorted(set(re.findall(r'data/wild/maps/\w+\.asm', gw)))
    prefetch([(repo, p) for p in incs])
    body = ''.join(fetch(repo, p) + '\n' for p in incs)
    body = preprocess(body, flag)
    blocks = {}
    for m in re.finditer(r'^(\w+):\n(.*?)(?=^\w+:|\Z)', body, re.S | re.M):
        blocks[m.group(1)] = m.group(2)
    ptrs = re.findall(r'dw (\w+)', gw.split('WildDataPointers:')[1].split('assert_table_length')[0]
                      if 'assert_table_length' in gw else gw.split('WildDataPointers:')[1])
    out = {}
    for i, label in enumerate(ptrs):
        if label == 'NothingWildMons' or label not in blocks or i not in ids:
            continue
        blk = blocks[label]
        entry = {}
        for kind in ('grass', 'water'):
            m = re.search(r'def_%s_wildmons (\d+)(.*?)end_%s_wildmons' % (kind, kind), blk, re.S)
            mons = []
            rate = 0
            if m:
                rate = int(m.group(1))
                for l in m.group(2).split('\n'):
                    mm = re.match(r'\s*db\s+(\d+),\s*(\w+)', l)
                    if mm:
                        mons.append([int(mm.group(1)), norm(mm.group(2))])
            entry[kind] = {'rate': rate, 'mons': mons if rate else []}
        if entry['grass']['rate'] or entry['water']['rate']:
            out[ids[i]] = entry
    return out


def parse_good_rod(repo):
    t = fetch(repo, 'data/wild/good_rod.asm')
    return [[int(a), norm(b)] for a, b in re.findall(r'db\s+(\d+),\s*(\w+)', t)]


def parse_super_rod(repo):
    t = preprocess(fetch(repo, 'data/wild/super_rod.asm'), '_RED')
    out = {}
    if 'dbw' in t:  # pokered: map -> group, groups hold count + level/mon pairs
        groups = {}
        for m in re.finditer(r'^\.(Group\d+):\n(.*?)(?=^\.Group|\Z)', t, re.S | re.M):
            pairs = re.findall(r'db\s+(\d+),\s*(\w+)', m.group(2))
            groups[m.group(1)] = [[int(a), norm(b)] for a, b in pairs]
        for c, g in re.findall(r'dbw (\w+),\s*\.(Group\d+)', t):
            out[c] = groups[g]
    else:  # pokeyellow: db MAP, MON, lvl, MON, lvl, MON, lvl, MON, lvl
        for l in t.split('\n'):
            l = clean(l)
            m = re.match(r'db\s+([A-Z_0-9]+),\s*(.*)', l)
            if not m or m.group(1) == '-1':
                continue
            a = [x.strip() for x in m.group(2).split(',')]
            if len(a) == 8:
                out[m.group(1)] = [[int(a[i + 1]), norm(a[i])] for i in range(0, 8, 2)]
    return out


# ---------------------------------------------------------------- trades / prizes / marts
def parse_trades(repo):
    t = fetch(repo, 'data/events/trades.asm')
    res = []
    for m in re.finditer(r'npctrade\s+(\w+),\s*(\w+),\s*(\w+),\s*"([^"]+)"', t):
        res.append({'give': norm(m.group(1)), 'get': norm(m.group(2)), 'dialog': m.group(3), 'nick': m.group(4)})
    return res


def parse_prizes(repo, flag):
    t = preprocess(fetch(repo, 'data/events/prizes.asm'), flag)
    lv = preprocess(fetch(repo, 'data/events/prize_mon_levels.asm'), flag)
    levels = {norm(a): int(b) for a, b in re.findall(r'db\s+(\w+),\s*(\d+)', lv)}
    def entries(label):
        blk = re.search(r'^%s:\n(.*?)(?=^\w+:|\Z)' % label, t, re.S | re.M).group(1)
        return [norm(x) for x in re.findall(r'db\s+([A-Z_0-9]+)', blk)]
    def costs(label):
        blk = re.search(r'^%s:\n(.*?)(?=^\w+:|\Z)' % label, t, re.S | re.M).group(1)
        return [int(x) for x in re.findall(r'bcd2\s+(\d+)', blk)]
    out = []
    for k, tm in (('Mon1', False), ('Mon2', False), ('TMs', True)):
        e = entries('PrizeMenu%sEntries' % k)
        c = costs('PrizeMenu%sCost' % k)
        out.append([[s, c[i]] if tm else [s, c[i], levels[s]] for i, s in enumerate(e)])
    return out


def parse_marts(repo):
    """{ClerkText label: [items]} from data/items/marts.asm"""
    t = fetch(repo, 'data/items/marts.asm')
    res = {}
    for m in re.finditer(r'^(\w+)::[^\n]*\n\s*script_mart\s+([A-Z_0-9, ]+)', t, re.M):
        res[m.group(1)] = [x.strip() for x in m.group(2).split(',')]
    return res


# ---------------------------------------------------------------- trainers
def parse_parties(repo, flag):
    t = preprocess(fetch(repo, 'data/trainers/parties.asm'), flag)
    order = re.findall(r'dw (\w+Data)', t.split('TrainerDataPointers:')[1].split('assert_table_length')[0])
    blocks = {}
    for m in re.finditer(r'^(\w+Data):\n(.*?)(?=^\w+Data:|\Z)', t, re.S | re.M):
        blocks[m.group(1)] = m.group(2)
    res = []
    for lab in order:
        parties = []
        for l in blocks.get(lab, '').split('\n'):
            l = clean(l)
            m = re.match(r'db\s+(.*)', l)
            if not m:
                continue
            a = [x.strip() for x in m.group(1).split(',')]
            if a[-1] != '0':
                continue
            a = a[:-1]
            if a and a[0] == '$FF':
                a = a[1:]
                parties.append([[int(a[i]), norm(a[i + 1])] for i in range(0, len(a), 2)])
            elif a:
                parties.append([[int(a[0]), norm(s)] for s in a[1:]])
        res.append(parties)
    return res


def parse_special_moves(repo):
    t = fetch(repo, 'data/trainers/special_moves.asm')
    out = {}
    cur = None
    for l in t.split('\n'):
        l = clean(l)
        m = re.match(r'db\s+(\w+),\s*(\d+)$', l)
        if m and not re.match(r'db\s+\d', l):
            cur = (m.group(1), int(m.group(2)))
            out.setdefault(cur[0], {})[cur[1]] = []
            continue
        m = re.match(r'db\s+(\d+),\s*(\d+),\s*(\w+)', l)
        if m and cur:
            out[cur[0]][cur[1]].append([int(m.group(1)), int(m.group(2)), m.group(3)])
    return out


# ---------------------------------------------------------------- species
def parse_species(repo):
    """DEX-name -> {hp,atk,def,spd,spc,types,catchRate,baseExp,moves1,growth,tmhm}"""
    bs = fetch(repo, 'data/pokemon/base_stats.asm')
    files = re.findall(r'INCLUDE "(data/pokemon/base_stats/\w+\.asm)"', bs)
    prefetch([(repo, f) for f in files])
    stats = {}
    for f in files:
        t = fetch(repo, f)
        flat = re.sub(r'\\\s*\n', ' ', t)  # join the `\` continuation lines of the tmhm list
        lines = [clean(l) for l in flat.split('\n')]
        db = [l for l in lines if l.startswith('db')]
        dex = re.match(r'db\s+DEX_(\w+)', db[0]).group(1)
        nums = [int(x) for x in re.findall(r'\d+', db[1])]
        types = [x.strip() for x in db[2][2:].split(',')]
        if types[0] == types[1]:
            types = types[:1]
        d = {'hp': nums[0], 'atk': nums[1], 'def': nums[2], 'spd': nums[3], 'spc': nums[4], 'types': types,
             'catchRate': int(db[3].split()[1]), 'baseExp': int(db[4].split()[1])}
        st = [x.strip() for x in db[5][2:].split(',')]
        d['moves1'] = [x for x in st if x not in ('NO_MOVE', '0')]
        d['growth'] = db[6].split()[1].replace('GROWTH_', '')
        tm = [l for l in lines if l.startswith('tmhm')]
        d['tmhm'] = [x.strip() for x in tm[0][4:].split(',') if x.strip()] if tm else []
        stats[dex] = d
    return stats


def parse_evos_moves(repo):
    t = fetch(repo, 'data/pokemon/evos_moves.asm')
    res = {}
    for m in re.finditer(r'^(\w+)EvosMoves:\n(.*?)(?=^\w+EvosMoves:|\Z)', t, re.S | re.M):
        name = m.group(1)
        body = m.group(2)
        ev_part, _, lm_part = body.partition('; Learnset')
        evos = []
        for l in ev_part.split('\n'):
            l = clean(l)
            mm = re.match(r'db\s+EVOLVE_LEVEL,\s*(\d+),\s*(\w+)', l)
            if mm:
                evos.append({'type': 'level', 'level': int(mm.group(1)), 'to': norm(mm.group(2))})
            mm = re.match(r'db\s+EVOLVE_ITEM,\s*(\w+),\s*\d+,\s*(\w+)', l)
            if mm:
                evos.append({'type': 'item', 'item': mm.group(1), 'to': norm(mm.group(2))})
            mm = re.match(r'db\s+EVOLVE_TRADE,\s*\d+,\s*(\w+)', l)
            if mm:
                evos.append({'type': 'trade', 'to': norm(mm.group(1))})
        learn = [[int(a), b] for a, b in re.findall(r'db\s+(\d+),\s*([A-Z_0-9]+)', lm_part)]
        res[name] = {'evos': evos, 'learn': learn}
    return res


# ---------------------------------------------------------------- objects
def parse_objects(repo, m):
    try:
        t = fetch(repo, f'data/maps/objects/{m}.asm')
    except Exception:
        return None
    ids = re.findall(r'const_export (\w+)', t)
    body = t.split('def_object_events')[1].split('def_warps_to')[0] if 'def_object_events' in t else ''
    objs = []
    for l in body.split('\n'):
        l = clean(l)
        if not l.startswith('object_event'):
            continue
        a = [x.strip() for x in l[len('object_event'):].split(',')]
        o = {'x': int(a[0]), 'y': int(a[1]), 'sprite': a[2][7:].lower(), 'move': a[3], 'dir': a[4], 'text': a[5]}
        if len(a) >= 8 and a[6].startswith('OPP_'):
            o['trainer'] = {'cls': norm_class(a[6][4:]), 'n': int(a[7])}
        elif len(a) >= 7 and not a[6].startswith('OPP_'):
            o['item'] = a[6]
        objs.append(o)
    for i, o in enumerate(objs):
        o['id'] = ids[i] if i < len(ids) else ''
    return objs


def norm_class(c):
    return {'PSYCHIC': 'PSYCHIC_TR', 'JR_TRAINER_M': 'JR_TRAINER_M', 'JR_TRAINER_F': 'JR_TRAINER_F'}.get(c, c)


SPRITE_ALIAS = {  # sprites Yellow adds that have no model of their own here -> the closest cast member
    'jessie': 'brunette_girl', 'james': 'rocket', 'officer_jenny': 'cooltrainer_f', 'chansey': 'mon:CHANSEY',
    'jigglypuff': 'mon:JIGGLYPUFF', 'clefairy': 'mon:CLEFAIRY', 'pikachu': 'mon:PIKACHU',
}


# Yellow renamed / replaced a few maps: the RED map -> the YELLOW map whose objects and text replace it
MAP_ALIAS = {'CeruleanTradeHouse': 'CeruleanMelaniesHouse'}


def object_overlay(map_names, species):
    out = {}
    prefetch([(r, f'data/maps/objects/{MAP_ALIAS.get(m, m)}.asm') for m in map_names for r in ('pokered', 'pokeyellow')])
    for m in map_names:
        r = parse_objects('pokered', m)
        y = parse_objects('pokeyellow', MAP_ALIAS.get(m, m))
        if r is None or y is None:
            continue
        for o in y:
            if o['sprite'].upper() in species:   # Bulbasaur, Oddish, Sandshrew ... stand in Melanie's house as Pokemon
                o['sprite'] = 'mon:' + o['sprite'].upper()
        rk = {o['text']: o for o in r}
        yk = {o['text']: o for o in y}
        patch, add, remove = {}, [], []
        for t, yo in yk.items():
            ro = rk.get(t)
            if ro is None:
                o = dict(yo)
                o['sprite'] = SPRITE_ALIAS.get(o['sprite'], o['sprite'])
                add.append(o)
                continue
            diff = {}
            for k in ('x', 'y', 'move', 'dir', 'trainer', 'item'):
                if ro.get(k) != yo.get(k):
                    diff[k] = yo.get(k)
            if ro['sprite'] != yo['sprite']:
                diff['sprite'] = SPRITE_ALIAS.get(yo['sprite'], yo['sprite'])
            if diff:
                patch[t] = diff
        for t in rk:
            if t not in yk:
                remove.append(t)
        if patch or add or remove:
            out[m] = {'patch': patch, 'add': add, 'remove': remove}
    return out


# ---------------------------------------------------------------- text
def to_text(cmds):
    """pret text macros -> the string format of godot/data/text.json ('\\f' = page break, {PLAYER}/{RIVAL} kept)."""
    out = ''
    for c, arg in cmds:
        arg = (arg.replace('#MON', 'POKéMON').replace('<PKMN>', 'POKéMON').replace('<PK><MN>', 'POKéMON')
               .replace('#', 'POKé').replace('<PLAYER>', '{PLAYER}').replace('<RIVAL>', '{RIVAL}')
               .replace('<TARGET>', '').replace('<USER>', ''))
        arg = re.sub(r'<[A-Z0-9_]+>', '', arg)
        if c == 'text':
            out += arg if not out else ' ' + arg
        elif c in ('line', 'cont', 'next'):
            out += ' ' + arg
        elif c in ('para', 'page'):
            out += '\f' + arg
        elif c == 'ram':
            out += '{' + arg + '}'
    return re.sub(r' +', ' ', out).strip()


def parse_text_file(t):
    res = {}
    for m in re.finditer(r'^_?(\w+)::\n(.*?)(?=^_?\w+::|\Z)', t, re.S | re.M):
        cmds = []
        for l in m.group(2).split('\n'):
            l = l.strip()
            mm = re.match(r'(text|line|cont|para|page|next)\s+"(.*)"', l)
            if mm:
                cmds.append((mm.group(1), mm.group(2)))
                continue
            mm = re.match(r'text_ram\s+(\w+)', l)
            if mm:
                cmds.append(('ram', mm.group(1)))
        if cmds:
            res[m.group(1)] = to_text(cmds)
    return res


def text_overrides(map_names):
    """Labels whose text differs between pokered and pokeyellow (or exists only in Yellow)."""
    map_names = list(map_names) + ['CeruleanMelaniesHouse', 'SummerBeachHouse']
    prefetch([(r, f'text/{m}.asm') for m in map_names for r in ('pokered', 'pokeyellow')])
    out = {}
    for m in map_names:
        try:
            r = parse_text_file(fetch('pokered', f'text/{m}.asm'))
        except Exception:
            r = {}
        try:
            y = parse_text_file(fetch('pokeyellow', f'text/{m}.asm'))
        except Exception:
            continue
        for k, v in y.items():
            if r.get(k) != v:
                out[k] = v
    return out


# ---------------------------------------------------------------- main
def main():
    global CACHE
    ap = argparse.ArgumentParser()
    ap.add_argument('--cache', default=CACHE)
    ap.add_argument('--out', default=os.path.join(ROOT, 'godot/data/versions.json'))
    args = ap.parse_args()
    CACHE = args.cache
    pd = json.load(open(os.path.join(ROOT, 'godot/data/pokedata.json')))
    md = json.load(open(os.path.join(ROOT, 'godot/data/mapdata.json')))
    classes = list(pd['parties'].keys())
    res = {'versions': ['RED', 'BLUE', 'YELLOW'], 'source': 'pret/pokered + pret/pokeyellow (data/*.asm)'}

    wild, rods, srods, trades, prizes = {}, {}, {}, {}, {}
    for v, repo, flag in (('RED', 'pokered', '_RED'), ('BLUE', 'pokered', '_BLUE'), ('YELLOW', 'pokeyellow', '_YELLOW')):
        wild[v] = parse_wild(repo, flag)
        rods[v] = parse_good_rod(repo)
        srods[v] = parse_super_rod(repo)
        trades[v] = parse_trades(repo)
        prizes[v] = parse_prizes(repo, flag)
    res.update({'wild': wild, 'goodRod': rods, 'superRod': srods, 'trades': trades, 'prizes': prizes})

    # marts: pokered's list order is the ClerkText order of pokedata.json["marts"]
    mr = parse_marts('pokered')
    my = parse_marts('pokeyellow')
    marts = {}
    for lab in pd['marts'].keys():
        if mr.get(lab) is not None and mr[lab] != pd['marts'][lab]:
            print('  note: pokered mart', lab, 'differs from the base data', file=sys.stderr)
        if my.get(lab) and my[lab] != mr.get(lab):
            marts[lab] = my[lab]
    res['marts'] = {'YELLOW': marts}

    # trainer parties
    pr = parse_parties('pokered', '_RED')
    py = parse_parties('pokeyellow', '_YELLOW')
    res['parties'] = {'YELLOW': {c: py[i] for i, c in enumerate(classes)}}
    res['redPartiesMatchBase'] = all(pr[i] == pd['parties'][c] for i, c in enumerate(classes))
    res['specialMoves'] = {'YELLOW': parse_special_moves('pokeyellow')}
    # Jessie & James are four ROCKET parties (Mt. Moon B2F, Rocket Hideout B4F, Pokemon Tower 7F, Silph Co. 11F), 1-based
    rk = res['parties']['YELLOW']['ROCKET']
    jj = [[14, 'EKANS'], [14, 'MEOWTH'], [14, 'KOFFING']]
    first = rk.index(jj) + 1
    res['jessieJames'] = {'MtMoonB2F': first, 'RocketHideoutB4F': first + 1, 'PokemonTower7F': first + 2, 'SilphCo11F': first + 3}

    # species overrides for YELLOW
    sr, sy = parse_species('pokered'), parse_species('pokeyellow')
    er, ey = parse_evos_moves('pokered'), parse_evos_moves('pokeyellow')
    by_dex = {}
    for sid, sp in pd['species'].items():
        by_dex[sp['id']] = sp
    dexname = {}  # pret base_stats file uses DEX_<NAME> = the species constant
    over = {}
    for k, ys in sy.items():
        sid = norm(k)
        base = pd['species'].get(sid)
        if base is None:
            continue
        diff = {}
        for f in ('hp', 'atk', 'def', 'spd', 'spc', 'types', 'catchRate', 'baseExp', 'moves1', 'growth', 'tmhm'):
            if ys.get(f) != base.get(f) and ys.get(f) not in (None, ''):
                diff[f] = ys[f]
        key = k.title().replace('_', '')
        # evos_moves labels are CamelCase-ish (e.g. "Nidoranm")
        cand = [n for n in ey if n.upper() == k.replace('_', '').upper()]
        if cand:
            e = ey[cand[0]]
            if e['learn'] != base.get('learn'):
                diff['learn'] = e['learn']
            if e['evos'] != base.get('evos'):
                diff['evos'] = e['evos']
        if diff:
            over[sid] = diff
    res['species'] = {'YELLOW': over}

    # map objects (trainers / items / added and removed NPCs)
    res['objects'] = {'YELLOW': object_overlay(list(md['maps'].keys()), set(pd['species'].keys()))}
    res['text'] = {'YELLOW': text_overrides(list(md['maps'].keys()))}
    print('yellow text overrides:', len(res['text']['YELLOW']))

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w') as f:
        json.dump(res, f, separators=(',', ':'), sort_keys=True)
    print('wrote', args.out, os.path.getsize(args.out), 'bytes')
    for v in res['versions']:
        print(v, 'wild maps', len(wild[v]), 'superRod', len(srods[v]), 'trades', len(trades[v]))
    print('red parties match base:', res['redPartiesMatchBase'])
    print('yellow species overrides:', len(over), 'object maps:', len(res['objects']['YELLOW']))


if __name__ == '__main__':
    main()
