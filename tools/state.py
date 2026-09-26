# -*- coding: utf-8 -*-
r"""DuckStation 세이브스테이트(.sav, DUCC v0x57) → 데이터 블롭(zstd 풀림). RAM·VRAM 위치는 내용으로 찾는다.
  from state import load; blob = load(path)
  python tools/state.py <.sav>   → work/state/<이름>.raw
"""
import os, struct, sys
import zstandard

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(p):
    d = open(p, 'rb').read()
    assert d[:4] == b'DUCC', d[:4]
    v = struct.unpack_from('<12I', d, 168)
    comp, csize, usize, off = v[8], v[9], v[10], v[11]
    assert comp == 2, comp
    return zstandard.ZstdDecompressor().decompress(d[off:off + csize], max_output_size=usize)


def ram(blob, exe):
    """EXE 코드 조각으로 RAM(2 MB) 시작을 찾는다 (적재 0x80010000, EXE 머리 0x800)"""
    k = blob.find(exe[0x900:0x940])
    assert k >= 0
    base = k - 0x100 - 0x10000
    return blob[base:base + 0x200000]


if __name__ == '__main__':
    os.makedirs(os.path.join(ROOT, 'work', 'state'), exist_ok=True)
    exe = open(os.path.join(ROOT, 'work', 'SLPS_013.19'), 'rb').read()
    for p in sys.argv[1:]:
        b = load(p)
        n = os.path.splitext(os.path.basename(p))[0]
        open(os.path.join(ROOT, 'work', 'state', n + '.ram'), 'wb').write(ram(b, exe))
        print(n, len(b))
