"""PyInstaller `--version-file` 용 버전 리소스를 생성한다.

배경: 서명되지 않은 `.exe` 에 버전 리소스(회사/제품/설명) 까지 비어 있으면
Chrome Safe Browsing 과 SmartScreen 의 평판 휴리스틱에서 불리하다. 실제로
v0.4.16 릴리스 산출물은 CompanyName/ProductName/FileVersion 이 모두 공란이었다.

사용:
    python build_version_info.py [출력경로]

기본 출력: build/version_info.txt (gitignore 대상)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COMPANY = "genishs"
PRODUCT = "대항해시대 II 세이브 에디터"
DESCRIPTION = "대항해시대 II (Koukai 2) 세이브·MAIN.EXE 편집기"
COPYRIGHT = "MIT License. github.com/genishs/dh2-py-editor"
EXE_NAME = "koukai2_editor.exe"

_TEMPLATE = """\
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({v0}, {v1}, {v2}, 0),
    prodvers=({v0}, {v1}, {v2}, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '041204b0',
        [StringStruct('CompanyName', {company!r}),
         StringStruct('FileDescription', {description!r}),
         StringStruct('FileVersion', {version!r}),
         StringStruct('InternalName', {exe_name!r}),
         StringStruct('LegalCopyright', {copyright!r}),
         StringStruct('OriginalFilename', {exe_name!r}),
         StringStruct('ProductName', {product!r}),
         StringStruct('ProductVersion', {version!r})])
    ]),
    VarFileInfo([VarStruct('Translation', [0x0412, 1200])])
  ]
)
"""


def read_version() -> str:
    """horiedit_py/__init__.py 의 __version__ 을 import 없이 읽는다."""
    src = (ROOT / "horiedit_py" / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', src, re.M)
    if not m:
        raise SystemExit("horiedit_py/__init__.py 에서 __version__ 을 찾지 못했습니다.")
    return m.group(1)


def _force_utf8_output() -> None:
    """stdout/stderr 를 UTF-8 로. 러너 기본 인코딩(cp1252) 에서 한글 출력이
    UnicodeEncodeError 를 내는 것을 막는다."""
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def main(argv: list[str]) -> int:
    _force_utf8_output()
    version = read_version()
    parts = [int(p) for p in re.findall(r"\d+", version)[:3]]
    while len(parts) < 3:
        parts.append(0)

    out = Path(argv[1]) if len(argv) >= 2 else ROOT / "build" / "version_info.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        _TEMPLATE.format(
            v0=parts[0],
            v1=parts[1],
            v2=parts[2],
            version=version,
            company=COMPANY,
            product=PRODUCT,
            description=DESCRIPTION,
            copyright=COPYRIGHT,
            exe_name=EXE_NAME,
        ),
        encoding="utf-8",
    )
    print(f"version_info written: {out} (version {version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
