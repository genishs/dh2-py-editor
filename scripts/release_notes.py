"""GitHub 릴리스 본문의 「변경 사항」 절을 README 버전 히스토리에서 뽑는다.

사용 (release.yml 의 release job, ubuntu 러너):
    python3 scripts/release_notes.py --tag v0.4.20 --repo owner/name --out release_changes.md
    python3 scripts/release_notes.py --tag v0.5.0-rc1 --allow-missing ...   # prerelease 용

규칙
- README.md 의 `### vX.Y.Z ...` 헤더부터, 다음 `### v` 헤더 또는 다음 `## ` 헤더 직전까지가 한 항목.
- 해당 버전 항목이 없으면 종료 코드 1 (릴리스를 막는다). --allow-missing 이면 안내 문구로 대체.
- 이 레포의 파일은 Windows 작업트리에선 CRLF, 리눅스 러너에선 LF 다. 읽을 때 universal newline
  으로 통일하고, 모든 입출력은 UTF-8 을 **명시**한다 (Windows 러너 stdout 은 cp1252 라
  암묵 인코딩에 기대면 한글 print 에서 죽는다. 그래서 파일은 encoding= 을 명시하고, stdout/stderr 도
  main() 첫머리에서 UTF-8 로 재설정한다).
- 직전 태그(--prev-tag 생략 시 git 태그에서 자동)가 있으면 Full Changelog 비교 링크를 덧붙인다.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys

FENCE = re.compile(r"^\s*(```|~~~)")
VERSION_HEADER = re.compile(r"^### v")
H2_HEADER = re.compile(r"^## ")


def norm_version(tag: str) -> str:
    """'v0.4.20' / '0.4.20' -> '0.4.20'."""
    return tag.strip().lstrip("vV")


def extract_section(text: str, version: str) -> tuple[str, list[str]] | None:
    """(헤더 줄, 본문 줄들) 을 돌려준다. 없으면 None. text 는 줄끝이 \\n 으로 통일된 것."""
    # `### v0.4.2` 가 `### v0.4.20` 에 걸리지 않도록 뒤는 공백/줄끝/여는 괄호만 허용.
    want = re.compile(r"^### v" + re.escape(version) + r"(?=[\s(]|$)")
    lines = text.split("\n")
    in_fence = False
    start = None
    body: list[str] = []
    for line in lines:
        if FENCE.match(line):
            in_fence = not in_fence
        if start is None:
            if not in_fence and want.match(line):
                start = line
            continue
        if not in_fence and (VERSION_HEADER.match(line) or H2_HEADER.match(line)):
            break
        body.append(line)
    if start is None:
        return None
    while body and not body[-1].strip():
        body.pop()
    while body and not body[0].strip():
        body.pop(0)
    return start, body


def heading_title(header: str, version: str) -> str:
    """`### v0.4.20 (2026-11-16 — 제목 ([#1](url)))` -> `2026-11-16 — 제목 ([#1](url))`."""
    rest = header[len("### v" + version):].strip()
    if rest.startswith("(") and rest.endswith(")"):
        rest = rest[1:-1].strip()
    return rest


def tag_list() -> list[str]:
    try:
        out = subprocess.run(
            ["git", "tag", "-l", "v*", "--sort=-v:refname"],
            check=True, capture_output=True, text=True, encoding="utf-8",
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    return [t.strip() for t in out.splitlines() if t.strip()]


def pick_prev_tag(tag: str, tags: list[str]) -> str | None:
    """tags 는 최신순. tag 가 목록에 있으면 그 다음 것, 없으면(디스패치로 새로 만들 때) 가장 최신."""
    if tag in tags:
        i = tags.index(tag)
        return tags[i + 1] if i + 1 < len(tags) else None
    return tags[0] if tags else None


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tag", required=True, help="릴리스 태그 (예: v0.4.20)")
    ap.add_argument("--repo", default="", help="owner/name — 비교 링크용")
    ap.add_argument("--readme", default="README.md")
    ap.add_argument("--out", required=True, help="결과 마크다운 (UTF-8, LF)")
    ap.add_argument("--allow-missing", action="store_true",
                    help="README 항목이 없어도 실패하지 않고 안내 문구로 대체 (prerelease 용)")
    ap.add_argument("--prev-tag", default=None, help="직전 태그 (생략하면 git 태그에서 자동)")
    ap.add_argument("--no-compare-link", action="store_true")
    a = ap.parse_args()

    version = norm_version(a.tag)
    # newline=None -> CRLF/CR 을 \n 으로 통일해서 읽는다.
    with open(a.readme, encoding="utf-8", newline=None) as f:
        text = f.read()
    found = extract_section(text, version)

    parts = ["## 변경 사항", ""]
    if found is None:
        if not a.allow_missing:
            print(f"::error title=README 변경 기록 없음::{a.readme} 에 '### v{version}' 항목이 없어 "
                  "릴리스를 중단합니다. 버전 히스토리에 항목을 먼저 추가하세요.")
            return 1
        print(f"::warning title=README 변경 기록 없음::'### v{version}' 항목이 없지만 "
              "--allow-missing 이라 안내 문구로 대체합니다.")
        parts += ["README 버전 히스토리에 아직 이 버전의 항목이 없는 시험(prerelease) 빌드입니다."]
    else:
        header, body = found
        title = heading_title(header, version)
        if title:
            parts += [f"**{title}**", ""]
        parts += body

    if a.repo and not a.no_compare_link:
        prev = a.prev_tag if a.prev_tag is not None else pick_prev_tag(a.tag, tag_list())
        if prev and prev != a.tag:
            parts += ["", f"Full Changelog: https://github.com/{a.repo}/compare/{prev}...{a.tag}"]

    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(parts).rstrip("\n") + "\n\n")
    print(f"wrote {a.out}: version={version} found={found is not None}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
