# 배포와 운영

문서 점검일: **2026-10-16 KST**

현재 서비스는 **Cloudflare에 배포한 고정 페이지**와 **GitHub의 소스 검사**로 구성됩니다. 문서나 소스를 GitHub에 올리는 작업이 뉴스 갱신을 실행하지 않습니다.

## 현재 상태

| 항목 | 구성 |
|---|---|
| 사이트 | [today-issue-dlwo8520.pages.dev](https://today-issue-dlwo8520.pages.dev) |
| 데이터 | 2026-10-15 11:21 KST 고정본, 이슈 6개 |
| 입장 | 지정 이메일 입력; 메일 인증번호·비밀번호 없음 |
| 호스팅 | Cloudflare Pages Direct Upload |
| GitHub | 비공개 `dlwo8520/today-issue` 저장소 |
| CI | `main` push와 PR의 소스 검사 |
| 뉴스 수집·GPT | 공통 중지 정책으로 차단 |
| 예약·수동 자동화 | workflow에 생성·배포 트리거 및 작업 없음 |

## GitHub와 Cloudflare의 역할

**GitHub**는 소스·가상 DEMO·테스트·문서를 보관합니다. `.github/workflows/daily.yml`의 **Source checks**는 Python·프론트·이메일 입장 서버·DEMO 브라우저를 검사합니다.

**Cloudflare**는 기존 빌드 파일과 실제 뉴스 고정본을 제공합니다. Pages Worker가 이메일과 쿠키를 확인한 뒤 파일을 전달합니다.

이전 `ENABLE_PAGES`, `ENABLE_CLOUDFLARE`, `NEWS_MODE` 설정은 현재 workflow에서 사용하지 않습니다. Secrets를 등록하는 것만으로 자동 갱신이 시작되지 않습니다.

## 화면을 바꿔 다시 빌드할 때

기존 실제 뉴스 고정본과 Python·Node 환경이 있는 작업 폴더를 사용합니다. [시작하기](GETTING_STARTED.md)에서 환경 준비를 확인하세요.

개인용 빌드는 다음 명령입니다.

~~~powershell
.\.venv\Scripts\python.exe scripts/build_private.py
~~~

이 빌드는 Cloudflare 조회용 환경변수 `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCESS_EMAIL`과 기존 프로젝트 설정이 필요합니다. 이메일 입장·이전 배포 보호를 확인하고 저장된 JSON으로 빌드하며, GPT·뉴스 API를 호출하지 않습니다.

산출물은 **`.tools/private-deploy/dist/`**입니다. `_worker.js`와 `_routes.json`을 포함한 검증된 개인용 산출물로 수동 배포합니다. 현재 workflow에는 자동 배포 작업이 없습니다.

문서 수정만으로는 이 빌드나 사이트 재배포가 필요하지 않습니다. 구체적인 프로젝트·입장 구성은 [Cloudflare 구성](CLOUDFLARE_SETUP.md)과 [이메일 입력 입장](CLOUDFLARE_PRIVATE_SETUP.md)에 있습니다.

## 가상 DEMO만 빌드할 때

~~~powershell
.\.venv\Scripts\python.exe scripts/build_public.py --mode demo
~~~

산출물은 **`.tools/public-deploy/dist/`**입니다. DEMO JSON과 필요한 화면 파일만 골라 빌드하므로 로컬 실제 뉴스·상태 파일이 섞이지 않습니다.

일반 `npm run build`는 기본 `public/` 안의 파일을 포함할 수 있습니다. 실제 뉴스 파일이 있는 작업 폴더에서는 배포 목적에 맞는 위 빌드 도구를 사용합니다.

## 소스 전달

~~~powershell
.\.venv\Scripts\python.exe scripts/package_project.py
~~~

프로젝트 상위 폴더에 `today-issue-delivery.zip`을 만듭니다. 현재 개인용 데이터 구성에서 아래 자료를 제외합니다.

- `.env`와 실제 API 키
- 실제 뉴스 `latest.json`·`status.json`과 비공개 빌드
- 원자료·캐시·진단·실제 뉴스 캡처
- 로컬 실행 도구와 설치된 의존성

현재 데이터 보존 기준과 호출 차단 범위는 [고정 운영](FROZEN_EDITION.md), 검사는 [검증 안내](VALIDATION.md)를 따릅니다.
