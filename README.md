# 오늘의 잇슈 · Today’s Issue

같은 사건의 여러 보도를 묶고, 근거가 충분한 이슈를 쉽게 설명하는 AI 뉴스 큐레이션 웹서비스입니다. React 화면과 Python 파이프라인을 함께 제공합니다.

**현재 기준은 최근 2주(336시간), 최신 기사 발행 시각 순, 검증 통과 이슈 최대 6개입니다.** 첫 번째 원문의 사진, 원문 링크, 상세 오른쪽 이동 목록을 제공합니다. GNews·NewsData·OpenAI 실제 연동과 로컬 Live 검증을 완료했습니다.

[**기획부터 현재까지 전체 1차 개발 정리**](docs/PHASE_1_REPORT.md) · [API 실행 안내](docs/API_LIVE_INTEGRATION.md) · [검증 결과](docs/VALIDATION.md) · [화면 수정 기록](docs/UI_REVISION.md) · [운영 준비](docs/LIVE_LAUNCH_CHECKLIST.md)

## 현재 상태

| 항목 | 결과 |
|---|---|
| 기술 | React 19 · TypeScript · Vite 7 · Tailwind 4 / Python 3.13 · Pydantic · httpx · OpenAI SDK |
| 화면 | PC 3열 · 태블릿 2열 · 모바일 1열, 공유 가능한 상세 hash URL |
| 뉴스 | GNews 날짜 구간·페이지 조회 + NewsData 최신 관련 기사 + 기간 내 로컬 수집 이력 |
| 선정 | 복수 언론사·독립 원출처 조건 → 최신 발행 순 → GPT 3단계·코드 검증 |
| 최신 로컬 결과 | 291건 스냅샷 → 285건 분석 → 270그룹 → 적격 후보 8개 → 검증 통과 6개 |
| 검증 | 현재 Python 100 · 프론트 20 · 공개 DEMO 브라우저 5 통과; 실제 Live 브라우저 1은 1차 단계에서 확인 |
| 뉴스 이용 범위 | local_private, 실제 계정 플랜 unknown, 공개 재사용 허가 미확인 |
| GitHub 전달 범위 | 소스·가상 DEMO·테스트·문서; 실제 키와 비공개 Live 자료 제외 |

DEMO는 가상 사건·매체 6개와 example.com 링크를 사용합니다. 공개 뉴스 운영은 가입 플랜과 AI 전송·보관·요약·사진 사용 범위를 확인한 뒤 진행합니다. 세부 한계와 이력은 전체 정리 문서에 있습니다.

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

## 실제 API 설정과 실행

.env에 아래 변수의 값을 입력합니다. 실제 값을 저장소에 넣지 않습니다.

~~~dotenv
GNEWS_API_KEY=
NEWSDATA_API_KEY=
OPENAI_API_KEY=
OPENAI_MODEL=
VITE_DATA_MODE=demo
VITE_BASE_PATH=./
~~~

현재 로컬 모델은 gpt-5.4-mini이며 OPENAI_MODEL로 선택합니다. 키에 VITE_ 접두사를 붙이지 않습니다. API는 Python이 호출하고 화면은 JSON만 읽습니다.

~~~powershell
# 상한만 확인: 실제 API 호출·자료 변경 없음
.\.venv\Scripts\python.exe -m pipeline.run --mode live --dry-run
# 수집: 캐시가 없으면 뉴스 API 호출
.\.venv\Scripts\python.exe -m pipeline.run --mode live --stage collect
# 수집 스냅샷으로 후보 확인
.\.venv\Scripts\python.exe -m pipeline.run --mode live --stage select --from-cache
# 최상위 후보 한 건 미리보기: 필요한 경우 GPT 호출
.\.venv\Scripts\python.exe -m pipeline.run --mode live --stage summarize --from-cache
# 최종 에디션 생성: 필요한 경우 GPT 호출
.\.venv\Scripts\python.exe -m pipeline.run --mode live --stage live --from-cache
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Mode live
# 관측된 누적 사용량과 추정 비용
.\.venv\Scripts\python.exe scripts/report_usage.py
~~~

전체 수집부터 생성까지는 python -m pipeline.run --mode live를 사용합니다. 현재 기본 시도 상한은 뉴스 26회(GNews 20·NewsData 6), GPT 18회, 성공 이슈 6개입니다. --max-news-requests, --max-newsdata-requests, --max-related-queries, --max-issues, --max-gpt-requests로 더 작게 제한할 수 있습니다. --fresh는 캐시를 무시합니다. --from-cache는 기존 수집 기준 시각을 유지하며 TTL 만료·기간 변경 시 새 수집을 요구합니다.

GNews는 14개 날짜 구간과 최근 6개 구간의 두 번째 페이지를 사용합니다. NewsData latest 자체는 최근 48시간 범위이며 2주 archive를 가정하지 않습니다. 후보 조건을 만족하지 못하거나 검증·예산이 부족하면 실제 성공 개수만 표시합니다. 조회수·댓글수는 현재 정렬에 사용하지 않습니다.

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

GitHub Actions는 소스 push/PR에서 키 없는 DEMO CI를 실행합니다. 현재 배포 대상은 **Cloudflare Pages**입니다. Cloudflare 계정과 Actions Secrets 두 개를 연결한 뒤 수동 demo 배포로 시작합니다. ENABLE_CLOUDFLARE=true는 main push 배포를 활성화하고 NEWS_MODE=live일 때 KST 오전 7시 예약도 활성화합니다. 공개 Live는 뉴스·사진 이용 근거와 API Secrets를 별도로 확인해야 합니다. [Cloudflare 실행 안내](docs/CLOUDFLARE_SETUP.md)

공개 빌드는 python scripts/build_public.py --mode demo로 .tools/public-deploy/dist에 생성합니다. 로컬 private Live 파일을 포함하지 않도록 선택한 데이터만 별도 staging에서 빌드합니다. 기존 private dist와 .env는 유지합니다.

현재 로컬 dist에는 비공개 Live JSON이 있으므로 외부 업로드하지 않습니다. 전달 ZIP도 현재 private 결과·빌드·원문·키를 제외한 소스 패키지입니다.

## 문서 안내

- [PHASE_1_REPORT](docs/PHASE_1_REPORT.md): 전체 개발 내용과 현재 결과
- [PRD](docs/PRD.md), [ARCHITECTURE](docs/ARCHITECTURE.md): 제품과 구조
- [API_LIVE_INTEGRATION](docs/API_LIVE_INTEGRATION.md), [SOURCES](docs/SOURCES.md): 수집·출처·권한
- [UI_REVISION](docs/UI_REVISION.md): 최근 2주·사진·상세 목록 변경
- [VALIDATION](docs/VALIDATION.md), [DEPLOYMENT](docs/DEPLOYMENT.md): 검증과 운영
- [HOSTING_OPTIONS](docs/HOSTING_OPTIONS.md): 공개 도메인 배포 후보·비용·장단점 비교
- [CLOUDFLARE_SETUP](docs/CLOUDFLARE_SETUP.md): 실제 Cloudflare 배포·계정 연결·일일 갱신 설정
- [LIVE_LAUNCH_CHECKLIST](docs/LIVE_LAUNCH_CHECKLIST.md): 공개 운영 준비
- [WEEKLY_UPDATE](docs/WEEKLY_UPDATE.md), [FINAL_REPORT](docs/FINAL_REPORT.md): 7일 단계와 최초 DEMO 단계의 이력

실제 뉴스 결과가 포함된 API_LIVE_REPORT.md와 Live 캡처는 로컬 비공개 자료로만 보존합니다.
