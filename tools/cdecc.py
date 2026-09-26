# -*- coding: utf-8 -*-
"""MODE2/2352 Form 1 섹터의 EDC/ECC 재계산.

⚠️섹터 내용만 바꾸고 EDC/ECC 를 안 맞추면 «내용과 무관하게» 크래시한다
   → [[feedback_gdm_build_and_font]]. 반드시 무수정 섹터로 규약을 먼저 검산할 것.

섹터 2352B = 동기12 + 헤더4 + 서브헤더8 + 데이터2048 + EDC4 + 예비8 + ECC276
ECC 는 헤더 4바이트를 «0으로 두고» 계산한다(Mode 2 규약).
"""
import struct

_EDC = []
for _i in range(256):
    _e = _i
    for _ in range(8):
        _e = (_e >> 1) ^ (0xD8018001 if _e & 1 else 0)
    _EDC.append(_e)

_F = [0] * 256
_B = [0] * 256
for _i in range(256):
    _F[_i] = ((_i << 1) ^ (0x11D if _i & 0x80 else 0)) & 0xFF
    _B[_i ^ _F[_i]] = _i


def edc(data):
    e = 0
    for b in data:
        e = (e >> 8) ^ _EDC[(e ^ b) & 0xFF]
    return e & 0xFFFFFFFF


def _ecc_block(sec, major_count, minor_count, major_mult, minor_inc, doff):
    """src 는 언제나 섹터 오프셋 12부터. Q 는 «방금 쓴 P 패리티»까지 읽으므로
    별도 사본이 아니라 섹터 자체를 봐야 한다(P를 먼저 쓸 것)."""
    size = major_count * minor_count
    for major in range(major_count):
        index = (major >> 1) * major_mult + (major & 1)
        a = b = 0
        for _ in range(minor_count):
            t = sec[12 + index]
            index += minor_inc
            if index >= size:
                index -= size
            a ^= t
            b ^= t
            a = _F[a]
        a = _B[_F[a] ^ b]
        sec[doff + major] = a
        sec[doff + major + major_count] = (a ^ b) & 0xFF


def fix_sector(sec):
    """2352B 섹터(bytearray)를 제자리에서 EDC/ECC 재계산. Mode 2 Form 1 전용."""
    assert len(sec) == 2352
    # Mode 2 Form 1 의 EDC 는 0x818(2072)에 있고 «서브헤더부터» 2056B 를 덮는다.
    # (0x810/2064 는 Mode 1 자리다 — 헷갈리면 전 섹터가 어긋난다)
    sec[2072:2076] = struct.pack('<I', edc(sec[16:2072]))
    hdr = bytes(sec[12:16])
    sec[12:16] = b'\0\0\0\0'                 # ECC 계산 동안 헤더는 0
    _ecc_block(sec, 86, 24, 2, 86, 2076)     # P
    _ecc_block(sec, 52, 43, 86, 88, 2248)    # Q  (P 패리티를 읽으므로 순서 고정)
    sec[12:16] = hdr
    return sec

# ─────────────────────────────────────────────────────────────────────────
# Mode 2 Form 2 (오디오·`.STR` 안에 섞여 있다) + 섹터 헤더
# ★★`.STR`/`.XA` 는 **비디오 Form 1(2048B) + 오디오 Form 2(2324B)** 가 섞여 있다.
#   Form 2 는 **ECC 가 없고** EDC 4B 가 섹터 «맨 끝»(2348)에 있으며 16..2347 을 덮는다.
#   Form 1 처리기를 그대로 돌리면 오디오 섹터를 통째로 망가뜨린다.
# ★섹터 헤더(12..15) = 분·초·프레임을 **BCD** 로, 그리고 모드 2.
#   LBA n 의 MSF 는 n+150 을 75프레임/초로 나눈 값이다. 파일을 다른 자리에 넣으면
#   **반드시 다시 써야 한다** — psxavenc 산출물은 LBA 0 기준으로 찍혀 나온다.


def _bcd(v):
    return ((v // 10) << 4) | (v % 10)


def set_header(sec, lba):
    """섹터 헤더를 그 섹터의 «절대 위치»에 맞춰 다시 쓴다 (Mode 2)."""
    n = lba + 150
    sec[12] = _bcd(n // (75 * 60))
    sec[13] = _bcd(n // 75 % 60)
    sec[14] = _bcd(n % 75)
    sec[15] = 2
    return sec


def is_form2(sec):
    return bool(sec[18] & 0x20)


def fix_sector2(sec):
    """2352B Form 2 섹터의 EDC 재계산. ECC 는 없다."""
    assert len(sec) == 2352
    sec[2348:2352] = struct.pack('<I', edc(sec[16:2348]))
    return sec


def fix_any(sec, lba=None):
    """Form 1/2 를 알아서 가려 고친다. `lba` 를 주면 헤더도 다시 쓴다."""
    if lba is not None:
        set_header(sec, lba)
    return fix_sector2(sec) if is_form2(sec) else fix_sector(sec)
