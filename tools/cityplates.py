# -*- coding: utf-8 -*-
r"""도시 이름 판 20개(GRP.BIN 723,160 / 734,680 — 72×16 판 10개씩, 8bpp, 색표 미확보) 한글화
  바탕 = 빈 판(work/kr/cityplate_blank.npy — 20판 겹쳐 글자 걸러낸 최빈값, 사용자 «완벽해»).
  글자 = 원본처럼 짙은 획(색인 28) + 획 오른쪽 아래 밝은 점(색인 155), 갈무리9, 1‥9행, 위로 갈수록 오른쪽으로(기울임).
  가로 가운데(4‥67열 안). 지명은 도시 제목(tools/towntitles.py NAMES)과 같다.
  python tools/cityplates.py → my files/그래픽/도시목록_한글.png
"""
import os, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import bdf, towntitles

GALMURI9 = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri9.bdf'
SHEETS = (722944, 734464)      # ★판 실제 시작(예전 723,160/734,680 은 3줄 늦어 둘째 판 끝 3줄이 뒤에 붙은 숫자 그림 0·1을 덮었다 — 연월 숫자 깨짐, 2026-09-26)
PW, PH, N = 72, 16, 10
DARK, LIGHT = 28, 155
ROW0 = 4                      # 글자 윗줄(실제 판 기준 — 예전 좌표 1)


def plate(blank, F, name):
    p = blank.copy()
    pts, _ = F.draw(name)
    xs = [x for x, _ in pts]; ys = [y for _, y in pts]
    h = max(ys) - min(ys) + 1
    ink = set()
    for x, y in pts:
        yy = y - min(ys)
        xx = x - min(xs) + (h - 1 - yy) // 3                       # 위로 갈수록 오른쪽(원본 기울임)
        ink.add((yy + ROW0, xx))                                   # 가늘게(사용자 선택 2026-09-26 — 굵게 하면 획 많은 음절이 뭉침)
    w = max(x for _, x in ink) + 1
    ox = 4 + (64 - w) // 2
    for y, x in ink:
        hy, hx = y + 1, x + 1                                      # 밝은 점: 획의 오른쪽 아래
        if (hy, hx) not in ink and hy - ROW0 < PH - 6:              # 예전 좌표(ROW0 1)의 hy < 11 과 같은 한계
            p[hy, hx + ox] = LIGHT
    for y, x in ink:
        p[y, x + ox] = DARK
    return p


def build(grp):
    blank = np.roll(np.load(os.path.join(ROOT, 'work', 'kr', 'cityplate_blank.npy')), 3, axis=0)   # 저장본은 3줄 늦은 좌표 → 실제 판 좌표
    F = bdf.Font(GALMURI9)
    for s, off in enumerate(SHEETS):
        sheet = np.frombuffer(bytes(grp[off:off + PW * PH * N]), np.uint8).reshape(N, PH, PW).copy()
        for k in range(N):
            sheet[k] = plate(blank, F, towntitles.NAMES[s * N + k])
        grp[off:off + PW * PH * N] = sheet.tobytes()


if __name__ == '__main__':
    g = bytearray(open(os.path.join(ROOT, 'work', 'GRP.BIN'), 'rb').read())
    old = [np.frombuffer(bytes(g[o:o + PW * PH * N]), np.uint8).reshape(N * PH, PW) for o in SHEETS]
    build(g)
    new = [np.frombuffer(bytes(g[o:o + PW * PH * N]), np.uint8).reshape(N * PH, PW) for o in SHEETS]
    gap = np.zeros((N * PH, 4), np.uint8)
    sheet = np.concatenate([old[0], gap, new[0], gap + 255, old[1], gap, new[1]], 1)
    dst = os.path.join(ROOT, 'my files', '그래픽', '도시목록_한글.png')
    Image.fromarray(sheet).resize((sheet.shape[1] * 4, sheet.shape[0] * 4), Image.NEAREST).save(dst)
    print(dst)
