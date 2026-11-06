"""Verify the live server without writing passwords or JWTs into evidence."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import requests


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("docs/evidence/integration.json"))
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    credentials = json.loads(args.credentials.read_text())
    checks = []

    def check(name, response, expected):
        checks.append({"check": name, "status": response.status_code, "expected": expected})
        assert response.status_code == expected, f"{name}: HTTP {response.status_code}"

    session = requests.Session()
    health = session.get(base + "/health/", timeout=20)
    check("health", health, 200)
    anonymous = session.get(base + "/api_root/Post/", timeout=20)
    check("anonymous_rejected", anonymous, 401)
    login = session.post(base + "/api-token-auth/", data=credentials, timeout=20)
    check("jwt_login", login, 200)
    session.headers["Authorization"] = "JWT " + login.json()["token"]
    with args.image.open("rb") as image:
        uploaded = session.post(base + "/api_root/Post/", data={
            "title": "통합 검증 · person 출현",
            "text": "실제 HTTP multipart 업로드·조회·검색·확인 처리 검증. 사진은 YOLOv5 검출 결과입니다.",
        }, files={"image": ("integration.jpg", image, "image/jpeg")}, timeout=30)
    check("multipart_upload", uploaded, 201)
    post = uploaded.json()
    post_id = post["id"]
    listing = session.get(base + "/api_root/Post/", timeout=20)
    check("lecture_json_array", listing, 200)
    assert isinstance(listing.json(), list)
    assert any(item["id"] == post_id for item in listing.json())
    search = session.get(base + "/api_root/Post/", params={"search": "통합 검증"}, timeout=20)
    check("search", search, 200)
    assert any(item["id"] == post_id for item in search.json())
    unread = session.get(base + "/api_root/Post/", params={"unread": "1"}, timeout=20)
    check("unread_before", unread, 200)
    assert any(item["id"] == post_id for item in unread.json())
    acknowledged = session.post(base + f"/api_root/Post/{post_id}/acknowledge/", timeout=20)
    check("acknowledge", acknowledged, 200)
    assert acknowledged.json()["acknowledged"] is True
    unread = session.get(base + "/api_root/Post/", params={"unread": "1"}, timeout=20)
    check("unread_after", unread, 200)
    assert not any(item["id"] == post_id for item in unread.json())
    image = session.get(post["image"], timeout=20)
    check("image_download", image, 200)
    assert image.headers.get("Content-Type", "").startswith("image/")
    report = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_url": base, "result": "PASS", "checks": checks,
        "post_id": post_id, "post": post,
        "note": "실행 중인 서버에 실제 HTTP 요청. 인증 정보는 기록하지 않음.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"PASS: {len(checks)} live HTTP checks; post {post_id}; {args.output}")


if __name__ == "__main__":
    main()
