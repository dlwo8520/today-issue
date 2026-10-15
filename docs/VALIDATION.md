# 실행 검증 기록

> 2026-10-15 가독성 개선: 프론트 21개·DEMO 프로덕션 브라우저 5개·실제 Cloudflare Live 브라우저 1개 통과, TypeScript 및 두 배포 모드 빌드 성공. 오늘 새로 생성한 이슈·첫 원문 사진 6개, 이메일 입력·PC/모바일·원문·상세 이동·접근성과 배포 JSON 일치를 확인했습니다. [변경·검증 상세](READABILITY_UPDATE.md).

> 현재 개인용 Live 검증(2026-10-14): Python 112개·서버 이메일 입장 8개 통과, Ruff·TypeScript·개인용 빌드 성공. 실제 Cloudflare 주소에서 이메일 입력·사진 6개·PC/모바일·상세 이동·접근성 Live 브라우저 1개 통과. 입력 전·위조 쿠키는 입장 화면으로 이동하고 다른 이메일은 403, 지정 이메일은 인증번호 없이 입장하여 원격 JSON과 로컬 빌드의 일치를 확인했습니다. 프론트 20개·DEMO 브라우저 5개는 앞선 검증이며 반복 실행을 고유 개수에 더하지 않습니다. [현재 운영](CLOUDFLARE_PRIVATE_SETUP.md).

> 2026-10-14 Cloudflare 공개 빌드 변경 검증: Python 100개·프론트 20개·공개 DEMO 프로덕션 브라우저 5개 통과, TypeScript·빌드·Ruff 성공. [원격 CI](https://github.com/dlwo8520/today-issue/actions/runs/38499480332)도 성공했습니다. 직접 Cloudflare 배포 후 [실제 공개 주소](https://today-issue-dlwo8520.pages.dev)에서도 브라우저 5개를 통과했습니다. 반복 실행은 고유 검사 수에 더하지 않습니다. 실제 Live 브라우저 1개는 아래 1차 단계의 검증이며 이번 공개 빌드 작업에서 다시 실행하지 않았습니다. [현재 배포 안내](CLOUDFLARE_SETUP.md).

최종 기능 검증일: 2026-10-13 KST. Windows, Python 3.13.9, Node v24.21.0, Google Chrome headless. 현재 기준은 최근 2주·최신순 최대 6개입니다. [전체 1차 개발 정리](PHASE_1_REPORT.md)

| 검사 | 최신 기능 검증 결과 |
|---|---|
| Python pytest | 92 passed |
| Ruff | All checks passed |
| 프론트 Vitest | 20 passed |
| TypeScript + Vite Live build | 성공 |
| DEMO Playwright | 5 passed |
| 실제 Live Playwright — 프로덕션 정적 서버 | 1 passed |
| Live axe | PC 1440px·모바일 390px 홈/상세의 위반 0 |
| DEMO axe | PC·태블릿·모바일 홈/상세 통과 |
| 실제 API | GNews·NewsData HTTP 200, OpenAI 구조화 응답 성공 |
| 사진 | 6개 첫 원문 사진 실제 로드 확인 |
| 공개 검사 | private Live 결과의 공개 거부 확인 |
| 전달 검사 | 실제 키 미포함, 비공개 자료·빌드 제외 |

고유 테스트는 Python 92 + 프론트 20 + DEMO 브라우저 5 + 실제 Live 브라우저 1 = **118개**입니다. 같은 테스트의 반복 실행을 추가 개수로 세지 않았습니다. 이전 7일 단계의 109개·이슈 4개 기록은 [WEEKLY_UPDATE](WEEKLY_UPDATE.md)에 보존합니다.

## 자동 테스트 범위

RSS·정규화·사건 그룹화·중복 전재·결측·JSON 스키마·원자적 저장·실행 잠금·근거 검증 회귀 검사를 유지했습니다. API 인증·쿼터·속도 제한·타임아웃·날짜 시간대·URL·공급자 이력·실제 언론사 별칭·포털 재게시 제외·정보 부족·예산·캐시·dry-run·공개 차단을 검사합니다.

현재 변경은 336시간 경계와 그룹화, 최신 기사 발행 순, 날짜 구간·추가 페이지, 사진 필드와 중복 보존, 제한된 OG 메타데이터 확인, 안전한 이미지 URL, Windows ReplaceFile 보완을 포함합니다. 프론트는 사진·제거된 안내/번호/선정 설명·현재 링크와 이동 목록을 검사합니다.

OpenAI SDK responses.parse를 httpx.MockTransport와 연결한 검사도 있습니다. 모의 응답의 통과는 실제 모델의 요약 품질을 확인한 결과와 구분합니다.

## 실제 Live 검사

현재 수집 스냅샷은 이력 포함 291건, 포털 미확인 5건과 중복을 제외한 285건, 270그룹, 적격 후보 8개, 최종 검증 통과 6개입니다. API·GPT를 실제 호출했으며 불합격 후보를 제외했습니다. 같은 캐시의 최종 Live 재실행은 새 뉴스·GPT 호출 0회로 성공했습니다.

127.0.0.1:4173의 프로덕션 정적 서버에서 PC 1440px·모바일 390px을 검사했습니다. 336시간 기간·최근 2주 표기·6개 카드·최신 발행 순·실제 사진 naturalWidth·갱신 시각·직접 상세 URL/새로고침·원문 링크의 href/target/rel·상세 오른쪽 목록·두 번째 이슈 이동을 확인했습니다.

모바일의 lazy 이미지도 각각 화면으로 스크롤하여 로드를 확인했습니다. 중복 날짜·긴 처리 안내·문장 출처 번호·선정 설명 영역이 없는지 검사했습니다. 홈/상세 axe 위반, 가로 넘침, pageerror는 없었습니다. 캡처를 눈으로 확인했고 실제 뉴스 캡처는 비공개 data/reports/screenshots에 보관합니다.

DEMO는 1440px·800px·390px의 홈/상세를 별도로 검사했습니다. 테스트 출력 디렉터리를 공유하는 동시 실행은 피하며 최종 통과 결과는 단독 실행을 기준으로 합니다.

## 전달·운영 검사와 미완료 범위

실제 키를 출력하지 않고 로컬 설정값과 전달 파일의 일치를 검사합니다. 소스 ZIP의 무결성, .env·원문·캐시·진단·private JSON·private 빌드 제외와 스키마를 확인합니다. 비공개 Live 자료는 공개 검사에서 거부됩니다.

1차 소스 업로드에서는 Pages와 예약 발행을 ENABLE_PAGES Variable로 명시적으로 활성화하도록 구성합니다. 원격 Actions 결과, 예약·복구 운영, 실제 가입 플랜, 공개 뉴스·사진 이용 범위는 로컬 테스트 통과와 별개입니다.

초기 DEMO 단계에서 /today-issue/ 하위 경로 프로덕션 검사 5개와 npm audit --omit=dev의 0 vulnerabilities를 확인했습니다. 이번 화면 변경에서 해당 audit·하위 경로 검사를 새로 수행했다는 뜻은 아닙니다. 최근 기능 변경은 의존성을 추가하지 않았습니다.

사람 판정 실제 뉴스 평가, Lighthouse, 읽기 시간 실험, 수동 스크린리더 검사는 미완료입니다. axe 통과는 WCAG 적합성 인증이 아닙니다.

## 재현

기본 명령은 [README](../README.md)에 있습니다. Chrome이 없으면 npx playwright install chromium을 사용합니다. 실행 중인 Live 서버와 DEMO 검사를 혼용하지 않습니다.

~~~powershell
# 별도 DEMO 서버를 먼저 실행한 경우 주소 지정
$env:PLAYWRIGHT_BASE_URL='http://127.0.0.1:5175/'
$env:VITE_DATA_MODE='demo'
npm run test:e2e -- tests/browser/site.spec.ts
# 실제 local_private latest.json과 Live 정적 서버가 있는 경우
$env:PLAYWRIGHT_BASE_URL='http://127.0.0.1:4173/'
$env:TEST_REAL_LIVE='1'
npm run test:e2e -- tests/browser/live.spec.ts
~~~

실제 Live 검사는 opt-in이며 일반 GitHub CI에서는 실행하지 않습니다. 새 소스 체크아웃에는 private latest.json이 없으므로 DEMO로 시작합니다.
