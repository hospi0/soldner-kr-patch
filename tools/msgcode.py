# -*- coding: utf-8 -*-
r"""MESSAGE.DAT 제어 글자 문법(통계로 확정, 2026-09-26) — 표기 ↔ 바이트
  인수 없음 : z(문장 머리) g(대기·끝) u(끝) n(줄바꿈) w(대기) f o d
  1바이트 인수: c(글자색) b(숫자 끼워 넣기) p
  2바이트 인수: s(이름표) l(얼굴) v(음성 번호) a j
  5바이트 인수: y(예/아니요 — 00 + 이동할 문장 번호 u16 BE × 2)
  그 밖 반각(숫자 0‥9·기호)은 글자 그대로(대사 속 «500Ｇ» 등). 00 은 문장 끝.
  표기: 제어 = {z} {g} {c:05} {s:0320} … , 줄바꿈 = \n, 반각 글자 그대로, 전각 SJIS 그대로.
  ★인수 바이트가 SJIS 앞 바이트 범위라도 글자로 짝짓지 않는다(이전 추출은 1,800줄가량을 한자로 잘못 읽었다).
"""
import re

ARGS = {'z': 0, 'g': 0, 'u': 0, 'f': 0, 'o': 0, 'd': 0, 'w': 0,
        'c': 1, 'b': 1, 'p': 1,
        's': 2, 'l': 2, 'v': 2, 'a': 2, 'j': 2, 'y': 5}


def decode(b):
    """바이트 → 표기. 풀리지 않는 바이트는 {xx}"""
    out, i = [], 0
    while i < len(b):
        x = b[i]
        ch = chr(x)
        if ch == 'n':
            out.append('\\n'); i += 1
        elif ch in ARGS:
            k = ARGS[ch]
            if k == 0:
                out.append('{%s}' % ch)
            else:
                out.append('{%s:%s}' % (ch, b[i + 1:i + 1 + k].hex()))
            i += 1 + k
        elif 0x81 <= x <= 0x9f or 0xe0 <= x <= 0xef:
            c = b[i:i + 2].decode('cp932', 'replace')
            if len(c) == 1 and c != '�' and c.encode('cp932', 'replace') == b[i:i + 2]:
                out.append(c); i += 2
            else:
                out.append('{%02x}' % x); i += 1
        elif 0x20 <= x <= 0x7e and ch not in '{}\\':
            out.append(ch); i += 1
        else:
            out.append('{%02x}' % x); i += 1
    return ''.join(out)


TOK = re.compile(r'\{([a-z]):([0-9a-f]*)\}|\{([a-z])\}|\{([0-9a-f]{2})\}|(\\n)')


def encode(s, conv=None):
    """표기 → 바이트. conv(글자열) → 바이트 (한글 등 글자 부분 변환, 기본 cp932)"""
    conv = conv or (lambda t: t.encode('cp932'))
    out = bytearray()
    pos = 0
    for m in TOK.finditer(s):
        if m.start() > pos:
            out += conv(s[pos:m.start()])
        if m.group(1):
            out += m.group(1).encode() + bytes.fromhex(m.group(2))
        elif m.group(3):
            out += m.group(3).encode()
        elif m.group(4):
            out.append(int(m.group(4), 16))
        else:
            out += b'n'
        pos = m.end()
    if pos < len(s):
        out += conv(s[pos:])
    return bytes(out)
