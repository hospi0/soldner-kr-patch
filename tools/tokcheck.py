# -*- coding: utf-8 -*-
r"""번역문 제어 표기 검사 — 원문 토큰이 «빠짐·추가·순서 바뀜·인수 변경» 없이 그대로 있는지
  ★이 게임 문제는 대개 원문 토큰 손상에서 온다(사용자 지적 2026-09-26). build.py 가 모든 번역 행에 이 검사를 건다.
  msg.tsv : 제어 표기 {z} {g} {s:02ce} {y:00006e0071} {00} … 의 «순서열»이 원문과 같아야 한다. 줄바꿈 \n 만 자유.
            ({g}{z} = 새 쪽, {y:…} = 예/아니요 이동, {b:00} = 숫자 끼움, {00} = 문장 끝 — 하나라도 어긋나면 멈춤·크래시)
  그 밖 표(exe·kana·job·bevent·scenario) : {xx} 바이트 표기의 순서열이 원문과 같아야 한다. \n 은 자유.
  공통 : 제어 표기 꼴이 아닌 «{» «}» «\» 가 남아 있으면(오타 {s:2ce} · {z } · \N 등) 오류.
  python tools/tokcheck.py [번역폴더]      (기본 work/text)
"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import msgcode

TOK_MSG = re.compile(r'\{[a-z](?::[0-9a-f]*)?\}|\{[0-9a-f]{2}\}')
TOK_RAW = re.compile(r'\{[0-9a-f]{2}\}')
NL = re.compile(r'\\n')


def well_formed_msg(t):
    """{c:..} 인수 길이가 문법(msgcode.ARGS)과 맞는지"""
    m = re.fullmatch(r'\{([a-z])(?::([0-9a-f]*))?\}', t)
    if not m:
        return True                                    # {xx}
    k = msgcode.ARGS.get(m.group(1))
    if k is None:
        return False
    return (k == 0 and m.group(2) is None) or (k > 0 and m.group(2) is not None and len(m.group(2)) == 2 * k)


def check(name, jp, ko):
    """오류 문장 목록(빈 목록 = 통과)"""
    tok = TOK_MSG if name == 'msg.tsv' else TOK_RAW
    e = []
    a, b = tok.findall(jp), tok.findall(ko)
    if a != b:
        i = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))
        e.append('토큰 순서열 다름 — %d번째: 원문 %s / 번역 %s' % (i + 1, a[i] if i < len(a) else '(없음)', b[i] if i < len(b) else '(없음)'))
    if name == 'msg.tsv':
        bad = [t for t in b if not well_formed_msg(t)]
        if bad:
            e.append('제어 인수 길이 틀림 %s' % ' '.join(bad))
    if name != 'msg.tsv':                              # 렌더러(0x80015664)는 반각 공백·숫자·-·:·대문자 말고는 «0» 모양으로 그린다
        jpa = set(NL.sub('', tok.sub('', jp)))
        odd = sorted({ch for ch in NL.sub('', tok.sub('', ko)) if ord(ch) < 0x80 and ch not in jpa
                      and not (ch == ' ' or ch.isdigit() or ch in '-:' or 'A' <= ch <= 'Z')})
        if odd:
            e.append('반각 기호 %s — 전각으로(（）？！ 등)' % ''.join(odd))
    rest = NL.sub('', tok.sub('', ko))
    junk = [ch for ch in rest if ch in '{}\\']
    if junk:
        e.append('토큰 꼴이 아닌 %s 남음' % ''.join(sorted(set(junk))))
    return e


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    d = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'work', 'text')
    tot = n = 0
    for name in ('msg.tsv', 'exe.tsv', 'kana.tsv', 'job.tsv', 'bevent.tsv', 'scenario.tsv'):
        p = os.path.join(d, name)
        if not os.path.exists(p):
            continue
        for ln in open(p, encoding='utf-8'):
            c = ln.rstrip('\n').split('\t')
            if ln.startswith('#') or len(c) < 4 or not c[3] or c[3] == '=':   # '=' = 원문 유지
                continue
            n += 1
            for msg in check(name, c[2], c[3]):
                tot += 1
                if tot <= 200:
                    print('⛔ %s %s  %s\n    JP %s\n    KO %s' % (name, c[0], msg, c[2], c[3]))
    print('번역 %d행 검사 · 토큰 오류 %d' % (n, tot))
    sys.exit(1 if tot else 0)


if __name__ == '__main__':
    main()
