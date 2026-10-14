# 소스 전달·배포·운영

현재 실제 API와 로컬 Live는 검증을 완료했습니다. 1차 GitHub 전달 대상은 키와 실제 뉴스 자료를 제외한 소스·DEMO·테스트·문서입니다. 공개 Live 서비스와 원격 예약·복구는 별도 운영 단계입니다. [전체 기록](PHASE_1_REPORT.md)

## 소스 업로드와 CI

.github/workflows/daily.yml은 main push와 PR에서 Secret 없이 Python·프론트·DEMO 브라우저를 검사합니다. 처음 저장소를 올리는 것만으로 Pages·뉴스 수집을 활성화하지 않습니다.

저장소 Variable **ENABLE_PAGES=true**를 설정해야 prepare/deploy가 실행됩니다. 해당 값이 없으면 schedule의 검사·발행도 건너뜁니다. cron 정의는 유지되어 있으며 활성화 시 0 22 * * * UTC, 즉 다음 날 KST 오전 7시입니다. 예약은 지연·누락될 수 있습니다.

.env·원문·캐시·진단·비공개 API 보고서·Live latest/status·private 빌드·실제 뉴스 사진 캡처는 업로드하지 않습니다. Vite에는 모드와 경로만 전달하며 API 키를 전달하지 않습니다.

## 공개 운영 전 설정

1. GNews·NewsData 실제 가입 플랜과 AI 전송·보관·공개 요약·메타데이터·사진 사용 범위를 확인하고 근거를 기록합니다.
2. 확인된 허가 범위에 따라 config/news_apis.json의 usage_scope·public_reuse_granted·permission_reference를 설정합니다. 플래그 변경 자체가 허가 취득은 아닙니다. RSS 권한은 별도입니다.
3. 저장소 Settings → Pages → Source에서 GitHub Actions를 선택합니다.
4. Secrets에 GNEWS_API_KEY·NEWSDATA_API_KEY·OPENAI_API_KEY를 설정하고 Variable OPENAI_MODEL을 지정합니다. Live 예약에는 NEWS_MODE=live를 사용합니다.
5. 계정별 예산을 확인한 뒤 ENABLE_PAGES=true를 설정하고 수동 demo/live 실행·예약·복구를 검증합니다.

[공식 Pages 안내](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages), [schedule 안내](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)

## 발행 동작과 예산

checks → prepare → deploy 순서이며 PR은 검사만 실행합니다. 활성화된 prepare는 이전 공개 news-state 복원, 새 Live 생성, 공개 범위 검사, artifact 보관, 선택 모드 빌드를 수행합니다. 기본 모드는 demo이며 수동 입력 또는 NEWS_MODE Variable로 변경합니다.

현재 기본 상한은 최근 2주 뉴스 26회(GNews 20·NewsData 6), GPT 18회, 성공 이슈 6개입니다. 복수 출처 사건을 최신 기사 발행 시각 순으로 검증하며 실패·예산 소진 시 더 적게 발행할 수 있습니다. --dry-run으로 실제 호출 전에 상한을 확인합니다.

publicationScope=local_private인 결과는 공개 artifact 생성 전에 거부됩니다. DEMO도 public 디렉터리를 복사하므로 private latest.json이 섞여 있으면 거부합니다. 공개 빌드 전에 python scripts/validate_public.py --mode demo 또는 --mode live를 실행합니다. 현재 로컬 config의 private 설정으로 Live를 선택하면 공개 검사를 통과하지 못합니다.

## 상태 복원과 권한

같은 workflow·main에서 생성된 공개 news-state artifact만 다운로드하고 스키마를 검증합니다. 보존 기간은 90일입니다. 정상 이전 에디션을 복원한 뒤 갱신이 실패하면 기존 데이터와 오류/stale 상태를 유지합니다. 첫 발행 실패 또는 유효한 이전 상태가 없으면 새 배포를 중단합니다. 원문·캐시·상세 로그·private 결과는 artifact에도 올리지 않습니다.

같은 ref는 직렬화합니다. 기본 contents:read, prepare actions:read/pages:read, deploy pages:write/id-token:write이며 github-pages 환경을 사용합니다. 실제 원격 실행 로그에서 복원·예약 동작을 확인해야 운영 검증 완료로 기록할 수 있습니다.

## 로컬 확인

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Mode live
$env:VITE_DATA_MODE='live'
npm run build
python -m http.server 4173 --bind 127.0.0.1 --directory dist
~~~

현재 dist에는 비공개 Live 자료가 포함되므로 외부 업로드하지 않습니다. hash 상세와 Vite base ./로 정적 경로·새로고침을 지원합니다. Live 실패를 DEMO로 대체하지 않습니다. 사용자가 실행 중인 서버는 유지하고 검사 목적으로 연 서버만 종료합니다.

API 인증·모델 오류는 로컬 설정과 계정 접근을, quota/429는 잔량·요청 상한·호출 간격을 확인합니다. 검증 실패를 해결하기 위해 검증을 꺼서 게시하지 않습니다. 잠금 파일은 실행 중인 해당 프로세스가 없다는 것을 확인한 뒤에만 처리합니다.

공개 전 전체 준비 항목은 [LIVE_LAUNCH_CHECKLIST](LIVE_LAUNCH_CHECKLIST.md)에 있습니다.
