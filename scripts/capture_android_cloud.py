"""Capture the real native client connected to PythonAnywhere, without secrets.

Requires a running Android emulator and completed cloud deployment/YOLO upload.
Uses the installed APK; never reinstalls or patches the app. All screenshots have
distinct cloud filenames, so the original local-run evidence remains intact.
"""
import argparse
import hashlib
import io
import json
import re
import shlex
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from PIL import Image, ImageChops, ImageOps, ImageStat

from capture_android import OUT, PACKAGE, ROOT, adb, capture, locate, tap, wait_for


def type_text(value):
    # adb's remote shell parses arguments again. Quote values before that hop.
    adb("shell", "input", "text", shlex.quote(value.replace(" ", "%s")))


def bounds(node):
    return tuple(map(int, re.findall(r"\d+", node.attrib["bounds"])))


def image_error(screenshot, node, remote_image, fit):
    box = bounds(node)
    actual = Image.open(io.BytesIO(screenshot)).convert("RGB").crop(box)
    if fit == "cover":
        expected = ImageOps.fit(remote_image, actual.size, method=Image.Resampling.BILINEAR)
    else:
        expected = Image.new("RGB", actual.size, "white")
        contained = ImageOps.contain(remote_image, actual.size, method=Image.Resampling.BILINEAR)
        expected.paste(contained, ((actual.width - contained.width) // 2,
                                  (actual.height - contained.height) // 2))
    error = sum(ImageStat.Stat(ImageChops.difference(actual, expected)).mean) / 3
    return round(error, 4), box


def capture_loaded_photo(filename, image_description, remote_image, fit):
    # Native ImageView has no exposed bitmap field. Compare the actual device
    # pixels with the HTTPS image after matching that view's layout transform.
    best = None
    for _ in range(12):
        node = wait_for(image_description, "content-desc", attempts=2)
        screenshot = adb("exec-out", "screencap", "-p", binary=True)
        error, box = image_error(screenshot, node, remote_image, fit)
        if best is None or error < best[0]:
            best = (error, screenshot, box)
        if error < 18:
            (OUT / filename).write_bytes(screenshot)
            return {"screenshot": filename, "image_bounds": list(box),
                    "remote_image_pixel_mae": error, "loaded_photo_verified": True}
        time.sleep(.7)
    raise RuntimeError("Native photo pixels did not match the HTTPS YOLO image; screenshot not accepted")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--base-url", default="https://asdfgh0986.pythonanywhere.com")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    if not base.startswith("https://"):
        raise RuntimeError("Cloud evidence requires HTTPS")
    for filename in ("cloud-deployment.json", "cloud-edge-integration.json"):
        if not (OUT / filename).exists():
            raise RuntimeError("Cloud evidence is not ready: " + filename)
    credentials = json.loads(args.credentials.read_text())
    edge = json.loads((OUT / "cloud-edge-integration.json").read_text())
    expected_id = edge.get("verified_post", {}).get("id")
    if expected_id is None:
        uploaded = [item for frame in edge.get("frames", []) for item in frame.get("uploaded", [])]
        if not uploaded:
            raise RuntimeError("Cloud YOLO evidence has no uploaded post ID")
        expected_id = uploaded[-1]["post_id"]

    session = requests.Session()
    login = session.post(base + "/api-token-auth/", data=credentials, timeout=30)
    login.raise_for_status()
    session.headers["Authorization"] = "JWT " + login.json()["token"]
    response = session.get(f"{base}/api_root/Post/{expected_id}/", timeout=30)
    response.raise_for_status()
    remote_post = response.json()
    if remote_post["acknowledged"]:
        raise RuntimeError("Expected an unread cloud event before Android verification")
    image_url = remote_post["image"]
    if not image_url.startswith(base + "/"):
        raise RuntimeError("Cloud image URL is not served from the HTTPS deployment")
    image_response = session.get(image_url, timeout=30)
    image_response.raise_for_status()
    remote_image = Image.open(io.BytesIO(image_response.content)).convert("RGB")
    posts_response = session.get(base + "/api_root/Post/", timeout=30)
    posts_response.raise_for_status()
    posts = posts_response.json()

    installed_path = adb("shell", "pm", "path", PACKAGE).strip().removeprefix("package:")
    installed_sha = hashlib.sha256(adb("exec-out", "cat", installed_path, binary=True)).hexdigest()
    build_apk = ROOT / "PhotoViewer/app/build/outputs/apk/debug/app-debug.apk"
    build_sha = hashlib.sha256(build_apk.read_bytes()).hexdigest()
    if installed_sha != build_sha:
        raise RuntimeError("Installed APK differs from the compiled APK; no app replacement performed")

    adb("shell", "pm", "clear", PACKAGE)
    adb("shell", "am", "start", "-n", PACKAGE + "/.MainActivity")
    server = wait_for("서버 주소", "content-desc")
    tap(server)
    time.sleep(.7)
    adb("shell", "input", "keyevent", "123")  # MOVE_END
    adb("shell", "input", "keyevent", *(["67"] * 100))  # DEL, no clipboard
    type_text(base)
    adb("shell", "input", "keyevent", "4")
    time.sleep(.6)
    if wait_for("서버 주소", "content-desc").attrib.get("text") != base:
        raise RuntimeError("Cloud server URL input check failed")
    # This image deliberately precedes entering any username or password.
    capture("android-cloud-login.png")

    tap(wait_for("아이디", "content-desc"))
    time.sleep(.7)
    type_text(credentials["username"])
    adb("shell", "input", "keyevent", "61")  # TAB avoids keyboard movement
    time.sleep(.5)
    type_text(credentials["password"])
    adb("shell", "input", "keyevent", "4")
    time.sleep(.6)
    if (wait_for("아이디", "content-desc").attrib.get("text") != credentials["username"]
            or not wait_for("비밀번호", "content-desc").attrib.get("text")):
        raise RuntimeError("Native login input focus check failed; credentials not logged")
    tap(wait_for("로그인"))
    wait_for("감지 기록", attempts=15)

    # The uploaded fixture is normally newest. A unique event search avoids
    # selecting another person's identically named detection if more exist.
    event_match = re.search(r"Edge event: ([a-f0-9]+)", remote_post.get("text", ""))
    if posts and posts[0]["id"] != expected_id:
        if event_match is None:
            raise RuntimeError("Cannot identify the cloud fixture uniquely in the feed")
        tap(wait_for("객체 또는 내용 검색", "content-desc"))
        type_text(event_match.group(1))
        adb("shell", "input", "keyevent", "4")
        tap(wait_for("검색"))
    card_description = remote_post["title"] + ", 미확인, 상세 보기"
    wait_for(card_description, "content-desc", attempts=15)
    image_description = "감지 사진: " + remote_post["title"]
    feed = capture_loaded_photo("android-cloud.png", image_description, remote_image, "cover")
    tap(wait_for(card_description, "content-desc"))
    wait_for("감지 내용", attempts=12)
    detail = capture_loaded_photo("android-cloud-detail.png", image_description, remote_image, "contain")
    if event_match and locate(event_match.group(1), contains=True) is None:
        raise RuntimeError("Detail does not display the expected cloud event ID")
    # Do not click acknowledge: root still needs unread cloud browser evidence.
    after = session.get(f"{base}/api_root/Post/{expected_id}/", timeout=30)
    after.raise_for_status()
    if after.json()["acknowledged"]:
        raise RuntimeError("Cloud event unexpectedly became acknowledged")
    report = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "package": PACKAGE,
        "device": adb("shell", "getprop", "ro.product.model").strip(),
        "android_release": adb("shell", "getprop", "ro.build.version.release").strip(),
        "sdk": adb("shell", "getprop", "ro.build.version.sdk").strip(),
        "server_in_app": base,
        "transport": "HTTPS with platform certificate verification",
        "post_id": expected_id,
        "photo_source": "actual cloud YOLOv5 inference upload",
        "image_url": image_url,
        "image_sha256": hashlib.sha256(image_response.content).hexdigest(),
        "image_dimensions": list(remote_image.size),
        "installed_apk_sha256": installed_sha,
        "installed_apk_unchanged_from_build": installed_sha == build_sha,
        "read_state_before": remote_post["acknowledged"],
        "read_state_after": after.json()["acknowledged"],
        "feed": feed,
        "detail": detail,
        "verified": ["native_server_url_input", "native_https_login", "cloud_post_id",
                     "feed_with_network_loaded_cloud_yolo_photo", "detail_with_same_cloud_event",
                     "installed_apk_unchanged", "unread_state_preserved"],
        "result": "PASS",
    }
    (OUT / "android-cloud-runtime.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print("PASS: unchanged native APK, HTTPS cloud login, matching YOLO photo pixels, feed/detail, unread preserved")


if __name__ == "__main__":
    main()
