# -*- coding: utf-8 -*-
r"""이름 입력판(주인공 이름) 한글 글자판 — EXE 0xB13D8(RAM 0x800C0BD8), 칸 = SJIS 2바이트 + NUL, 6줄 × 16칸 = 96칸
  원본: 가타카나 5·5·5 + 기호 1 열 (アイウエオ マミムメモ ザジズゼゾ ヴ / … / ハヒフヘホ ガギグゲゴ ５６７８９ 　).
  한글: 95음절(자음 순) + 마지막 칸 전각 공백(띄어쓰기) 그대로. 하·스·피 · 아인 · 슈타인돌프 음절 포함.
  글꼴: build.py 가 이 음절들을 번역 음절과 함께 FONT12 한자 칸에 넣는다.
"""
OFF, N = 0xB13D8, 96
ORIG = ('アイウエオマミムメモザジズゼゾヴ'
        'カキクケコヤユヨワヲダヂヅデドー'
        'サシスセソラリルレロバビブベボ・'
        'タチツテトンッャュョパピプペポ＝'
        'ナニヌネノァィゥェォ０１２３４世'
        'ハヒフヘホガギグゲゴ５６７８９　')
SYL = ('가거고구그기길김'
       '나너노누니'
       '다더도두드디돌'
       '라러로루르리린'
       '마머모무미민'
       '바버보부브비'
       '사서소수스시성세슈'
       '아어오우으이인안연영윤은유에'
       '자저조주지준진제'
       '차초치'
       '카커코쿠크키'
       '타터토트티'
       '파포프피'
       '하허호후히한현')
KR = SYL + '　'
assert len(ORIG) == N and len(KR) == N and len(set(SYL)) == len(SYL), (len(ORIG), len(KR))


def patch(exe, m):
    """exe: bytearray(EXE 파일), m: 음절 → 빌린 SJIS 코드. 원문이 다르면 오류 문자열"""
    for i, ch in enumerate(ORIG):
        p = OFF + 3 * i
        if bytes(exe[p:p + 3]) != ch.encode('cp932') + b'\x00':
            return '이름 입력판 원문 불일치 칸 %d' % i
    for i, ch in enumerate(KR):
        p = OFF + 3 * i
        exe[p:p + 2] = m[ch].to_bytes(2, 'big') if ch in m else ch.encode('cp932')
    return None


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    for r in range(6):
        print(' '.join(KR[r * 16 + k * 5:r * 16 + k * 5 + 5] for k in range(3)), KR[r * 16 + 15])
