# 오늘의 잇슈 · Today’s Issue

같은 사건의 여러 보도를 묶고, 근거가 충분한 이슈를 쉽게 설명하는 AI 뉴스 큐레이션 웹서비스입니다. React 화면과 Python 파이프라인을 함께 제공합니다.

**현재 서비스는 2026년 10월 15일 11:21 KST 결과로 고정되어 있습니다. GPT·뉴스 API 호출과 자동·수동 갱신을 중지했습니다.** 저장된 최근 2주(336시간), 최신 발행 순 이슈 6개를 읽을 수 있습니다. 첫 번째 원문의 사진, 원문 링크, 상세 오른쪽 이동 목록을 제공합니다. GNews·NewsData·OpenAI 실제 연동과 로컬 Live 검증을 완료했습니다.

[**기획부터 현재까지 전체 1차 개발 정리**](docs/PHASE_1_REPORT.md) · [API 실행 안내](docs/API_LIVE_INTEGRATION.md) · [검증 결과](docs/VALIDATION.md) · [화면 수정 기록](docs/UI_REVISION.md) · [운영 준비](docs/LIVE_LAUNCH_CHECKLIST.md)

**접속 주소: [오늘의 잇슈](https://today-issue-dlwo8520.pages.dev)** — 2026-10-15 새로 수집·검증한 실제 이슈 6개와 첫 원문 사진 6개를 배포했습니다. 제목·요약 박스·문단 간격·용어 강조를 다듬었습니다. 지정한 이메일 입력만으로 입장하며 메일 인증번호·비밀번호를 요구하지 않습니다. [가독성 개선 기록](docs/READABILITY_UPDATE.md) · [개인용 설정 안내](docs/CLOUDFLARE_PRIVATE_SETUP.md)

이메일 일치 확인은 본인 인증이 아닙니다. 같은 이메일을 아는 다른 사람도 입장할 수 있습니다. 실제 주소의 이메일 입력·뉴스·사진·PC·모바일·상세 이동 검사를 통과했습니다. GitHub 예약·수동 생성·배포 작업을 제거했으며, 소스 검사만 실행합니다. [고정 운영 기록](docs/FROZEN_EDITION.md)

## 현재 상태

| 항목 | 결과 |
|---|---|
| 기술 | React 19 · TypeScript · Vite 7 · Tailwind 4 / Python 3.13 · Pydantic · httpx · OpenAI SDK |
| 화면 | PC 3열 · 태블릿 2열 · 모바일 1열, 공유 가능한 상세 hash URL |
| 뉴스 | GNews 날짜 구간·페이지 조회 + NewsData 최신 관련 기사 + 기간 내 로컬 수집 이력 |
| 선정 | 복수 언론사·독립 원출처 조건 → 최신 발행 순 → GPT 3단계·코드 검증 |
| 최신 결과 | 673건 스냅샷 → 667건 분석 → 628그룹 → 적격 후보 29개 → 검증 통과 6개 |
| 검증 | API 중지·스냅샷 보존 회귀 검사와 기존 기능 검사; 상세는 고정 운영 기록 참조 |
| 뉴스 이용 범위 | local_private; GNews·NewsData 모두 무료 플랜이라고 사용자 확인, 사진 공개 이용 권한 미확인 |
| 배포 | Cloudflare Pages 고정 에디션·이메일 입력 입장; GitHub Actions는 API 키 없는 CI만 실행 |
| GitHub 전달 범위 | 소스·가상 DEMO·테스트·문서; 실제 키와 비공개 Live 자료 제외 |

DEMO는 가상 사건·매체 6개와 example.com 링크를 사용합니다. 무료 플랜 자체를 공개 금지로 판단하지 않습니다. GNews의 비상업적 이용 조건과 언론사 사진의 별도 권리는 [뉴스 이용 조건 확인](docs/NEWS_USAGE_REVIEW.md)에 기록했습니다. 세부 한계와 이력은 전체 정리 문서에 있습니다.

## 새 환경에서 실행

Node 22.12 이상 또는 Node 24와 Python 3.13을 준비합니다. 저장소 루트에서:

~~~powershell
npm ci
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
# .env가 없는 환경에서만 복사
Copy-Item -LiteralPath .env.example -Destination .env
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Mode demo
~~~

http://127.0.0.1:5173/ 에서 확인합니다. dev.ps1은 필요 시 공식 Node portable 도구를 준비하며 전역 실행 정책을 변경하지 않습니다. macOS/Linux는 .venv/bin/python을 사용하고 VITE_DATA_MODE=demo npm run dev로 실행합니다. DEMO에는 API 키가 필요 없습니다.

기존 작업 폴더에는 실제 .env가 준비되어 있으므로 덮어쓰지 않습니다. 저장된 로컬 Live 결과를 보려면 dev.ps1 -Mode live를 사용합니다. 이 화면 실행 명령 자체는 뉴스·GPT API를 호출하지 않습니다.

## 고정 운영과 API 중지

config/service.json의 updates_enabled=false가 뉴스·RSS 수집과 GPT 호출을 차단합니다. --fresh, --from-cache, --stage, --dry-run을 붙여도 Live CLI는 기존 파일을 변경하지 않고 종료합니다. 어댑터·GPT 요약기를 직접 호출해도 같은 정책을 확인합니다. 정책 파일이 없거나 잘못되어도 호출을 허용하지 않습니다.

현재 페이지는 저장된 JSON만 표시합니다. 이메일 입력, 페이지 이동, 새로고침은 GPT·뉴스 API를 호출하지 않습니다. 사진은 기존 첫 원문의 이미지 URL을 사용합니다. 기사·수집 시각을 새로 만들지 않았습니다.

기존 .env의 API 키는 Git에서 제외한 상태로 유지하며, 고정 운영에는 사용하지 않습니다. API 키 자체를 폐기하거나 다른 프로젝트 사용을 중단한 것은 아닙니다. 재개는 별도 요청을 받은 뒤 정책과 운영 설정을 다시 검토해야 합니다. [이전 API 구현 안내](docs/API_LIVE_INTEGRATION.md)의 수집·요약 명령은 현재 차단됩니다.

## 검증 명령

~~~powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check pipeline scripts tests/python
npm test
npm run build
$env:VITE_DATA_MODE='demo'
npm run test:e2e -- tests/browser/site.spec.ts
~~~

브라우저 테스트는 DEMO 모드로 실행합니다. Live 개발 서버가 이미 5173을 사용 중이면 별도 DEMO 서버를 열고 PLAYWRIGHT_BASE_URL로 지정합니다. 실제 Live 브라우저 검사는 TEST_REAL_LIVE=1을 사용하는 로컬 opt-in입니다. [검사 범위와 재현](docs/VALIDATION.md)

## 저장·배포

Live 화면 결과는 public/data/latest.json과 status.json이며 Git에서 제외합니다. 원문·캐시·진단은 data/raw·cache·debug·reports에 저장합니다. 실패 시 이전 정상 JSON을 보존하고 Live를 DEMO로 대체하지 않습니다. 실제 원문 사진 URL만 연결하며 사진 파일을 저장소에 복사하지 않습니다.

GitHub Actions는 소스 push/PR에서 키 없는 DEMO CI만 실행합니다. 예약 트리거, 수동 생성·배포 트리거, 실제 뉴스 생성·배포 작업, API Secrets 참조를 제거했습니다. 기존 Variable이나 Secret이 등록되더라도 이 workflow에서 갱신을 실행할 경로가 없습니다. 현재 Cloudflare 고정 페이지는 계속 유지합니다.

공개 빌드는 python scripts/build_public.py --mode demo로 .tools/public-deploy/dist에 생성합니다. 로컬 private Live 파일을 포함하지 않도록 선택한 데이터만 별도 staging에서 빌드합니다. 기존 private dist와 .env는 유지합니다.

현재 로컬 dist에는 비공개 Live JSON이 있으므로 외부 업로드하지 않습니다. 전달 ZIP도 현재 private 결과·빌드·원문·키를 제외한 소스 패키지입니다.

## 문서 안내

- [FROZEN_EDITION](docs/FROZEN_EDITION.md): 현재 고정 기준과 API 중지 범위

- [PHASE_1_REPORT](docs/PHASE_1_REPORT.md): 전체 개발 내용과 현재 결과
- [PRD](docs/PRD.md), [ARCHITECTURE](docs/ARCHITECTURE.md): 제품과 구조
- [API_LIVE_INTEGRATION](docs/API_LIVE_INTEGRATION.md), [SOURCES](docs/SOURCES.md): 수집·출처·권한
- [UI_REVISION](docs/UI_REVISION.md): 최근 2주·사진·상세 목록 변경
- [READABILITY_UPDATE](docs/READABILITY_UPDATE.md): 10월 15일 글 가독성 개선·최신 에디션·배포 검증
- [VALIDATION](docs/VALIDATION.md), [DEPLOYMENT](docs/DEPLOYMENT.md): 검증과 운영
- [HOSTING_OPTIONS](docs/HOSTING_OPTIONS.md): 공개 도메인 배포 후보·비용·장단점 비교
- [CLOUDFLARE_SETUP](docs/CLOUDFLARE_SETUP.md): 실제 Cloudflare 배포·계정 연결·일일 갱신 설정
- [NEWS_USAGE_REVIEW](docs/NEWS_USAGE_REVIEW.md): 무료 플랜 확인과 실제 뉴스·사진 공개 조건
- [CLOUDFLARE_PRIVATE_SETUP](docs/CLOUDFLARE_PRIVATE_SETUP.md): 본인 이메일 인증번호 로그인과 개인용 Live 빌드
- [LIVE_LAUNCH_CHECKLIST](docs/LIVE_LAUNCH_CHECKLIST.md): 공개 운영 준비
- [WEEKLY_UPDATE](docs/WEEKLY_UPDATE.md), [FINAL_REPORT](docs/FINAL_REPORT.md): 7일 단계와 최초 DEMO 단계의 이력

실제 뉴스 결과가 포함된 API_LIVE_REPORT.md와 Live 캡처는 로컬 비공개 자료로만 보존합니다.
