# 오늘의 잇슈 — Cloudflare Pages 실제 배포 안내

작성일: 2026-10-14 KST

**공개 주소: [오늘의 잇슈](https://today-issue-dlwo8520.pages.dev)**

2026-10-14 사용자가 만든 Cloudflare 계정에 Direct Upload 프로젝트를 생성하고 가상 이슈 6개의 DEMO를 직접 배포했습니다. 실제 Production 주소의 HTTPS와 Playwright 검사 5개를 확인했습니다. 배포 ID는 `9d94910c-c4ec-4bbd-b117-e5a4f868b2d4`입니다. 실제 뉴스와 사진은 아직 공개하지 않았습니다.

사용자는 GitHub Actions Secrets를 아직 등록하지 않았다고 확인했습니다. 첫 배포는 Actions가 아닌 직접 배포이며, 자동 배포와 일일 갱신은 아직 활성화하지 않았습니다. 받은 토큰은 배포 프로세스의 환경변수로만 사용했고 소스·문서·전달 ZIP에 저장하지 않았습니다.

## 1. 이번에 구현한 것

- 기존 `.github/workflows/daily.yml`을 Cloudflare Pages 대상으로 전환했습니다.
- 키 없는 CI → 공개 권한 검사 → 프로젝트 확인/최초 생성 → 선택 모드 빌드 → Cloudflare 배포 순서입니다.
- `scripts/ensure_cloudflare_project.py`가 자격 증명을 환경변수로 읽고, 선택한 Direct Upload 프로젝트가 없을 때만 생성합니다. 기존 Git 연동 프로젝트를 임의로 변경하지 않습니다.
- `scripts/build_public.py`가 선택한 공개 데이터와 favicon만 별도 디렉터리에 넣어 빌드합니다. DEMO 공개 빌드에 로컬 private Live JSON·상태·사진 파일이 섞이지 않습니다.
- 실제 Live는 설정의 공개 이용 근거와 Edition의 공개 범위를 모두 검사합니다. 수집 전에 설정을 검사하여 공개 준비가 안 된 상태에서 원격 API 비용을 사용하지 않습니다.
- 생성 JSON은 `Cache-Control: no-store`, 해시가 붙은 빌드 asset은 장기 캐시로 제공합니다.
- 실제 URL은 성공한 Actions 실행의 Deployment와 Production 항목에 기록합니다.

실제 프로젝트 이름은 `today-issue-dlwo8520`, production branch는 `main`입니다. 위 주소는 현재 접속 가능한 Production 주소입니다. 별도 도메인 구매나 DNS 변경은 하지 않았습니다.

## 2. 처음 한 번 필요한 사용자 설정

### 무료 Cloudflare 계정

Cloudflare 가입과 첫 배포 연결을 완료했습니다. 새 환경에서 시작하는 경우 [Cloudflare 가입](https://dash.cloudflare.com/sign-up)을 사용합니다. 현재 `pages.dev` 주소는 도메인을 먼저 구매할 필요 없이 공유할 수 있습니다.

### GitHub Actions Secrets 두 개

Cloudflare 계정의 Account ID와 API Token을 다음 저장소에 등록합니다. 토큰을 채팅이나 소스 파일에 붙여넣지 않습니다.

[GitHub Actions Secrets 설정](https://github.com/dlwo8520/today-issue/settings/secrets/actions)

1. **New repository secret**을 누릅니다.
2. 아래 표의 이름을 **Name**, 해당 값을 **Secret**에 넣고 **Add secret**을 누릅니다.
3. 두 이름이 목록에 표시되는지 확인합니다. 이 두 값은 이미 사용자가 보유한 Cloudflare 값이며 토큰을 다시 발급할 필요는 없습니다.

현재 연결된 GitHub 도구는 Secrets 쓰기를 지원하지 않아 이 등록은 계정 소유자가 해야 합니다. 토큰은 이 문서에 적지 않습니다.

| Secret 이름 | 넣을 값 |
|---|---|
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare 계정의 Account ID |
| `CLOUDFLARE_API_TOKEN` | 해당 계정의 Pages 프로젝트를 관리할 API Token |

Cloudflare에서 API Token을 만들 때 권한은 `Account → Cloudflare Pages → Edit`, Account Resources는 사용할 계정으로 제한합니다. API Token과 전역 Global API Key를 혼동하지 않습니다. 토큰의 값은 GitHub Secret에 직접 저장합니다. 계정 ID 확인·토큰 설정 절차는 [Cloudflare 공식 CI 안내](https://developers.cloudflare.com/pages/how-to/use-direct-upload-with-continuous-integration/)를 따릅니다.

프로젝트는 workflow가 API로 처음 생성하므로 직접 Git 연동 프로젝트를 만들 필요가 없습니다. 이미 같은 이름의 Git 연동 프로젝트가 있으면 별도 이름을 선택합니다.

## 3. GitHub Actions 배포 확인 — DEMO

현재 사이트는 이미 공개되어 있습니다. Secrets 등록 후 아래 절차로 자동 배포 경로를 확인합니다.

1. 저장소 [Actions](https://github.com/dlwo8520/today-issue/actions)를 엽니다.
2. **Cloudflare edition**을 선택합니다.
3. **Run workflow**에서 branch `main`, mode `demo`를 선택합니다.
4. `checks`, `prepare`, `deploy` 성공을 확인합니다.
5. 실행 Summary에 표시된 실제 Production 주소를 엽니다.

이 실행은 API 키 없이 가상 DEMO 6개를 공개하는 검사입니다. 실제 뉴스·실제 사진의 공개 서비스는 아래 Live 조건을 완료한 뒤 시작합니다. DEMO 실행에는 뉴스·OpenAI 요청이 없습니다.

수동 실행은 `ENABLE_CLOUDFLARE` Variable 없이도 가능합니다. 지속적인 main push 배포를 활성화하려면 다음 Variables를 설정합니다.

[GitHub Actions Variables 설정](https://github.com/dlwo8520/today-issue/settings/variables/actions)

| Variable | 처음 사용할 값 | 의미 |
|---|---|---|
| `ENABLE_CLOUDFLARE` | `true` | main push의 Cloudflare 배포 활성화 |
| `CLOUDFLARE_PROJECT_NAME` | 필요 시 `today-issue-dlwo8520` | 생략하면 같은 기본 이름 사용 |
| `NEWS_MODE` | `demo` 또는 생략 | 자동 배포의 데이터 모드 |

기존 `ENABLE_PAGES`는 이번 Cloudflare workflow에서 사용하지 않습니다. private 소스 저장소는 그대로 유지합니다. DEMO 모드에서는 의미 없는 일일 재배포를 피하기 위해 schedule을 건너뜁니다.

## 4. 실제 뉴스와 일일 자동 갱신

사용자가 GNews·NewsData 모두 무료 플랜이라고 확인하여 설정의 `account_plan`을 `free`로 기록했습니다. 대시보드나 계약을 직접 조회한 확인과는 구분합니다. 현재 광고·결제 기능은 없습니다. 무료 플랜의 공개 이용 조건과 사진 권한은 [NEWS_USAGE_REVIEW.md](NEWS_USAGE_REVIEW.md)를 확인합니다.

뉴스 이용 범위는 아직 `local_private`, `public_reuse_granted=false`입니다. 첫 원문 사진의 공개 사용 권한 확인 또는 사진 없는 공개판 선택이 남아 있어 기존 비공개 결과의 플래그만 바꾸어 업로드하지 않습니다.

확인 뒤 진행할 항목:

1. `config/news_apis.json`에 `usage_scope=public`, `public_reuse_granted=true`, 확인 근거 `permission_reference`를 기록합니다.
2. Secrets에 `GNEWS_API_KEY`, `NEWSDATA_API_KEY`, `OPENAI_API_KEY`를 설정합니다. 로컬 `.env`는 업로드하지 않습니다.
3. Variable `OPENAI_MODEL`을 설정합니다. 현재 로컬 평가 모델은 `gpt-5.4-mini`입니다.
4. 수동 mode `live` 실행으로 공개 가능한 새 데이터를 생성·검증·배포합니다.
5. 실제 원문·사진·정렬·갱신 시각·상세 URL을 확인합니다.
6. `NEWS_MODE=live`, `ENABLE_CLOUDFLARE=true`로 예약을 활성화합니다.

현재 설정은 최근 2주·최신 기사 발행 순·검증 통과 최대 6개, 뉴스 시도 최대 26회·GPT 시도 최대 18회입니다. cron은 UTC `0 22 * * *`, KST 오전 7시입니다. 예약은 지연·누락 가능성이 있어 정확한 시각 보장이 아닙니다. [GitHub schedule 설명](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)

이전 공개 정상 에디션을 `news-state`에서 복원한 뒤 갱신 실패 시 이전 에디션과 오류 상태를 배포할 수 있습니다. 첫 발행이 실패하거나 유효한 이전 데이터가 없으면 배포를 중단합니다. 원자료·GPT 캐시·상세 로그는 공개 artifact에 넣지 않습니다. 수집 이력의 별도 원격 보관은 추가 운영 항목입니다.

## 5. 도메인 연결

기본 주소에서 공개 동작을 확인한 뒤 원하는 도메인을 추가합니다.

- 도메인이 없는 경우: 등록 가능 여부와 첫해·갱신 요금을 확인한 뒤 구매합니다. 구매는 이번 코드 작업에 포함하지 않았습니다.
- 보유 도메인인 경우: Pages 프로젝트의 **Custom domains**에서 도메인을 등록합니다.
- `example.com` 같은 apex는 같은 Cloudflare 계정에 zone을 추가하고 nameserver를 연결해야 합니다.
- `news.example.com` 같은 서브도메인은 외부 DNS의 CNAME을 Pages 주소로 연결할 수 있습니다.
- HTTPS와 대표 주소를 확인합니다. 기존 메일 등을 사용하는 DNS 레코드는 유지합니다.

[Cloudflare 공식 사용자 도메인 안내](https://developers.cloudflare.com/pages/configuration/custom-domains/)

## 6. 로컬에서 공개 빌드 확인

```powershell
.\.venv\Scripts\python.exe scripts/build_public.py --mode demo
python -m http.server 4180 --bind 127.0.0.1 --directory .tools/public-deploy/dist
```

출력은 `.tools/public-deploy/dist`이며 기존 로컬 private `dist`를 덮어쓰지 않습니다. 새로운 환경은 먼저 `npm ci`와 `requirements.lock.txt` 설치를 완료합니다.

공개용 DEMO ZIP이 제공된 경우 내용의 최상위에 `index.html`이 있는 완성된 정적 파일입니다. Cloudflare Direct Upload의 수동 업로드에도 사용할 수 있지만, 일일 자동 갱신에는 Actions Secrets와 workflow 연결이 필요합니다.

## 7. 이번 검증과 남은 검증

- Python 100개 통과, Ruff 통과. 새 공개 빌드·프로젝트 생성 검사 8개를 포함합니다.
- 프론트 20개 통과, TypeScript·공개 DEMO 프로덕션 빌드 성공.
- 공개 빌드 정적 서버의 PC·태블릿·모바일·키보드·오류 복구 Playwright 5개 통과.
- DEMO 결과의 private latest/status·원자료·사진 파일 제외와 원본 보존 확인.
- [원격 GitHub CI](https://github.com/dlwo8520/today-issue/actions/runs/38499480332)는 Python 100개·프론트 20개·DEMO 브라우저 5개를 통과했습니다. 자동 배포를 켜지 않아 prepare/deploy는 건너뛰었습니다.
- Cloudflare 프로젝트 생성·Production 배포 성공과 실제 HTTPS 주소를 확인했습니다.
- 실제 Production 주소에서도 PC·태블릿·모바일·상세 새로고침·키보드·오류 복구 Playwright 5개를 통과했습니다. 반복 실행을 고유 검사 개수에 더하지 않습니다.
- 공개 `/data/demo.json`은 `mode=demo`, `publicationScope=public`, 이슈 6개입니다. `/data/latest.json`에는 비공개 Live JSON이 없습니다.
- GitHub Secrets 등록·Actions 배포·실제 뉴스 공개·일일 갱신·사용자 도메인은 아직 완료하지 않았습니다.

관련 문서: [배포 후보](HOSTING_OPTIONS.md), [전체 1차 개발 정리](PHASE_1_REPORT.md), [공개 운영 체크리스트](LIVE_LAUNCH_CHECKLIST.md).
