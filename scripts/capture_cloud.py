"""Capture this assessment's deployed Django app, preserving local captures."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
E = ROOT / "docs/evidence"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--credentials", type=Path, required=True)
    args = parser.parse_args()
    credentials = json.loads(args.credentials.read_text())
    deployment = json.loads((E / "cloud-deployment.json").read_text())
    base = deployment["server"].rstrip("/")
    edge = json.loads((E / "cloud-edge-integration.json").read_text())
    post_id = edge["verified_post"]["id"]
    captures = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless=True
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1080})
        response = page.goto(base + "/accounts/login/", wait_until="networkidle")
        assert response.status == 200
        page.locator('[name="username"]').fill(credentials["username"])
        page.locator('[name="password"]').fill(credentials["password"])
        page.locator('button[type="submit"]').first.click()
        page.wait_for_load_state("networkidle")
        assert "/accounts/login/" not in page.url
        for name, path in [
            ("cloud-feed.png", "/"),
            ("cloud-detail.png", f"/posts/{post_id}/"),
            ("cloud-api.png", "/api_root/Post/"),
        ]:
            response = page.goto(base + path, wait_until="networkidle")
            assert response.status == 200
            page.screenshot(path=str(E / name), full_page=True)
            captures.append({"file": name, "url": page.url, "status": response.status})
        browser.close()
    (E / "cloud-captures.json").write_text(json.dumps({
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "post_id": post_id, "captures": captures,
    }, ensure_ascii=False, indent=2))
    print(f"Captured {len(captures)} deployed Django browser views")


if __name__ == "__main__":
    main()
