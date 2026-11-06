# PythonAnywhere 배포

대상 주소: https://asdfgh0986.pythonanywhere.com

현재 과제 02 서버는 로컬에서 검증했습니다. 클라우드 배포 완료 여부는 실제 실행 결과인 `docs/evidence/cloud-deployment.json` 생성 여부와 내용을 확인해야 합니다.

## 확인한 기존 환경

사용자가 지정한 `/Users/gimseung-won/mwp-middle01/mwp-middleexam01`의 배포 문서에 따르면 과제 01 환경은 다음과 같습니다.

| 항목 | 기존 경로 |
|---|---|
| 소스 | `/home/asdfgh0986/photoblog-server-v2/PhotoBlogServer` |
| 가상환경 | `/home/asdfgh0986/.virtualenvs/photoblog-v2` |
| WSGI | `/var/www/asdfgh0986_pythonanywhere_com_wsgi.py` |
| 서버 비밀 설정 | `/home/asdfgh0986/.config/photoblog-v2.json` |
| 관리자 설정 | `/home/asdfgh0986/.config/photoblog-v2-admin.json` |

해당 로컬 프로젝트의 숨김·무시 파일과 가상환경 활성화 스크립트를 확인했지만 API 토큰이나 배포 환경변수 값은 발견되지 않았습니다. 서버 안의 설정 파일 경로는 로컬에서 읽을 수 있는 배포 인증수단이 아닙니다. 브라우저 쿠키나 다른 서비스의 인증정보는 조사하지 않았습니다.

## 준비된 배포 도구

`scripts/deploy_pythonanywhere.py`는 PythonAnywhere 공식 API로 별도 과제 02 소스, 가상환경, DB, 미디어 폴더를 준비합니다. 기존 소스와 DB는 그대로 두며, 전환 전에 원본 프로젝트·WSGI·웹 설정·정적 경로 설정과 SQLite 무결성을 확인한 백업을 만듭니다. 전환 뒤 HTTPS 상태·JWT 로그인·익명 API 거부를 확인하고 실패하면 기존 WSGI와 웹 설정을 복구합니다.

필수 정보는 계정의 API 토큰과 **브라우저에서 이미 열어 둔 유휴 Bash 콘솔 ID**입니다. API로 콘솔 객체만 만드는 경우 실제 프로세스가 시작되지 않으므로, 실행 중인 콘솔이 필요합니다. 토큰은 명령행 인자로 받지 않으며 저장소나 로그에 기록하지 않습니다.

```sh
# 계정 비밀관리 도구 등으로 프로세스 환경에 PYTHONANYWHERE_API_TOKEN 설정
.venv-server/bin/python scripts/deploy_pythonanywhere.py --console-id 콘솔ID
```

애플리케이션 로그인 정보는 저장소 밖 권한 600 JSON 파일에 생성합니다. 기존 로컬 테스트 계정을 그대로 쓰려면 저장소 밖 `{"username":"guardian","password":"사용자 비밀번호"}` 파일을 준비하고 `--credentials-file /private/tmp/개인설정.json`을 지정합니다. 실제 비밀번호를 문서·보고서·GitHub에 쓰지 않습니다.

| 새 환경 항목 | 원격 위치 |
|---|---|
| 소스 | `~/home-guardian-assessment02/releases/배포시각/PhotoBlogServer` |
| 공용 데이터 | `~/home-guardian-assessment02/data/` |
| 가상환경 | `~/.virtualenvs/home-guardian-assessment02` |
| 비밀 설정 | `~/.config/home-guardian-assessment02.json` |
| 관리자 설정 | `~/.config/home-guardian-assessment02-admin.json` |
| 이전 환경 백업 | `~/photoblog-backups/before-assessment02-배포시각/` |

배포 도구의 소스 구문과 압축 파일에서 비밀키·DB·미디어가 제외되는지는 로컬에서 확인했습니다. 인증정보가 준비되기 전에는 원격 실행이나 배포 성공을 검증한 것으로 취급하지 않습니다.

공식 문서: [API](https://help.pythonanywhere.com/pages/API/), [기존 Django 프로젝트 배포](https://help.pythonanywhere.com/pages/DeployExistingDjangoProject/).
