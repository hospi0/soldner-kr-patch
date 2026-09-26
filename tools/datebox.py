# -*- coding: utf-8 -*-
r"""지도 배경(GRP.BIN 646,914, 8bpp 320×240) 왼쪽 위 연월 상자의 구운 「年」「月」 → 「년」「월」
  숫자(951, 1)는 실행 중 스프라이트로 덧그리므로 그대로. 상자 안쪽의 밝은 회색 화소 = 글자.
  색표는 세이브스테이트 4 화면 버퍼와 대조(work/kr/map_clut.npy, 상자 부근은 겹침이 없어 믿을 만함).
  글자 → 둘레 1px 까지 상자 안쪽 색으로 번져 메우고, 갈무리9 로 원본 글자 최빈 색인 한 색으로 찍는다.
  python tools/datebox.py → my files/그래픽/연월상자_비교.png
"""
import os, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import bdf

GALMURI = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri9.bdf'
OFF, W, H = 646914, 320, 240
# (글자 상자 x0, y0, x1, y1, 한글) — 지도 배경 좌표
GLYPHS = [((44, 15, 60, 28), '년'), ((67, 15, 84, 28), '월')]     # 상자 윗줄 12‥14행·아랫줄 28행·오른쪽 윤곽 84열~ 은 건드리지 않음
TOP = 17                                                         # 한글 윗줄 행(사용자 확정 17 — 18 판을 보고 «한도트 더». 16 은 두 번 올린 실수)


def lum(clut):
    c = clut.astype(int)
    r, g, b = c & 31, (c >> 5) & 31, (c >> 10) & 31
    return (r * 3 + g * 6 + b) / 10, np.maximum(np.maximum(r, g), b) - np.minimum(np.minimum(r, g), b)


def rebuild(bg, clut):
    L, sat = lum(clut)
    F = bdf.Font(GALMURI)
    new = bg.copy()
    for (x0, y0, x1, y1), ko in GLYPHS:
        sub = new[y0:y1, x0:x1]
        ink = (L[sub] >= 15) & (sat[sub] <= 6)                   # 밝은 회색 = 글자
        c_ink = int(np.bincount(sub[ink]).argmax())
        ys, xs = np.nonzero(ink)
        # 지우기 = 회색 화소(휘도 ≥ 10 — 배경 안쪽은 8 이하) 둘레 1px. 15 로 잡았더니 휘도 12‥14 획 끝이
        #   「년」 옆 가로 찌꺼기로 남았다(사용자 2026-09-26). 사각형째 지우면 아래가 검게 번진다.
        gray = (L[sub] >= 10) & (sat[sub] <= 6)
        kill = gray.copy()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                kill |= np.roll(np.roll(gray, dy, 0), dx, 1)
        cy, cx = (ys.min() + ys.max()) / 2, (xs.min() + xs.max()) / 2
        out = sub.copy()
        known = ~kill
        while not known.all():
            grown = known.copy()
            for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                src = np.roll(np.roll(out, dy, 0), dx, 1)
                kn = np.roll(np.roll(known, dy, 0), dx, 1)
                fill = ~known & kn & ~grown
                out[fill] = src[fill]
                grown |= fill
            known = grown
        pts, _ = F.draw(ko)
        px = [x for x, _ in pts]; py = [y for _, y in pts]
        ox = int(round(cx - (min(px) + max(px)) / 2)); oy = TOP - y0 - min(py)
        assert 0 <= min(py) + oy and max(py) + oy < y1 - y0, ('상자 안쪽을 넘음', ko)
        for x, y in pts:
            out[y + oy, x + ox] = c_ink
        new[y0:y1, x0:x1] = out
    return new


def rgb(img, clut):
    c = clut[img].astype(int)
    return (np.stack([c & 31, (c >> 5) & 31, (c >> 10) & 31], -1) * 8).astype(np.uint8)


if __name__ == '__main__':
    g = open(os.path.join(ROOT, 'work', 'GRP.BIN'), 'rb').read()
    clut = np.load(os.path.join(ROOT, 'work', 'kr', 'map_clut.npy'))
    bg = np.frombuffer(g[OFF:OFF + W * H], np.uint8).reshape(H, W)
    new = rebuild(bg, clut)
    sheet = np.concatenate([rgb(bg[5:38, 10:105], clut), rgb(new[5:38, 10:105], clut)], 0)
    dst = os.path.join(ROOT, 'my files', '그래픽', '연월상자_비교7.png')
    Image.fromarray(sheet).resize((sheet.shape[1] * 6, sheet.shape[0] * 6), Image.NEAREST).save(dst)
    print(dst)
