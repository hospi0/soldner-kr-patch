# -*- coding: utf-8 -*-
r"""대사 줄 맞춤 — 엔진 자동 줄바꿈이 낱말 한복판을 자르지 않게, 빌더가 띄어쓰기 자리에 \n 을 넣는다.
  폭(렌더러 0x80015664 · 창 레지스터 gp+0xE20/0xE24): 전각 12px, 반각(공백·숫자) 8px, 제어 표기 0.
    대사창: 줄 시작 x 40, 한계 x 272 → 한 줄 232px 초과 시 엔진이 자동으로 줄을 바꾼다
            (세이브스테이트 + 실기 스샷 «…지휘관의 기본이|다» 244px 에서 넘어감, 2026-09-26).
    인물 소개(블록 20, {z} 없는 글): 실기 스샷 «…가희. 전쟁|으로» → 156px.
  줄 수: 대사창 3줄, 이름표({s:…})가 있는 쪽은 2줄. 쪽 경계 = {g} {u} {z}. {j} 이어 쓰기 사슬은 fit_all 이 한 흐름으로.
  ① 넘치는 줄만 마지막 띄어쓰기에서 나눈다 → ② 그래도 쪽 줄 수를 넘으면 그 쪽 전체를 다시 채운다 → ③ 그래도 넘치면 경고.
"""
import re

TOK = re.compile(r'(\{[a-z](?::[0-9a-f]*)?\}|\{[0-9a-f]{2}\}|\\n)')
PAGE = re.compile(r'(\{g\}|\{u\}|\{z\})')      # 문장 가운데 {z} 도 새 쪽(«…참이라네{w}{w}{w}{z}그래서…»)


def width(s, names=None):
    w = 0
    for t in TOK.split(s):
        if not t:
            continue
        if t.startswith('{'):
            m = re.fullmatch(r'\{a:([0-9a-f]{4})\}', t)
            if m:
                w += (names or {}).get(int(m.group(1), 16), 72)
            elif t.startswith('{b:'):
                w += 40                                   # 숫자 끼움(반각 5자리)
            continue
        w += sum(8 if ord(c) < 0x80 else 12 for c in t)
    return w


def wrap_line(line, lim, names):
    """한 줄을 lim 안으로 — 띄어쓰기에서만 자른다"""
    out = []
    while width(line, names) > lim:
        cut = None
        for m in re.finditer(r' ', line):
            if width(line[:m.start()], names) <= lim:
                cut = m.start()
            else:
                break
        if cut is None:
            break                                          # 띄어쓰기 없는 긴 낱말 — 그대로(경고)
        out.append(line[:cut]); line = line[cut + 1:]
    out.append(line)
    return out


def fit_all(texts, lim_of, names=None):
    """texts: {'블록:문장': 번역문(wide 거침)}. {j:XXXX}{00} 로 끝나고 대상 문장이 {z} 로 시작하지 않으면 대상은 «같은 줄에 이어»
    나온다(실기 21:70→21:71). 그런 사슬은 이어 붙여 한 흐름으로 맞춘 뒤 다시 문장별로 나눈다(표지 {q} 는 폭 0).
    lim_of(id) → 줄 폭. 반환 (맞춘 번역문 dict, 경고 목록)"""
    JE = re.compile(r'\{j:([0-9a-f]{4})\}\{00\}$')
    nxt, srcs = {}, {}
    for rid, t in texts.items():
        m = JE.search(t)
        if m:
            b = rid.split(':')[0]
            tg = '%s:%d' % (b, int(m.group(1), 16))
            if tg in texts and not texts[tg].startswith('{z}'):
                nxt[rid] = tg
                srcs.setdefault(tg, []).append(rid)
    shared = {tg for tg, s in srcs.items() if len(s) > 1}      # 두 곳에서 이어지는 문장(2개) — 사슬로 묶지 않는다
    out, warn = {}, []
    for rid in texts:
        if rid in srcs and rid not in shared:
            continue                                          # 사슬 가운데 — 머리에서 처리
        chain = [rid]
        while chain[-1] in nxt and nxt[chain[-1]] not in shared and nxt[chain[-1]] not in chain:
            chain.append(nxt[chain[-1]])
        tails = []
        parts = []
        for k, c in enumerate(chain):
            t = texts[c]
            if k < len(chain) - 1:
                m = JE.search(t)
                tails.append(m.group(0)); t = t[:m.start()]
            parts.append(t)
        joined = '{q}'.join(parts)
        fitted, w = fit(joined, lim_of(rid), names)
        warn += ['%s %s' % (rid, x) for x in w]
        pieces = fitted.split('{q}')
        assert len(pieces) == len(chain), (rid, chain)
        for k, c in enumerate(chain):
            out[c] = pieces[k] + (tails[k] if k < len(tails) else '')
    return out, warn


BTN = 12      # 대사창 셋째 줄(창 맨 아래 줄) 오른쪽 끝에 ○ 버튼 그림 — 한 글자 덜 쓴다(사용자 2026-09-26)


def wrap_seq(line, lim_at, i0, names):
    """한 줄을 i0 번째 줄부터 줄마다 lim_at(i) 안으로 — 띄어쓰기에서만 자른다"""
    out = []
    while width(line, names) > lim_at(i0 + len(out)):
        cut = None
        for m in re.finditer(r' ', line):
            if width(line[:m.start()], names) <= lim_at(i0 + len(out)):
                cut = m.start()
            else:
                break
        if cut is None:
            break                                          # 띄어쓰기 없는 긴 낱말 — 그대로(경고)
        out.append(line[:cut]); line = line[cut + 1:]
    out.append(line)
    return out


def fit(ko, lim, names=None):
    """ko: wide() 거친 번역문. 반환 (새 번역문, 경고 목록)"""
    warn = []
    parts = PAGE.split(ko)
    for k in range(0, len(parts), 2):
        page = parts[k]
        maxl = 2 if re.search(r'\{s:[0-9a-f]{4}\}', page) else 3
        box = lim >= 200                                   # 대사창(인물 소개 창은 줄 수·버튼 없음)
        lim_at = (lambda i: lim - BTN if i >= maxl - 1 else lim) if box else (lambda i: lim)
        lines = page.split('\\n')
        if all(width(l, names) <= lim_at(i) for i, l in enumerate(lines)):
            continue
        new = []
        for l in lines:
            new += wrap_seq(l, lim_at, len(new), names)
        while len(new) > maxl and box:                     # ②-1 이웃한 두 줄 합치기(합친 폭이 가장 좁은 쌍부터) — 번역자 줄 나눔을 살린다
            pairs = [(width(new[j] + ' ' + new[j + 1], names), j) for j in range(len(new) - 1)]
            pairs = [p for p in pairs if p[0] <= lim_at(p[1])]
            if not pairs:
                break
            j = min(pairs)[1]
            new[j:j + 2] = [new[j] + ' ' + new[j + 1]]
        if box and (len(new) > maxl or any(width(l, names) > lim_at(i) for i, l in enumerate(new))):
            new = wrap_seq(' '.join(lines), lim_at, 0, names)   # ②-2 쪽 전체 다시 채우기
        if any(width(l, names) > lim_at(i) for i, l in enumerate(new)):
            warn.append('줄 폭 넘침 ' + page[:40])
        if len(new) > maxl and box:
            warn.append('쪽 줄 수 %d > %d ' % (len(new), maxl) + page[:40])
        parts[k] = '\\n'.join(new)
    return ''.join(parts), warn
