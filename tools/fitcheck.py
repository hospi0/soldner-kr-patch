# -*- coding: utf-8 -*-
r"""대사 줄 맞춤 검사(빌더와 같은 규칙, tools/linefit.py) — 줄 폭·쪽 줄 수를 넘는 행을 줄별 폭과 함께 보여 준다
  python tools/fitcheck.py [번역폴더]   (기본 work/text)
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import linefit
from build import wide


def load(d, name):
    return [l.rstrip('\r\n').split('\t') for l in open(os.path.join(d, name), encoding='utf-8') if not l.startswith('#')]


def names_from(d):
    names = {0: 72}
    for r in load(d, 'exe.tsv'):
        k, rr = divmod(int(r[0][1:], 16) - 0xB7D48, 21)
        if rr == 0 and 0 < k < 256 and len(r) > 3 and r[3] not in ('', '='):
            names[k] = linefit.width(wide(r[3]))
    return names


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    d = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'work', 'text')
    names = names_from(d)
    rows = {r[0]: r for r in load(d, 'msg.tsv') if len(r) > 3 and r[3] not in ('', '=')}
    texts = {k: wide(r[3]) for k, r in rows.items()}
    lim_of = lambda k: 156 if k.startswith('20:') and '{z}' not in rows[k][2] else 232
    fitted, warn = linefit.fit_all(texts, lim_of, names)
    for x in warn:
        print(x)
    n = len(warn)
    if len(sys.argv) > 2:                                  # 문장 번호를 주면 맞춘 결과를 줄별 폭과 함께
        for k in sys.argv[2:]:
            print(k, ' | '.join('%d:%s' % (linefit.width(x, names), x) for x in fitted[k].split('\n')))
    print('경고 행', n)


if __name__ == '__main__':
    main()
