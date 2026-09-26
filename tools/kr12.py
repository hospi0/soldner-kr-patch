# -*- coding: utf-8 -*-
r"""12×12 글꼴(FONT12.BIN) 한글 + MESSAGE.DAT 되쓰기 공통
  FONT12.BIN = [u16 LE SJIS 코드 × 3,200 (오름차순)][12×12 1bpp 18 B × 3,200], 글리프 = 코드 순번.
  한글 음절 → «대사에 적게 쓰인 한자»의 코드를 빌려 그 칸을 한글로 덮는다(배정은 work/kr/charmap.tsv 이어받음).
  글리프: 갈무리11(잉크 y 3‥13, x 0‥10) → 칸 y 1‥11 (원본 가나·한자와 같은 자리).
  MESSAGE.DAT = (u32 BE 오프셋, 크기)×151 블록, 블록 = u16 BE 문장 수 N + u16 BE 오프셋 × N (블록 기준).
    제어 글자는 반각(z f l s n g c j …) + 인수 바이트(00 포함) → 문장 경계는 오프셋 표로만.
"""
import collections, os, re, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import bdf

GALMURI11 = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri11.bdf'
CHARMAP = os.path.join(ROOT, 'work', 'kr', 'charmap.tsv')
N = 3200


def codes(fnt):
    return list(struct.unpack_from('<%dH' % N, fnt, 0))


def kanji_freq(msg):
    """MESSAGE.DAT 전체의 SJIS 글자 빈도"""
    c = collections.Counter()
    for m in re.finditer(rb'[\x81-\x9f\xe0-\xef][\x40-\xfc]', msg):
        c[struct.unpack('>H', m.group())[0]] += 1
    return c


def assign(sylls, fnt, freq, keep=()):
    """음절 → 빌릴 코드. keep = 빌리면 안 되는 코드(이번 번역·원문이 쓰는 글자)"""
    prev = {}
    if os.path.exists(CHARMAP):
        for ln in open(CHARMAP, encoding='utf-8'):
            r = ln.rstrip('\n').split('\t')
            if len(r) >= 2:
                prev[r[0]] = int(r[1], 16)
    cs = codes(fnt)
    cand = sorted((c for c in cs if c >= 0x889F and c not in keep), key=lambda c: (freq[c], c))
    m = {s: prev[s] for s in sylls if s in prev and prev[s] in cand}
    used = set(m.values())
    free = iter(c for c in cand if c not in used)
    for s in sylls:
        if s not in m:
            m[s] = next(free)
    os.makedirs(os.path.dirname(CHARMAP), exist_ok=True)
    with open(CHARMAP, 'w', encoding='utf-8') as f:
        for s, c in m.items():
            f.write('%s\t%04x\t%s\n' % (s, c, struct.pack('>H', c).decode('cp932', 'replace')))
    return m


def glyph12(F, ch):
    pts, _ = F.draw(ch)
    rows = [0] * 12
    for x, y in pts:
        yy = y - 2
        assert 0 <= yy < 12 and 0 <= x < 12, (ch, x, y)
        rows[yy] |= 1 << (11 - x)
    bits = ''.join(format(r, '012b') for r in rows)
    return int(bits, 2).to_bytes(18, 'big')


def put_font(fnt, m):
    cs = codes(fnt)
    F = bdf.Font(GALMURI11)
    for s, c in m.items():
        k = cs.index(c)
        fnt[2 * N + 18 * k:2 * N + 18 * k + 18] = glyph12(F, s)


def encode(ko, m):
    """번역 표기 → 바이트: \\n → n, {xx} → 바이트 그대로, 한글 → 빌린 코드, 그 밖 cp932"""
    out = bytearray()
    i = 0
    while i < len(ko):
        if ko.startswith('\\n', i):
            out += b'n'; i += 2; continue
        mm = re.match(r'\{([0-9a-f]{2})\}', ko[i:])
        if mm:
            out.append(int(mm.group(1), 16)); i += 4; continue
        ch = ko[i]
        if ch in m:
            out += struct.pack('>H', m[ch])
        else:
            out += ch.encode('cp932')
        i += 1
    return bytes(out)


def blocks(msg):
    return [struct.unpack_from('>II', msg, k) for k in range(0, 151 * 8, 8)]


def block_msgs(b):
    n = struct.unpack_from('>H', b, 0)[0]
    offs = [struct.unpack_from('>H', b, 2 + 2 * i)[0] for i in range(n)]
    end = len(b.rstrip(b'\x00'))
    return [b[offs[i]:(offs[i + 1] if i + 1 < n else end)] for i in range(n)]


def build_block(msgs, size):
    n = len(msgs)
    body = bytearray()
    offs = []
    pos = 2 + 2 * n
    for m in msgs:
        offs.append(pos); body += m; pos += len(m)
    b = struct.pack('>H', n) + b''.join(struct.pack('>H', o) for o in offs) + body
    assert len(b) <= size, ('블록 넘침', len(b), size)
    return b + bytes(size - len(b))
