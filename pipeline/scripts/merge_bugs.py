"""Merges docs/bugs/*.md (one table per review area) into docs/BUGFIXES.md with a numbered index and totals.

    python3 pipeline/scripts/merge_bugs.py
"""
import glob
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
TITLES = {
    'battle-engine': 'Battle engine (BattleEngine / BattleMath / BattleSide)',
    'battle-presentation': 'Battle presentation (scene, VFX, HUD, actors, shaders)',
    'overworld': 'Overworld (scene, maps, encounters, fx, util)',
    'story': 'Story scripts (Story.gd and story/*)',
    'ui-audio': 'UI, menus, audio, scene routing',
    'state-data-pipeline': 'Game state, data, pipeline, shaders',
    'characters-tools': 'Character pipeline, tools',
    'new-features': 'This branch\'s new features',
    'misc': 'Found while testing',
}


def rows_of(path):
    out = []
    for line in open(path, encoding='utf-8'):
        m = re.match(r'^\|\s*\d+[a-z]?\s*\|(.+)\|\s*$', line)
        if m:
            cells = [c.strip() for c in m.group(1).split('|')]
            if len(cells) >= 3:
                out.append(cells[:3])
    return out


def main():
    parts, total = [], 0
    index = []
    for path in sorted(glob.glob(os.path.join(ROOT, 'docs', 'bugs', '*.md')), key=lambda p: list(TITLES).index(os.path.basename(p)[:-3]) if os.path.basename(p)[:-3] in TITLES else 99):
        key = os.path.basename(path)[:-3]
        rows = rows_of(path)
        if not rows:
            continue
        title = TITLES.get(key, key)
        index.append('* **%s**: %d' % (title, len(rows)))
        body = ['## %s (%d)' % (title, len(rows)), '', '| # | Where | Symptom | Fix |', '|---|---|---|---|']
        for r in rows:
            total += 1
            body.append('| %d | %s | %s | %s |' % (total, r[0], r[1], r[2]))
        parts.append('\n'.join(body))
    head = ['# Bug-fix log', '',
            'A review of every subsystem found and fixed **%d bugs**. Each was checked against the code (and against the upstream '
            'JS game where the rule comes from it) before being fixed; the per-area source tables live in `docs/bugs/`.' % total, '']
    open(os.path.join(ROOT, 'docs', 'BUGFIXES.md'), 'w', encoding='utf-8').write('\n'.join(head + index + [''] + parts) + '\n')
    print('wrote docs/BUGFIXES.md with', total, 'bugs')


if __name__ == '__main__':
    main()
