# 검증 결과와 재현 방법

문서 점검일: **2026-10-16 KST**

아래 수치는 **10월 15일 고정 운영 전환 버전**에서 확인한 결과입니다. 이전 문서에 섞여 있던 92개·112개 등의 검사 수는 해당 개발 단계의 기록이며 현재 표와 합산하지 않습니다.

## 확인된 결과

| 검사 | 결과 | 확인 범위 |
|---|---:|---|
| Python | 129개 통과 | 기존 파이프라인·저장·검증, 호출 중지·파일 보존 |
| 프론트 Vitest | 22개 통과 | 홈·상세·스키마·고정 안내·상태 조회 생략 |
| 이메일 입장 서버 | 8개 통과 | 이메일·서명 쿠키·입력 전 파일 차단 |
| DEMO 브라우저 | 5개 통과 | PC·태블릿·모바일, 원문·상세 이동, 오류 복구 |
| 실제 주소 Live 브라우저 | 1개 통과 | 이메일 입장, 기사·사진 6개, PC·모바일 상세 |
| Ruff·TypeScript·Vite | 통과 | 코드 검사와 빌드 |
| 고정 데이터 | 원본과 원격 해시 일치 | 본문·출처·시각·사진 URL 보존 |

[고정 운영 버전의 원격 CI](https://github.com/dlwo8520/today-issue/actions/runs/38673202683)는 소스 검사만 실행했습니다. 실제 Live 브라우저 검사는 비공개 파일이 있는 로컬 환경에서 별도로 실행했습니다.

## 무엇을 검사했나요?

**API 중지:** Live CLI의 각 단계와 직접 어댑터 호출을 차단하고, 클라이언트 호출·기존 JSON·상태 파일 변경이 없는지 검사했습니다. 정책이 없거나 잘못되어도 호출을 허용하지 않습니다.

**화면:** 6개 카드, 사진 로드, 최신 발행 순, 상세 새로고침, 원문 링크, 오른쪽 목록 이동과 고정 안내를 확인했습니다. 고정 화면은 지연 경고와 상태 JSON 조회를 생략합니다.

**입장:** 지정 이메일 입장, 다른 이메일 거부, 서명이 없거나 잘못된 쿠키의 파일 접근 차단을 확인했습니다.

**전달:** 실제 키와 비공개 뉴스·캐시·캡처가 소스 ZIP에 포함되지 않는지 확인했습니다.

## 로컬 단위 검사

먼저 [시작하기](GETTING_STARTED.md)에서 Node·패키지와 선택 사항인 Python 환경을 준비합니다.

### Python

~~~powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check pipeline scripts tests/python
~~~

### 프론트와 입장 서버

~~~powershell
npm.cmd test
npm.cmd run check
node --test tests/server/email-gate.test.mjs
~~~

Python의 수집·GPT 연동 검사는 모의 응답과 임시 정책을 사용합니다. 운영 중지 정책을 바꾸거나 실제 뉴스·GPT를 호출하지 않습니다.

## DEMO 브라우저 검사

기존 Live 서버와 혼동하지 않도록 별도 포트 **5175**를 사용합니다. 두 터미널 모두 같은 프로젝트 폴더에서 실행하세요.

**터미널 1 — DEMO 서버**

~~~powershell
$env:VITE_DATA_MODE = 'demo'
npm.cmd run dev -- --port 5175 --strictPort
~~~

**터미널 2 — 검사**

~~~powershell
$env:PLAYWRIGHT_BASE_URL = 'http://127.0.0.1:5175/'
npm.cmd run test:e2e -- tests/browser/site.spec.ts
~~~

브라우저 실행 파일이 없다는 오류가 나오면 `npx.cmd playwright install chromium`으로 준비합니다. 검사 후 터미널 1에서 `Ctrl+C`로 검사 서버를 종료합니다.

## 실제 고정본 브라우저 검사

기존 `public/data/latest.json`이 있는 환경에서만 실행합니다. 사이트의 입장 이메일을 로컬 환경변수로 전달합니다.

~~~powershell
$env:PLAYWRIGHT_BASE_URL = 'https://today-issue-dlwo8520.pages.dev'
$env:TEST_REAL_LIVE = '1'
$env:TEST_PERSONAL_EMAIL = '입장에 사용하는 이메일'
npm.cmd run test:e2e -- tests/browser/live.spec.ts
~~~

검사 파일의 위치와 실제 서버를 먼저 확인한 뒤 실행합니다. 이 검사는 저장된 페이지를 읽으며, 브라우저에서 뉴스·GPT API 요청이 발생하면 차단하고 실패로 처리합니다. 일반 GitHub CI에서는 이 검사를 건너뜁니다.

## 결과의 범위

자동 접근성 검사 통과는 수동 스크린리더 검증이나 접근성 인증을 뜻하지 않습니다. 사람의 뉴스 사실 판정, 읽기 시간 실험, Lighthouse 평가는 위 결과에 포함하지 않았습니다.

과거 단계별 수집 결과·호출 비용·검사 수는 [개발 이력 목록](README.md)에 보존합니다.
