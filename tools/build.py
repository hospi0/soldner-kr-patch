# -*- coding: utf-8 -*-
r"""젤드너실트 스페셜 한글판 빌더 — work/text/*.tsv 번역(KO 열) 전부 → 디스크 이미지
  python tools/build.py                 예행(검사만)
  python tools/build.py --write [--install]

  1) 글꼴 FONT12.BIN : 번역에 쓰인 한글 음절 → 한자 칸을 빌려 12×12 로 덮음(tools/kr12.py, 배정 work/kr/charmap.tsv 이어받음).
     «아직 번역 안 된 줄»의 원문 글자 칸은 빌리지 않는다(부분 빌드에서도 원문이 멀쩡하게).
  2) 대사 MESSAGE.DAT(msg.tsv) : 블록마다 문장을 새로 짜고, 블록들을 파일 안에서 다시 배치(머리 표 오프셋·크기 고침, 파일 크기 그대로).
     {xx}·\n 밖의 반각 영문·기호는 전각으로(소문자는 제어 글자), 반각 공백은 1바이트 그대로(8px 빈칸). 토큰은 tools/tokcheck.py 로 검사.
  3) 실행 파일 SLPS_013.19(exe.tsv) · JOBDATA(job.tsv) · BEVENT(bevent.tsv) · SCENARIO(scenario.tsv) : 제자리, 원문 바이트 이내, 남는 자리 NUL.
     ★인물 이름표는 EXE 쪽 인물 표를 쓴다(SCENARIO 는 사본) — 두 곳 다 번역할 것.
  4) 그림 GRP.BIN : 건물 표지(plates) · 도시 제목 20장(towntitles) · 도시 이름 판(cityplates) · 연월 상자(datebox).
  kana.tsv(반각 가타카나 이름)는 제자리 2바이트 한글, 칸을 넘으면 반각→전각 변환 표 칸을 음절에 배정해 1바이트로(전량 번역 때만).
"""
import hashlib, os, re, shutil, struct, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import kr12, discfs, plates, towntitles, cityplates, datebox, msgcode, cdecc, tokcheck, kbd, linefit, battlewords
from cdsector import fix_sector

SRC = r'C:\claude\roms\ps\Soldnerschild Special (Japan)\Soldnerschild Special (Japan).bin'
CUE = SRC[:-4] + '.cue'
OUT = os.path.join(ROOT, 'work', 'out', os.path.basename(SRC))
INSTALL = r'F:\hospi\roms\ps roms\Soldnerschild Special (Japan)'
TXT = os.path.join(ROOT, 'work', 'text')
if '--text' in sys.argv:                                        # 시험용 번역 폴더
    TXT = sys.argv[sys.argv.index('--text') + 1]
INPLACE = [('exe.tsv', '/SLPS_013.19'), ('job.tsv', '/JOBDATA.DAT'), ('bevent.tsv', '/BEVENT.DAT'), ('scenario.tsv', '/SCENARIO.DAT'),
           ('kana.tsv', '/SLPS_013.19')]          # 반각 이름: 예산 = 같은 표 원문 최장(원문 뒤는 0 이어야), 한글은 2바이트 코드로


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
    """{xx}·\\n 밖의 반각 영숫자·기호 → 전각(반각 공백은 그대로 1바이트)"""
    out = []
    for tok in re.split(r'(\{[a-z](?::[0-9a-f]*)?\}|\{[0-9a-f]{2}\}|\\n)', s):   # 제어 표기(tools/msgcode.py)는 그대로
        if tok.startswith('{') or tok == '\\n':
            out.append(tok)
        else:
            # \ubc18\uac01 \uacf5\ubc31\uc740 \uadf8\ub300\ub85c 1\ubc14\uc774\ud2b8: \ub80c\ub354\ub7ec(0x80015664)\uac00 0x20 \uc744 8px \ube48\uce78(\uc791\uc740 \uae00\uaf34 10\ubc88)\uc73c\ub85c \uadf8\ub9b0\ub2e4 \u2014 EXE \ud654\uba74 \uae00({20})\uc774 \uc774\ubbf8 \uc4f4\ub2e4.
            #   \uc804\uac01\uc73c\ub85c \ubc14\uafb8\uba74 MESSAGE.DAT \uac00 11\uc139\ud130 \ub118\uce5c\ub2e4(\ub744\uc5b4\uc4f0\uae30 77,417\uac1c, 2026-09-26).
            out.append(''.join(' ' if ch == ' ' else (chr(ord(ch) + 0xFEE0) if '!' <= ch <= '~' else ch) for ch in tok.replace('·', '・')))   # 가운뎃점(SJIS 에 없음) → ・
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
    names = ['/MESSAGE.DAT', '/FONT12.BIN', '/GRP.BIN', '/BATTLE.GRP', '/MARCH.GRP'] + [p for _, p in INPLACE]
    with open(SRC, 'rb') as f:
        data = {p: bytearray(discfs.sector(f, fs[p][0], (fs[p][1] + 2047) // 2048)[:fs[p][1]]) for p in names}
    orig = {p: bytes(d) for p, d in data.items()}
    err = []
    msg_rows = load_tsv('msg.tsv')
    inpl = {name: load_tsv(name) for name, _ in INPLACE}
    done = lambda r: r[3] and r[3] != '='
    # ★원문 토큰 손상 검사(tools/tokcheck.py) — 이 게임 문제는 대개 여기서 온다. 걸리면 그 줄은 넣지 않고 빌드를 막는다.
    for name, rows in [('msg.tsv', msg_rows)] + list(inpl.items()):
        for r in rows:
            if done(r):
                err += ['%s %s %s' % (name, r[0], e) for e in tokcheck.check(name, r[2], r[3])]
    # --- 1) 글꼴 -----------------------------------------------------------------------------------
    all_ko = [wide(r[3]) for r in msg_rows if done(r)] + [r[3] for rows in inpl.values() for r in rows if done(r)]
    sylls = sorted({c for ko in all_ko + [kbd.SYL] for c in ko if '가' <= c <= '힣'})   # 이름 입력판 음절도(tools/kbd.py)
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
    # 줄 맞춤(tools/linefit.py): 이름 끼움 {a:xxxx} 폭 = EXE 인물 표(0xB7D48 + 번호×21) 번역 이름, 주인공(0000)은 한글 6자로 잡는다
    names = {0: 72}
    for rid, n, jp, ko in inpl['exe.tsv']:
        k, r = divmod(int(rid[1:], 16) - 0xB7D48, 21)
        if done((rid, n, jp, ko)) and r == 0 and 0 < k < 256:
            names[k] = linefit.width(wide(ko))
    jpof = {rid: jp for rid, n, jp, ko in msg_rows}
    texts = {rid: wide(ko) for rid, n, jp, ko in msg_rows if done((rid, n, jp, ko))}
    lim_of = lambda rid: 156 if rid.startswith('20:') and '{z}' not in jpof[rid] else 232   # 인물 소개 창 / 대사창
    fitted, fitw = linefit.fit_all(texts, lim_of, names)          # {j} 이어 쓰기 사슬은 한 흐름으로
    for rid, ko2 in fitted.items():
        b, i = map(int, rid.split(':'))
        by.setdefault(b, {})[i] = (jpof[rid], ko2)
    print('줄 맞춤 경고 %d' % len(fitw))
    for x in fitw[:15]:
        print('  ⚠', x)
    # 블록은 파일 안에서 다시 배치한다: 머리 표(u32 BE 오프셋·크기 × 151)는 파일에서 읽힌다(EXE 에 표 사본·LBA 없음).
    #   블록 크기 = 내용을 2048 로 올림(원본도 전부 2048 배수·2048 정렬). 파일 크기는 그대로(뒤에 MEVENT.DAT 가 붙어 있다),
    #   한 블록 최대 = 원본 최대 40,960(읽기 버퍼가 그만큼은 된다).
    SEC, BMAX = 2048, max(s for _, s in bl)
    n_msg = 0
    newb = []
    for b, (o, s) in enumerate(bl):
        tr = by.get(b)
        if not tr:
            newb.append(bytes(msg[o:o + s]).rstrip(b'\x00')); continue
        ms = kr12.block_msgs(bytes(msg[o:o + s]))
        for i, (jp, ko) in tr.items():
            if ms[i] != msgcode.encode(jp):
                err.append('대사 %d:%d 원문 불일치' % (b, i)); continue
            kb = msgcode.encode(ko, lambda t: kr12.encode(t, m))
            if tokcheck.TOK_MSG.findall(msgcode.decode(kb)) != tokcheck.TOK_MSG.findall(jp):   # 바이트로 되읽어도 토큰이 같은가(한글 칸 바이트가 제어로 읽히지 않는가)
                err.append('대사 %d:%d 인코딩 후 토큰 어긋남' % (b, i)); continue
            ms[i] = kb; n_msg += 1
        nb = kr12.build_block(ms, 1 << 16)[:2 + 2 * len(ms) + sum(map(len, ms))]
        if kr12.block_msgs(nb) != ms:
            err.append('대사 블록 %d 되읽기 불일치' % b)
        if len(nb) > BMAX:
            err.append('대사 블록 %d 가 원본 최대 블록(%d)보다 크다 %d' % (b, BMAX, len(nb)))
        newb.append(nb)
    pos, tbl = SEC, bytearray()
    body = bytearray(len(msg))
    for b, nb in enumerate(newb):
        sz = max(SEC, -(-len(nb) // SEC) * SEC)
        tbl += struct.pack('>II', pos, sz)
        if pos + sz <= len(body):
            body[pos:pos + len(nb)] = nb
        pos += sz
    if pos > len(msg):
        err.append('MESSAGE.DAT 넘침 %d > %d (%d섹터 초과)' % (pos, len(msg), (pos - len(msg)) // SEC))
    else:
        body[:len(tbl)] = tbl
        body[len(tbl):SEC] = msg[len(tbl):SEC]
        msg[:] = body
        print('MESSAGE.DAT 재배치: %d / %d 섹터 사용' % (pos // SEC, len(msg) // SEC))
    # --- 3) 제자리 문자열 ----------------------------------------------------------------------------
    # 반각 이름(kana.tsv)이 2바이트로 예산을 넘으면(도시 표 8바이트 등) 반각→전각 표(EXE 0xB23F8 = 0xA6‥0xDD, u16 LE)의
    # 칸을 그 음절에 배정해 1바이트로 쓴다. ★반각 이름이 «전부» 번역됐을 때만(아니면 원문 반각 이름이 엉뚱한 글자로 나온다).
    #   2바이트 한글이 반각 이름 자리에서 그려지는 것은 실기 확인(2026-09-26 상태 화면 «소드엘리트·메가힐링»).
    HALF_TBL, HIRA_TBL = 0xB23F8, 0xB2354          # 가타카나판(RAM 0x800C1BF8) · 히라가나판(0x800C1B54), 색인 = 바이트 − 0xA6
    kana_rows = inpl['kana.tsv']
    half = {}
    if kana_rows and all(done(r) for r in kana_rows):
        need = []
        for r in kana_rows:
            if len(kr12.encode(r[3], m)) > r[1]:
                for ch in r[3]:
                    if ch in m and ch not in need:
                        need.append(ch)
        if len(need) > 0xDD - 0xA6 + 1:
            err.append('반각 칸 부족 %d음절' % len(need))
        half = {ch: bytes([0xA6 + i]) for i, ch in enumerate(need[:0xDD - 0xA6 + 1])}
        exe = data['/SLPS_013.19']
        for ch, b in half.items():
            for tb in (HALF_TBL, HIRA_TBL):
                struct.pack_into('<H', exe, tb + (b[0] - 0xA6) * 2, m[ch])
        if half:
            print('반각 칸 배정 %d음절: %s' % (len(half), ''.join(half)))

    def enc_kana(ko, n):
        kb = kr12.encode(ko, m)
        if len(kb) <= n or not half:
            return kb
        return b''.join(half[ch] if ch in half else kr12.encode(ch, m) for ch in ko)   # 넘칠 때만 1바이트 칸으로
    n_in = 0
    for name, p in INPLACE:
        d = data[p]
        for rid, n, jp, ko in inpl[name]:
            if not done((rid, n, jp, ko)):
                continue
            off = int(rid[1:], 16)
            jb = jp_bytes(jp, name == 'job.tsv')
            if bytes(d[off:off + len(jb)]) != jb or any(orig[p][off + len(jb):off + n]):
                err.append('%s %s 원문 불일치(또는 예산 안에 0 아닌 바이트)' % (name, rid)); continue
            kb = enc_kana(ko, n) if name == 'kana.tsv' else kr12.encode(ko, m)   # job.tsv 는 «\n» → 'n'(원문 줄바꿈), EXE 쪽 'n' 은 원문 표기 그대로
            if len(kb) > n:
                err.append('%s %s 예산 %d < %d: %s' % (name, rid, n, len(kb), ko)); continue
            d[off:off + n] = kb + bytes(n - len(kb))
            n_in += 1
    e = kbd.patch(data['/SLPS_013.19'], m)                        # 이름 입력판 한글(0xB13D8, 96칸)
    if e:
        err.append(e)
    # --- 4) 그림 -----------------------------------------------------------------------------------
    grp = data['/GRP.BIN']
    plates.build(grp, np.load(os.path.join(ROOT, 'work', 'kr', 'plate_bld_clut.npy')))
    towntitles.build(grp)
    cityplates.build(grp)
    mb = np.frombuffer(bytes(grp[datebox.OFF:datebox.OFF + datebox.W * datebox.H]), np.uint8).reshape(datebox.H, datebox.W)
    grp[datebox.OFF:datebox.OFF + datebox.W * datebox.H] = datebox.rebuild(mb, np.load(os.path.join(ROOT, 'work', 'kr', 'map_clut.npy'))).tobytes()
    battlewords.build_events(grp)                                  # 이달의 사건(GRP.BIN 8bpp)
    battlewords.build(data['/BATTLE.GRP'])                         # 전투 결과 무승부·승리·패배(세 벌)
    battlewords.build_turn(data['/MARCH.GRP'], test='--turntest' in sys.argv)   # 턴 표시(--turntest = 색 시험판)
    battlewords.build_mission8(data['/MARCH.GRP'])                  # 임무 달성!·임무 실패...(8bpp)

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
        # --- 5) 오프닝 자막 동영상(tools/opsub.py build → work/movie/kr/ZZOP.STR) — 원래 자리, 원본 섹터 수 안 ---
        #   ★★킹스 필드 3 방식(실기 2026-09-26 «오프닝 끝나고 크래시»): 채움 섹터를 EOF 뒤에 몰면 끝까지 재생했을 때 죽는다.
        #   → 채움(01 00 00 00)을 «끝에서 8섹터마다»(소리 자리) 흩어 넣어 마지막 섹터 = 데이터+EOF(원본도 마지막 섹터가 EOF).
        #   프레임 수는 opsub.py 가 원본(2,723)에 맞춘다. MSF·EDC/ECC 는 절대 위치로 다시.
        mv = os.path.join(ROOT, 'work', 'movie', 'kr', 'ZZOP.STR')
        if os.path.exists(mv):
            lba, size = fs['/ZZOP.STR']
            orig_n = (size + 2047) // 2048
            new = open(mv, 'rb').read()
            new_n = len(new) // 2352
            need = orig_n - new_n
            assert 0 <= need and need * 8 < orig_n, ('오프닝 섹터 수', new_n, orig_n)
            holes = {orig_n - 1 - 8 * k for k in range(1, need + 1)}          # 마지막 섹터는 비우지 않는다
            di = 0
            for i in range(orig_n):
                if i in holes:
                    s = bytearray(2352); s[0:12] = b'\x00' + b'\xff' * 10 + b'\x00'
                    s[16:24] = bytes([1, 0, 0, 0, 1, 0, 0, 0])                # 원본 채움 꼴
                else:
                    s = bytearray(new[di * 2352:(di + 1) * 2352])
                    if di == new_n - 1:
                        s[18] |= 0x80; s[22] |= 0x80
                    else:
                        s[18] &= ~0x80; s[22] &= ~0x80
                    di += 1
                cdecc.fix_any(s, lba + i)
                fh.seek((lba + i) * 2352); fh.write(s)
            assert di == new_n
            print('오프닝 자막 동영상 %d 섹터 + 채움 %d(끝에서 8섹터마다) = %d, 마지막 = 데이터+EOF' % (new_n, need, orig_n))
    h = hashlib.md5(open(OUT, 'rb').read()).hexdigest().upper()
    print('섹터 %d개 · %s md5 %s' % (n, OUT, h))
    if '--install' in sys.argv:
        os.makedirs(INSTALL, exist_ok=True)
        shutil.copyfile(OUT, os.path.join(INSTALL, os.path.basename(OUT)))
        shutil.copyfile(CUE, os.path.join(INSTALL, os.path.basename(CUE)))
        print('설치', INSTALL)


if __name__ == '__main__':
    main()
