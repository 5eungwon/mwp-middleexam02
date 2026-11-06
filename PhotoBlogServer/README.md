# PhotoBlogServer

Python 3.12와 Django 5.2 LTS로 구현한 침입자 감지 사진 서버. Ch08의 JWT 로그인 → multipart 사진 전송 → 웹/Android 조회 흐름을 지원합니다.

## 로컬 실행

저장소 루트에서 실행합니다.

```sh
python3.12 -m venv .venv-server
.venv-server/bin/python -m pip install -r PhotoBlogServer/requirements.txt
.venv-server/bin/python PhotoBlogServer/manage.py migrate
read -s DEMO_PASSWORD
export DEMO_PASSWORD
.venv-server/bin/python PhotoBlogServer/manage.py seed_demo --username guardian --superuser
unset DEMO_PASSWORD
.venv-server/bin/python PhotoBlogServer/manage.py runserver 0.0.0.0:8000
```

웹: http://127.0.0.1:8000/ / 관리자: `/admin/` / 상태: `/health/`
API 로그인 요청은 IP별 1분당 10회로 제한합니다. 로컬 비밀키는 첫 실행 때 생성되며 Git에서 제외합니다. 이미지는 최대 8MB, JPEG/PNG/WEBP만 허용합니다.

## API 계약

| 메서드 | 경로 | 결과 |
|---|---|---|
| POST | `/api-token-auth/` | `username`, `password`로 로그인. `{token, username}` 반환 |
| GET | `/api_root/Post/` | 자신의 기록 JSON 배열. `?search=person`, `?unread=1` 지원 |
| POST | `/api_root/Post/` | multipart `title`, `text`, `image` 전송. 생성 시 201 |
| GET/PATCH/PUT/DELETE | `/api_root/Post/{id}/` | 자신의 기록만 조회/수정/삭제 |
| POST | `/api_root/Post/{id}/acknowledge/` | 확인 완료 처리 |

인증 헤더는 `Authorization: JWT <token>`이며 `Bearer`도 허용합니다. 토큰 유효기간은 8시간이고 만료되면 다시 로그인합니다. 반환 필드: `id`, `title`, `text`, `image`(절대 URL), `created_date`, `published_date`, `author`(아이디), `acknowledged`. 작성자와 확인 여부는 일반 생성/수정 요청으로 바꿀 수 없습니다. 다른 사용자의 기록은 404입니다.

추가 편의 기능은 **검색·미확인 필터**와 **확인 완료 처리**의 두 가지입니다.

미디어 파일명은 UUID이며 목록과 상세 API는 인증이 필요합니다. 현재 `/media/` 파일 자체는 URL을 아는 사람이 읽을 수 있으므로 실제 개인 영상 운영에는 인증된 미디어 프록시 또는 비공개 스토리지 구성이 추가로 필요합니다. 제출 증빙에는 공개 샘플 이미지만 사용합니다.

## 테스트

```sh
.venv-server/bin/python PhotoBlogServer/manage.py test blog --verbosity 2
.venv-server/bin/python PhotoBlogServer/manage.py check
```

## PythonAnywhere

공식 문서: https://help.pythonanywhere.com/pages/DeployExistingDjangoProject/

1. Bash 콘솔에서 저장소를 clone하고 Python 3.12 가상환경을 만듭니다. `mkvirtualenv --python=/usr/bin/python3.12 home-guardian` 후 `pip install -r PhotoBlogServer/requirements.txt`.
2. `cd PhotoBlogServer`에서 `python manage.py migrate`, `python manage.py createsuperuser`, `python manage.py collectstatic --noinput`을 실행합니다.
3. Web 탭에서 **Manual configuration / Python 3.12** 웹 앱을 만들고 Virtualenv를 `/home/계정/.virtualenvs/home-guardian`으로 지정합니다.
4. `deploy/pythonanywhere_wsgi.py.example`에 따라 WSGI 파일을 설정합니다. 비밀키는 저장소 밖 설정 파일에 보관합니다. `DJANGO_ALLOWED_HOSTS`에는 실제 도메인을 설정합니다.
5. Static files에 `/static/` → `/home/계정/mwp-middleexam02/PhotoBlogServer/staticfiles/`, `/media/` → `/home/계정/mwp-middleexam02/PhotoBlogServer/media/`를 추가합니다.
6. Reload 후 HTTPS `/health/` 응답, 웹 로그인, 사진, API 업로드, Android 앱 서버 주소를 실제 도메인으로 바꾼 연결을 확인합니다.

배포 설정에서는 DEBUG 해제, HTTPS 리다이렉트, secure cookie, HSTS가 적용됩니다. 설정 파일의 비밀키와 도메인을 환경변수로 내보낸 상태에서 `python manage.py check --deploy`도 실행합니다. 클라우드 동작 증빙은 실제 배포 후 별도로 캡처해야 합니다. 로컬 실행 결과는 PythonAnywhere 배포 증빙이 아닙니다.

현재 `check --deploy`의 W005(HSTS 하위 도메인)와 W021(HSTS preload)은 도메인 관리 정책을 확인하기 전까지 의도적으로 설정하지 않아 출력됩니다. 서비스의 모든 하위 도메인이 HTTPS로 동작하는지와 브라우저 preload 등록 여부를 확인한 후 운영자가 결정합니다. 일반 `check`는 경고 없이 통과합니다.
