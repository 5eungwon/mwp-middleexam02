"""Drive and capture the real Android emulator. Never log login credentials."""
import argparse
import json
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests

ADB = str(Path.home() / "Library/Android/sdk/platform-tools/adb")
PACKAGE = "kr.ac.homeguard.photoviewer"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs/evidence"


def adb(*arguments, binary=False):
    return subprocess.check_output([ADB, *arguments], text=not binary, stderr=subprocess.DEVNULL)


def nodes():
    adb("shell", "uiautomator", "dump", "/sdcard/mwp02-ui.xml")
    return ET.fromstring(adb("shell", "cat", "/sdcard/mwp02-ui.xml")).iter("node")


def locate(value, attribute="text", contains=False):
    for node in nodes():
        candidate = node.attrib.get(attribute, "")
        if (value in candidate) if contains else (candidate == value):
            return node
    return None


def wait_for(value, attribute="text", contains=False, attempts=8):
    for _ in range(attempts):
        node = locate(value, attribute, contains)
        if node is not None:
            return node
        time.sleep(.5)
    raise RuntimeError(f"Android element not found: {value}")


def tap(node):
    x1, y1, x2, y2 = map(int, re.findall(r"\d+", node.attrib["bounds"]))
    adb("shell", "input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2))


def capture(name):
    time.sleep(.8)
    (OUT / name).write_bytes(adb("exec-out", "screencap", "-p", binary=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--credentials", type=Path, required=True)
    args = parser.parse_args()
    credentials = json.loads(args.credentials.read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    adb("shell", "pm", "clear", PACKAGE)
    adb("shell", "am", "start", "-n", PACKAGE + "/.MainActivity")
    wait_for("아이디", "content-desc")
    capture("android-login.png")
    # Tab changes focus without reusing coordinates while the soft keyboard
    # animates and moves the form.
    tap(wait_for("아이디", "content-desc"))
    time.sleep(.7)
    adb("shell", "input", "text", credentials["username"])
    adb("shell", "input", "keyevent", "61")
    time.sleep(.5)
    adb("shell", "input", "text", credentials["password"])
    adb("shell", "input", "keyevent", "4")
    time.sleep(.5)
    user_field = wait_for("아이디", "content-desc")
    password_field = wait_for("비밀번호", "content-desc")
    if user_field.attrib.get("text") != credentials["username"] or not password_field.attrib.get("text"):
        raise RuntimeError("Login input focus check failed; no credentials logged")
    tap(wait_for("로그인"))
    wait_for("감지 기록")
    wait_for("person, 미확인, 상세 보기", "content-desc")
    capture("android-feed.png")
    tap(wait_for("미확인"))
    wait_for("person, 미확인, 상세 보기", "content-desc")
    capture("android-unread.png")
    tap(wait_for("person, 미확인, 상세 보기", "content-desc"))
    wait_for("감지 내용")
    capture("android-detail.png")
    button = locate("이 기록 확인 완료로 표시")
    if button is None:
        adb("shell", "input", "swipe", "550", "1900", "550", "1000", "350")
        button = wait_for("이 기록 확인 완료로 표시")
    tap(button)
    wait_for("✓ 확인 완료")
    time.sleep(1)
    capture("android-acknowledged.png")
    session = requests.Session()
    login = session.post("http://127.0.0.1:8000/api-token-auth/", data=credentials, timeout=20)
    login.raise_for_status()
    session.headers["Authorization"] = "JWT " + login.json()["token"]
    edge = json.loads((OUT / "edge-integration.json").read_text())
    post_id = edge["verified_post"]["id"]
    response = session.get(f"http://127.0.0.1:8000/api_root/Post/{post_id}/", timeout=20)
    response.raise_for_status()
    assert response.json()["acknowledged"] is True
    report = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "package": PACKAGE,
        "device": adb("shell", "getprop", "ro.product.model").strip(),
        "android_release": adb("shell", "getprop", "ro.build.version.release").strip(),
        "sdk": adb("shell", "getprop", "ro.build.version.sdk").strip(),
        "server_in_app": "http://10.0.2.2:8000",
        "post_id": post_id, "photo_source": "real YOLOv5 inference upload",
        "verified": ["login", "feed_with_yolo_photo", "unread_filter", "detail", "acknowledge", "server_state_acknowledged"],
        "result": "PASS",
    }
    (OUT / "android-runtime.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print("PASS: native Android login, YOLO photo feed/detail, unread filter, acknowledgement + server state")


if __name__ == "__main__":
    main()
