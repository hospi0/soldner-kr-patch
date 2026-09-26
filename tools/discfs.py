# -*- coding: utf-8 -*-
"""MODE2/2352 CD 이미지(PS2 CD-ROM)의 ISO9660 파일시스템을 읽는다.

  python tools/discfs.py <bin>                 # 파일 목록
  python tools/discfs.py <bin> --get /X.Y <출력>
  python tools/discfs.py <bin> --grep 패턴

## 섹터 배치 (실측 Theme Park Roller Coaster (USA))
```
2352 B/섹터 = SYNC 12 + 헤더 4 + 서브헤더 8 + 사용자 2048 + EDC/ECC 280
254,774섹터 · 단일 트랙 MODE2/2352 (.cue 선언과 일치)
```
⛔ 2048 단위로 읽으면 안 된다 — 사용자 데이터는 각 섹터의 +24 에 있다.
"""
import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdsector import fix_sector

RAW, OFF, USER = 2352, 24, 2048


def sector(f, lba, n=1):
    out = []
    for i in range(n):
        f.seek((lba + i) * RAW + OFF)
        out.append(f.read(USER))
    return b''.join(out)


def both32(b, p):
    """ISO9660 은 LE·BE 를 «둘 다» 적어 둔다. LE 만 읽되 BE 와 어긋나면 알린다."""
    le, be = struct.unpack_from('<I', b, p)[0], struct.unpack_from('>I', b, p + 4)[0]
    if le != be:
        print('  ⚠️ both-endian 불일치 %d != %d' % (le, be), file=sys.stderr)
    return le


def records(data):
    p = 0
    while p < len(data):
        ln = data[p]
        if ln == 0:
            p = (p // USER + 1) * USER          # 다음 논리 블록으로
            if p >= len(data):
                break
            continue
        r = data[p:p + ln]
        lba = both32(r, 2)
        size = both32(r, 10)
        flags = r[25]
        nlen = r[32]
        name = r[33:33 + nlen].decode('latin1')
        yield name, lba, size, flags
        p += ln


def walk(f, lba, size, base='', depth=0, out=None):
    if out is None:
        out = []
    data = sector(f, lba, (size + USER - 1) // USER)
    for name, l, s, fl in records(data):
        if name in ('\x00', '\x01'):
            continue
        nm = name.split(';')[0]
        path = base + '/' + nm
        if fl & 2:
            if depth < 8:
                walk(f, l, s, path, depth + 1, out)
        else:
            out.append((path, l, s))
    return out


def read_fs(path):
    f = open(path, 'rb')
    pvd = sector(f, 16)
    if pvd[1:6] != b'CD001':
        raise SystemExit('⛔ PVD 가 아니다 (16번 섹터 %r)' % pvd[:8])
    vol = pvd[40:72].decode('latin1').strip()
    root = pvd[156:190]
    rl, rs = both32(root, 2), both32(root, 10)
    return f, vol, rl, rs, walk(f, rl, rs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('bin')
    ap.add_argument('--get', nargs=2, metavar=('경로', '출력'))
    ap.add_argument('--put', nargs=2, metavar=('경로', '입력'),
                    help='«같은 크기»로 제자리 교체. 섹터 EDC/ECC 를 다시 계산한다')
    ap.add_argument('--grep', default='')
    ap.add_argument('--out', help='전부 이 폴더로 뽑기')
    a = ap.parse_args()
    f, vol, rl, rs, files = read_fs(a.bin)

    have = [p.lower() for p, l, s in files]

    def norm(q):
        # ⛔ Git Bash 가 /AUDIO/... 를 C:/Program Files/Git/AUDIO/... 로 바꿔 버린다.
        #    그래서 «뒤에서부터» 실제 파일 경로와 맞는 가장 긴 꼬리를 찾는다.
        #    (끝의 두 칸만 보던 옛 방식은 /A/B/C/D.EXT 같은 깊은 경로에서 안 맞았다)
        parts = q.replace(chr(92), '/').strip('/').split('/')
        for k in range(len(parts)):
            cand = '/' + '/'.join(parts[k:])
            if cand.lower() in have:
                return cand
        return q

    if a.get:
        a.get = [norm(a.get[0]), a.get[1]]
    if a.put:
        a.put = [norm(a.put[0]), a.put[1]]
    if a.get:
        for p, l, s in files:
            if p.lower() == a.get[0].lower():
                open(a.get[1], 'wb').write(sector(f, l, (s + USER - 1) // USER)[:s])
                print('✅ %s  %d B (LBA %d)' % (a.get[1], s, l))
                return
        raise SystemExit('⛔ 없다: %s' % a.get[0])
    if a.put:
        want, src = a.put
        blob = open(src, 'rb').read()
        for pth, l, sz in files:
            if pth.lower() != want.lower():
                continue
            if len(blob) != sz:
                raise SystemExit('⛔ 크기가 다르다 — 원본 %d B, 넣으려는 것 %d B. '
                                 '크기가 바뀌면 LBA 재배치가 필요하다(아직 미구현).'
                                 % (sz, len(blob)))
            n = (sz + USER - 1) // USER
            g = open(a.bin, 'r+b')
            for k in range(n):
                g.seek((l + k) * RAW)
                sec = bytearray(g.read(RAW))
                chunk = blob[k * USER:(k + 1) * USER]
                sec[OFF:OFF + USER] = chunk + bytes(USER - len(chunk))
                fix_sector(sec)
                g.seek((l + k) * RAW)
                g.write(sec)
            g.close()
            print('  ✅ %s  %d B · 섹터 %d개 (LBA %d~) · EDC/ECC 재계산' % (pth, sz, n, l))
            return
        raise SystemExit('⛔ 없다: %s' % want)
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        for p, l, s in files:
            q = os.path.join(a.out, p.strip('/').replace('/', '_'))
            open(q, 'wb').write(sector(f, l, (s + USER - 1) // USER)[:s])
        print('✅ %d개 뽑음 → %s' % (len(files), a.out))
        return
    print('볼륨 %r · 루트 LBA %d · 파일 %d개' % (vol, rl, len(files)))
    tot = 0
    for p, l, s in sorted(files, key=lambda x: -x[2]):
        if a.grep and a.grep.lower() not in p.lower():
            continue
        print('  %-44s LBA %7d  %10d B' % (p, l, s))
        tot += s
    print('합계 %d B (%.1f MB)' % (tot, tot / 1e6))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')   # ⛔cp949 콘솔에서 ✅ 하나에 빌드가 죽는다
    main()
