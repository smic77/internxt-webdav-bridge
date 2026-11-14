#!/usr/bin/env python3
"""Container healthcheck: authenticated request against the local WebDAV server.

Uses WEBDAV_USERNAME / WEBDAV_PASSWORD from the environment, so it works
whatever credentials the stack defines. Exit 0 = healthy, 1 = unhealthy.
"""
import base64
import os
import sys
import urllib.error
import urllib.request

user = os.environ.get("WEBDAV_USERNAME", "admin")
password = os.environ.get("WEBDAV_PASSWORD", "changeme")
token = base64.b64encode(f"{user}:{password}".encode()).decode()

req = urllib.request.Request(
    "http://127.0.0.1:8000/",
    method="PROPFIND",
    headers={"Authorization": f"Basic {token}", "Depth": "0"},
)
try:
    with urllib.request.urlopen(req, timeout=8) as resp:
        sys.exit(0 if resp.status < 400 else 1)
except urllib.error.HTTPError as e:
    # 207 Multi-Status is the normal PROPFIND answer; anything >= 400 is a failure
    sys.exit(0 if e.code < 400 else 1)
except Exception:
    sys.exit(1)
