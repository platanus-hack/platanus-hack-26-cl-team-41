"""Share only the Pi's latest JPEG with the Nexa web console."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen


MAX_BYTES = 256 * 1024
DEFAULT_SITE = "https://nexa-rover-demo.onrender.com"
DEFAULT_CAMERA = "http://172.16.0.127:8080/snapshot"
KEY_FILE = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Nexa" / "camera-keys.json"


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def load_keys(*, create=False):
    if create:
        KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(KEY_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump({role: secrets.token_hex(32) for role in ("publish", "view")}, handle)
    if not KEY_FILE.is_file():
        raise ValueError("Camera pairing is missing. Run camera_relay.py --prepare first.")
    keys = json.loads(KEY_FILE.read_text(encoding="utf-8"))
    if not all(isinstance(keys.get(role), str) and re.fullmatch(r"[0-9a-f]{64}", keys[role])
               for role in ("publish", "view")):
        raise ValueError("Camera pairing file is invalid")
    return keys


def share(camera_url, site, keys):
    url = urlsplit(site)
    if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError("The Nexa site must be an HTTPS address")
    endpoint = site.rstrip("/") + "/api/rover-camera"
    print(f"Share the camera at {camera_url} with {site}?")
    if input("Type SHARE to start. Press Ctrl+C to stop: ").strip().upper() != "SHARE":
        return

    transport = build_opener(NoRedirects())
    auth = {"Authorization": f"Bearer {keys['publish']}"}
    headers = {**auth, "Content-Type": "image/jpeg"}
    started = False
    last_error = ""
    try:
        while True:
            try:
                with urlopen(camera_url, timeout=3) as response:
                    image = response.read(MAX_BYTES + 1)
                if len(image) > MAX_BYTES or not image.startswith(b"\xff\xd8") or not image.endswith(b"\xff\xd9"):
                    raise ValueError("Camera must provide a JPEG snapshot up to 256 KiB")
                with transport.open(Request(endpoint, data=image, headers=headers, method="POST"), timeout=8):
                    pass
                if not started:
                    print(f"Viewer: {site.rstrip('/')}/rover")
                    print(f"Viewer access code: {keys['view']}", flush=True)
                    started = True
                elif last_error:
                    print("Live feed resumed", flush=True)
                last_error = ""
                time.sleep(.65)
            except HTTPError as exc:
                # The deployed relay returns 401 or 503 until its paired digests are configured.
                if exc.url == endpoint and exc.code in (401, 503):
                    raise ValueError(f"The Nexa camera relay is not paired (HTTP {exc.code})") from exc
                message = f"Camera or relay HTTP {exc.code}; retrying"
                if message != last_error:
                    print(message, flush=True)
                last_error = message
                time.sleep(2)
            except (OSError, ValueError) as exc:
                message = f"Camera or relay unavailable: {exc}. Retrying"
                if message != last_error:
                    print(message, flush=True)
                last_error = message
                time.sleep(2)
    except KeyboardInterrupt:
        print("\nCamera sharing stopped.")
    finally:
        if started:
            try:
                with transport.open(Request(endpoint, headers=auth, method="DELETE"), timeout=3):
                    pass
            except OSError:
                pass  # The relay also expires frames after six seconds.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", default=DEFAULT_SITE)
    parser.add_argument("--camera-url", default=DEFAULT_CAMERA)
    parser.add_argument("--prepare", action="store_true", help="Create local pairing codes and print their public hashes")
    args = parser.parse_args()
    try:
        keys = load_keys(create=args.prepare)
        if args.prepare:
            for role, key in keys.items():
                print(f"NEXA_CAMERA_{role.upper()}_SHA256={hashlib.sha256(key.encode()).hexdigest()}")
        else:
            share(args.camera_url, args.site, keys)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
