# 최근 2주 API 수집·선정·Live 실행

현재 기준은 실행 시각 직전 336시간, 복수 출처 사건, 최신 기사 발행 순, 검증 통과 최대 6개입니다. 실제 GNews·NewsData·OpenAI 연결과 로컬 Live 검증을 완료했습니다. [전체 개발 정리](PHASE_1_REPORT.md), [화면 수정](UI_REVISION.md)

## 수집과 실제 제공 범위

GNews top-headlines는 ko/kr, category general, max 10으로 14개 날짜 구간을 조회합니다. 최근 6개 구간은 page 2까지 보강합니다. GNews 관련 search 기능은 구현되어 있지만 현재 max_gnews_related_queries=0이며 총 GNews 상한은 20회입니다. 빈 검색 결과가 관측되어 날짜·페이지 수집을 우선하도록 조정했습니다.

NewsData latest는 ko/kr, size 10, 관련 q로 최대 6회 보강합니다. latest 자체의 범위는 최근 48시간입니다. 2주 전체나 권한을 확인하지 않은 유료 archive 기능을 제공한다고 가정하지 않습니다. 로컬 api-history.json에는 실제 확보한 자료만 보관하고 매 실행 시 336시간 밖의 기사를 제외합니다.

공급자의 요청당 제한과 상한 때문에 기간 내 모든 기사를 수집하는 구조는 아닙니다. 2026-10-14 사용자가 두 API 모두 무료 플랜이라고 확인하여 `account_plan`에 `free`를 기록했습니다. 대시보드를 직접 조회한 검증은 아닙니다. 공개 조건은 [뉴스 이용 조건 확인](NEWS_USAGE_REVIEW.md)을 따릅니다. 개발 시 참고한 공식 문서: [GNews 날짜 필터](https://docs.gnews.io/endpoints/top-headlines-endpoint), [GNews search](https://docs.gnews.io/endpoints/search-endpoint), [NewsData 범위](https://newsdata.io/documentation).

응답 완료 후 GNews 1.25초, NewsData .25초 간격을 둡니다. GNews의 429 속도 제한과 403 일일 quota를 구분합니다. API 뉴스 기본 재시도는 0회이며 4xx 오류를 무한 재시도하지 않습니다. [GNews 오류](https://docs.gnews.io/error-handling)

## 공통 데이터와 사건 겹침

Article은 제목·설명·제공 content/excerpt·원문 URL·실제 매체·발행 시간대·수집 시각·providers·원출처·관측 관심도·사진 URL을 보존합니다. NewsData pubDateTZ와 명시 시간대를 사용하며 시간대 없는 값을 임의로 해석하지 않습니다. null·프리미엄 안내·잘림 표시는 기사 사실로 사용하지 않습니다.

동일 URL은 공급자 이력을 합쳐 1건으로 정리합니다. 같은 매체의 제목 재전송, 별칭, 알려진 통신사 전재를 처리합니다. 실제 원매체를 식별하지 못한 Daum/Naver 재게시는 독립 언론사로 세지 않습니다. 사진 정보는 중복 병합에서 보존합니다.

문자 2·3·4-gram TF-IDF와 complete-link를 사용하고 336시간 안의 후속 보도를 허용합니다. 명시 날짜·반대 행동·다른 기관 제약은 유지합니다. 표기 차이와 구체적 사건어·공통 당사자·문맥 유사도를 함께 검사합니다. 같은 국가 이름이나 일반 사건어 한 개만으로 합치지 않습니다.

## 최신순 최대 6개

후보는 같은 사건의 실제 언론사 2곳·추정 독립 원출처 2개 이상과 출처별 최소 50자의 제공 설명을 요구합니다. GNews 기사 포함이 필수는 아닙니다.

selection_strategy=latest에 따라 사건 내 가장 최근 기사 발행 시각 순으로 후보를 검증합니다. 기존 관심도 조건부 정렬은 이전 7일 단계의 이력이며 현재 조회수·댓글수·보도량은 선택 순서의 우선순위로 사용하지 않습니다. 관측 관심도 결측은 null입니다. API 배열 위치·source_priority·감정 점수를 인기 지표로 바꾸지 않습니다.

최대 12개 후보를 보관하고 요청 예산 안에서 최신순으로 처리하여 검증 통과 결과 최대 6개를 저장합니다. 검증 실패나 예산 소진 시 더 적게 발행할 수 있습니다. 표시 출처는 최신 기사 우선, GPT 입력은 충분한 텍스트를 우선하는 안정된 순서를 사용합니다. rankingMethod의 기존 coverage_recency 표기는 출력 호환을 위해 유지됩니다.

## GPT와 사진

OpenAI Responses API Structured Outputs의 근거 추출 → 요약 → 별도 검토를 사용합니다. 모델은 sourceId/spanId를 선택하고 코드가 정확한 인용 구간을 연결합니다. 핵심 문장·출처·수치·주장 주체·상충 보도를 확인하고 근거 없는 배경·반응은 생략합니다. 핵심 검증 실패 후보는 제외합니다. store=False, SDK 재시도 0회, 타임아웃 45초입니다. [구조화 출력](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)

현재 로컬 모델은 gpt-5.4-mini이며 OPENAI_MODEL로 변경합니다. 모델·자료·프롬프트·스키마가 같은 결과는 캐시를 재사용합니다. 자동 검토는 독립적인 사실 확인의 보장이 아닙니다. 화면의 문장별 번호와 선정 설명은 제거했지만 내부 근거와 상세 원문 링크는 유지합니다.

홈과 상세는 첫 번째 원문의 API 사진 URL을 표시합니다. 누락된 경우 그 원문 head의 og:image/twitter:image를 최대 512KiB·최대 3리다이렉트·공개 주소 검증으로 보완합니다. 기사 HTML 전문은 저장하거나 요약에 쓰지 않으며 사진 파일을 복사하지 않습니다. 로드 실패 시 사진 영역을 숨깁니다.

## 기본 상한

| 설정 | 현재 값 |
|---|---:|
| 수집·그룹화 | 336시간 |
| GNews 날짜 구간 / 추가 페이지 구간 | 14 / 6 |
| GNews 관련 search | 0회 |
| GNews / NewsData 요청 시도 | 20 / 6회 |
| 뉴스 요청 시도 총합 | 26회 |
| GPT 요청 시도 / 최대 성공 이슈 | 18회 / 6개 |
| 요청당 기사 | 10개 |
| 뉴스·스냅샷 TTL | 6시간 |
| 뉴스 HTTP 크기 / 타임아웃 | 2MiB / 15초 |

실패도 요청 시도 예산에 포함하고 캐시 hit는 새 요청으로 세지 않습니다. 제공된 응답 토큰과 기록된 모델 요율로 비용을 추정하며 청구서와 구분합니다. 뉴스 구독비·세금·환율은 미포함입니다.

## 실행

~~~powershell
.\.venv\Scripts\python.exe -m pipeline.run --mode live --dry-run
.\.venv\Scripts\python.exe -m pipeline.run --mode live --stage probe --providers gnews
.\.venv\Scripts\python.exe -m pipeline.run --mode live --stage probe --providers newsdata
.\.venv\Scripts\python.exe -m pipeline.run --mode live --stage collect
.\.venv\Scripts\python.exe -m pipeline.run --mode live --stage select --from-cache
.\.venv\Scripts\python.exe -m pipeline.run --mode live --stage summarize --from-cache
.\.venv\Scripts\python.exe -m pipeline.run --mode live --stage live --from-cache
.\.venv\Scripts\python.exe scripts/report_usage.py
~~~

summarize는 한 건 미리보기, live는 최종 저장입니다. --from-cache는 기존 수집 기준 시각을 유지하고 기간 변경·TTL 만료 시 새 수집을 요구합니다. --fresh는 캐시를 무시합니다. 각 요청 상한은 CLI로 더 작게 제한할 수 있습니다. 키 설정과 프론트 실행은 [README](../README.md)에 있습니다.

## 파일·보안·현재 결과

- public/data/latest.json, status.json: 로컬 Live 화면 결과
- data/raw/api-collected.json, api-history.json: 스냅샷과 수집 이력
- data/raw/summary-preview.json: 한 건 미리보기
- data/cache: 뉴스·GPT·사진 메타데이터 캐시
- data/reports/history, usage-total.json: 실행 이력·누적 사용량

현재 이력 포함 291건 → 285건 분석 → 270그룹 → 후보 8개 → 검증 통과 6개입니다. 같은 캐시의 최종 재실행은 새 뉴스·GPT 호출 없이 성공했습니다. 세부 결과는 [전체 정리](PHASE_1_REPORT.md)와 [검증](VALIDATION.md)에 있습니다.

키·원문·캐시·비공개 보고서·Live JSON·private 빌드·실제 사진 캡처는 Git과 전달 ZIP에서 제외합니다. usage_scope=local_private, public_reuse_granted=false를 유지하며 validate_public.py는 private 데이터의 외부 배포를 거부합니다. 공개 운영은 이용 범위 확인과 [배포 준비](DEPLOYMENT.md)를 완료한 뒤 활성화합니다.
