# 오늘의 잇슈 — 초기 DEMO·RSS 구현 보고서

이 문서는 첫 DEMO 구현 단계의 이력입니다. 이후 같은 프로젝트에 실제 GNews·NewsData·OpenAI 연동과 로컬 Live 검증을 완료했습니다. 현재 결과는 [README](../README.md), [API 구현](API_LIVE_INTEGRATION.md), [최신 검증](VALIDATION.md), 로컬 비공개 API 결과 보고서(저장소 업로드 제외)에 있습니다. 아래의 실제 API 미실행 설명은 초기 단계의 상태입니다.

2026-10-13 KST. 결과물 위치: `C:\Users\uos\Desktop\project\today-issue`.

## 1. 프로젝트 개요
하루 한 번 최대 6개 사건을 쉽게 설명하는 정적 뉴스 큐레이션 서비스다. 정보 과잉과 반복 보도, 어려운 용어를 줄이는 읽기 경험을 중심으로 설계했다. 기존 프로젝트가 없는 빈 작업 폴더에 독립 프로젝트로 구현했다.

## 2. 구현 완료 기능
반응형 6개 카드, 700px 상세 읽기 영역, 원문 링크 UI, 문장별 출처, 선택적 용어와 반응, URL 복사, KST 시각, DEMO/Live 분리, 로딩/빈 데이터/오류/오래된 데이터 상태를 구현했다. Python RSS 어댑터·정규화·그룹화·선정·GPT 3단계 처리·검증·JSON 저장, 자동화와 정적 배포 설정도 구현했다. 실제 외부 운영의 완료 상태는 5·12번에서 구분한다.

## 3. 주요 파일과 역할
`src/App.tsx`와 `src/pages`는 화면과 hash 라우팅, `src/types/news.ts`는 JSON 입력 검증이다. `pipeline/sources.py`, `normalize.py`, `grouping.py`, `ranking.py`는 수집과 선정, `summarize.py/prompts.py`는 AI 처리, `storage.py/run.py`는 안전한 저장과 CLI다. `config`는 소스 권한·가중치, `.github/workflows/daily.yml`은 검증·발행·배포, `tests`는 검증, `docs`는 PRD·설계·출처·운영·결과를 담는다.

## 4. 기술 스택과 이유
React·TypeScript·Vite·Tailwind CSS로 정적 화면을 구성하고 Python·Pydantic·httpx·feedparser·OpenAI SDK로 하루 한 번 데이터를 생성한다. DB나 상시 서버 없이 목적을 달성할 수 있어 서버 프레임워크와 사용자 DB를 제외했다. LangChain 없이 직접 SDK를 사용해 호출·검증 흐름을 명확히 했다. 문자 TF-IDF는 CPU에서 실행되고 모델 가중치가 필요 없다.

## 5. 뉴스 수집 및 실제 연결 상태
실제로 진단한 8개 후보 중 동아·한겨레·경향·연합·매경·한경 RSS는 읽을 수 있었다. 서울신문·YTN의 후보 경로는 404였다. 확보한 피드에서 검사한 조회수·댓글수 필드는 없었다. 이 결과는 합법적 공개 재사용 계약 확보와 별개다. 동아·한겨레의 공식 제한을 확인했고, 모든 소스는 공개 활용 및 OpenAI 처리 권한 미확보로 비활성 상태다. 전체 기사 HTML이나 사진을 가져오지 않았다. 진단 자료는 `data/source-probe.json`에 있다.

## 6. 이슈 선정 알고리즘
제목의 문자 n-gram TF-IDF·코사인 유사도와 기관·발행 시간·명시 날짜·반대 행동 제약으로 complete-link 그룹화한다. 실제 제공되는 관심도는 언론사 내부에서 정규화하고 결측은 null로 보존한다. 관심도가 없으면 다양성·알려진 독립성·최신성·excerpt 충분성으로 재정규화한다. 반복 기사와 명시 통신사 전재의 중복 가산을 줄이고 최소 2개 원출처를 요구한다. 적격 수가 부족하면 가짜 기사로 채우지 않는다.

## 7. GPT 요약 및 검증
공식 OpenAI 문서를 확인한 Responses API의 Structured Outputs를 사용한다. 정확한 인용을 가진 사실/주장 추출, 쉬운 요약 생성, 별도 세그먼트 검토를 수행한다. 코드로 형식·출처 존재·인용 존재·주장 주체·전체 검토·새 수치·용어 사용·충돌 처리를 검사한다. 불합격 후보는 게시하지 않는다. 실제 API 호출은 미실행이며 실제 SDK와 모의 HTTP 응답으로 연동을 검증했다. 자동 검토를 완전한 사실 확인이라고 설명하지 않는다.

## 8. 실제 테스트 결과
Python 42개, 프론트엔드 17개, 브라우저 5개가 통과했다. Python 품질 검사, TypeScript 검사, 프로덕션 빌드가 성공했다. 브라우저 5개는 개발 서버와 `/today-issue/` 하위 경로의 프로덕션 정적 파일에서 각각 통과했다. PC·태블릿·모바일의 홈/상세에서 axe 위반 0개였다. 프로덕션 의존성 audit는 0건이었다. 자세한 범위와 한계는 `docs/VALIDATION.md`에 있다.

## 9. 로컬 실행 명령
```powershell
cd C:\Users\uos\Desktop\project\today-issue
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\dev.ps1
```
현재 준비된 portable Node 또는 설치된 Node를 사용한다. 다른 환경에서는 `npm ci` 후 `npm run dev`를 실행한다. Python은 `.venv` 생성 후 `requirements.lock.txt`를 설치하고 `python -m pipeline.run --mode demo`를 실행한다. DEMO에는 키가 필요 없다.

## 10. API 키 설정
`.env.example`을 `.env`로 복사해 `OPENAI_API_KEY`, `OPENAI_MODEL`을 본인의 값으로 설정한다. Python CLI가 `.env`를 읽고 기존 환경변수가 우선한다. 프론트에는 키를 전달하지 않는다. 허가된 소스를 설정한 후 `python -m pipeline.run --mode live`와 `dev.ps1 -Mode live`를 사용한다. 없는 키나 모델을 임의로 가정하지 않았다.

## 11. GitHub 배포
사용자 소유 저장소 main에 프로젝트를 올리고 Pages Source를 GitHub Actions로 선택한다. 기본은 DEMO이며 수동 실행에서 demo/live를 고른다. Live는 Secret `OPENAI_API_KEY`, Variables `OPENAI_MODEL`, `NEWS_MODE=live`, 소스 허가 설정이 필요하다. 예약은 UTC 22시로 다음 날 KST 7시다. 검증 후 생성 JSON과 화면을 함께 artifact로 배포하고 별도 데이터 커밋을 하지 않는다. 실패 시 이전 news-state artifact를 복원한다. 실제 원격 배포는 수행하지 않았다.

## 12. 아직 완료하지 않은 부분
실제 OpenAI 호출, 공개 활용 가능한 뉴스 계약/API 연결, 실제 사용자 반응/인기 순위 연결, Live 공개 발행, 원격 GitHub Actions/Pages 운영 검증은 미완료다. 권한이나 키가 없는데 완료한 것으로 보고하지 않는다. 회원가입·검색·개인화·결제 등은 미완료 문제가 아니라 명시적으로 제외한 MVP 범위다.

## 13. 알려진 한계
제목 기반 그룹화는 실제 사건을 완전히 구분하지 못하며 인간이 판정한 실제 뉴스 데이터로 아직 평가하지 않았다. 명시적 전재만 탐지한다. 같은 모델의 추가 검토도 오류를 반복할 수 있다. artifact 만료/삭제 시 이전 데이터 복원에 제한이 있다. 과거 에디션 아카이브가 없어 교체 이후 오래된 공유 URL이 사라질 수 있다. 정상 JSON과 status는 별도 원자적 쓰기로 전체 트랜잭션은 아니다. 스크린리더 수동 검사·사용자 조사·Lighthouse는 수행하지 않았다.

## 14. 다음 개선 우선순위
1. 공개 요약과 OpenAI 처리가 허용되는 소스/API 확보
2. 실제 뉴스의 사람 판정 데이터로 그룹화와 요약 평가
3. 공통 원출처·상충 주장에 대한 편집 검토 강화
4. 허가된 인기 순위 및 실제 관심도 지표 연결
5. 사용자 읽기 경험 검증 및 장기 공유 URL 보존

실행·설치·운영의 자세한 절차는 README, 기술 선택은 ARCHITECTURE, 실제 출처 상태는 SOURCES, 배포 권한과 복구는 DEPLOYMENT 문서에 정리했다.
