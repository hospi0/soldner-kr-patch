# -*- coding: utf-8 -*-
r"""전투 결과 문구 그림(BATTLE.GRP, 4bpp) 한글화 — 「引き分け」→무승부 · 「勝利」→승리 · 「敗北」→패배
  위치(세이브스테이트 VRAM ↔ 파일 대조, 2026-09-26): 한 줄 W 바이트, 40줄. BATTLE.GRP 안에 같은 그림이 세 벌(+200,704 간격).
  색표(VRAM 895,103): 0 투명 · 1 밝은 회색 테두리 · 2 · 3 짙은 테두리 · 4‥6 승리 채움 · 7‥9 무승부 채움 · 10‥13 패배 채움 · 14 흰 · 15 그림자.
  원본 꾸밈: 바깥 1px = 3, 그 안 1px = 1, 안쪽 = 줄마다 원본 그 줄의 채움 무늬(디더) 그대로,
            위·왼쪽 안쪽 가장자리 = 15·3 점선(3칸 주기). 글꼴 나눔고딕 ExtraBold, 몸통 높이 = 원본 몸통.
  python tools/battlewords.py → my files/그래픽/전투결과_비교.png
"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
FONT = r'C:\claude\utils\font\nanum-gothic\NanumGothicExtraBold.ttf'
GROW = 1                    # 글자 바깥으로 넓히는 px(테두리 자리)
COPIES = (0, 200704, 401408)
WORDS = [  # (이름, 파일 오프셋, 줄 바이트, 줄 수, 한글)
    ('draw', 16192, 76, 40, '무승부'),
    ('win', 12352, 48, 40, '승리'),                      # ★세 그림은 이어 붙어 있다: 승리 12,352 · 패배 14,272 · 무승부 16,192(각 1,920 B)
    ('lose', 14272, 48, 40, '패배'),                     #   (예전 12,354 / 14,276 은 앞 빈칸 때문에 잘못 맞은 위치 — 실기 «오른쪽 끝이 왼쪽으로»)
]
CLUT = [0x0000, 0x739c, 0x6b5a, 0x18c6, 0x25b7, 0x1954, 0x323b, 0x3f53, 0x32f0, 0x2aae, 0x6f34, 0x62d1, 0x5e8f, 0x7755, 0x7fff, 0x0421]


def rgb(c):
    r, g, b = c & 31, (c >> 5) & 31, (c >> 10) & 31
    return tuple((v << 3) | (v >> 2) for v in (r, g, b))


PAL = np.array([rgb(c) for c in CLUT], np.uint8)
PAL[0] = (122, 138, 80)                                    # 미리보기 바탕(전투 풀밭)


def unpack(b, W, H):
    a = np.frombuffer(b, np.uint8).reshape(H, W)
    p = np.zeros((H, W * 2), np.uint8); p[:, 0::2] = a & 15; p[:, 1::2] = a >> 4
    return p


def pack(p):
    return (p[:, 0::2] | (p[:, 1::2] << 4)).astype(np.uint8).tobytes()


def depth(ink):
    dist = np.zeros(ink.shape, int); cur = ink.copy(); k = 0
    while cur.any():
        k += 1; dist[cur] = k
        pad = np.pad(cur, 1); er = cur.copy()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                er &= pad[1 + dy:1 + dy + cur.shape[0], 1 + dx:1 + dx + cur.shape[1]]
        cur = er
    return dist


PIXEL = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri11-Bold.bdf'   # 도트 글꼴을 정수배로(원본 한자도 도트 그림)
SPACE = 1                   # 글자 사이(도트 글꼴 원래 px 단위)


def glyph_mask(text, H, W, body):
    if PIXEL:
        sys.path.insert(0, HERE)
        import bdf
        F = bdf.Font(PIXEL)
        cols = []
        for ch in text:
            pts, _ = F.draw(ch)
            xs = [x for x, _ in pts]; ys = [y for _, y in pts]
            cols.append((pts, min(xs), max(xs), min(ys), max(ys)))
        top = min(c[3] for c in cols); bot = max(c[4] for c in cols)
        widths = [c[2] - c[1] + 1 for c in cols]
        gw = sum(widths) + SPACE * (len(text) - 1)
        gh = bot - top + 1
        s = min(body // gh, (W - 4) // gw)
        a = np.zeros((gh * s, gw * s), bool)
        ox = 0
        for (pts, x0, x1, y0, y1), w in zip(cols, widths):
            for x, y in pts:
                a[(y - top) * s:(y - top + 1) * s, (ox + x - x0) * s:(ox + x - x0 + 1) * s] = True
            ox += w + SPACE
        return a
    """나눔고딕 ExtraBold 로 몸통 높이 body 가 되게, 가로 W 안(양옆 3px)"""
    for size in range(body + 20, 8, -1):
        F = ImageFont.truetype(FONT, size)
        im = Image.new('L', (W * 3, H * 3)); d = ImageDraw.Draw(im)
        d.text((10, 10), text, font=F, fill=255)
        a = np.asarray(im) > 110
        ys, xs = np.nonzero(a)
        h, w = ys.max() - ys.min() + 1, xs.max() - xs.min() + 1
        if h <= body and w <= W - 6:
            return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    raise SystemExit('글자가 안 들어간다 ' + text)


def render(orig, text):
    H, W = orig.shape
    oink = orig != 0
    od = depth(oink)
    ys = np.nonzero(oink.any(1))[0]
    y0, y1 = ys.min(), ys.max()                            # 원본 잉크 줄 범위(테두리 포함)
    fill_codes = {4, 5, 6, 7, 8, 9, 10, 11, 12, 13}
    seq = {}
    for y in range(H):
        s = [int(v) for v, dd in zip(orig[y], od[y]) if dd >= 4 and v in fill_codes]
        if s:
            seq[y] = s
    g = glyph_mask(text, H, W, (y1 - y0 + 1) - 2 * GROW)
    ink = np.zeros((H, W), bool)
    gy = y0 + GROW + ((y1 - y0 + 1 - 2 * GROW) - g.shape[0]) // 2
    gx = (W - g.shape[1]) // 2
    ink[gy:gy + g.shape[0], gx:gx + g.shape[1]] = g
    pad = np.pad(ink, 2)                                   # GROW px 넓히기(테두리 자리)
    big = np.zeros_like(ink)
    for dy in range(-GROW, GROW + 1):
        for dx in range(-GROW, GROW + 1):
            big |= pad[2 + dy:2 + dy + H, 2 + dx:2 + dx + W]
    dd = depth(big)
    out = np.zeros((H, W), np.uint8)
    keys = sorted(seq)
    for y in range(H):
        for x in range(W):
            k = dd[y, x]
            if k == 0:
                continue
            if k == 1:
                out[y, x] = 3
            elif k == 2:
                out[y, x] = 1
            else:
                edge = k == 3 and ((y > 0 and dd[y - 1, x] == 2) or (x > 0 and dd[y, x - 1] == 2))
                if edge:
                    out[y, x] = 3 if (x + y) % 3 == 0 else 15
                else:
                    s = seq[min(keys, key=lambda t: abs(t - y))]
                    out[y, x] = s[x % len(s)]
    return out


# ── 턴 표시(MARCH.GRP 37,777,728, 4bpp 176×32, VRAM 703,460 · 색표 VRAM 528,479) ─────────────────────────
#   원본 «ターン»: 기울임 글자 + 위 밝은 노랑 → 아래 어두운 노랑 + 왼쪽 위 검은 윤곽(8) + 오른쪽 아래 입체 그림자(9).
#   숫자(턴 수)는 따로 그린다(VRAM 기울임 숫자 0‥9) → 이 그림은 «턴» 한 글자.
TURN = ('turn', 37777728, 88, 32, '턴')
TCLUT = [0x0000, 0x27de, 0x1631, 0x0dce, 0x175a, 0x0e31, 0x0ab5, 0x058c, 0x0042, 0x0129, 0x46d5, 0x3651, 0x25cd, 0x3e51, 0x3776, 0x2690]
TPAL = np.array([rgb(c) for c in TCLUT], np.uint8); TPAL[0] = (60, 70, 45)
TGRAD = [1, 1, 4, 4, 4, 6, 6, 6, 2, 2, 5, 5, 3, 3, 7, 7]  # 위→아래 채움 단계(원본 색표의 밝기 순)


def render_turn(orig, text):
    H, W = orig.shape
    sx, sy = 4, 2                                         # 원본처럼 가로로 넓고 납작하게
    sys.path.insert(0, HERE)
    import bdf
    F = bdf.Font(PIXEL)
    pts, _ = F.draw(text)
    xs = [x for x, _ in pts]; ys = [y for _, y in pts]
    gw, gh = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
    g = np.zeros((gh * sy, gw * sx), bool)
    for x, y in pts:
        g[(y - min(ys)) * sy:(y - min(ys) + 1) * sy, (x - min(xs)) * sx:(x - min(xs) + 1) * sx] = True
    top = 3
    slant = 1.0                                           # 기울기(아래로 갈수록 왼쪽, 원본 약 1.5px/줄 — 한글은 획이 많아 덜 기울임)
    ink = np.zeros((H, W), bool)
    ox = 168 - g.shape[1] - int((g.shape[0] - 1) * slant)   # 오른쪽 끝을 원본 «ン» 끝 부근에(옆에 턴 숫자)
    for y in range(g.shape[0]):
        sh = int(round((g.shape[0] - 1 - y) * slant))
        for x in np.nonzero(g[y])[0]:
            if 0 <= top + y < H and 0 <= ox + x + sh < W:
                ink[top + y, ox + x + sh] = True
    out = np.zeros((H, W), np.uint8)
    for k in range(3, 0, -1):                             # 입체 그림자: 오른쪽 아래로(원본에서 가장 많은 그림자 색인 9)
        sh = np.zeros_like(ink); sh[k // 2:, k:] = ink[:H - k // 2, :W - k]
        out[sh] = 9
    # ★색은 원본 색인 무늬를 옮긴다(실기 2026-09-26: 색표 짐작으로 칠했더니 빨강·크림으로 나왔다 — 색표가 실행 중 바뀐다).
    #   원본 글자 몸통(9 아닌 곳)을 (줄 비율, 가장자리 깊이)별로 모아 같은 자리에 같은 무늬를 입힌다.
    body = (orig != 0) & (orig != 9)
    od = np.minimum(depth(body), 4)
    brow = np.nonzero(body.any(1))[0]; b0, b1 = brow.min(), brow.max()
    seq = {}
    for y in range(H):
        for k in range(1, 5):
            s = [int(v) for v in orig[y][(od[y] == k) & body[y]]]
            if s:
                seq[(y, k)] = s
    gd = np.minimum(depth(ink), 4)
    rows = np.nonzero(ink.any(1))[0]
    r0, r1 = rows.min(), rows.max()
    for y in range(H):
        yo = int(round(b0 + (y - r0) / max(1, r1 - r0) * (b1 - b0)))
        for x in np.nonzero(ink[y])[0]:
            k = gd[y, x]
            s = None
            for kk in (k, k - 1, k + 1, 4, 3, 2, 1):
                ys_ = [yy for (yy, k2) in seq if k2 == kk]
                if 1 <= kk <= 4 and ys_:
                    s = seq[(min(ys_, key=lambda t: abs(t - yo)), kk)]
                    break
            out[y, x] = s[x % len(s)]
    return out


VFONT = r'C:\claude\utils\font\nanum-gothic\NanumGothicExtraBold.ttf'    # 윤곽 글꼴(맑은 고딕·나눔 Bold·검은고딕과 비교해 원본 굵기에 가장 가까움)(사용자 «더 고해상도로 예쁘게» 2026-09-26 — 도트 3배는 계단이 심했다)
VSTRETCH = 1.25                              # 가로 늘림 상한(칸이 남으면 원본처럼 넓게)
VSPACE = 3                                   # 글자 사이 px


def vglyph(text, H, W, stretch=None, space=None, thr=110):
    """윤곽 글꼴을 4배로 그려 줄인 글자 가면(높이 H, 가로 W 안). 글자별로 그려 간격을 맞춘다"""
    SS = 4
    F = ImageFont.truetype(VFONT, H * SS)
    common = any(not ('가' <= ch <= '힣') for ch in text)   # 부호·띄어쓰기가 있으면 공통 기준선(«…»·«!» 제자리)
    raw = []
    for ch in text:
        im = Image.new('L', (H * SS * 2, H * SS * 2)); ImageDraw.Draw(im).text((H * SS // 2, H * SS // 4), ch, font=F, fill=255)
        raw.append(np.asarray(im))
    allys = np.nonzero(np.any([r > 127 for r in raw], 0).any(1))[0]
    marks = []
    for ch, a in zip(text, raw):
        ys, xs = np.nonzero(a > 127)
        if not len(xs):                                    # 띄어쓰기
            marks.append(np.zeros(((allys.max() - allys.min() + 1) if common else H * SS, H * SS * 3 // 10), np.uint8))
            continue
        if common:
            marks.append(a[allys.min():allys.max() + 1, xs.min():xs.max() + 1])
        else:
            marks.append(a[ys.min():ys.max() + 1, xs.min():xs.max() + 1])
    top = 0
    hmax = max(m.shape[0] for m in marks)
    scale = H / hmax
    widths = [m.shape[1] * scale for m in marks]
    sp = VSPACE if space is None else space
    total = sum(widths) + sp * (len(text) - 1)
    st = min(stretch or VSTRETCH, (W - 4 - sp * (len(text) - 1)) / sum(widths))
    out = np.zeros((H, W), bool)
    gw = [max(1, int(round(w * st))) for w in widths]
    x = (W - (sum(gw) + sp * (len(text) - 1))) // 2
    for m, w in zip(marks, gw):
        h = max(1, int(round(m.shape[0] * scale)))
        im = Image.fromarray(m).resize((w, h), Image.LANCZOS)
        a = np.asarray(im) > thr
        y = (H - h) // 2 + (H - h) % 2 * 0
        out[y:y + h, x:x + w] |= a
        x += w + sp
    return out


def render_v(orig, text):
    """윤곽 글꼴판: 바깥 1px = 3, 글자 가장자리 1px = 1, 위·왼쪽 안쪽 = 15·3 점선, 안 = 원본 줄 채움 무늬"""
    H, W = orig.shape
    oink = orig != 0
    od = depth(oink)
    ys = np.nonzero(oink.any(1))[0]
    y0, y1 = ys.min(), ys.max()
    fill_codes = {4, 5, 6, 7, 8, 9, 10, 11, 12, 13}
    seq = {}
    for y in range(H):
        s = [int(v) for v, dd in zip(orig[y], od[y]) if dd >= 4 and v in fill_codes]
        if s:
            seq[y] = s
    keys = sorted(seq)
    g = np.zeros((H, W), bool)
    gh = (y1 - y0 + 1) - 2
    g[y0 + 1:y0 + 1 + gh] = vglyph(text, gh, W)
    gd = depth(g)
    out = np.zeros((H, W), np.uint8)
    pad = np.pad(g, 1)
    ring = np.zeros_like(g)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            ring |= pad[1 + dy:1 + dy + H, 1 + dx:1 + dx + W]
    out[ring & ~g] = 3
    for y in range(H):
        for x in np.nonzero(g[y])[0]:
            k = gd[y, x]
            if k == 1:
                out[y, x] = 1
            elif k == 2 and ((y > 0 and gd[y - 1, x] == 1) or (x > 0 and gd[y, x - 1] == 1)) and gd[min(H - 1, y + 1), x] >= 2:
                out[y, x] = 3 if (x + y) % 3 == 0 else 15
            else:
                s = seq[min(keys, key=lambda t: abs(t - y))]
                out[y, x] = s[x % len(s)]
    return out


# ── 임무 결과(MARCH.GRP 37,766,464, 4bpp 352×64 = 위 32줄 «任務達成！» + 아래 32줄 «任務失敗…», VRAM 895,380) ──────────
#   꾸밈이 «줄 × 테두리 깊이»마다 두 색을 섞은 무늬 → 원본에서 (줄, 깊이)별 색인 무늬를 떠서 한글 글자에 그대로 입힌다.
#   색표는 세이브스테이트에 안 올라와 있어 미리보기는 회색조(게임에선 원본 색 그대로).
MISSION = (37766464, 176, [(0, 32, '임무 달성!'), (32, 64, '임무 실패…')])
MSHEAR = 0.25                                 # 원본의 살짝 기운 글자


def render_m(orig, text):
    H, W = orig.shape
    oink = orig != 0
    od = np.minimum(depth(oink), 5)
    seq = {}
    for y in range(H):
        for k in range(1, 6):
            s = [int(v) for v in orig[y][od[y] == k]]
            if s:
                seq[(y, k)] = s
    rows = np.nonzero(oink.any(1))[0]
    y0, y1 = rows.min(), rows.max()
    gh = (y1 - y0 + 1) - 2
    extra = int(gh * MSHEAR) + 1
    g0 = vglyph(text, gh, W - extra, stretch=2.0, space=6)
    g = np.zeros((H, W), bool)
    for y in range(gh):
        sh = int((gh - 1 - y) * MSHEAR)
        g[y0 + 1 + y, sh:sh + W - extra] = g0[y, :W - extra]
    pad = np.pad(g, 1)
    ink = np.zeros_like(g)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            ink |= pad[1 + dy:1 + dy + H, 1 + dx:1 + dx + W]
    dd = np.minimum(depth(ink), 5)
    out = np.zeros((H, W), np.uint8)
    for y in range(H):
        for x in np.nonzero(ink[y])[0]:
            k = dd[y, x]
            cand = [kk for kk in (k, k - 1, k + 1, 5, 4, 3) if 1 <= kk <= 5]
            s = None
            for kk in cand:
                ys_ = [yy for (yy, k2) in seq if k2 == kk]
                if ys_:
                    s = seq[(min(ys_, key=lambda t: abs(t - y)), kk)]
                    break
            out[y, x] = s[x % len(s)]
    return out


def build_mission(march):
    off, W, specs = MISSION
    full = unpack(bytes(march[off:off + W * 64]), W, 64)
    for a, b, ko in specs:
        full[a:b] = render_m(full[a:b], ko)
    march[off:off + W * 64] = pack(full)


# ══ ★★8bpp 판(2026-09-26 색 시험판으로 확정): 턴·임무 그림은 4bpp 가 아니라 «8bpp»(1바이트 = 1화소, 256색) ══════════
#   (위의 4bpp 처리는 틀렸다 — 두 칸씩 짝지은 무늬가 사실은 한 화소 색 0xNN). 화면엔 1:1 로 그려진다.
#   원본 «ターン»을 실기 스샷에 1:1 로 맞대 얻은 바이트 → 색(오차 0):
#     0x8f (255,255,107) 0x91 (255,255,90) 0x92 (247,247,74) 0x90 (214,214,82) 0x95 (214,214,41) 0x97 (173,173,16)
#     0x96 (140,140,24) 0x94 (115,115,24) 0x98 (99,99,8) 0x9a (74,74,0) 0x62 (57,49,0) 0x99 (16,16,0)
TURN8 = (37777728, 88, 32, '턴')
T8_RIM, T8_TOP, T8_FILL, T8_LOW, T8_SHADOW = 0x90, 0x94, 0x98, 0x9a, 0x99   # 숫자 «4»처럼 짙은 금 몸통 + 한 단계 낮춘 밝은 금 테두리(사용자 «너무 밝고 경박해» 2026-09-26)
T8_FONT = r'C:\claude\utils\font\nanum-gothic\NanumGothicBold.ttf'   # 획도 숫자처럼 가늘게
T8_H = 26                                      # 글자 높이(숫자와 비슷하게 — 사용자 «조금 더 키우고»)
T8_SLANT = 0.3                                 # 숫자와 같은 기울기


def shear(mask, slant):
    h, w = mask.shape
    extra = int((h - 1) * slant) + 1
    out = np.zeros((h, w + extra), bool)
    for y in range(h):
        sh = int(round((h - 1 - y) * slant))
        out[y, sh:sh + w] = mask[y]
    return out


def dilate(m, r=1):
    pad = np.pad(m, r)
    out = np.zeros_like(m)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out |= pad[r + dy:r + dy + m.shape[0], r + dx:r + dx + m.shape[1]]
    return out


def render_turn8(orig, text):
    H, W = orig.shape
    global VFONT
    keep, VFONT = VFONT, T8_FONT
    g = shear(vglyph(text, T8_H, T8_H * 2), T8_SLANT)
    VFONT = keep
    cols = np.nonzero(g.any(0))[0]; g = g[:, cols.min():cols.max() + 1]
    ink = np.zeros((H, W), bool)
    y0 = (H - T8_H) // 2 - 1
    x0 = W - 4 - g.shape[1]                                # 오른쪽 끝 가까이(바로 옆에 턴 숫자)
    ink[y0:y0 + g.shape[0], x0:x0 + g.shape[1]] = g
    rim = dilate(ink)
    shadow = np.zeros_like(rim); shadow[2:, 2:] = rim[:-2, :-2]
    out = np.zeros((H, W), np.uint8)
    out[shadow] = T8_SHADOW
    out[rim] = T8_RIM
    rows = np.nonzero(ink.any(1))[0]; r0, r1 = rows.min(), rows.max()
    for y in range(H):
        for x in np.nonzero(ink[y])[0]:
            t = (y - r0) / max(1, r1 - r0)
            out[y, x] = T8_TOP if t < 0.2 else (T8_FILL if t < 0.75 else T8_LOW)
    return out


M8FONT = r'C:\claude\utils\font\logo\BlackHanSans.ttf'
MISSION8 = (37766464, 176, [(0, 32, '임무 달성!'), (32, 64, '임무 실패...')])   # «…»는 검은고딕에 없음 → 마침표 셋 · 8bpp 176×64(위·아래 32줄씩)


def render_m8(orig, text):
    """원본의 (줄, 테두리 깊이)별 최빈 바이트를 한글 글자에 입힌다(8bpp라 한 칸 = 한 화소 → 깔끔)"""
    H, W = orig.shape
    oink = orig != 0
    od = np.minimum(depth(oink), 5)
    rows = np.nonzero(oink.any(1))[0]; y0, y1 = rows.min(), rows.max()
    best = {}
    for y in range(H):
        for k in range(1, 6):
            s = orig[y][od[y] == k]
            if len(s):
                best[(y, k)] = int(np.bincount(s).argmax())
    global VFONT
    keep, VFONT = VFONT, M8FONT                            # 검은고딕(나눔 ExtraBold·바깥 테두리안과 비교 — 받침 세 겹이 안 뭉침)
    gh = (y1 - y0 + 1)
    g0 = shear(vglyph(text, gh, W - 16, stretch=1.2, space=7, thr=60), 0.2)   # 기울임(정자 판을 실기로 보고 사용자가 이탤릭으로 되돌림)
    VFONT = keep
    cols = np.nonzero(g0.any(0))[0]; g0 = g0[:, cols.min():cols.max() + 1]
    g = np.zeros((H, W), bool)
    gx = (W - g0.shape[1]) // 2
    g[y0:y0 + g0.shape[0], gx:gx + g0.shape[1]] = g0[:H - y0]
    ink = g                                                # 테두리는 글자 안쪽 깊이로(바깥으로 넓히면 받침이 뭉친다)
    dd = np.minimum(depth(ink), 5)
    out = np.zeros((H, W), np.uint8)
    for y in range(H):
        for x in np.nonzero(ink[y])[0]:
            k = dd[y, x]
            for kk in (k, k - 1, k + 1, 5, 4, 3, 2, 1):
                if 1 <= kk <= 5:
                    ys_ = [yy for (yy, k2) in best if k2 == kk]
                    if ys_:
                        out[y, x] = best[(min(ys_, key=lambda t: abs(t - y)), kk)]
                        break
    return out


#   «임무 달성!»: 줄마다 원본 바이트를 옮기니 중간에 줄이 보였다(사용자) → 바깥 짙은 갈색 · 안 테두리 밝은 금 ·
#   몸통은 아래(짙은 금)→위(옅은 금) 부드러운 단계. 바이트 색은 실기 스샷 1:1 대조값.
M8_OUT, M8_RIM = 0x2b, 0x6e                                  # (107,33,0) · (206,198,66) — 사용자 «너무 밝아»
M8_RAMP = [0x55, 0x4c, 0x4e, 0x49, 0x46, 0x44, 0x48, 0x30, 0x47, 0x33, 0x31]   # 위(옅음) → 아래(짙음), 한 단계 어둡게


def smooth_m8(out, ink):
    H, W = out.shape
    dd = depth(ink)
    rows = np.nonzero(ink.any(1))[0]; r0, r1 = rows.min(), rows.max()
    res = np.zeros_like(out)
    for y in range(H):
        t = (y - r0) / max(1, r1 - r0)
        fillb = M8_RAMP[min(len(M8_RAMP) - 1, int(t * len(M8_RAMP)))]
        for x in np.nonzero(ink[y])[0]:
            res[y, x] = M8_OUT if dd[y, x] == 1 else (M8_RIM if dd[y, x] == 2 else fillb)
    return res


def build_mission8(march):
    off, W, specs = MISSION8
    full = np.frombuffer(bytes(march[off:off + W * 64]), np.uint8).reshape(64, W).copy()
    for a, b, ko in specs:
        r = render_m8(full[a:b], ko)
        if a == 0:                                            # 달성(색 확인됨) — 부드러운 단계
            r = smooth_m8(r, r != 0)
        full[a:b] = r
    march[off:off + W * 64] = full.tobytes()


def build_turn(march, test=False):
    off, W, H, ko = TURN8
    if not test:
        o = np.frombuffer(bytes(march[off:off + W * H]), np.uint8).reshape(H, W)
        march[off:off + W * H] = render_turn8(o, ko).tobytes()
        return
    name, off, W, H, ko = TURN
    name, off, W, H, ko = TURN
    if test:                                              # 색 시험판: 색인 1‥15 를 왼쪽부터 세로 띠(11px)로 — 실기 스샷으로 색표를 읽는다
        p = np.zeros((H, W * 2), np.uint8)
        for i in range(1, 16):
            p[3:29, (i - 1) * 11 + 3:(i - 1) * 11 + 12] = i
        march[off:off + W * H] = pack(p)
        return
    march[off:off + W * H] = pack(render_turn(unpack(bytes(march[off:off + W * H]), W, H), ko))


def build(grp):
    for name, off, W, H, ko in WORDS:
        base = bytes(grp[off:off + W * H])
        for c in COPIES:
            assert bytes(grp[off + c:off + c + W * H]) == base, (name, c, '사본이 다르다')
        new = pack(render_v(unpack(base, W, H), ko))
        for c in COPIES:
            grp[off + c:off + c + W * H] = new


if __name__ == '__main__':
    d = open(os.path.join(ROOT, 'work', 'BATTLE.GRP'), 'rb').read()
    tiles = []
    for name, off, W, H, ko in WORDS:
        o = unpack(d[off:off + W * H], W, H)
        n = render_v(o, ko)
        tiles.append(np.vstack([PAL[o], np.zeros((4, W * 2, 3), np.uint8), PAL[n]]))
    m = open(os.path.join(ROOT, 'work', 'MARCH.GRP'), 'rb').read()
    name, off, W, H, ko = TURN
    o = unpack(m[off:off + W * H], W, H)
    tiles.append(np.vstack([TPAL[o], np.zeros((4, W * 2, 3), np.uint8), TPAL[render_turn(o, ko)]]))
    h = max(t.shape[0] for t in tiles)
    row = np.hstack([np.pad(t, ((0, h - t.shape[0]), (0, 8), (0, 0))) for t in tiles])
    dst = os.path.join(ROOT, 'my files', '그래픽', sys.argv[1] if len(sys.argv) > 1 else '전투결과_비교.png')
    Image.fromarray(row).resize((row.shape[1] * 3, row.shape[0] * 3), Image.NEAREST).save(dst)
    print(dst)


# ── 이달의 사건(GRP.BIN 634,368, 8bpp 240×32, VRAM 255,221 · 화면 1:1) ───────────────────────────────
#   원본 «今月の出来事»(정자): 바깥 1px 갈색 윤곽(위·왼쪽 밝은 갈색 73, 아래·오른쪽 짙은 갈색 51),
#   글자 안 가장자리 위·왼쪽 흰빛(121), 아래·오른쪽 옅은 노랑(137), 속 노랑(143). 바이트 색은 세이브스테이트 화면 버퍼 1:1 대조.
EVENTS8 = (634368, 240, 32, '이달의 사건')
EV_OUT_TL, EV_OUT_BR, EV_IN_TL, EV_IN_BR, EV_FILL = 73, 51, 121, 137, 143


def render_events(text):
    off, W, H, _ = EVENTS8
    g0 = vglyph(text, 24, W - 40, stretch=1.1, space=4)
    cols = np.nonzero(g0.any(0))[0]; g0 = g0[:, cols.min():cols.max() + 1]
    g = np.zeros((H, W), bool)
    gx = (W - g0.shape[1]) // 2
    g[4:4 + g0.shape[0], gx:gx + g0.shape[1]] = g0
    ring = dilate(g) & ~g
    out = np.zeros((H, W), np.uint8)
    def near(m, y, x, dirs):
        return any(0 <= y + dy < H and 0 <= x + dx < W and m[y + dy, x + dx] for dy, dx in dirs)
    TL, BR = ((1, 0), (0, 1), (1, 1)), ((-1, 0), (0, -1), (-1, -1))   # 글자가 아래·오른쪽에 있으면 위·왼쪽 윤곽
    for y, x in zip(*np.nonzero(ring)):
        out[y, x] = EV_OUT_TL if near(g, y, x, TL) else EV_OUT_BR
    gd = depth(g)
    for y, x in zip(*np.nonzero(g)):
        if gd[y, x] == 1:
            out[y, x] = EV_IN_TL if near(ring, y, x, ((-1, 0), (0, -1))) else EV_IN_BR
        else:
            out[y, x] = EV_FILL
    return out


def build_events(grp):
    off, W, H, ko = EVENTS8
    grp[off:off + W * H] = render_events(ko).tobytes()
