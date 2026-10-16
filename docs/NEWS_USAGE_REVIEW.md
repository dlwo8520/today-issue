> **개발·조사 이력 — 2026-10-14 뉴스 이용 조건 조사**
> 아래 내용은 각 항목의 작성 당시 기록입니다. 현재는 2026-10-15 11:21 KST 고정본을 유지하며 GPT·뉴스 API와 갱신을 중지했습니다. 실행 절차는 [시작하기](GETTING_STARTED.md), 운영 상태는 [고정 운영](FROZEN_EDITION.md)을 따릅니다.

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

사용자는 사진을 유지하는 개인 확인용을 선택했습니다. Cloudflare에 사진을 포함한 Live를 배포했고, 이후 메일 인증 없이 지정 이메일 입력만으로 입장하도록 변경을 요청하여 적용했습니다.

`usage_scope=local_private`, `public_reuse_granted=false`, `permission_reference=null`을 유지하며 Live JSON을 public으로 재표시하지 않습니다. 서버에서 이메일을 비교하고 서명 쿠키가 있어야 뉴스 파일을 제공합니다. 이는 본인 인증이 아니며 같은 이메일을 아는 사람도 입장할 수 있습니다. 이전 개별 배포 주소는 Cloudflare Access로 보호합니다. [현재 개인용 운영 안내](CLOUDFLARE_PRIVATE_SETUP.md)

무료 플랜은 제공 텍스트가 짧고 지연될 수 있으므로 근거가 부족한 후보는 제외합니다. 개인용 결과를 공개 서비스로 전환할 때는 사진과 뉴스 이용 조건을 다시 확인합니다.

## 후속 운영 변경

2026-10-15에 기존 에디션을 고정하고 GPT·뉴스 API 호출과 자동·수동 갱신을 중지했습니다. 현재 상태는 [고정 운영](FROZEN_EDITION.md)을 기준으로 확인합니다.

이 문서는 10월 14일에 확인한 이용 조건과 구현 상태의 기록입니다.
