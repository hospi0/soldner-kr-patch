# -*- coding: utf-8 -*-
r"""번역 원문 추출 → work/text/*.tsv  (열: 번호 · 위치/예산 · JP · KO(빈칸))
  표기: SJIS 글자는 그대로, 줄바꿈 제어 'n' → \n, 그 밖의 1바이트(제어 글자·인수·00 포함)는 {xx}.
  msg.tsv      MESSAGE.DAT — 번호 = 블록:문장 (블록 표 → u16 문장 수 + 오프셋, 문장 길이 자유)
  exe.tsv      SLPS_013.19 — 앞이 NUL 인 SJIS 문자열(전각 2자 이상), 예산 = 원문 바이트 수(제자리)
  kana.tsv     SLPS_013.19 — 반각 가타카나 문자열(마법 이름 등, 그릴 때 전각으로 바뀜), 예산 = 원문 바이트 수
  job.tsv · bevent.tsv · scenario.tsv — 같은 방식(앞이 NUL 인 SJIS 문자열), 형식 해독 전이라 «제자리 예산»으로
  python tools/extract.py
"""
import os, re, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import kr12

W = os.path.join(ROOT, 'work')
OUT = os.path.join(W, 'text')
SJ = rb'[\x81-\x9f\xe0-\xef][\x40-\x7e\x80-\xfc]'


def esc(b, newline_n=True, halfkana=True):
    out, i = [], 0
    while i < len(b):
        x = b[i]
        ch = b[i:i + 2].decode('cp932', 'replace') if (0x81 <= x <= 0x9f or 0xe0 <= x <= 0xef) and i + 1 < len(b) else ''
        if len(ch) == 1 and ch != '�' and ch.encode('cp932', 'replace') == b[i:i + 2]:   # 왕복이 같을 때만(87 92 → ∫ → 81 E7 같은 중복 코드 제외)
            # ★실제로 풀리는 글자일 때만 짝짓는다 — 제어 글자 인수(j 00 e2 · v 86 82 …)가 SJIS 앞 바이트 범위라
            #   무조건 짝지으면 «�»가 되어 원문을 잃는다(551줄, 2026-09-26)
            out.append(ch); i += 2
        elif newline_n and x == 0x6e:
            out.append('\\n'); i += 1
        elif halfkana and 0xa1 <= x <= 0xdf:
            out.append(bytes([x]).decode('cp932')); i += 1
        else:
            out.append('{%02x}' % x); i += 1
    return ''.join(out)


def write(name, rows, head):
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, name)
    ko = {}
    if os.path.exists(p):                                   # 다시 뽑아도 (번호, JP) 가 같으면 번역 유지
        for ln in open(p, encoding='utf-8'):
            c = ln.rstrip('\n').split('\t')
            if len(c) >= 4 and not c[0].startswith('#'):
                ko[(c[0], c[2])] = c[3]
    with open(p, 'w', encoding='utf-8') as f:
        f.write(head + '\n')
        for r in rows:
            f.write('\t'.join(map(str, r)) + '\t' + ko.get((r[0], r[2]), '') + '\n')
    return len(rows)


def scan_strings(d, halfkana=False):
    """앞이 NUL 인 문자열: 전각 SJIS 2자 이상(또는 반각 가타카나 2자 이상) 섞인 NUL 끝 구간"""
    rows = []
    unit = rb'(?:' + SJ + rb'|[\x20-\x7e\x1b\x0a]|[\xa1-\xdf])'
    for m in re.finditer(rb'(?<=\x00)' + unit + rb'+(?=\x00)', d):
        s = m.group()
        n_sj = len(re.findall(SJ, s))
        n_hk = len(re.findall(rb'[\xa1-\xdf]', re.sub(SJ, b'', s)))
        if halfkana:
            if n_hk >= 2 and n_sj == 0:
                rows.append((m.start(), s))
        elif n_sj >= 2:
            try:
                s.decode('cp932')
            except UnicodeDecodeError:
                continue
            rows.append((m.start(), s))
    return rows


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    msg = open(os.path.join(W, 'MESSAGE.DAT'), 'rb').read()
    rows = []
    for bi, (o, s) in enumerate(kr12.blocks(msg)):
        for mi, m in enumerate(kr12.block_msgs(msg[o:o + s])):
            if re.search(SJ, m):
                rows.append(('%d:%d' % (bi, mi), len(m), esc(m, halfkana=False)))   # 대사 속 0xA1‥DF 는 제어 글자 인수
    n = write('msg.tsv', rows, '#블록:문장\t바이트\tJP\tKO')
    print('msg.tsv', n)
    exe = open(os.path.join(W, 'SLPS_013.19'), 'rb').read()
    rows = [('E%06x' % o, len(s), esc(s, False)) for o, s in scan_strings(exe)]
    print('exe.tsv', write('exe.tsv', rows, '#위치(EXE 파일)\t예산\tJP\tKO'))
    # 반각 가타카나: «반각만 3자 이상 + NUL 끝», EXE 데이터 표 영역(0xB0000~)만 — 그 앞은 코드 바이트 우연 일치
    rows = [('K%06x' % m.start(), len(m.group()), m.group().decode('cp932'))
            for m in re.finditer(rb'[\xa6-\xdf]{3,}(?=\x00)', exe) if m.start() >= 0xB0000]
    print('kana.tsv', write('kana.tsv', rows, '#위치(EXE 파일)\t예산(반각 1B/자)\tJP\tKO'))
    for fn, name in (('JOBDATA.DAT', 'job.tsv'), ('BEVENT.DAT', 'bevent.tsv'), ('SCENARIO.DAT', 'scenario.tsv')):
        d = open(os.path.join(W, fn), 'rb').read()
        rows = [('%s%06x' % (fn[0], o), len(s), esc(s, fn == 'JOBDATA.DAT')) for o, s in scan_strings(b'\x00' + d)]
        rows = [('%s%06x' % (fn[0], int(r[0][1:], 16) - 1), r[1], r[2]) for r in rows]
        print(name, write(name, rows, '#위치(%s)\t예산\tJP\tKO' % fn))


if __name__ == '__main__':
    main()
