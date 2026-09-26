# -*- coding: utf-8 -*-
r"""도시 배경(GRP.BIN, 8bpp 320×240, 오른쪽 아래에 도시 이름이 구워져 있음) 제목 한글화
  색표(CLUT)는 세이브스테이트 화면 버퍼와 배경을 1:1 대조해 얻는다(화면 x = 배경 x + 1, 일치 96%).
  글자 화소 = 제목 상자 안에서 «밝고 푸른» 화소 → 둘레 2px 까지 지우고(가까운 배경 화소 색인으로 번져 메움),
  한글은 원본 글자 화소 색인 3층(흰 심·중간·파란 가장자리)으로, 가늘게 오른쪽으로 기울여, 위→아래 흰→파랑.
  python tools/townbg.py  → my files/그래픽/도시제목_비교.png
"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
FONT = r'C:\claude\utils\font\nanum-gothic\NanumGothic.ttf'
W, H = 320, 240

# (GRP.BIN 오프셋, 색표 파일, 제목 상자 x0,y0,x1,y1, 한글)
TOWNS = [(1451778, 'bg_baiden_clut.npy', (228, 196, 305, 222), '바이덴')]


def lum(clut):
    c = clut.astype(int)
    r, g, b = c & 31, (c >> 5) & 31, (c >> 10) & 31
    return r, g, b, (r * 3 + g * 6 + b) / 10


def rebuild(bg, clut, box, text, px=17, shear=0.3):
    x0, y0, x1, y1 = box
    r, g, b, L = lum(clut)
    sub = bg[y0:y1, x0:x1]
    text_m = (L[sub] >= 14) & (b[sub] >= r[sub])          # 글자 = 밝고 푸른 기
    kill = text_m.copy()
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            kill |= np.roll(np.roll(text_m, dy, 0), dx, 1)
    ink = sub[text_m]
    order = ink[np.argsort(L[ink])]
    k = len(order) // 3
    c_blue, c_mid, c_white = (int(np.bincount(order[:k]).argmax()), int(np.bincount(order[k:2 * k]).argmax()),
                              int(np.bincount(order[2 * k:]).argmax()))
    out = sub.copy()
    known = ~kill
    while not known.all():                                  # 지운 자리를 가까운 배경 색인으로 번져 메움
        grown = known.copy()
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            src = np.roll(np.roll(out, dy, 0), dx, 1)
            kn = np.roll(np.roll(known, dy, 0), dx, 1)
            fill = ~known & kn & ~grown
            out[fill] = src[fill]
            grown |= fill
        known = grown
    F = ImageFont.truetype(FONT, px)
    pw, ph = x1 - x0 + 20, y1 - y0 + 10
    lay = Image.new('L', (pw, ph), 0)
    # 음절을 원본 글자 폭(글자 화소 x 범위)에 고르게 펼친다
    xs_ink = np.nonzero(text_m.any(0))[0]
    c0, c1 = xs_ink.min() + 10, xs_ink.max() + 10
    span0, span1 = c0 + (c1 - c0) * 0.03, c1 - (c1 - c0) * 0.03        # 원본 폭의 94% 안에
    n = len(text)
    for i, ch in enumerate(text):
        cx = span0 + (span1 - span0) * (i + 0.5) / n
        ImageDraw.Draw(lay).text((cx, ph / 2), ch, font=F, anchor='mm', fill=255)
    lay = lay.transform(lay.size, Image.AFFINE, (1, shear, -ph * shear / 2, 0, 1, 0), Image.BICUBIC)
    m = np.asarray(lay)[5:5 + (y1 - y0), 10:10 + (x1 - x0)]
    ys, xs = np.nonzero(m > 90)
    top, bot = ys.min(), ys.max()
    for yy, xx in zip(ys, xs):
        t = (yy - top) / max(1, bot - top)
        out[yy, xx] = c_white if t < 0.4 else (c_mid if t < 0.75 else c_blue)
    new = bg.copy()
    new[y0:y1, x0:x1] = out
    return new


def rgb(img, clut):
    c = clut[img].astype(int)
    return (np.stack([c & 31, (c >> 5) & 31, (c >> 10) & 31], -1) * 8).astype(np.uint8)


if __name__ == '__main__':
    g = bytearray(open(os.path.join(ROOT, 'work', 'GRP.BIN'), 'rb').read())
    tiles = []
    for off, cl, box, text in TOWNS:
        clut = np.load(os.path.join(ROOT, 'work', 'kr', cl))
        bg = np.frombuffer(bytes(g[off:off + W * H]), np.uint8).reshape(H, W)
        new = rebuild(bg, clut, box, text)
        x0, y0, x1, y1 = box
        a = rgb(bg[y0 - 6:y1 + 6, x0 - 10:x1 + 10], clut)
        b_ = rgb(new[y0 - 6:y1 + 6, x0 - 10:x1 + 10], clut)
        tiles.append(np.concatenate([a, b_], 0))
    sheet = np.concatenate(tiles, 1)
    dst = os.path.join(ROOT, 'my files', '그래픽', '도시제목_비교.png')
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    Image.fromarray(sheet).resize((sheet.shape[1] * 6, sheet.shape[0] * 6), Image.NEAREST).save(dst)
    print(dst)
