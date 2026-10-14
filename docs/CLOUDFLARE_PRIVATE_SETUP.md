# 오늘의 잇슈 — 사진과 이메일 입력 입장

기준일: 2026-10-14 KST

**접속 주소: [오늘의 잇슈](https://today-issue-dlwo8520.pages.dev)**

실제 이슈 6개와 첫 원문 사진 6개를 제공합니다. 지정 이메일 입력만으로 입장하며 메일 인증번호·비밀번호를 요구하지 않습니다. 이는 본인 인증이 아니므로 같은 이메일을 아는 다른 사람도 입장할 수 있습니다.

## 현재 동작

- 서버에서 이메일을 비교합니다. 허용 이메일과 서명 키는 브라우저 코드에 넣지 않습니다.
- 입장 후 Secure·HttpOnly·SameSite 쿠키를 사용하며 유효 기간은 30일입니다.
- 입력 전에는 홈·뉴스 JSON·상태 JSON·JS/CSS 자산을 제공하지 않습니다. 잘못된 이메일은 거부합니다.
- 서명 키 설정이 없거나 잘못되면 파일을 제공하지 않습니다.
- 기본 주소의 Access OTP 앱을 제거하고 Pages Worker가 전체 요청을 처리합니다.
- Worker가 없는 이전 Live 배포를 보호하기 위해 wildcard Access 앱을 유지합니다. 개별 배포 주소는 기존 OTP가 적용되므로 위 기본 주소를 사용합니다.

## 실제 데이터와 검증

2026-10-14 17:33 KST에 새 수집을 시작하여 이력 포함 451건 → 분석 440건 → 413그룹 → 적격 후보 17개 → 검증 통과 6개를 생성했습니다. 에디션 갱신 시각은 17:35 KST입니다. 최근 2주·최신 기사 발행 순·최대 6개 설정을 유지했습니다.

현재 배포 ID는 `52cfcbf5-8351-43bd-a577-c22148734c10`입니다. 실제 결과 JSON과 사진 URL은 소스 저장소에 넣지 않습니다. 수집과 JSON의 범위는 `local_private`를 유지하며 이 메타데이터를 본인 인증의 보장으로 해석하지 않습니다.

Python 112개·이메일 입장 서버 8개·실제 주소 Live 브라우저 1개가 통과했습니다. 실제 서버에서 지정 이메일 입장·다른 이메일 거부·입력 전 JSON 차단·위조 쿠키 차단과 원격 데이터 일치를 확인했습니다. 브라우저에서는 이메일 입력부터 PC·모바일 뉴스·사진·상세 URL·목록 이동·접근성까지 확인했습니다.

구현은 `server/email-gate.mjs`, 개인용 빌드는 `scripts/build_private.py`입니다. 산출물 `.tools/private-deploy/dist`에는 `_worker.js`와 모든 경로를 포함하는 `_routes.json`이 반드시 있어야 합니다. [Worker 전체 요청 처리](https://developers.cloudflare.com/pages/functions/advanced-mode/), [Functions 경로 설정](https://developers.cloudflare.com/pages/functions/routing/).

## GitHub 자동 갱신

현재 Secrets는 미등록이므로 실제 일일 갱신은 활성화하지 않았습니다. [GitHub Actions Secrets](https://github.com/dlwo8520/today-issue/settings/secrets/actions)에 다음 5개 값을 등록합니다.

- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN`
- `GNEWS_API_KEY`
- `NEWSDATA_API_KEY`
- `OPENAI_API_KEY`

[Actions Variables](https://github.com/dlwo8520/today-issue/settings/variables/actions)에 다음을 설정합니다.

| Variable | 값 |
|---|---|
| CLOUDFLARE_ACCESS_EMAIL | 실제 입장에 사용하는 이메일 |
| NEWS_MODE | private |
| OPENAI_MODEL | gpt-5.4-mini 또는 선택한 모델 |
| ENABLE_CLOUDFLARE | 수동 private 배포 확인 후 true |

Cloudflare production에는 PERSONAL_EMAIL과 secret binding PERSONAL_SESSION_SECRET을 이미 설정했습니다. 같은 프로젝트에 계속 배포하면 기존 서버 설정을 사용합니다. 토큰은 Pages Edit 및 이전 배포 Access 설정 조회 권한을 유지해야 합니다. 서명 키·API 키를 소스에 적지 않습니다.

처음에는 **Cloudflare edition → Run workflow → mode private**로 확인합니다. 이후 KST 오전 7시 예약이 활성화됩니다. 예약 실행은 지연될 수 있습니다. 실패 시 유효한 이전 private 에디션을 복원하며 공개 news-state와 개인용 private-news-state를 섞지 않습니다.

개인용 빌드는 `python scripts/build_private.py`입니다. Worker가 없는 과거 Live로 기본 주소를 rollback하면 입장 제한이 빠질 수 있으므로 해당 배포로 되돌리지 않습니다. 공개판 운영 절차는 [기존 배포 안내](CLOUDFLARE_SETUP.md)에 보존했습니다.
