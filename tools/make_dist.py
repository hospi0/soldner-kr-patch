# -*- coding: utf-8 -*-
r"""배포 묶음 — dist/Soldnerschild_KR_v0.9/ (xdelta + xdelta.exe + readme.txt + 패치적용.bat)

  python tools/make_dist.py        # work/out 의 패치본으로 xdelta 생성 → 원본에 적용해 바이트 대조까지

규칙: 해시는 MD5 대문자 · readme 머리말 형식 고정 · 한국어 문서는 CP949(CRLF) · 버전은 v0.9 한 자리.
같은 버전 안에서 내용이 바뀌면 이 스크립트를 다시 돌려 해시만 갱신한다.
"""
import hashlib, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import build

VER = 'v0.9'
NAME = "Soldnerschild Special (Japan).bin"
PKG = 'Soldnerschild_KR_' + VER
DIST = os.path.join(ROOT, 'dist', PKG)
PATCH = PKG + '.xdelta'
XDELTA = r'C:\claude\project\chocobo-kr-patch\dist\Chocobo_KR_v0.91\xdelta.exe'


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()


README = """젤드너실트 스페셜 (PS1 일본판) 한글 패치 {ver}
==========================================

{name} 에 패치하시면 됩니다.

원본md5 : {src}
패치md5 : {dst}

입니다.


[ 적용 방법 ]

1. 원본 {name} 과 .cue 를 한 폴더에 둡니다.
   (트랙 1개 · MODE2/2352 · {srcsize:,} 바이트)
2. 이 패치 묶음을 통째로 그 폴더에 풀고 「패치적용.bat」 을 실행합니다.
3. 배치가 원본 MD5 를 먼저 확인하고, 끝난 뒤 결과 MD5 까지 검사합니다.
   원본은 .bak 으로 남겨 둡니다.
4. 파일 크기는 바뀌지 않습니다. .cue 는 그대로 씁니다.


[ 바뀌는 것 ]

■ 대사 전부(20,247문장), 메뉴·아이템·인물·마법·의뢰·전투 조건
■ 오프닝 내레이션 자막(동영상에 한글을 입힘)
■ 그림 글자: 도시 제목·도시 이름 판·건물 표지·연월 상자,
   전투 결과(무승부·승리·패배)·턴 표시·임무 달성/실패
■ 주인공 이름 입력판을 한글 글자판으로 바꿈


[ 알려진 사항 ]

■ 예전 세이브스테이트는 글자판이 달라 글자가 어긋나 보일 수 있습니다.
   메모리카드 세이브로 불러오면 정상으로 나옵니다.
■ 이름 입력판은 한 쪽(95음절)뿐입니다.
■ 오프닝 지도 위의 나라 이름은 원문 그대로입니다.
"""

BAT = r"""@echo off
setlocal
set NAME={name}
set PATCH={patch}
set SRCMD5={src}
set DSTMD5={dst}

echo.
echo  ==============================================
echo    Soldnerschild Special ^(PS1 JP^) Korean Patch {ver}
echo  ==============================================
echo.

if not exist "%NAME%" (
  echo  [!] "%NAME%" 파일이 이 폴더에 없습니다.
  echo      원본 .bin 과 같은 폴더에 두고 실행하세요.
  goto END
)
if not exist "%~dp0xdelta.exe" (
  echo  [!] xdelta.exe 가 없습니다. 패치 묶음을 그대로 풀고 실행하세요.
  goto END
)

echo  [1/3] 원본 검사 중...
set HASH=
for /f "skip=1 tokens=* delims=" %%H in ('certutil -hashfile "%NAME%" MD5') do (
  if not defined HASH set HASH=%%H
)
set HASH=%HASH: =%

if /I "%HASH%"=="%DSTMD5%" (
  echo.
  echo  [!] 이미 이 버전의 한글 패치가 적용된 파일입니다.
  goto END
)
if /I not "%HASH%"=="%SRCMD5%" (
  echo.
  echo  [!] 원본 MD5 가 다릅니다. 패치하지 않고 중단합니다.
  echo      필요 : %SRCMD5%
  echo      현재 : %HASH%
  goto END
)

echo  [2/3] 패치 적용 중...
"%~dp0xdelta.exe" -d -f -s "%NAME%" "%~dp0%PATCH%" "%NAME%.kr"
if errorlevel 1 (
  echo  [!] 패치에 실패했습니다.
  if exist "%NAME%.kr" del "%NAME%.kr"
  goto END
)

echo  [3/3] 결과 검사 중...
set HASH2=
for /f "skip=1 tokens=* delims=" %%H in ('certutil -hashfile "%NAME%.kr" MD5') do (
  if not defined HASH2 set HASH2=%%H
)
set HASH2=%HASH2: =%

if /I not "%HASH2%"=="%DSTMD5%" (
  echo  [!] 결과 MD5 가 다릅니다. 원본은 그대로 두고 중단합니다.
  del "%NAME%.kr"
  goto END
)

move /y "%NAME%" "%NAME%.bak" >nul
move /y "%NAME%.kr" "%NAME%" >nul
echo.
echo  [OK] 한글 패치 완료. 원본은 "%NAME%.bak" 으로 남겨 두었습니다.

:END
echo.
pause
endlocal
"""


def write_cp949(path, text):
    data = text.replace('\r\n', '\n').replace('\n', '\r\n').encode('cp949')   # 인코딩 먼저(실패해도 파일을 안 비운다)
    with open(path, 'wb') as f:
        f.write(data)


def main():
    src, out = build.SRC, build.OUT
    src_md5, dst_md5 = md5(src), md5(out)
    os.makedirs(DIST, exist_ok=True)
    patch = os.path.join(DIST, PATCH)
    subprocess.run([XDELTA, '-e', '-9', '-f', '-s', src, out, patch], check=True)
    shutil.copyfile(XDELTA, os.path.join(DIST, 'xdelta.exe'))
    # 되짚기: 원본에 패치를 적용해 패치본과 바이트 동일한지
    chk = os.path.join(ROOT, 'work', 'dist_check.bin')
    subprocess.run([XDELTA, '-d', '-f', '-s', src, patch, chk], check=True)
    ok = md5(chk) == dst_md5
    os.remove(chk)
    if not ok:
        raise SystemExit('⛔ xdelta 되짚기 결과가 패치본과 다르다')
    v = dict(ver=VER, name=NAME, patch=PATCH, src=src_md5, dst=dst_md5,
             srcsize=os.path.getsize(src), dstsize=os.path.getsize(out))
    write_cp949(os.path.join(DIST, 'readme.txt'),
                README.format(**dict(v, src=src_md5.upper(), dst=dst_md5.upper())))
    write_cp949(os.path.join(DIST, '패치적용.bat'), BAT.format(**v))
    print('✅ %s\n   xdelta %d B · 원본md5 %s · 패치md5 %s · 되짚기 일치'
          % (DIST, os.path.getsize(patch), src_md5.upper(), dst_md5.upper()))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
