# 오늘의 잇슈 · Today’s Issue

여러 언론사의 보도를 하나의 사건으로 묶고, 주요 이슈의 배경과 흐름을 쉽게 설명하는 뉴스 큐레이션 웹서비스입니다.

> **현재는 고정 에디션을 제공합니다.**
> 2026년 10월 15일 11:21 KST에 생성한 기사 6개를 유지하며, GPT·뉴스 API 호출과 자동 갱신은 중지했습니다.

**[사이트 열기](https://today-issue-dlwo8520.pages.dev)** · [로컬 실행 안내](docs/GETTING_STARTED.md) · [전체 문서](docs/README.md)

## 현재 이용할 수 있는 기능

- 첫 원문 사진이 있는 이슈 카드 6개
- 배경·현재 상황·반응·용어를 구분한 상세 글
- 원문 기사 링크와 상세 오른쪽의 이슈 이동 목록
- PC·태블릿·모바일에 맞춘 화면과 상세 URL 공유

사이트에는 지정된 이메일을 입력해 입장합니다. 메일 인증번호와 비밀번호는 사용하지 않습니다.

| 항목 | 현재 상태 |
|---|---|
| 뉴스 기준 | 2026-10-15 11:21 KST 고정본 |
| 선정 범위 | 고정본의 수집 기준 시각 직전 2주, 336시간 |
| 표시 순서 | 이슈에 포함된 가장 최근 기사 발행 시각 순 |
| 화면 개수 | 검증을 통과한 이슈 6개 |
| GPT·뉴스 API | 호출 중지 |
| GitHub Actions | 소스 검사만 실행; 뉴스 생성·배포 작업 없음 |

페이지 열기, 이메일 입력, 새로고침, 상세 이동은 저장된 결과만 읽습니다. 사진은 기존 첫 원문의 이미지 URL을 사용합니다.

## 내 컴퓨터에서 화면 실행하기

처음 받은 소스는 **가상 뉴스 6개가 들어 있는 DEMO**로 시작합니다. 화면을 확인하는 데는 **Node.js 24와 npm**만 있으면 됩니다. Python 설치와 API 키, `.env` 생성은 필요하지 않습니다.

아래는 **Windows PowerShell 기준**입니다. `README.md`와 `package.json`이 있는 `today-issue` 폴더에서 실행하세요.

**1. 처음 한 번, 화면에 필요한 패키지를 설치합니다.**

~~~powershell
npm.cmd ci
~~~

**2. DEMO 화면을 엽니다.**

~~~powershell
$env:VITE_DATA_MODE = 'demo'
npm.cmd run dev
~~~

터미널에 표시되는 주소를 브라우저에서 여세요. 기본 주소는 **[http://127.0.0.1:5173/](http://127.0.0.1:5173/)** 입니다. 종료할 때는 터미널에서 `Ctrl+C`를 누릅니다.

macOS·Linux 실행, Node가 없는 Windows 환경, 오류 해결은 [자세한 실행 안내](docs/GETTING_STARTED.md)에 정리했습니다.

### 기존 실제 뉴스 고정본 보기

실제 뉴스 파일은 GitHub와 전달 ZIP에 포함하지 않습니다. **기존 작업 폴더에 `public/data/latest.json`이 있는 경우**에만 다음 명령으로 저장된 실제 뉴스를 볼 수 있습니다.

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Mode live
~~~

`live`는 실제 뉴스 데이터 모드의 이름입니다. 현재는 고정본을 표시하며, 이 명령으로 GPT나 뉴스 API를 다시 사용하지 않습니다.

## 코드와 데이터 구성

| 위치 | 역할 |
|---|---|
| `src/` | React·TypeScript 화면과 JSON 검증 |
| `server/email-gate.mjs` | 배포 사이트의 이메일 입력과 쿠키 확인 |
| `config/service.json` | 갱신 중지 정책; 현재 `updates_enabled=false` |
| `pipeline/` | 수집·그룹화·요약 구현; 현재 실행 차단 |
| `public/data/demo.json` | 소스에 포함한 가상 체험 데이터 |
| `public/data/latest.json` | 기존 로컬·배포에만 보관한 실제 뉴스 고정본 |

현재 호스팅은 Cloudflare Pages입니다. GitHub에 문서를 수정해 올려도 사이트를 다시 배포하거나 뉴스를 생성하지 않습니다.

## 목적별 문서

| 확인할 내용 | 문서 |
|---|---|
| 설치·실행·오류 해결 | [시작하기](docs/GETTING_STARTED.md) |
| 고정 기준과 API 중지 범위 | [고정 운영](docs/FROZEN_EDITION.md) |
| Cloudflare·입장 방식·소스 전달 | [배포와 운영](docs/DEPLOYMENT.md) |
| 테스트 결과와 재현 방법 | [검증](docs/VALIDATION.md) |
| 화면·서버·데이터 구조 | [기술 구조](docs/ARCHITECTURE.md) |
| 기획·변경 이력·이전 API 설계 | [전체 문서 목록](docs/README.md) |

문서 정리 기준일: **2026-10-16 KST**. 기사 데이터의 기준 시각은 위 고정본 시각을 유지합니다.
