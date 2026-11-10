# 감시 영역 설정과 원격 감시 ON/OFF

2026-11-10 현재 평가용 편의 기능은 **감시 영역 설정**과 **원격 감시 ON/OFF** 두 가지입니다. Firebase 연결을 보류한 푸시 알림은 원격 제어로 교체했습니다. 현재 Android 앱에는 Firebase 의존성·알림 권한·연결 대기 화면이 없습니다. 별도 외부 계정 없이 기존 Django 로그인으로 동작합니다.

## 1. 감시 영역 설정

웹의 감시 설정 또는 Android 목록의 **감시 영역 · 원격 제어**에서 사진 위를 드래그해 영역을 저장합니다. 이름, 활성화 상태, 정규화 좌표(0~1)는 계정별로 분리됩니다. 반전·범위 초과·NaN·너무 작은 사각형은 거부합니다.

YOLO는 사람 검출 상자의 발밑 중심점이 영역 안에 있는지 판정합니다. 영역 안 클래스 존재 여부가 0→1로 변할 때 사진을 보냅니다. 영역 기능을 끄면 전체 화면을 감시합니다. 사람별 ID 추적이나 사람 수 변화 감지는 포함하지 않습니다.

- [실제 YOLO 로컬 검증](evidence/features-20261110/roi-integration.json): 영역 밖 0건, 영역 안 1건.
- [실제 YOLO 클라우드 검증](evidence/features-20261110/cloud-roi/roi-integration.json).
- [Android 실제 드래그·클라우드 저장](evidence/features-20261110/cloud-android/android-zone-runtime.json).

## 2. 원격 감시 ON/OFF

웹 감시 설정과 Android 설정의 **감시 작동** 스위치를 바꾸면 `PATCH /api/settings/`가 `monitoring_enabled`를 계정별로 저장합니다. 저장 실패 시 스위치를 이전 상태로 되돌리고 오류를 표시합니다. 영역 저장과 감시 작동 변경은 독립적인 요청이라 서로의 설정을 덮어쓰지 않습니다.

YOLO는 기본 5초마다 설정을 조회합니다. OFF를 확인하면 모델 추론과 새 이벤트 생성·전송을 중지합니다. 프로그램과 영상 입력 자체는 계속 실행하므로 ON을 다시 확인하면 감지를 재개합니다. 카메라 전원을 끄는 기능은 아닙니다. OFF 중에도 기존 사진·검색·확인 처리는 사용할 수 있고 ROI도 유지됩니다. ON으로 복귀하면 출현 상태를 초기화해 계속 서 있는 사람도 다시 한 번 기록합니다.

서버도 OFF 상태의 새 감지 사진 POST를 HTTP **423**으로 거부합니다. 엣지가 아직 이전 ON 설정을 캐시하고 있어도 서버 등록은 차단됩니다. `--zone`으로 영역을 덮어써도 원격 OFF는 우회하지 못합니다. 서버가 423으로 거부한 이벤트는 로컬 `paused/`에 남기고 자동 재전송하지 않습니다. 수동 웹 사진 등록은 운영자의 직접 등록 기능으로 계속 허용합니다.

실제 공개 예제 `bus.jpg`를 **동일한 YOLO 모델·변화 감지 인스턴스**로 ON → OFF → ON 순서로 처리해 등록 **1 → 0 → 1건**과 유지 프레임 중복 0건을 검증했습니다. 정지 이미지 검증이며 실제 카메라 이동을 촬영한 결과는 아닙니다.

- [로컬 YOLO·HTTP 실제 연동](evidence/monitoring-20261110/local/monitoring-integration.json).
- [클라우드 YOLO·HTTP 실제 연동](evidence/monitoring-20261110/cloud/monitoring-integration.json).
- [실제 Android 로컬 스위치·서버 저장](evidence/monitoring-20261110/local-android/android-monitoring-runtime.json).
- [실제 Android 클라우드 스위치·서버 저장](evidence/monitoring-20261110/cloud-android/android-monitoring-runtime.json).
- [실제 클라우드 웹 스위치·서버 저장](evidence/monitoring-20261110/cloud-web/web-monitoring-runtime.json).

## 검증·제출 자료

Django 28개, 엣지 16개 테스트 통과. Android 빌드·Lint 성공(오류 0개, Gradle 버전 안내 경고 1개). 새 캡처와 JSON은 `docs/evidence/monitoring-20261110/`에 있습니다. 과거 `features-20261110/`의 푸시 보류 증빙은 당시 기록입니다.

사용자가 수정한 루트 Word 제출본은 보존합니다. `scripts/build_report.py --feature-update --output <별도파일.docx>`는 새로운 두 기능과 실제 캡처를 반영하도록 준비했습니다. 이번 변경에서 Word를 덮어쓰거나 새 문서의 렌더링 검증을 완료했다고 표시하지 않습니다. 보고서의 편의 기능 2를 **원격 감시 ON/OFF**로 바꾸고 새 웹·Android 캡처를 사용하면 됩니다.

서버의 이전 푸시 테이블·모듈은 기존 DB 호환을 위해 남겼지만 신규 사진의 자동 푸시 작업 생성은 중단했습니다. 현재 앱과 평가 기능에서 푸시 발송·수신을 제공하지 않습니다.
