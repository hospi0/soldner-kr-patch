# -*- coding: utf-8 -*-
r"""도시 화면 배경 20장(GRP.BIN) 오른쪽 아래 구운 도시 이름 → 한글
  기록: 색표 512 B + 8bpp 320×240, 38섹터(77,824 B) 간격, 1,216,512‥2,695,168 (순서 = 도시 목록 표지 순서).
  글자 찾기: 아래 띠(190‥232행)에서 «주변 7×7 중앙값보다 ±4 이상 밝거나 어두운» 화소 → 가장 많이 모인 20행 창
            → 그 창 안 가로 덩어리(틈 ≤ 10)를 제목 상자로. 밝은 쪽 = 글자, 어두운 쪽 = 오른쪽 아래 그림자.
  지우기: 상자 안 후보 화소 둘레 1px 를 가까운 배경 색인으로 번져 메움.
  그리기: 모든 도시 같은 크기(사용자 2026-09-26 «그래픽이니 작게 하지 말고»), 원본 제목 오른쪽 끝에 맞춰 왼쪽으로 뻗는다.
          가늘게 오른쪽으로 기울이고, 위→아래 흰 심·중간·파랑 3색(원본 글자 화소 밝기 3분위의 최빈 색인) + 오른쪽 아래 1px 그림자.
  python tools/towntitles.py → my files/그래픽/지역제목_비교.png
"""
import os, sys
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
FONT = r'C:\claude\utils\font\nanum-gothic\NanumGothic.ttf'
BASE, STEP, W, H = 1216512, 77824, 320, 240
JP_LEN = [4, 4, 4, 4, 5, 6, 4, 4, 4, 6, 5, 5, 6, 7, 4, 4, 4, 4, 5, 5]      # 원문 가타카나 글자 수(トルニオ … ホーイック)
STRICT_X0 = {0: 236}                 # 토르니오: 글자 왼쪽 눈 나무가 통째로 지워졌다(사용자 2026-09-26) — 이 도시만 좁고 엄격하게
X1_FIX = {2: 302, 18: 299}          # 오른쪽 바위·땅 무늬가 끝으로 잡히는 곳(기센·오리스타노) — 실측한 제목 끝
KANA_W = 16.5                                                               # 원본 제목 가타카나 한 글자 폭(바이덴 66px/4자)
NAMES = ['토르니오', '레스노이', '기센', '바이덴', '브라우엔', '프라이하이트', '올비아', '홈토프', '트리르', '안스바흐',
         '펠덴', '샤토루', '오르토독스', '로즈플리트', '랑그르', '바스티아', '마르살라', '로아르', '오리스타노', '호이크']
PX, SHEAR, GAP = 17, 0.3, 1          # 글자 크기·기울기·글자 사이(원본 가타카나와 비슷한 느낌)


def load(grp, i):
    p = BASE + i * STEP
    clut = np.frombuffer(bytes(grp[p:p + 512]), '<u2').astype(int)
    img = np.frombuffer(bytes(grp[p + 512:p + 512 + W * H]), np.uint8).reshape(H, W).copy()
    return p, clut, img


def rgb_of(clut):
    return np.stack([clut & 31, (clut >> 5) & 31, (clut >> 10) & 31], -1)


def find_title(img, clut, n_jp, x1_fix=None):
    R = rgb_of(clut)[img].astype(float)
    L = (R[..., 0] * 3 + R[..., 1] * 6 + R[..., 2]) / 10
    loc = np.median(sliding_window_view(np.pad(L, 3, mode='edge'), (7, 7)), axis=(-1, -2))
    d = L - loc
    band = np.zeros(L.shape, bool); band[190:233, 120:318] = True
    lit = (d >= 5) & (L >= 11) & band                    # 밝은 글자 화소(상자 잡기용)
    rows = lit.sum(1)
    y0 = max(range(190, 215), key=lambda y: rows[y:y + 18].sum())
    win = lit[y0:y0 + 18]
    cols = np.nonzero(win.any(0))[0]
    runs, cur = [], [cols[0]]
    for c in cols[1:]:
        if c - cur[-1] <= 12: cur.append(c)
        else: runs.append(cur); cur = [c]
    runs.append(cur)
    run = max(runs, key=lambda r: win[:, r[0]:r[-1] + 1].sum())
    strong = [c for c in run if win[:, c].sum() >= 2]    # 획이 2화소 이상인 열 — 오른쪽 잡음 점을 끝으로 잡지 않게
    x1 = x1_fix or strong[-1] + 1
    x0 = max(run[0] - 6, int(x1 - n_jp * KANA_W - 14))   # 첫 글자 왼쪽 획 끝까지 넉넉히        # 원문 글자 수만큼만 — 왼쪽 눈 나무 등은 제외
    ys = np.nonzero(lit[y0:y0 + 18, x0:x1].any(1))[0]
    box = (x0, y0 + ys.min(), x1, y0 + ys.max() + 1)
    cand = (np.abs(d) >= 4) & band                       # 지울 화소 = 밝은 글자 + 어두운 그림자
    return box, cand, d, L


def rebuild(img, clut, name, n_jp, x1_fix=None, strict_x0=None):
    (x0, y0, x1, y1), cand, d, L = find_title(img, clut, n_jp, x1_fix)
    if strict_x0 is not None:
        # 명암 큰 배경(토르니오 눈 나무)이 글자 옆에 붙은 곳: 상자를 좁히고, 지울 화소 = 제목색 밝은 화소 + 그 오른쪽 아래 2px 안 어두운 그림자만
        x0 = strict_x0
        rgbv = rgb_of(clut)[img]
        lit = (d >= 5) & (L >= 11) & (rgbv[..., 2] >= rgbv[..., 0])
        near = np.zeros_like(lit)
        for dy in (0, 1, 2):
            for dx in (0, 1, 2):
                near |= np.roll(np.roll(lit, dy, 0), dx, 1)
        cand = lit | (near & (d <= -4))
    m = np.zeros_like(cand); m[y0 - 1:y1 + 2, x0 - 1:x1 + 2] = cand[y0 - 1:y1 + 2, x0 - 1:x1 + 2]   # 그림자는 오른쪽 아래 1‥2px
    light = m & (d > 0); dark = m & (d < 0)
    lv = img[light]; order = lv[np.argsort(L[light])]
    k = max(1, len(order) // 3)
    c_blue = int(np.bincount(order[:k]).argmax()); c_mid = int(np.bincount(order[k:2 * k]).argmax())
    c_white = int(np.bincount(order[2 * k:]).argmax())
    c_shadow = int(np.bincount(img[dark]).argmax()) if dark.any() else None
    kill = m.copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            kill |= np.roll(np.roll(m, dy, 0), dx, 1)
    kill[:y0 - 2] = False; kill[y1 + 2:] = False
    out = img.copy()
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
    # 한글 그리기: 오른쪽 끝 = 원본 제목 오른쪽 끝, 세로 가운데 = 원본 가운데
    F = ImageFont.truetype(FONT, PX)
    lay = Image.new('L', (W + 40, H), 0)
    dr = ImageDraw.Draw(lay)
    widths = [dr.textlength(ch, font=F) for ch in name]
    total = sum(widths) + GAP * (len(name) - 1)
    x = x1 + 20 - total
    cy = (y0 + y1) / 2
    for ch, w in zip(name, widths):
        dr.text((x, cy), ch, font=F, anchor='lm', fill=255)
        x += w + GAP
    lay = lay.transform(lay.size, Image.AFFINE, (1, SHEAR, -cy * SHEAR, 0, 1, 0), Image.BICUBIC)
    a = np.asarray(lay)[:, 20:20 + W] > 90
    ys, xs = np.nonzero(a)
    top, bot = ys.min(), ys.max()
    if c_shadow is not None:
        sh = np.zeros_like(a); sh[1:, 1:] = a[:-1, :-1]
        out[sh & ~a] = c_shadow
    for yy, xx in zip(ys, xs):
        t = (yy - top) / max(1, bot - top)
        out[yy, xx] = c_white if t < 0.4 else (c_mid if t < 0.75 else c_blue)
    return out, (x0, y0, x1, y1)


def build(grp):
    for i, name in enumerate(NAMES):
        p, clut, img = load(grp, i)
        new, _ = rebuild(img, clut, name, JP_LEN[i], X1_FIX.get(i), STRICT_X0.get(i))
        grp[p + 512:p + 512 + W * H] = new.tobytes()


if __name__ == '__main__':
    grp = bytearray(open(os.path.join(ROOT, 'work', 'GRP.BIN'), 'rb').read())
    tiles = []
    for i, name in enumerate(NAMES):
        p, clut, img = load(grp, i)
        new, box = rebuild(img, clut, name, JP_LEN[i], X1_FIX.get(i), STRICT_X0.get(i))
        rgb = lambda im: (rgb_of(clut)[im] * 8).astype(np.uint8)
        a, b = rgb(img)[178:238, 138:320], rgb(new)[178:238, 138:320]
        tiles.append(np.concatenate([a, b], 0))
        print(i, name, 'box', box)
    rows = [np.concatenate(tiles[r * 4:(r + 1) * 4], 1) for r in range(5)]
    sheet = np.concatenate(rows, 0)
    dst = os.path.join(ROOT, 'my files', '그래픽', '지역제목_비교.png')
    Image.fromarray(sheet).resize((sheet.shape[1] * 2, sheet.shape[0] * 2), Image.NEAREST).save(dst)
    print(dst)
