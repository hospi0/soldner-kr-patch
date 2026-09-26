# -*- coding: utf-8 -*-
"""MODE2/2352 섹터의 EDC/ECC 검증·재계산.

  python tools/cdsector.py <bin> --check 100      # 섹터 100개 검사
  python tools/cdsector.py <bin> --check-all

## 섹터 배치 (Mode 2 Form 1)
```
 0..11   SYNC   00 FF×10 00
12..15   헤더   분 초 프레임 모드(=2)
16..23   서브헤더 8 B (파일·채널·서브모드·코딩 을 «두 번» 적는다)
24..2071 사용자 데이터 2048 B
2072..2075  EDC (u32 LE)
2076..2087  P 패리티 0  (Form 1 은 여기 0 을 채운 뒤 ECC 를 만든다)
2088..2363  ECC (P 172 B + Q 104 B)
```
⛔ Form 2(서브모드 비트 0x20)는 데이터 2324 B 에 EDC 만 있고 ECC 가 없다 — 따로 다뤄야 한다.

## EDC
CRC-32, 다항식 **0x8001801B**(반사), 초기값 0, 최종 XOR 없음.
Form 1 은 바이트 **16..2071**(서브헤더+데이터)에 대해 계산한다.
"""
import argparse
import struct

EDC_POLY = 0xD8018001          # 0x8001801B 를 반사한 값


def _edc_table():
    t = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = (c >> 1) ^ (EDC_POLY if c & 1 else 0)
        t.append(c)
    return t


EDC_TAB = _edc_table()


def edc(buf):
    c = 0
    for b in buf:
        c = (c >> 8) ^ EDC_TAB[(c ^ b) & 0xFF]
    return c & 0xFFFFFFFF


# ── ECC (ECMA-130 부록 A) — GF(2^8), 원시다항식 0x11D
def _luts():
    f = [0] * 256
    b = [0] * 256
    for i in range(256):
        j = ((i << 1) ^ (0x11D if i & 0x80 else 0)) & 0xFF
        f[i] = j
        b[i ^ j] = i
    return f, b


ECC_F, ECC_B = _luts()


def _writepq(sec, major_count, minor_count, major_mult, minor_inc, base):
    """ECMA-130 의 P/Q 패리티.
       ⛔ Q 는 «P 패리티까지 포함한» 범위를 읽는다 — 그래서 섹터를 통째로 넘겨야 하고
          P 를 먼저 채운 뒤 Q 를 계산해야 한다. (처음에 data 를 2060 B 로 잘라 넘겨 터졌다)
       ⛔ 주소 4바이트는 Form 1 에서 «0 으로 보고» 계산한다."""
    size = major_count * minor_count
    for major in range(major_count):
        index = (major >> 1) * major_mult + (major & 1)
        a = bb = 0
        for _ in range(minor_count):
            t = 0 if index < 4 else sec[16 + index - 4]
            index += minor_inc
            if index >= size:
                index -= size
            a ^= t
            bb ^= t
            a = ECC_F[a]
        a = ECC_B[ECC_F[a] ^ bb]
        sec[base + major] = a
        sec[base + major + major_count] = a ^ bb


def ecc_make(sector):
    """2352 B bytearray 의 P(2076~)·Q(2248~) 를 다시 만든다. Mode 2 Form 1 전용."""
    _writepq(sector, 86, 24, 2, 86, 2076)     # P 먼저
    _writepq(sector, 52, 43, 86, 88, 2248)    # Q 는 P 를 포함해 읽는다


def fix_sector(sector):
    """사용자 데이터를 고친 뒤 EDC·ECC 를 다시 채운다."""
    e = edc(bytes(sector[16:2072]))
    struct.pack_into('<I', sector, 2072, e)
    ecc_make(sector)
    return sector


def check(path, n=None):
    f = open(path, 'rb')
    import os
    total = os.path.getsize(path) // 2352
    n = total if n is None else min(n, total)
    ok = form2 = bad = 0
    modes = {}
    for i in range(n):
        f.seek(i * 2352)
        s = f.read(2352)
        if s[:12] != b'\x00' + b'\xff' * 10 + b'\x00':
            bad += 1
            continue
        mode = s[15]
        modes[mode] = modes.get(mode, 0) + 1
        sub = s[16:24]
        if mode != 2:
            continue
        if sub[2] & 0x20:                      # Form 2
            form2 += 1
            continue
        want = struct.unpack_from('<I', s, 2072)[0]
        got = edc(s[16:2072])
        if want == got:
            ok += 1
        else:
            bad += 1
            if bad < 4:
                print('  ⛔ 섹터 %d EDC 불일치 저장 %08X 계산 %08X' % (i, want, got))
    print('%s  섹터 %d 중 %d개 검사' % (path, total, n))
    print('  모드 분포 %s · Form1 EDC 일치 %d · Form2 %d · 불일치/이상 %d' % (modes, ok, form2, bad))
    return bad == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('bin')
    ap.add_argument('--check', type=int)
    ap.add_argument('--check-all', action='store_true')
    a = ap.parse_args()
    check(a.bin, None if a.check_all else (a.check or 200))


if __name__ == '__main__':
    main()
