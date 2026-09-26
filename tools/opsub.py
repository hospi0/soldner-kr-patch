# -*- coding: utf-8 -*-
r"""오프닝(ZZOP.STR, MDEC BS v2 320×192 15fps + XA 37.8kHz 스테레오, 동영상 7섹터 뒤 소리 1섹터) 내레이션 자막
  번역 = work/text/movie_op.tsv (시각 · 원문 · 번역(\n 줄나눔) · 비고)
  자막: 나눔고딕 Bold 13px 흰 글씨 + 검은 1px 테두리, 화면 아래 가운데(최대 3줄).
        시간 = 행 시각부터 «다음 행 시각 − 0.3초» 와 «시각 + 글자 × 0.2초 + 2초» 중 이른 때까지.
  다시 굽기: psxavenc -t strcd -v v2 -F 1 -C 1(원본 파일·채널 1/1) -x 2 -X(소리 섹터를 동영상 뒤에 — 원본 순서)
  python tools/opsub.py preview   → my files/그래픽/오프닝자막_확인.png
  python tools/opsub.py build     → work/movie/kr/ZZOP.STR (디스크는 build.py 가 원래 자리에 넣는다)
"""
import os, re, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
FF = r'C:/claude/utils/ps1/ffmpeg.exe'
PSXAVENC = r'C:/claude/utils/ps1/psxavenc.exe'
SRC = os.path.join(ROOT, 'work', 'movie', 'ZZOP.STR')
OUT = os.path.join(ROOT, 'work', 'movie', 'kr', 'ZZOP.STR')
TSV = os.path.join(ROOT, 'work', 'text', 'movie_op.tsv')
FONT = r'C:\claude\utils\font\nanum-gothic\NanumGothicBold.ttf'
W, H, FPS, PX, LINE = 320, 192, 15, 13, 15


def cues():
    rows = []
    for ln in open(TSV, encoding='utf-8'):
        if ln.startswith('#') or not ln.strip():
            continue
        c = ln.rstrip('\n').split('\t')
        m, s = c[0].split(':')
        rows.append((int(m) * 60 + int(s), c[2].split('\\n')))
    out = []
    for k, (t, lines) in enumerate(rows):
        nxt = rows[k + 1][0] if k + 1 < len(rows) else 1e9
        end = min(nxt - 0.3, t + sum(map(len, lines)) * 0.2 + 2)
        out.append((int(t * FPS), int(end * FPS), lines))
    return out


def draw(fr, lines, F):
    im = Image.fromarray(fr)
    d = ImageDraw.Draw(im)
    y = H - 8 - (len(lines) - 1) * LINE
    for ln in lines:
        assert d.textlength(ln, font=F) <= W - 6, ('줄이 화면보다 넓다', ln)
        d.text((W / 2, y), ln, font=F, anchor='mm', fill=(255, 255, 255), stroke_width=1, stroke_fill=(0, 0, 0))
        y += LINE
    return np.asarray(im)


def frames():
    p = subprocess.Popen([FF, '-hide_banner', '-loglevel', 'error', '-f', 'psxstr', '-i', SRC, '-map', '0:v',
                          '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'], stdout=subprocess.PIPE)
    n = W * H * 3
    while True:
        b = p.stdout.read(n)
        if len(b) < n:
            break
        yield np.frombuffer(b, np.uint8).reshape(H, W, 3)
    p.wait()


def per_frame():
    pf = {}
    for a, b, lines in cues():
        for i in range(a, b + 1):
            pf[i] = lines
    return pf


def preview():
    F = ImageFont.truetype(FONT, PX)
    cs = cues()
    want = {(a + b) // 2: lines for a, b, lines in cs}
    tiles = []
    for i, fr in enumerate(frames()):
        if i in want:
            tiles.append(draw(fr, want[i], F))
    cols = 3
    rows = [np.concatenate(tiles[r:r + cols] + [np.zeros_like(tiles[0])] * (cols - len(tiles[r:r + cols])), 1)
            for r in range(0, len(tiles), cols)]
    dst = os.path.join(ROOT, 'my files', '그래픽', '오프닝자막_확인.png')
    Image.fromarray(np.concatenate(rows, 0)).save(dst)
    for a, b, lines in cs:
        print('%6.1f‥%6.1f초  %s' % (a / FPS, b / FPS, ' / '.join(lines)))
    print(dst)


def build():
    F = ImageFont.truetype(FONT, PX)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    wav = OUT + '.wav'; mkv = OUT + '.mkv'
    subprocess.run([FF, '-y', '-hide_banner', '-loglevel', 'error', '-f', 'psxstr', '-i', SRC, '-map', '0:a',
                    '-c:a', 'pcm_s16le', '-ar', '37800', '-ac', '2', wav], check=True)
    wr = subprocess.Popen([FF, '-y', '-hide_banner', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                           '-s', '%dx%d' % (W, H), '-framerate', str(FPS), '-i', '-', '-i', wav,
                           '-c:v', 'ffv1', '-c:a', 'pcm_s16le', mkv], stdin=subprocess.PIPE)
    pf = per_frame()
    n = 0
    for i, fr in enumerate(frames()):
        wr.stdin.write((draw(fr, pf[i], F) if i in pf else fr).tobytes()); n += 1
    wr.stdin.close(); wr.wait()
    subprocess.run([PSXAVENC, '-q', '-t', 'strcd', '-v', 'v2', '-f', '37800', '-b', '4', '-c', '2', '-F', '1', '-C', '1',
                    '-s', '%dx%d' % (W, H), '-r', str(FPS), '-x', '2', '-X', mkv, OUT], check=True)
    os.remove(wav); os.remove(mkv)
    old, new = os.path.getsize(SRC) // 2352, os.path.getsize(OUT) // 2352
    print('프레임 %d · %d → %d 섹터 %s' % (n, old, new, 'OK' if new <= old else '★원본보다 크다★'))


if __name__ == '__main__':
    {'preview': preview, 'build': build}[sys.argv[1] if len(sys.argv) > 1 else 'preview']()
