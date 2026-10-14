# 뉴스 출처 조사 및 사용 상태

## 추가된 공식 API 경로

2026-10-13에 GNews Top Headlines와 NewsData latest를 실제 호출하고 로컬 비공개 Live를 만들었습니다. `config/news_apis.json`이 API 전용 설정이며 기존 RSS 권한은 그대로 비활성입니다. API 인증 성공은 공개 뉴스 재사용 허가를 뜻하지 않습니다. 계정 플랜은 둘 다 `unknown`, 이용 범위는 `local_private`, 공개 재사용 플래그는 `false`입니다.

공개 무료 플랜에서 GNews는 100요청/일·10기사/요청·12시간 지연·잘린 content·개발/시험 이용을 안내합니다. NewsData는 200 credits/일·10기사/credit·12시간 지연·전문 제한을 안내합니다. 계정 대시보드의 실제 플랜·AI 처리·보관·공개 요약/메타데이터 사용 범위는 추가 확인 대상입니다. [GNews 공식 플랜](https://gnews.io/pricing), [NewsData 공식 플랜](https://newsdata.io/pricing), [NewsData 플랜 설명](https://newsdata.io/blog/pricing-plan-in-newsdata-io/)

실제 API 필드·본문 부족·원출처 정규화·요청 상한은 [API 문서](API_LIVE_INTEGRATION.md)에 있습니다. 아래 내용은 초기 RSS 조사와 **RSS 수집기**의 권한 요건입니다. 현재 기본 API Live 실행에 RSS 소스 활성화가 필요하지는 않습니다.

조사일: 2026-10-13 KST. 실제 네트워크 관측은 `data/source-probe.json`에 있다. 이는 RSS endpoint의 읽기 결과이며 기사 라이선스나 공개 서비스 허가의 증명이 아니다.

## 확인한 정책
- [동아일보 공식 RSS 안내](https://rss.donga.com/): 개인의 비상업적 사용을 안내한다. 이 프로젝트의 공개 요약·AI 전송까지 허가한다고 해석하지 않아 비활성화했다.
- [한겨레 공식 저작권 안내](https://oauth.hani.co.kr/help/rules/mypage_help_copyright.html?type=digital_use_rule): 개인 구독과 재배포를 구분한다. 공개 재사용 허가를 확보하지 않아 비활성화했다.
- 경향신문·연합뉴스·매일경제·한국경제: 해당 RSS를 읽을 수 있음을 확인했지만 공개 요약과 AI 처리 권한은 확인하지 않았다. 기본 비활성화한다.
- 서울신문·YTN: 후보 경로는 404였다. 매체 전체에서 RSS가 없다고 결론 내리지 않는다. 사용 가능한 공식 경로와 정책은 추가 확인 대상이다.

## 기술적으로 확인한 결과
동아 50, 한겨레 30, 경향 50, 연합 120, 매경 50, 한경 50항목이 파싱되었다. 항목 수는 직전 24시간 적격 기사 수나 독립 사건 수가 아니다. 모든 매체에서 기사 본문을 크롤링하지 않았고, 진단 파일에는 제목·요약·기사 전문을 저장하지 않았다.

관측한 피드에서는 `views/viewcount/commentcount/comments_count` 필드를 발견하지 못했다. 필드 이름을 모두 아는 완전한 조사는 아니며 “매체에 조회수가 없다”라는 뜻도 아니다. 댓글 URL은 댓글 수로 변환하지 않는다. 공개 순위 피드 또는 허가된 API 계약도 확보하지 않았다. 따라서 실제 관심도 연결 완료로 보고하지 않는다.

## RSS Live 활성화 요건
`config/sources.json` 각 항목에 다음을 설정한다.

| 필드 | 의미 |
|---|---|
| enabled | 자동 수집에 사용할지 |
| reuseGranted | 공개 요약 및 출처 메타데이터 재사용이 허용되는지 |
| llmProcessingGranted | excerpt를 OpenAI로 보내 처리할 권한이 있는지 |
| permissionReference | 계약·허가·공개 라이선스를 확인할 식별 정보 |
| reviewedAt | 허가 확인일 |
| independenceKey | 원출처 조직, 통신사이면 wire key |
| assumedTimezone | timezone 없는 발행일이 명세상 특정 시간대인 경우에만 설정 |
| syndicationMarkers | 명시적 전재 원출처 식별을 보완하는 설정 |

첫 네 가지 권한 정보가 부족하면 enabled=true 설정을 거부한다. 단순히 플래그를 바꾸는 것이 실제 허가를 취득하는 행위는 아니다. 계약이 필요한 매체는 해당 절차를 완료한 후 설정해야 한다. 기본 설정에서는 활성 RSS 소스가 0개이므로 `--collector rss` 실행은 명확하게 실패하고 기존 본문을 보존한다.

## 확장
RSS 이외 어댑터는 `NewsSourceAdapter` 계약과 `collect_sources`의 registry를 이용해 추가할 수 있다. 초기 RSS 단계에서는 API를 연결하지 않았으나 이후 GNews·NewsData 공식 API의 실제 연동을 완료했다. 현재 구현은 상단 API 절과 API_LIVE_INTEGRATION.md를 기준으로 확인한다. 향후 계약된 API에 한해 Engagement 숫자·관측 출처·관측 시각을 함께 반환하면 현재 정규화 알고리즘을 사용할 수 있다.

기사 HTML 전문 수집, robots 제한 우회, 로그인/유료벽 우회, 비공개 포털 API는 구현하지 않았다. 현재는 첫 원문 head에서 제한된 사진 메타데이터 확인과 이미지 URL 연결을 제공한다. 사진 파일은 복사하지 않으며 공개 사용 범위는 별도 확인 대상이다. 공개 체험용 데이터는 가상 DEMO다.
