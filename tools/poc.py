# -*- coding: utf-8 -*-
r"""PoC 1 — 여관 대사(MESSAGE.DAT 블록 5 문장 0) 한 줄 한글 + 12×12 글꼴
  python tools/poc.py [--write [--install]]
  디스크: 원본 .bin 사본에 FONT12.BIN·MESSAGE.DAT 를 제자리(크기 그대로)로, 바뀐 섹터만 EDC/ECC 재계산 → work/out/
"""
import hashlib, os, shutil, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import kr12, discfs, plates, towntitles, datebox, cityplates
import numpy as np
from cdsector import fix_sector

SRC = r'C:\claude\roms\ps\Soldnerschild Special (Japan)\Soldnerschild Special (Japan).bin'
CUE = SRC[:-4] + '.cue'
OUT = os.path.join(ROOT, 'work', 'out', os.path.basename(SRC))
INSTALL = r'F:\hospi\roms\ps roms\Soldnerschild Special (Japan)'

# (블록, 문장, 원문 확인용 조각, 번역 — 제어 글자는 {xx}, 줄바꿈 \n, 띄어쓰기는 전각 공백)
TR = [(5, 0, '３人ともよく戦ってくれたな', 'zfl{00}#s{00}#３명　모두　잘　싸워　주었군\\n푹　쉬도록　해라g{00}')]

# SCENARIO.DAT 인물 표: 머리 4 B + 이름 칸 17 B(NUL 채움) — 새 게임 때 RAM(0x800C7827 부근)으로 복사된다
NAMES = [('シュタインドルフ', '슈타인돌프')]          # 사용자 지정 2026-09-26
NAME_FIELD = 17


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    fs = {p: (l, s) for p, l, s in discfs.read_fs(SRC)[4]}
    with open(SRC, 'rb') as f:
        def get(p):
            l, s = fs[p]
            return bytearray(discfs.sector(f, l, (s + 2047) // 2048)[:s])
        msg, fnt, scn, exe, grp = get('/MESSAGE.DAT'), get('/FONT12.BIN'), get('/SCENARIO.DAT'), get('/SLPS_013.19'), get('/GRP.BIN')
    orig = {'/MESSAGE.DAT': bytes(msg), '/FONT12.BIN': bytes(fnt), '/SCENARIO.DAT': bytes(scn), '/SLPS_013.19': bytes(exe), '/GRP.BIN': bytes(grp)}
    sylls = sorted({c for *_, ko in TR for c in ko if '가' <= c <= '힣'} | {c for _, ko in NAMES for c in ko if '가' <= c <= '힣'})
    keep = set()
    for bi, mi, jp, ko in TR:
        keep |= {struct.unpack('>H', ch.encode('cp932'))[0] for ch in jp if ord(ch) > 0x7f}
    m = kr12.assign(sylls, fnt, kr12.kanji_freq(bytes(msg)), keep)
    kr12.put_font(fnt, m)
    bl = kr12.blocks(bytes(msg))
    for bi, mi, jp, ko in TR:
        o, s = bl[bi]
        ms = kr12.block_msgs(bytes(msg[o:o + s]))
        assert jp.encode('cp932') in ms[mi], (bi, mi)
        ms[mi] = kr12.encode(ko, m)
        msg[o:o + s] = kr12.build_block(ms, s)
        assert kr12.block_msgs(bytes(msg[o:o + s]))[mi] == ms[mi]
    # ★인물 표는 SCENARIO.DAT 와 EXE(0xB8027 = RAM 0x800C7827) 두 벌 — 이름표는 EXE 쪽을 쓴다(실기 2026-09-26: SCENARIO 만 고치면 그대로)
    for buf in (scn, exe):
        for jp, ko in NAMES:
            j = jp.encode('cp932')
            i = buf.find(j + bytes(1))
            assert i >= 0 and buf.count(j + bytes(1)) == 1, jp
            k = kr12.encode(ko, m)
            assert len(k) < NAME_FIELD
            assert all(x == 0 for x in buf[i + len(j):i + NAME_FIELD]), '이름 칸 뒤가 0 이 아님'
            buf[i:i + NAME_FIELD] = k + bytes(NAME_FIELD - len(k))
    # 그림: 건물 표지 12칸(tools/plates.py) · 도시 배경 제목(tools/townbg.py)
    plates.build(grp, np.load(os.path.join(ROOT, 'work', 'kr', 'plate_bld_clut.npy')))
    towntitles.build(grp)                                 # 도시 화면 배경 20장 제목(사용자 «완벽해 기대 이상»)
    cityplates.build(grp)                                 # 도시 이름 판 20개(빈 판 + 갈무리9 가늘게)
    # 지도 배경 연월 상자 年/月 → 년/월 (tools/datebox.py)
    mb = np.frombuffer(bytes(grp[datebox.OFF:datebox.OFF + datebox.W * datebox.H]), np.uint8).reshape(datebox.H, datebox.W)
    grp[datebox.OFF:datebox.OFF + datebox.W * datebox.H] = datebox.rebuild(mb, np.load(os.path.join(ROOT, 'work', 'kr', 'map_clut.npy'))).tobytes()
    print('음절 %d · 대사 %d줄' % (len(m), len(TR)), ' '.join('%s→%04x' % kv for kv in m.items()))
    if '--write' not in sys.argv:
        print('예행 끝 — 쓰려면 --write'); return
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    shutil.copyfile(SRC, OUT)
    n = 0
    with open(OUT, 'r+b') as fh:
        for p, data in (('/MESSAGE.DAT', msg), ('/FONT12.BIN', fnt), ('/SCENARIO.DAT', scn), ('/SLPS_013.19', exe), ('/GRP.BIN', grp)):
            l, _ = fs[p]
            for k in range(0, len(data), 2048):
                if data[k:k + 2048] != orig[p][k:k + 2048]:
                    pos = (l + k // 2048) * discfs.RAW
                    fh.seek(pos); sec = bytearray(fh.read(discfs.RAW))
                    chunk = data[k:k + 2048]
                    sec[24:24 + len(chunk)] = chunk
                    fh.seek(pos); fh.write(fix_sector(sec)); n += 1
    h = hashlib.md5(open(OUT, 'rb').read()).hexdigest().upper()
    print('섹터 %d개 · %s md5 %s' % (n, OUT, h))
    if '--install' in sys.argv:
        os.makedirs(INSTALL, exist_ok=True)
        shutil.copyfile(OUT, os.path.join(INSTALL, os.path.basename(OUT)))
        shutil.copyfile(CUE, os.path.join(INSTALL, os.path.basename(CUE)))
        print('설치', INSTALL)


if __name__ == '__main__':
    main()
