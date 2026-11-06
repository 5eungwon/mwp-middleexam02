"""Create a readable, static viewer for saved execution evidence."""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "docs/evidence"
sections = []
sources = [
    ("Django 자동 테스트", EVIDENCE / "backend-tests.txt"),
    ("엣지 출현 변화·전송 테스트", ROOT / "YOLOv5/evidence/tests.txt"),
    ("실제 YOLO 추론·서버 업로드", EVIDENCE / "edge-integration.json"),
    ("실제 HTTP 통합 검증", EVIDENCE / "integration.json"),
    ("Android APK 빌드", EVIDENCE / "android-build.txt"),
    ("PythonAnywhere 실제 배포·백업", EVIDENCE / "cloud-deployment.json"),
    ("PythonAnywhere 실제 HTTPS 기능 검증", EVIDENCE / "cloud-integration.json"),
]
for title, path in sources:
    if not path.exists():
        continue
    body = path.read_text(errors="replace")
    if len(body) > 14000:
        body = body[-14000:]
    sections.append(f'<section><h2>{html.escape(title)}</h2><p>{html.escape(str(path.relative_to(ROOT)))}</p><pre>{html.escape(body)}</pre></section>')
document = '''<!doctype html><html lang="ko"><meta charset="utf-8"><title>공통평가 02 · 실행 증빙</title>
<style>body{background:#f3f6fa;color:#14213d;font:16px -apple-system,BlinkMacSystemFont,sans-serif;margin:0;padding:48px;max-width:1400px}h1{font-size:36px}h2{font-size:25px}header p{color:#637187}section{background:white;padding:28px;border-radius:18px;margin:26px 0;border:1px solid #dbe3eb}section p{color:#66758a}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#152238;color:#d8e6f2;padding:24px;border-radius:12px;font:13px/1.6 Menlo,monospace}</style>
<header><p>모바일/웹서비스 프로젝트 · 공통평가 02</p><h1>실행 증빙 기록</h1><p>아래 내용은 실제 명령과 HTTP 요청으로 생성한 로그입니다. 인증 정보는 저장하지 않았습니다.</p></header>
'''+"\n".join(sections)+"</html>"
(EVIDENCE / "verification.html").write_text(document)
print(EVIDENCE / "verification.html")

baseline = ROOT / "YOLOv5/evidence/baseline-command.txt"
if baseline.exists():
    import re
    log = re.sub(r"\x1b\[[0-9;]*m", "", baseline.read_text())
    baseline_html = '''<!doctype html><html lang="ko"><meta charset="utf-8"><title>수정 전 공식 YOLOv5 detect.py 실행 증빙</title><style>body{font:15px -apple-system,sans-serif;color:#14213d;margin:0;padding:32px;background:#f3f6fa}h1{font-size:30px}main{display:grid;grid-template-columns:52% 48%;gap:22px}img{height:800px;max-width:100%;object-fit:contain;background:white;border-radius:14px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#14213d;color:#e4edf7;padding:22px;border-radius:14px;font:12px/1.7 Menlo,monospace}p{color:#637187}</style><h1>수정 전 공식 YOLOv5 detect.py 실행</h1><p>v7.0 · 원본 파일 변경 없음 · 실제 정지 이미지 추론 결과와 저장된 명령 실행 로그</p><main><img src="../../YOLOv5/evidence/baseline/bus.jpg"><div><h2>3 persons · 1 bus</h2><pre>'''+html.escape(log)+'''</pre><p>실행 전후 원본 SHA-256 일치는 baseline-run.json에서 확인.</p></div></main></html>'''
    (EVIDENCE / "baseline.html").write_text(baseline_html)
