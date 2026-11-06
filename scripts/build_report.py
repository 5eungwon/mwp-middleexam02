"""Fill the provided Word template and embed actual capture image bytes."""
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
E = ROOT / 'docs/evidence'
OUTPUT = ROOT / '모바일웹서비스 프로젝트_공통평가 02_수행 결과 보고서.docx'
STATE = json.loads((E / 'submission-status.json').read_text()) if (E / 'submission-status.json').exists() else {}
doc = Document(ROOT / 'docs/templates/report-template.docx')
for p in doc.paragraphs:
    if p.text.strip() == '학번 :': p.text = '학번 : 2021105579'
    if p.text.strip() == '이름 :': p.text = '이름 : 김승원'
setting = OxmlElement('w:doNotAutoCompressPictures')
doc.settings.element.append(setting)
normal = doc.styles['Normal']
normal.font.name = '맑은 고딕'
normal._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'), '맑은 고딕')
normal.font.size = Pt(10)
normal.paragraph_format.space_after = Pt(6)
table = doc.tables[0]

FIGURES = {
 'repository.png': ('A01 · 별도 GitHub 저장소와 폴더 구조', '실제 GitHub 저장소 화면. 공통평가 01과 다른 mwp-middleexam02 저장소입니다.'),
 'baseline-screen.png': ('A03 · 수정 전 공식 YOLOv5 detect.py 실행', '공식 v7.0 원본 detect.py의 실제 실행 로그와 저장된 검출 사진을 보여주는 브라우저 캡처입니다. 정지 이미지에서 3 persons, 1 bus를 검출했습니다.'),
 'vscode-changedetection.png': ('A04-1 · VS Code의 객체 출현 감지 코드', '실제 Visual Studio Code 편집기에서 changedetection.py의 추가 코드를 확인한 화면입니다.'),
 'vscode-detect.png': ('A04-2 · VS Code의 검출기 연동 코드', '실제 Visual Studio Code 편집기의 detect.py에서 ChangeDetection 호출과 전송 연동 코드를 확인한 화면입니다.'),
 'web-api.png': ('A05 · 로컬 api_root/Post', '실제 http://127.0.0.1:8000/api_root/Post/ 응답. YOLO가 전송한 사진과 게시물 정보를 확인했습니다.'),
 'web-feed.png': ('A06-1 · 로컬 서버 목록·사진', '실제 로컬 Django 서버에 로그인한 뒤 YOLO가 등록한 사진을 조회한 화면입니다.'),
 'web-detail.png': ('A06-2 · 로컬 서버 검출 사진 상세', '실제 YOLO 전송 게시물 상세 화면입니다. 등록된 사진은 강의 방식에 따라 320×240 JPEG로 축소 전송됐습니다.'),
 'android-login.png': ('A07-1 · Android 앱 시작 화면', '실제 Pixel 7 Android 에뮬레이터의 네이티브 앱. 비밀번호를 입력하기 전의 화면입니다.'),
 'android-feed.png': ('A07-2 · Android 로컬 서버 동기화', 'http://10.0.2.2:8000의 Django API에서 YOLO 검출 사진을 받아 실제로 표시한 화면입니다.'),
 'android-detail.png': ('A07-3 · Android에서 YOLO 전송 사진 확인', 'YOLOv5가 실제로 검출해 Django에 전송한 게시물 id=2의 사진과 감지 정보를 Android 앱에서 열었습니다.'),
 'cloud-api.png': ('A08 · PythonAnywhere api_root/Post', '이번 과제의 Django 코드를 배포한 PythonAnywhere HTTPS API 응답입니다.'),
 'cloud-feed.png': ('A09-1 · PythonAnywhere 목록·사진', '이번 과제의 Django 서버가 PythonAnywhere에서 실제로 제공하는 사진 목록입니다.'),
 'cloud-detail.png': ('A09-2 · PythonAnywhere 검출 사진 상세', 'PythonAnywhere에 실제 전송된 YOLO 검출 사진과 메타데이터입니다.'),
 'android-cloud.png': ('A09-3 · Android 클라우드 사진 동기화', '실제 Android 앱이 이번 Django 클라우드 서버의 사진을 HTTPS로 동기화한 화면입니다.'),
 'android-cloud-login.png': ('A09-4 · Android의 클라우드 서버 설정', '실제 Android 앱에 PythonAnywhere HTTPS 주소를 입력한 화면입니다. 비밀번호 입력 전 캡처입니다.'),
 'android-cloud-detail.png': ('A09-5 · Android 클라우드 YOLO 사진 상세', '실제 YOLO가 클라우드에 전송한 사진을 Android 앱에서 HTTPS로 조회한 화면입니다.'),
 'web-search.png': ('A10-1 · 편의 기능 1 · 서버 검색', '실제 서버에서 person을 검색한 결과입니다. 제목과 내용 검색을 지원합니다.'),
 'web-unread.png': ('A10-2 · 편의 기능 1 · 서버 미확인 필터', '확인 처리된 기록을 제외하고 미확인 기록만 조회하는 서버 화면입니다.'),
 'android-unread.png': ('A10-3 · 편의 기능 1 · Android 미확인 필터', 'Android가 API의 unread=1을 사용해 미확인 기록만 표시한 실제 화면입니다.'),
 'android-search.png': ('A10-4 · 편의 기능 1 · Android 검색', 'Android가 API의 search 매개변수로 실제 검색한 화면입니다.'),
 'android-acknowledged.png': ('A10-5 · 편의 기능 2 · Android 확인 처리', '앱에서 확인 완료 요청을 보낸 후 표시되는 상태입니다. 서버 API에서 acknowledged=true도 별도로 확인했습니다.'),
 'web-acknowledged.png': ('A10-6 · 편의 기능 2 · 서버 상태 반영', 'Android에서 확인 완료한 게시물의 상태를 웹 서버에서 다시 조회한 화면입니다.'),
 'tests.png': ('A11 · 자동 테스트 실행 기록', '원본 실행 로그를 읽어 보여주는 증빙 HTML의 실제 브라우저 캡처입니다. 원본 텍스트와 JSON도 저장소에 포함합니다.'),
 'yolo-inference.jpg': ('A12 · 실제 YOLOv5 모델 추론 결과', '공식 공개 예제 bus.jpg에서 person 3명(82.3%, 81.6%, 67.6%)과 bus(52.6%)를 실제 검출했습니다. 실제 침입 사건 사진은 아닙니다.'),
}


def evidence(cell, filenames, note=''):
    cell.text = note
    for filename in filenames:
        path = E / filename
        if not path.exists(): continue
        title, _ = FIGURES[filename]
        cell.add_paragraph(title)
        p = cell.add_paragraph()
        p.add_run().add_picture(str(path), width=Inches(1.34))
        p = cell.add_paragraph('확대본: 뒤쪽 증빙 페이지')
        for run in p.runs: run.font.size = Pt(8)


def fill(row_index, status, filenames=(), note=''):
    cells = table.rows[row_index].cells
    cells[4].text = '완료' if status else '미완료'
    cells[5].text = '○' if status else '×'
    evidence(cells[6], filenames, note)


fill(2, True, ['repository.png'], 'ROOT의 서버·Android·YOLO·Word 구성. A01 확대본 참조.')
fill(3, STATE.get('github') == '완료', note='https://github.com/5eungwon/mwp-middleexam02')
fill(4, (ROOT/'YOLOv5/evidence/baseline-run.json').exists(), ['baseline-screen.png'], '수정 없는 공식 v7.0 원본 실행. baseline-run.json에 실행 전후 SHA-256 일치 기록.')
fill(5, (E/'vscode-changedetection.png').exists(), ['vscode-changedetection.png','vscode-detect.png'], '추가 소스와 실제 VS Code 편집 화면.')
fill(6, (E/'edge-integration.json').exists(), ['web-api.png'], 'JWT 인증과 multipart 등록 후 JSON 배열 확인.')
fill(7, (E/'edge-integration.json').exists(), ['web-feed.png','web-detail.png'], '실제 YOLO 게시물 id=2, HTTP 201 등록/사진 200 확인.')
fill(8, (E/'android-runtime.json').exists(), ['android-feed.png','android-detail.png'], 'PC 브라우저의 모바일 크기 화면이 아닌 실제 네이티브 Android 에뮬레이터.')
cloud_ok = STATE.get('cloud') == '완료'
fill(9, cloud_ok, ['cloud-api.png'], '새 코드의 실제 배포 검증.' if cloud_ok else '배포용 API 토큰 미확인. 기존 01 사이트 접속만으로 이번 코드 동작을 완료 처리하지 않음.')
fill(10, cloud_ok, ['cloud-feed.png','cloud-detail.png'], '실제 클라우드 목록·사진 증빙. Android HTTPS 연결 화면은 A09-3~5 확대본에 추가.' if cloud_ok else '새 Django 배포 후 실제 목록·사진 확인 필요. 기존 원격 사이트는 변경하지 않음.')
# Keep the template's original requirement row and use its blank rows for the
# explicitly requested separate server/client convenience implementations.
feature_rows = [
 (11,'10-1','Server','검색·미확인 필터','제목/내용 검색 및 미확인 기록만 조회. 추가 편의 기능 1의 서버 구현.',['web-search.png','web-unread.png'],STATE.get('filters') == '완료'),
 (12,'10-1','Client','검색·미확인 필터','서버 search/unread 매개변수와 연동하는 Android 화면. 추가 편의 기능 1의 Client 구현.',['android-unread.png','android-search.png'],STATE.get('android') == '완료'),
 (13,'10-2','Server','확인 완료 처리','본인 게시물의 확인 상태 저장, 미확인 필터 및 웹 상태에 반영. 추가 편의 기능 2의 서버 구현.',['web-acknowledged.png'],STATE.get('acknowledge') == '완료'),
 (14,'10-2','Client','확인 완료 처리','Android 확인 완료 버튼이 서버에 상태를 저장하고 완료 상태를 표시. 추가 편의 기능 2의 Client 구현.',['android-acknowledged.png'],STATE.get('acknowledge') == '완료'),
]
for index, ident, category, name, description, files, ok in feature_rows:
    cells=table.rows[index].cells
    for cell,value in zip(cells[:4],[ident,category,name,description]): cell.text=value
    fill(index,ok,files)

# Evidence appendices retain full resolution while providing a readable display
# size, in addition to the thumbnails in each original related-evidence cell.
doc.add_page_break()
doc.add_heading('구현·검증 개요',level=1)
doc.add_paragraph('원본 공통평가 02 Word 양식의 1~10 요구사항을 모두 대조해 원본 표의 완료 여부, 판정과 관련증빙을 작성했습니다. 편의 기능은 2개이며 서버/클라이언트 구현을 각각 별도 행에 기록했습니다. 이미지는 원본 바이트를 문서에 포함했고 자동 압축을 껐습니다.')
doc.add_paragraph('작성일: '+datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d %H:%M KST'))
doc.add_paragraph('현재 상태: '+STATE.get('overall','로컬 구현 검증 완료 · 클라우드 배포 인증정보 확인 필요'))
doc.add_paragraph('클라우드 서비스: https://asdfgh0986.pythonanywhere.com / 강의 API: https://asdfgh0986.pythonanywhere.com/api_root/Post/ (로그인 필요)')
doc.add_paragraph(STATE.get('test_summary','자동 테스트와 실제 연동 결과는 원본 로그 참조.'))
doc.add_paragraph('Django: Python3.12.14 / Django5.2.19 / DRF3.18.3 / PyJWT2.15.1. 엣지: Python3.9.6 / OpenCV4.11.0.86 / NumPy1.26.4. 기본 원본 detect.py는 별도 Python3.12 가상환경에서 공식 v7.0 소스를 수정 없이 실행했습니다. Android: Java, compileSdk36, 실제 Pixel7 Android15(API35) 에뮬레이터.')
doc.add_paragraph('강의 호환: POST /api-token-auth/ → JWT 발급; Authorization: JWT <token>; POST /api_root/Post/ multipart 사진·제목·설명 전송. API GET은 JSON Array입니다. 클래스 존재 여부가 0→1로 변할 때 새 이벤트를 전송하고 동일 클래스가 계속 보이는 동안 반복 등록하지 않습니다. 실패 이벤트는 파일 outbox에 남겨 재시도합니다.')
doc.add_paragraph('실제 추론은 Ultralytics 공개 bus.jpg 정지 이미지로 검증했습니다. 웹캠/RTSP 실시간 영상은 이번 환경에서 테스트하지 않았습니다. HTTP 응답 유실 후 재시도 시 중복 등록 가능성이 있습니다. 기록 API는 계정별로 제한하지만 미디어 UUID URL 자체는 공개이므로 실제 사생활 영상 서비스에는 보호된 미디어 전달 구성이 필요합니다.')
for filename,(title,caption) in FIGURES.items():
    path=E/filename
    if not path.exists(): continue
    doc.add_page_break()
    doc.add_heading(title,level=1)
    with Image.open(path) as image: width,height=image.size
    display_width=min(6.1,6.5*width/height)
    p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(path),width=Inches(display_width))
    doc.add_paragraph(caption)
    doc.add_paragraph(f'원본: docs/evidence/{filename} · {width}×{height}px. 원본 데이터 내장, 표시 크기만 조정.')
doc.add_page_break()
doc.add_heading('재현 방법 및 참고',level=1)
doc.add_paragraph('설치·실행·테스트는 루트 및 각 프로젝트의 README.md를 참조합니다. 원본 소스 기본 실행 명령은 YOLOv5/evidence/baseline-command.txt, 해시 검증은 baseline-run.json, 수정 검출기 결과는 docs/evidence/edge-integration.json, Android 실행 기록은 android-runtime.json에 있습니다.')
doc.add_paragraph('증빙 재생성: scripts/capture_web.py, scripts/capture_android.py, scripts/verify_integration.py, scripts/build_report.py. 계정은 외부 비밀 파일로 전달하며 비밀번호/JWT를 Git이나 보고서에 넣지 않습니다.')
doc.add_paragraph('PythonAnywhere 배포·백업·복구는 docs/PYTHONANYWHERE.md를 참조합니다. 실제 배포 결과는 cloud-deployment.json, YOLO 전송은 cloud-edge-integration.json, 실제 HTTPS 기능 검증은 cloud-integration.json, 모바일 클라우드 검증은 android-cloud-runtime.json에 있습니다.')
doc.add_paragraph('기준 강의: ch08. Django와 YOLO를 이용한 침입자 감시 시스템_v1.8.pdf 3·6·8–13쪽. 원본 모델·이미지 출처와 라이선스는 YOLOv5/README.md 및 ASSETS.md, 원본 소스는 upstream-source.json에 있습니다.')
doc.add_paragraph('공식 배포 문서: https://help.pythonanywhere.com/pages/DeployExistingDjangoProject/')
doc.save(OUTPUT)
print(OUTPUT)
