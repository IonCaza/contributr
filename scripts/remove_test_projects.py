#!/usr/bin/env python3
"""
Remove test/fixture projects via the API.

Criteria (any match):
  - name starts with "fixture"
  - name starts with "project-"
  - name contains "test project" (case-insensitive)

Never removed: project named "NAV AI" (case-insensitive).

Uses credentials from env API_USERNAME / API_PASSWORD (default: tester / tester).
API base from API_URL (default: http://localhost:8000/api).
"""
from __future__ import annotations

import os
import sys

try:
    import requests
except ImportError:
    print("Install requests: pip install requests", file=sys.stderr)
    sys.exit(1)

API_URL = os.environ.get("API_URL", "http://localhost:8000/api").rstrip("/")
API_USERNAME = os.environ.get("API_USERNAME", "tester")
API_PASSWORD = os.environ.get("API_PASSWORD", "tester")


def is_test_project(name: str) -> bool:
    n = name.strip()
    if n.upper() == "NAV AI":
        return False
    if n.startswith("fixture"):
        return True
    if n.startswith("project-"):
        return True
    if "test project" in n.lower():
        return True
    return False


def main() -> int:
    session = requests.Session()
    session.headers["Content-Type"] = "application/json"

    # Login
    r = session.post(
        f"{API_URL}/auth/login",
        json={"username": API_USERNAME, "password": API_PASSWORD},
        timeout=30,
    )
    if r.status_code != 200:
        print(f"Login failed: {r.status_code} {r.text}", file=sys.stderr)
        return 1
    data = r.json()
    token = data.get("access_token")
    if not token:
        print("Login response missing access_token", file=sys.stderr)
        return 1
    session.headers["Authorization"] = f"Bearer {token}"

    # List projects
    r = session.get(f"{API_URL}/projects", timeout=30)
    if r.status_code != 200:
        print(f"List projects failed: {r.status_code} {r.text}", file=sys.stderr)
        return 1
    projects = r.json()

    to_delete = [p for p in projects if is_test_project(p.get("name", ""))]
    if not to_delete:
        print("No test/fixture projects found.")
        return 0

    print(f"Found {len(to_delete)} project(s) to remove:")
    for p in to_delete:
        print(f"  - {p['name']} ({p['id']})")

    for p in to_delete:
        pid = p["id"]
        name = p["name"]
        r = session.delete(f"{API_URL}/projects/{pid}", timeout=30)
        if r.status_code in (200, 204):
            print(f"Deleted: {name}")
        else:
            print(f"Failed to delete {name}: {r.status_code} {r.text}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
