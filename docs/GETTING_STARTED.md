# 시작하기

이 문서는 **화면 실행**, **기존 실제 뉴스 확인**, **개발 검증** 순서로 안내합니다. 모든 명령은 `package.json`이 있는 프로젝트 폴더에서 실행합니다.

## 1. 무엇을 실행할지 선택하기

| 목적 | 필요한 것 |
|---|---|
| DEMO 화면 확인 | Node.js 24·npm |
| 실제 뉴스 고정본 확인 | Node.js 24·npm, 기존 `public/data/latest.json` |
| Python 테스트·패키징 | Python 3.13·Python 패키지 |

**DEMO에는 API 키와 `.env`가 필요하지 않습니다.** 가상 사건과 가상 매체 6개로 화면을 확인합니다.

`live` 모드도 현재는 저장된 고정본만 읽습니다. GitHub에서 새로 받은 소스에는 실제 뉴스 파일이 없으므로 DEMO부터 사용하세요.

## 2. Windows에서 DEMO 실행

### 준비 확인

Node.js 24와 npm이 설치된 터미널에서 버전을 확인합니다.

~~~powershell
node --version
npm.cmd --version
~~~

이 프로젝트는 Node 24 환경에서 검증했습니다. 명령을 찾지 못하면 Node 설치를 완료한 뒤 터미널을 다시 엽니다. 기존 작업 폴더의 portable Node를 사용하는 방법은 아래 5번에 있습니다.

### 패키지 설치 — 처음 한 번

~~~powershell
npm.cmd ci
~~~

이 명령은 `package-lock.json`에 맞춰 화면 패키지를 설치합니다. 소스를 다시 받은 경우나 의존성이 변경된 경우에도 실행합니다.

### 화면 실행 — 사용할 때마다

~~~powershell
$env:VITE_DATA_MODE = 'demo'
npm.cmd run dev
~~~

- 터미널에 표시된 주소를 브라우저에서 엽니다. 기본 주소는 [http://127.0.0.1:5173/](http://127.0.0.1:5173/)입니다.
- 실행 중에는 터미널을 열어 둡니다.
- 종료할 때는 `Ctrl+C`를 누릅니다.

`npm.cmd`는 Windows PowerShell의 스크립트 실행 정책에 영향을 덜 받도록 사용한 표기입니다.

## 3. 기존 실제 뉴스 고정본 확인

기존 작업 폴더에서 파일 유무를 확인합니다.

~~~powershell
Test-Path -LiteralPath .\public\data\latest.json
~~~

결과가 `True`이면 다음 명령을 실행합니다.

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Mode live
~~~

결과가 `False`이면 이 폴더에는 실제 뉴스 고정본이 없습니다. DEMO를 사용하거나 [기존 배포 사이트](https://today-issue-dlwo8520.pages.dev)에서 확인합니다.

기존 `.env`를 복사하거나 수정할 필요는 없습니다. 화면 실행은 저장된 JSON만 읽으며, `config/service.json`의 갱신 중지 정책도 그대로 유지됩니다.

## 4. macOS·Linux에서 DEMO 실행

Node.js 24와 npm을 준비한 뒤 실행합니다.

~~~bash
npm ci
VITE_DATA_MODE=demo npm run dev
~~~

기존 실제 뉴스 파일이 있는 환경은 `VITE_DATA_MODE=live npm run dev`로 표시 모드만 바꿀 수 있습니다.

## 5. Windows 보조 실행 스크립트

기존 작업 폴더에 portable Node가 준비되어 있다면 다음 한 줄로도 DEMO를 실행할 수 있습니다.

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Mode demo
~~~

이 스크립트는 설치된 Node 또는 프로젝트의 `.tools/node-*-win-x64`를 사용하고, `node_modules`가 없으면 패키지를 설치합니다. 둘 다 없으면 **Python의 `python` 명령**으로 공식 Node 도구를 내려받습니다.

따라서 Node와 Python이 모두 없는 새 환경은 **2번의 Node 설치 후 실행 방식**으로 시작하세요. 보조 스크립트는 기존에 설치된 Node의 버전을 교체하지 않습니다.

## 6. Python 개발 환경 — 필요한 경우에만

Python 테스트, 안전한 배포 빌드, 소스 패키징을 실행할 때 준비합니다. DEMO 화면만 보는 경우 이 절은 건너뜁니다.

Windows에서 Python 3.13을 선택한 뒤, 가상환경이 없다면 생성합니다.

~~~powershell
python --version
python -m venv .venv
~~~

가상환경의 Python으로 패키지를 설치합니다. 이미 `.venv`가 있으면 생성 단계는 생략합니다.

~~~powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
~~~

macOS·Linux에서는 같은 가상환경의 Python 경로가 `.venv/bin/python`입니다.

현재 고정 운영에는 뉴스·OpenAI 키 등록이 필요하지 않습니다. 이전 API 설정 과정은 [API 구현 이력](API_LIVE_INTEGRATION.md)에 보존했습니다.

## 7. 자주 만나는 상황

| 상황 | 확인할 내용 |
|---|---|
| `node` 또는 `npm.cmd`를 찾을 수 없음 | Node.js 24 설치 후 새 터미널을 열었는지 확인 |
| `npm.ps1` 실행 정책 오류 | Windows 명령은 문서처럼 `npm.cmd` 사용 |
| `package.json`을 찾을 수 없음 | 압축 해제한 프로젝트 폴더에서 터미널을 열었는지 확인 |
| 5173 대신 다른 주소가 표시됨 | 이미 해당 포트를 사용 중일 수 있으므로 터미널에 나온 실제 주소로 접속 |
| Live 데이터 로드 실패 | `public/data/latest.json`이 있는 기존 작업 폴더인지 확인 |
| Live CLI가 `Updates disabled`로 종료됨 | 현재 고정 운영의 정상 동작; API 호출과 파일 변경 없음 |
| 브라우저 테스트가 기존 Live 화면을 읽음 | [검증 안내](VALIDATION.md)대로 별도 DEMO 포트 사용 |

다음으로 [검증 방법](VALIDATION.md) 또는 [전체 문서](README.md)를 확인할 수 있습니다.
