# PhotoViewer — Android Client

Java 네이티브 앱입니다. 서버 설정, JWT 로그인, 사진 목록·상세 조회를 제공합니다. 추가 편의 기능은 서버와 공통으로 **검색/미확인 필터**와 **확인 완료 표시** 두 가지입니다. 비밀번호는 저장하지 않으며 로그인 토큰은 앱 전용 SharedPreferences에 저장합니다. 네트워크 요청과 이미지 디코딩은 작업 스레드에서 실행합니다.

## 빌드

- JDK 17 이상, Android SDK Platform 36, Gradle 8.14.3, Android Gradle Plugin 8.11.0
- Android Studio에서 이 디렉터리를 열거나 명령행으로 빌드합니다.

```bash
cd PhotoViewer
# SDK 경로는 자신의 환경에 맞게 설정합니다.
printf 'sdk.dir=%s\n' "$ANDROID_HOME" > local.properties
./gradlew assembleDebug lintDebug
```

macOS에서 Android Studio 번들 JDK를 사용할 수 있습니다.

```bash
export JAVA_HOME='/Applications/Android Studio.app/Contents/jbr/Contents/Home'
./gradlew assembleDebug
```

APK: `app/build/outputs/apk/debug/app-debug.apk`.

## 실행

1. Django 서버를 먼저 실행하고 계정을 준비합니다.
2. 에뮬레이터에 APK를 설치합니다.
3. 서버 주소, 아이디, 비밀번호를 입력하고 **로그인**합니다.
4. 사진 카드를 눌러 상세 화면을 확인합니다.
5. **이 기록 확인 완료로 표시** 후 목록의 **미확인** 필터에서 사라지는지 확인합니다.
6. 제목 또는 내용으로 검색하고 **새로고침**으로 새 업로드를 불러옵니다.

```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb shell am start -n kr.ac.homeguard.photoviewer/.MainActivity
```

- Android Emulator 로컬 서버: `http://10.0.2.2:8000`.
- USB 연결 실제 기기: `adb reverse tcp:8000 tcp:8000` 이후 `http://127.0.0.1:8000`.
- PythonAnywhere: 실제 배포된 `https://계정명.pythonanywhere.com`.
- Debug 빌드만 `10.0.2.2`, `127.0.0.1`, `localhost`의 HTTP를 허용합니다. 그 외 서버와 Release 빌드는 HTTPS를 사용합니다.
- 앱은 API 응답으로 받은 자신의 기록을 표시합니다. 스크린샷용 가짜 목록이나 하드코딩된 계정은 포함하지 않습니다.

## API

| 동작 | 요청 |
| --- | --- |
| 로그인 | `POST /api-token-auth/` — `username`, `password` |
| 목록 | `GET /api_root/Post/?search=...&unread=1` |
| 상세 | `GET /api_root/Post/{id}/` |
| 확인 완료 | `POST /api_root/Post/{id}/acknowledge/` |

인증 헤더: `Authorization: JWT <token>`. 목록은 JSON 배열을 받습니다. HTTP 401은 저장 토큰을 삭제하고 로그인 화면으로 이동합니다. 네트워크 실패는 화면에 오류와 재시도 방법을 표시합니다. 화면 회전 시 로그인 상태, 검색 조건, 열어 둔 상세 기록을 복원합니다.

자동 빌드와 Android Lint는 소스·리소스의 정적 검증입니다. 실제 로그인/사진 조회 여부는 루트 보고서에 기록된 에뮬레이터 또는 기기 실행 결과를 따릅니다.
