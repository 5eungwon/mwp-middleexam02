> 과거 푸시 구현의 연결 참고 기록입니다. 현재 앱은 푸시를 원격 감시 ON/OFF로 교체했고 Firebase 의존성·수신 코드를 제거했습니다. 이 안내만 따라도 현재 APK에서 푸시가 동작하는 것은 아닙니다. 현재 기능은 [FEATURES.md](FEATURES.md)를 참조하세요.

# 감지 푸시 알림 연결

현재 프로젝트가 없는 상태이므로 서버·앱의 FCM 연결 코드는 준비되어 있어도 실제 휴대폰 수신은 아직 검증할 수 없습니다. 앱과 웹에는 설정 대기 상태가 표시됩니다. 모의 발송 테스트의 성공을 실제 Firebase 발송으로 표시하지 않습니다.

1. [Firebase Console](https://console.firebase.google.com/)에서 본인 Google 계정으로 로그인하고 프로젝트를 만듭니다. 이 과제의 푸시에는 Google Analytics가 필요하지 않습니다.
2. 프로젝트에 Android 앱을 추가합니다. 패키지 이름은 **`kr.ac.homeguard.photoviewer`**입니다.
3. 제공되는 `google-services.json`을 내려받아 **`PhotoViewer/app/google-services.json`**에 저장합니다. 이 파일이 있으면 Gradle이 앱 ID·발신자 ID 등을 읽어 Firebase를 초기화합니다. 다른 패키지의 설정 파일은 빌드에서 거부합니다.
4. 프로젝트 설정 → 서비스 계정에서 서버 발송용 비공개 키 JSON을 발급하고 **`.credentials/firebase-service-account.json`**에 보관합니다. 비공개 키의 내용을 채팅·보고서·GitHub에 붙여 넣지 않습니다. 생성에는 본인 Google 계정 권한이 필요합니다.
5. 로컬 서버는 `FCM_SERVICE_ACCOUNT_FILE`에 해당 JSON의 절대 경로를 설정해 재시작합니다. 클라우드는 JSON을 저장소 밖 비공개 경로에 권한 600으로 저장하고 WSGI 환경에 같은 변수를 설정합니다. `FCM HTTP v1 API`가 활성화되어 있어야 합니다.
6. Android 앱을 다시 빌드·설치하고 로그인한 뒤 **감시 영역 · 알림 설정 → 이 기기에서 알림 받기**를 켭니다. Android 13 이상에서는 알림 권한을 허용합니다.
7. 앱을 백그라운드로 이동한 상태에서 실제 YOLO 사진을 등록합니다. 알림 수신과 알림 클릭 후 같은 사진 상세로 이동하는 것을 확인합니다. 기기를 OS에서 강제 종료한 상태의 전달은 보장하지 않습니다.

두 설정 파일과 `.credentials/`는 Git에서 제외됩니다. Android 설정 파일과 서버 키는 같은 Firebase 프로젝트여야 합니다. 서비스 계정 키는 서버에만 두며 APK에 넣지 않습니다.

서버는 사진 저장이 완료된 후 발송 작업을 DB에 기록하고 별도 작업 스레드에서 FCM HTTP v1을 호출합니다. 웹 프로세스 재시작 등으로 작업이 남으면 다음 명령으로 재시도합니다. 호스팅에서 지원하는 예약 작업으로 실행할 수도 있습니다.

```sh
.venv-server/bin/python PhotoBlogServer/manage.py send_pending_push
```

발송 실패가 사진 저장을 취소하지 않으며 `PushDelivery`에 상태와 비밀정보를 제외한 오류 코드가 남습니다. 로그아웃/계정 전환 후 예전 계정의 알림이 표시되지 않도록 기기별 로그인 연결 ID를 확인합니다. 기기 토큰은 API 응답에 노출하지 않습니다.

공식 문서: [Android 설정](https://firebase.google.com/docs/cloud-messaging/android/get-started), [HTTP v1 발송과 인증](https://firebase.google.com/docs/cloud-messaging/send/v1-api).
