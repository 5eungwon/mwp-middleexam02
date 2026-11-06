# 우리집 지킴이 · 공통평가 02

YOLOv5가 새 객체의 출현을 감지하면 사진을 Django 서버에 전송하고 웹과 네이티브 Android 앱에서 확인합니다.

**제출 URL:** https://github.com/5eungwon/mwp-middleexam02

공통평가 01(`mwp-middleexam01`)과 별개인 저장소입니다. 기준 자료는 제공된 Ch08 강의 PDF와 공통평가 02 Word 원본 양식입니다.

```text
ROOT/
├── PhotoBlogServer/   # Django 서버, JWT REST API, 웹
├── PhotoViewer/       # Java Android Client, Gradle 프로젝트
├── YOLOv5/            # Edge Client + 수정 전 공식 v7.0 원본
├── 모바일웹서비스 프로젝트_공통평가 02_수행 결과 보고서.docx
├── docs/              # 캡처, 실제 실행 기록, 원본 양식, 배포 안내
└── scripts/           # 연동 검증, 캡처, Word 생성
```

## 실제 검증 결과

| 항목 | 결과 | 증빙 |
| --- | --- | --- |
| 수정 전 공식 detect.py | 원본 해시 유지, 사람 3명·버스 1대 검출 | [실행 결과](YOLOv5/evidence/baseline-run.json), [로그](YOLOv5/evidence/baseline-command.txt) |
| YOLO → Django | 실제 추론 → JWT → multipart 등록 → 사진 HTTP 200 | [실제 연동](docs/evidence/edge-integration.json) |
| Django 자동 테스트 | 14개 통과 | [로그](docs/evidence/backend-tests.txt) |
| 엣지 자동 테스트 | 실제 모델 추론 포함 9개 통과 | [로그](YOLOv5/evidence/tests.txt) |
| 실제 HTTP 통합 검증 | 10개 검사 통과 | [HTTP 결과](docs/evidence/integration.json) |
| Android 빌드·Lint | assembleDebug/lintDebug 성공, Lint 문제 0개 | [빌드 기록](PhotoViewer/validation/build-summary.json) |
| 실제 Android 실행 | 로그인·YOLO 사진·검색·미확인·확인 처리·서버 반영 | [실행 기록](docs/evidence/android-runtime.json) |
| PythonAnywhere | 최신 배포·검증 결과는 배포 문서와 Word에 기록 | [배포·복구](docs/PYTHONANYWHERE.md) |

캡처 원본은 [docs/evidence](docs/evidence)에 있습니다. Word 원본 표의 관련증빙 칸에 이미지를 내장하고 뒤쪽에 확대본을 추가합니다. 실제 VS Code 화면, 수정 전 공식 검출기, 수정 검출기의 결과를 구분해 보관합니다.

## 서버 실행

Python 3.12를 사용합니다. 자세한 API·운영 설정은 [서버 README](PhotoBlogServer/README.md)에 있습니다.

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

웹: `http://127.0.0.1:8000/`. 같은 계정으로 로그인합니다.

## 엣지 실행

Python 3.9 이상. 설치·원본 검출기 재현·장치 입력은 [엣지 README](YOLOv5/README.md)를 참조하세요.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r YOLOv5/requirements.txt
.venv/bin/python YOLOv5/download_assets.py
export PHOTO_SERVER=http://127.0.0.1:8000
export PHOTO_USERNAME=guardian
read -s PHOTO_PASSWORD
export PHOTO_PASSWORD
.venv/bin/python YOLOv5/detect.py --source YOLOv5/data/bus.jpg
unset PHOTO_PASSWORD
```

객체 존재 여부가 **0→1**로 바뀔 때만 새 사진을 등록합니다. 같은 클래스가 계속 보이는 동안 매 프레임 전송하지 않습니다. 전송 실패 이벤트는 계정·서버별 outbox에 보존해 재시도합니다. 서버 등록 후 응답만 유실된 경우 중복 등록될 수 있습니다. 클래스의 유무를 보므로 같은 클래스의 개체 수 증가는 추적하지 않습니다.

검출 사진은 강의와 같이 320×240 JPEG로 전송합니다. 실제 추론 테스트는 공식 공개 **정지 이미지**로 수행했습니다. `--source 0`, 동영상, RTSP URL을 지원하지만 웹캠/RTSP 장치 테스트는 수행하지 않았습니다. 모델은 공식 URL과 SHA-256을 확인해 다운로드하며 Git에서 제외합니다.

## Android 실행

Android Studio에서 `PhotoViewer/`를 열거나 JDK 17 이상과 Android SDK 36으로 빌드합니다. [Android 설명](PhotoViewer/README.md).

```sh
cd PhotoViewer
./gradlew assembleDebug lintDebug
```

APK: `app/build/outputs/apk/debug/app-debug.apk`. 에뮬레이터의 서버는 `http://10.0.2.2:8000`, 실제 기기는 PC의 LAN 주소를 사용합니다. PythonAnywhere는 HTTPS 주소를 입력합니다. HTTP 개발 연결은 debug 앱의 로컬·사설망 설정으로 제한됩니다.

## API와 편의 기능

`POST /api-token-auth/`에서 username/password로 토큰을 발급하고 `Authorization: JWT <token>`으로 `/api_root/Post/`를 호출합니다. GET은 강의와 같은 JSON 배열이고, POST는 multipart title/text/image를 받습니다. 기록은 로그인한 계정별로 제한됩니다.

추가 편의 기능은 **2개**입니다.

1. **검색·미확인 필터:** 제목·내용 검색과 미확인 기록 조회를 서버·Android에서 지원합니다.
2. **확인 완료 처리:** Android에서 확인한 상태를 서버에 저장하고 웹·목록 필터에 반영합니다.

## 테스트와 보고서

```sh
.venv-server/bin/python PhotoBlogServer/manage.py test blog --verbosity 2
.venv/bin/python -m unittest discover -s YOLOv5/tests -v
```

원본 양식은 [docs/templates/report-template.docx](docs/templates/report-template.docx)에 보존했습니다. 도구 의존성은 `python-docx`, `Pillow`, `playwright`와 Chrome입니다. `verify_integration.py`, `capture_web.py`, `capture_android.py`는 Git 외부의 username/password JSON 파일을 `--credentials`로 받습니다. 캡처 도구는 실제 검증한 로컬 시나리오에 맞춰 작성됐습니다.

```sh
.venv/bin/python scripts/render_evidence.py
.venv/bin/python scripts/build_report.py
```

최신 상태는 `docs/evidence/submission-status.json`과 Word의 항목별 판정을 참조하세요. 비밀번호·JWT·배포 토큰·DB·촬영 자료는 Git에서 제외합니다. 미디어 UUID URL 자체는 공개이므로 실제 사생활 영상 서비스에는 인증된 미디어 전송 구성을 추가해야 합니다. 제출 증빙은 공식 공개 예제만 사용합니다.
