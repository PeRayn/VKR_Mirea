import os
import random
import string
import sys

import httpx


BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")


def random_email() -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"smoke_{suffix}@example.com"


def assert_status(response: httpx.Response, expected: int, hint: str) -> None:
    if response.status_code != expected:
        print(f"{hint}: expected {expected}, got {response.status_code}, body={response.text}")
        sys.exit(1)


def main() -> None:
    email = random_email()
    password = "SuperPass123!"

    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        r = client.post("/auth/register", json={"email": email, "password": password})
        assert_status(r, 200, "register")
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        r = client.get("/auth/me", headers=headers)
        assert_status(r, 200, "auth/me")

        files = {"upload": ("smoke.txt", b"Smart Disk smoke test content.", "text/plain")}
        r = client.post("/files/upload", headers=headers, files=files)
        assert_status(r, 200, "upload")

        file_id = r.json()["id"]
        r = client.get("/files", headers=headers)
        assert_status(r, 200, "list files")
        if not r.json():
            print("list files: expected at least one file")
            sys.exit(1)

        r = client.post("/chats", headers=headers, json={"title": "Smoke chat"})
        assert_status(r, 200, "create chat")
        chat_id = r.json()["id"]

        r = client.post(
            f"/chats/{chat_id}/ask",
            headers=headers,
            json={"question": "Что содержится в smoke-файле?"},
        )
        assert_status(r, 200, "ask")

        r = client.delete(f"/files/{file_id}", headers=headers)
        assert_status(r, 200, "delete")

    print("SMOKE TEST PASSED")


if __name__ == "__main__":
    main()
