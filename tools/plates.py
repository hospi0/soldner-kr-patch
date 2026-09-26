# -*- coding: utf-8 -*-
r"""건물 표지(GRP.BIN 2,773,504, 8bpp 72×248 = 20행 × 12칸) 한글화
  색표 = 세이브스테이트 화면의 「宿屋」 표지(화면 x 85, y 63 ↔ 시트 5번 칸)에서 1:1 대조(일치 100%).
  글자 = 밝은(휘도 ≥ 16/31) 화소 → 둘레 1px 까지 «12칸의 같은 자리 최빈값(배경 무늬)»으로 지우고,
  한글은 갈무리11(1px 획, 원본 명조 1px 획과 같은 굵기)로 원본 글자 흰 색인 하나로 가운데 찍는다.
  python tools/plates.py  → my files/그래픽/건물표지_비교.png
"""
import os, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import bdf

GALMURI11 = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri11.bdf'
OFF, W, STEP, N = 2773504, 72, 20, 12
KO = ['상점', '길드', '교회', '대성당', '훈련소', '여관', '주점', '성', '투기장', '광장', '민가', '저택']


def lum(clut):
    c = clut.astype(int)
    return ((c & 31) * 3 + ((c >> 5) & 31) * 6 + ((c >> 10) & 31)) / 10


def build(grp, clut):
    sh = np.frombuffer(bytes(grp[OFF:OFF + W * STEP * N]), np.uint8).reshape(STEP * N, W).copy()
    pl = sh.reshape(N, STEP, W)
    L = lum(clut)
    text = L[pl] >= 16
    inner = np.zeros((STEP, W), bool); inner[3:STEP - 3, 5:W - 5] = True     # 밝은 테두리는 글자가 아니다
    text &= inner
    halo = text.copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            halo |= np.roll(np.roll(text, dy, 1), dx, 2) & inner
    # 배경 무늬 = 글자·둘레가 아닌 칸들의 같은 자리 최빈 색인
    bgm = np.zeros((STEP, W), np.uint8)
    for y in range(STEP):
        for x in range(W):
            vals = pl[:, y, x][~halo[:, y, x]]
            bgm[y, x] = np.bincount(vals if len(vals) else pl[:, y, x]).argmax()
    white = int(np.bincount(pl[text]).argmax())
    F = bdf.Font(GALMURI11)
    # ★바탕 = 사용자가 만든 빈 판때기(2026-09-26, work/kr/plate_blank.npy — 비교 그림의 城 칸 오른쪽을 색인으로 되돌림, 색 오차 0)
    blank = np.load(os.path.join(ROOT, 'work', 'kr', 'plate_blank.npy'))
    out = pl.copy()
    for k, ko in enumerate(KO):
        out[k] = blank
        p = out[k]
        pts, adv = F.draw(ko)
        xs = [x for x, _ in pts]; ys = [y for _, y in pts]
        # 원본 글자 상자의 세로 가운데에 맞춤
        ty = np.nonzero(text[k].any(1))[0]
        cy = (ty.min() + ty.max()) / 2
        ox = (W - (max(xs) - min(xs) + 1)) // 2 - min(xs)
        oy = int(round(cy - (min(ys) + max(ys)) / 2))
        for x, y in pts:
            p[y + oy, x + ox] = white
    grp[OFF:OFF + W * STEP * N] = out.reshape(-1).tobytes()
    return sh, out.reshape(STEP * N, W)


def rgb(img, clut):
    c = clut[img].astype(int)
    return (np.stack([c & 31, (c >> 5) & 31, (c >> 10) & 31], -1) * 8).astype(np.uint8)


if __name__ == '__main__':
    grp = bytearray(open(os.path.join(ROOT, 'work', 'GRP.BIN'), 'rb').read())
    clut = np.load(os.path.join(ROOT, 'work', 'kr', 'plate_bld_clut.npy'))
    old, new = build(grp, clut)
    sheet = np.concatenate([rgb(old, clut), np.zeros((old.shape[0], 6, 3), np.uint8), rgb(new, clut)], 1)
    dst = os.path.join(ROOT, 'my files', '그래픽', '건물표지_비교.png')
    Image.fromarray(sheet).resize((sheet.shape[1] * 4, sheet.shape[0] * 4), Image.NEAREST).save(dst)
    print(dst)
