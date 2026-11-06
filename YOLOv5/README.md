# YOLOv5 Edge Client

Ch08의 객체 출현 규칙(`직전 프레임 0 → 현재 프레임 1`)으로 새 검출 사진을 Django 서버에 전송합니다. 공식 YOLOv5n v7.0 COCO ONNX 모델을 OpenCV DNN의 CPU 엔진에서 실행합니다. PyTorch나 GPU는 필요하지 않습니다.

## 설치와 실제 추론

저장소 루트에서 Python 3.9 이상을 사용합니다.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r YOLOv5/requirements.txt
.venv/bin/python YOLOv5/download_assets.py
.venv/bin/python YOLOv5/detect.py --source YOLOv5/data/bus.jpg --no-upload
```

`download_assets.py`는 공식 Ultralytics 저장소의 파일만 다운로드하고 SHA-256을 검증합니다. 4MB ONNX 가중치는 Git에서 제외하며 설치 시 받습니다. 원본 예제 사진과 라이선스는 포함되어 있습니다.

## Django로 사진 전송

먼저 Django 서버에서 계정을 만듭니다. 실제 비밀번호는 터미널에서 입력하며 소스와 보고서에 넣지 않습니다.

```sh
export PHOTO_SERVER=http://127.0.0.1:8000
export PHOTO_USERNAME=사용자이름
read -s PHOTO_PASSWORD
export PHOTO_PASSWORD
.venv/bin/python YOLOv5/detect.py --source YOLOv5/data/bus.jpg
unset PHOTO_PASSWORD
```

- 토큰: `POST /api-token-auth/`의 `token` 값을 받아 `Authorization: JWT …`로 요청합니다.
- 등록: `POST /api_root/Post/`에 `title`, `text`, 날짜와 JPEG `image`를 multipart로 전송합니다.
- 기본 감시 클래스는 `person`입니다. `--classes person bus` 또는 `--classes all`로 변경할 수 있습니다.
- `--source 0`은 웹캠, `--source video.mp4`는 동영상, `--source rtsp://…`는 네트워크 카메라입니다. 예: `--max-frames 100`으로 테스트를 제한합니다.
- 같은 클래스가 계속 보이는 동안에는 중복 등록하지 않습니다. 사라졌다가 다시 나타나면 새 이벤트가 생깁니다. 이 규칙은 클래스의 유무를 보므로 사람이 한 명에서 두 명으로 늘어나는 것까지 구분하지 않습니다.

## 실패 시 동작

사진(강의와 동일한 320×240 JPEG)과 이벤트를 `runs/detect/delivery-<계정·서버 해시>/outbox/`에 먼저 보관합니다. 연결 실패나 서버 오류가 발생해도 이벤트는 삭제되지 않으며 다음 프레임에서 다시 전송합니다. 토큰 만료 시 재인증을 한 번 수행합니다. 성공한 이벤트는 `sent/`로 이동합니다.

한 장의 사진 테스트에서 미전송 이벤트가 남으면 종료 코드 2를 반환합니다. 동일한 계정·서버 설정으로 실행을 재개하면 보관된 이벤트도 다시 전송합니다. 서버가 등록을 완료한 뒤 응답만 유실되는 경우에는 재시도에 의해 중복 게시물이 생길 수 있습니다. 서버와 협의된 멱등 키가 없는 현재 API의 한계입니다.

`runs/`와 outbox는 촬영 자료이므로 Git에 포함하지 않습니다. 토큰·비밀번호는 파일이나 로그에 남기지 않습니다.

## 검증과 증거

```sh
.venv/bin/python -m unittest discover -s YOLOv5/tests -v
.venv/bin/python YOLOv5/detect.py --source YOLOv5/data/bus.jpg --no-upload --output YOLOv5/evidence/inference
```

- `evidence/inference/latest.jpg`: 공식 `bus.jpg`를 실제 모델로 추론한 bounding box 이미지.
- `evidence/inference/results.json`: confidence, 좌표, 모델 해시, 추론 시간 등 실제 결과.
- `evidence/tests.txt`: 0→1, 계속 출현, 재출현, 비감시 클래스, 서버 오류 보관·재시도, 재시작 후 재전송, 토큰 갱신, 인스턴스 분리와 실제 모델 추론 테스트.

공식 이미지 테스트는 웹캠/RTSP 장치 테스트와 다릅니다. 장치와 클라우드 환경은 별도로 실제 실행 후 확인해야 합니다.

## 수정 전 공식 detect.py 실행

보고서의 수정 전 기본 검출기 평가를 위해 공식 소스를 `upstream/`에 별도로 보존했습니다. v7.0 commit은 `915bbf294bb74c859f0b41f1c23bc395014ea679`이며 `upstream/detect.py`는 수정하지 않았습니다. 원본 검출기의 의존성은 사용자 클라이언트와 분리합니다.

```sh
python3.12 -m venv .venv-yolo
.venv-yolo/bin/python -m pip install -r YOLOv5/baseline-requirements.txt
MPLCONFIGDIR="$PWD/YOLOv5/runs/matplotlib" YOLOV5_CONFIG_DIR="$PWD/YOLOv5/runs/config" YOLOv5_AUTOINSTALL=false .venv-yolo/bin/python YOLOv5/upstream/detect.py --weights YOLOv5/models/yolov5n.onnx --dnn --source YOLOv5/data/bus.jpg --conf-thres 0.4 --device cpu --save-txt --save-conf --project YOLOv5/evidence --name baseline --exist-ok
```

이 실행은 서버 업로드 기능이 없는 **수정 전 원본**입니다. `evidence/baseline/bus.jpg`와 `baseline/labels/bus.txt`는 원본 검출기가 실제 저장한 결과이고, `baseline-command.txt`는 실행 로그입니다. `baseline-run.json`에 기록된 실행 전후 SHA-256이 일치합니다. 원본 배포 ZIP과 `detect.py` 해시는 `upstream-source.json`에 기록했습니다. `baseline-requirements.txt`는 검증한 Python 3.12/macOS 환경용이며, 다른 OS에서는 해당 플랫폼에 맞는 PyTorch wheel이 필요합니다.

## 원본 및 라이선스

- YOLOv5 v7.0: <https://github.com/ultralytics/yolov5/tree/v7.0>
- ONNX 가중치: <https://github.com/ultralytics/yolov5/releases/download/v7.0/yolov5n.onnx>
- 예제 이미지: <https://github.com/ultralytics/yolov5/blob/v7.0/data/images/bus.jpg>
- 공식 ONNX 배포 문서: <https://docs.ultralytics.com/yolov5/tutorials/model-export/>

루트의 `detect.py`·`changedetection.py`는 과제용 Python 클라이언트이고 `upstream/`은 비교 실행용 공식 v7.0 소스입니다. v7.0에서 제공하는 GNU GPL v3 라이선스 원문을 `UPSTREAM-LICENSE.txt`와 `upstream/LICENSE`에 보존했습니다. 원본 모델·데이터의 출처와 checksum은 `download_assets.py`에 명시되어 있습니다.
