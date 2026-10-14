# 오늘의 잇슈 — 뉴스 API 무료 플랜과 공개 조건 확인

확인일: 2026-10-14 KST

사용자는 GNews·NewsData 모두 무료 플랜이라고 확인했습니다. `config/news_apis.json`의 `account_plan`에 `free`를 기록했습니다. 계정 대시보드를 직접 확인한 결과는 아니므로 실행 보고서의 `accountPlansVerified`는 계속 `false`입니다. 현재 제품에는 광고·결제 기능이 없습니다.

## 공식 이용 조건 확인

| 공급자 | 확인한 내용 | 프로젝트에 적용할 조건 |
|---|---|---|
| GNews | 무료 플랜은 개인·학술·평가 등 비상업적 이용 범위이며 상업적 이용에는 유효한 유료 구독이 필요합니다. 제3자 기사·사진의 권리가 자동 부여되는 것은 아닙니다. | 무료라는 이유만으로 모든 공개를 금지하지 않습니다. 개인 비상업적 범위를 유지하고 수익화·사업 목적 도입 전에 다시 확인합니다. |
| NewsData | 공식 블로그는 무료 플랜의 상업적 이용을 안내합니다. 정식 약관은 데이터와 미디어의 권리가 원 소유자에게 있고 이용자가 적용 법과 권리를 준수해야 한다고 설명합니다. | API 이용 조건과 원문·사진의 이용 권한을 구분합니다. |

근거: [GNews 이용 약관 §3.1·3.3·5.2·7](https://gnews.io/legal/terms-of-service), [NewsData 공식 무료 플랜 안내](https://newsdata.io/blog/top-free-news-apis/), [NewsData 약관의 DATA LICENSE·COPYRIGHT POLICIES](https://newsdata.io/terms).

GNews는 성능을 위한 합리적인 응답 캐시를 허용하지만 제한 우회·경쟁 서비스 목적의 대량 아카이브는 금지합니다. 현재의 제한된 로컬 캐시와 수집 이력을 무제한 공개 아카이브 허가로 해석하지 않습니다. [GNews 약관 §7](https://gnews.io/legal/terms-of-service)

## 사진과 실제 뉴스 전환

첫 원문 사진의 URL이 API나 OG 메타데이터로 제공된다는 사실만으로 재사용 권한을 확인할 수 없습니다. 출처 표시와 원문 링크를 붙였다는 이유만으로 사진 권한이 확보되지는 않습니다. 유료 API로 전환해도 언론사 사진 권리는 별도로 확인해야 합니다. [GNews 약관 §3.3](https://gnews.io/legal/terms-of-service), [NewsData 데이터 권리 조건](https://newsdata.io/terms)

공개판 진행 방식은 사용자에게 확인 중입니다.

- 사진 없이 실제 뉴스의 사실 중심 요약과 원문 링크부터 공개하는 방식
- 첫 원문 사진의 이용 권한을 확인한 뒤 사진을 포함해 공개하는 방식

현재는 기존 요청의 사진 기능을 유지하고 공개 설정을 바꾸지 않았습니다. `usage_scope=local_private`, `public_reuse_granted=false`, `permission_reference=null`이며 기존 private Live JSON을 public으로 재표시하지 않습니다. 공개 방식 결정 후 실제 사용 범위와 근거를 설정에 기록하고 새 공개 에디션을 생성·검증합니다. 무료 플랜은 제공 텍스트가 짧고 지연될 수 있으므로 근거가 부족한 후보는 제외합니다.

## 현재 공개 및 자동 갱신 상태

- [Cloudflare Production 주소](https://today-issue-dlwo8520.pages.dev)는 DEMO 이슈 6개이며 실제 뉴스로 오인하지 않도록 DEMO를 표시합니다.
- 첫 배포와 HTTPS·공개 주소 브라우저 검증을 완료했습니다.
- GitHub Actions Secrets는 사용자가 아직 미등록이라고 확인했습니다. 연결 도구는 Secrets 쓰기를 지원하지 않습니다.
- [Cloudflare 설정 문서](CLOUDFLARE_SETUP.md)의 Secrets 등록 후 Actions 배포를 확인합니다. 실제 뉴스 자동 갱신에는 뉴스·OpenAI Secrets 세 개도 필요합니다.

이 문서는 확인한 서비스 약관과 구현 상태를 기록한 것으로, 모든 원문과 사진의 이용 권한이 확보되었다는 보증은 아닙니다.
