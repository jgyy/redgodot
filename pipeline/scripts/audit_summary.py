#!/usr/bin/env python3
"""Counts done / partial / missing (before and after) in docs/CONTENT_AUDIT.md and rewrites its Summary table.

  python3 pipeline/scripts/audit_summary.py          # rewrite the summary in place
  python3 pipeline/scripts/audit_summary.py --check  # exit 1 if the summary is out of date (used by CI)
"""
import os, re, sys

DOC = os.path.join(os.path.dirname(__file__), '..', '..', 'docs', 'CONTENT_AUDIT.md')
ROW = re.compile(r'^\| (?P<item>.+?) \| (?P<before>done|partial|missing)[^|]* \| (?P<after>done|partial|missing)[^|]* \|')


def counts(text):
    before = {'done': 0, 'partial': 0, 'missing': 0}
    after = dict(before)
    for line in text.split('\n'):
        m = ROW.match(line)
        if m and m.group('item') not in ('Item', 'Mechanic'):
            before[m.group('before')] += 1
            after[m.group('after')] += 1
    return before, after


def table(before, after):
    def row(name, c):
        return f'| {name} | {c["done"]} | {c["partial"]} | {c["missing"]} | {sum(c.values())} |'
    return '\n'.join(['| | done | partial | missing | rows |', '| --- | ---: | ---: | ---: | ---: |', row('Before', before), row('After', after)])


def main():
    text = open(DOC, encoding='utf-8').read()
    before, after = counts(text)
    new = re.sub(r'(<!-- SUMMARY:START -->\n).*?(\n<!-- SUMMARY:END -->)', lambda m: m.group(1) + table(before, after) + m.group(2), text, flags=re.S)
    print('before', before, 'after', after)
    if '--check' in sys.argv:
        sys.exit(0 if new == text else 1)
    open(DOC, 'w', encoding='utf-8').write(new)


if __name__ == '__main__':
    main()
