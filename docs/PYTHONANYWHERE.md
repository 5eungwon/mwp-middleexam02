# PythonAnywhere 배포

대상 주소: https://asdfgh0986.pythonanywhere.com

과제 02 서버를 **2026년 11월 6일 17:38:14(한국 시간)**에 실제 배포했습니다. HTTPS 상태 API 200, 익명 API 접근 거부 401, JWT 로그인 200을 확인했습니다. 기존 DB 백업의 `PRAGMA integrity_check` 결과는 `ok`이며, 기존 프로젝트 파일과 DB는 원래 위치에 보존했습니다.

실제 YOLOv5n 추론에서 person 3개와 bus 1개를 검출했습니다. 감시 대상인 person의 새 출현 이벤트가 클라우드 게시물 **ID 1**로 생성됐고, 상세 API 200과 JPEG 이미지 200(320×240), 미확인 상태를 확인했습니다. 추가 클라우드 HTTP 검사 10개도 통과했습니다. 토큰과 비밀번호는 증빙에서 제외했습니다.

- 배포·백업 결과: `docs/evidence/cloud-deployment.json`
- 실제 YOLO → 클라우드 검증: `docs/evidence/cloud-edge-integration.json`
- 실제 클라우드 HTTP 검증: `docs/evidence/cloud-integration.json`

## 현재 운영 경로와 복구

| 항목 | 실제 배포 경로 |
|---|---|
| 소스 | `/home/asdfgh0986/home-guardian-assessment02/releases/20261106-083539/PhotoBlogServer` |
| Python / 가상환경 | 3.12 / `/home/asdfgh0986/.virtualenvs/home-guardian-assessment02` |
| DB | `/home/asdfgh0986/home-guardian-assessment02/data/db.sqlite3` |
| 미디어 | `/home/asdfgh0986/home-guardian-assessment02/data/media` |
| 정적 파일 | `/home/asdfgh0986/home-guardian-assessment02/releases/20261106-083539/PhotoBlogServer/staticfiles` |
| WSGI | `/var/www/asdfgh0986_pythonanywhere_com_wsgi.py` |
| 원본 백업 | `/home/asdfgh0986/photoblog-backups/before-assessment02-20261106-083539` |

백업 폴더에는 `previous-wsgi.py`, `previous-web-settings.json`, `previous-static-mappings.json`, `previous-project/`, `previous-database.sqlite3`가 있습니다. DB는 SQLite backup API로 복사한 뒤 무결성을 검사했습니다. 기존 과제 01 가상환경, 비밀 설정, 소스, 원본 DB는 수정하지 않았습니다.

이전 과제 01 사이트로 되돌려야 할 경우 다음을 실행합니다. 새 과제 02의 DB와 사진은 별도 데이터 폴더에 계속 보존됩니다.

1. PythonAnywhere Bash 콘솔에서 원본 WSGI를 복구합니다.

   ```sh
   cp /home/asdfgh0986/photoblog-backups/before-assessment02-20261106-083539/previous-wsgi.py /var/www/asdfgh0986_pythonanywhere_com_wsgi.py
   ```

2. Web 탭의 Source code를 `/home/asdfgh0986/photoblog-server-v2/PhotoBlogServer`, Virtualenv를 `/home/asdfgh0986/.virtualenvs/photoblog-v2`로 되돌립니다. Python은 3.12, Working directory는 `/home/asdfgh0986/`, Force HTTPS는 켜짐을 유지합니다.
3. 정적 매핑 `/static/`를 `/home/asdfgh0986/photoblog-server-v2/PhotoBlogServer/staticfiles`, `/media/`를 `/home/asdfgh0986/photoblog-server-v2/PhotoBlogServer/media`로 되돌립니다.
4. Reload 후 기존 갤러리와 `/api/health/`를 확인합니다. 원래 웹 설정 전체와 매핑은 백업 JSON에서도 확인할 수 있습니다.

계정 웹앱 만료일은 API 조회 당시 **2026년 11월 17일**입니다. 이 날짜와 실제 배포 검사 결과는 조회 시점의 상태입니다.

## 확인한 기존 환경

사용자가 지정한 `/Users/gimseung-won/mwp-middle01/mwp-middleexam01`의 배포 문서에 따르면 과제 01 환경은 다음과 같습니다.

| 항목 | 기존 경로 |
|---|---|
| 소스 | `/home/asdfgh0986/photoblog-server-v2/PhotoBlogServer` |
| 가상환경 | `/home/asdfgh0986/.virtualenvs/photoblog-v2` |
| WSGI | `/var/www/asdfgh0986_pythonanywhere_com_wsgi.py` |
| 서버 비밀 설정 | `/home/asdfgh0986/.config/photoblog-v2.json` |
| 관리자 설정 | `/home/asdfgh0986/.config/photoblog-v2-admin.json` |

해당 로컬 프로젝트의 숨김·무시 파일과 가상환경 활성화 스크립트를 확인했지만 API 토큰이나 배포 환경변수 값은 발견되지 않았습니다. 이후 사용자가 배포 API 토큰을 별도로 제공했습니다. 토큰은 Git에서 제외된 로컬 비밀 파일에서 읽으며 로그·보고서·소스에 기록하지 않습니다. 브라우저 쿠키나 다른 서비스의 인증정보는 조사하지 않았습니다.

## 준비된 배포 도구

`scripts/deploy_pythonanywhere.py`는 PythonAnywhere 공식 API로 별도 과제 02 소스, 가상환경, DB, 미디어 폴더를 준비합니다. 기존 소스와 DB는 그대로 두며, 전환 전에 원본 프로젝트·WSGI·웹 설정·정적 경로 설정과 SQLite 무결성을 확인한 백업을 만듭니다. 전환 뒤 HTTPS 상태·JWT 로그인·익명 API 거부를 확인하고 실패하면 기존 WSGI와 웹 설정을 복구합니다.

일반 실행에는 계정의 API 토큰과 **브라우저에서 이미 열어 둔 유휴 Bash 콘솔 ID**가 필요합니다. API로 콘솔 객체만 만드는 경우 실제 프로세스가 시작되지 않습니다. 토큰은 명령행 인자로 받지 않으며 저장소나 로그에 기록하지 않습니다.

```sh
# 계정 비밀관리 도구 등으로 프로세스 환경에 PYTHONANYWHERE_API_TOKEN 설정
.venv-server/bin/python scripts/deploy_pythonanywhere.py --console-id 콘솔ID
```

실행 중인 콘솔이 없는 환경에서는 명시적인 `--wsgi-bootstrap` 옵션을 사용할 수 있습니다. 정상적인 계정 파일 API와 WSGI Reload 권한으로 일회성 준비 프로세스를 시작하고, 준비 중에는 원래 WSGI 앱을 계속 제공합니다. 설치용 공개 URL이나 토큰을 노출하지 않습니다. 준비 실패 시 원본 WSGI를 복구하며, 새 환경 준비가 완료된 후에 웹앱 설정과 미디어 경로를 전환합니다.

애플리케이션 로그인 정보는 저장소 밖 권한 600 JSON 파일에 생성합니다. 기존 로컬 테스트 계정을 그대로 쓰려면 저장소 밖 `{"username":"guardian","password":"사용자 비밀번호"}` 파일을 준비하고 `--credentials-file /private/tmp/개인설정.json`을 지정합니다. 실제 비밀번호를 문서·보고서·GitHub에 쓰지 않습니다.

| 새 환경 항목 | 원격 위치 |
|---|---|
| 소스 | `~/home-guardian-assessment02/releases/배포시각/PhotoBlogServer` |
| 공용 데이터 | `~/home-guardian-assessment02/data/` |
| 가상환경 | `~/.virtualenvs/home-guardian-assessment02` |
| 비밀 설정 | `~/.config/home-guardian-assessment02.json` |
| 관리자 설정 | `~/.config/home-guardian-assessment02-admin.json` |
| 이전 환경 백업 | `~/photoblog-backups/before-assessment02-배포시각/` |

배포 도구의 소스 구문과 압축 파일에서 비밀키·DB·미디어가 제외되는지는 로컬에서 확인했습니다. 실제 배포 성공 여부와 검사 결과는 `docs/evidence/cloud-deployment.json`에 기록합니다.

공식 문서: [API](https://help.pythonanywhere.com/pages/API/), [기존 Django 프로젝트 배포](https://help.pythonanywhere.com/pages/DeployExistingDjangoProject/).
