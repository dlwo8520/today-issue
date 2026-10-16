# Cloudflare 구성

문서 점검일: **2026-10-16 KST**

현재 사이트는 이미 배포되어 있습니다. 페이지를 보기 위해 계정을 새로 만들거나 GitHub Secrets를 등록할 필요는 없습니다.

**[사이트 열기](https://today-issue-dlwo8520.pages.dev)**

## 배포 정보

| 항목 | 값 |
|---|---|
| 프로젝트 | `today-issue-dlwo8520` |
| 방식 | Cloudflare Pages Direct Upload |
| 기본 주소 | `today-issue-dlwo8520.pages.dev` |
| production branch | `main` |
| 고정 에디션 배포 ID | `011d0882-ff68-4128-8a98-ac027a9ec839` |
| 데이터 생성 시각 | 2026-10-15 11:21:26 KST |
| 자동 뉴스 갱신 | 중지 |
| 별도 구매 도메인 | 연결하지 않음 |

위 배포 ID는 **10월 15일 고정 운영 전환 당시**의 확인 기록입니다. 이후 문서 수정 커밋은 이 배포와 별개입니다.

## 방문 흐름

1. 기본 주소에서 지정된 이메일을 입력합니다.
2. 서버가 이메일을 비교하고 입장 쿠키를 발급합니다.
3. 브라우저가 화면 파일과 저장된 뉴스 JSON을 읽습니다.

기본 주소는 메일 인증번호를 요구하지 않습니다. 이전 개별 배포 주소의 Cloudflare Access 보호는 유지합니다. [입장 방식 상세](CLOUDFLARE_PRIVATE_SETUP.md)

## 운영 설정

고정 서비스를 유지하는 데 뉴스 API나 OpenAI Secrets 등록은 필요하지 않습니다. 현재 workflow는 **Source checks**이며 뉴스 생성과 Cloudflare 배포 작업이 없습니다.

Cloudflare의 기존 production 설정에는 다음 서버 값이 있습니다.

| 이름 | 역할 |
|---|---|
| `PERSONAL_EMAIL` | 입장을 허용할 이메일 |
| `PERSONAL_SESSION_SECRET` | 쿠키 서명용 비밀 값 |

이 값은 브라우저 코드와 문서에 넣지 않습니다. 현재 갱신 차단 정책은 [고정 운영](FROZEN_EDITION.md)을 따릅니다.

## 빌드 산출물

| 목적 | 도구 | 출력 |
|---|---|---|
| 기존 실제 뉴스·이메일 입장 유지 | `scripts/build_private.py` | `.tools/private-deploy/dist/` |
| 가상 DEMO 확인 | `scripts/build_public.py --mode demo` | `.tools/public-deploy/dist/` |

개인용 빌드는 기존 Cloudflare 보호 설정을 조회하고, 저장된 실제 뉴스 파일을 사용합니다. 새 뉴스나 GPT 요약을 만들지 않습니다. 실행 환경과 소스 전달은 [배포와 운영](DEPLOYMENT.md)을 확인하세요.

## 이전 구성과의 차이

10월 14일 첫 배포는 DEMO였고, 이후 실제 뉴스와 사진을 포함한 이메일 입장 방식으로 바꿨습니다. 10월 15일에는 에디션을 고정하고 생성·배포 자동화를 제거했습니다.

과거 문서의 **Cloudflare edition → Run workflow**, `mode private`, 오전 7시 예약 설정은 현재 workflow에 존재하지 않습니다. 현재 상태는 이 문서와 [고정 운영](FROZEN_EDITION.md)을 기준으로 확인합니다.
