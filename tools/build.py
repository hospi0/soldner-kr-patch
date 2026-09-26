# -*- coding: utf-8 -*-
r"""젤드너실트 스페셜 한글판 빌더 — work/text/*.tsv 번역(KO 열) 전부 → 디스크 이미지
  python tools/build.py                 예행(검사만)
  python tools/build.py --write [--install]

  1) 글꼴 FONT12.BIN : 번역에 쓰인 한글 음절 → 한자 칸을 빌려 12×12 로 덮음(tools/kr12.py, 배정 work/kr/charmap.tsv 이어받음).
     «아직 번역 안 된 줄»의 원문 글자 칸은 빌리지 않는다(부분 빌드에서도 원문이 멀쩡하게).
  2) 대사 MESSAGE.DAT(msg.tsv) : 블록마다 문장을 새로 짜고 오프셋 표만 고침. 블록 크기(머리 표의 크기, 2048 배수) 안.
     대사창은 2바이트 글자만 — {xx}·\n 밖의 반각(숫자·영문·공백)은 전각으로 바꿔 넣는다.
  3) 실행 파일 SLPS_013.19(exe.tsv) · JOBDATA(job.tsv) · BEVENT(bevent.tsv) · SCENARIO(scenario.tsv) : 제자리, 원문 바이트 이내, 남는 자리 NUL.
     ★인물 이름표는 EXE 쪽 인물 표를 쓴다(SCENARIO 는 사본) — 두 곳 다 번역할 것.
  4) 그림 GRP.BIN : 건물 표지(plates) · 도시 제목 20장(towntitles) · 도시 이름 판(cityplates) · 연월 상자(datebox).
  ⏳ kana.tsv(반각 가타카나 이름)는 반각→전각 변환 표 해독 전이라 아직 안 넣음.
"""
import hashlib, os, re, shutil, struct, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import kr12, discfs, plates, towntitles, cityplates, datebox, msgcode
from cdsector import fix_sector

SRC = r'C:\claude\roms\ps\Soldnerschild Special (Japan)\Soldnerschild Special (Japan).bin'
CUE = SRC[:-4] + '.cue'
OUT = os.path.join(ROOT, 'work', 'out', os.path.basename(SRC))
INSTALL = r'F:\hospi\roms\ps roms\Soldnerschild Special (Japan)'
TXT = os.path.join(ROOT, 'work', 'text')
if '--text' in sys.argv:                                        # 시험용 번역 폴더
    TXT = sys.argv[sys.argv.index('--text') + 1]
INPLACE = [('exe.tsv', '/SLPS_013.19'), ('job.tsv', '/JOBDATA.DAT'), ('bevent.tsv', '/BEVENT.DAT'), ('scenario.tsv', '/SCENARIO.DAT')]


def load_tsv(name):
    rows = []
    p = os.path.join(TXT, name)
    if not os.path.exists(p):
        return rows
    for ln in open(p, encoding='utf-8'):
        if ln.startswith('#'):
            continue
        c = ln.rstrip('\n').split('\t')
        if len(c) >= 3:
            rows.append((c[0], int(c[1]), c[2], c[3] if len(c) > 3 else ''))
    return rows


def wide(s):
    """{xx}·\\n 밖의 반각 영숫자·공백 → 전각(대사창은 2바이트 글자만)"""
    out = []
    for tok in re.split(r'(\{[a-z](?::[0-9a-f]*)?\}|\{[0-9a-f]{2}\}|\\n)', s):   # 제어 표기(tools/msgcode.py)는 그대로
        if tok.startswith('{') or tok == '\\n':
            out.append(tok)
        else:
            out.append(''.join('\u3000' if ch == ' ' else (chr(ord(ch) + 0xFEE0) if '!' <= ch <= '~' else ch) for ch in tok))
    return ''.join(out)


def jp_bytes(jp, newline_n):
    out = bytearray()
    for tok in re.split(r'(\{[0-9a-f]{2}\}|\\n)', jp):
        if not tok:
            continue
        if tok == '\\n':
            out += b'n'
        elif re.fullmatch(r'\{[0-9a-f]{2}\}', tok):
            out.append(int(tok[1:3], 16))
        else:
            out += tok.encode('cp932')
    return bytes(out)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    fs = {p: (l, s) for p, l, s in discfs.read_fs(SRC)[4]}
    names = ['/MESSAGE.DAT', '/FONT12.BIN', '/GRP.BIN'] + [p for _, p in INPLACE]
    with open(SRC, 'rb') as f:
        data = {p: bytearray(discfs.sector(f, fs[p][0], (fs[p][1] + 2047) // 2048)[:fs[p][1]]) for p in names}
    orig = {p: bytes(d) for p, d in data.items()}
    err = []
    msg_rows = load_tsv('msg.tsv')
    inpl = {name: load_tsv(name) for name, _ in INPLACE}
    done = lambda r: r[3] and r[3] != '='
    # --- 1) 글꼴 -----------------------------------------------------------------------------------
    all_ko = [wide(r[3]) for r in msg_rows if done(r)] + [r[3] for rows in inpl.values() for r in rows if done(r)]
    sylls = sorted({c for ko in all_ko for c in ko if '가' <= c <= '힣'})
    keep = set()                                                  # 아직 번역 안 된 줄의 원문 글자 칸은 빌리지 않음
    for rows in [msg_rows] + list(inpl.values()):
        for r in rows:
            if not done(r):
                keep |= {struct.unpack('>H', ch.encode('cp932'))[0] for ch in r[2]
                         if len(ch.encode('cp932', 'ignore')) == 2}
    fnt = data['/FONT12.BIN']
    try:
        m = kr12.assign(sylls, fnt, kr12.kanji_freq(orig['/MESSAGE.DAT']), keep)
    except StopIteration:
        raise SystemExit('⛔ 한자 칸 부족 — 음절 %d' % len(sylls))
    kr12.put_font(fnt, m)
    # 번역문 글자 검사: 한글·글꼴에 있는 글자만
    fcodes = set(kr12.codes(fnt)) | {0x8140}
    for ko in all_ko:
        for ch in re.sub(r'\{[0-9a-f]{2}\}|\\n', '', ko):
            if ch in m or ord(ch) < 0x80:
                continue
            try:
                eb = ch.encode('cp932')
            except UnicodeEncodeError:
                err.append('SJIS 에 없는 글자 %r' % ch); continue
            if len(eb) == 1:                                      # 반각 가타카나 등 1바이트 글자(EXE 원문에 있음)
                continue
            c = struct.unpack('>H', eb)[0]
            if c not in fcodes or c in m.values():
                err.append('글꼴에 없거나 한글 칸으로 덮인 글자 %r' % ch)
    # --- 2) 대사 ------------------------------------------------------------------------------------
    msg = data['/MESSAGE.DAT']
    bl = kr12.blocks(bytes(msg))
    by = {}
    for rid, n, jp, ko in msg_rows:
        if done((rid, n, jp, ko)):
            b, i = map(int, rid.split(':'))
            by.setdefault(b, {})[i] = (jp, wide(ko))
    n_msg = 0
    for b, tr in sorted(by.items()):
        o, s = bl[b]
        ms = kr12.block_msgs(bytes(msg[o:o + s]))
        for i, (jp, ko) in tr.items():
            if ms[i] != msgcode.encode(jp):
                err.append('대사 %d:%d 원문 불일치' % (b, i)); continue
            ms[i] = msgcode.encode(ko, lambda t: kr12.encode(t, m)); n_msg += 1
        try:
            msg[o:o + s] = kr12.build_block(ms, s)
        except AssertionError as e:
            err.append('대사 블록 %d 넘침 %s' % (b, e)); continue
        if kr12.block_msgs(bytes(msg[o:o + s])) != ms:
            err.append('대사 블록 %d 되읽기 불일치' % b)
    # --- 3) 제자리 문자열 ----------------------------------------------------------------------------
    n_in = 0
    for name, p in INPLACE:
        d = data[p]
        for rid, n, jp, ko in inpl[name]:
            if not done((rid, n, jp, ko)):
                continue
            off = int(rid[1:], 16)
            if bytes(d[off:off + n]) != jp_bytes(jp, name == 'job.tsv'):
                err.append('%s %s 원문 불일치' % (name, rid)); continue
            kb = kr12.encode(ko, m)                               # job.tsv 는 «\n» → 'n'(원문 줄바꿈), EXE 쪽 'n' 은 원문 표기 그대로
            if len(kb) > n:
                err.append('%s %s 예산 %d < %d: %s' % (name, rid, n, len(kb), ko)); continue
            d[off:off + n] = kb + bytes(n - len(kb))
            n_in += 1
    # --- 4) 그림 -----------------------------------------------------------------------------------
    grp = data['/GRP.BIN']
    plates.build(grp, np.load(os.path.join(ROOT, 'work', 'kr', 'plate_bld_clut.npy')))
    towntitles.build(grp)
    cityplates.build(grp)
    mb = np.frombuffer(bytes(grp[datebox.OFF:datebox.OFF + datebox.W * datebox.H]), np.uint8).reshape(datebox.H, datebox.W)
    grp[datebox.OFF:datebox.OFF + datebox.W * datebox.H] = datebox.rebuild(mb, np.load(os.path.join(ROOT, 'work', 'kr', 'map_clut.npy'))).tobytes()

    for e in err[:60]:
        print('⛔', e)
    print('음절 %d · 대사 %d/%d · 제자리 %d · 오류 %d' % (len(m), n_msg, len(msg_rows), n_in, len(err)))
    if err:
        raise SystemExit('오류 — 빌드 안 함')
    if '--write' not in sys.argv:
        print('예행 끝 — 쓰려면 --write'); return
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    shutil.copyfile(SRC, OUT)
    n = 0
    with open(OUT, 'r+b') as fh:
        for p, d in data.items():
            l, _ = fs[p]
            for k in range(0, len(d), 2048):
                if d[k:k + 2048] != orig[p][k:k + 2048]:
                    pos = (l + k // 2048) * discfs.RAW
                    fh.seek(pos); sec = bytearray(fh.read(discfs.RAW))
                    chunk = d[k:k + 2048]
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
