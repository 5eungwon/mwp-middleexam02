"""Capture the running Django application using a real Chrome browser."""
import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--credentials", required=True, type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, default=Path("docs/evidence"))
    args = parser.parse_args()
    credentials = json.loads(args.credentials.read_text())
    args.output.mkdir(parents=True, exist_ok=True)
    base = args.base_url.rstrip("/")
    captures = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            headless=True,
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1080}, device_scale_factor=1)
        page.goto(base + "/accounts/login/", wait_until="networkidle")
        page.screenshot(path=str(args.output / "web-login.png"), full_page=True)
        captures.append({"file": "web-login.png", "url": page.url, "title": "웹 로그인"})
        page.locator('[name="username"]').fill(credentials["username"])
        page.locator('[name="password"]').fill(credentials["password"])
        page.locator('button[type="submit"]').first.click()
        page.wait_for_load_state("networkidle")
        assert "/accounts/login" not in page.url, "Browser login failed"
        for filename, path, title in [
            ("web-feed.png", "/", "검출 사진 웹 목록"),
            ("web-unread.png", "/?unread=1", "미확인 필터"),
            ("web-search.png", "/?search=person", "검색 결과"),
            ("web-api.png", "/api_root/Post/", "강의 JSON Array API"),
        ]:
            response = page.goto(base + path, wait_until="networkidle")
            assert response.status == 200, f"{title}: HTTP {response.status}"
            page.screenshot(path=str(args.output / filename), full_page=True)
            captures.append({"file": filename, "url": page.url, "title": title})
        edge_path = args.output / "edge-integration.json"
        if edge_path.exists():
            edge = json.loads(edge_path.read_text())
            post_id = edge["verified_post"]["id"]
            page.goto(base + f"/posts/{post_id}/", wait_until="networkidle")
            page.screenshot(path=str(args.output / "web-detail.png"), full_page=True)
            captures.append({"file": "web-detail.png", "url": page.url, "title": "YOLO 전송 사진 상세"})
            if page.get_by_text("✓ 확인 완료", exact=True).count():
                page.screenshot(path=str(args.output / "web-acknowledged.png"), full_page=True)
                captures.append({"file": "web-acknowledged.png", "url": page.url, "title": "Android 확인 처리 서버 반영"})
        browser.close()
    (args.output / "web-captures.json").write_text(json.dumps(captures, ensure_ascii=False, indent=2))
    print(f"Captured {len(captures)} real browser views")


if __name__ == "__main__":
    main()
