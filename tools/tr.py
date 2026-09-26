# -*- coding: utf-8 -*-
r"""번역 칸(KO) 작업 도구 — 할 일 뽑기 · 번역 넣기(검사 + 같은 틀 채우기) · 검사 · 진행률
  python tools/tr.py stat
  python tools/tr.py todo msg [--block 5] [--limit 200]   → 번호 \t 틀(①② = 이어진 제어 표기 묶음) \t 제어
  python tools/tr.py apply msg patch.tsv                  ← 번호 \t 번역(자리표 ①② 또는 제어 표기 그대로)
  python tools/tr.py check [msg exe …]

  자리표: 원문의 이어진 제어 표기({z}{f}{l:00c4}…) 한 덩어리 = ①, 다음 = ② … — 넣을 때 원래 표기로 펼친다.
  검사: 제어 표기 순서·개수 원문과 같음(줄바꿈 \n 은 자유), 가나·한자 남지 않음, 예산 파일은 한글 2 B/자로 예산 이내.
  msg 는 «제어 인수만 다르고 글이 같은» 줄(얼굴·이름표만 다른 같은 대사)에 같은 번역을 함께 넣는다(각자 제어 그대로).
"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXT = os.path.join(ROOT, 'work', 'text')
FILES = ['msg', 'exe', 'kana', 'job', 'bevent', 'scenario']
TOK = r'\{[a-z](?::[0-9a-f]*)?\}|\{[0-9a-f]{2}\}'
RUN = re.compile('(?:%s)+' % TOK)
OKNEXT = set(' \u3000\\…!?！？,.，．、。~～-－―『』「」（）()님경씨의도에한께만하처같조까부대그놈입아인맞형왕군령성')
# {a:xxxx} 이름 끼움 번호 → 번역 이름(대사 문맥으로 확인, 용어집과 같게). 여기 있는 이름은 받침에 맞는 조사를 써도 된다.
# 0000(주인공)은 플레이어가 바꾸므로 없음. EXE 인물 표도 반드시 이 이름으로 번역할 것.
ANAME = {'0001': '아나스타샤', '0002': '류크', '0003': '루이자', '0004': '안토니오', '0005': '길퍼드',
         '0028': '코르테스', '005e': '오즈월드', '002b': '이자벨', '0031': '스마일리', '0066': '페르디난트', '0068': '테레지아',
         '006e': '프랑수아', '0070': '웨인', '0076': '알베르트', '0078': '비앙카', '007e': '빌렘',
         '0086': '프레데리카', '0087': '구스타프', '008e': '이그나티우스', '0090': '프리드룸', '0091': '라슬로',
         '0092': '마르가레테', '0093': '만프리트', '0094': '클로비스', '0095': '조반니', '0096': '로렌초',
         '0097': '에셀발드', '0098': '크리스티나', '0099': '카테리나', '009b': '호킨스', '00a0': '크로토네',
         '00a1': '포이어바흐', '00a2': '로이트가르트', '00a4': '카를', '00a7': '알렉시오스', '00a8': '메리',
         '00a9': '소피아'}
PAIRS = [('이', '가'), ('은', '는'), ('을', '를'), ('과', '와'), ('이야', '야'), ('이라', '라'), ('으로', '로'), ('아', '야'), ('이여', '여'), ('이랑', '랑'), ('이지', '지'), ('이잖', '잖'), ('이군', '군'), ('이냐', '냐'), ('이네', '네'), ('이다', '다'), ('이오', '오'), ('인가', '인가')]


def batchim(w):
    c = w[-1]
    return '가' <= c <= '힣' and (ord(c) - 0xAC00) % 28 != 0


MARKS = [chr(0x2460 + i) for i in range(20)] + [chr(0x3251 + i) for i in range(15)] + [chr(0x32B1 + i) for i in range(15)]


def load(name):
    lines = open(os.path.join(TEXT, name + '.tsv'), encoding='utf-8', newline='').read().split('\n')
    lines = [l.rstrip('\r') for l in lines]
    head, rows = lines[0], [l.split('\t') for l in lines[1:] if l]
    for r in rows:
        while len(r) < 4:
            r.append('')
    return head, rows


def save(name, head, rows):
    with open(os.path.join(TEXT, name + '.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(head + '\n')
        for r in rows:
            f.write('\t'.join(r[:4]) + '\n')


def skel(jp):
    """(틀, 제어 묶음 목록)"""
    runs = RUN.findall(jp)
    it = iter(MARKS)
    return RUN.sub(lambda m: next(it), jp), runs


def expand(ko, runs):
    for k, run in enumerate(runs):
        ko = ko.replace(MARKS[k], run)
    return ko


def to_marks(ko, runs):
    """펼친 번역 → 자리표 번역(같은 틀의 다른 줄에 옮겨 담기용)"""
    out, pos = [], 0
    for k, run in enumerate(runs):
        i = ko.find(run, pos)
        if i < 0:
            return None
        out.append(ko[pos:i] + MARKS[k]); pos = i + len(run)
    return ''.join(out) + ko[pos:]


def hangul_len(s):
    n = 0
    for ch in re.sub(TOK, '', s).replace('\\n', 'n'):
        n += 2 if ('가' <= ch <= '힣' or ord(ch) > 0xff) else 1
    return n + len(re.findall(TOK, s)) + sum(len(x) // 2 - 1 for x in re.findall(r'\{[a-z]:([0-9a-f]*)\}', s))


def problems(name, r):
    rid, bud, jp, ko = r[:4]
    err, warn = [], []
    if not ko or ko == '=':
        return err, warn
    if re.findall(TOK, ko) != re.findall(TOK, jp):
        err.append('제어 표기가 원문과 다름')
    if re.search('[' + ''.join(MARKS) + ']', ko):
        err.append('펼치지 않은 자리표')
    body = re.sub(TOK + r'|\\n', '', ko)
    if name in ('exe', 'kana'):                               # 앞 데이터 바이트가 붙어 뽑힌 줄: 원문과 같은 앞머리는 그대로 둔 것
        body = re.sub(TOK + r'|\\n', '', ko[len(os.path.commonprefix([jp, ko])):])
    for ch in body:
        if '぀' <= ch <= 'ヿ' or '一' <= ch <= '鿿' or '｡' <= ch <= 'ﾟ':
            err.append('일본 글자 남음 %r' % ch); break
    if ',' in body or '，' in body:
        warn.append('쉼표(글꼴 미확인 — 띄어쓰기로)')
    # 이름·낱말 끼움({a:} {p:}) 바로 뒤엔 받침에 따라 바뀌는 조사를 붙이지 않는다(님·의·에게·도·께서 등만)
    for m in re.finditer(r'\{[ap]:([0-9a-f]*)\}(?!\{)(.?)', ko):
        nx = ko[m.end():m.end() + 1]
        nm = ANAME.get(m.group(1)) if m.group(0).startswith('{a') else None
        if nm and m.group(2):
            rest = ko[m.end() - 1:m.end() + 2]
            bad = [b if batchim(nm) else a for a, b in PAIRS if a != b]
            if any(rest.startswith(x) for x in bad) and not any(rest.startswith(y) for y in ('이다', '이니', '이오', '이옵', '이시', '이었', '입')):
                warn.append('%s 뒤 조사 %r' % (nm, rest))
            continue
        if m.group(2) == '이' and nx and nx in '다니오옵시었': # 계사 «이다·이니라·입니다…» 는 받침과 무관
            continue
        if m.group(2) and m.group(2) not in OKNEXT:
            warn.append('끼움 뒤 조사 %r' % ko[m.end() - 1:m.end() + 3])
    if name == 'msg':
        sk = RUN.sub('', jp)
        lim = max(24, max(len(x) for x in sk.split('\\n')))
        if '{z}' not in jp and '\\n' not in jp and len(sk) <= 12:
            lim = 12                                          # 엔딩 서술 조각(12자 칸)
        for x in RUN.sub('\\\\n', ko).split('\\n'):
            if len(x) > lim:
                warn.append('줄 %d자 > %d: %s' % (len(x), lim, x))
    elif name == 'kana':                                      # 반각 1 B, 한글(2바이트 코드) 2 B
        n = sum(2 if '가' <= ch <= '힣' else 1 for ch in re.sub(TOK, '.', ko))
        if n > int(bud):
            err.append('예산 넘침 %d > %s B' % (n, bud))
    else:
        n = hangul_len(ko)
        if n > int(bud):
            err.append('예산 넘침 %d > %s B' % (n, bud))
    return err, warn


def cmd_todo(name, args):
    head, rows = load(name)
    blk = args[args.index('--block') + 1] if '--block' in args else None
    lim = int(args[args.index('--limit') + 1]) if '--limit' in args else 10 ** 9
    done = {skel(r[2])[0] for r in rows if r[3]}
    seen, n = set(), 0
    for r in rows:
        if r[3] or (blk is not None and r[0].split(':')[0] != blk):
            continue
        sk, runs = skel(r[2])
        if sk in done or sk in seen:
            continue
        seen.add(sk)
        print('%s\t%s' % (r[0], sk) + ('\t' + ' '.join('%s%s' % (MARKS[k], x) for k, x in enumerate(runs)) if runs else ''))
        n += 1
        if n >= lim:
            break


def cmd_apply(name, patch):
    head, rows = load(name)
    idx = {r[0]: r for r in rows}
    bysk = {}
    for r in rows:
        bysk.setdefault(skel(r[2])[0], []).append(r)
    bad = n = 0
    for ln in open(patch, encoding='utf-8'):
        ln = ln.rstrip('\r\n')
        if not ln.strip() or ln.startswith('#'):
            continue
        rid, ko = ln.split('\t', 1)
        if rid not in idx:
            print('없는 번호', rid); bad += 1; continue
        r = idx[rid]
        sk, runs = skel(r[2])
        mk = ko if any(m in ko for m in MARKS) else to_marks(ko, runs)
        if mk is None:
            print('✗', rid, '제어 표기 못 찾음 |', ko); bad += 1; continue
        # 엔딩 서술 조각({z} 없는 줄)은 앞뒤 조각과 이어지는 문장이라 같은 원문이라도 따로 번역한다
        targets = bysk[sk] if name == 'msg' and '{z}' in r[2] else [r]
        old = r[3]
        for q in targets:
            if q is not r and q[3] and q[3] != old:
                continue
            new = expand(mk, skel(q[2])[1])
            err, warn = problems(name, q[:3] + [new])
            if err:
                print('✗', q[0], '; '.join(err), '|', new); bad += 1; break
            for w in warn:
                print('△', q[0], w)
            q[3] = new; n += 1
    save(name, head, rows)
    print('넣음 %d줄 · 오류 %d' % (n, bad))


def cmd_check(names):
    for name in names:
        head, rows = load(name)
        ne = nw = 0
        for r in rows:
            err, warn = problems(name, r)
            for e in err:
                print('✗', name, r[0], e); ne += 1
            nw += len(warn)
        print('%s: 오류 %d · 경고 %d' % (name, ne, nw))


def cmd_stat():
    for name in FILES:
        head, rows = load(name)
        t = sum(1 for r in rows if r[3])
        u = {skel(r[2])[0] for r in rows}
        ud = {skel(r[2])[0] for r in rows if r[3]}
        print('%-9s %6d / %6d 줄 (%5.1f%%) · 고유 %d / %d' % (name, t, len(rows), 100 * t / max(1, len(rows)), len(ud), len(u)))


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    a = sys.argv[1:]
    if not a or a[0] == 'stat':
        cmd_stat()
    elif a[0] == 'todo':
        cmd_todo(a[1], a[2:])
    elif a[0] == 'apply':
        cmd_apply(a[1], a[2])
    elif a[0] == 'check':
        cmd_check(a[1:] or FILES)


if __name__ == '__main__':
    main()
