# 코드 서명 정책 (Code Signing Policy)

이 문서는 [SignPath Foundation](https://signpath.org/) 무료 코드 서명 프로그램이
요구하는 "Code signing policy" 문서다. 프로젝트의 역할 구분, 릴리스 절차,
개인정보 처리 방침을 밝힌다.

## 프로젝트

- 이름: 대항해시대 II 세이브 에디터 (`dh2-py-editor`)
- 저장소: https://github.com/genishs/dh2-py-editor
- 라이선스: [MIT](LICENSE) — 상업용 이중 라이선스 없음
- 목적: 코에이 *대항해시대 II* 의 **로컬 세이브 파일과 게임 실행 파일을
  사용자 본인의 PC 에서 편집**하는 단일 실행형 GUI 도구. 네트워크 통신,
  텔레메트리, 번들 소프트웨어, 광고가 일절 없다.

## 역할 (Roles)

이 프로젝트는 1 인 유지보수 프로젝트다.

| 역할 | 담당 | 권한 |
|---|---|---|
| Author | [@genishs](https://github.com/genishs) | `master` 직접 커밋 |
| Reviewer | [@genishs](https://github.com/genishs) | 외부 기여(PR) 검토·승인 |
| Approver | [@genishs](https://github.com/genishs) | 서명 요청 승인 |

- 외부 기여는 **Pull Request 로만** 받으며, 병합 전 Reviewer 가 전체 diff 를
  검토한다.
- GitHub 계정과 SignPath 계정 모두 **다중 인증(MFA)** 을 사용한다.

## 빌드와 서명 절차

1. `v*` 태그를 push 하면 [`.github/workflows/release.yml`](.github/workflows/release.yml)
   이 GitHub 호스티드 `windows-latest` 러너에서 빌드한다. 로컬 빌드 산출물을
   릴리스에 올리지 않는다 — **모든 배포 바이너리는 공개 저장소의 소스에서
   자동 빌드된 것**이다.
2. 빌드는 PyInstaller `--onefile` 이며, `build_version_info.py` 가 생성한
   버전 리소스(제품명·버전)를 `--version-file` 로 임베드한다.
3. 서명 전 검증 단계가 버전 리소스 누락을 빌드 실패로 처리한다.
4. 서명 요청은 SignPath 로 제출되며, **Approver 의 수동 승인**을 거쳐야
   서명된다. 자동 승인은 설정하지 않는다.
5. 서명된 `.exe`, `.zip`, `SHA256SUMS.txt` 가 GitHub Release 에 게시된다.

## 개인정보 (Privacy)

이 프로그램은 사용자의 어떤 데이터도 수집·전송하지 않는다. 인터넷에 접속하지
않으며, 사용자가 지정한 게임 폴더의 `KOUKAI2.DAT` / `MAIN.EXE` 만 로컬에서
읽고 쓴다. 유일하게 생성하는 파일은 게임 폴더 옆의 `.dh2editor_seen`
(안내 창 표시 여부 1 byte) 이다.

## 크레딧

무료 코드 서명은 [SignPath Foundation](https://signpath.org/) 이 제공하며,
서명 인프라는 [SignPath.io](https://signpath.io/) 를 사용한다.
