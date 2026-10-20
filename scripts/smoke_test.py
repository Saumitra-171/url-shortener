"""Smoke test for a deployed instance:  python scripts/smoke_test.py https://your-app.onrender.com"""
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8000"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # hand the 302 back to us instead of following it


opener = urllib.request.build_opener(NoRedirect)


def call(method, path, *, body=None, form=None, token=None, timeout=90):
    """Returns (status, parsed_json_or_text). The long timeout covers a cold start."""
    headers, data = {}, None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        response = opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as error:  # 3xx/4xx/5xx arrive here
        response = error
    raw = response.read().decode()
    try:
        return response.status, json.loads(raw) if raw else None
    except ValueError:
        return response.status, raw


failures = 0


def check(name, ok, detail=""):
    global failures
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"   {detail}"))
    failures += 0 if ok else 1


print(f"Smoke test against {BASE} (the first request may take a minute if the service was asleep)")

status, body = call("GET", "/health")
check("liveness", status == 200 and body.get("status") == "ok", (status, body))

status, body = call("GET", "/health/ready")
check("readiness (database up)", status == 200 and body.get("database") == "up", (status, body))
print(f"      redis: {body.get('redis') if isinstance(body, dict) else '?'}")

email = f"smoke-{uuid.uuid4().hex[:10]}@example.com"
status, body = call("POST", "/auth/register", body={"email": email, "password": "smoke-test-pass"})
check("register", status == 201, (status, body))

status, body = call("POST", "/auth/login", form={"username": email, "password": "smoke-test-pass"})
token = body.get("access_token") if isinstance(body, dict) else None
check("login", status == 200 and token, (status, body))
if not token:
    sys.exit("cannot continue without a token")

status, body = call("POST", "/shorten", body={"url": "https://example.com"}, token=token)
code = body.get("short_code") if isinstance(body, dict) else None
check("create short link", status == 201 and code, (status, body))
if not code:
    sys.exit("cannot continue without a short code")

request = urllib.request.Request(f"{BASE}/{code}")
try:
    response = opener.open(request, timeout=60)
except urllib.error.HTTPError as error:
    response = error
check("redirect is a 302 to the target", response.status == 302 and response.headers.get("location") == "https://example.com",
      (response.status, response.headers.get("location")))

# Clicks are written by the background worker, so poll instead of expecting an instant result.
clicks = 0
deadline = time.time() + 45
while time.time() < deadline:
    status, body = call("GET", f"/{code}/analytics", token=token)
    clicks = body["stats"]["click_count"] if status == 200 else -1
    if clicks == 1:
        break
    time.sleep(3)
check("click recorded by the worker", clicks == 1, f"click_count={clicks} after 45s")

status, _ = call("DELETE", f"/{code}", token=token)
check("delete", status == 204, status)
status, _ = call("GET", f"/{code}")
check("deleted link returns 404", status == 404, status)

print("\nAll checks passed." if not failures else f"\n{failures} check(s) FAILED.")
sys.exit(1 if failures else 0)